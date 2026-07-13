#!/usr/bin/env python3
"""合格率（pass_rate）の安全な補完パイプライン。

リポジトリ方針「数値は必ず公式の一次情報で確認」を担保するため、
人手での穴埋めを **証跡（出典URL＋確認日）必須** で受け入れ、検証してから
正本の data/overrides.csv にだけ反映する。憶測値の混入を機械的に防ぐ。

使い方:
  1) 穴埋めリストを書き出す（GSC表示回数の多い順に並ぶ）
       python3 tools/pass_rate_pipeline.py export
       → data/worklist_pass_rate.csv を生成

  2) 生成された CSV の pass_rate / source_url / checked_at 列を、各資格の
     公式サイト等の一次情報を確認して記入する（記入した行だけが反映対象）

  3) 検証して overrides.csv に反映
       python3 tools/pass_rate_pipeline.py apply
       → 検証OKの行のみ data/overrides.csv に pass_rate と source_checked_at を反映
       → 証跡を data/pass_rate_sources.csv に追記（監査用）
       → その後 build_seed.py → validate.py → build_pages.py を実行して再生成

設計上の安全策:
  - pass_rate を記入した行は source_url（出典）と checked_at（確認日）が両方必須。
    どちらか欠けた行は「証跡不足」として却下し、overrides を書き換えない。
  - checked_at は YYYY-MM-DD 形式のみ許可。
  - 既に overrides.csv に pass_rate がある slug は既定でスキップ（--overwrite で上書き可）。
  - apply は追記・更新のみ。空欄で提出した行は既存値を消さない。
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CERT = ROOT / "data" / "certifications.csv"
OVERRIDES = ROOT / "data" / "overrides.csv"
WORKLIST = ROOT / "data" / "worklist_pass_rate.csv"
SOURCES = ROOT / "data" / "pass_rate_sources.csv"
GSC_IMP = ROOT / "data" / "gsc_page_impressions.json"

OVERRIDE_COLS = ["slug", "authority", "official_url", "fee", "exam_format",
                 "eligibility", "frequency", "pass_rate", "source_checked_at"]
WORKLIST_COLS = ["priority", "gsc_impressions", "slug", "name", "category",
                 "official_url", "current_pass_rate",
                 "pass_rate", "source_url", "checked_at"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_gsc():
    """GSC のページ別表示回数（slug -> impressions）。無ければ空。"""
    if GSC_IMP.exists():
        return {k: int(v) for k, v in json.load(GSC_IMP.open(encoding="utf-8")).items()}
    return {}


def cmd_export(args):
    certs = read_csv(CERT)
    if not certs:
        sys.exit(f"ERROR: {CERT} が見つかりません。先に build_seed.py を実行してください。")
    ov = {r["slug"]: r for r in read_csv(OVERRIDES)}
    gsc = load_gsc()

    targets = []
    for r in certs:
        if r.get("is_bucket") == "1" or r.get("is_duplicate") == "1":
            continue
        cur = (r.get("pass_rate") or "").strip()
        if cur and not args.include_filled:
            continue
        targets.append(r)

    # GSC表示回数が多い順 → published優先 → 名前順
    def sort_key(r):
        return (-gsc.get(r["slug"], 0),
                0 if r.get("status") == "published" else 1,
                r.get("name", ""))
    targets.sort(key=sort_key)

    with WORKLIST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=WORKLIST_COLS)
        w.writeheader()
        for i, r in enumerate(targets, 1):
            imp = gsc.get(r["slug"], 0)
            w.writerow({
                "priority": "★GSC上位" if imp > 0 else "",
                "gsc_impressions": imp or "",
                "slug": r["slug"],
                "name": r.get("name", ""),
                "category": r.get("category", ""),
                "official_url": r.get("official_url", ""),
                "current_pass_rate": (r.get("pass_rate") or "").strip(),
                "pass_rate": "",
                "source_url": "",
                "checked_at": "",
            })
    n_gsc = sum(1 for r in targets if gsc.get(r["slug"], 0) > 0)
    print(f"書き出し: {WORKLIST.relative_to(ROOT)}（{len(targets)}件・うちGSC表示あり {n_gsc}件を上位に配置）")
    print("→ pass_rate / source_url / checked_at を公式の一次情報で記入し、apply を実行してください。")


def _validate_row(row, overwrite, existing):
    """(ok, value_dict|None, message)。pass_rate 空欄の行は (None,...) でスキップ扱い。"""
    slug = (row.get("slug") or "").strip()
    pr = (row.get("pass_rate") or "").strip()
    if not slug:
        return False, None, "slug が空"
    if not pr:
        return None, None, "pass_rate 空欄（スキップ）"
    src = (row.get("source_url") or "").strip()
    at = (row.get("checked_at") or "").strip()
    if not src:
        return False, None, f"{slug}: source_url（出典）が未記入 — 証跡不足のため却下"
    if not DATE_RE.match(at):
        return False, None, f"{slug}: checked_at が YYYY-MM-DD 形式でない（'{at}'）"
    if "%" not in pr and "非公表" not in pr and "非公開" not in pr:
        return False, None, f"{slug}: pass_rate に % も『非公表』も無い（'{pr}'）— 形式を確認"
    if slug in existing and existing[slug] and not overwrite:
        return False, None, f"{slug}: 既に pass_rate 登録済み（--overwrite で上書き）"
    return True, {"pass_rate": pr, "source_checked_at": at, "source_url": src}, f"{slug}: OK"


def cmd_apply(args):
    rows = read_csv(WORKLIST)
    if not rows:
        sys.exit(f"ERROR: {WORKLIST} が見つかりません。先に export を実行してください。")

    ov_rows = read_csv(OVERRIDES)
    ov_by_slug = {r["slug"]: r for r in ov_rows}
    existing_pr = {s: (r.get("pass_rate") or "").strip() for s, r in ov_by_slug.items()}

    applied, rejected, skipped = [], [], 0
    audit = []
    for row in rows:
        ok, val, msg = _validate_row(row, args.overwrite, existing_pr)
        if ok is None:
            skipped += 1
            continue
        if not ok:
            rejected.append(msg)
            continue
        slug = row["slug"].strip()
        target = ov_by_slug.get(slug)
        if not target:
            rejected.append(f"{slug}: overrides.csv に該当行なし")
            continue
        target["pass_rate"] = val["pass_rate"]
        target["source_checked_at"] = val["source_checked_at"]
        applied.append(msg)
        audit.append({"slug": slug, "pass_rate": val["pass_rate"],
                      "source_url": val["source_url"],
                      "checked_at": val["source_checked_at"]})

    if rejected:
        print("却下（反映されません）:")
        for m in rejected:
            print("  ✗", m)
    if args.dry_run:
        print(f"\n[dry-run] 反映予定 {len(applied)}件 / 却下 {len(rejected)}件 / スキップ {skipped}件")
        return

    if applied:
        with OVERRIDES.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=OVERRIDE_COLS)
            w.writeheader()
            w.writerows(ov_rows)
        # 監査証跡を追記
        write_header = not SOURCES.exists()
        with SOURCES.open("a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["slug", "pass_rate", "source_url", "checked_at"])
            if write_header:
                w.writeheader()
            w.writerows(audit)

    print(f"\n反映 {len(applied)}件 / 却下 {len(rejected)}件 / スキップ {skipped}件")
    if applied:
        print(f"→ overrides.csv 更新・{SOURCES.relative_to(ROOT)} に証跡追記")
        print("  次を実行して再生成してください:")
        print("    python3 tools/build_seed.py && python3 tools/validate.py && python3 tools/build_pages.py")


def main():
    p = argparse.ArgumentParser(description="合格率の安全な補完パイプライン")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="穴埋めリスト worklist_pass_rate.csv を書き出す")
    e.add_argument("--include-filled", action="store_true",
                   help="既に合格率がある資格も一覧に含める")
    e.set_defaults(func=cmd_export)
    a = sub.add_parser("apply", help="記入済みリストを検証して overrides.csv に反映")
    a.add_argument("--overwrite", action="store_true", help="既存の pass_rate も上書きする")
    a.add_argument("--dry-run", action="store_true", help="反映せず検証結果だけ表示")
    a.set_defaults(func=cmd_apply)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
