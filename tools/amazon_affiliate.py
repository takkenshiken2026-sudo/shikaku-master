#!/usr/bin/env python3
"""Amazonアソシエイトの掲載準備ヘルパー。

- ASIN → タグ付きアフィリンクの生成（手作業のリンク組み立てをなくす）
- data/materials.csv のタグ整合性チェック（タグ欠け・別タグの検出）
- 教材未整備の公開資格の洗い出し（掲載準備のワークリスト）

使い方:
  python3 tools/amazon_affiliate.py link 4300119279        # ASIN→URL
  python3 tools/amazon_affiliate.py check                   # タグ整合性チェック
  python3 tools/amazon_affiliate.py gaps [N]                # 未整備資格を流入順にN件表示
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CERTS_CSV = ROOT / "data" / "certifications.csv"
MATERIALS_CSV = ROOT / "data" / "materials.csv"
GSC_JSON = ROOT / "data" / "gsc_page_impressions.json"

# 既存 materials.csv 全リンクで使われているアソシエイトタグ。
AMAZON_TAG = "ue083093-22"


def aff_url(asin: str, tag: str = AMAZON_TAG) -> str:
    """ASIN からタグ付きの amazon.co.jp アフィリンクを組み立てる。"""
    asin = asin.strip()
    if not re.fullmatch(r"[0-9A-Z]{10}", asin):
        raise ValueError(f"ASINの形式が不正: {asin!r}")
    return f"https://www.amazon.co.jp/dp/{asin}?tag={tag}"


def plain_url(asin: str) -> str:
    return f"https://www.amazon.co.jp/dp/{asin.strip()}"


def _load_materials():
    if not MATERIALS_CSV.exists():
        return []
    with MATERIALS_CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check():
    """Amazonリンクのタグ整合性を検査。異常があれば非ゼロ終了。"""
    rows = _load_materials()
    bad = []
    for i, r in enumerate(rows, 2):  # 2 = ヘッダ次の行番号
        aff = (r.get("affiliate") or "").strip()
        if "amazon.co.jp" not in aff:
            continue  # 講座(A8)等は対象外
        m = re.search(r"[?&]tag=([^&]+)", aff)
        if not m:
            bad.append((i, r["slug"], "タグ無し", aff))
        elif m.group(1) != AMAZON_TAG:
            bad.append((i, r["slug"], f"別タグ:{m.group(1)}", aff))
    amazon_n = sum(1 for r in rows if "amazon.co.jp" in (r.get("affiliate") or ""))
    print(f"Amazonリンク {amazon_n} 件を検査。異常 {len(bad)} 件。")
    for line, slug, why, aff in bad:
        print(f"  行{line} {slug} [{why}] {aff}")
    return 1 if bad else 0


def gaps(limit=40):
    """教材(テキスト)が未整備の公開資格を、GSC流入の多い順に表示。"""
    certs = list(csv.DictReader(CERTS_CSV.open(encoding="utf-8")))
    disp = [r for r in certs
            if r["is_bucket"] == "0" and r["is_duplicate"] == "0"
            and r["scope"] == "domestic" and r.get("status") == "published"]
    text_slugs = {m["slug"] for m in _load_materials() if m["kind"] == "テキスト"}
    gsc = json.loads(GSC_JSON.read_text(encoding="utf-8")) if GSC_JSON.exists() else {}
    gap = [r for r in disp if r["slug"] not in text_slugs]
    gap.sort(key=lambda r: -gsc.get(r["slug"], 0))
    print(f"未整備(公開)資格: {len(gap)} 件 / 公開資格 {len(disp)} 件中")
    for r in gap[:limit]:
        print(f'  {r["slug"]:7} imp{gsc.get(r["slug"],0):5} | {r["major_category"][:10]:10} | {r["name"]}')


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "link":
        print(aff_url(argv[2]))
    elif cmd == "check":
        return check()
    elif cmd == "gaps":
        gaps(int(argv[2]) if len(argv) > 2 else 40)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
