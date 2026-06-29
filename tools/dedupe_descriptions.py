#!/usr/bin/env python3
"""descriptions.csv の重複説明文を、各資格の固有部分から一意化する。

複数の資格が同一の説明文を共有していると重複コンテンツ評価を招くため、
等級・部門・種別・職種など名称の固有部分を反映したユニークな説明文に
書き換える（事実値は扱わず、編集上の概要のみ。一意性のみを担保）。
既に固有（単一出現）の説明文は変更しない。
"""
from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESC = ROOT / "data" / "descriptions.csv"
CERTS = ROOT / "data" / "certifications.csv"

TYPE_LABEL = {"国家": "国家資格", "公的": "公的資格", "民間": "民間資格",
              "要確認": "資格", "海外": "海外資格", "": "資格"}

# 元データのグルーピング誤りで共有文が実態と合わない資格は、正しい説明を手当て。
MANUAL = {
    "小型船舶操縦士": (
        "小型船舶操縦士は、モーターボートや小型クルーザーなど小型船舶を"
        "操縦するための国家資格です。マリンレジャーから漁業・旅客輸送まで、"
        "海や湖での船舶の運航に必要となります。"),
}

LEVEL_RE = re.compile(
    r"^(特級|[1-9０-９]+級|準[1-9０-９]+級|[1-9０-９]+段|初段|初級|中級|上級|"
    r"甲種|乙種|丙種|一等|二等|三等|第[一二三四1-9０-９]+種)$")


def family_of(core: str) -> str:
    """共有説明文の主語（資格ファミリー名）を取り出す。'珠算能力検定は、…'→'珠算能力検定'。"""
    m = re.match(r"^(.{2,20}?)は[、。]", core)
    return m.group(1) if m else ""


def gino_shi(name: str) -> str:
    """技能士（技能検定）系のユニーク説明文を職種名から生成。"""
    n = re.sub(r"^(特級|[1-9０-９]+級)", "", name)
    n = re.sub(r"技能士[1-9０-９]*級?$", "技能士", n)
    trade = n.replace("技能士", "").strip()
    trade = trade or "専門職種"
    return (f"{name}は、{trade}に関する技能を国が認定する技能検定（技能士）の"
            f"国家資格です。等級ごとに到達レベルが定められ、現場での技術力を"
            f"公的に証明でき、就職・転職や社内評価で役立ちます。")


def strip_subject(core: str, family: str) -> str:
    """共有説明文の冒頭の主語『{family}は、』を取り除いて述部だけにする。"""
    for sep in ("は、", "は"):
        head = family + sep
        if family and core.startswith(head):
            return core[len(head):]
    return core


def make_unique(name: str, core: str, major: str, typ: str) -> str:
    if name in MANUAL:
        return MANUAL[name]
    if core.startswith("この技能士は"):
        return gino_shi(name)
    family = family_of(core)
    variant = ""
    if family and family in name:
        variant = name.replace(family, "", 1).strip(" 　()（）「」・-")
    body = strip_subject(core, family)
    if variant and LEVEL_RE.match(variant):
        lead = f"{name}は、{family}の{variant}にあたる区分です。"
    elif variant:
        lead = f"{name}は、{family}のうち{variant}を対象とする区分です。"
    else:
        lead = f"{name}は、{major}分野の{TYPE_LABEL.get(typ, '資格')}です。"
    # 述部が主語付きのまま残った場合（family抽出失敗）はそのまま続け、二重主語を避ける
    if body == core and family:
        # 主語除去できなかった → リード＋元文（情報量優先）
        return lead + core
    return lead + body


def main() -> int:
    certs = {r["slug"]: r for r in csv.DictReader(CERTS.open(encoding="utf-8"))}
    rows = list(csv.DictReader(DESC.open(encoding="utf-8")))
    counts = Counter(r["description"] for r in rows)
    dup = {d for d, n in counts.items() if n > 1}

    changed = 0
    for r in rows:
        if r["description"] not in dup:
            continue
        c = certs.get(r["slug"])
        if not c:
            continue
        new = make_unique(c["name"], r["description"],
                          c["major_category"], c["type"])
        if new != r["description"]:
            r["description"] = new
            changed += 1

    with DESC.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["slug", "description"])
        w.writeheader()
        w.writerows(rows)

    after = Counter(r["description"] for r in rows)
    dupes = sum(1 for n in after.values() if n > 1)
    print(f"rewritten: {changed} rows")
    print(f"unique now: {len(after)} / {len(rows)} rows  (残り重複文: {dupes})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
