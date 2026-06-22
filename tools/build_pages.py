#!/usr/bin/env python3
"""certifications.csv から静的サイト(prototype/site/)を生成する。

- site/index.html        : ファセット検索トップ(大分類・type・フリーワード)
- site/c/<slug>.html     : 資格詳細ページ
- site/data/certifications.json : クライアント検索用データ
- site/assets/app.css, search.js

掲載対象(indexable): is_bucket=0 かつ is_duplicate=0 かつ scope=domestic。
プロトタイプのため全ページ <meta name="robots" content="noindex"> で出力。
事実値(受験料/合格率/公式URL)は未検証なら「公式で確認」を促す。
"""
import csv
import html
import json
import math
import re
import shutil
from collections import Counter
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "certifications.csv"
CAREERS_CSV = ROOT / "data" / "careers.csv"
EXAM_CSV = ROOT / "data" / "exam_details.csv"
STUDY_CSV = ROOT / "data" / "study_time.csv"
DIFFICULTY_CSV = ROOT / "data" / "difficulty.csv"
SITE = ROOT / "site"
BRAND = ROOT / "brand"

# 厚労省 職業情報提供サイト（job tag）— 関連職業の公式ディスカバリ導線
JOBTAG_URL = "https://shigoto.mhlw.go.jp/User/Search/Top"

SITE_NAME = "資格マスター"
SITE_DESC = "日本の資格を「探せる・絞れる・比べられる」資格データベース。受験料・試験形式・受験資格・合格率・実施団体・公式サイトを公式の一次情報に基づき掲載。"
BASE_URL = "https://shikaku-master.jp"
CUSTOM_DOMAIN = "shikaku-master.jp"

# 運営者が制作する資格別の対策サイト（「おすすめの資格対策サイト」導線）。
# 通常リンク（dofollow）・別タブ。certs に該当資格 slug を持つものは、その詳細ページにも出し分ける。
PARTNER_SITES = [
    {"name": "宅建対策サイト", "url": "https://takken-master.jp/",
     "tagline": "宅地建物取引士（不動産）", "certs": ["c-3207"]},
    {"name": "マンション管理士対策サイト", "url": "https://mankan-master.jp/",
     "tagline": "不動産・マンション管理", "certs": ["c-3209"]},
    {"name": "管理業務主任者対策サイト", "url": "https://kangyou-master.jp/",
     "tagline": "不動産・マンション管理", "certs": ["c-3210"]},
    {"name": "賃貸不動産経営管理士対策サイト", "url": "https://chintaikanrishi-master.jp/",
     "tagline": "不動産・賃貸管理", "certs": []},
    {"name": "FP対策サイト", "url": "https://fp-master.jp/",
     "tagline": "FP技能士 1〜3級・CFP/AFP",
     "certs": ["c-2505", "c-2515", "c-2516", "c-2517"]},
    {"name": "証券外務員対策サイト", "url": "https://gaimuin-master.jp/",
     "tagline": "一種・二種外務員資格", "certs": ["c-4201"]},
    {"name": "危険物取扱者対策サイト", "url": "https://kikenbutsu-master.jp/",
     "tagline": "甲種・乙種・丙種",
     "certs": ["c-5206", "c-5207", "c-5208"]},
    {"name": "ボイラー技士対策サイト", "url": "https://boiler-master.jp/",
     "tagline": "特級・1級・2級", "certs": ["c-6701", "c-6702", "c-6703"]},
    {"name": "第一種衛生管理者対策サイト", "url": "https://eisei1shu-master.jp/",
     "tagline": "労働衛生管理", "certs": ["c-2202"]},
    {"name": "第二種衛生管理者対策サイト", "url": "https://eisei2shu-master.jp/",
     "tagline": "労働衛生管理", "certs": ["c-2203"]},
    {"name": "運行管理者対策サイト", "url": "https://unkan-master.jp/",
     "tagline": "旅客・貨物", "certs": ["c-3705", "c-3706"]},
    {"name": "メンタルヘルス・マネジメント検定対策サイト", "url": "https://mentalhealth-master.jp/",
     "tagline": "II種ほか", "certs": []},
    {"name": "AI資格対策サイト", "url": "https://ai-master.jp/",
     "tagline": "AI・データサイエンス系", "certs": []},
]
PARTNER_BY_CERT = {}
for _p in PARTNER_SITES:
    for _c in _p["certs"]:
        PARTNER_BY_CERT.setdefault(_c, []).append(_p)


def partner_footer_html():
    """フッター共通の運営者サイト導線（全ページ）。"""
    items = "".join(
        f'<a href="{esc(p["url"])}" target="_blank" rel="noopener">{esc(p["name"])}</a>'
        for p in PARTNER_SITES)
    return ('<nav class="site-footer-partners" aria-label="運営者の資格対策サイト">'
            '<span class="sfp-label">運営者の資格対策サイト</span>'
            f'<span class="sfp-links">{items}</span></nav>')


def partner_cards_html():
    """おすすめ対策サイトのカード一覧（トップ・aboutで使用）。"""
    return "".join(
        f'<a class="partner-card" href="{esc(p["url"])}" target="_blank" rel="noopener">'
        f'<span class="partner-card-name">{esc(p["name"])}<span class="partner-ext" aria-hidden="true">↗</span></span>'
        f'<span class="partner-card-tag">{esc(p["tagline"])}</span></a>'
        for p in PARTNER_SITES)


def partner_detail_html(slug):
    """資格詳細ページに、その資格の対策サイトがあれば出し分けるボックス。"""
    ps = PARTNER_BY_CERT.get(slug)
    if not ps:
        return ""
    items = "".join(
        f'<a class="partner-detail-card" href="{esc(p["url"])}" target="_blank" rel="noopener">'
        f'<span class="pd-name">{esc(p["name"])}<span class="partner-ext" aria-hidden="true">↗</span></span>'
        f'<span class="pd-tag">{esc(p["tagline"])}</span></a>' for p in ps)
    return ('<section class="partner-detail" aria-labelledby="pd-h">'
            '<h2 class="detail-section-title" id="pd-h">この資格の対策サイト</h2>'
            f'<div class="partner-detail-grid">{items}</div>'
            '<p class="muted partner-note">当サイト運営者が制作している学習・対策サイトです。</p>'
            '</section>')


TYPE_BADGE = {
    "国家": ("国家資格", "badge-national"),
    "公的": ("公的資格", "badge-public"),
    "民間": ("民間資格", "badge-private"),
    "要確認": ("区分要確認", "badge-unknown"),
    "海外": ("海外資格", "badge-overseas"),
}


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def load_rows():
    with CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_careers():
    """slug → {careers, source} の辞書。出典付きで個別キュレーションした関連職業。"""
    if not CAREERS_CSV.exists():
        return {}
    out = {}
    with CAREERS_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s = (r.get("slug") or "").strip()
            careers = (r.get("careers") or "").strip()
            if s and careers:
                out[s] = {"careers": careers, "source": (r.get("source") or "").strip()}
    return out


CAREERS = load_careers()


def load_exam_details():
    """slug → {exam_subjects, applicants, source}。公式の一次情報に基づく試験科目・受験者数。"""
    if not EXAM_CSV.exists():
        return {}
    out = {}
    with EXAM_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s = (r.get("slug") or "").strip()
            if not s:
                continue
            out[s] = {
                "exam_subjects": (r.get("exam_subjects") or "").strip(),
                "applicants": (r.get("applicants") or "").strip(),
                "source": (r.get("source") or "").strip(),
            }
    return out


EXAM = load_exam_details()


def load_descriptions():
    """slug → 手書きの独自解説文（編集部によるユニーク概要）。"""
    path = ROOT / "data" / "descriptions.csv"
    if not path.exists():
        return {}
    out = {}
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s = (r.get("slug") or "").strip()
            d = (r.get("description") or "").strip()
            if s and d:
                out[s] = d
    return out


DESC = load_descriptions()


def load_study_time():
    """slug → {study_hours, source}。学習時間の目安（編集値・公式の一次情報ではない）。"""
    if not STUDY_CSV.exists():
        return {}
    out = {}
    with STUDY_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s = (r.get("slug") or "").strip()
            h = (r.get("study_hours") or "").strip()
            if s and h:
                out[s] = {"study_hours": h, "source": (r.get("source") or "").strip()}
    return out


STUDY = load_study_time()


def load_difficulty_data():
    """slug → {value, source}。編集部が出典付きで投入する難易度データ（0-100、高いほど難）。
    総合難易度スコアの第3軸。空でも可（その場合は合格率・学習時間のみで算出）。"""
    if not DIFFICULTY_CSV.exists():
        return {}
    out = {}
    with DIFFICULTY_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s = (r.get("slug") or "").strip()
            v = (r.get("difficulty") or "").strip()
            if not s or not v:
                continue
            try:
                val = float(v)
            except ValueError:
                continue
            out[s] = {"value": val, "source": (r.get("source") or "").strip()}
    return out


DIFFICULTY_DATA = load_difficulty_data()


# ── 職種データベース（occupations.csv / cert_occupations.csv）──
import build_occupations as occlib  # 正規化ロジック（split_name_note / canonical）を共有

OCC_CSV = ROOT / "data" / "occupations.csv"
MAP_CSV = ROOT / "data" / "cert_occupations.csv"
OCC_DESC_CSV = ROOT / "data" / "occupation_descriptions.csv"


def load_occupations():
    """occ_id → {name, major_category, cert_count}。職種マスタ。"""
    if not OCC_CSV.exists():
        return {}
    out = {}
    with OCC_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            oid = (r.get("occ_id") or "").strip()
            nm = (r.get("name") or "").strip()
            if not oid or not nm:
                continue
            try:
                cc = int(r.get("cert_count") or 0)
            except ValueError:
                cc = 0
            out[oid] = {"name": nm, "major_category": (r.get("major_category") or "").strip(),
                        "cert_count": cc}
    return out


OCC = load_occupations()
OCC_ID_BY_NAME = {v["name"]: k for k, v in OCC.items()}


def load_cert_occ():
    """occ_id → [slug]（逆引き）と slug → set(occ_id) を返す。"""
    occ_certs, slug_occs = {}, {}
    if not MAP_CSV.exists():
        return occ_certs, slug_occs
    with MAP_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s = (r.get("slug") or "").strip()
            oid = (r.get("occ_id") or "").strip()
            if not s or not oid:
                continue
            occ_certs.setdefault(oid, []).append(s)
            slug_occs.setdefault(s, set()).add(oid)
    return occ_certs, slug_occs


OCC_CERTS, SLUG_OCC_IDS = load_cert_occ()


def load_occupation_descriptions():
    """occ_id → {summary, work, skills}（手書きのキュレーション。work/skillsは任意）。"""
    if not OCC_DESC_CSV.exists():
        return {}
    out = {}
    with OCC_DESC_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            oid = (r.get("occ_id") or "").strip()
            d = (r.get("summary") or "").strip()
            if oid and d:
                out[oid] = {"summary": d,
                            "work": (r.get("work") or "").strip(),
                            "skills": (r.get("skills") or "").strip()}
    return out


OCC_DESC = load_occupation_descriptions()


def load_occupation_salary():
    """occ_id → 想定年収レンジ（目安・編集値）。公式値ではない。"""
    path = ROOT / "data" / "occupation_salary.csv"
    if not path.exists():
        return {}
    out = {}
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            oid = (r.get("occ_id") or "").strip()
            sal = (r.get("salary") or "").strip()
            if oid and sal:
                out[oid] = sal
    return out


OCC_SALARY = load_occupation_salary()


def _salary_quantitative(sal):
    """『約480〜560万円』等のレンジを schema.org の QuantitativeValue(円・年額) に変換。"""
    if not sal:
        return None
    m = re.search(r"([0-9,]+)\s*[〜~～]\s*([0-9,]+)\s*万", sal)
    if not m:
        return None
    lo = int(m.group(1).replace(",", "")) * 10000
    hi = int(m.group(2).replace(",", "")) * 10000
    return {"@type": "QuantitativeValue", "minValue": lo, "maxValue": hi,
            "unitText": "YEAR"}


# ── おすすめ教材・講座（アフィリエイト対応。本体DBとは分離）──
MATERIALS_CSV = ROOT / "data" / "materials.csv"


def load_materials():
    """slug → [教材dict]。編集部選定の学習教材・講座。affiliate列があれば収益リンク。"""
    if not MATERIALS_CSV.exists():
        return {}
    out = {}
    with MATERIALS_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s = (r.get("slug") or "").strip()
            title = (r.get("title") or "").strip()
            if not s or not title:
                continue
            out.setdefault(s, []).append({
                "kind": (r.get("kind") or "教材").strip(),
                "title": title,
                "provider": (r.get("provider") or "").strip(),
                "url": (r.get("url") or "").strip(),
                "affiliate": (r.get("affiliate") or "").strip(),
                "note": (r.get("note") or "").strip(),
            })
    return out


MATERIALS = load_materials()


# ── 資格間の関係（ステップアップ・免除/受験資格・ダブルライセンス）──
RELATIONS_CSV = ROOT / "data" / "cert_relations.csv"


def load_cert_relations():
    """slug → {up, down, exempt_to, exempt_from, combo}（各 (相手slug, note) のリスト）。"""
    rel = {}

    def b(s):
        return rel.setdefault(s, {"up": [], "down": [], "exempt_to": [],
                                  "exempt_from": [], "combo": []})
    if not RELATIONS_CSV.exists():
        return rel
    with RELATIONS_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            a = (r.get("slug_a") or "").strip()
            c = (r.get("slug_b") or "").strip()
            t = (r.get("relation") or "").strip()
            note = (r.get("note") or "").strip()
            if not a or not c:
                continue
            if t == "step_up":
                b(a)["up"].append((c, note))
                b(c)["down"].append((a, note))
            elif t == "exemption":
                b(a)["exempt_to"].append((c, note))
                b(c)["exempt_from"].append((a, note))
            elif t == "combo":
                b(a)["combo"].append((c, note))
                b(c)["combo"].append((a, note))
    return rel


CERT_RELATIONS = load_cert_relations()


def _rel_name(s):
    n = NAME_BY_SLUG.get(s, s)
    return re.sub(r"[（(].*?[）)]", "", n).strip() or n


def step_up_chain(slug):
    """step_up 関係をたどり、この資格を含む級・上位資格の直線チェーンを返す。
    前段階(down)を遡り、上位(up)を辿る。分岐は最初の枝のみを背骨に採用。"""
    seen = {slug}
    preds, cur = [], slug
    while True:
        nxt = next((s for s, _ in CERT_RELATIONS.get(cur, {}).get("down", []) if s not in seen), None)
        if not nxt:
            break
        preds.append(nxt); seen.add(nxt); cur = nxt
    preds.reverse()
    succs, cur = [], slug
    while True:
        nxt = next((s for s, _ in CERT_RELATIONS.get(cur, {}).get("up", []) if s not in seen), None)
        if not nxt:
            break
        succs.append(nxt); seen.add(nxt); cur = nxt
    return preds + [slug] + succs


def roadmap_html(slug, chain):
    """step_up チェーンを取得ロードマップとして横並び表示。2段未満なら空文字。"""
    if len(chain) < 2:
        return ""
    steps = []
    for s in chain:
        if s == slug:
            steps.append(f'<li class="rm-step rm-cur"><span>{esc(_rel_name(s))}</span>'
                         f'<small>いま見ている資格</small></li>')
        else:
            steps.append(f'<li class="rm-step"><a href="{esc(s)}.html">{esc(_rel_name(s))}</a></li>')
    return ('<div class="roadmap"><h3>取得ロードマップ</h3>'
            '<ol class="rm-track">' + "".join(steps) + "</ol>"
            '<p class="muted">級・段階のステップアップの流れです（左から上位へ）。'
            'いま見ている資格を起点に、前後の資格ページへ進めます。</p></div>')


def cert_relations_html(slug):
    """資格ページの「関連資格・ステップアップ」セクション。
    step_up はロードマップで可視化し、免除・ダブルライセンスを併記。なければ空文字。"""
    rel = CERT_RELATIONS.get(slug)
    if not rel:
        return ""

    def li(s, note):
        note_html = f' <span class="muted">— {esc(note)}</span>' if note else ""
        return f'<li><a href="{esc(s)}.html">{esc(_rel_name(s))}</a>{note_html}</li>'

    chain = step_up_chain(slug)
    rm = roadmap_html(slug, chain)
    chain_set = set(chain)

    subs = []
    # ロードマップに載らない上位/前段階（分岐）だけ補足リスト化
    branch_up = [(s, n) for s, n in rel["up"] if s not in chain_set]
    branch_down = [(s, n) for s, n in rel["down"] if s not in chain_set]
    if branch_up:
        subs.append("<h3>そのほか上位として目指せる資格</h3><ul>"
                    + "".join(li(s, n) for s, n in branch_up) + "</ul>")
    if branch_down:
        subs.append("<h3>そのほか前段階となる資格</h3><ul>"
                    + "".join(li(s, n) for s, n in branch_down) + "</ul>")
    if rel["exempt_to"] or rel["exempt_from"]:
        items = "".join(li(s, n) for s, n in rel["exempt_to"] + rel["exempt_from"])
        subs.append("<h3>試験の免除・受験資格の優遇</h3><ul>" + items + "</ul>")
    if rel["combo"]:
        subs.append("<h3>あわせて取りたい資格（ダブルライセンス）</h3><ul>"
                    + "".join(li(s, n) for s, n in rel["combo"]) + "</ul>")
    if not rm and not subs:
        return ""
    return ('<section class="rel-certs"><h2>ステップアップ・上位資格を目指す</h2>'
            + rm + "".join(subs)
            + '<p class="muted">※免除・受験資格の要件は変更されることがあります。'
              '出願前に必ず各資格の公式情報でご確認ください。</p></section>')


def materials_section_html(slug):
    """おすすめ教材・講座セクション。アフィリンクがある場合は広告表示(景表法/ステマ規制)と
    rel=sponsored を自動付与する。教材が無ければ空文字。"""
    mats = MATERIALS.get(slug) or []
    if not mats:
        return ""
    has_aff = any(m["affiliate"] for m in mats)
    items = []
    for m in mats:
        link = m["affiliate"] or m["url"]
        rel = "sponsored nofollow noopener" if m["affiliate"] else "nofollow noopener"
        if link:
            title_html = (f'<a href="{esc(link)}" rel="{rel}" target="_blank">'
                          f'{esc(m["title"])} ↗</a>')
        else:
            title_html = esc(m["title"])
        prov = f' <span class="muted">／{esc(m["provider"])}</span>' if m["provider"] else ""
        note = f'<span class="mat-note">{esc(m["note"])}</span>' if m["note"] else ""
        items.append(f'<li><span class="mat-kind">{esc(m["kind"])}</span>'
                     f'<span class="mat-body">{title_html}{prov}{note}</span></li>')
    pr = '<span class="pr-badge">PR</span>' if has_aff else ""
    disclosure = (
        '<p class="ad-disclosure">本セクションには広告（アフィリエイトリンク）を含みます。'
        'リンクを経由して購入・申込みされた場合、当サイトが収益を得ることがあります。'
        '掲載は編集部の選定によるもので、内容の正確性・価格は各提供元の公式情報をご確認ください。</p>'
        if has_aff else "")
    return (
        f'<section class="materials-sec"><h2>おすすめテキスト・講座{pr}</h2>'
        f'{disclosure}'
        f'<ul class="materials">{"".join(items)}</ul>'
        '<p class="muted mat-foot">編集部が選んだ学習教材・講座の例です。最新の価格・改訂版・'
        '開講状況は各販売元・提供元の公式情報で必ずご確認ください。</p></section>')


def applicants_num(r):
    """受験者数の文字列から代表数（最初の「N人/N名」）を整数で。なければ None。"""
    ed = EXAM.get(r.get("slug", ""))
    if not ed or not ed.get("applicants"):
        return None
    m = re.search(r"([0-9][0-9,]*)\s*[人名]", ed["applicants"])
    return int(m.group(1).replace(",", "")) if m else None


def page_shell(title: str, body: str, depth: int, noindex: bool = True,
               desc: str = "", path: str = "", jsonld=None) -> str:
    base = "../" * depth
    robots = ('<meta name="robots" content="noindex">\n' if noindex else "")
    desc = desc or SITE_DESC
    canon = BASE_URL + "/" + path
    og_img = BASE_URL + "/assets/og.png"
    og = (f'<link rel="canonical" href="{esc(canon)}">\n'
          f'<meta property="og:type" content="website">\n'
          f'<meta property="og:site_name" content="{esc(SITE_NAME)}">\n'
          f'<meta property="og:title" content="{esc(title)}">\n'
          f'<meta property="og:description" content="{esc(desc)}">\n'
          f'<meta property="og:url" content="{esc(canon)}">\n'
          f'<meta property="og:locale" content="ja_JP">\n'
          f'<meta property="og:image" content="{esc(og_img)}">\n'
          f'<meta property="og:image:width" content="1200">\n'
          f'<meta property="og:image:height" content="630">\n'
          f'<meta name="twitter:card" content="summary_large_image">\n'
          f'<meta name="twitter:image" content="{esc(og_img)}">\n')
    ld = ""
    if jsonld:
        for obj in (jsonld if isinstance(jsonld, list) else [jsonld]):
            ld += f'<script type="application/ld+json">{json.dumps(obj, ensure_ascii=False)}</script>\n'
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#1a1a1a">
{robots}<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{og}<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap"></noscript>
<link rel="icon" href="{base}assets/favicon.ico" sizes="32x32">
<link rel="icon" href="{base}assets/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{base}assets/apple-touch-icon.png">
<link rel="stylesheet" href="{base}assets/app.css">
{ld}</head>
<body>
<a class="skip-link" href="#main">本文へスキップ</a>
<header class="site-header" id="siteHeader">
  <div class="header-inner">
    <div class="header-brand"><a class="logo" href="{base}index.html">{esc(SITE_NAME)}</a>
      <span class="site-tagline">就職・転職・スキルアップの資格情報</span></div>
    <nav class="header-nav" aria-label="サイトメニュー">
      <a href="{base}index.html#purpose">目的から探す</a><span class="header-nav-sep" aria-hidden="true">｜</span>
      <a href="{base}index.html#fields">分野から探す</a><span class="header-nav-sep" aria-hidden="true">｜</span>
      <a href="{base}index.html">資格一覧</a><span class="header-nav-sep" aria-hidden="true">｜</span>
      <a href="{base}shoku/index.html">職種から探す</a>
    </nav>
    <div class="header-actions">
      <button type="button" class="header-icon-btn" data-toggle="search" aria-label="資格名で検索" aria-controls="hSearch" aria-expanded="false"><svg class="ico-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L21 21"/></svg></button>
      <button type="button" class="header-icon-btn" data-toggle="menu" aria-label="メニューを開く" aria-controls="hMenu" aria-expanded="false"><svg class="ico-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>
    </div>
  </div>
  <div class="header-search-panel" id="hSearch" hidden>
    <form class="header-search-form" role="search" action="{base}index.html" method="get">
      <input type="search" name="q" placeholder="資格名で検索（例: 簿記、宅建、ITパスポート）" aria-label="資格名で検索">
      <button type="submit">検索</button>
    </form>
  </div>
  <nav class="header-menu-panel" id="hMenu" aria-label="サイトメニュー" hidden>
    <a href="{base}index.html#purpose">目的から探す</a>
    <a href="{base}index.html#fields">分野から探す</a>
    <a href="{base}index.html">資格一覧</a>
    <a href="{base}shoku/index.html">職種から探す</a>
  </nav>
</header>
<main class="container" id="main">
{body}
</main>
<div id="cmpbar" class="cmpbar" data-base="{base}" aria-live="polite"></div>
<script src="{base}assets/compare-bar.js"></script>
<footer class="site-footer">
  <div class="site-footer-inner">
    <p class="site-footer-brand">{esc(SITE_NAME)}</p>
    <nav class="site-footer-nav" aria-label="フッターナビ">
      <a href="{base}index.html">資格一覧</a>
      <a href="{base}index.html#fields">分野から探す</a>
      <a href="{base}shoku/index.html">職種から探す</a>
      <a href="{base}index.html#compare">よく比較される資格</a>
      <a href="{base}about.html">サイトについて・編集方針</a>
    </nav>
    {partner_footer_html()}
    <p class="site-footer-note">掲載内容は参考情報です。受験料・合格率・制度・日程等は変更される場合があるため、出願前に各資格の公式情報で必ずご確認ください。各詳細ページに最終確認日と情報源を表示しています。</p>
    <p class="site-footer-copy">© {esc(SITE_NAME)}／一覧データ出典: 厚生労働省 ハローワーク「免許・資格コード一覧」ほか、各資格の公式の一次情報に基づき整備。</p>
  </div>
