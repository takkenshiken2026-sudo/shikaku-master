#!/usr/bin/env python3
"""未掲載(seed)資格の一次情報リサーチ用ワークリストを生成する。

published化には受験料・受験資格・合格率等を公式の一次情報で確認し
data/overrides.csv に追記する必要がある（数値の捏造は厳禁）。
本ツールは「確認すべき資格の一覧＋空欄の記入欄＋検索クエリ案」を出力し、
人手での一次情報確認を効率化する。事実値は生成しない。

出力:
  data/seed_worklist.csv  : overrides.csv と同じ列＋name/major/query の記入用CSV
  data/seed_worklist.md   : 分野別チェックリスト（進捗管理用）
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CERTS = ROOT / "data" / "certifications.csv"
OUT_CSV = ROOT / "data" / "seed_worklist.csv"
OUT_MD = ROOT / "data" / "seed_worklist.md"

# overrides.csv のスキーマ（build_pages が参照する事実値の列）
OVERRIDE_COLS = ["slug", "authority", "official_url", "fee", "exam_format",
                 "eligibility", "frequency", "pass_rate", "source_checked_at"]


def seed_rows():
    rows = list(csv.DictReader(CERTS.open(encoding="utf-8")))
    return [r for r in rows
            if r["status"] == "seed" and r["is_bucket"] == "0"
            and r["is_duplicate"] == "0" and r["scope"] == "domestic"]


def main() -> int:
    seed = seed_rows()
    seed.sort(key=lambda r: (r["major_category"], r["type"], r["name"]))

    # 記入用CSV（overrides 互換＋補助列）
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(OVERRIDE_COLS + ["name", "major_category", "type", "search_query"])
        for r in seed:
            q = f'{r["name"]} 受験料 受験資格 公式'
            w.writerow([r["slug"], "", "", "", "", "", "", "", "",
                        r["name"], r["major_category"], r["type"], q])

    # 分野別チェックリスト（Markdown）
    by_major = defaultdict(list)
    for r in seed:
        by_major[r["major_category"]].append(r)
    lines = [
        "# 未掲載(seed)資格 一次情報リサーチ・ワークリスト",
        "",
        f"対象 {len(seed)} 件。各資格の**公式サイト（一次情報）**で受験料・受験資格・"
        "試験形式・合格率・実施頻度・実施団体を確認し、`data/overrides.csv` に追記する。",
        "",
        "## 手順",
        "1. 公式サイトで事実を確認（数値の推測・捏造は禁止）。",
        "2. `data/seed_worklist.csv` の該当行に記入（`source_checked_at` に確認日 YYYY-MM-DD）。",
        "3. 記入済み行を `data/overrides.csv` に追記。",
        "4. `python3 tools/build_pages.py && python3 tools/validate.py` で反映・検査。",
        "   - published 条件: 受験料/合格率/受験資格のいずれかがあり、実データ2項目以上。",
        "",
        "## 注意",
        "- 廃止・名称変更済み（例: ホームヘルパー級, 介護職員基礎研修）は無理に掲載せず、",
        "  後継資格へのリンクや沿革の注記で扱うのが適切。",
        "- 民間で実施団体が複数ある汎用名（例: 整体師, リフレクソロジー）は、",
        "  代表的な団体を明示するか、団体横断の解説に留める。",
        "",
        "## 分野別チェックリスト",
    ]
    for major in sorted(by_major):
        items = by_major[major]
        lines.append(f"\n### {major}（{len(items)}件）")
        for r in items:
            lines.append(f"- [ ] `{r['slug']}` {r['name']}　〔{r['type']}〕")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {OUT_CSV.relative_to(ROOT)} ({len(seed)} rows)")
    print(f"wrote {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
