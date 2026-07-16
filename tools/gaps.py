#!/usr/bin/env python3
"""データ網羅性のギャップを需要加重で可視化する作業リスト生成ツール。

「どの資格の・どの項目を・どの順で埋めるか」を機械的に出力する。
公式一次情報の確認作業（人手）を最短化するための優先度付けであり、
値そのものを推測・生成することはしない（SOURCES.md の方針に従う）。

使い方:
    python3 tools/gaps.py            # 上位の優先ギャップを表示
    python3 tools/gaps.py --limit 40 # 表示件数
    python3 tools/gaps.py --csv out.csv  # 作業リストをCSV出力

需要シグナル: 受験者数(applicants) / 関連参照数(related_slugs) / 学習時間整備済み
穴シグナル: published だが fee / pass_rate が空、要確認(type)、未整備(seed)
"""
import argparse
import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def load(name):
    p = DATA / name
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(s):
    m = re.search(r"([\d,]{2,})", s or "")
    return int(m.group(1).replace(",", "")) if m else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--csv", default="")
    args = ap.parse_args()

    rows = load("certifications.csv")
    exam = {r["slug"]: r for r in load("exam_details.csv")}
    study = {r["slug"]: r for r in load("study_time.csv")}

    # 需要スコア
    ref = Counter()
    for r in rows:
        for sep in (" ", ","):
            for s in (r.get("related_slugs") or "").split(sep):
                if s.strip():
                    ref[s.strip()] += 1

    def applicants(slug):
        return num(exam.get(slug, {}).get("applicants", ""))

    def demand(r):
        s = min(applicants(r["slug"]) // 1000, 30)
        s += ref.get(r["slug"], 0) * 2
        if study.get(r["slug"], {}).get("study_hours", "").strip():
            s += 2
        return s

    pub = [r for r in rows if r["status"] == "published"]

    # ギャップ収集: (優先度, 需要, slug, 名前, 種別, メモ)
    work = []
    for r in pub:
        d = demand(r)
        if not r["fee"].strip():
            # 都道府県/団体で額が割れる資格は原則スキップ対象（メモで注意喚起）
            note = "受験料が空"
            work.append((d, r, "fee", note))
        if not r["pass_rate"].strip() and applicants(r["slug"]) > 0:
            work.append((d, r, "pass_rate", "人気だが合格率が空"))
    for r in rows:
        if r["type"] == "要確認":
            work.append((demand(r), r, "type", "区分未確定(国家/公的/民間)"))
    for r in rows:
        if r["status"] == "seed":
            work.append((demand(r), r, "status", "未整備(実施団体の有無を確認)"))

    work.sort(key=lambda t: -t[0])

    print(f"# データ網羅性ギャップ 作業リスト（需要順・上位{args.limit}）\n")
    print(f"{'需要':>4}  {'種別':<10} {'slug':<8} {'資格名':<28} メモ")
    for d, r, kind, note in work[:args.limit]:
        print(f"{d:>4}  {kind:<10} {r['slug']:<8} {r['name'][:26]:<28} {note}")

    # サマリ
    kinds = Counter(k for _, _, k, _ in work)
    print("\n# 種別ごとの残数")
    labels = {"fee": "受験料が空", "pass_rate": "合格率が空(人気)",
              "type": "区分要確認", "status": "未整備(seed)"}
    for k, c in kinds.most_common():
        print(f"  {labels.get(k, k):<20} {c}")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["demand", "kind", "slug", "name", "major_category", "note"])
            for d, r, kind, note in work:
                w.writerow([d, kind, r["slug"], r["name"],
                            r.get("major_category", ""), note])
        print(f"\n→ {args.csv} に全 {len(work)} 件を出力")


if __name__ == "__main__":
    main()