</footer>
<script>(function(){{var h=document.getElementById('siteHeader');if(!h)return;function close(){{h.classList.remove('site-header--search-open','site-header--menu-open');h.querySelectorAll('[data-toggle]').forEach(function(b){{b.setAttribute('aria-expanded','false');}});}}h.querySelectorAll('[data-toggle]').forEach(function(b){{b.addEventListener('click',function(){{var k=b.getAttribute('data-toggle');var cls=k==='search'?'site-header--search-open':'site-header--menu-open';var open=h.classList.contains(cls);close();if(!open){{h.classList.add(cls);b.setAttribute('aria-expanded','true');var p=document.getElementById(k==='search'?'hSearch':'hMenu');if(p){{p.hidden=false;var inp=p.querySelector('input');if(inp)setTimeout(function(){{inp.focus();}},30);}}}}}});}});document.addEventListener('keydown',function(e){{if(e.key==='Escape')close();}});}})();</script>
</body>
</html>
"""


def build_detail(row) -> str:
    name = row["name"]
    label, cls = TYPE_BADGE.get(row["type"], ("区分要確認", "badge-unknown"))
    major = row["major_category"]
    cat = row["category"]

    def field(v, fallback="公式情報で確認"):
        return esc(v) if v else f'<span class="muted">{fallback}</span>'

    official = ""
    if row["official_url"]:
        u = esc(row["official_url"])
        official = f'<a href="{u}" rel="nofollow noopener" target="_blank">公式サイト</a>'
    else:
        official = '<span class="muted">未登録（一次情報で確認予定）</span>'

    spec = [
        ("資格区分", f'<span class="badge {cls}">{esc(label)}</span>'
                    f' <span class="muted">（{esc(row["type_reason"])}）</span>'),
        ("分野（大分類）", esc(major)),
        ("カテゴリ", esc(cat)),
        ("実施団体", field(row["authority"])),
        ("公式サイト", official),
        ("受験資格", field(row["eligibility"])),
        ("試験形式", field(row["exam_format"])),
        ("受験料", field(row["fee"])),
        ("合格率", field(row["pass_rate"])),
        ("実施頻度", field(row["frequency"])),
        ("ハローワークコード", esc(row["hellowork_code"])),
    ]
    ed = EXAM.get(row["slug"], {})
    if ed.get("applicants"):
        spec.append(("受験者数", esc(ed["applicants"])))
    diff = difficulty(row)
    if diff:
        dlabel, dcls = diff
        spec.append(("難易度の目安",
                     f'<span class="diff-badge {dcls}">{esc(dlabel)}</span>'
                     f' <span class="muted">（公表合格率 {esc(row["pass_rate"])} に基づく簡易目安）</span>'))
    dr = DIFFICULTY_RANK.get(row["slug"])
    if dr:
        badges = [f'<span class="diff-rank">掲載資格中 上位{dr["pct"]}%</span>']
        if dr.get("fpct"):
            badges.append(f'<span class="diff-rank diff-rank-field">'
                          f'{esc(dr["fname"])}分野内 上位{dr["fpct"]}%</span>')
        conf_note = {"高": "高（主要指標2つ以上で算出）",
                     "中": "中（単一指標ベースの参考値）"}.get(dr["conf"], dr["conf"])
        meta = (f'信頼度: {conf_note}／スコア算出{dr["total"]}件中{dr["rank"]}位相当。'
                f'{"・".join(dr["srcs"])}から算出した編集部の総合スコアで、'
                f'難易度の絶対指標ではありません。')
        spec.append(("総合難易度（目安）",
                     " ".join(badges)
                     + f'<div class="muted diff-meta">{meta}</div>'))
    if ed.get("exam_subjects"):
        spec.append(("試験科目・出題範囲", esc(ed["exam_subjects"])))
    st = STUDY.get(row["slug"], {})
    if st.get("study_hours"):
        spec.append(("学習時間の目安",
                     esc(st["study_hours"])
                     + ' <span class="muted">（編集部調べの目安。個人差があり、公式の数値ではありません）</span>'))
    inds = industry_tags(row)
    if inds:
        chips = "".join(
            f'<a class="tag-chip tag-ind" href="../index.html?industry={quote(t)}#all"'
            f' title="「{esc(t)}」で活かせる資格を探す">{esc(t)}</a>' for t in inds)
        spec.append(("活かせる業界", chips))
    tags = cert_tags(row)
    if tags:
        chips = "".join(
            f'<a class="tag-chip" href="../index.html?tag={quote(t)}#all"'
            f' title="「{esc(t)}」の資格を探す">{esc(t)}</a>' for t in tags)
        spec.append(("特徴・目的タグ", chips))
    src = row.get("source_checked_at", "")
    if src:
        spec.append(("情報確認日", esc(src) + ' <span class="muted">（公式の一次情報に基づき確認）</span>'))
    # ページ上部の「基本情報」グリッドに出す項目は詳細表から省いて重複を避ける
    _grid_keys = {"資格区分", "受験料", "実施頻度"}
    rows_html = "".join(f"<tr><th>{esc(k)}</th><td>{v}</td></tr>"
                        for k, v in spec if k not in _grid_keys)

    # 基本情報グリッド（区分・受験料・受験資格・実施頻度）
    def _short_elig(v):
        if not v:
            return '<span class="muted">公式で確認</span>'
        if re.search(r"(受験資格|制限)?(なし|不問)", v) and "実務" not in v and "級" not in v:
            return "なし"
        return esc(v if len(v) <= 16 else v[:15] + "…")
    facts_grid = (
        '<div class="detail-facts" aria-label="基本情報"><div class="facts">'
        f'<div class="fact"><div class="l">区分</div><div class="v">{esc(label)}</div></div>'
        f'<div class="fact"><div class="l">受験料</div><div class="v">{field(row["fee"], "公式で確認")}</div></div>'
        f'<div class="fact"><div class="l">受験資格</div><div class="v">{_short_elig(row["eligibility"])}</div></div>'
        f'<div class="fact"><div class="l">実施頻度</div><div class="v">{field(row["frequency"], "公式で確認")}</div></div>'
        + (f'<div class="fact"><div class="l">合格率</div><div class="v">{esc(row["pass_rate"])}</div></div>'
           if row["pass_rate"] else "")
        + (f'<div class="fact"><div class="l">学習目安</div><div class="v">{esc(st_h)}</div></div>'
           if (st_h := (STUDY.get(row["slug"], {}) or {}).get("study_hours", "")) else "")
        + '</div></div>')

    # 公式サイトへの導線（CTA）と出典・注意書き
    if row["official_url"]:
        u = esc(row["official_url"])
        cta = (f'<p class="official-cta"><a class="btn-official" href="{u}" '
               f'rel="nofollow noopener" target="_blank">公式サイトで最新情報を確認 ↗</a></p>')
    else:
        cta = ""
    provenance = (
        '<p class="provenance">受験料・試験形式・受験資格・合格率・実施団体は、'
        '各資格の<strong>公式の一次情報</strong>に基づいて整備しています。'
        '制度・金額・日程は改定されることがあるため、出願前に必ず公式サイトで'
        'ご確認ください。空欄の項目は公式で確認のうえ追記します。</p>')

    # 鮮度シグナル（最終更新日の可視表示）
    jd = jp_date(src)
    updated_html = (f'<p class="updated">最終更新: {esc(jd)}'
                    f'<span class="muted">（公式の一次情報に基づき確認）</span></p>\n') if jd else ""

    # ユニーク本文（概要）— 手書きの独自解説があれば優先、なければテンプレート生成
    hand_desc = DESC.get(row["slug"], "")
    if hand_desc:
        lead = esc(hand_desc)
    else:
        lead = f"{esc(name)}は、{esc(major)}分野の{esc(label)}です。"
        if row["authority"]:
            lead += f"実施団体は{esc(row['authority'])}。"
        lead += "このページでは受験料・試験形式・受験資格・合格率・実施頻度・公式サイトをまとめています。"
    fact = []
    if row["fee"]:
        fact.append(f"受験料は{esc(row['fee'])}")
    if row["pass_rate"]:
        fact.append(f"合格率は{esc(row['pass_rate'])}")
    if row["exam_format"]:
        fact.append(f"試験形式は{esc(row['exam_format'])}")
    if row["frequency"]:
        fact.append(f"実施頻度は{esc(row['frequency'])}")
    fact_p = (f"<p>{name}の概要: " + "、".join(fact)
              + "。最新の金額・日程・合格率は公式サイトで必ずご確認ください。</p>") if fact else ""

    # 活かせる仕事・キャリア（職種DBへの内部リンク化 + job tag 導線）
    cur = CAREERS.get(row["slug"])
    if cur:
        items = []
        for tok in cur["careers"].split("、"):
            tok = tok.strip()
            if not tok:
                continue
            nm, note = occlib.split_name_note(tok)
            nm = occlib.canonical(nm)
            note_html = f'<span class="muted">（{esc(note)}）</span>' if note else ""
            oid = OCC_ID_BY_NAME.get(nm)
            if oid:
                items.append(f'<li><a href="../shoku/{oid}.html">{esc(nm)}</a>{note_html}</li>')
            else:
                items.append(f'<li>{esc(nm)}{note_html}</li>')
        jobs_html = "".join(items)
        src_html = ""
        if cur["source"]:
            src_html = (f'<p class="muted careers-src">出典: '
                        f'<a href="{esc(cur["source"])}" rel="nofollow noopener" target="_blank">'
                        f'公式・job tag 等</a>（職種名から各職種ページへ：その職種に活かせる資格を逆引きできます）</p>')
        careers_body = f'<ul class="careers">{jobs_html}</ul>{src_html}'
    else:
        careers_body = (f'<p class="muted">{esc(name)}（{esc(major)}分野）を要件・推奨とする'
                        '職業は個別に精査中です。関連する職業は、厚生労働省の職業情報提供'
                        'サイト（job tag）で資格名から検索できます。</p>')
    careers_section = (
        '<section class="careers-sec"><h2>活かせる仕事・キャリア</h2>'
        + careers_body
        + f'<p class="jobtag"><a href="{JOBTAG_URL}" rel="nofollow noopener" '
          f'target="_blank">厚生労働省 job tag で関連職業を調べる ↗</a></p></section>')

    # 関連内部リンク
    bslug = MAJOR_SLUGS.get(major, "other")
    rel = [(f"../bunya/{bslug}.html", f"{major}の資格一覧")]
    tslug = {"国家": "national", "公的": "public"}.get(row["type"])
    if tslug:
        rel.append((f"../feature/{tslug}.html", f"{label}の一覧"))
    if is_noreq(row):
        rel.append(("../feature/no-requirement.html", "受験資格なしで受けられる資格"))
    if is_cbt(row):
        rel.append(("../feature/cbt.html", "在宅・CBTで受けられる資格"))
    # 意図ハブへの相互リンク（属するガイドのみ）
    s = row["slug"]
    if s in HUB_INDEPENDENCE_SET:
        rel.append(("../feature/independence.html", "独立・開業を目指せる資格"))
    if s in HUB_JOB_SET:
        rel.append(("../feature/job-hunting.html", "就職・転職に役立つ資格"))
    if s in HUB_REMOTE_SET:
        rel.append(("../feature/remote-work.html", "在宅・リモートワークに活かせる資格"))
    if s in HUB_TRADE_SET:
        rel.append(("../feature/skilled-trade.html", "手に職をつけられる資格"))
    if s in HUB_IT_BEGINNER_SET:
        rel.append(("../feature/it-beginner.html", "未経験からITエンジニアを目指す資格"))
    if s in HUB_SENIOR_SET:
        rel.append(("../feature/senior.html", "定年後・シニアに役立つ資格"))
    if is_working_adult(row):
        rel.append(("../feature/working-adults.html", "働きながら取りやすい資格"))
    # 比較ペアは下の「よく比較される資格」で扱うため、ここでは一覧・特集への導線のみ
    rel += [("../feature/cheap.html", "受験料が安い資格ランキング"),
            ("../feature/high-pass.html", "合格率が高い資格")]
    more_links = ('<nav class="more-links" aria-label="もっと探す"><h3>もっと探す</h3><ul>'
                  + "".join(f'<li><a href="{u}">{esc(t)}</a></li>' for u, t in rel)
                  + "</ul></nav>")

    # FAQ 構造化データ
    qa = []
    if row["fee"]:
        qa.append((f"{name}の受験料はいくらですか？", row["fee"]))
    if row["eligibility"]:
        qa.append((f"{name}に受験資格はありますか？", row["eligibility"]))
    if row["exam_format"]:
        qa.append((f"{name}の試験はどのような形式ですか？", row["exam_format"]))
    if row["pass_rate"]:
        qa.append((f"{name}の合格率はどのくらいですか？", row["pass_rate"]))
    if ed.get("exam_subjects"):
        qa.append((f"{name}の試験科目・出題範囲は？", ed["exam_subjects"]))
    if ed.get("applicants"):
        qa.append((f"{name}の受験者数はどのくらいですか？", ed["applicants"]))
    if row["frequency"]:
        qa.append((f"{name}はいつ実施されますか？", row["frequency"]))
    if row["authority"]:
        qa.append((f"{name}の実施団体はどこですか？", row["authority"]))
    # 派生Q&A（保有データに基づく事実回答。ロングテール検索を狙う）
    _sth = (STUDY.get(row["slug"], {}) or {}).get("study_hours", "")
    if is_noreq(row):
        qa.append((f"{name}は誰でも受験できますか？",
                   "受験資格の制限はなく、誰でも受験できます。"))
    if is_cbt(row):
        qa.append((f"{name}は在宅・CBTで受けられますか？",
                   "CBT（テストセンターやネット試験）方式に対応しています。会場や日程は公式サイトでご確認ください。"))
    if _sth:
        qa.append((f"{name}の合格に必要な学習時間の目安は？",
                   f"編集部調べでは{_sth}が目安です（個人差があり、公式の数値ではありません）。"))
    _dq = difficulty(row)
    if _dq and row["pass_rate"]:
        qa.append((f"{name}の難易度はどのくらいですか？",
                   f"公表合格率（{row['pass_rate']}）に基づく簡易的な目安では「{_dq[0]}」です。"
                   "合格率は受験者層により変わるため、難易度の絶対指標ではありません。"))
    faq = ({"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q,
                            "acceptedAnswer": {"@type": "Answer", "text": a}}
                           for q, a in qa]} if qa else None)
    faq_html = ""
    if qa:
        _items = "".join(
            f'<details class="faq-item"><summary>{esc(q)}</summary>'
            f'<div class="faq-a">{esc(a)}</div></details>' for q, a in qa)
        faq_html = ('<section class="detail-faq" aria-labelledby="faq-h">'
                    f'<h2 class="detail-section-title" id="faq-h">{esc(name)}のよくある質問</h2>'
                    f'{_items}</section>')

    _mat = materials_section_html(row["slug"])
    _mat_block = ("\n" + _mat) if _mat else ""
    _rel = cert_relations_html(row["slug"])
    _rel_block = ("\n" + _rel) if _rel else ""

    # 関連資格との比較（この資格が含まれる比較ペア＝静的vsページへ）
    vs_pairs = []
    for ps, other in COMPARE_INDEX.get(row["slug"], []):
        if other in INDEXABLE_SLUGS:
            on = re.sub(r"[（(].*?[）)]", "", NAME_BY_SLUG.get(other, other)).strip() or other
            vs_pairs.append((ps, on))
    compare_block = ""
    if vs_pairs:
        links = " ・ ".join(f'<a href="../vs/{esc(ps)}.html">{esc(on)}との違い</a>'
                            for ps, on in vs_pairs[:5])
        compare_block = ('<div class="more-compare"><h3>よく比較される資格</h3>'
                         f'<p>よく一緒に比較されます： {links}</p></div>')

    # 出典・最終確認日（フッターだけでなく資格ごとに明示）
    if row["official_url"]:
        u = esc(row["official_url"])
        official_src = f'<a href="{u}" rel="nofollow noopener" target="_blank">公式サイト</a>'
        if row["authority"]:
            official_src += f'（{esc(row["authority"])}）'
    elif row["authority"]:
        official_src = esc(row["authority"])
    else:
        official_src = "各資格の公式情報"
    source_aside = (
        '<aside class="detail-source" aria-label="情報の出典">'
        f'<p><span class="k">最終確認日：</span>{esc(jd) if jd else "—"}</p>'
        f'<p><span class="k">情報源：</span>{official_src}</p>'
        '<p class="detail-source-note">受験料・受験資格・試験形式・合格率・実施団体は公式の一次情報に基づきます。'
        '学習時間・難易度・総合スコアは編集部による目安で、公式の数値ではありません。'
        '制度・金額・日程は改定されることがあるため、出願前に必ず公式サイトでご確認ください。</p>'
        '</aside>')

    # この資格のポイント（保有データ・タグから導く定性的ハイライト。捏造しない）
    pts = []
    if is_noreq(row):
        pts.append("受験資格の制限がなく、誰でも受験できます")
    if is_cbt(row):
        pts.append("CBT・ネット試験に対応し、比較的受けやすい試験です")
    _d = difficulty(row)
    if _d:
        pts.append(f"難易度の目安は「{_d[0]}」です（公表合格率に基づく簡易目安）")
    _tg = cert_tags(row)
    _tagmsg = [("就職・転職", "就職・転職でアピールしやすい資格です"),
               ("独立・開業", "独立・開業につながる資格です"),
               ("在宅ワーク", "在宅・リモートワークに活かせます"),
               ("手に職", "手に職をつけられる実務的な資格です"),
               ("未経験からIT", "未経験からITを目指す入口になります"),
               ("定年後・シニア", "定年後・シニアの活動にも役立ちます")]
    for _k, _m in _tagmsg:
        if _k in _tg:
            pts.append(_m)
    _inds = industry_tags(row)
    if _inds:
        pts.append(f"主に{'・'.join(_inds[:2])}の分野で活かせます")
    pts = pts[:5]
    points_html = ""
    if pts:
        _lis = "".join(f"<li>{esc(p)}</li>" for p in pts)
        points_html = ('<section class="detail-points" aria-labelledby="dp-h">'
                       '<h2 class="detail-section-title" id="dp-h">この資格のポイント</h2>'
                       f'<ul class="point-list">{_lis}</ul></section>')

    # 「最近見た資格」記録（localStorage）
    _rn = esc(re.sub(r"[（(].*?[）)]", "", name).strip() or name)
    recent_js = ("<script>(function(){try{var k='recent',a=JSON.parse(localStorage.getItem(k)||'[]');"
                 f"a=a.filter(function(x){{return x.s!=='{esc(row['slug'])}';}});"
                 f"a.unshift({{s:'{esc(row['slug'])}',n:'{_rn}'}});a=a.slice(0,8);"
                 "localStorage.setItem(k,JSON.stringify(a));}catch(e){}})();</script>")
    partner_detail = partner_detail_html(row["slug"])
    body = f"""<nav class="crumbs"><a href="../index.html">トップ</a> ›
