#!/usr/bin/env python3
"""データ整合性チェック（CI / 手元での品質ゲート用）。

確認すること:
- overrides.csv の slug が一意で、certifications.csv に実在する
- overrides の必須列がそろっている
- published 化の条件（authority と official_url の両方あり）を満たすか
- 受験料・合格率の表記ゆれ（明らかな桁区切りミス等）の軽い検査

公式サイトの数値そのものの正誤は本スクリプトでは検証できない（ネットワーク不可の
環境前提）。本スクリプトは「内部整合性」を保証し、回帰を防ぐためのもの。
異常があれば終了コード1を返す。
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CERTS = ROOT / "data" / "certifications.csv"
OVERRIDES = ROOT / "data" / "overrides.csv"

OV_COLS = ["slug", "authority", "official_url", "fee", "exam_format",
           "eligibility", "frequency", "pass_rate", "source_checked_at"]


def main() -> int:
    errors, warnings = [], []
    certs = list(csv.DictReader(CERTS.open(encoding="utf-8")))
    valid = {r["slug"] for r in certs}
    ov = list(csv.DictReader(OVERRIDES.open(encoding="utf-8")))

    # 列チェック
    missing_cols = [c for c in OV_COLS if c not in (ov[0].keys() if ov else [])]
    if missing_cols:
        errors.append(f"overrides.csv に必須列が不足: {missing_cols}")

    seen = {}
    pub = 0
    for i, r in enumerate(ov, 2):  # 2 = ヘッダの次の行番号
        s = r.get("slug", "")
        if not s:
            errors.append(f"L{i}: slug が空")
            continue
        if s in seen:
            errors.append(f"L{i}: slug 重複 {s}（L{seen[s]} と）")
        seen[s] = i
        if s not in valid:
            errors.append(f"L{i}: {s} は certifications.csv に存在しない")
        # published 条件
        if r.get("official_url") and r.get("authority"):
            pub += 1
        else:
            warnings.append(f"{s}: authority/official_url が未充足（published 化されない）")
        # 表記の軽い検査: 受験料に円があるのに数字がないなど
        fee = r.get("fee", "")
        if fee and "円" in fee and not re.search(r"\d", fee):
            warnings.append(f"{s}: fee に数字がない: {fee!r}")
        pr = r.get("pass_rate", "")
        if pr and "%" in pr and not re.search(r"\d", pr):
            warnings.append(f"{s}: pass_rate に数字がない: {pr!r}")
        if r.get("source_checked_at", "") and not re.match(
                r"^\d{4}-\d{2}-\d{2}$", r["source_checked_at"]):
            warnings.append(f"{s}: source_checked_at の形式が不正: {r['source_checked_at']!r}")

    print(f"overrides: {len(ov)} 行 / published化条件を満たす: {pub} 件")
    if warnings:
        print(f"\n警告 {len(warnings)} 件:")
        for w in warnings[:50]:
            print(f"  - {w}")
        if len(warnings) > 50:
            print(f"  …他 {len(warnings) - 50} 件")
    if errors:
        print(f"\nエラー {len(errors)} 件:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("\nOK: 整合性エラーなし")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
