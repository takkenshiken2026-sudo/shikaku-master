#!/usr/bin/env python3
"""ハローワーク 免許・資格コード一覧（小分類）のTSVを正本シードとして
certifications.csv（資格カタログの骨格）へ変換する。

- 入力: data/sources/hellowork_license_list.tsv（「# カテゴリ」＋ code<TAB>name）
- 出力: data/certifications.csv（1行=1資格）
- 名称はNFKC正規化（全角英数→半角）。原文は name_raw に保持。
- 末尾 xx99「その他の…関係資格」はバケット項目として is_bucket=1。
- 同一カテゴリ内の同名は is_duplicate=1（先頭以外）。
- 8000番台「海外資格」は scope=overseas（既定の網羅対象=domestic から除外可）。
事実値（受験料/合格率/公式URL等）は本スクリプトでは埋めない（一次情報で後追い検証）。
"""
import csv
import re
import sys
import unicodedata
from pathlib import Path

import classify_rules

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "sources" / "hellowork_license_list.tsv"
OUT = ROOT / "data" / "certifications.csv"
OVERRIDES = ROOT / "data" / "overrides.csv"


def load_overrides():
    """data/overrides.csv（slug をキーに検証済み事実値を保持）を読む。無ければ空。"""
    if not OVERRIDES.exists():
        return {}
    with OVERRIDES.open(encoding="utf-8") as f:
        return {r["slug"]: r for r in csv.DictReader(f) if r.get("slug")}

# certifications.csv のスキーマ（事実値の列は空で用意し、後工程で検証して埋める）
COLUMNS = [
    "slug", "hellowork_code", "name", "name_raw", "category", "major_category",
    "scope", "is_bucket", "is_duplicate",
    "type", "type_confidence", "type_reason",
    "authority", "official_url",
    "eligibility", "exam_format", "fee", "pass_rate", "frequency", "difficulty",
    "related_slugs", "source_checked_at", "status",
]


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s).strip()


def slugify(code: str, name: str) -> str:
    """URL用slug。現状は安定一意なコードベース（例 c-6703）。
    将来ローマ字slugに差し替え可能だがリダイレクト維持のためコードを主キーに残す。"""
    return f"c-{code}"


def parse(src: Path):
    rows = []
    category = ""
    for raw in src.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        if line.startswith("# "):  # 出典コメント等（半角#+空白）
            continue
        if line.startswith("#"):   # カテゴリ見出し
            category = nfkc(line[1:].strip())
            continue
        if "\t" not in line:
            continue
        code, name_raw = line.split("\t", 1)
        code = code.strip()
        name_raw = name_raw.strip()
        if not re.fullmatch(r"\d{3,5}", code):
            continue
        rows.append((code, name_raw, category))
    return rows


def main() -> int:
    if not SRC.exists():
        print(f"seed source not found: {SRC}", file=sys.stderr)
        return 1
    parsed = parse(SRC)

    seen_by_cat = {}
    out_rows = []
    for code, name_raw, category in parsed:
        name = nfkc(name_raw)
        is_bucket = 1 if code.endswith("99") and name.startswith("その他") else 0
        scope = "overseas" if code.startswith("8") else "domestic"
        key = (category, name)
        is_dup = 1 if key in seen_by_cat else 0
        seen_by_cat[key] = True
        major = classify_rules.major_category(code, category)
        ctype, conf, reason = classify_rules.classify_type(
            code, name, category, scope, is_bucket)
        out_rows.append({
            "slug": slugify(code, name),
            "hellowork_code": code,
            "name": name,
            "name_raw": name_raw,
            "category": category,
            "major_category": major,
            "scope": scope,
            "is_bucket": is_bucket,
            "is_duplicate": is_dup,
            "type": ctype,            # 国家/公的/民間/要確認/海外
            "type_confidence": conf,  # high/medium/low
            "type_reason": reason,
            "authority": "",
            "official_url": "",
            "eligibility": "",
            "exam_format": "",
            "fee": "",
            "pass_rate": "",
            "frequency": "",
            "difficulty": "",
            "related_slugs": "",
            "source_checked_at": "",
            "status": "seed",      # seed -> draft -> published
        })

    # --- 一次情報で検証した事実値(data/overrides.csv)をマージ ---
    overrides = load_overrides()
    applied = 0
    FACT_FIELDS = ("authority", "official_url", "eligibility", "exam_format",
                   "fee", "pass_rate", "frequency", "difficulty",
                   "source_checked_at", "type", "type_reason")
    by_slug = {r["slug"]: r for r in out_rows}
    for slug, ov in overrides.items():
        row = by_slug.get(slug)
        if not row:
            print(f"  WARN override未該当slug: {slug}", file=sys.stderr)
            continue
        for k in FACT_FIELDS:
            v = ov.get(k, "").strip()
            if v:
                row[k] = v
        # 公式URLと実施団体が入ったら published（noindex解除の対象）
        if row["official_url"] and row["authority"]:
            row["status"] = "published"
        applied += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out_rows)

    from collections import Counter
    total = len(out_rows)
    buckets = sum(r["is_bucket"] for r in out_rows)
    dups = sum(r["is_duplicate"] for r in out_rows)
    overseas = sum(1 for r in out_rows if r["scope"] == "overseas")
    cats = len({r["category"] for r in out_rows})
    majors = Counter(r["major_category"] for r in out_rows)
    types = Counter(r["type"] for r in out_rows if not r["is_bucket"])
    indexable = total - buckets - dups
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  total rows      : {total}")
    print(f"  中分類 categories: {cats}")
    print(f"  大分類 majors   : {len(majors)}")
    print(f"  bucket (xx99)   : {buckets}  (noindex想定)")
    print(f"  duplicates      : {dups}  (noindex想定)")
    print(f"  overseas(8xxx)  : {overseas}")
    print(f"  candidate pages : {indexable}")
    print("  --- 大分類別件数 ---")
    for k, v in majors.most_common():
        print(f"    {v:4d}  {k}")
    print("  --- type別件数(バケット除く) ---")
    for k, v in types.most_common():
        print(f"    {v:4d}  {k or '(空)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