<a href="../bunya/{esc(bslug)}.html">{esc(major)}</a> › {esc(name)}</nav>
<h1 class="detail-title">{esc(name)}</h1>
<p class="detail-audience">{lead}</p>
{facts_grid}
<div class="detail-actions"><button type="button" class="cmp-add-btn" data-slug="{esc(row["slug"])}" data-name="{esc(re.sub(r"[（(].*?[）)]", "", name).strip() or name)}">＋ 比較</button>{cta}</div>
{points_html}
{partner_detail}
<section class="detail-spec" aria-labelledby="ds-h">
<h2 class="detail-section-title" id="ds-h">詳細情報</h2>
<table class="spec">{rows_html}</table></section>
{provenance}
{faq_html}
{careers_section}{_mat_block}{_rel_block}
<section class="detail-related" aria-labelledby="dr2-h">
<h2 class="detail-section-title" id="dr2-h">ほかの資格を見る・比較する</h2>
<div class="more-same"><h3>同じ分野の他の資格</h3><ul id="related"></ul></div>
{compare_block}
{more_links}
</section>
{source_aside}
<script>
fetch("../data/certifications.json").then(r=>r.json()).then(all=>{{
  const cat={json.dumps(cat, ensure_ascii=False)}, me={json.dumps(row["slug"], ensure_ascii=False)};
  const ul=document.getElementById("related");
  all.filter(x=>x.category===cat&&x.slug!==me).slice(0,12).forEach(x=>{{
    const li=document.createElement("li");
    li.innerHTML='<a href="'+x.slug+'.html">'+x.name+'</a>';
    ul.appendChild(li);
  }});
  if(!ul.children.length) ul.innerHTML='<li class="muted">なし</li>';
}});
</script>
{recent_js}
"""
    # meta description は各ページで一意になるよう、必ず固有の資格名で始め、
    # 固有の事実（受験料・合格率・実施団体）を添える（家族で共通の説明文の重複を回避）。
    _short = re.sub(r"[（(].*?[）)]", "", name).strip() or name
    lead_txt = hand_desc or f"{name}は{major}分野の{label}です。"
    if _short not in lead_txt:
        lead_txt = f"{_short}は{label}。" + lead_txt
    _facts = []
    if row["fee"]:
        _facts.append("受験料" + row["fee"])
    if row["pass_rate"]:
        _facts.append("合格率" + row["pass_rate"])
    if not _facts and row["authority"]:
        _facts.append("実施団体は" + row["authority"])
    desc = lead_txt + ("（" + "／".join(_facts) + "）" if _facts else "")
    desc = re.sub(r"\s+", " ", desc).strip()
    if len(desc) < 90:
        desc += " 受験資格・試験形式・公式サイトも掲載。"
    desc = desc[:158]
    breadcrumb = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "トップ", "item": BASE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": major,
             "item": f"{BASE_URL}/bunya/{bslug}.html"},
            {"@type": "ListItem", "position": 3, "name": name},
        ],
    }
    # schema.org/EducationalOccupationalCredential（資格＝資格証明）
    credential = {
        "@context": "https://schema.org",
        "@type": "EducationalOccupationalCredential",
        "name": name,
        "url": f'{BASE_URL}/c/{row["slug"]}.html',
        "credentialCategory": label,
    }
    cred_desc = hand_desc or f"{name}は、{major}分野の{label}です。"
    credential["description"] = cred_desc[:300]
    if row["authority"]:
        credential["recognizedBy"] = {"@type": "Organization",
                                      "name": row["authority"]}
    if ed.get("exam_subjects"):
        credential["competencyRequired"] = ed["exam_subjects"][:300]
    ld = [breadcrumb, credential] + ([faq] if faq else [])
    return page_shell(f"{name}｜{SITE_NAME}", body, depth=1,
                      noindex=(not is_indexable_detail(row)),
                      desc=desc, path=f'c/{row["slug"]}.html', jsonld=ld)


def fee_yen(r):
    """受験料文字列から代表額（最初の「N円」）を整数で。なければ None。"""
    m = re.search(r"([0-9][0-9,]*)\s*円", r.get("fee", ""))
    return int(m.group(1).replace(",", "")) if m else None


def pass_pct(r):
    """合格率文字列から最初の「N%」を float で。なければ None。"""
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", r.get("pass_rate", ""))
    return float(m.group(1)) if m else None


def difficulty(r):
    """公表合格率から難易度バンドを推定。(ラベル, CSSクラス) を返す。なければ None。

    合格率は資格ごとに母集団（受験者層）が大きく異なるため厳密な難易度ではなく、
    あくまで公表合格率に基づく簡易的な目安。確証のため pass_rate がある時のみ表示。
    """
    p = pass_pct(r)
    if p is None:
        return None
    if p < 10:
        return ("難関", "diff-veryhard")
    if p < 30:
        return ("やや難関", "diff-hard")
    if p < 60:
        return ("標準", "diff-mid")
    if p < 80:
        return ("比較的やさしい", "diff-easy")
    return ("入門〜標準", "diff-veryeasy")


def study_hours_max(slug):
    """学習時間文字列から代表値（範囲なら上限）を時間で。なければ None。"""
    s = (STUDY.get(slug, {}) or {}).get("study_hours", "")
    nums = [int(x.replace(",", "")) for x in re.findall(r"([0-9][0-9,]*)", s)]
    return max(nums) if nums else None


def eff_pass_pct(r):
    """合格率文字列の全%を段階（一次/二次・学科/実地）の積として合成した実効合格率(%)。
    例: 一次36.7%/二次49.6% → 0.367×0.496 = 18.2%。なければ None。"""
    nums = [float(x) for x in re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*%", r.get("pass_rate", ""))]
    if not nums:
        return None
    p = 1.0
    for n in nums:
        p *= min(max(n, 0.0), 100.0) / 100.0
    return p * 100.0


_ELIG_NEG = re.compile(r"(受験資格.{0,4}(なし|不問)|制限なし|どなたでも|誰でも|だれでも"
                       r"|学歴.{0,3}不問|年齢.{0,3}不問|実務.{0,3}不問)")


def elig_strictness(r):
    """受験資格テキストから受験ハードルを 0-1 で粗く推定。判別不能・空は None。

    注: 受験資格の厳しさは試験そのものの難しさとは別物。総合スコアでは低い重みの
    「補助シグナル」として、主要シグナル（合格率・学習時間・難易度データ）がある資格の
    位置を微調整する用途に限って使う（単独では極端な順位を作らない）。"""
    t = (r.get("eligibility") or "").strip()
    if not t:
        return None
    if _ELIG_NEG.search(t):
        return 0.10
    m = re.search(r"実務.{0,4}(?:経験|従事).{0,8}?(\d+)\s*年", t)
    if m:
        y = int(m.group(1))
        return 0.85 if y >= 5 else 0.70 if y >= 3 else 0.60
    if re.search(r"実務.{0,4}経験|業務.{0,4}経験|従事.{0,3}経験", t):
        return 0.60
    if re.search(r"(大学|短大|高専|専門学校|高校|学校).{0,8}(卒|修了|在学|課程|履修)", t):
        return 0.50
    if re.search(r"(資格.{0,5}保有|合格者|級.{0,5}(取得|保持)|上位.{0,3}資格"
                 r"|指定.{0,5}講習|登録.{0,4}(必要|要)|養成.{0,3}課程)", t):
        return 0.55
    return None


# 総合難易度ランキング（合格率・学習時間・難易度データ・受験資格からの編集部スコア）。
# main() で build_difficulty_rank() が算出。
DIFFICULTY_RANK = {}  # slug -> {pct,rank,total,conf,fpct,frank,ftotal,fname,...}

# 各シグナルの重み（主要3軸＋補助1軸）と信頼度補正の強さ。
_W_PASS, _W_HOUR, _W_DIFF, _W_ELIG = 1.0, 0.8, 1.0, 0.35
_SHRINK_K0 = 0.9   # 大きいほど主要シグナルが少ない資格を中央値へ強く収縮
_FIELD_MIN = 8     # 分野内ランキングを出す最小母数


def build_difficulty_rank(rows):
    """合格率(実効)・学習時間・編集部難易度データを全体内パーセンタイルに正規化し、
    受験資格の厳しさを補助シグナルとして加重平均。主要シグナルの数に応じて中央値へ
    収縮(shrinkage)させ、過信を抑える。全体および分野内のランキングを DIFFICULTY_RANK に格納。"""
    import bisect
    from collections import defaultdict

    items = []  # (row, eff_pass, hours, diff_value, elig)
    pass_vals, hour_vals, diff_vals = [], [], []
    for r in rows:
        ep = eff_pass_pct(r)
        hr = study_hours_max(r["slug"])
        dv = (DIFFICULTY_DATA.get(r["slug"], {}) or {}).get("value")
        es = elig_strictness(r)
        if ep is None and hr is None and dv is None:
            continue  # 主要シグナルが1つも無ければ対象外（受験資格のみでは順位化しない）
        items.append((r, ep, hr, dv, es))
        if ep is not None:
            pass_vals.append(ep)
        if hr is not None:
            hour_vals.append(hr)
        if dv is not None:
            diff_vals.append(dv)
    pass_sorted, hour_sorted, diff_sorted = sorted(pass_vals), sorted(hour_vals), sorted(diff_vals)

    def pctl(sorted_vals, v):
        n = len(sorted_vals)
        return (bisect.bisect_left(sorted_vals, v) + 0.5) / n if n else None

    records = []  # (slug, major, hardness, conf, sources)
    for r, ep, hr, dv, es in items:
        sig = []  # (hardness0-1, weight, is_primary)
        if ep is not None:
            sig.append((1.0 - pctl(pass_sorted, ep), _W_PASS, True))   # 低合格率=難
        if hr is not None:
            sig.append((pctl(hour_sorted, hr), _W_HOUR, True))         # 長時間=難
        if dv is not None:
            sig.append((pctl(diff_sorted, dv), _W_DIFF, True))         # 難易度データ
        if es is not None:
            sig.append((es, _W_ELIG, False))                           # 受験資格(補助)
        wsum = sum(w for _, w, _ in sig)
        h_raw = sum(h * w for h, w, _ in sig) / wsum
        prim_w = sum(w for _, w, p in sig if p)
        nprim = sum(1 for _, _, p in sig if p)
        # 主要シグナルの重み総和が小さいほど中央値(0.5)へ収縮 → 単一指標の過信を抑制
        k = prim_w / (prim_w + _SHRINK_K0)
        h = 0.5 + (h_raw - 0.5) * k
        conf = "高" if nprim >= 2 else "中"
        srcs = []
        if ep is not None:
            srcs.append("合格率(実効)")
        if hr is not None:
            srcs.append("学習時間")
        if dv is not None:
            srcs.append("編集部難易度データ")
        if es is not None:
            srcs.append("受験資格の要件")
        records.append((r["slug"], r.get("major_category", ""), h, conf, srcs))

    records.sort(key=lambda x: (-x[2], x[0]))  # 難しい順、slug で安定化
    total = len(records)
    DIFFICULTY_RANK.clear()
    for i, (s, mj, h, conf, srcs) in enumerate(records):
        DIFFICULTY_RANK[s] = {"pct": max(1, math.ceil((i + 1) / total * 100)),
                              "rank": i + 1, "total": total, "conf": conf, "srcs": srcs}

    # 分野内ランキング（母集団差の補正）。母数が十分な分野のみ。
    groups = defaultdict(list)
    for s, mj, h, conf, srcs in records:
        groups[mj].append((s, h))
    for mj, lst in groups.items():
        if not mj or len(lst) < _FIELD_MIN:
            continue
        lst.sort(key=lambda x: (-x[1], x[0]))
        ft = len(lst)
        for j, (s, _h) in enumerate(lst):
            DIFFICULTY_RANK[s].update({"fpct": max(1, math.ceil((j + 1) / ft * 100)),
                                       "frank": j + 1, "ftotal": ft, "fname": mj})


def n_facts(r):
    """受験料・合格率・受験資格・試験形式・実施頻度のうち、値が入っている数。"""
    return sum(1 for k in ("fee", "pass_rate", "eligibility", "exam_format", "frequency")
               if r.get(k, "").strip())


def is_indexable_detail(r):
    """SEOインデックス対象の詳細ページか（インデックス衛生）。

    published かつ実データが十分なページのみインデックスし、薄いページ
    （廃止・旧制度・データほぼ無し）は noindex にしてサイト全体の評価希釈を防ぐ。
    条件: published かつ 受験料/合格率/受験資格のいずれかがあり、実データ2項目以上。
    """
    if r.get("status") != "published":
        return False
    has_key = bool(r.get("fee", "").strip() or r.get("pass_rate", "").strip()
                   or r.get("eligibility", "").strip())
    return has_key and n_facts(r) >= 2


def jp_date(iso):
    """'2026-06-18' → '2026年6月18日'。不正・空なら空文字。"""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", iso or "")
    return f"{int(m.group(1))}年{int(m.group(2))}月{int(m.group(3))}日" if m else ""


def is_cbt(r):
    return bool(re.search(r"CBT|ネット試験|IBT", r.get("exam_format", "")))


def is_noreq(r):
    return bool(re.search(r"受験資格なし|受検資格なし|制限なし|誰でも", r.get("eligibility", "")))


def _badge(t):
    label, cls = TYPE_BADGE.get(t, ("区分要確認", "badge-unknown"))
    return f'<span class="badge {cls}">{esc(label)}</span>'


def _list_items(items, depth, ranked=False):
    """資格の一覧／ランキングのリストHTML。
    2段組（資格名＋メタ情報）のカードで、ranked=True のとき順位番号を表示する。"""
    base = "../" * depth
    out = []
    for i, r in enumerate(items, 1):
        pub = r.get("status") == "published"
        meta = [_badge(r["type"]),
                f'<span class="cl-major">{esc(r["major_category"])}</span>']
        if pub:
            bits = [b for b in (r.get("fee"),
                                (("合格率" + r["pass_rate"]) if r.get("pass_rate") else "")) if b]
            meta.append('<span class="cl-data">'
                        + (esc(" / ".join(bits)) if bits else "データ掲載") + "</span>")
        else:
            meta.append(f'<span class="cl-cat">{esc(r["category"])}</span>')
        rank = ""
        if ranked:
            rank = (f'<span class="cl-rank{" cl-rank--top" if i <= 3 else ""}">'
                    f'{i}</span>')
        out.append(
            f'<li class="cl-item">{rank}'
            f'<a class="cl-link" href="{base}c/{esc(r["slug"])}.html">'
            f'<span class="cl-name">{esc(r["name"])}</span>'
            f'<span class="cl-meta">{"".join(meta)}</span></a></li>')
    cls = "cert-list" + (" cert-list--ranked" if ranked else "")
    return f'<ul class="{cls}">' + "".join(out) + "</ul>"


# 大分類のページslug（安定・ローマ字キー）
MAJOR_SLUGS = {
    "IT・情報処理": "it", "法律・法務・知財": "law", "会計・金融・経営": "finance",
    "不動産": "realestate", "建築・設備": "architecture", "設備・プラント・機械運転": "plant",
    "土木・測量・建設": "civil", "電気・通信": "electric", "機械・電気・ものづくり": "manufacturing",
    "食品・調理・栄養": "food", "医療・看護・薬": "medical", "福祉・介護・心理": "welfare",
    "教育・保育・学術": "education", "語学・コミュニケーション": "language",
    "デザイン・美術・文化": "design", "美容・サービス・スポーツ": "service",
    "商業・販売・事務": "business", "安全・環境・危険物": "safety",
    "運輸・運転・航空": "transport", "農林水産・動物": "agriculture", "海外資格": "overseas",
}

# 業界レイヤー（分野とは別軸）。分野→業界の対応＋全業界で通用する汎用資格。
MAJOR_INDUSTRY = {
    "IT・情報処理": "IT・通信", "法律・法務・知財": "法律・士業",
    "会計・金融・経営": "金融・会計", "不動産": "不動産",
    "建築・設備": "建設・不動産", "設備・プラント・機械運転": "建設・設備",
    "土木・測量・建設": "建設・土木", "電気・通信": "電気・通信",
    "機械・電気・ものづくり": "製造・ものづくり", "食品・調理・栄養": "食品・飲食",
    "医療・看護・薬": "医療・ヘルスケア", "福祉・介護・心理": "福祉・介護",
    "教育・保育・学術": "教育・保育", "語学・コミュニケーション": "語学・国際",
    "デザイン・美術・文化": "デザイン・クリエイティブ", "美容・サービス・スポーツ": "美容・サービス",
    "商業・販売・事務": "商業・販売・事務", "安全・環境・危険物": "安全・環境",
    "運輸・運転・航空": "運輸・物流", "農林水産・動物": "農林水産", "海外資格": "海外",
}
# 業種を問わず通用する汎用資格（事務・会計・労務・PC・語学・法務など）→「全業界で活かせる」
GENERIC_INDUSTRY_SLUGS = {
    "c-3623", "c-3624", "c-3625", "c-3626", "c-3627", "c-3628", "c-3629",  # 簿記
    "c-2515", "c-2516", "c-2517",  # FP
    "c-2510", "c-2202", "c-2203", "c-2204",  # 社労士・衛生管理者
    "c-2511", "c-3112",  # 中小企業診断士・キャリコン
    "c-2406", "c-2407", "c-2408", "c-2409",  # ビジ法務・知財管理
    "c-1538", "c-3815", "c-3816", "c-3817", "c-3818", "c-3838", "c-3839", "c-3840",  # ITパスポート・MOS
    "c-3841", "c-3842", "c-3843", "c-3844", "c-3845", "c-3846", "c-3879", "c-3880", "c-3881",  # 日商PC
    "c-3322", "c-3323", "c-3324", "c-3307", "c-3308", "c-3309",  # TOEIC・英検
    "c-3401", "c-3402", "c-3403", "c-3513", "c-3514", "c-3515",  # 秘書・ビジネス文書
    "c-4001", "c-4002", "c-4003", "c-4004", "c-4005", "c-4007", "c-4011", "c-4012",  # ビジキャリ
}


def industry_tags(r):
    """業界タグ（分野→業界の対応＋汎用資格の『全業界で活かせる』）。"""
    out = []
    ind = MAJOR_INDUSTRY.get(r["major_category"])
    if ind:
        out.append(ind)
    if r["slug"] in GENERIC_INDUSTRY_SLUGS:
        out.append("全業界で活かせる")
    return out


def build_category_pages(indexable):
    """大分類ごとの一覧ページ（site/bunya/<slug>.html）。"""
    pages = {}
    by_major = {}
    for r in indexable:
        by_major.setdefault(r["major_category"], []).append(r)
    for major, items in by_major.items():
        slug = MAJOR_SLUGS.get(major, "other")
        items.sort(key=lambda r: (r["status"] != "published", r["category"], r["name"]))
        npub = sum(1 for r in items if r["status"] == "published")
        from collections import Counter
        tc = Counter(r["type"] for r in items)
        tparts = "・".join(f"{t} {tc[t]}件" for t in ("国家", "公的", "民間", "要確認")
                          if tc.get(t))
        cats = sorted({r["category"] for r in items})
        body = (
            f'<nav class="crumbs"><a href="../index.html">トップ</a> › {esc(major)}</nav>'
            f"<h1>{esc(major)}の資格一覧</h1>"
            f'<p class="lead">「{esc(major)}」分野の資格 {len(items)} 件'
            f"（うち公式データ掲載 {npub} 件）。各資格の受験料・試験形式・受験資格・"
            f"合格率・実施団体・公式サイトを詳細ページで確認できます。</p>"
            f'<p class="muted">区分の内訳: {esc(tparts)}。'
            f"主なカテゴリ: {esc('、'.join(cats[:12]))}{'ほか' if len(cats) > 12 else ''}。</p>"
            + _list_items(items, depth=1)
        )
        ld = [
            {"@context": "https://schema.org", "@type": "BreadcrumbList",
             "itemListElement": [
                 {"@type": "ListItem", "position": 1, "name": "トップ",
                  "item": BASE_URL + "/"},
                 {"@type": "ListItem", "position": 2, "name": f"{major}の資格一覧"}]},
            {"@context": "https://schema.org", "@type": "ItemList",
             "name": f"{major}の資格一覧",
             "numberOfItems": len(items),
             "itemListElement": [
                 {"@type": "ListItem", "position": i,
                  "url": f'{BASE_URL}/c/{r["slug"]}.html', "name": r["name"]}
                 for i, r in enumerate(items[:50], 1)
                 if is_indexable_detail(r)]},
        ]
        pages[slug] = page_shell(
            f"{major}の資格一覧｜{SITE_NAME}", body, depth=1, noindex=False,
            desc=f"「{major}」分野の資格 {len(items)} 件（うち公式データ掲載 {npub} 件）。"
                 f"受験料・試験形式・受験資格・合格率を一覧・比較できます。",
            path=f"bunya/{slug}.html", jsonld=ld)
    return pages


# 特集・ランキングページの定義（トップのナビとも共有）
FEATURE_NAV = [
    ("popular", "受験者数が多い人気資格ランキング"),
    ("cheap", "受験料が安い資格ランキング"),
    ("high-pass", "合格率が高い資格"),
    ("hard", "合格率が低い難関資格"),
    ("cbt", "在宅・CBTで受けられる資格"),
    ("no-requirement", "受験資格なしで受けられる資格"),
    ("no-requirement-national", "受験資格なしで取れる国家資格"),
    ("national", "国家資格の一覧"),
    ("public", "公的資格の一覧"),
    ("data-available", "公式データ掲載資格の一覧"),
]

# 意図ベースのハブ（検索意図に当てる集約ページ）。掲載 slug は資格の性質に基づく編集上の選定。
HUB_INDEPENDENCE = [
    "c-3701", "c-2510", "c-2503", "c-2501", "c-2402", "c-2403", "c-2511", "c-3201",
    "c-3203", "c-2405", "c-3207", "c-3209", "c-1301", "c-1302", "c-4303", "c-4301",
    "c-4401", "c-6004", "c-2104", "c-2101", "c-2102", "c-2103", "c-2515",
]
HUB_JOB = [
    "c-3207", "c-2517", "c-3625", "c-3624", "c-1505", "c-1538", "c-4115", "c-2302",
    "c-3710", "c-3815", "c-3816", "c-3322", "c-2510", "c-3701", "c-1803", "c-2001",
    "c-2405", "c-2202",
]
HUB_REMOTE = [
    "c-1505", "c-1504", "c-1502", "c-1565", "c-1555", "c-3815", "c-3816", "c-3817",
    "c-3818", "c-3625", "c-3624", "c-2517", "c-3322", "c-2813", "c-1538",
]
HUB_TRADE = [
    "c-6809", "c-6808", "c-5818", "c-4401", "c-4303", "c-4301", "c-6004", "c-5206",
    "c-5207", "c-6702", "c-6703", "c-1315", "c-1404", "c-4115", "c-2302", "c-1907",
    "c-7110", "c-1313",
]
HUB_IT_BEGINNER = [
    "c-1538", "c-1505", "c-1504", "c-1565", "c-1502", "c-1510", "c-1503", "c-1555",
]
HUB_SENIOR = [
    "c-3207", "c-3209", "c-3210", "c-5207", "c-6703", "c-6809", "c-4401", "c-2517",
    "c-3701", "c-2510", "c-1622",
]
HUB_INDEPENDENCE_SET = set(HUB_INDEPENDENCE)
HUB_JOB_SET = set(HUB_JOB)
HUB_REMOTE_SET = set(HUB_REMOTE)
HUB_TRADE_SET = set(HUB_TRADE)
HUB_IT_BEGINNER_SET = set(HUB_IT_BEGINNER)
HUB_SENIOR_SET = set(HUB_SENIOR)

# 意図ハブのナビ（トップ・各ハブの相互リンク用）
INTENT_HUB_NAV = [
    ("independence", "独立・開業を目指せる資格"),
    ("job-hunting", "就職・転職に役立つ資格"),
    ("remote-work", "在宅・リモートワークに活かせる資格"),
    ("skilled-trade", "手に職をつけられる資格"),
    ("working-adults", "働きながら取りやすい資格"),
    ("it-beginner", "未経験からITエンジニアを目指す資格"),
    ("senior", "定年後・シニアに役立つ資格"),
]


def is_working_adult(r):
    """働きながら取りやすい資格の目安: 受験資格なし かつ（CBT/ネット試験 または 合格率40%以上）。"""
    if r.get("status") != "published" or not is_noreq(r):
        return False
    p = pass_pct(r)
    return is_cbt(r) or (p is not None and p >= 40)


def cert_tags(r):
    """目的別検索のための構造化タグ（クライアント検索JSONに搭載）。
    既存のキュレーション（意図ハブ）や客観データから機械的に導出する。"""
    s = r["slug"]
    tags = []
    # 目的（意図ハブのキュレーション集合から）
    if s in HUB_INDEPENDENCE_SET:
        tags.append("独立・開業")
    if s in HUB_JOB_SET or s in CAREERS:
        # 「活かせる仕事」が整備済み＝就職・転職に直結する資格
        tags.append("就職・転職")
    if s in HUB_REMOTE_SET:
        tags.append("在宅ワーク")
    if s in HUB_TRADE_SET:
        tags.append("手に職")
    if s in HUB_IT_BEGINNER_SET:
        tags.append("未経験からIT")
    if s in HUB_SENIOR_SET:
        tags.append("定年後・シニア")
    # 働き方・受験のしやすさ（客観データから）
    if is_noreq(r):
        tags.append("受験資格なし")
    if is_cbt(r):
        tags.append("CBT・ネット試験")
    if is_working_adult(r):
        tags.append("働きながら")
    return tags


# 比較ページの人気ペア（「A vs B」「A B どっち」「違い」系クエリに当てる）。
# (pair_slug, certA_slug, certB_slug, 固有の比較・選び方の導入文HTML)
COMPARE_PAIRS = [
    ("takken-gyoseishoshi", "c-3207", "c-3701",
     "どちらも受験資格のない人気の国家資格ですが、活かす分野が異なります。"
     "宅地建物取引士は<strong>不動産取引</strong>に特化し求人も多いのが強み、"
     "行政書士は<strong>官公庁への許認可申請など幅広い書類業務</strong>を扱い"
     "独立開業を見据えやすい資格です。難易度は一般に行政書士の方が高めです。"),
    ("gyoseishoshi-sharoshi", "c-3701", "c-2510",
     "ともに独立開業を狙える法律系国家資格です。行政書士は"
     "<strong>許認可・各種書類作成</strong>と業務範囲が広く、社会保険労務士は"
     "<strong>労働・社会保険・人事労務</strong>に専門特化します。"
     "社労士は受験資格があり、行政書士は誰でも受験できます。"),
    ("boki-2-3", "c-3624", "c-3625",
     "日商簿記の2級と3級の比較です。3級は<strong>商業簿記の基礎</strong>で"
     "経理の入門に、2級は<strong>商業簿記＋工業簿記</strong>まで広がり"
     "就職・転職で評価されやすくなります。まず3級から段階的に狙うのが定番です。"),
    ("kihonjoho-ojoho", "c-1505", "c-1504",
     "情報処理技術者試験の基本情報と応用情報の比較です。基本情報は"
     "<strong>IT基礎・開発の登竜門</strong>、応用情報は"
     "<strong>応用力・管理寄りの知識</strong>まで問う中級者向けで、"
     "難易度・評価ともに応用情報が一段上です。"),
    ("fp-2-3", "c-2516", "c-2517",
     "FP技能士の2級と3級の比較です。3級は<strong>家計・お金の基礎</strong>を"
     "学ぶ入門、2級は<strong>実務・相談業務で評価される</strong>水準で、"
     "金融・保険・不動産の仕事で活かすなら2級が目安です。"),
    ("takken-mankanshi", "c-3207", "c-3209",
     "不動産系国家資格同士の比較です。宅地建物取引士は"
     "<strong>不動産の売買・仲介</strong>に必須で求人が豊富、"
     "マンション管理士は<strong>マンション管理組合へのコンサル</strong>が中心です。"
     "求人数・汎用性では宅建が優勢です。"),
    ("mankanshi-kanrigyomu", "c-3209", "c-3210",
     "マンション管理士と管理業務主任者は試験範囲が近く同時受験も多い資格です。"
     "管理業務主任者は<strong>管理会社側で必置</strong>の実務資格、"
     "マンション管理士は<strong>管理組合側を支援</strong>するコンサル資格という違いがあります。"),
    ("shihoshoshi-gyoseishoshi", "c-2402", "c-3701",
     "司法書士と行政書士はどちらも独立できる法律系国家資格ですが、"
     "司法書士は<strong>登記・供託や簡裁訴訟代理</strong>が独占業務で難易度が高く、"
     "行政書士は<strong>許認可など官公庁書類</strong>が中心です。"),
    ("zeirishi-koninkaikeishi", "c-2503", "c-2501",
     "税理士と公認会計士はともに会計系の最高峰資格です。税理士は"
     "<strong>税務</strong>に特化し科目合格制で働きながら目指しやすく、"
     "公認会計士は<strong>監査</strong>が独占業務で大企業・監査法人が主戦場です。"),
    ("denki-2shu-1shu", "c-6809", "c-6808",
     "電気工事士の第二種と第一種の比較です。第二種は"
     "<strong>一般住宅・小規模設備</strong>、第一種は"
     "<strong>大規模なビル・工場の高圧設備</strong>まで扱えます。"
     "まず第二種から取得するのが一般的です。"),
    ("kaigofukushishi-caremane", "c-2302", "c-2308",
     "介護福祉士とケアマネジャー（介護支援専門員）の比較です。介護福祉士は"
     "<strong>現場の介護のプロ</strong>、ケアマネは"
     "<strong>ケアプラン作成・調整</strong>を担います。"
     "ケアマネは介護福祉士など実務経験を経て受験するのが一般的です。"),
    ("shakaifukushi-seishinhoken", "c-2301", "c-2307",
     "社会福祉士と精神保健福祉士はともに相談援助の国家資格です。社会福祉士は"
     "<strong>福祉全般</strong>を幅広く、精神保健福祉士は"
     "<strong>精神保健・精神障害分野</strong>に特化します。共通科目もあり"
     "ダブル取得を目指す人もいます。"),
    ("kanrieiyoshi-eiyoshi", "c-2001", "c-2002",
     "管理栄養士と栄養士の比較です。栄養士は<strong>養成施設の卒業</strong>で"
     "取得でき、管理栄養士は<strong>国家試験合格</strong>が必要な上位資格で、"
     "病院・行政・特定保健指導など活躍の幅が広がります。"),
    ("itpassport-kihonjoho", "c-1538", "c-1505",
     "ITパスポートと基本情報技術者の比較です。ITパスポートは"
     "<strong>社会人全般のITリテラシー</strong>を問う入門、基本情報は"
     "<strong>IT技術者の登竜門</strong>でより専門的です。"
     "IT職を目指すなら基本情報が目標になります。"),
    ("torokuhanbai-yakuzaishi", "c-4115", "c-1704",
     "登録販売者と薬剤師の比較です。登録販売者は"
     "<strong>第2類・第3類医薬品</strong>を扱える実務資格で受験資格がなく挑戦しやすい一方、"
     "薬剤師は<strong>6年制大学＋国家試験</strong>が必要ですべての医薬品を扱えます。"),
    ("shindanshi-sharoshi", "c-2511", "c-2510",
     "中小企業診断士と社会保険労務士の比較です。診断士は"
     "<strong>経営全般のコンサル</strong>、社労士は"
     "<strong>労務・社会保険の専門</strong>です。"
     "独占業務がある社労士に対し、診断士は名称独占で活かし方の自由度が高いのが特徴です。"),
    ("boki2-fp2", "c-3624", "c-2516",
     "就職・転職で人気の簿記2級とFP2級の比較です。簿記2級は"
     "<strong>企業の経理・会計</strong>に直結、FP2級は"
     "<strong>個人のお金・金融商品</strong>に強くなります。"
     "目指す職種（経理系か金融・保険系か）で選ぶのがおすすめです。"),
    ("sokuryoshi-sokuryoshiho", "c-1408", "c-1409",
     "測量士と測量士補の比較です。測量士補は<strong>測量の補助</strong>を行う入門、"
     "測量士は<strong>測量計画の作成</strong>まで担える上位資格です。"
     "測量士補は土地家屋調査士試験の一部免除にもつながります。"),
    ("denken3-denkikoji", "c-1205", "c-6808",
     "第三種電気主任技術者（電験三種）と第一種電気工事士の比較です。電験三種は"
     "<strong>電気設備の保安・監督</strong>、電気工事士は"
     "<strong>電気工事の施工</strong>と役割が異なります。"
     "電験三種の方が難易度は高めで、設備管理・ビルメンテで重宝されます。"),
    ("toeic-eiken", "c-3322", "c-3308",
     "TOEICと実用英語技能検定（英検）の比較です。TOEICは"
     "<strong>ビジネス英語のスコア</strong>で就職・昇進の指標に、"
     "英検は<strong>4技能の級認定</strong>で進学・教育分野に強いのが特徴です。"
     "用途に合わせて使い分けましょう。"),
    ("kangoshi-junkangoshi", "c-1803", "c-1804",
     "看護師と准看護師の比較です。看護師は<strong>国家資格</strong>、"
     "准看護師は<strong>都道府県知事免許</strong>で、養成期間や業務上の位置づけが"
     "異なります。准看護師から看護師を目指すルートもあります。"),
    ("biyoshi-riyoshi", "c-4303", "c-4301",
     "美容師と理容師の比較です。理容師は<strong>カット・顔そり（シェービング）</strong>、"
     "美容師は<strong>パーマ・カラー・セット</strong>を中心に扱います。"
     "どちらも養成施設での課程修了と国家試験合格が必要です。"),
    ("ri1gaku-sagyo", "c-1904", "c-1905",
     "理学療法士（PT）と作業療法士（OT）の比較です。理学療法士は"
     "<strong>立つ・歩くなどの基本動作の回復</strong>を、作業療法士は"
     "<strong>食事・着替えや手の作業、精神面まで含めた応用動作</strong>を支援します。"
     "対象や活躍の場が一部異なります。"),
    ("shakaifukushi-kaigofukushi", "c-2301", "c-2302",
     "社会福祉士と介護福祉士の比較です。社会福祉士は"
     "<strong>相談援助（ソーシャルワーク）</strong>の専門職、介護福祉士は"
     "<strong>現場の介護（ケアワーク）</strong>の専門職です。"
     "相談業務か直接ケアか、目指す役割で選びます。"),
    ("hoikushi-yochien", "c-2303", "c-2601",
     "保育士と幼稚園教諭の比較です。保育士は<strong>0歳〜就学前の保育</strong>"
     "（児童福祉施設など）、幼稚園教諭は<strong>3歳〜就学前の教育</strong>を担います。"
     "認定こども園では両方の資格（保育教諭）が求められる傾向です。"),
    ("kikenbutsu-ko-otsu", "c-5206", "c-5207",
     "危険物取扱者の甲種と乙種の比較です。乙種は<strong>指定の類のみ</strong>"
     "（乙4＝ガソリン等が人気）、甲種は<strong>全種類の危険物</strong>を扱え、"
     "受験には一定の要件があります。まず乙4から取得するのが定番です。"),
    ("eisei-1shu-2shu", "c-2202", "c-2203",
     "衛生管理者の第一種と第二種の比較です。第一種は<strong>全業種</strong>"
     "（製造業・建設業など有害業務を含む）、第二種は<strong>有害業務の少ない"
     "業種に限定</strong>されます。製造業などを想定するなら第一種が必要です。"),
    ("kenchiku-sekan-1-2", "c-1315", "c-1316",
     "建築施工管理技士の1級と2級の比較です。1級は<strong>大規模工事の"
     "監理技術者</strong>になれ、2級は<strong>中小規模の主任技術者</strong>が"
     "対象です。担当できる現場の規模と将来性で1級が有利です。"),
    ("doboku-sekan-1-2", "c-1404", "c-1405",
     "土木施工管理技士の1級と2級の比較です。1級は<strong>大規模な"
     "土木工事の監理技術者</strong>、2級は<strong>中小規模の主任技術者</strong>"
     "に対応します。公共工事の評価でも1級が高く扱われます。"),
    ("shindanshi-gyoseishoshi", "c-2511", "c-3701",
     "中小企業診断士と行政書士の比較です。診断士は<strong>経営コンサルティング</strong>"
     "（名称独占）、行政書士は<strong>官公庁への許認可・書類作成</strong>（独占業務）"
     "が中心です。コンサル志向か、書類・許認可業務かで選びます。"),
    ("denken3-enekan", "c-1205", "c-1603",
     "第三種電気主任技術者（電験三種）とエネルギー管理士の比較です。電験三種は"
     "<strong>電気設備の保安・監督</strong>、エネルギー管理士は"
     "<strong>工場などの省エネ・エネルギー使用の合理化</strong>が役割です。"
     "設備管理ではどちらも重宝され、両方持つ人もいます。"),
    ("boki1-zeirishi", "c-3623", "c-2503",
     "日商簿記1級と税理士の比較です。簿記1級は<strong>高度な会計知識の証明</strong>"
     "（税理士試験の受験資格にもなる）、税理士は<strong>税務の独占業務を持つ国家資格</strong>"
     "です。経理のステップアップか、独立できる士業かで方向性が分かれます。"),
    ("itpassport-mos", "c-1538", "c-3816",
     "ITパスポートとMOS（Excel等）の比較です。ITパスポートは"
     "<strong>IT全般の基礎知識</strong>を証明する国家試験、MOSは"
     "<strong>Office製品の操作スキル</strong>を証明する民間資格です。"
     "知識の証明か、実務操作スキルかで使い分けます。"),
    ("anma-judo", "c-2101", "c-2104",
     "あん摩マッサージ指圧師と柔道整復師の比較です。あん摩マッサージ指圧師は"
     "<strong>手技による施術</strong>、柔道整復師は<strong>骨折・脱臼・打撲・"
     "捻挫などへの施術（接骨院）</strong>を行います。いずれも養成課程と国家試験が必要です。"),
    ("kanrigyomu-takken", "c-3210", "c-3207",
     "管理業務主任者と宅地建物取引士の比較です。管理業務主任者は"
     "<strong>マンション管理会社で必置</strong>、宅建士は"
     "<strong>不動産取引（売買・仲介）で必置</strong>です。"
     "試験範囲に重なりがあり、ダブル取得を狙う人もいます。"),
    ("takken-fp2", "c-3207", "c-2516",
     "就職・転職で人気の宅地建物取引士とFP2級の比較です。宅建は"
     "<strong>不動産取引</strong>に必須で求人が多く、FP2級は"
     "<strong>金融・保険・不動産・税の幅広いお金の知識</strong>が強みです。"
     "不動産業界なら宅建、金融・相談業務ならFPが目安です。"),
    ("takken-boki2", "c-3207", "c-3624",
     "人気資格の宅地建物取引士と簿記2級の比較です。宅建は"
     "<strong>不動産分野の必置資格</strong>、簿記2級は"
     "<strong>経理・会計の実務スキル</strong>です。"
     "目指す業界（不動産か経理・事務か）で選ぶのがおすすめです。"),
    ("denko2-kikenbutsu", "c-6809", "c-5207",
     "設備・ビルメンテ系で人気の第二種電気工事士と危険物取扱者（乙種）の比較です。"
     "電気工事士は<strong>電気設備の工事</strong>、危険物は"
     "<strong>ガソリンなど危険物の取扱い</strong>が対象です。"
     "ビル管理では両方を揃えると業務の幅が広がります。"),
    ("denko-denken3", "c-6809", "c-1205",
     "第二種電気工事士と第三種電気主任技術者（電験三種）の比較です。電気工事士は"
     "<strong>電気工事の施工</strong>、電験三種は<strong>電気設備の保安・監督</strong>"
     "が役割で、電験三種の方が難易度は高めです。工事から保安へとステップアップする人もいます。"),
    ("sokuryoshi-chosashi", "c-1408", "c-3203",
     "測量士と土地家屋調査士の比較です。測量士は<strong>各種測量の計画・実施</strong>、"
     "土地家屋調査士は<strong>不動産の表示登記に関する調査・測量と申請代理</strong>"
     "が独占業務です。調査士は独立開業、測量士は測量会社での活躍が中心です。"),
    ("shihoshoshi-chosashi", "c-2402", "c-3203",
     "司法書士と土地家屋調査士の比較です。どちらも不動産登記に関わりますが、"
     "司法書士は<strong>権利に関する登記（所有権・抵当権など）</strong>、"
     "土地家屋調査士は<strong>表示に関する登記（土地・建物の形状や面積）</strong>"
     "を扱います。両方取得して連携する人もいます。"),
    ("shika-eisei-gikou", "c-1907", "c-1906",
     "歯科衛生士と歯科技工士の比較です。歯科衛生士は<strong>予防処置・診療補助・"
     "保健指導</strong>で患者と接し、歯科技工士は<strong>入れ歯・被せ物などの製作</strong>"
     "を行います。人と接する仕事かものづくりかで方向性が分かれます。"),
    ("rinsho-hoshasen", "c-1901", "c-1908",
     "臨床検査技師と診療放射線技師の比較です。臨床検査技師は<strong>血液・尿などの"
     "検体検査や生理機能検査</strong>、診療放射線技師は<strong>X線・CT・MRIなどの"
     "画像検査</strong>を担当します。扱う検査領域が異なります。"),
    ("chorishi-seika", "c-4401", "c-6004",
     "調理師と製菓衛生師の比較です。調理師は<strong>飲食店・給食などの料理全般</strong>、"
     "製菓衛生師は<strong>洋菓子・和菓子・パンの製造（製菓・製パン）</strong>の専門資格です。"
     "料理人かパティシエ・製菓職人かで選びます。"),
    ("shisho-gakugeiin", "c-2701", "c-2703",
     "司書と学芸員の比較です。司書は<strong>図書館</strong>で資料の収集・整理・"
     "提供を、学芸員は<strong>博物館・美術館</strong>で資料の収集・保存・展示・研究を"
     "担います。働く施設と扱う対象が異なります。"),
    ("nesupe-sc", "c-1502", "c-1565",
     "ネットワークスペシャリストと情報処理安全確保支援士（登録セキスペ）の比較です。"
     "ネスペは<strong>ネットワーク設計・構築の専門</strong>、支援士は"
     "<strong>情報セキュリティの専門（唯一の士業系IT国家資格）</strong>です。"
     "インフラ志向かセキュリティ志向かで選びます。"),
    ("kangoshi-kaigofukushi", "c-1803", "c-2302",
     "看護師と介護福祉士の比較です。看護師は<strong>医療行為・診療の補助</strong>"
     "が中心、介護福祉士は<strong>日常生活の介護・自立支援</strong>が中心です。"
     "医療寄りか生活支援寄りか、目指すケアの方向で選びます。"),
    ("career-sharoshi", "c-3112", "c-2510",
     "キャリアコンサルタントと社会保険労務士の比較です。キャリコンは"
     "<strong>個人のキャリア相談・支援</strong>、社労士は"
     "<strong>企業の労務・社会保険の手続きと相談（独占業務あり）</strong>が中心です。"
     "人材・就職支援か、労務の専門家かで方向性が分かれます。"),
    ("boiler-1-2", "c-6702", "c-6703",
     "ボイラー技士の1級と2級の比較です。2級は<strong>小規模ボイラーの取扱い</strong>"
     "から始められ、1級は<strong>より大規模なボイラーの取扱作業主任者</strong>に"
     "なれます。ビル設備管理ではまず2級から取得するのが一般的です。"),
    ("ikkyu-kenchikushi-sekan", "c-1301", "c-1315",
     "一級建築士と1級建築施工管理技士の比較です。建築士は<strong>建物の設計・"
     "工事監理</strong>、施工管理技士は<strong>工事現場の施工管理（工程・品質・安全）</strong>"
     "が役割です。設計側か現場の管理側かで選びます。"),
    ("boki3-fp3", "c-3625", "c-2517",
     "入門人気の簿記3級とFP3級の比較です。簿記3級は<strong>経理・会計の基礎</strong>、"
     "FP3級は<strong>家計・お金の基礎知識</strong>が身につきます。"
     "経理・事務を目指すなら簿記、保険・金融や生活のお金ならFPが入口です。"),
]

# slug → [(pair_slug, 相手slug)]（詳細ページから比較ページへの相互リンク用）
COMPARE_INDEX = {}
for _ps, _a, _b, _ in COMPARE_PAIRS:
    COMPARE_INDEX.setdefault(_a, []).append((_ps, _b))
    COMPARE_INDEX.setdefault(_b, []).append((_ps, _a))

# main() で設定（詳細→比較リンクの表示名・存在判定に使用）
NAME_BY_SLUG = {}
INDEXABLE_SLUGS = set()


def build_feature_pages(indexable):
    """特集・ランキングページ（site/feature/<slug>.html）。"""
    pub = [r for r in indexable if r["status"] == "published"]
    pages = {}

    def page(slug, title, h1, intro, items, desc, ranked=False):
        body = (
            f'<nav class="crumbs"><a href="../index.html">トップ</a> › 特集</nav>'
            f"<h1>{esc(h1)}</h1>"
            f'<p class="lead">{intro}</p>'
            + _list_items(items, depth=1, ranked=ranked)
            + '<p class="muted" style="margin-top:14px">※受験料・合格率は公式の一次情報に基づきますが、'
              '最新の金額・制度・日程は各資格の公式サイトで必ずご確認ください。</p>'
        )
        _ld = [
            {"@context": "https://schema.org", "@type": "BreadcrumbList",
             "itemListElement": [
                 {"@type": "ListItem", "position": 1, "name": "トップ",
                  "item": BASE_URL + "/"},
                 {"@type": "ListItem", "position": 2, "name": h1}]},
            {"@context": "https://schema.org", "@type": "ItemList",
             "name": h1, "numberOfItems": len(items),
             "itemListElement": [
                 {"@type": "ListItem", "position": i,
                  "url": f'{BASE_URL}/c/{r["slug"]}.html', "name": r["name"]}
                 for i, r in enumerate(items[:50], 1)
                 if is_indexable_detail(r)]},
        ]
        pages[slug] = page_shell(f"{title}｜{SITE_NAME}", body, depth=1,
                                 noindex=False, desc=desc,
                                 path=f"feature/{slug}.html", jsonld=_ld)

    # 受験者数が多い順（公式統計のある資格）
    popular = sorted((r for r in pub if applicants_num(r) is not None),
                     key=lambda r: (-applicants_num(r), r["name"]))[:120]
    if popular:
        page("popular", "受験者数が多い人気資格ランキング", "受験者数が多い人気資格ランキング",
             f"公式が公表する直近の受験者数が多い順に並べた資格ランキング（データ掲載分の"
             f"上位 {len(popular)} 件）。受験者数は実施回・年度により変動します。",
             popular, "受験者数が多い人気資格を受験者数の多い順にランキング。"
             "受験料・合格率・受験者数・公式情報を掲載。", ranked=True)

    # 受験料が安い順（代表額のあるものを昇順・上位120）
    cheap = sorted((r for r in pub if fee_yen(r) is not None),
                   key=lambda r: (fee_yen(r), r["name"]))[:120]
    page("cheap", "受験料が安い資格ランキング", "受験料が安い資格ランキング",
         f"受験料（代表額）が安い順に並べた資格ランキング。データ掲載分の上位 {len(cheap)} 件。"
         "受験料は級・方式で異なる場合があります。",
         cheap, "受験料が安い資格を安い順にランキング。受験料・合格率・公式情報を掲載。",
         ranked=True)

    # 合格率が高い順
    hi = sorted((r for r in pub if pass_pct(r) is not None),
                key=lambda r: (-pass_pct(r), r["name"]))[:120]
    page("high-pass", "合格率が高い資格", "合格率が高い資格",
         f"公表されている合格率が高い順に並べた資格一覧（上位 {len(hi)} 件）。"
         "合格率は実施回・年度により変動します。",
         hi, "合格率が高い資格を高い順に一覧。受験料・合格率・公式情報を掲載。",
         ranked=True)

    # 合格率が低い順（難関）
    lo = sorted((r for r in pub if pass_pct(r) is not None),
                key=lambda r: (pass_pct(r), r["name"]))[:120]
    page("hard", "合格率が低い難関資格", "合格率が低い難関資格",
         f"公表されている合格率が低い（難易度が高い）順に並べた資格一覧（上位 {len(lo)} 件）。",
         lo, "合格率が低い難関資格を一覧。受験料・合格率・公式情報を掲載。",
         ranked=True)

    # 在宅・CBT
    cbt = sorted((r for r in pub if is_cbt(r)),
                 key=lambda r: (r["major_category"], r["name"]))
    page("cbt", "在宅・CBTで受けられる資格", "在宅・CBT（ネット試験）で受けられる資格",
         f"CBT・ネット試験など、テストセンターや在宅で受験できる資格 {len(cbt)} 件。",
         cbt, "CBT・ネット試験で受けられる資格の一覧。受験料・試験形式・公式情報を掲載。")

    # 受験資格なし（全区分）
    noreq = sorted((r for r in pub if is_noreq(r)),
                   key=lambda r: (r["major_category"], r["name"]))
    page("no-requirement", "受験資格なしで受けられる資格", "受験資格なしで受けられる資格",
         f"学歴・実務経験を問わず誰でも受験できる資格 {len(noreq)} 件（全区分）。"
         "受験資格は出願時に必ず公式でご確認ください。",
         noreq, "学歴・実務経験を問わず誰でも受験できる資格の一覧（全区分）。")

    # 受験資格なし × 国家資格
    noreq_n = [r for r in noreq if r["type"] == "国家"]
    page("no-requirement-national", "受験資格なしで取れる国家資格",
         "受験資格なしで取れる国家資格",
         f"誰でも受験できる国家資格 {len(noreq_n)} 件。"
         "受験資格は出願時に必ず公式で確認してください。",
         noreq_n, "学歴・実務経験を問わず誰でも受験できる国家資格の一覧。")

    # 国家資格・公的資格の一覧（全件・名称リンク）
    for typ, slug, label in (("国家", "national", "国家資格"),
                             ("公的", "public", "公的資格")):
        items = sorted((r for r in indexable if r["type"] == typ),
                       key=lambda r: (r["major_category"], r["status"] != "published",
                                      r["category"], r["name"]))
        npub = sum(1 for r in items if r["status"] == "published")
        page(slug, f"{label}の一覧", f"{label}の一覧",
             f"日本の{label} {len(items)} 件（うち公式データ掲載 {npub} 件）。"
             "分野・カテゴリ別に名称から詳細（受験料・合格率・公式情報）を確認できます。",
             items, f"日本の{label}の一覧（{len(items)}件）。受験料・合格率・公式情報を掲載。")

    # データ掲載一覧
    page("data-available", "公式データ掲載資格の一覧", "公式データ掲載資格の一覧",
         f"受験料・合格率・公式情報などを公式の一次情報で整備済みの {len(pub)} 件。",
         sorted(pub, key=lambda r: (r["major_category"], r["name"])),
         f"受験料・試験形式・受験資格・合格率を整備済みの資格 {len(pub)} 件の一覧。")

    # ── 意図ベースのハブページ（検索意図に当てる集約） ──
    by_slug = {r["slug"]: r for r in indexable}

    def curated(slugs):
        out = []
        for s in slugs:
            r = by_slug.get(s)
            if r and is_indexable_detail(r) and r not in out:
                out.append(r)
        return out

    def hub_nav(current):
        lis = "".join(
            f'<li><a href="{s}.html">{esc(l)}</a></li>'
            for s, l in INTENT_HUB_NAV if s != current)
        return ('<nav class="rel-links"><h2>関連ガイド</h2><ul>' + lis + "</ul></nav>")

    def hub(slug, title, h1, intro_html, items, desc, group=False):
        if group:
            from collections import OrderedDict
            by_major = OrderedDict()
            for r in sorted(items, key=lambda r: (r["major_category"], r["name"])):
                by_major.setdefault(r["major_category"], []).append(r)
            listing = ""
            for major, its in by_major.items():
                listing += (f'<h2 class="hub-grp">{esc(major)}</h2>'
                            + _list_items(its, depth=1))
        else:
            listing = _list_items(items, depth=1)
        body = (
            f'<nav class="crumbs"><a href="../index.html">トップ</a> › ガイド</nav>'
            f"<h1>{esc(h1)}</h1>"
            f'<div class="lead">{intro_html}</div>'
            + listing
            + '<p class="muted" style="margin-top:14px">※掲載は各資格の性質に基づく編集上の選定です。'
              '個々の制度・受験料・合格率・独立開業や就職の条件は、各資格の公式サイトで'
              '必ずご確認ください。</p>'
            + hub_nav(slug)
        )
        _ld = [
            {"@context": "https://schema.org", "@type": "BreadcrumbList",
             "itemListElement": [
                 {"@type": "ListItem", "position": 1, "name": "トップ",
                  "item": BASE_URL + "/"},
                 {"@type": "ListItem", "position": 2, "name": h1}]},
            {"@context": "https://schema.org", "@type": "ItemList",
             "name": h1, "numberOfItems": len(items),
             "itemListElement": [
                 {"@type": "ListItem", "position": i,
                  "url": f'{BASE_URL}/c/{r["slug"]}.html', "name": r["name"]}
                 for i, r in enumerate(items[:50], 1)
                 if is_indexable_detail(r)]},
        ]
        pages[slug] = page_shell(f"{title}｜{SITE_NAME}", body, depth=1,
                                 noindex=False, desc=desc,
                                 path=f"feature/{slug}.html", jsonld=_ld)

    ind = curated(HUB_INDEPENDENCE)
    hub("independence", "独立・開業を目指せる資格", "独立・開業を目指せる資格",
        "<p>将来の独立や開業を視野に入れて資格を選びたい人向けのガイドです。"
        "ここでは、<strong>業務独占の士業</strong>（行政書士・社会保険労務士・税理士・"
        "司法書士など）や、<strong>施術所・店舗を構えて開業できる資格</strong>"
        "（美容師・調理師・柔道整復師・あん摩マッサージ指圧師など）を中心に取り上げます。</p>"
        "<p>独立のしやすさは、資格そのものに加えて実務経験・顧客基盤・初期投資によって"
        "大きく変わります。まずは各資格の受験資格・難易度・受験料を比較し、現実的な"
        "ロードマップを描く出発点にしてください。</p>",
        ind, "独立・開業を目指せる資格の一覧。士業や手に職系を中心に、受験資格・難易度・"
        "受験料・公式情報を比較できます。", group=True)

    job = curated(HUB_JOB)
    hub("job-hunting", "就職・転職に役立つ資格", "就職・転職に役立つ資格",
        "<p>就職・転職で評価されやすい、実務に直結する定番資格をまとめたガイドです。"
        "事務・経理（簿記）、IT（基本情報技術者・ITパスポート）、不動産（宅地建物取引士）、"
        "金融（FP）、医療・介護・販売など、<strong>求人で歓迎・必須にされやすい資格</strong>"
        "を中心に取り上げます。</p>"
        "<p>資格は「持っているだけ」より、応募職種との関連が明確なときに効きます。"
        "志望業界を決めてから、関連の深い資格を選ぶのがおすすめです。各ページの"
        "「活かせる仕事」も参考にしてください。</p>",
        job, "就職・転職に役立つ定番資格の一覧。事務・IT・不動産・金融・医療など、"
        "求人で評価されやすい資格を比較できます。", group=True)

    rem = curated(HUB_REMOTE)
    hub("remote-work", "在宅・リモートワークに活かせる資格", "在宅・リモートワークに活かせる資格",
        "<p>在宅・リモートワークやフリーランスで働く際に役立つスキル系の資格をまとめました。"
        "IT・Web（基本情報技術者・ウェブデザイン技能士）、オフィス（MOS）、会計（簿記）、"
        "金融（FP）、語学（TOEIC・日本語教育）など、<strong>パソコンとネット環境で"
        "完結しやすい仕事</strong>に結びつく資格を中心に取り上げます。</p>"
        "<p>多くがCBT・ネット試験に対応し、独学やオンライン学習でも取得を目指せます。"
        "在宅案件は実績やポートフォリオも重視されるため、資格取得と並行した実務経験の"
        "積み上げが近道です。</p>",
        rem, "在宅・リモートワークに活かせる資格の一覧。IT・Web・会計・語学など、"
        "パソコン中心の仕事に役立つ資格を比較できます。", group=True)

    trade = curated(HUB_TRADE)
    hub("skilled-trade", "手に職をつけられる資格", "手に職をつけられる資格",
        "<p>景気や年齢に左右されにくい「手に職」を身につけたい人向けの技術・技能系資格の"
        "ガイドです。電気工事士・自動車整備士・調理師・美容師・施工管理技士・登録販売者・"
        "介護福祉士など、<strong>専門スキルが現場で長く活きる資格</strong>を中心に"
        "取り上げます。</p>"
        "<p>これらは実務に直結し、慢性的な人手不足の分野も多いのが特徴です。"
        "受験資格や実務経験の要件がある資格も含まれるため、各ページで取得ルートを"
        "確認してください。</p>",
        trade, "手に職をつけられる技術・技能系資格の一覧。電気・整備・調理・美容・"
        "建設・医療など、専門スキルが長く活きる資格を比較できます。", group=True)

    wa = sorted((r for r in pub if is_working_adult(r)),
                key=lambda r: (r["major_category"], r["name"]))
    hub("working-adults", "働きながら取りやすい資格", "社会人が働きながら取りやすい資格",
        "<p>仕事を続けながら無理なく挑戦しやすい資格をまとめたガイドです。"
        "<strong>受験資格がなく</strong>（学歴・実務経験を問わない）、かつ"
        "<strong>CBT・ネット試験で受けやすい、または合格率が比較的高め（目安40%以上）</strong>"
        f"の資格 {len(wa)} 件を、公式データから自動的に抽出しています。</p>"
        "<p>通年・随時実施やネット試験対応の資格は、自分のペースで受験日を選びやすいのが"
        "利点です。合格率は受験者層によって変わるため、難易度の目安としてご覧ください。</p>",
        wa, "社会人が働きながら取りやすい資格の一覧。受験資格なし＋CBTまたは高めの合格率で"
        "抽出。受験料・合格率・公式情報を掲載。", group=True)

    itb = curated(HUB_IT_BEGINNER)
    hub("it-beginner", "未経験からITエンジニアを目指す資格", "未経験からITエンジニアを目指す資格",
        "<p>プログラミングやインフラの実務未経験から、IT業界への就職・転職を目指す人向けの"
        "資格ガイドです。<strong>ITパスポート</strong>でIT全般の基礎を押さえ、"
        "<strong>基本情報技術者</strong>で開発・アルゴリズムの土台を作り、"
        "<strong>応用情報技術者</strong>や各高度区分（ネットワーク・データベース・"
        "情報処理安全確保支援士など）で専門性を深める、という段階設計が王道です。</p>"
        "<p>資格は「採用で足切りされない・学習の指針になる」点で有効ですが、IT職は"
        "成果物やスキルそのものも重視されます。資格学習と並行して、手を動かす学習を"
        "進めるのが近道です。</p>",
        itb, "未経験からITエンジニアを目指すための資格の一覧。ITパスポート・基本情報・"
        "応用情報・高度区分まで段階的に比較できます。", group=False)

    sen = curated(HUB_SENIOR)
    hub("senior", "定年後・シニアに役立つ資格", "定年後・シニアに再就職・独立で役立つ資格",
        "<p>定年後の再就職・再雇用や、セカンドキャリアでの独立を見据えて取りたい資格を"
        "まとめたガイドです。<strong>年齢に関係なく働きやすい分野</strong>"
        "（マンション管理・ビル設備・不動産・危険物・電気工事など）や、"
        "<strong>経験を活かして独立しやすい資格</strong>（行政書士・社会保険労務士・"
        "ファイナンシャルプランナーなど）を中心に取り上げます。</p>"
        "<p>受験に年齢制限のない資格がほとんどで、これまでの職務経験と組み合わせると"
        "強みになります。需要のある分野・働き方から逆算して選ぶのがおすすめです。</p>",
        sen, "定年後・シニアの再就職や独立に役立つ資格の一覧。マンション管理・設備・"
        "不動産・士業など、経験を活かせる資格を比較できます。", group=True)

    return pages


def build_comparison_pages(indexable):
    """人気ペアの比較ページ（site/vs/<pair>.html）。「A vs B」「違い」系クエリ向け。"""
    by_slug = {r["slug"]: r for r in indexable}
    pages = {}

    def shortname(r):
        # 区分や旧称の括弧書きを落として比較表を読みやすく
        return re.sub(r"[（(].*?[）)]", "", r["name"]).strip() or r["name"]

    def cell(r, key, fallback="公式情報で確認"):
        v = r.get(key, "")
        return esc(v) if v else f'<span class="muted">{fallback}</span>'

    def diff_cell(r):
        d = difficulty(r)
        if not d:
            return '<span class="muted">―</span>'
        label, cls = d
        return f'<span class="diff-badge {cls}">{esc(label)}</span>'

    for pslug, sa, sb, intro in COMPARE_PAIRS:
        ra, rb = by_slug.get(sa), by_slug.get(sb)
        if not (ra and rb and is_indexable_detail(ra) and is_indexable_detail(rb)):
            continue
        na, nb = shortname(ra), shortname(rb)
        la = TYPE_BADGE.get(ra["type"], ("", ""))[0]
        lb = TYPE_BADGE.get(rb["type"], ("", ""))[0]

        rows_spec = [
            ("資格区分", esc(la), esc(lb)),
            ("分野", esc(ra["major_category"]), esc(rb["major_category"])),
            ("受験料", cell(ra, "fee"), cell(rb, "fee")),
            ("合格率", cell(ra, "pass_rate"), cell(rb, "pass_rate")),
            ("難易度の目安", diff_cell(ra), diff_cell(rb)),
            ("受験資格", cell(ra, "eligibility"), cell(rb, "eligibility")),
            ("試験形式", cell(ra, "exam_format"), cell(rb, "exam_format")),
            ("実施頻度", cell(ra, "frequency"), cell(rb, "frequency")),
            ("実施団体", cell(ra, "authority"), cell(rb, "authority")),
        ]
        tbody = "".join(
            f"<tr><th>{esc(k)}</th><td>{va}</td><td>{vb}</td></tr>"
            for k, va, vb in rows_spec)
        table = (f'<table class="vs-table"><thead><tr><th></th>'
                 f'<th>{esc(na)}</th><th>{esc(nb)}</th></tr></thead>'
                 f"<tbody>{tbody}</tbody></table>")

        cards = (
            '<div class="vs-cta">'
            f'<a class="btn-official" href="../c/{esc(ra["slug"])}.html">{esc(na)}の詳細</a> '
            f'<a class="btn-official" href="../c/{esc(rb["slug"])}.html">{esc(nb)}の詳細</a>'
            "</div>"
            '<div class="vs-cta">'
            f'<button type="button" class="cmp-add-btn" data-slug="{esc(ra["slug"])}" data-name="{esc(na)}">＋ {esc(na)}を比較に追加</button>'
            f'<button type="button" class="cmp-add-btn" data-slug="{esc(rb["slug"])}" data-name="{esc(nb)}">＋ {esc(nb)}を比較に追加</button>'
            "</div>")

        # 比較 FAQ（違い・難易度）
        qa = [(f"{na}と{nb}の違いは何ですか？",
               re.sub("<[^>]+>", "", intro))]
        if ra.get("pass_rate") and rb.get("pass_rate"):
            qa.append((f"{na}と{nb}はどちらが難しいですか？",
                       f"公表合格率は{na}が{ra['pass_rate']}、{nb}が{rb['pass_rate']}です。"
                       "合格率は受験者層により変わるため難易度の目安としてご覧ください。"))
        faq = {"@context": "https://schema.org", "@type": "FAQPage",
               "mainEntity": [{"@type": "Question", "name": q,
                               "acceptedAnswer": {"@type": "Answer", "text": a}}
                              for q, a in qa]}
        breadcrumb = {
            "@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "トップ",
                 "item": BASE_URL + "/"},
                {"@type": "ListItem", "position": 2, "name": "比較",
                 "item": BASE_URL + "/compare.html"},
                {"@type": "ListItem", "position": 3, "name": f"{na}と{nb}"},
            ]}

        h1 = f"{na}と{nb}の違い・比較"
        body = (
            f'<nav class="crumbs"><a href="../index.html">トップ</a> › 比較</nav>'
            f"<h1>{esc(h1)}</h1>"
            f'<div class="lead"><p>{intro}</p></div>'
            f"{table}{cards}"
            '<p class="muted" style="margin-top:14px">※受験料・合格率・受験資格は公式の'
            '一次情報に基づきますが、最新の制度・金額・日程は各資格の公式サイトで必ず'
            'ご確認ください。難易度は公表合格率に基づく簡易目安です。</p>'
            '<nav class="rel-links"><h2>関連リンク</h2><ul>'
            f'<li><a href="../c/{esc(ra["slug"])}.html">{esc(na)}の詳細</a></li>'
            f'<li><a href="../c/{esc(rb["slug"])}.html">{esc(nb)}の詳細</a></li>'
            '<li><a href="../compare.html">資格を自分で比較する（最大4件）</a></li>'
            "</ul></nav>")
        desc = (f"{na}と{nb}の違いを比較。受験料・合格率・難易度の目安・受験資格・"
                f"試験形式を一覧で比べ、どちらを取るべきか選ぶ参考にできます。")
        pages[pslug] = page_shell(
            f"{na}と{nb}の違い・比較｜どっちを取る？｜{SITE_NAME}", body, depth=1,
            noindex=False, desc=desc, path=f"vs/{pslug}.html",
            jsonld=[breadcrumb, faq])
    return pages


def _occ_short(name):
    return re.sub(r"[（(].*?[）)]", "", name).strip() or name


def occ_is_indexable(occ_id, shown_count):
    """職種ページをSEOインデックス対象にするか（インデックス衛生）。
    逆引きで十分な内部リンク（2資格以上）があるか、独自解説があるpage のみインデックス。"""
    return shown_count >= 2 or bool(OCC_DESC.get(occ_id))


def related_occupations(occ_id):
    """同じ資格に共起する職種を関連度（共起資格数）順に最大8件返す。"""
    from collections import Counter
    c = Counter()
    for s in OCC_CERTS.get(occ_id, []):
        for oid in SLUG_OCC_IDS.get(s, ()):
            if oid != occ_id:
                c[oid] += 1
    # 同点時は occ_id を最終キーにして決定的に（set反復順に依存させない）
    ranked = sorted(c.items(),
                    key=lambda kv: (-kv[1], -OCC.get(kv[0], {}).get("cert_count", 0), kv[0]))
    return [(oid, n) for oid, n in ranked[:8]]


def build_occupation_pages(indexable):
    """職種ページ（site/shoku/<occ_id>.html）と職種インデックスを生成する。

    各ページの主役は「この職種に活かせる資格」の逆引き一覧。資格→職種の自由記述
    （careers）を正規化した occupations / cert_occupations をデータ源とする。
    """
    by_slug = {r["slug"]: r for r in indexable}
    pages = {}
    index_items = []  # (occ_id, name, major, shown) — インデックス対象のみ

    for occ_id, info in OCC.items():
        name = info["name"]
        major = info["major_category"]
        certs = [by_slug[s] for s in OCC_CERTS.get(occ_id, []) if s in by_slug]
        certs.sort(key=lambda r: (r["status"] != "published", r["major_category"], r["name"]))
        shown = len(certs)

        dinfo = OCC_DESC.get(occ_id) or {}
        desc_txt = dinfo.get("summary", "")
        if desc_txt:
            lead = esc(desc_txt)
        else:
            lead = (f"{esc(name)}は、関連資格の取得が役立つ職種です。"
                    f"このページでは{esc(name)}に活かせる資格を{shown}件まとめ、"
                    "各資格の受験料・合格率・受験資格・公式情報を確認できます。")

        # 仕事内容・活かせるスキル（あれば。事実ベースの編集コンテンツ）
        work_html = ""
        if dinfo.get("work"):
            work_html = ('<section class="occ-work"><h2>仕事内容</h2>'
                         f'<p>{esc(dinfo["work"])}</p></section>')
        if dinfo.get("skills"):
            chips = "".join(
                f'<span class="tag-chip">{esc(s.strip())}</span>'
                for s in dinfo["skills"].split("、") if s.strip())
            work_html += ('<section class="occ-work"><h2>活かせるスキル・知識</h2>'
                          f'<p class="occ-skills">{chips}</p></section>')
        sal = OCC_SALARY.get(occ_id)
        if sal:
            work_html += (
                '<section class="occ-salary"><h2>想定年収（目安）</h2>'
                f'<p class="salary-range">{esc(sal)} <span class="muted">／目安</span></p>'
                '<p class="muted occ-salary-note">※年収は地域・経験・雇用形態・勤務先により'
                '大きく異なります。公開の賃金統計・求人情報を参考にした<strong>目安</strong>で、'
                '公式の統計値ではありません。公的な賃金データは'
                f'<a href="{JOBTAG_URL}" rel="nofollow noopener" target="_blank">'
                '厚生労働省 job tag</a> 等でご確認ください。</p></section>')

        listing = (_list_items(certs, depth=1) if certs
                   else '<p class="muted">この職種に直接ひも付く掲載資格は精査中です。</p>')

        # 資格区分の内訳（国家/公的/民間/要確認）＋関連分野チップ（既存データから機械生成）
        from collections import Counter
        type_cnt = Counter(r["type"] for r in certs)
        stat_html = ""
        if certs:
            parts = [f'<span class="occ-stat">{esc(t)} {type_cnt[t]}</span>'
                     for t in ("国家", "公的", "民間", "要確認") if type_cnt.get(t)]
            major_cnt = Counter(r["major_category"] for r in certs)
            chips = "".join(
                f'<a class="chip" href="../bunya/{MAJOR_SLUGS.get(m, "other")}.html">'
                f'{esc(m)}<span class="muted"> {n}</span></a>'
                for m, n in major_cnt.most_common(6))
            stat_html = (
                '<div class="occ-meta">'
                f'<p class="occ-stats"><span class="occ-stats-label">資格区分の内訳：</span>'
                f'{"".join(parts)}</p>'
                f'<div class="occ-fields"><span class="occ-stats-label">関連する分野：</span>'
                f'<span class="chips">{chips}</span></div></div>')

        # 逆引き資格の ItemList 構造化データ
        itemlist = None
        if certs:
            itemlist = {
                "@context": "https://schema.org", "@type": "ItemList",
                "name": f"{name}に活かせる資格",
                "numberOfItems": len(certs),
                "itemListElement": [
                    {"@type": "ListItem", "position": i + 1, "name": r["name"],
                     "url": f'{BASE_URL}/c/{r["slug"]}.html'}
                    for i, r in enumerate(certs)],
            }

        # 関連職種（共起）
        rels = related_occupations(occ_id)
        rel_html = ""
        if rels:
            lis = "".join(
                f'<li><a href="{oid}.html">{esc(_occ_short(OCC[oid]["name"]))}</a>'
                f' <span class="muted">（{OCC[oid]["cert_count"]}資格）</span></li>'
                for oid, _ in rels if oid in OCC)
            rel_html = ('<nav class="rel-links"><h2>関連する職種</h2>'
                        '<p class="muted">同じ資格から目指せる近い職種です。</p>'
                        f'<ul>{lis}</ul></nav>')

        # 分野一覧・職種トップへの導線
        bslug = MAJOR_SLUGS.get(major, "other")
        nav_links = ['<li><a href="index.html">職種の一覧から探す</a></li>']
        if major:
            nav_links.append(f'<li><a href="../bunya/{bslug}.html">{esc(major)}の資格一覧</a></li>')
        nav_links.append(f'<li><a href="{JOBTAG_URL}" rel="nofollow noopener" target="_blank">'
                         '厚生労働省 job tag でこの職業を調べる ↗</a></li>')
        more_nav = ('<nav class="rel-links"><h2>関連リンク</h2><ul>'
                    + "".join(nav_links) + "</ul></nav>")

        body = (
            f'<nav class="crumbs"><a href="../index.html">トップ</a> › '
            f'<a href="index.html">職種から探す</a> › {esc(name)}</nav>'
            f"<h1>{esc(name)}に活かせる資格</h1>"
            f'<p class="lead">{lead}</p>'
            f"{work_html}{stat_html}"
            f'<section class="careers-sec"><h2>この職種に活かせる資格（{shown}件）</h2>'
            f"{listing}</section>"
            f"{rel_html}{more_nav}"
            '<p class="muted" style="margin-top:14px">※「活かせる資格」は厚生労働省の職業情報'
            '提供サイト（job tag）等を出所に各資格の関連職業を整理したものです。資格が必須・'
            '推奨かは職種・求人により異なります。詳細は各資格・求人の公式情報でご確認ください。</p>'
        )
        noindex = not occ_is_indexable(occ_id, shown)
        if desc_txt:
            desc = desc_txt[:118]
        else:
            desc = (f"{name}に活かせる資格を{shown}件まとめました。"
                    f"{name}を目指すうえで役立つ資格の受験料・合格率・受験資格・公式情報を一覧で確認できます。")
        breadcrumb = {
            "@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "トップ", "item": BASE_URL + "/"},
                {"@type": "ListItem", "position": 2, "name": "職種から探す",
                 "item": f"{BASE_URL}/shoku/index.html"},
                {"@type": "ListItem", "position": 3, "name": name},
            ]}
        # schema.org/Occupation 構造化データ（保有データを活用）
        occ_ld = {"@context": "https://schema.org", "@type": "Occupation",
                  "name": name, "url": f"{BASE_URL}/shoku/{occ_id}.html"}
        if major:
            occ_ld["occupationalCategory"] = major
        if desc_txt:
            occ_ld["description"] = desc_txt
        if dinfo.get("work"):
            occ_ld["responsibilities"] = dinfo["work"]
        if dinfo.get("skills"):
            occ_ld["skills"] = dinfo["skills"]
        qv = _salary_quantitative(OCC_SALARY.get(occ_id, ""))
        if qv:
            occ_ld["estimatedSalary"] = {"@type": "MonetaryAmount",
                                         "currency": "JPY", "value": qv}
        ld = [breadcrumb, occ_ld] + ([itemlist] if itemlist else [])
        pages[occ_id] = page_shell(f"{name}に活かせる資格｜{SITE_NAME}", body, depth=1,
                                   noindex=noindex, desc=desc,
                                   path=f"shoku/{occ_id}.html", jsonld=ld)
        if not noindex:
            index_items.append((occ_id, name, major, shown))

    # 職種インデックス（site/shoku/index.html）— 分野別に逆引きの太い職種から
    from collections import OrderedDict
    index_items.sort(key=lambda t: (t[2], -t[3], t[1]))
    by_major = OrderedDict()
    for occ_id, name, major, shown in index_items:
        by_major.setdefault(major or "その他", []).append((occ_id, name, shown))
    blocks = ""
    for major, lst in by_major.items():
        lis = "".join(
            f'<li><a href="{oid}.html">{esc(_occ_short(nm))}</a>'
            f' <span class="muted">（{sh}資格）</span></li>'
            for oid, nm, sh in lst)
        blocks += f'<h2 class="hub-grp">{esc(major)}</h2><ul class="results occ-list">{lis}</ul>'
    total_occ = len(OCC)
    idx_body = (
        f'<nav class="crumbs"><a href="../index.html">トップ</a> › 職種から探す</nav>'
        f"<h1>職種から資格を探す</h1>"
        f'<p class="lead">資格を取得して目指せる職種から、その職種に<strong>活かせる資格を逆引き</strong>'
        f'できます。資格ごとの「活かせる仕事」を正規化した職種データベース（全{total_occ}職種）。'
        f'検索・分野で絞り込めます（下の一覧は関連資格が複数ある{len(index_items)}職種）。</p>'
        '<div class="controls">'
        '<input id="occ-q" type="search" placeholder="職種名で検索（例: エンジニア, 整備, 事務）">'
        '<select id="occ-major"><option value="">分野（すべて）</option></select>'
        '</div>'
        '<p id="occ-status" class="muted"></p>'
        '<ul id="occ-results" class="results occ-list" hidden></ul>'
        f'<div id="occ-static">{blocks}</div>'
        '<p class="muted" style="margin-top:14px">※職種データは厚生労働省の職業情報提供サイト'
        '（job tag）等を出所に各資格の関連職業を整理・正規化したものです。'
        '検索は全職種が対象です（関連資格1件のみの職種も含みます）。</p>'
        '<script src="../assets/occ-search.js"></script>'
    )
    index_html = page_shell(f"職種から資格を探す｜{SITE_NAME}", idx_body, depth=1,
                            noindex=False,
                            desc="資格を取得して目指せる職種から、その職種に活かせる資格を逆引きできます。"
                                 "分野別に職種を一覧。",
                            path="shoku/index.html")
    return pages, index_html, index_items


def build_index(rows) -> str:
    pub = sum(1 for r in rows if r.get("status") == "published")
    majors = sorted({r["major_category"] for r in rows})
    cat_links = " ".join(
        f'<a class="chip" href="bunya/{MAJOR_SLUGS.get(m, "other")}.html">{esc(m)}</a>'
        for m in majors)
    feat_links = "".join(
        f'<li><a href="feature/{slug}.html">{esc(label)}</a></li>'
        for slug, label in FEATURE_NAV
        if slug != "popular" or any(applicants_num(r) is not None for r in rows))
    by_slug = {r["slug"]: r for r in rows}

    def _short(r):
        return re.sub(r"[（(].*?[）)]", "", r["name"]).strip() or r["name"]
    vs_links = ""
    for pslug, sa, sb, _ in COMPARE_PAIRS:
        ra, rb = by_slug.get(sa), by_slug.get(sb)
        if ra and rb and is_indexable_detail(ra) and is_indexable_detail(rb):
            vs_links += (f'<li><a href="vs/{pslug}.html">'
                         f'{esc(_short(ra))} と {esc(_short(rb))} の違い</a></li>')
    # --- 人気の資格（受験者数の多い順 上位8） ---
    ranked = sorted((r for r in rows
                     if applicants_num(r) is not None and is_indexable_detail(r)),
                    key=lambda r: -(applicants_num(r) or 0))
    pop = ranked[:8]
    pop_html = ""
    for i, r in enumerate(pop):
        more = " pop-card--more" if i >= 4 else ""
        facts = f'<li><span class="k">区分</span><span class="v">{esc(r["type"])}</span></li>'
        d = difficulty(r)
        if d:
            facts += f'<li><span class="k">難易度</span><span class="v">{esc(d[0])}</span></li>'
        sh = (STUDY.get(r["slug"], {}) or {}).get("study_hours", "")
        if sh:
            facts += f'<li><span class="k">学習目安</span><span class="v">{esc(sh)}</span></li>'
        pop_html += (f'<a class="pop-card card-link{more}" href="c/{r["slug"]}.html">'
                     f'<div class="pop-card-name">{esc(_short(r))}</div>'
                     f'<p class="pop-card-audience">{esc(r["major_category"])}</p>'
                     f'<ul class="pop-card-facts">{facts}</ul></a>')

    # --- 分野から探す（収録数の多い順 上位8） ---
    mcount = Counter(r["major_category"] for r in rows)
    by_major = {}
    for r in rows:
        by_major.setdefault(r["major_category"], []).append(r)

    def _examples(m):
        cs = sorted(by_major[m], key=lambda r: -(applicants_num(r) or 0))
        return "・".join(_short(r) for r in cs[:3]) + "など"
    FIELD_ICON = ('<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                  ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                  '<path d="M4 7a2 2 0 0 1 2-2h3l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/></svg>')
    fld_html = ""
    for m in sorted(mcount, key=lambda m: -mcount[m])[:8]:
        fld_html += (f'<a class="field-card" href="bunya/{MAJOR_SLUGS.get(m, "other")}.html">'
                     f'<div class="icon">{FIELD_ICON}</div>'
                     f'<div class="field-card-body">'
                     f'<div class="field-card-top"><h3>{esc(m)}</h3>'
                     f'<span class="field-count">{mcount[m]}件</span></div>'
                     f'<p class="field-examples">{esc(_examples(m))}</p></div></a>')

    # --- よく比較される資格（COMPARE_PAIRS 先頭6） ---
    cmp_html = ""
    _n = 0
    for pslug, sa, sb, intro in COMPARE_PAIRS:
        ra, rb = by_slug.get(sa), by_slug.get(sb)
        if not (ra and rb and is_indexable_detail(ra) and is_indexable_detail(rb)):
            continue
        tip = re.sub(r"<[^>]+>", "", intro or "")
        if len(tip) > 48:
            tip = tip[:47] + "…"
        cmp_html += (f'<a class="compare-card" href="vs/{pslug}.html">'
                     f'<span class="compare-tag">{esc(ra["major_category"])}</span>'
                     f'<div class="compare-names">{esc(_short(ra))} <em>vs</em> {esc(_short(rb))}</div>'
                     f'<p class="compare-tip">{esc(tip)}</p>'
                     f'<span class="compare-go">比較する →</span></a>')
        _n += 1
        if _n >= 6:
            break

    # --- 目的から探す（3カード・具体導線つき。意図ハブ＋特集＋条件フィルタへ直接リンク） ---
    PURPOSE = [
        ("就職", "新卒・就活・はじめて資格を選ぶ方", [
            ("就職・転職に役立つ資格", "feature/job-hunting.html"),
            ("受験資格なしで受けられる資格", "feature/no-requirement.html"),
            ("受験者数が多い人気資格", "feature/popular.html"),
            ("未経験からITを目指す", "feature/it-beginner.html"),
            ("「就職・転職」向けで絞り込む →", "index.html?tag=" + quote("就職・転職") + "#all"),
        ]),
        ("転職", "働きながら職種・キャリアを変えたい方", [
            ("働きながら取りやすい資格", "feature/working-adults.html"),
            ("在宅・リモートワークに活かせる", "feature/remote-work.html"),
            ("独立・開業を目指せる資格", "feature/independence.html"),
            ("国家資格の一覧", "feature/national.html"),
            ("「働きながら」で絞り込む →", "index.html?tag=" + quote("働きながら") + "#all"),
        ]),
        ("スキルアップ", "今の仕事に活かす・手に職をつけたい方", [
            ("手に職をつけられる資格", "feature/skilled-trade.html"),
            ("未経験からITエンジニアを目指す", "feature/it-beginner.html"),
            ("定年後・シニアに役立つ資格", "feature/senior.html"),
            ("合格率が高い資格", "feature/high-pass.html"),
            ("「手に職」で絞り込む →", "index.html?tag=" + quote("手に職") + "#all"),
        ]),
    ]
    PURPOSE_ICONS = [
        '<path d="M12 3L2 8l10 5 10-5-10-5z"/><path d="M5 11v5c0 2.5 3.5 5 7 5s7-2.5 7-5v-5"/><path d="M22 8v6"/>',
        '<path d="M4 9h12l-3-3"/><path d="M20 9V5"/><path d="M20 15H8l3 3"/><path d="M4 15v4"/>',
        '<path d="M4 18h16"/><path d="M7 15l4-6 3 3 5-7"/>',
    ]
    pur_html = ""
    for (title, forwhom, links), icon in zip(PURPOSE, PURPOSE_ICONS):
        lis = "".join(f'<li><a href="{esc(href)}">{esc(label)}</a></li>'
                      for label, href in links)
        pur_html += (
            f'<div class="purpose-card">'
            f'<div class="purpose-card-head">'
            f'<div class="icon"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
            f' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{icon}</svg></div>'
            f'<div><h3>{esc(title)}</h3><p class="purpose-card-for">{esc(forwhom)}</p></div></div>'
            f'<ul class="purpose-card-links">{lis}</ul></div>')

    body = f"""<section class="hero">
  <h1><span class="hero-h1-line">就職・転職・スキルアップの</span><span class="hero-h1-line">資格情報サイト</span></h1>
  <p class="hero-sub">日本国内の資格を <strong id="count">{len(rows)}</strong> 件以上掲載。受験料・受験資格・試験形式・合格率・公式サイトを、公式の一次情報に基づいて整理しています。</p>
  <div class="hero-search">
    <span class="ico"><svg class="ico-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L21 21"/></svg></span>
    <input id="q" type="search" placeholder="資格名で検索（例: 簿記, 宅建, ITパスポート）" aria-label="資格名で検索">
  </div>
  <p class="hero-hint">または <a href="#purpose">目的から探す</a>・<a href="#fields">分野から探す</a></p>
  <p class="hero-result" id="heroResult" hidden></p>
