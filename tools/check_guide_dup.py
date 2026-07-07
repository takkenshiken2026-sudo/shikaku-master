#!/usr/bin/env python3
"""guides.csv のガイド間で重複する文・定型フレーズを検出する（テンプレ・使い回し防止）。

深掘り済み（difficulty または pitfalls が非空）のガイドを対象に、
プロース欄を句点で文分割し、正規化した文が2件以上の資格に跨って現れる場合に警告。
steps は定型的になりやすいため文単位ではなく完全一致のみ参考表示。
"""
import csv, re, sys
from collections import defaultdict

PROSE = ("suited", "difficulty", "study", "pitfalls", "career")

def norm(s):
    s = re.sub(r"\s+", "", s)
    return s

def sentences(text):
    for p in text.split("\n"):
        for s in re.split(r"(?<=。)", p):
            s = s.strip()
            if len(norm(s)) >= 12:  # 短い定型断片は無視
                yield s

def main():
    rows = list(csv.DictReader(open("data/guides.csv", encoding="utf-8")))
    deep = [r for r in rows if (r.get("difficulty") or "").strip()
            or (r.get("pitfalls") or "").strip()]
    idx = defaultdict(set)   # 文 -> {slug}
    for r in deep:
        for f in PROSE:
            for s in sentences(r.get(f, "") or ""):
                idx[norm(s)].add(r["slug"])
    dups = {s: v for s, v in idx.items() if len(v) >= 2}
    print(f"深掘り済みガイド: {len(deep)} 件を検査")
    if not dups:
        print("OK: 資格を跨いだ重複文なし")
        return 0
    print(f"NG: 重複文 {len(dups)} 件")
    for s, slugs in sorted(dups.items(), key=lambda x: -len(x[1]))[:40]:
        print(f"  [{len(slugs)}件: {','.join(sorted(slugs))}] {s[:60]}")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
