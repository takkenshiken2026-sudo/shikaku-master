#!/usr/bin/env python3
"""careers.csv（資格ごとの自由記述「活かせる仕事」）を正規化し、
職種データベースの背骨（職種マスタ＋資格⇔職種マッピング）を生成する。

- 入力 : data/careers.csv（slug, careers, source）
- 出力 : data/occupations.csv      … 職種マスタ（occ_id, name, major_category, cert_count, source）
         data/cert_occupations.csv … 資格⇔職種(多対多)（slug, occ_id, note）

方針（名寄せは「保守的＋同義語表」）:
- 区切りは「、」のみで分割（「・」は職種名内部に多用されるため分割しない）。
- 末尾の括弧（全角（）/半角()）は補足とみなし note へ分離。name は括弧前の部分。
- NFKC 正規化＋空白圧縮。明白な表記ゆれ・同義語のみ SYNONYMS で正規名へ寄せる
  （経理事務/会計事務/金融事務 等の意味が異なるものは別職種のまま）。
- occ_id は安定化: 既存 occupations.csv の name→occ_id を引き継ぎ、新規のみ採番。
- major_category は、その職種にひも付く資格の最頻 major_category を採用。

職種ごとの独自解説は本スクリプトでは扱わない（別ファイル occupation_descriptions.csv で
キュレーションし、生成物を上書きしない＝certifications.csv と descriptions.csv の関係に倣う）。
"""
import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAREERS_CSV = ROOT / "data" / "careers.csv"
CERTS_CSV = ROOT / "data" / "certifications.csv"
OCC_CSV = ROOT / "data" / "occupations.csv"
MAP_CSV = ROOT / "data" / "cert_occupations.csv"

# 明白な表記ゆれ・同義語のみ（保守的）。左→右（正規名）へ寄せる。
# 意味が異なる近接職種（経理事務/会計事務/金融事務 等）は寄せない。
SYNONYMS = {
    "ＳＥ": "システムエンジニア",
    "ＩＴエンジニア": "ITエンジニア",
    "プログラマー": "プログラマ",
    "オフィスワーク全般": "オフィスワーク",
    "一般事務職": "一般事務",
    "経理・財務": "経理・財務担当",
}

# 分野(major_category)の補正。派生値（ひも付く資格の最頻分野）が明白に誤るものだけを
# 手動上書きする（保守的）。事務系がIT・語学に寄る等の誤分類を是正。
MAJOR_OVERRIDE = {
    "一般事務": "商業・販売・事務",
    "営業事務": "商業・販売・事務",
    "オフィスワーク": "商業・販売・事務",
    "データ入力・集計スタッフ": "商業・販売・事務",
    "事務職": "商業・販売・事務",
    "貿易事務": "商業・販売・事務",
    "秘書": "商業・販売・事務",
    "営業職": "商業・販売・事務",
    "経理事務": "会計・金融・経営",
    "事務職全般": "商業・販売・事務",
    "総務": "商業・販売・事務",
    "受付": "商業・販売・事務",
    "販売職": "商業・販売・事務",
    "小売店スタッフ": "商業・販売・事務",
    "義肢装具士": "医療・看護・薬",
    "営業": "商業・販売・事務",
    "総務・庶務": "商業・販売・事務",
    "印刷・製版オペレーター": "機械・電気・ものづくり",
    "衛生管理者": "安全・環境・危険物",
}

PAREN_RE = re.compile(r"[（(]\s*(.*?)\s*[）)]\s*$")


def norm(s: str) -> str:
    """NFKC 正規化＋空白圧縮＋トリム。"""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_name_note(token: str):
    """末尾の括弧を補足(note)として分離し、(name, note) を返す。"""
    token = token.strip()
    note = ""
    m = PAREN_RE.search(token)
    if m:
        note = norm(m.group(1))
        token = token[: m.start()].strip()
    name = norm(token)
    return name, note


def canonical(name: str) -> str:
    return SYNONYMS.get(name, name)


def load_major_category():
    """slug → major_category。"""
    out = {}
    if not CERTS_CSV.exists():
        return out
    with CERTS_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["slug"]] = (r.get("major_category") or "").strip()
    return out


def load_existing_ids():
    """既存 occupations.csv の name→occ_id を読み、ID を安定化する。"""
    ids = {}
    max_n = 0
    if OCC_CSV.exists():
        with OCC_CSV.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                oid = (r.get("occ_id") or "").strip()
                nm = (r.get("name") or "").strip()
                if oid and nm:
                    ids[nm] = oid
                    m = re.match(r"o-(\d+)$", oid)
                    if m:
                        max_n = max(max_n, int(m.group(1)))
    return ids, max_n


def main():
    major_of = load_major_category()
    name_to_id, max_n = load_existing_ids()

    rows = list(csv.DictReader(CAREERS_CSV.open(encoding="utf-8")))

    # マッピング収集（資格→職種）。同一資格内の重複職種は1回に。
    mapping = []  # (slug, name, note)
    occ_slugs = defaultdict(set)  # name -> set(slug)
    occ_majors = defaultdict(Counter)  # name -> Counter(major_category)
    seen_pairs = set()

    for r in rows:
        slug = (r.get("slug") or "").strip()
        careers = (r.get("careers") or "").strip()
        if not slug or not careers:
            continue
        for tok in careers.split("、"):
            tok = tok.strip()
            if not tok:
                continue
            name, note = split_name_note(tok)
            name = canonical(name)
            if not name:
                continue
            key = (slug, name)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            mapping.append((slug, name, note))
            occ_slugs[name].add(slug)
            mc = major_of.get(slug, "")
            if mc:
                occ_majors[name][mc] += 1

    # ID 採番（既存を引き継ぎ、新規は名前順で安定採番）
    for name in sorted(occ_slugs):
        if name not in name_to_id:
            max_n += 1
            name_to_id[name] = f"o-{max_n:04d}"

    # occupations.csv 出力
    occ_rows = []
    for name in sorted(occ_slugs, key=lambda n: (-len(occ_slugs[n]), n)):
        oid = name_to_id[name]
        mc = MAJOR_OVERRIDE.get(name) or (
            occ_majors[name].most_common(1)[0][0] if occ_majors[name] else "")
        occ_rows.append({
            "occ_id": oid,
            "name": name,
            "major_category": mc,
            "cert_count": len(occ_slugs[name]),
            "source": "厚労省 職業情報提供サイト（jobtag）を出所とする careers の正規化",
        })
    with OCC_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["occ_id", "name", "major_category", "cert_count", "source"])
        w.writeheader()
        w.writerows(occ_rows)

    # cert_occupations.csv 出力（slug, occ_id, note）。slug→occ_id 名前順で安定ソート。
    map_rows = sorted(
        ({"slug": s, "occ_id": name_to_id[n], "note": note} for (s, n, note) in mapping),
        key=lambda d: (d["slug"], d["occ_id"]),
    )
    with MAP_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["slug", "occ_id", "note"])
        w.writeheader()
        w.writerows(map_rows)

    print(f"職種マスタ: {len(occ_rows)} 件 -> {OCC_CSV.relative_to(ROOT)}")
    print(f"資格⇔職種マッピング: {len(map_rows)} 件 -> {MAP_CSV.relative_to(ROOT)}")
    print("上位職種(ひも付く資格数):")
    for r in occ_rows[:10]:
        print(f"  {r['occ_id']} {r['name'][:28]:<28} {r['cert_count']}資格 [{r['major_category']}]")


if __name__ == "__main__":
    main()