</section>

<section class="block block-secondary" id="recentBlock" hidden>
  <div class="block-head"><h2>最近見た資格</h2><p>このブラウザの閲覧履歴</p></div>
  <div class="popular-grid" id="recentGrid"></div>
</section>

<section class="block block-primary" id="purpose">
  <div class="block-head"><h2>目的から探す</h2><p>就職・転職・スキルアップ — やりたいことから具体的に絞り込めます</p></div>
  <div class="purpose-grid">{pur_html}</div>
</section>

<section class="block block-primary">
  <div class="block-head"><h2>人気の資格</h2><p>受験者数の多い順</p></div>
  <div class="popular-grid">{pop_html}</div>
  <p class="popular-more"><a href="feature/popular.html">人気資格をすべて見る →</a></p>
</section>

<section class="block block-secondary" id="fields">
  <div class="block-head"><h2>分野から探す</h2></div>
  <div class="field-grid">{fld_html}</div>
  <p class="field-more"><a href="#all">すべての分野・条件で絞り込む →</a></p>
</section>

<section class="block block-secondary block-compare" id="compare">
  <div class="block-head"><h2>よく比較される資格</h2><p>2つ以上を並べて違いを確認</p></div>
  <div class="compare-grid">{cmp_html}</div>
</section>

<section class="block block-primary" id="all">
  <div class="block-head"><h2>すべての資格から探す</h2><p>分野・区分・条件で絞り込み</p></div>
  <div class="controls">
    <label class="ctl"><span class="ctl-l">分野</span><select id="major" aria-label="分野で絞り込み"><option value="">すべて</option></select></label>
    <label class="ctl"><span class="ctl-l">区分</span><select id="type" aria-label="区分で絞り込み"><option value="">すべて</option></select></label>
    <label class="ctl"><span class="ctl-l">活かせる業界</span><select id="industry" aria-label="活かせる業界で絞り込み"><option value="">すべて</option></select></label>
    <label class="ctl"><span class="ctl-l">学習時間の目安</span><select id="study" aria-label="学習時間の目安で絞り込み">
      <option value="">すべて</option>
      <option value="0-50">〜50時間</option>
      <option value="50-100">50〜100時間</option>
      <option value="100-300">100〜300時間</option>
      <option value="300-1000">300〜1000時間</option>
      <option value="1000-">1000時間以上</option>
    </select></label>
    <label class="ctl"><span class="ctl-l">並び順</span><select id="sort" aria-label="並び順">
      <option value="">標準（人気を上位）</option>
      <option value="fee-asc">受験料が安い順</option>
      <option value="fee-desc">受験料が高い順</option>
      <option value="pass-desc">合格率が高い順</option>
      <option value="pass-asc">合格率が低い順</option>
      <option value="app-desc">受験者数が多い順（人気）</option>
    </select></label>
  </div>
  <div class="filters">
    <label><input type="checkbox" id="f-pub"> データ掲載のみ</label>
    <span class="muted" id="studynote" style="display:none">学習時間は編集部調べの目安（非公式）</span>
  </div>
  <div id="tagfilter" class="tagfilter"><span class="tf-label">目的・特徴で絞り込み：</span></div>
  <div class="results-bar"><p id="status" class="muted"></p><button type="button" id="clearFilters" class="clear-filters" hidden>× 条件をクリア</button></div>
  <p class="muted hint">各行の「＋比較」で資格を選ぶと、画面下の比較バーから最大4件まで並べて比較できます。</p>
  <ul id="results" class="results"><li class="muted">読み込み中…</li></ul>
</section>

<section class="block block-secondary" id="partners">
  <div class="block-head"><h2>おすすめの資格対策サイト</h2><p>当サイト運営者が制作している資格別の学習・対策サイト</p></div>
  <div class="partner-grid">{partner_cards_html()}</div>
</section>

<section class="feature-nav">
  <div class="block-head"><h2>サイトの索引</h2><p>特集・職種・全分野の一覧</p></div>
  <h3>特集・ランキングから探す</h3>
  <ul class="feat-list">{feat_links}</ul>
  <h3>職種から探す</h3>
  <ul class="feat-list"><li><a href="shoku/index.html">職種から資格を逆引きする（活かせる仕事から探す）</a></li></ul>
  <h3>すべての分野</h3>
  <div class="chips">{cat_links}</div>
</section>
<script src="assets/search.js"></script>
"""
    site_ld = [
        {"@context": "https://schema.org", "@type": "WebSite",
         "name": SITE_NAME, "url": BASE_URL + "/",
         "potentialAction": {"@type": "SearchAction",
                             "target": {"@type": "EntryPoint",
                                        "urlTemplate": BASE_URL + "/?q={search_term_string}"},
                             "query-input": "required name=search_term_string"}},
        {"@context": "https://schema.org", "@type": "Organization",
         "name": SITE_NAME, "url": BASE_URL + "/",
         "logo": BASE_URL + "/assets/favicon.svg",
         "image": BASE_URL + "/assets/og.png",
         "description": "日本国内の資格を、各資格の公式の一次情報に基づいて整理・"
                        "掲載する資格情報サイト。受験料・受験資格・試験形式・合格率・"
                        "実施団体・公式サイトを横断的に検索・比較できます。"},
    ]
    return page_shell(
        f"{SITE_NAME}｜就職・転職・スキルアップの資格を検索・比較（{len(rows)}件以上）",
        body, depth=0, noindex=False,
        desc=SITE_DESC, path="", jsonld=site_ld)


def build_compare() -> str:
    body = """<nav class="crumbs"><a href="index.html">トップ</a> › 比較</nav>
<h1>資格を比較</h1>
<p class="lead">選択した資格を並べて比較します（最大4件）。数値・制度は各資格の公式情報で必ずご確認ください。</p>
<div id="cmpVerdict"></div>
<div id="cmp" class="cmp-wrap"><p class="muted">読み込み中…</p></div>
<p style="margin-top:18px"><a href="index.html">← 検索に戻って選び直す</a></p>
<script src="assets/compare.js"></script>
"""
    return page_shell(f"資格を比較｜{SITE_NAME}", body, depth=0, noindex=False,
                      desc="選んだ資格を受験料・試験形式・受験資格・合格率などで横並びに比較できます。",
                      path="compare.html")


SEARCH_JS = """(function(){
  var q=document.getElementById('q'),majorSel=document.getElementById('major'),
      typeSel=document.getElementById('type'),sortSel=document.getElementById('sort'),
      industrySel=document.getElementById('industry'),studySel=document.getElementById('study'),
      fPub=document.getElementById('f-pub'),tagFilter=document.getElementById('tagfilter'),
      studyNote=document.getElementById('studynote'),
      results=document.getElementById('results'),
      status=document.getElementById('status'),count=document.getElementById('count'),
      heroResult=document.getElementById('heroResult'),
      clearBtn=document.getElementById('clearFilters');
  var DATA=[], activeTags=new Set();
  var TAG_ORDER=['就職・転職','独立・開業','在宅ワーク','手に職','未経験からIT','定年後・シニア','受験資格なし','CBT・ネット試験','働きながら'];
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function shortName(n){return (n||'').replace(/[（(][^）)]*[）)]/g,'').trim()||n;}
  function opt(sel,v){var o=document.createElement('option');o.value=v;o.textContent=v;sel.appendChild(o);}
  function feeNum(x){var m=(x.fee||'').replace(/,/g,'').match(/([0-9]+)\s*円/);return m?parseInt(m[1],10):null;}
  function passNum(x){var m=(x.pass_rate||'').replace(/,/g,'').match(/([0-9]+(?:\.[0-9]+)?)\s*%/);return m?parseFloat(m[1]):null;}
  function studyLow(x){var m=(x.study_hours||'').replace(/,/g,'').match(/([0-9]+)/);return m?parseInt(m[1],10):null;}
  function appNum(x){var m=(x.applicants||'').replace(/,/g,'').match(/([0-9]+)\s*[人名]/);return m?parseInt(m[1],10):null;}
  function syncURL(){
    try{
      var p=new URLSearchParams();
      if(q.value.trim())p.set('q',q.value.trim());
      if(majorSel.value)p.set('major',majorSel.value);
      if(typeSel.value)p.set('type',typeSel.value);
      if(industrySel.value)p.set('industry',industrySel.value);
      if(studySel.value)p.set('study',studySel.value);
      if(sortSel.value)p.set('sort',sortSel.value);
      if(fPub.checked)p.set('pub','1');
      if(activeTags.size)p.set('tag',[].slice.call(activeTags).join(','));
      var qs=p.toString();
      history.replaceState(null,'',qs?('?'+qs):location.pathname);
    }catch(e){}
  }
  function studyHit(x,band){
    var v=studyLow(x); if(v===null)return false;
    var p=band.split('-'),lo=parseInt(p[0],10),hi=p[1]===''?Infinity:parseInt(p[1],10);
    return v>=lo&&v<hi;
  }
  function render(){
    var t=(q.value||'').trim().toLowerCase(),mj=majorSel.value,tp=typeSel.value,sk=sortSel.value,
        ind=industrySel.value,band=studySel.value;
    studyNote.style.display=band?'inline':'none';
    var out=DATA.filter(function(x){
      if(mj&&x.major!==mj)return false;
      if(tp&&x.type!==tp)return false;
      if(t&&x.name.toLowerCase().indexOf(t)<0)return false;
      if(fPub.checked&&x.status!=='published')return false;
      if(ind&&(x.industries||[]).indexOf(ind)<0)return false;
      if(band&&!studyHit(x,band))return false;
      if(activeTags.size){
        var tg=x.tags||[],ok=true;
        activeTags.forEach(function(a){if(tg.indexOf(a)<0)ok=false;});
        if(!ok)return false;
      }
      return true;
    });
    if(sk){
      var key=sk.indexOf('app')===0?appNum:(sk.indexOf('fee')===0?feeNum:passNum), asc=sk.indexOf('asc')>=0;
      out=out.slice().sort(function(a,b){
        var va=key(a),vb=key(b);
        if(va===null&&vb===null)return 0;
        if(va===null)return 1; if(vb===null)return -1;
        return asc?va-vb:vb-va;
      });
    } else {
      // 既定: 定番（受験者数の多い人気資格）を上位に。残りは元の分野順を維持。
      out=out.slice().sort(function(a,b){
        var pa=a.popular?1:0,pb=b.popular?1:0;
        if(pa!==pb)return pb-pa;
        return (appNum(b)||0)-(appNum(a)||0);
      });
    }
    status.textContent=out.length+' 件';
    var anyFilter=t||mj||tp||ind||band||activeTags.size||fPub.checked;
    if(clearBtn)clearBtn.hidden=!anyFilter;
    if(heroResult){
      if(anyFilter){
        heroResult.hidden=false;
        heroResult.innerHTML=(t?'「<strong>'+esc(t)+'</strong>」を含む資格 ':'絞り込み結果 ')+
          '<strong>'+out.length+'</strong> 件 <a href="#all">一覧へ ↓</a>';
      } else { heroResult.hidden=true; heroResult.innerHTML=''; }
    }
    results.innerHTML=out.slice(0,300).map(function(x){
      var extra=x.status==='published'?[feeNum(x)!==null?esc(x.fee):'',passNum(x)!==null?'合格率'+esc(x.pass_rate):''].filter(Boolean).join(' / '):'';
      return '<li><div class="result-main">'+
        '<a href="c/'+x.slug+'.html">'+esc(x.name)+'</a>'+(x.popular?' <span class="result-label">定番</span>':'')+
        '<span class="meta"><span class="badge b-'+x.type+'">'+x.type+'</span> '+esc(x.major)+' / '+esc(x.category)+(extra?' ・ '+extra:'')+'</span>'+
        '</div>'+
        '<button type="button" class="cmp-add-btn" data-slug="'+x.slug+'" data-name="'+esc(shortName(x.name))+'">＋ 比較</button>'+
        '</li>';
    }).join('')||'<li class="empty-state">条件に一致する資格が見つかりませんでした。<br>キーワードを短くするか、上の「× 条件をクリア」で絞り込みを解除してください。</li>';
    if(out.length>300) results.innerHTML+='<li class="muted">…他 '+(out.length-300)+' 件。さらに絞り込むと見つけやすくなります。</li>';
    if(window.CmpBar)window.CmpBar.refresh();
    syncURL();
  }
  function buildTagChips(all){
    var present={},counts={};
    all.forEach(function(x){(x.tags||[]).forEach(function(tg){present[tg]=1;counts[tg]=(counts[tg]||0)+1;});});
    TAG_ORDER.forEach(function(tg){
      if(!present[tg])return;
      var b=document.createElement('button');
      b.type='button';b.className='tf-chip';b.setAttribute('data-tag',tg);
      b.textContent=tg+'（'+counts[tg]+'）';
      b.onclick=function(){
        if(activeTags.has(tg)){activeTags.delete(tg);b.classList.remove('on');}
        else{activeTags.add(tg);b.classList.add('on');}
        render();
      };
      tagFilter.appendChild(b);
    });
  }
  fetch('data/certifications.json').then(function(r){return r.json();}).then(function(all){
    DATA=all; if(count)count.textContent=all.length;
    var majors={},types={},inds={};
    all.forEach(function(x){majors[x.major]=1;types[x.type]=1;(x.industries||[]).forEach(function(i){inds[i]=(inds[i]||0)+1;});});
    Object.keys(majors).sort().forEach(function(v){opt(majorSel,v);});
    ['国家','公的','民間','要確認'].forEach(function(v){if(types[v])opt(typeSel,v);});
    Object.keys(inds).sort(function(a,b){return inds[b]-inds[a];}).forEach(function(v){
      var o=document.createElement('option');o.value=v;o.textContent=v+'（'+inds[v]+'）';industrySel.appendChild(o);});
    buildTagChips(all);
    var p=new URLSearchParams(location.search);
    if(p.get('q'))q.value=p.get('q');
    if(p.get('major'))majorSel.value=p.get('major');
    if(p.get('type'))typeSel.value=p.get('type');
    if(p.get('industry'))industrySel.value=p.get('industry');
    if(p.get('study'))studySel.value=p.get('study');
    if(p.get('sort'))sortSel.value=p.get('sort');
    if(p.get('pub')==='1')fPub.checked=true;
    if(p.get('tag')){p.get('tag').split(',').forEach(function(tg){
      activeTags.add(tg);
      var c=tagFilter.querySelector('[data-tag="'+tg+'"]'); if(c)c.classList.add('on');});}
    render();
  });
  [q,majorSel,typeSel,sortSel,industrySel,studySel].forEach(function(el){el.addEventListener('input',render);});
  fPub.addEventListener('change',render);
  q.addEventListener('keydown',function(e){
    if(e.key==='Enter'){var a=document.getElementById('all');if(a){e.preventDefault();a.scrollIntoView();}}
  });
  if(clearBtn)clearBtn.addEventListener('click',function(){
    q.value='';majorSel.value='';typeSel.value='';industrySel.value='';studySel.value='';sortSel.value='';fPub.checked=false;
    activeTags.clear();
    Array.prototype.forEach.call(tagFilter.querySelectorAll('.tf-chip.on'),function(c){c.classList.remove('on');});
    render();
  });
  (function renderRecent(){
    try{
      var a=JSON.parse(localStorage.getItem('recent')||'[]');
      var blk=document.getElementById('recentBlock'),grid=document.getElementById('recentGrid');
      if(!blk||!grid||!a.length)return;
      grid.innerHTML=a.slice(0,8).map(function(x){
        return '<a class="pop-card card-link" href="c/'+esc(x.s)+'.html"><div class="pop-card-name">'+esc(x.n)+'</div></a>';
      }).join('');
      blk.hidden=false;
    }catch(e){}
  })();
})();
"""


COMPARE_BAR_JS = """(function(){
  var MAX=4;
  function load(){try{return JSON.parse(localStorage.getItem('cmp')||'[]');}catch(e){return [];}}
  function names(){try{return JSON.parse(localStorage.getItem('cmpNames')||'{}');}catch(e){return {};}}
  function save(a,nm){try{localStorage.setItem('cmp',JSON.stringify(a));localStorage.setItem('cmpNames',JSON.stringify(nm));}catch(e){}}
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function toggle(slug,name){
    var a=load(),nm=names(),i=a.indexOf(slug);
    if(i>=0){a.splice(i,1);delete nm[slug];}
    else{if(a.length>=MAX){alert('比較は最大'+MAX+'件までです');return;}a.push(slug);if(name)nm[slug]=name;}
    save(a,nm);refresh();
  }
  function remove(slug){var a=load(),nm=names(),i=a.indexOf(slug);if(i>=0){a.splice(i,1);delete nm[slug];save(a,nm);refresh();}}
  function clear(){save([],{});refresh();}
  function refresh(){
    var a=load(),nm=names();
    var sel={};a.forEach(function(s){sel[s]=1;});
    var btns=document.querySelectorAll('.cmp-add-btn[data-slug]');
    for(var i=0;i<btns.length;i++){
      var b=btns[i],on=!!sel[b.getAttribute('data-slug')];
      b.classList.toggle('is-active',on);
      b.textContent=on?'✓ 比較中':'＋ 比較';
      b.setAttribute('aria-pressed',on?'true':'false');
    }
    var bar=document.getElementById('cmpbar');
    if(!bar)return;
    if(!a.length){bar.className='cmpbar';bar.innerHTML='';document.body.classList.remove('cmp-open');return;}
    var base=bar.getAttribute('data-base')||'';
    var pills=a.map(function(s){return '<span class="pill">'+esc(nm[s]||s)+' <button type="button" data-rm="'+esc(s)+'" aria-label="比較から外す">×</button></span>';}).join('');
    bar.className='cmpbar on';
    bar.innerHTML='<div class="cmpbar-inner"><span class="cmpbar-lbl">比較リスト</span>'+pills+
      '<a class="btn btn-sm" href="'+base+'compare.html?ids='+a.join(',')+'">'+a.length+'件を比較する →</a>'+
      '<button type="button" class="btn-ghost" data-cmpclear>クリア</button></div>';
    document.body.classList.add('cmp-open');
  }
  document.addEventListener('click',function(e){
    var t=e.target;
    var add=t.closest?t.closest('.cmp-add-btn[data-slug]'):null;
    if(add){e.preventDefault();toggle(add.getAttribute('data-slug'),add.getAttribute('data-name'));return;}
    var rm=t.closest?t.closest('[data-rm]'):null;
    if(rm){e.preventDefault();remove(rm.getAttribute('data-rm'));return;}
    if(t.closest&&t.closest('[data-cmpclear]')){clear();return;}
  });
  window.CmpBar={refresh:refresh,toggle:toggle,get:load};
  if(document.readyState!=='loading')refresh();
  else document.addEventListener('DOMContentLoaded',refresh);
})();
"""


COMPARE_JS = """(function(){
  var p=new URLSearchParams(location.search);
  var ids=(p.get('ids')||'').split(',').filter(Boolean);
  var root=document.getElementById('cmp');
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  if(!ids.length){root.innerHTML='<p class="muted">比較する資格が選択されていません。<a href="index.html">資格一覧</a>から各行の「＋比較」で資格を選んでください。</p>';return;}
  function feeNum(x){var m=(x.fee||'').replace(/,/g,'').match(/([0-9]+)\\s*円/);return m?parseInt(m[1],10):null;}
  function passNum(x){var m=(x.pass_rate||'').replace(/,/g,'').match(/([0-9]+(?:\\.[0-9]+)?)\\s*%/);return m?parseFloat(m[1]):null;}
  var FIELDS=[['区分','type'],['分野','major'],['カテゴリ','category'],
    ['実施団体','authority'],['受験資格','eligibility'],['試験形式','exam_format'],
    ['受験料','fee'],['合格率','pass_rate'],['実施頻度','frequency']];
  fetch('data/certifications.json').then(function(r){return r.json();}).then(function(all){
    var map={};all.forEach(function(x){map[x.slug]=x;});
    var items=ids.map(function(s){return map[s];}).filter(Boolean);
    if(!items.length){root.innerHTML='<p class="muted">該当する資格データが見つかりませんでした。</p>';return;}
    var v=[],seen={};
    function card(label,x,why){if(!x||seen[label+x.slug])return;seen[label+x.slug]=1;
      v.push('<div class="cmp-verdict-card"><div class="pick">'+label+'</div>'+
        '<div class="pickname"><a href="c/'+x.slug+'.html">'+esc(x.name)+'</a></div>'+
        '<div class="why">'+why+'</div></div>');}
    if(items.length>=2){
      var cheap=items.filter(function(x){return feeNum(x)!==null;}).sort(function(a,b){return feeNum(a)-feeNum(b);})[0];
      if(cheap)card('費用を抑えたいなら',cheap,'受験料が最も安い：'+esc(cheap.fee));
      var hp=items.filter(function(x){return passNum(x)!==null;}).sort(function(a,b){return passNum(b)-passNum(a);})[0];
      if(hp)card('合格しやすさなら',hp,'公表合格率が最も高い：'+esc(hp.pass_rate));
      var nr=items.filter(function(x){return /(なし|不問|制限なし)/.test(x.eligibility||'');})[0];
      if(nr)card('誰でも受けたいなら',nr,'受験資格の制限なし');
    }
    var vhtml=v.length?('<section class="cmp-verdict"><h2 class="cmp-verdict-title">選び方の目安（掲載データに基づく簡易判定）</h2><div class="cmp-verdict-grid">'+v.join('')+'</div></section>'):'';
    var vroot=document.getElementById('cmpVerdict'); if(vroot)vroot.innerHTML=vhtml;
    var h='<table class="cmp"><thead><tr><th></th>';
    items.forEach(function(x){h+='<th><a href="c/'+x.slug+'.html">'+esc(x.name)+'</a></th>';});
    h+='</tr></thead><tbody>';
    FIELDS.forEach(function(f){
      h+='<tr><th>'+f[0]+'</th>';
      items.forEach(function(x){
        var v;
        if(f[1]==='type')v='<span class="badge b-'+x.type+'">'+esc(x.type)+'</span>';
        else v=x[f[1]]?esc(x[f[1]]):'<span class="muted">公式で確認</span>';
        h+='<td>'+v+'</td>';
      });
      h+='</tr>';
    });
    h+='<tr><th>公式サイト</th>';
    items.forEach(function(x){
      h+='<td>'+(x.official_url?'<a href="'+esc(x.official_url)+'" target="_blank" rel="nofollow noopener">公式サイト</a>':'<span class="muted">未登録</span>')+'</td>';
    });
    h+='</tr></tbody></table>';
    root.innerHTML=h;
  });
})();
"""


OCC_SEARCH_JS = """(function(){
  var q=document.getElementById('occ-q'),mj=document.getElementById('occ-major'),
      res=document.getElementById('occ-results'),stat=document.getElementById('occ-status'),
      stat0=document.getElementById('occ-static');
  if(!q)return;
  var DATA=[];
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function render(){
    var t=(q.value||'').trim().toLowerCase(),m=mj.value;
    if(!t&&!m){res.hidden=true;stat0.hidden=false;stat.textContent='';return;}
    var out=DATA.filter(function(x){
      if(m&&x.m!==m)return false;
      if(t&&x.n.toLowerCase().indexOf(t)<0)return false;
      return true;
    });
    stat0.hidden=true;res.hidden=false;
    stat.textContent=out.length+' 件';
    res.innerHTML=out.slice(0,400).map(function(x){
      return '<li><a href="'+x.id+'.html">'+esc(x.n)+'</a> <span class="muted">（'+x.c+'資格）</span></li>';
    }).join('')||'<li class="empty-state">条件に一致する職種が見つかりませんでした。キーワードを短くするか、分野を「すべて」に戻してみてください。</li>';
    if(out.length>400)res.innerHTML+='<li class="muted">…他 '+(out.length-400)+' 件（絞り込んでください）</li>';
  }
  fetch('../data/occupations.json').then(function(r){return r.json();}).then(function(all){
    DATA=all.slice().sort(function(a,b){return b.c-a.c||(a.n<b.n?-1:1);});
    var mset={};all.forEach(function(x){if(x.m)mset[x.m]=1;});
    Object.keys(mset).sort().forEach(function(v){var o=document.createElement('option');o.value=v;o.textContent=v;mj.appendChild(o);});
    render();
  });
  q.addEventListener('input',render);mj.addEventListener('change',render);
})();
"""

APP_CSS = """:root{
--ink:#222222;--ink-deep:#1a1a1a;--gray-900:#2f2f2f;--gray-800:#434343;--gray-700:#525252;
--gray-600:#5a5a5a;--gray-500:#666666;--gray-400:#7f7f7f;--gray-300:#c4c4c4;--gray-200:#dcdcdc;
--gray-100:#f0f0f0;--gray-50:#f7f7f7;--white:#fff;--page-bg:#eef0f1;
--accent:#236f64;--accent-hover:#1c5a51;--accent-light:#e6f1ef;--accent-ring:rgba(35,111,100,.22);
--radius:8px;
--text-hero:clamp(1.75rem,4vw,2.45rem);--text-page:1.5rem;--text-section:1.3rem;--text-section-sub:1.12rem;
--text-card-title:1.18rem;--text-lead:1.06rem;--text-input:1.06rem;--text-body:1.02rem;--text-ui:1rem;
--text-nav:.95rem;--text-sm:.9rem;--text-xs:.86rem;--text-2xs:.82rem;--text-chip:.8rem}
*{box-sizing:border-box}
html{font-size:16px}
body{margin:0;min-height:100vh;display:flex;flex-direction:column;font-family:"Noto Sans JP",system-ui,-apple-system,"Hiragino Kaku Gothic ProN",Meiryo,sans-serif;font-size:var(--text-ui);color:var(--ink);background:var(--page-bg);line-height:1.7;-webkit-font-smoothing:antialiased}
a{color:var(--ink)}a:hover{text-decoration:underline}
img{max-width:100%}
:focus-visible{outline:3px solid var(--accent-ring);outline-offset:2px}
.skip-link{position:absolute;left:-9999px}.skip-link:focus{left:8px;top:8px;background:#fff;padding:8px 12px;z-index:50;border-radius:6px}

/* Header */
.site-header{background:var(--ink-deep);color:#fff;border-bottom:1px solid var(--gray-800);position:sticky;top:0;z-index:30}
@media(prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}
html{scroll-padding-top:64px}
.header-inner{max-width:1200px;margin:0 auto;padding:12px 24px;display:flex;align-items:center;gap:16px;min-width:0}
.header-brand{flex-shrink:0;display:flex;flex-direction:column;gap:2px}
.logo{color:#fff;font-weight:700;font-size:1.24rem;text-decoration:none;letter-spacing:.02em}
.logo:hover{color:var(--gray-300);text-decoration:none}
.site-tagline{color:var(--gray-400);font-size:var(--text-xs);font-weight:400;line-height:1.3}
.ico-svg{width:18px;height:18px;display:block;flex-shrink:0}
.header-nav{display:flex;align-items:center;flex-wrap:wrap;margin-left:auto;min-width:0}
.header-nav a{color:var(--gray-300);font-size:var(--text-nav);text-decoration:none;padding:6px 8px;white-space:nowrap;border-radius:4px}
.header-nav a:hover{color:#fff;text-decoration:none}
.header-nav a.is-current{color:#fff;font-weight:600}
.header-nav-sep{color:var(--gray-600);font-size:var(--text-xs);user-select:none;padding:0 1px}
.header-actions{display:none;align-items:center;gap:2px;margin-left:auto;flex-shrink:0}
.header-icon-btn{display:inline-flex;align-items:center;justify-content:center;background:transparent;border:none;color:var(--gray-300);cursor:pointer;padding:8px;border-radius:6px;line-height:0;font-family:inherit}
.header-icon-btn:hover{color:#fff;background:rgba(255,255,255,.08)}
.header-search-panel,.header-menu-panel{display:none;border-top:1px solid var(--gray-800);background:var(--ink-deep)}
.site-header--search-open .header-search-panel{display:block}
.site-header--menu-open .header-menu-panel{display:flex}
.header-search-panel{padding:12px 16px 14px}
.header-search-form{max-width:1200px;margin:0 auto;display:flex;gap:8px;min-width:0}
.header-search-form input{flex:1;min-width:0;padding:10px 14px;border:1px solid var(--gray-700);border-radius:var(--radius);background:rgba(255,255,255,.06);color:#fff;font-size:var(--text-input);font-family:inherit}
.header-search-form input::placeholder{color:var(--gray-500)}
.header-search-form button{padding:10px 16px;background:var(--accent);color:#fff;border:none;border-radius:var(--radius);font-family:inherit;font-weight:600;cursor:pointer;white-space:nowrap}
.header-search-form button:hover{background:var(--accent-hover)}
.header-menu-panel{flex-direction:column;max-width:1200px;margin:0 auto;padding:4px 16px 10px;width:100%}
.header-menu-panel a{color:var(--gray-300);text-decoration:none;padding:12px 4px;border-bottom:1px solid var(--gray-800);font-size:var(--text-ui)}
.header-menu-panel a:last-child{border-bottom:none}
.header-menu-panel a:hover{color:#fff;text-decoration:none}
@media(max-width:768px){.header-nav{display:none}.header-actions{display:flex}.header-inner{padding:10px 16px}.site-tagline{display:none}.container{padding:20px 16px 36px}.block-compare{margin-left:-16px;margin-right:-16px;padding-left:16px;padding-right:16px}}

.container{max-width:1200px;margin:0 auto;padding:24px 24px 40px;width:100%;flex:1 0 auto;min-width:0;background:#fff;box-shadow:0 0 24px rgba(0,0,0,.05)}

/* Hero */
.hero{padding:28px 0 4px;margin-bottom:8px}
.hero h1{font-weight:700;line-height:1.4;margin:0 0 12px;letter-spacing:.02em}
.hero-h1-line{display:block;font-size:var(--text-hero);font-weight:700;color:var(--ink-deep);letter-spacing:.02em}
.hero-h1-line+.hero-h1-line{margin-top:2px}
.hero-sub{font-size:var(--text-lead);color:var(--gray-800);line-height:1.75;max-width:40em;margin:0}
.hero-search{margin-top:18px;max-width:520px;position:relative}
.hero-search input{width:100%;padding:12px 16px 12px 42px;border:1px solid var(--gray-300);border-radius:var(--radius);font-size:var(--text-input);background:#fff;color:var(--gray-900);font-family:inherit}
.hero-search input::placeholder{color:var(--gray-500)}
.hero-search input:focus,.hero-search input:focus-visible{border-color:var(--accent);outline:3px solid var(--accent-ring);outline-offset:2px}
.hero-search .ico{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--gray-500);display:flex}
.hero-hint{margin-top:10px;font-size:var(--text-sm);color:var(--gray-500)}
.hero-hint a{color:var(--accent);font-weight:600;text-decoration:none}.hero-hint a:hover{text-decoration:underline}
.hero-result{margin-top:12px;font-size:var(--text-sm);color:var(--gray-700)}
.hero-result a{color:var(--accent);font-weight:600;text-decoration:underline;text-underline-offset:2px}
.hero-result strong{color:var(--ink-deep)}

/* Blocks */
.block{margin-bottom:28px}.block-primary{margin-bottom:40px}.block-secondary{margin-bottom:34px}
.block-head{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:12px;gap:8px;flex-wrap:wrap}
.block-primary .block-head h2{font-size:var(--text-section);font-weight:700;color:var(--ink-deep);margin:0}
.block-secondary .block-head h2{font-size:var(--text-section-sub);font-weight:600;color:var(--gray-800);margin:0}
.block-head p{font-size:var(--text-nav);color:var(--gray-500);margin:0}
.block-compare{background:var(--gray-50);margin-left:-24px;margin-right:-24px;padding:26px 24px 30px;border-top:1px solid var(--gray-200);margin-bottom:0}
.card-link{position:relative}
.card-link::after{content:"→";position:absolute;right:12px;top:14px;font-size:var(--text-nav);font-weight:600;color:var(--gray-400);opacity:0;transition:opacity .15s,color .15s;pointer-events:none}
.card-link:hover::after,.card-link:focus-visible::after{opacity:1;color:var(--accent)}
.card-link:hover,.card-link:focus-visible{background:var(--accent-light);border-color:var(--accent);text-decoration:none}

/* Purpose */
.purpose-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media(max-width:640px){.purpose-grid{grid-template-columns:1fr}}
.purpose-card{display:flex;flex-direction:column;background:#fff;border:1px solid var(--gray-200);border-radius:var(--radius);padding:16px 14px;color:inherit}
.purpose-card-head{display:flex;align-items:flex-start;gap:12px;margin-bottom:10px}
.purpose-card .icon{flex-shrink:0;width:44px;height:44px;display:flex;align-items:center;justify-content:center;background:var(--gray-100);border-radius:var(--radius);color:var(--gray-700)}
.purpose-card .icon-svg{width:26px;height:26px}
.purpose-card h3{font-size:var(--text-card-title);font-weight:700;margin:0 0 3px;color:var(--ink-deep)}
.purpose-card-for{font-size:var(--text-sm);color:var(--gray-600);line-height:1.45;margin:0}
.purpose-card-links{list-style:none;margin:0;padding:0;border-top:1px solid var(--gray-200)}
.purpose-card-links li{border-bottom:1px solid var(--gray-100)}
.purpose-card-links li:last-child{border-bottom:0}
.purpose-card-links a{display:block;padding:9px 4px 9px 16px;font-size:var(--text-sm);color:var(--gray-800);text-decoration:none;position:relative;line-height:1.4}
.purpose-card-links a::before{content:"›";position:absolute;left:3px;top:9px;color:var(--accent);font-weight:700}
.purpose-card-links a:hover,.purpose-card-links a:focus-visible{color:var(--accent);background:var(--accent-light)}
.purpose-card-links li:last-child a{font-weight:600;color:var(--accent)}

/* Popular */
.popular-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
@media(max-width:720px){.popular-grid{grid-template-columns:repeat(2,1fr);gap:10px}.pop-card--more{display:none}}
.pop-card{display:flex;flex-direction:column;background:#fff;color:var(--gray-900);border-radius:var(--radius);padding:14px 32px 12px 13px;text-decoration:none;border:1px solid var(--gray-200);transition:border-color .15s,background .15s}
.pop-card-name{font-size:var(--text-body);font-weight:700;line-height:1.35;margin-bottom:6px;color:var(--ink-deep)}
.pop-card-audience{font-size:var(--text-sm);color:var(--gray-800);line-height:1.5;margin:0 0 10px;font-weight:600;padding-left:8px;border-left:2px solid var(--accent)}
.pop-card-facts{list-style:none;margin:auto 0 0;padding:10px 0 0;border-top:1px solid var(--gray-200);display:flex;flex-direction:column;gap:5px}
.pop-card-facts li{display:grid;grid-template-columns:4.8em 1fr;gap:4px;font-size:var(--text-xs);line-height:1.45}
.pop-card-facts .k{color:var(--gray-500)}.pop-card-facts .v{color:var(--gray-800);font-weight:600}
.popular-more,.field-more,.compare-more{margin-top:12px;text-align:right}
.popular-more a,.field-more a,.compare-more a{font-size:var(--text-ui);font-weight:600;color:var(--gray-800);text-decoration:underline;text-underline-offset:2px}

/* Fields */
.field-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
@media(max-width:900px){.field-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:520px){.field-grid{grid-template-columns:1fr}}
.field-card{display:flex;align-items:flex-start;gap:12px;background:#fff;border:1px solid var(--gray-200);border-radius:10px;padding:13px;text-decoration:none;color:inherit;transition:border-color .15s,background .15s}
.field-card:hover,.field-card:focus-visible{background:var(--accent-light);border-color:var(--accent);text-decoration:none}
.field-card .icon{flex-shrink:0;width:40px;height:40px;display:flex;align-items:center;justify-content:center;background:var(--gray-100);border-radius:var(--radius);color:var(--ink)}
.field-card .icon-svg{width:22px;height:22px}
.field-card-body{min-width:0;flex:1}
.field-card-top{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin:0 0 4px}
.field-card h3{font-size:var(--text-body);font-weight:600;line-height:1.35;color:var(--ink-deep);margin:0}
.field-count{flex-shrink:0;margin-top:1px;padding:3px 7px;border-radius:4px;font-size:var(--text-2xs);font-weight:600;color:var(--gray-700);background:var(--gray-100);border:1px solid var(--gray-200);line-height:1.2;white-space:nowrap}
.field-examples{font-size:var(--text-xs);color:var(--gray-500);line-height:1.45;margin:0}

/* Compare cards */
.compare-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
@media(max-width:900px){.compare-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:560px){.compare-grid{grid-template-columns:1fr}}
.compare-card{display:flex;flex-direction:column;background:#fff;border:1px solid var(--gray-200);border-radius:10px;padding:14px;text-decoration:none;color:inherit;transition:border-color .15s,background .15s}
.compare-card:hover,.compare-card:focus-visible{background:var(--accent-light);border-color:var(--accent);text-decoration:none}
.compare-tag{font-size:var(--text-2xs);font-weight:600;color:var(--gray-500);letter-spacing:.04em;margin-bottom:6px}
.compare-names{font-size:var(--text-ui);font-weight:600;line-height:1.45;color:var(--ink-deep);margin-bottom:6px;flex:1}
.compare-names em{font-style:normal;color:var(--gray-500);font-weight:400;font-size:var(--text-sm)}
.compare-tip{font-size:var(--text-sm);color:var(--gray-700);line-height:1.5;margin-bottom:8px}
.compare-go{font-size:var(--text-sm);font-weight:600;color:var(--accent);text-decoration:underline;text-underline-offset:2px}

/* Buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;background:var(--accent);color:#fff;padding:9px 18px;border-radius:var(--radius);font-size:var(--text-ui);font-weight:600;text-decoration:none;border:none;cursor:pointer;font-family:inherit}
.btn:hover{background:var(--accent-hover);text-decoration:none}
.btn-outline{background:#fff;color:var(--accent);border:1px solid var(--accent)}
.btn-outline:hover{background:var(--gray-100)}

/* Lists / search */
h1{font-size:var(--text-page);margin:.1em 0 .35em;color:var(--ink-deep);font-weight:700}
h2{color:var(--ink-deep)}
.lead{color:var(--gray-700);font-size:var(--text-body);margin:0 0 14px}
.controls{display:flex;gap:10px 14px;flex-wrap:wrap;margin:16px 0;align-items:flex-end}
.controls input,.controls select{padding:10px 12px;border:1px solid var(--gray-300);border-radius:var(--radius);font-size:var(--text-ui);font-family:inherit;background:#fff;color:var(--ink)}
.controls input{flex:1 1 260px}.controls select{cursor:pointer}
.ctl{display:inline-flex;flex-direction:column;gap:3px;min-width:0}
.ctl-l{font-size:var(--text-2xs);font-weight:600;color:var(--gray-500);letter-spacing:.02em}
.ctl select{width:100%;min-width:130px}
@media(max-width:560px){.ctl{flex:1 1 44%}}
.filters{display:flex;flex-wrap:wrap;gap:14px;margin:-6px 0 6px;font-size:var(--text-sm);color:var(--gray-700)}
.filters label{display:inline-flex;align-items:center;gap:5px;cursor:pointer}
.tagfilter{display:flex;flex-wrap:wrap;align-items:center;gap:7px;margin:2px 0 10px}
.tagfilter .tf-label{font-size:var(--text-sm);color:var(--gray-700);margin-right:2px}
.tf-chip{background:#fff;color:var(--accent);border:1px solid var(--gray-300);border-radius:999px;padding:5px 13px;font-size:var(--text-sm);cursor:pointer;transition:.12s}
.tf-chip:hover{background:var(--accent-light)}
.tf-chip.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.results{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:7px}
.results li{background:#fff;border:1px solid var(--gray-200);border-radius:11px;padding:11px 14px}
.results li a{font-weight:600;color:var(--gray-900);text-decoration:none}
.results li a:hover{color:var(--accent)}
/* 資格の一覧・ランキングリスト */
.cert-list{list-style:none;padding:0;margin:.5em 0 0;display:flex;flex-direction:column;gap:8px}
.cl-item{display:flex;align-items:stretch;gap:10px}
.cl-rank{flex-shrink:0;display:flex;align-items:center;justify-content:center;min-width:30px;font-weight:700;font-size:var(--text-card-title);color:var(--gray-400);font-variant-numeric:tabular-nums;line-height:1}
.cl-rank--top{color:var(--accent)}
.cl-link{flex:1;min-width:0;display:flex;flex-direction:column;gap:5px;background:#fff;border:1px solid var(--gray-200);border-radius:10px;padding:12px 14px;text-decoration:none;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,.06);transition:border-color .15s,background .15s}
.cl-link:hover,.cl-link:focus-visible{border-color:var(--accent);background:var(--accent-light);text-decoration:none}
.cl-name{font-size:var(--text-body);font-weight:600;color:var(--gray-900);line-height:1.4}
.cl-link:hover .cl-name{color:var(--accent-hover)}
.cl-meta{display:flex;flex-wrap:wrap;align-items:center;gap:5px 9px;font-size:var(--text-sm);color:var(--gray-600);line-height:1.4}
.cl-major,.cl-cat{color:var(--gray-600)}
.cl-data{color:var(--gray-700);font-weight:600}
.cert-list--ranked .cl-rank{min-width:34px}
@media(max-width:480px){.cl-rank{min-width:22px;font-size:var(--text-body)}.cert-list--ranked .cl-rank{min-width:26px}}
.results .meta{display:block;color:var(--gray-500);font-size:var(--text-sm);margin-top:3px}
.hint{font-size:var(--text-sm);margin:4px 0 10px;color:var(--gray-500)}
.results-bar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:2px 0 2px}
.results-bar #status{margin:0}
.clear-filters{background:none;border:none;color:var(--accent);font-family:inherit;font-size:var(--text-sm);font-weight:600;cursor:pointer;padding:0;text-decoration:underline;text-underline-offset:2px}
.clear-filters:hover{color:var(--accent-hover)}
.muted{color:var(--gray-500)}
.purpose-card,.pop-card,.field-card,.compare-card,.faq-item,table.spec,.results li,.occ-list li{box-shadow:0 1px 3px rgba(0,0,0,.07)}
.crumbs{font-size:var(--text-nav);color:var(--gray-500);margin-bottom:10px}
.crumbs a{color:var(--gray-700)}

/* Badges (subtle) */
.badge{display:inline-block;padding:1px 8px;border-radius:4px;font-size:var(--text-2xs);font-weight:600;border:1px solid var(--gray-300);color:var(--gray-700);background:var(--gray-100);vertical-align:middle}
.badge-national,.b-国家{color:#9a3b32;background:#fbeeec;border-color:#eccfca}
.badge-public,.b-公的{color:var(--accent-hover);background:var(--accent-light);border-color:rgba(42,122,110,.22)}
.badge-private,.b-民間{color:#3a6b46;background:#eef5f0;border-color:#cfe2d5}
.badge-unknown,.b-要確認{color:var(--gray-600);background:var(--gray-100);border-color:var(--gray-300)}
.badge-overseas{color:#6a4a8a;background:#f3eef8;border-color:#ddd0ea}

/* Spec table (detail) */
table.spec{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--gray-200);border-radius:10px;overflow:hidden;font-size:var(--text-ui)}
table.spec th,table.spec td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--gray-200);vertical-align:top}
table.spec th{width:34%;background:var(--gray-100);color:var(--gray-800);font-weight:600;white-space:nowrap}
@media(max-width:480px){table.spec th,table.spec td{display:block;width:auto}table.spec th{white-space:normal;border-bottom:none;padding:9px 14px 1px}table.spec td{padding:1px 14px 11px}}
.related{margin-top:24px}.related ul{padding-left:1.1em}
.official-cta{margin:16px 0 6px}
.btn-official{display:inline-block;background:var(--accent);color:#fff;font-weight:700;padding:11px 20px;border-radius:var(--radius)}
.btn-official:hover{background:var(--accent-hover);text-decoration:none}
.provenance{font-size:var(--text-sm);color:var(--gray-600);background:var(--gray-50);border:1px solid var(--gray-200);border-radius:var(--radius);padding:11px 14px;margin:10px 0 0}
.feat-list{margin:.2em 0 .6em;padding-left:1.1em}.feat-list li{margin:2px 0}
.feat-list a{color:var(--gray-800)}
.updated{font-size:var(--text-sm);color:var(--gray-500);margin:.1em 0 .6em}.updated .muted{margin-left:.4em}
.tag-chip{display:inline-block;background:var(--gray-100);color:var(--gray-700);border:1px solid var(--gray-200);border-radius:12px;padding:2px 10px;margin:2px 4px 2px 0;font-size:var(--text-xs)}
.tag-ind{background:var(--accent-light);color:var(--accent-hover);border-color:rgba(42,122,110,.18)}
a.tag-chip{text-decoration:none;cursor:pointer;transition:border-color .12s,background .12s}
a.tag-chip:hover{border-color:var(--accent);background:var(--accent-light);text-decoration:none}
.diff-badge{display:inline-block;font-weight:700;font-size:var(--text-xs);padding:2px 9px;border-radius:6px;color:#fff}
.diff-veryhard{background:#9a3b32}.diff-hard{background:#b5642f}.diff-mid{background:#caa53c;color:#3a2c00}
.diff-easy{background:#3a6b46}.diff-veryeasy{background:var(--accent)}
.diff-rank{display:inline-block;font-weight:700;font-size:var(--text-xs);padding:2px 10px;border-radius:6px;background:var(--gray-700);color:#fff;margin:1px 2px 1px 0}
.diff-rank-field{background:var(--accent-hover)}
.diff-meta{font-size:var(--text-2xs);margin-top:3px}
.roadmap{margin:.4em 0 .6em}.roadmap h3{font-size:.95rem;margin:.7em 0 .35em;color:var(--gray-800)}
.rm-track{list-style:none;display:flex;flex-wrap:wrap;align-items:stretch;gap:8px;padding:0;margin:.2em 0}
.rm-step{display:flex;flex-direction:column;justify-content:center;background:#fff;border:1px solid var(--gray-300);border-radius:9px;padding:8px 12px;position:relative;min-width:96px}
.rm-step:not(:last-child){margin-right:14px}
.rm-step:not(:last-child)::after{content:"›";position:absolute;right:-13px;top:50%;transform:translateY(-50%);color:var(--gray-400);font-weight:700;font-size:1.2rem}
.rm-step a{text-decoration:none;color:var(--accent);font-weight:600}
.rm-cur{background:var(--accent-light);border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
.rm-cur span{font-weight:700;color:var(--ink-deep)}.rm-cur small{display:block;color:var(--gray-600);font-size:.72rem;margin-top:1px}
@media(max-width:560px){.rm-step{min-width:0;flex:1 1 100%}.rm-step:not(:last-child){margin-right:0;margin-bottom:14px}.rm-step:not(:last-child)::after{content:"▾";right:50%;top:auto;bottom:-13px;transform:translateX(50%)}}
.careers-sec,.materials-sec,.rel-certs,.rel-links{margin:18px 0 0;border-top:1px solid var(--gray-200);padding-top:12px}
.careers-sec h2,.materials-sec h2,.rel-certs h2,.rel-links h2,.occ-work h2,.occ-salary h2{font-size:1.05rem;margin:.2em 0 .4em}
.careers,.rel-certs ul,.rel-links ul{margin:.2em 0;padding-left:1.1em}.careers li{margin:2px 0}
.careers-src{font-size:var(--text-2xs);margin:.3em 0 0}
.occ-list{columns:2;column-gap:22px}.occ-list li{break-inside:avoid;background:#fff;border:1px solid var(--gray-200);border-radius:8px;padding:8px 11px;margin-bottom:7px}
@media(max-width:560px){.occ-list{columns:1}}
.jobtag{margin:.5em 0 0;font-size:.92rem}
.pr-badge{display:inline-block;background:var(--gray-400);color:#fff;font-size:.62rem;font-weight:700;padding:1px 6px;border-radius:4px;margin-left:8px;vertical-align:middle;letter-spacing:.05em}
.ad-disclosure{font-size:var(--text-2xs);color:var(--gray-600);background:#fbf6ee;border:1px solid #efe1c8;border-radius:8px;padding:9px 12px;margin:0 0 10px}
.materials{list-style:none;padding:0;margin:.2em 0}
.materials li{display:flex;gap:10px;align-items:flex-start;background:#fff;border:1px solid var(--gray-200);border-radius:8px;padding:9px 12px;margin-bottom:7px}
.mat-kind{flex:0 0 auto;background:var(--accent-light);color:var(--accent-hover);border:1px solid rgba(42,122,110,.18);border-radius:6px;font-size:.74rem;font-weight:700;padding:2px 8px;margin-top:2px}
.mat-body{flex:1}.mat-note{display:block;color:var(--gray-500);font-size:var(--text-xs);margin-top:2px}
.mat-foot{font-size:var(--text-2xs);margin:.4em 0 0}
.rel-certs h3{font-size:.92rem;margin:.7em 0 .2em;color:var(--gray-800)}
.occ-meta{background:var(--gray-50);border:1px solid var(--gray-200);border-radius:8px;padding:10px 13px;margin:10px 0}
.occ-stats{margin:0 0 6px}.occ-fields{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px}
.occ-stats-label{font-size:var(--text-xs);color:var(--gray-700);font-weight:600;margin-right:4px}
.occ-stat{display:inline-block;background:var(--accent-light);color:var(--accent-hover);border:1px solid rgba(42,122,110,.18);border-radius:6px;font-size:.8rem;padding:1px 8px;margin-right:6px}
.occ-work{margin:14px 0 0}.occ-work p{margin:.2em 0}
.occ-salary{margin:14px 0 0}
.salary-range{font-size:1.2rem;font-weight:700;color:var(--accent);margin:.1em 0}
.occ-salary-note{font-size:var(--text-2xs)}
.occ-skills{display:flex;flex-wrap:wrap;gap:2px 0}
.hub-grp{font-size:1rem;margin:1.1em 0 .3em;color:var(--accent-hover);border-bottom:1px solid var(--gray-200);padding-bottom:3px}
.vs-table{width:100%;border-collapse:collapse;margin:14px 0;font-size:.94rem}
.vs-table th,.vs-table td{border:1px solid var(--gray-200);padding:8px 10px;text-align:left;vertical-align:top}
.vs-table thead th{background:var(--gray-100);color:var(--ink-deep);text-align:center}
.vs-table tbody th{background:var(--gray-50);white-space:nowrap;width:7.5em}
.vs-cta{margin:14px 0;display:flex;gap:10px;flex-wrap:wrap}
.feature-nav{margin-top:28px;border-top:1px solid var(--gray-200);padding-top:14px}
.feature-nav h2{font-size:1.05rem;margin:.6em 0 .3em}
.feature-nav h3{font-size:.92rem;font-weight:600;color:var(--gray-800);margin:.9em 0 .3em}
.feature-nav ul{margin:.2em 0 .6em;padding-left:1.1em}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{display:inline-block;padding:5px 11px;border:1px solid var(--gray-300);background:#fff;border-radius:999px;font-size:var(--text-sm);color:var(--gray-800)}
.chip:hover{background:var(--accent-light);border-color:var(--accent);text-decoration:none}

/* Compare bar + table */
.cmp-add{margin-right:9px;cursor:pointer}.cmp-add input{width:16px;height:16px;vertical-align:middle;cursor:pointer}
.cmpbar{position:fixed;left:0;right:0;bottom:0;background:var(--ink-deep);color:#fff;display:none;z-index:20;border-top:1px solid var(--gray-800)}
.cmpbar.on{display:block}
.cmpbar-inner{max-width:1200px;margin:0 auto;padding:10px 20px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.cmpbar-lbl{font-size:var(--text-xs);color:var(--gray-400)}
.cmpbar .pill{display:inline-flex;align-items:center;gap:5px;background:var(--gray-800);padding:4px 10px;border-radius:999px;font-size:var(--text-nav);border:1px solid var(--gray-700);color:#fff}
.cmpbar .pill button{background:none;border:none;color:var(--gray-400);cursor:pointer;font:inherit;padding:0 0 0 2px;line-height:1}
.cmpbar .pill button:hover{color:#fff}
.cmpbar .btn{margin-left:auto}
body.cmp-open{padding-bottom:76px}
.cmpbar .btn{background:var(--accent);color:#fff;font-weight:700;padding:7px 16px;border-radius:var(--radius)}
.cmpbar .btn:hover{background:var(--accent-hover)}
.cmpbar .btn-ghost{background:transparent;color:var(--gray-300);border:1px solid var(--gray-600);padding:6px 13px;border-radius:var(--radius);cursor:pointer;font:inherit;font-size:.9rem}
.cmpbar .btn-ghost:hover{background:rgba(255,255,255,.08)}
.cmp-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
table.cmp{border-collapse:collapse;background:#fff;border:1px solid var(--gray-200);border-radius:10px;min-width:100%}
table.cmp th,table.cmp td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--gray-200);border-right:1px solid var(--gray-200);vertical-align:top;font-size:.9rem;min-width:150px}
table.cmp thead th{background:var(--gray-100);color:var(--ink-deep);font-weight:700}
table.cmp tbody th{background:var(--gray-50);color:var(--gray-800);white-space:nowrap;min-width:110px;width:110px}

/* Footer */
.site-footer{background:var(--gray-50);border-top:1px solid var(--gray-200);margin-top:auto;color:var(--gray-600)}
.site-footer-inner{max-width:1200px;margin:0 auto;padding:24px 24px 22px}
.site-footer-brand{font-size:var(--text-body);font-weight:700;color:var(--ink-deep);margin:0 0 10px}
.site-footer-nav{display:flex;flex-wrap:wrap;gap:6px 18px;margin-bottom:12px}
.site-footer-nav a{font-size:var(--text-sm);color:var(--gray-700);text-decoration:none}
.site-footer-nav a:hover{color:var(--ink);text-decoration:underline;text-underline-offset:2px}
.site-footer-note{font-size:var(--text-xs);color:var(--gray-500);line-height:1.65;margin:0 0 8px;max-width:54em}
.site-footer-copy{font-size:var(--text-2xs);color:var(--gray-400);line-height:1.5;margin:0}
.site-footer-partners{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px;padding:12px 0;margin:0 0 12px;border-top:1px solid var(--gray-200);border-bottom:1px solid var(--gray-200)}
.sfp-label{font-size:var(--text-xs);font-weight:700;color:var(--gray-700)}
.sfp-links{display:flex;flex-wrap:wrap;gap:4px 14px}
.site-footer-partners a{font-size:var(--text-sm);color:var(--accent);text-decoration:none;font-weight:600}
.site-footer-partners a:hover{text-decoration:underline;text-underline-offset:2px}
/* Partner sites (おすすめ対策サイト) */
.partner-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media(max-width:760px){.partner-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:460px){.partner-grid{grid-template-columns:1fr}}
.partner-card{display:flex;flex-direction:column;gap:3px;background:#fff;border:1px solid var(--gray-200);border-radius:var(--radius);padding:13px 14px;text-decoration:none;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,.07);transition:border-color .15s,background .15s}
.partner-card:hover{border-color:var(--accent);background:var(--accent-light)}
.partner-card-name{font-size:var(--text-card-title);font-weight:700;color:var(--ink-deep)}
.partner-card-tag{font-size:var(--text-sm);color:var(--gray-700);line-height:1.5}
.partner-ext{font-size:.78em;color:var(--accent);margin-left:5px;font-weight:700}
.partner-detail{margin:0 0 22px;background:var(--accent-light);border:1px solid rgba(35,111,100,.2);border-radius:var(--radius);padding:14px 16px}
.partner-detail .detail-section-title{margin-bottom:8px}
.partner-detail-grid{display:flex;flex-wrap:wrap;gap:10px}
.partner-detail-card{display:flex;flex-direction:column;gap:2px;flex:1 1 220px;background:#fff;border:1px solid rgba(35,111,100,.25);border-radius:var(--radius);padding:11px 13px;text-decoration:none;color:inherit;transition:border-color .15s}
.partner-detail-card:hover{border-color:var(--accent)}
.pd-name{font-size:var(--text-body);font-weight:700;color:var(--accent-hover)}
.pd-tag{font-size:var(--text-sm);color:var(--gray-700);line-height:1.45}
.partner-note{font-size:var(--text-2xs);margin:8px 0 0}
/* Detail */
.detail-title{font-size:var(--text-page);font-weight:700;color:var(--ink-deep);line-height:1.35;margin:.1em 0 8px}
.detail-audience{font-size:var(--text-lead);color:var(--gray-700);line-height:1.65;margin:0 0 18px;max-width:42em}
.detail-facts{margin-bottom:18px}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px}
.fact{background:var(--gray-50);border-radius:8px;padding:9px 11px;border:1px solid var(--gray-200)}
.fact .l{font-size:var(--text-2xs);color:var(--gray-500)}
.fact .v{font-size:var(--text-nav);font-weight:600;color:var(--ink-deep)}
.detail-actions{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:22px;align-items:center}
.detail-actions .official-cta{margin:0}
.detail-section-title{font-size:var(--text-nav);font-weight:600;color:var(--ink-deep);margin:0 0 10px}
.detail-related{margin:18px 0 0;border-top:1px solid var(--gray-200);padding-top:14px}
.detail-related h3{font-size:.95rem;margin:.9em 0 .35em;color:var(--gray-800)}
.detail-related h3:first-of-type{margin-top:.2em}
.detail-related ul{margin:.2em 0;padding-left:1.1em}
.detail-related .more-compare p{margin:.2em 0;line-height:1.55;color:var(--gray-700);font-size:var(--text-ui)}
.detail-related .more-compare a{color:var(--accent);font-weight:600}
.detail-related .more-same ul{columns:2;column-gap:22px}
.detail-related .more-same li{break-inside:avoid;margin:2px 0}
@media(max-width:560px){.detail-related .more-same ul{columns:1}}
.detail-spec{margin-bottom:4px}
.detail-source{margin-top:22px;padding:14px 0 0;border-top:1px solid var(--gray-200);font-size:var(--text-sm);color:var(--gray-600);line-height:1.65}
.detail-source p{margin:0 0 5px}.detail-source .k{font-weight:600;color:var(--gray-700)}
.detail-source a{color:var(--ink);text-decoration:underline;text-underline-offset:2px}
.detail-source-note{margin-top:8px;color:var(--gray-500);font-size:var(--text-xs)}
.detail-points{margin:0 0 22px}
.point-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:7px}
.point-list li{position:relative;padding:8px 12px 8px 32px;background:var(--accent-light);border:1px solid rgba(42,122,110,.15);border-radius:var(--radius);font-size:var(--text-ui);color:var(--gray-800);line-height:1.55}
.point-list li::before{content:"✓";position:absolute;left:12px;top:8px;color:var(--accent);font-weight:700}
.detail-faq{margin:0 0 22px}
.faq-item{border:1px solid var(--gray-200);border-radius:var(--radius);margin-bottom:8px;background:#fff;overflow:hidden}
.faq-item summary{cursor:pointer;padding:12px 14px;font-weight:600;color:var(--ink-deep);font-size:var(--text-ui);list-style:none;position:relative;padding-right:36px}
.faq-item summary::-webkit-details-marker{display:none}
.faq-item summary::after{content:"＋";position:absolute;right:14px;top:12px;color:var(--accent);font-weight:700}
.faq-item[open] summary::after{content:"−"}
.faq-item summary:hover{background:var(--gray-50)}
.faq-a{padding:0 14px 13px;color:var(--gray-700);line-height:1.7;font-size:var(--text-sm)}
.btn-sm{padding:7px 14px;font-size:var(--text-nav)}
/* 一覧の行＋比較ボタン */
.results li{display:flex;gap:12px;align-items:center}
.results li.empty-state{display:block;text-align:center;color:var(--gray-600);background:var(--gray-50);border:1px dashed var(--gray-300);padding:22px 16px;line-height:1.75}
.result-main{flex:1;min-width:0}
.result-label{display:inline-block;font-size:var(--text-2xs);font-weight:600;color:var(--gray-600);background:var(--gray-100);border:1px solid var(--gray-300);border-radius:4px;padding:1px 6px;margin-left:6px;vertical-align:middle}
.cmp-add-btn{flex-shrink:0;min-width:78px;padding:8px 10px;font-size:var(--text-xs);font-weight:600;line-height:1.2;border:1px solid var(--accent);border-radius:8px;background:var(--white);color:var(--accent);cursor:pointer;font-family:inherit;text-align:center;transition:border-color .15s,background .15s,color .15s}
.cmp-add-btn:hover{background:var(--gray-50)}
.cmp-add-btn.is-active{background:var(--accent);border-color:var(--accent);color:#fff}
/* 比較ページの結論カード */
.cmp-verdict{margin:2px 0 18px}
.cmp-verdict-title{font-size:var(--text-nav);font-weight:600;color:var(--ink-deep);margin:0 0 10px}
.cmp-verdict-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}
.cmp-verdict-card{border:1px solid var(--gray-200);border-radius:var(--radius);padding:12px 14px;background:var(--white)}
.cmp-verdict-card .pick{font-size:var(--text-sm);font-weight:700;color:var(--accent-hover);margin-bottom:4px}
.cmp-verdict-card .pickname{font-size:var(--text-body);font-weight:700;color:var(--ink-deep);line-height:1.4}
.cmp-verdict-card .pickname a{color:var(--ink-deep);text-decoration:underline;text-underline-offset:2px}
.cmp-verdict-card .why{font-size:var(--text-xs);color:var(--gray-600);margin-top:3px;line-height:1.5}
"""


def main() -> int:
    rows = load_rows()
    indexable = [r for r in rows
                 if r["is_bucket"] == "0" and r["is_duplicate"] == "0"
                 and r["scope"] == "domestic"]

    # 詳細→比較ページの相互リンク用グローバルを設定
    NAME_BY_SLUG.update({r["slug"]: r["name"] for r in rows})
    INDEXABLE_SLUGS.update(r["slug"] for r in indexable if is_indexable_detail(r))
    # 総合難易度ランキング（合格率・学習時間ベース）を算出
    build_difficulty_rank(indexable)

    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "c").mkdir(parents=True)
    (SITE / "data").mkdir()
    (SITE / "assets").mkdir()

    # JSON（検索＋比較用。比較で使う事実値＋目的別検索のタグ等も含める）
    def _diff_label(r):
        d = difficulty(r)
        return d[0] if d else ""
    # 「定番」マーク: 受験者数の多い上位80件（一覧で目印として表示）
    _pop_ranked = sorted((r for r in indexable if applicants_num(r) is not None),
                         key=lambda r: -(applicants_num(r) or 0))
    POPULAR_SET = set(r["slug"] for r in _pop_ranked[:80])
    payload = [{
        "popular": (r["slug"] in POPULAR_SET),
        "slug": r["slug"], "name": r["name"], "major": r["major_category"],
        "category": r["category"], "type": r["type"],
        "authority": r["authority"], "official_url": r["official_url"],
        "eligibility": r["eligibility"], "exam_format": r["exam_format"],
        "fee": r["fee"], "pass_rate": r["pass_rate"], "frequency": r["frequency"],
        "status": r.get("status", ""),
        "tags": cert_tags(r),
        "industries": industry_tags(r),
        "difficulty": _diff_label(r),
        "applicants": (EXAM.get(r["slug"], {}) or {}).get("applicants", ""),
        "study_hours": (STUDY.get(r["slug"], {}) or {}).get("study_hours", ""),
    } for r in indexable]
    payload.sort(key=lambda x: (x["major"], x["category"], x["name"]))
    (SITE / "data" / "certifications.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    (SITE / "assets" / "app.css").write_text(APP_CSS, encoding="utf-8")
    (SITE / "assets" / "search.js").write_text(SEARCH_JS, encoding="utf-8")
    (SITE / "assets" / "compare.js").write_text(COMPARE_JS, encoding="utf-8")
    (SITE / "assets" / "compare-bar.js").write_text(COMPARE_BAR_JS, encoding="utf-8")
    for name in ("favicon.svg", "favicon.ico", "favicon-16.png", "favicon-32.png", "apple-touch-icon.png"):
        src = BRAND / name
        if src.exists():
            shutil.copy2(src, SITE / "assets" / name)
    if (BRAND / "favicon.ico").exists():
        shutil.copy2(BRAND / "favicon.ico", SITE / "favicon.ico")
    (SITE / "index.html").write_text(build_index(indexable), encoding="utf-8")
    (SITE / "compare.html").write_text(build_compare(), encoding="utf-8")

    for r in indexable:
        (SITE / "c" / f'{r["slug"]}.html').write_text(build_detail(r), encoding="utf-8")

    # 集約: 分野別一覧
    (SITE / "bunya").mkdir()
    cat_pages = build_category_pages(indexable)
    for slug, htmlc in cat_pages.items():
        (SITE / "bunya" / f"{slug}.html").write_text(htmlc, encoding="utf-8")

    # 特集
    (SITE / "feature").mkdir()
    feat_pages = build_feature_pages(indexable)
    for slug, htmlc in feat_pages.items():
        (SITE / "feature" / f"{slug}.html").write_text(htmlc, encoding="utf-8")

    # 比較（人気ペア）
    (SITE / "vs").mkdir()
    vs_pages = build_comparison_pages(indexable)
    for slug, htmlc in vs_pages.items():
        (SITE / "vs" / f"{slug}.html").write_text(htmlc, encoding="utf-8")

    # 職種DB（職種ページ＋「活かせる仕事」からの逆引きインデックス）
    occ_index_items = []
    if OCC:
        (SITE / "shoku").mkdir()
        occ_pages, occ_index_html, occ_index_items = build_occupation_pages(indexable)
        for oid, htmlc in occ_pages.items():
            (SITE / "shoku" / f"{oid}.html").write_text(htmlc, encoding="utf-8")
        (SITE / "shoku" / "index.html").write_text(occ_index_html, encoding="utf-8")
        # 職種の検索用JSON（全職種。索引ページのクライアント検索・分野フィルタで使用）
        occ_payload = sorted(
            ({"id": oid, "n": info["name"], "m": info["major_category"],
              "c": info["cert_count"]} for oid, info in OCC.items()),
            key=lambda x: (-x["c"], x["n"]))
        (SITE / "data" / "occupations.json").write_text(
            json.dumps(occ_payload, ensure_ascii=False), encoding="utf-8")
        (SITE / "assets" / "occ-search.js").write_text(OCC_SEARCH_JS, encoding="utf-8")

    # sitemap.xml（index対象 = トップ・比較・分野別・特集・インデックス対象の詳細のみ）
    # noindex のページは sitemap に入れない（インデックス衛生・整合性）。
    from datetime import date
    today = date.today().isoformat()
    # (path, lastmod, priority)
    entries = [("", today, "1.0"), ("compare.html", today, "0.7"),
               ("about.html", today, "0.5")]
    entries += [(f"bunya/{s}.html", today, "0.8") for s in cat_pages]
    entries += [(f"feature/{s}.html", today, "0.8") for s in feat_pages]
    entries += [(f"vs/{s}.html", today, "0.7") for s in vs_pages]
    if OCC:
        entries.append(("shoku/index.html", today, "0.7"))
        entries += [(f"shoku/{oid}.html", today, "0.6")
                    for oid, _, _, _ in occ_index_items]
    idx_details = [r for r in indexable if is_indexable_detail(r)]
    entries += [(f'c/{r["slug"]}.html',
                 (r.get("source_checked_at") or today), "0.6") for r in idx_details]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, lm, pr in entries:
        loc = esc(BASE_URL + "/" + u)
        sm.append(f"<url><loc>{loc}</loc><lastmod>{esc(lm)}</lastmod>"
                  f"<priority>{pr}</priority></url>")
    sm.append("</urlset>")
    (SITE / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")
    (SITE / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n", encoding="utf-8")

    # GitHub Pages 独自ドメイン（毎回 site/ を作り直すため、ビルドで必ず出力）
    if CUSTOM_DOMAIN:
        (SITE / "CNAME").write_text(CUSTOM_DOMAIN + "\n", encoding="utf-8")

    # サイトについて・編集方針（E-E-A-T: 出典・信頼性の明示）
    _n_total = len(indexable)
    _n_checked = sum(1 for r in indexable if (r.get("source_checked_at") or "").strip())
    about_body = f"""<nav class="crumbs"><a href="index.html">トップ</a> › サイトについて</nav>
<h1>サイトについて・編集方針</h1>
<p class="lead">{esc(SITE_NAME)}は、日本国内の資格を「探せる・絞れる・比べられる」ことを目的に、
各資格の<strong>公式の一次情報</strong>に基づいて情報を整理・掲載する資格情報サイトです。
就職・転職・スキルアップに役立つ資格選びを支援します。</p>

<section class="detail-spec"><h2 class="detail-section-title">掲載範囲</h2>
<p>国内の資格 <strong>{_n_total}件</strong> を収録し、各資格について受験料・受験資格・試験形式・
合格率・実施頻度・実施団体・公式サイトを掲載しています。資格は国家・公的・民間・要確認に区分し、
区分の判定基準は編集方針として明文化しています。</p></section>

<section class="detail-spec"><h2 class="detail-section-title">編集方針・情報源</h2>
<ul class="point-list">
<li>掲載値は各資格の<strong>実施団体公式・所管省庁などの一次情報</strong>に基づいて整備しています。</li>
<li>各詳細ページに<strong>最終確認日</strong>と<strong>情報源</strong>を表示し、確認状況を追跡できるようにしています（確認済み {_n_checked}/{_n_total}件）。</li>
<li>一次情報で確認できない項目は推測で埋めず、「公式で確認」と表示しています。</li>
<li>資格名・区分は厚生労働省 ハローワーク「免許・資格コード一覧」を出発点に、各実施団体の公式情報で精査しています。</li>
<li>学習時間・難易度・総合スコアは編集部による<strong>目安</strong>であり、公式の数値ではありません。</li>
</ul></section>

<section class="detail-spec"><h2 class="detail-section-title">ご利用にあたっての注意</h2>
<p>制度・受験料・日程・合格率は改定されることがあります。掲載内容は参考情報であり、
出願・受験の前には必ず各資格の<strong>公式サイトで最新情報をご確認</strong>ください。
本サイトの情報の利用により生じたいかなる損害についても責任を負いかねます。</p></section>

<section class="detail-spec"><h2 class="detail-section-title">運営者の資格対策サイト</h2>
<p>当サイトの運営者は、個別資格の学習・対策に特化した以下のサイトも制作・運営しています。
各資格の試験対策には、あわせてご活用ください。</p>
<div class="partner-grid">{partner_cards_html()}</div></section>

<aside class="detail-source"><p class="detail-source-note">
一覧データ出典: 厚生労働省 ハローワーク「免許・資格コード一覧」ほか、各資格の公式の一次情報。
関連: 厚生労働省 職業情報提供サイト（job tag）等。</p></aside>"""
    about_ld = {"@context": "https://schema.org", "@type": "AboutPage",
                "name": f"サイトについて・編集方針｜{SITE_NAME}",
                "url": BASE_URL + "/about.html",
                "publisher": {"@type": "Organization", "name": SITE_NAME,
                              "url": BASE_URL + "/"}}
    (SITE / "about.html").write_text(
        page_shell(f"サイトについて・編集方針｜{SITE_NAME}", about_body, depth=0,
                   noindex=False,
                   desc=f"{SITE_NAME}の編集方針・情報源・免責。各資格の公式の一次情報に基づき"
                        f"国内の資格{_n_total}件を整理。最終確認日と情報源を明示しています。",
                   path="about.html", jsonld=about_ld),
        encoding="utf-8")

    # カスタム 404（GitHub Pages が未検出時に配信）
    _nf_pop = "".join(
        f'<li><a href="/c/{r["slug"]}.html">'
        f'{esc(re.sub(r"[（(].*?[）)]", "", r["name"]).strip() or r["name"])}</a></li>'
        for r in _pop_ranked[:8])
    nf_body = (
        '<h1>ページが見つかりません（404）</h1>'
        '<p class="lead">お探しのページは移動または削除された可能性があります。'
        '資格名で検索するか、人気の資格・分野からお探しください。</p>'
        '<form class="hero-search" action="/index.html" method="get" style="max-width:480px;margin-bottom:8px">'
        '<span class="ico"><svg class="ico-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.75" stroke-linecap="round" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/>'
        '<path d="M15.5 15.5L21 21"/></svg></span>'
        '<input type="search" name="q" placeholder="資格名で検索（例: 簿記, 宅建）" aria-label="資格名で検索">'
        '</form>'
        '<section class="block block-secondary" style="margin-top:22px">'
        '<div class="block-head"><h2>人気の資格</h2></div>'
        f'<ul class="feat-list">{_nf_pop}</ul></section>'
        '<p><a href="/">▶ トップページへ</a>　・　<a href="/index.html#fields">分野から探す</a>'
        '　・　<a href="/shoku/index.html">職種から探す</a></p>')
    (SITE / "404.html").write_text(
        page_shell(f"404 ページが見つかりません｜{SITE_NAME}", nf_body, depth=0,
                   noindex=True, desc="ページが見つかりません。", path="404.html"),
        encoding="utf-8")

    print(f"built site at {SITE.relative_to(ROOT)}")
    print(f"  index + {len(indexable)} detail pages")
    print(f"  sitemap urls: {len(entries)} (index対象詳細: {len(idx_details)})")
    print(f"  分野別一覧: {len(cat_pages)}  特集: {len(feat_pages)}")
    if OCC:
        print(f"  職種ページ: {len(OCC)}（うちindex対象 {len(occ_index_items)}）")
    print(f"  excluded: bucket/duplicate/overseas = {len(rows)-len(indexable)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
