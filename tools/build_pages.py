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


def type_reason_note(cert_type, badge_label, reason):
    """バッジと重複する接頭辞を除き、補足理由だけを返す。"""
    if not reason:
        return ""
    r = reason.strip()
    prefixes = (
        badge_label,
        f"{cert_type}資格",
        cert_type,
        "民間資格",
        "国家資格",
        "公的資格",
        "区分要確認",
    )
    for prefix in prefixes:
        if r.startswith(prefix):
            r = r[len(prefix):].strip()
            break
    if r.startswith("(") and r.endswith(")"):
        r = r[1:-1].strip()
    if not r or r in {badge_label, cert_type, f"{cert_type}資格"}:
        return ""
    return f' <span class="muted">（{esc(r)}）</span>'


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
    """関連資格・ロードマップ用の短縮名。級・種別など識別に必要な括弧書きは残す。"""
    n = NAME_BY_SLUG.get(s, s)
    qualifiers = re.findall(r"[（(]([^）)]+)[）)]", n)
    base = re.sub(r"[（(][^）)]+[）)]", "", n).strip() or n
    for q in reversed(qualifiers):
        q = q.strip()
        if not q or len(q) > 14:
            continue
        if re.search(r"旧|廃止|所管|法律|国家資格|検定の|誰でも|一次情報", q):
            continue
        if re.search(r"種|級|類|号|部門|上級|中級|下級|全経|日商", q):
            return f"{base}({q})"
    return base


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
    for i, s in enumerate(chain, 1):
        num = f'<span class="rm-num">{i}</span>'
        if s == slug:
            steps.append(f'<li class="rm-step rm-cur">{num}'
                         f'<span class="rm-name">{esc(_rel_name(s))}</span>'
                         f'<span class="rm-badge">いま見ている資格</span></li>')
        else:
            steps.append(f'<li class="rm-step">{num}'
                         f'<a class="rm-name" href="{esc(s)}.html">{esc(_rel_name(s))}</a></li>')
    return ('<div class="roadmap"><h3>取得ロードマップ</h3>'
            '<ol class="rm-track">' + "".join(steps) + "</ol></div>")


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


def _detail_link_item(slug, note=""):
    desc = f'<span class="detail-link-desc">{esc(note)}</span>' if note else ""
    return (f'<li class="detail-link-item"><a href="{esc(slug)}.html">'
            f'{esc(_rel_name(slug))}</a>{desc}</li>')


def detail_nav_html(slug, cat, rel_links, vs_pairs):
    """UI spec v2.8: detail-nav（ステップアップ + ほかの資格を見る）。"""
    rel = CERT_RELATIONS.get(slug)
    subs = []
    if rel:
        chain = step_up_chain(slug)
        chain_set = set(chain)
        branch_up = [(s, n) for s, n in rel["up"] if s not in chain_set]
        branch_down = [(s, n) for s, n in rel["down"] if s not in chain_set]
        if branch_up:
            subs.append(
                '<h3 class="detail-nav-subhead">そのほか上位として目指せる資格</h3>'
                '<ul class="detail-link-list">'
                + "".join(_detail_link_item(s, n) for s, n in branch_up)
                + "</ul>")
        if branch_down:
            subs.append(
                '<h3 class="detail-nav-subhead">そのほか前段階となる資格</h3>'
                '<ul class="detail-link-list">'
                + "".join(_detail_link_item(s, n) for s, n in branch_down)
                + "</ul>")
        if rel["exempt_to"] or rel["exempt_from"]:
            items = rel["exempt_to"] + rel["exempt_from"]
            subs.append(
                '<h3 class="detail-nav-subhead">試験の免除・受験資格の優遇</h3>'
                '<ul class="detail-link-list">'
                + "".join(_detail_link_item(s, n) for s, n in items)
                + "</ul>")
        if rel["combo"]:
            subs.append(
                '<h3 class="detail-nav-subhead detail-nav-subhead-title">あわせて取りたい資格</h3>'
                '<ul class="detail-link-list">'
                + "".join(_detail_link_item(s, n) for s, n in rel["combo"])
                + "</ul>")

    compare_row = ""
    if vs_pairs:
        links = "".join(
            f'<a href="../vs/{esc(ps)}.html">{esc(on)}との違い</a>'
            for ps, on in vs_pairs[:5])
        compare_row = (
            '<h3 class="detail-nav-subhead detail-nav-subhead-title">よく比較される資格</h3>'
            f'<div class="detail-compare-row">{links}</div>')
        subs.append(compare_row)

    block1 = ""
    if subs:
        note = ('<p class="detail-nav-note">※免除・受験資格の要件は変更されることがあります。'
                '出願前に必ず各資格の公式情報でご確認ください。</p>' if rel else "")
        block1 = (
            '<div class="detail-nav-block">'
            + "".join(subs)
            + note
            + '</div>')

    more_grid = (
        '<h3 class="detail-nav-subhead">もっと探す</h3>'
        '<ul class="detail-link-grid">'
        + "".join(
            f'<li class="detail-link-item"><a href="{u}">{esc(t)}</a></li>'
            for u, t in rel_links)
        + "</ul>")

    related_js = f"""<script>
fetch("../data/certifications.json").then(r=>r.json()).then(all=>{{
  const cat={json.dumps(cat, ensure_ascii=False)}, me={json.dumps(slug, ensure_ascii=False)};
  const ul=document.getElementById("relatedGrid");
  all.filter(x=>x.category===cat&&x.slug!==me).slice(0,8).forEach(x=>{{
    const li=document.createElement("li");
    li.className="detail-link-item";
    li.innerHTML='<a href="'+x.slug+'.html">'+x.name+'</a>';
    ul.appendChild(li);
  }});
  if(!ul.children.length) ul.innerHTML='<li class="detail-link-item muted">なし</li>';
}});
</script>"""

    block2 = (
        '<div class="detail-nav-block">'
        '<h2 class="detail-nav-head">ほかの資格を見る・比較する</h2>'
        '<h3 class="detail-nav-subhead">同じ分野の他の資格</h3>'
        '<ul class="detail-link-grid" id="relatedGrid"></ul>'
        + more_grid
        + '</div>'
        + related_js)

    return f'<nav class="detail-nav" aria-label="関連する資格への導線">{block1}{block2}</nav>'


def materials_cell_html(slug):
    """おすすめ教材・講座（表セル用）。教材が無ければ空文字。"""
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
        note = f' <span class="note-muted">— {esc(m["note"])}</span>' if m["note"] else ""
        items.append(f'<li><span class="mat-kind">{esc(m["kind"])}</span> '
                     f'{title_html}{prov}{note}</li>')
    disclosure = (
        '<p class="ad-disclosure">本セクションには広告（アフィリエイトリンク）を含みます。'
        'リンクを経由して購入・申込みされた場合、当サイトが収益を得ることがあります。'
        '掲載は編集部の選定によるもので、内容の正確性・価格は各提供元の公式情報をご確認ください。</p>'
        if has_aff else "")
    return (
        f'{disclosure}'
        f'<ul class="materials">{"".join(items)}</ul>'
        '<p class="muted mat-foot">編集部が選んだ学習教材・講座の例です。最新の価格・改訂版・'
        '開講状況は各販売元・提供元の公式情報で必ずご確認ください。</p>')


def materials_section_html(slug):
    """おすすめ教材・講座セクション（後方互換）。"""
    cell = materials_cell_html(slug)
    if not cell:
        return ""
    has_aff = any(m["affiliate"] for m in (MATERIALS.get(slug) or []))
    pr = '<span class="pr-badge">PR</span>' if has_aff else ""
    return (
        f'<section class="materials-sec"><h2 class="detail-section-title">おすすめテキスト・講座{pr}</h2>'
        f'{cell}</section>')


def applicants_num(r):
    """受験者数の文字列から代表数（最初の「N人/N名」）を整数で。なければ None。"""
    ed = EXAM.get(r.get("slug", ""))
    if not ed or not ed.get("applicants"):
        return None
    m = re.search(r"([0-9][0-9,]*)\s*[人名]", ed["applicants"])
    return int(m.group(1).replace(",", "")) if m else None


def popular_slug_set(rows, limit=80):
    """受験者数の多い上位資格の slug 集合（一覧の人気マーク用）。"""
    ranked = sorted((r for r in rows if applicants_num(r) is not None),
                    key=lambda r: (-(applicants_num(r) or 0), r["name"]))
    return {r["slug"] for r in ranked[:limit]}


def fmt_nums_in_text(s: str) -> str:
    """文字列内の4桁以上の整数に3桁カンマを付与（小数部・年数は除外）。"""
    if not s:
        return s

    def repl(m: re.Match[str]) -> str:
        n = m.group(0)
        if len(n) < 4:
            return n
        start, end = m.start(), m.end()
        if start > 0 and s[start - 1] == ".":
            return n
        if end < len(s) and s[end] == "年":
            return n
        return f"{int(n):,}"

    return re.sub(r"\d+", repl, s)


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
<meta name="theme-color" content="#ffffff">
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
    <div class="header-brand"><a class="logo" href="{base}index.html" aria-label="{esc(SITE_NAME)}、トップへ"><span class="logo-mark" aria-hidden="true"><span class="logo-mark-line">資格</span><span class="logo-mark-line logo-mark-line--sub">マスター</span></span><span class="logo-stack"><span class="logo-text">{esc(SITE_NAME)}</span><span class="logo-sub">国内最大級の資格情報サイト</span></span></a></div>
    <nav class="header-nav" aria-label="サイトメニュー">
      <a href="{base}index.html#purpose">目的から探す</a><span class="header-nav-sep" aria-hidden="true">｜</span>
      <a href="{base}index.html#fields">分野から探す</a><span class="header-nav-sep" aria-hidden="true">｜</span>
      <a href="{base}index.html#all-certs">資格一覧</a><span class="header-nav-sep" aria-hidden="true">｜</span>
      <a href="{base}compare.html">比較</a>
      <a href="{base}index.html#partners" class="header-nav-cta">資格対策サイト</a>
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
    <a href="{base}index.html#all-certs">資格一覧</a>
    <a href="{base}compare.html">比較</a>
    <a href="{base}shoku/index.html">職種から探す</a>
    <a href="{base}feature/index.html">特集・ランキング</a>
    <a href="{base}index.html#partners">資格対策サイト</a>
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
      <a href="{base}index.html#compare">よく比較される資格</a>
      <a href="{base}about.html">サイトについて・編集方針</a>
    </nav>
    <p class="site-footer-copy">© {esc(SITE_NAME)}／一覧データ出典: 厚生労働省 ハローワーク「免許・資格コード一覧」ほか、各資格の公式の一次情報に基づき整備。</p>
  </div>
</footer>
<script>(function(){{var h=document.getElementById('siteHeader');if(!h)return;function close(){{h.classList.remove('site-header--search-open','site-header--menu-open');h.querySelectorAll('[data-toggle]').forEach(function(b){{b.setAttribute('aria-expanded','false');}});}}h.querySelectorAll('[data-toggle]').forEach(function(b){{b.addEventListener('click',function(){{var k=b.getAttribute('data-toggle');var cls=k==='search'?'site-header--search-open':'site-header--menu-open';var open=h.classList.contains(cls);close();if(!open){{h.classList.add(cls);b.setAttribute('aria-expanded','true');var p=document.getElementById(k==='search'?'hSearch':'hMenu');if(p){{p.hidden=false;var inp=p.querySelector('input');if(inp)setTimeout(function(){{inp.focus();}},30);}}}}}});}});document.addEventListener('keydown',function(e){{if(e.key==='Escape')close();}});}})();</script>
</body>
</html>
"""


def build_detail(row, popular_slugs=None) -> str:
    name = row["name"]
    label, cls = TYPE_BADGE.get(row["type"], ("区分要確認", "badge-unknown"))
    major = row["major_category"]
    cat = row["category"]

    def field(v, fallback="公式情報で確認"):
        return esc(fmt_nums_in_text(v)) if v else f'<span class="muted">{fallback}</span>'

    official = ""
    if row["official_url"]:
        u = esc(row["official_url"])
        official = f'<a href="{u}" rel="nofollow noopener" target="_blank">公式サイト</a>'
    else:
        official = '<span class="muted">未登録（一次情報で確認予定）</span>'

    spec_basic = [
        ("資格区分", f'<span class="badge {cls}">{esc(label)}</span>'
                    + type_reason_note(row["type"], label, row["type_reason"])),
        ("分野（大分類）", esc(major)),
        ("カテゴリ", esc(cat)),
        ("実施団体", field(row["authority"])),
        ("公式サイト", official),
        ("ハローワークコード", esc(row["hellowork_code"])),
    ]
    spec_exam = [
        ("受験資格", field(row["eligibility"])),
        ("試験形式", field(row["exam_format"])),
        ("受験料", field(row["fee"])),
        ("合格率", field(pass_rate_display(row["pass_rate"]) or row["pass_rate"])),
        ("実施頻度", field(row["frequency"])),
    ]
    ed = EXAM.get(row["slug"], {})
    if ed.get("applicants"):
        spec_exam.append(("受験者数", esc(fmt_nums_in_text(ed["applicants"]))))
    diff = difficulty(row)
    if diff:
        dlabel, dcls = diff
        spec_exam.append(("難易度の目安",
                          esc(dlabel)
                          + f' <span class="note-muted">（公表合格率 {esc(pass_rate_display(row["pass_rate"]))} に基づく簡易目安）</span>'))
    dr = DIFFICULTY_RANK.get(row["slug"])
    if dr:
        rank_parts = [f'掲載資格中 上位{dr["pct"]}%']
        if dr.get("fpct"):
            rank_parts.append(f'{dr["fname"]}分野内 上位{dr["fpct"]}%')
        conf_note = {"高": "高（主要指標2つ以上で算出）",
                     "中": "中（単一指標ベースの参考値）"}.get(dr["conf"], dr["conf"])
        meta = (f'信頼度: {conf_note}／スコア算出{dr["total"]}件中{dr["rank"]}位相当。'
                f'{"・".join(dr["srcs"])}から算出した編集部の総合スコアで、'
                f'難易度の絶対指標ではありません。')
        spec_exam.append(("総合難易度（目安）",
                          esc(" / ".join(rank_parts))
                          + f'<div class="note-muted">{esc(meta)}</div>'))
    if ed.get("exam_subjects"):
        spec_exam.append(("試験科目・出題範囲", esc(ed["exam_subjects"])))
    st = STUDY.get(row["slug"], {})
    if st.get("study_hours"):
        spec_exam.append(("学習時間の目安",
                          esc(fmt_nums_in_text(st["study_hours"]))
                          + ' <span class="note-muted">（編集部調べの目安。個人差があり、公式の数値ではありません）</span>'))

    spec_use = []
    inds = industry_tags(row)
    if inds:
        chips = "".join(
            f'<a class="tag-chip tag-ind" href="../index.html?industry={quote(t)}#all-certs"'
            f' title="「{esc(t)}」で活かせる資格を探す">{esc(t)}</a>' for t in inds)
        spec_use.append(("活かせる業界", chips))
    tags = cert_tags(row)
    if tags:
        chips = "".join(
            f'<a class="tag-chip" href="../index.html?tag={quote(t)}#all-certs"'
            f' title="「{esc(t)}」の資格を探す">{esc(t)}</a>' for t in tags)
        spec_use.append(("特徴・目的タグ", chips))
    src = row.get("source_checked_at", "")

    # この資格のポイント
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
    if pts:
        _lis = "".join(f"<li>{esc(p)}</li>" for p in pts)
        spec_use.append(("この資格のポイント",
                         f'<ul class="spec-list">{_lis}</ul>'))

    # 活かせる仕事・キャリア
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
        careers_cell = f'<ul class="spec-list careers">{"".join(items)}</ul>'
        if cur["source"]:
            careers_cell += (f'<p class="muted careers-src">出典: '
                             f'<a href="{esc(cur["source"])}" rel="nofollow noopener" target="_blank">'
                             f'公式・job tag 等</a>（職種名から各職種ページへ：'
                             f'その職種に活かせる資格を逆引きできます）</p>')
    else:
        careers_cell = (f'<p class="muted">{esc(name)}（{esc(major)}分野）を要件・推奨とする'
                        '職業は個別に精査中です。関連する職業は、厚生労働省の職業情報提供'
                        'サイト（job tag）で資格名から検索できます。</p>')
    careers_cell += (f'<p class="jobtag"><a href="{JOBTAG_URL}" rel="nofollow noopener" '
                     f'target="_blank">厚生労働省 job tag で関連職業を調べる ↗</a></p>')
    spec_use.append(("活かせる仕事・キャリア", careers_cell))

    spec_ref = []
    # おすすめ教材
    _mat_cell = materials_cell_html(row["slug"])
    if _mat_cell:
        _mat_aff = any(m["affiliate"] for m in (MATERIALS.get(row["slug"]) or []))
        _mat_pr = ' <span class="pr-badge">PR</span>' if _mat_aff else ""
        spec_ref.append((f"おすすめテキスト・講座{_mat_pr}", _mat_cell))

    jd = jp_date(src)
    if row["official_url"]:
        u = esc(row["official_url"])
        official_src = f'<a href="{u}" rel="nofollow noopener" target="_blank">公式サイト</a>'
        if row["authority"]:
            official_src += f'（{esc(row["authority"])}）'
    elif row["authority"]:
        official_src = esc(row["authority"])
    else:
        official_src = "各資格の公式情報"
    if jd:
        spec_ref.append(("最終確認日", esc(jd)))
    elif src:
        spec_ref.append(("最終確認日", esc(src)))
    spec_ref.append(("情報源", official_src))
    if row["official_url"]:
        u = esc(row["official_url"])
        spec_ref.append(("最新情報の確認",
                         f'<a href="{u}" rel="nofollow noopener" target="_blank">'
                         f'公式サイトで最新情報を確認 ↗</a>'))
    spec_ref.append(("データの注記",
                     '<p class="detail-source-note">受験料・受験資格・試験形式・合格率・実施団体は公式の一次情報に基づきます。'
                     '学習時間・難易度・総合スコアは編集部による目安で、公式の数値ではありません。'
                     '制度・金額・日程は改定されることがあるため、出願前に必ず公式サイトでご確認ください。</p>'))

    spec_html = spec_sections_html([
        ("基本情報", "spec-basic", spec_basic),
        ("試験・学習", "spec-exam", spec_exam),
        ("活かし方", "spec-use", spec_use),
        ("参考・出典", "spec-ref", spec_ref),
    ], row.get("official_url") or "")

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
        fact.append(f"受験料は{esc(fmt_nums_in_text(row['fee']))}")
    if row["pass_rate"]:
        fact.append(f"合格率は{esc(pass_rate_display(row['pass_rate']))}")
    if row["exam_format"]:
        fact.append(f"試験形式は{esc(row['exam_format'])}")
    if row["frequency"]:
        fact.append(f"実施頻度は{esc(row['frequency'])}")
    fact_p = (f"<p>{name}の概要: " + "、".join(fact)
              + "。最新の金額・日程・合格率は公式サイトで必ずご確認ください。</p>") if fact else ""

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

    vs_pairs = []
    for ps, other in COMPARE_INDEX.get(row["slug"], []):
        if other in INDEXABLE_SLUGS:
            on = re.sub(r"[（(].*?[）)]", "", NAME_BY_SLUG.get(other, other)).strip() or other
            vs_pairs.append((ps, on))

    # FAQ 構造化データ（表示は表に統合、JSON-LD のみ出力）
    qa = []
    if row["fee"]:
        qa.append((f"{name}の受験料はいくらですか？", fmt_nums_in_text(row["fee"])))
    if row["eligibility"]:
        qa.append((f"{name}に受験資格はありますか？", row["eligibility"]))
    if row["exam_format"]:
        qa.append((f"{name}の試験はどのような形式ですか？", row["exam_format"]))
    if row["pass_rate"]:
        qa.append((f"{name}の合格率はどのくらいですか？", pass_rate_display(row["pass_rate"])))
    if ed.get("exam_subjects"):
        qa.append((f"{name}の試験科目・出題範囲は？", ed["exam_subjects"]))
    if ed.get("applicants"):
        qa.append((f"{name}の受験者数はどのくらいですか？", fmt_nums_in_text(ed["applicants"])))
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
                   f"公表合格率（{pass_rate_display(row['pass_rate'])}）に基づく簡易的な目安では「{_dq[0]}」です。"
                   "合格率は受験者層により変わるため、難易度の絶対指標ではありません。"))
    faq = ({"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q,
                            "acceptedAnswer": {"@type": "Answer", "text": a}}
                           for q, a in qa]} if qa else None)

    detail_nav = detail_nav_html(row["slug"], cat, rel, vs_pairs)

    # 「最近見た資格」記録（localStorage）
    _rn = esc(re.sub(r"[（(].*?[）)]", "", name).strip() or name)
    recent_js = ("<script>(function(){try{var k='recent',a=JSON.parse(localStorage.getItem(k)||'[]');"
                 f"a=a.filter(function(x){{return x.s!=='{esc(row['slug'])}';}});"
                 f"a.unshift({{s:'{esc(row['slug'])}',n:'{_rn}'}});a=a.slice(0,8);"
                 "localStorage.setItem(k,JSON.stringify(a));}catch(e){}})();</script>")
    partner_detail = partner_detail_html(row["slug"])
    _rm_chain = step_up_chain(row["slug"])
    _roadmap_block = roadmap_html(row["slug"], _rm_chain)
    if _roadmap_block:
        _roadmap_block = f'<section class="detail-roadmap">{_roadmap_block}</section>'
    body = f"""<div class="page-detail">
<nav class="crumbs"><a href="../index.html">トップ</a> ›
<a href="../bunya/{esc(bslug)}.html">{esc(major)}</a> › {esc(name)}</nav>
{detail_title_html(name, row["slug"], popular_slugs)}
<p class="detail-audience">{lead}</p>
{partner_detail}
{_roadmap_block}
<section class="detail-spec" aria-labelledby="ds-h">
<h2 class="detail-section-title" id="ds-h">資格情報</h2>
<div class="spec-sections">{spec_html}</div>{SPEC_TABLE_JS}</section>
{detail_nav}
{recent_js}
</div>"""
    # meta description は各ページで一意になるよう、必ず固有の資格名で始め、
    # 固有の事実（受験料・合格率・実施団体）を添える（家族で共通の説明文の重複を回避）。
    _short = re.sub(r"[（(].*?[）)]", "", name).strip() or name
    lead_txt = hand_desc or f"{name}は{major}分野の{label}です。"
    if _short not in lead_txt:
        lead_txt = f"{_short}は{label}。" + lead_txt
    _facts = []
    if row["fee"]:
        _facts.append("受験料" + fmt_nums_in_text(row["fee"]))
    if row["pass_rate"]:
        _facts.append("合格率" + pass_rate_display(row["pass_rate"]))
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


def pass_rate_short(val):
    """表示用: 数値と%のみ（年度・回次などの括弧書きは省略）。"""
    if not val:
        return ""
    s = str(val).replace(",", "")
    s = re.sub(r"[（(][^）)]*(?:年度|令和|平成|昭和|第\d+回)[^）)]*[）)]", "", s)
    s = s.strip()
    parts = re.findall(
        r"((?:一次|二次|筆記|口頭|学科|実地|全体|上期|下期)?[0-9]+(?:\.[0-9]+)?%)",
        s)
    if len(parts) > 1:
        return "/".join(parts)
    if parts:
        return parts[0]
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", s)
    return f"{m.group(1)}%" if m else ""


def pass_rate_display(val):
    """合格率の画面表示用文字列（カンマ整形＋年度省略）。"""
    s = pass_rate_short(val)
    return fmt_nums_in_text(s) if s else ""


def spec_row_html(label, value, href=""):
    """資格情報表の1行（クリック・ホバー対応）。"""
    href_attr = f' data-href="{esc(href)}"' if href else ""
    return (
        f'<tr class="spec-row" tabindex="0"{href_attr}>'
        f"<th>{spec_label_html(label)}</th><td>{value}</td></tr>")


_SPEC_LINK_LABELS = frozenset({"公式サイト", "最新情報の確認"})


def spec_table_html(rows, official_url=""):
    """行リストから spec 表の tbody 相当 HTML を生成。"""
    return "".join(
        spec_row_html(
            k, v,
            official_url if k in _SPEC_LINK_LABELS and official_url else "",
        )
        for k, v in rows
    )


def spec_sections_html(section_rows, official_url=""):
    """セクション見出し付きの資格情報表ブロックを生成。"""
    parts = []
    for title, sid, rows in section_rows:
        if not rows:
            continue
        parts.append(
            f'<div class="spec-section" id="{esc(sid)}">'
            f'<h3 class="spec-section-title">{esc(title)}</h3>'
            f'<div class="spec-wrap"><table class="spec">'
            f'<colgroup><col class="spec-col-label"><col class="spec-col-value"></colgroup>'
            f'{spec_table_html(rows, official_url)}'
            f'</table></div></div>'
        )
    return "".join(parts)


SPEC_TABLE_JS = """<script>
(function(){
  document.querySelectorAll(".page-detail table.spec").forEach(function(tbl){
    tbl.querySelectorAll("tr.spec-row").forEach(function(tr){
      tr.addEventListener("click",function(e){
        if(e.target.closest("a"))return;
        var href=tr.getAttribute("data-href");
        if(href){window.open(href,"_blank","noopener");return;}
        tbl.querySelectorAll("tr.spec-row.is-active").forEach(function(r){
          if(r!==tr)r.classList.remove("is-active");
        });
        tr.classList.toggle("is-active");
      });
      tr.addEventListener("keydown",function(e){
        if(e.key==="Enter"||e.key===" "){e.preventDefault();tr.click();}
      });
    });
  });
})();
</script>"""


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
            bits = [b for b in (fmt_nums_in_text(r.get("fee") or ""),
                                (("合格率" + pass_rate_display(r["pass_rate"])) if r.get("pass_rate") else "")) if b]
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


_CERTS_TABLE_SCRIPT = """<script>
(function(){
  document.querySelectorAll('.all-certs-table tbody').forEach(function(tb){
    function go(tr){var h=tr.getAttribute('data-href');if(h)location.href=h;}
    tb.addEventListener('click',function(e){var tr=e.target.closest('tr.cert-row');if(tr)go(tr);});
    tb.addEventListener('keydown',function(e){
      if(e.key!=='Enter'&&e.key!==' ')return;
      var tr=e.target.closest('tr.cert-row');if(!tr)return;
      e.preventDefault();go(tr);
    });
  });
})();
</script>"""


def _certs_name_cell(r, popular_slugs=None):
    trophy = ""
    if popular_slugs and r["slug"] in popular_slugs:
        trophy = f'<span class="all-certs-trophy" aria-hidden="true">{ICON_TROPHY}</span>'
    return (
        f'<td class="all-certs-name"><span class="all-certs-name-inner">'
        f'{trophy}<span class="all-certs-name-text">{esc(r["name"])}</span></span></td>')


def _all_certs_colgroup(show_major=False):
    cols = ['<col class="all-certs-col-name">']
    if show_major:
        cols.append('<col class="all-certs-col-major">')
    cols.extend([
        '<col class="all-certs-col-study">',
        '<col class="all-certs-col-pass">',
        '<col class="all-certs-col-freq">',
    ])
    return "".join(cols)


def _certs_table(items, depth=1, *, show_major=False,
                 with_script=True, popular_slugs=None):
    """資格一覧の表形式HTML（分野・目的別ガイドなどで共用）。"""
    base = "../" * depth
    col_mod = "all-certs-table--5col" if show_major else "all-certs-table--4col"
    headers = ['<th scope="col">資格名</th>']
    if show_major:
        headers.append('<th scope="col">分野</th>')
    headers.extend([
        '<th scope="col">学習時間</th>',
        '<th scope="col">合格率</th>',
        '<th scope="col">実施頻度</th>',
    ])
    rows = []
    for r in items:
        pr = pass_rate_display(r.get("pass_rate", "")) or "—"
        study = fmt_nums_in_text((STUDY.get(r["slug"], {}) or {}).get("study_hours", "")) or "—"
        freq_raw = (r.get("frequency") or "").strip()
        freq = esc(freq_raw) if freq_raw else "—"
        cells = [_certs_name_cell(r, popular_slugs)]
        if show_major:
            cells.append(
                f'<td class="all-certs-cell">{esc(r["major_category"])}</td>')
        cells.extend([
            f'<td class="all-certs-cell all-certs-num">{esc(study)}</td>',
            f'<td class="all-certs-cell all-certs-num">{esc(pr)}</td>',
            f'<td class="all-certs-cell all-certs-cell--freq">{freq}</td>',
        ])
        rows.append(
            f'<tr class="cert-row" tabindex="0" data-href="{base}c/{esc(r["slug"])}.html">'
            + "".join(cells) + "</tr>")
    table = (
        '<div class="all-certs-table-wrap">'
        f'<table class="all-certs-table {col_mod}">'
        f'<colgroup>{_all_certs_colgroup(show_major)}</colgroup>'
        f'<thead><tr>{"".join(headers)}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>')
    return table + (_CERTS_TABLE_SCRIPT if with_script else "")


def _category_table(items, depth=1, popular_slugs=None):
    """分野別一覧ページ用の表形式HTML（トップの資格一覧と同じ列構成）。"""
    return _certs_table(items, depth, show_major=True, popular_slugs=popular_slugs)


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

_SVG = ('<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>')

def _icon_svg(paths):
    return _SVG.format(paths)

ICON_TROPHY = _icon_svg(
    '<path d="M8 21h8"/><path d="M12 17v4"/>'
    '<path d="M7 4h10v5a5 5 0 0 1-10 0V4z"/>'
    '<path d="M5 5H3v2a3 3 0 0 0 3 3"/>'
    '<path d="M19 5h2v2a3 3 0 0 1-3 3"/>')


def detail_title_html(name, slug, popular_slugs=None):
    """詳細ページ h1。人気資格（受験者数上位）にはトロフィーを付ける。"""
    text = esc(name)
    if popular_slugs and slug in popular_slugs:
        return (
            f'<h1 class="detail-title">'
            f'<span class="detail-title-inner">'
            f'<span class="detail-title-trophy" aria-hidden="true">{ICON_TROPHY}</span>'
            f'<span>{text}</span></span></h1>'
        )
    return f'<h1 class="detail-title">{text}</h1>'

FIELD_ICONS = {
    "IT・情報処理": _icon_svg(
        '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>'),
    "法律・法務・知財": _icon_svg(
        '<path d="M12 3v18"/><path d="M5 7h14"/>'
        '<path d="M7 10l-2 7h4l-2-7z"/><path d="M17 10l-2 7h4l-2-7z"/>'),
    "会計・金融・経営": _icon_svg(
        '<rect x="4" y="2" width="16" height="20" rx="2"/>'
        '<path d="M8 6h8M8 10h2M12 10h2M8 14h2M12 14h2M8 18h8"/>'),
    "不動産": _icon_svg(
        '<path d="M3 10.5L12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>'),
    "建築・設備": _icon_svg(
        '<path d="M3 21h18"/><path d="M5 21V9l7-5 7 5v12"/>'
        '<path d="M9 21v-6h6v6"/>'),
    "設備・プラント・機械運転": _icon_svg(
        '<path d="M12 2v4"/><path d="M12 18v4"/>'
        '<path d="M4.93 4.93l2.83 2.83"/><path d="M16.24 16.24l2.83 2.83"/>'
        '<path d="M2 12h4"/><path d="M18 12h4"/>'
        '<path d="M4.93 19.07l2.83-2.83"/><path d="M16.24 7.76l2.83-2.83"/>'
        '<circle cx="12" cy="12" r="3"/>'),
    "土木・測量・建設": _icon_svg(
        '<path d="M2 20h20"/><path d="M6 20V8l6-4 6 4v12"/>'
        '<path d="M10 12h4"/><path d="M12 10v4"/>'),
    "電気・通信": _icon_svg('<path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>'),
    "機械・電気・ものづくり": _icon_svg(
        '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>'),
    "食品・調理・栄養": _icon_svg(
        '<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/>'
        '<path d="M7 2v20"/><path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3z"/>'),
    "医療・看護・薬": _icon_svg(
        '<path d="M12 8v8"/><path d="M8 12h8"/>'
        '<circle cx="12" cy="12" r="9"/>'),
    "福祉・介護・心理": _icon_svg(
        '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>'),
    "教育・保育・学術": _icon_svg(
        '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>'
        '<path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>'),
    "語学・コミュニケーション": _icon_svg(
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'),
    "デザイン・美術・文化": _icon_svg(
        '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z"/>'
        '<path d="M12 2a10 10 0 0 1 0 20"/><path d="M2 12h20"/>'),
    "美容・サービス・スポーツ": _icon_svg(
        '<circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/>'
        '<path d="M9 6h6"/><path d="M6 9v3a6 6 0 0 0 12 0V9"/>'),
    "商業・販売・事務": _icon_svg(
        '<rect x="2" y="7" width="20" height="14" rx="2"/>'
        '<path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>'),
    "安全・環境・危険物": _icon_svg(
        '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'),
    "運輸・運転・航空": _icon_svg(
        '<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/>'
        '<path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/>'
        '<circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/>'),
    "農林水産・動物": _icon_svg(
        '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10z"/>'
        '<path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>'),
    "海外資格": _icon_svg(
        '<path d="M17.8 19.2L16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H8l-1 1 1 1h1l5-2 3.2 3.2c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>'),
}

_FIELD_ICON_DEFAULT = _icon_svg(
    '<path d="M4 7a2 2 0 0 1 2-2h3l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/>')


def field_icon(major):
    return FIELD_ICONS.get(major, _FIELD_ICON_DEFAULT)


SPEC_ICONS = {
    "資格区分": _icon_svg('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'),
    "分野（大分類）": _icon_svg(
        '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>'
        '<rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>'),
    "カテゴリ": _icon_svg(
        '<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>'
        '<circle cx="7" cy="7" r="1.5"/>'),
    "実施団体": _icon_svg(
        '<path d="M3 21h18"/><path d="M5 21V7l7-4 7 4v14"/>'
        '<path d="M9 21v-6h6v6"/>'),
    "公式サイト": _icon_svg(
        '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
        '<path d="M15 3h6v6"/><path d="M10 14L21 3"/>'),
    "受験資格": _icon_svg(
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>'
        '<circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/>'
        '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),
    "試験形式": _icon_svg(
        '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>'),
    "受験料": _icon_svg(
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M8.5 7.5h7M8.5 11h5.5M10 15c1.2 1 2.5 1.5 4 1.5s2.8-.5 4-1.5"/>'),
    "合格率": _icon_svg(
        '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>'),
    "実施頻度": _icon_svg(
        '<rect x="3" y="4" width="18" height="18" rx="2"/>'
        '<path d="M16 2v4M8 2v4M3 10h18"/>'),
    "ハローワークコード": _icon_svg('<path d="M4 9h16M4 15h16"/>'),
    "受験者数": _icon_svg(
        '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
        '<circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/>'
        '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),
    "難易度の目安": _icon_svg(
        '<path d="M3 3v18h18"/><path d="M7 16l4-5 4 3 5-7"/>'),
    "総合難易度（目安）": _icon_svg('<path d="M3 3v18h18"/><path d="M7 14l3-3 3 2 5-6"/>'),
    "試験科目・出題範囲": _icon_svg(
        '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>'
        '<path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>'),
    "学習時間の目安": _icon_svg('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
    "活かせる業界": _icon_svg(
        '<rect x="2" y="7" width="20" height="14" rx="2"/>'
        '<path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>'),
    "特徴・目的タグ": _icon_svg(
        '<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>'
        '<circle cx="7" cy="7" r="1.5"/>'),
    "この資格のポイント": _icon_svg(
        '<path d="M9 18h6"/><path d="M10 22h4"/>'
        '<path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z"/>'),
    "活かせる仕事・キャリア": _icon_svg(
        '<rect x="2" y="7" width="20" height="14" rx="2"/>'
        '<path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>'),
    "おすすめテキスト・講座": _icon_svg(
        '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>'
        '<path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>'),
    "最終確認日": _icon_svg(
        '<rect x="3" y="4" width="18" height="18" rx="2"/>'
        '<path d="M16 2v4M8 2v4M3 10h18"/><path d="M9 16l2 2 4-4"/>'),
    "情報源": _icon_svg('<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
                      '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>'),
    "最新情報の確認": _icon_svg(
        '<path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>'),
    "データの注記": _icon_svg(
        '<circle cx="12" cy="12" r="9"/><path d="M12 8v4"/><path d="M12 16h.01"/>'),
}


def _spec_label_key(label):
    """PRバッジ等のHTML付きラベルから照合用の純テキストを取り出す。"""
    return re.sub(r"<.*", "", label, flags=re.DOTALL).strip()


def spec_label_html(label):
    key = _spec_label_key(label)
    suffix = label[len(key):] if len(label) > len(key) else ""
    text = esc(key) + suffix
    icon = SPEC_ICONS.get(key)
    if not icon:
        return text
    return (
        f'<span class="spec-th-inner">'
        f'<span class="spec-th-icon" aria-hidden="true">{icon}</span>'
        f'<span class="spec-th-text">{text}</span></span>')

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


def build_category_pages(indexable, popular_slugs=None):
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
            f'<div class="page-bunya">'
            f'<nav class="crumbs"><a href="../index.html">トップ</a> › {esc(major)}</nav>'
            f"<h1>{esc(major)}の資格一覧</h1>"
            f'<p class="lead">「{esc(major)}」分野の資格 {len(items)} 件'
            f"（うち公式データ掲載 {npub} 件）。各資格の受験料・試験形式・受験資格・"
            f"合格率・実施団体・公式サイトを詳細ページで確認できます。</p>"
            f'<p class="muted">区分の内訳: {esc(tparts)}。'
            f"主なカテゴリ: {esc('、'.join(cats[:12]))}{'ほか' if len(cats) > 12 else ''}。</p>"
            + _category_table(items, depth=1, popular_slugs=popular_slugs)
            + "</div>"
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


def build_feature_pages(indexable, popular_slugs=None):
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
                            + _certs_table(its, depth=1, with_script=False,
                                           popular_slugs=popular_slugs))
            listing += _CERTS_TABLE_SCRIPT
        else:
            listing = _certs_table(items, depth=1, show_major=True,
                                   popular_slugs=popular_slugs)
        body = (
            f'<div class="page-feature">'
            f'<nav class="crumbs"><a href="../index.html">トップ</a> › ガイド</nav>'
            f"<h1>{esc(h1)}</h1>"
            f'<div class="lead">{intro_html}</div>'
            + listing
            + '<p class="muted" style="margin-top:14px">※掲載は各資格の性質に基づく編集上の選定です。'
              '個々の制度・受験料・合格率・独立開業や就職の条件は、各資格の公式サイトで'
              '必ずご確認ください。</p>'
            + hub_nav(slug)
            + "</div>"
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

    # 特集・ランキングの一覧（ヘッダーから参照する index ページ）
    feat_li = "".join(f'<li><a href="{s}.html">{esc(l)}</a></li>'
                      for s, l in FEATURE_NAV if s in pages)
    hub_li = "".join(f'<li><a href="{s}.html">{esc(l)}</a></li>'
                     for s, l in INTENT_HUB_NAV if s in pages)
    fidx_body = (
        '<nav class="crumbs"><a href="../index.html">トップ</a> › 特集・ランキング</nav>'
        '<h1>特集・ランキングから探す</h1>'
        '<p class="lead">人気・受験料・合格率などの切り口で資格を一覧できる特集・ランキングと、'
        '目的別のガイドをまとめています。</p>'
        f'<h2 class="hub-grp">ランキング・特集</h2><ul class="feat-list">{feat_li}</ul>'
        + (f'<h2 class="hub-grp">目的別ガイド</h2><ul class="feat-list">{hub_li}</ul>'
           if hub_li else ""))
    fidx_ld = {"@context": "https://schema.org", "@type": "BreadcrumbList",
               "itemListElement": [
                   {"@type": "ListItem", "position": 1, "name": "トップ",
                    "item": BASE_URL + "/"},
                   {"@type": "ListItem", "position": 2, "name": "特集・ランキング"}]}
    pages["index"] = page_shell(
        f"特集・ランキングから探す｜{SITE_NAME}", fidx_body, depth=1, noindex=False,
        desc="人気・受験料・合格率などの切り口で資格を一覧できる特集・ランキングと、"
             "目的別ガイドの一覧。",
        path="feature/index.html", jsonld=fidx_ld)

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
        if key == "pass_rate" and v:
            v = pass_rate_display(v) or v
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
        table = (f'<table class="vs-table"><colgroup><col class="vs-col-label">'
                 f'<col class="vs-col-cert"><col class="vs-col-cert"></colgroup>'
                 f'<thead><tr><th></th>'
                 f'<th>{esc(na)}</th><th>{esc(nb)}</th></tr></thead>'
                 f"<tbody>{tbody}</tbody></table>")

        cards = (
            '<div class="vs-cta">'
            f'<a class="btn-official" href="../c/{esc(ra["slug"])}.html">{esc(na)}の詳細</a> '
            f'<a class="btn-official" href="../c/{esc(rb["slug"])}.html">{esc(nb)}の詳細</a>'
            "</div>")

        # 比較 FAQ（違い・難易度）
        qa = [(f"{na}と{nb}の違いは何ですか？",
               re.sub("<[^>]+>", "", intro))]
        if ra.get("pass_rate") and rb.get("pass_rate"):
            qa.append((f"{na}と{nb}はどちらが難しいですか？",
                       f"公表合格率は{na}が{pass_rate_display(ra['pass_rate'])}、{nb}が{pass_rate_display(rb['pass_rate'])}です。"
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
        facts = ""
        d = difficulty(r)
        if d:
            facts += f'<li><span class="k">難易度</span><span class="v">{esc(d[0])}</span></li>'
        sh = (STUDY.get(r["slug"], {}) or {}).get("study_hours", "")
        if sh:
            facts += f'<li><span class="k">学習目安</span><span class="v">{esc(fmt_nums_in_text(sh))}</span></li>'
        pop_html += (f'<a class="pop-card card-link{more}" href="c/{r["slug"]}.html">'
                     f'<div class="pop-card-head">'
                     f'<span class="pop-card-trophy" aria-hidden="true">{ICON_TROPHY}</span>'
                     f'<div class="pop-card-name">{esc(_short(r))}</div></div>'
                     f'<ul class="pop-card-facts">{facts}</ul></a>')

    # --- 分野から探す（収録数の多い順 上位8） ---
    mcount = Counter(r["major_category"] for r in rows)
    by_major = {}
    for r in rows:
        by_major.setdefault(r["major_category"], []).append(r)

    def _examples(m):
        cs = sorted(by_major[m], key=lambda r: -(applicants_num(r) or 0))
        return "・".join(_short(r) for r in cs[:3]) + "など"
    fld_html = ""
    for m in sorted(mcount, key=lambda m: -mcount[m])[:8]:
        fld_html += (f'<a class="field-card" href="bunya/{MAJOR_SLUGS.get(m, "other")}.html">'
                     f'<div class="icon">{field_icon(m)}</div>'
                     f'<div class="field-card-body">'
                     f'<div class="field-card-top"><h3>{esc(m)}</h3>'
                     f'<span class="field-count">{mcount[m]}件</span></div>'
                     f'<p class="field-examples">{esc(_examples(m))}</p></div></a>')

    # --- よく比較される資格（COMPARE_PAIRS 先頭6） ---
    def _cmpname(r):
        return (_short(r).replace("ファイナンシャル・プランニング", "FP")
                .replace("ファイナンシャルプランニング", "FP"))
    cmp_html = ""
    _n = 0
    for pslug, sa, sb, intro in COMPARE_PAIRS:
        ra, rb = by_slug.get(sa), by_slug.get(sb)
        if not (ra and rb and is_indexable_detail(ra) and is_indexable_detail(rb)):
            continue
        cmp_html += (f'<a class="compare-card" href="vs/{pslug}.html">'
                     f'<span class="compare-tag">{esc(ra["major_category"])}</span>'
                     f'<div class="compare-names">{esc(_cmpname(ra))} <em>vs</em> {esc(_cmpname(rb))}</div>'
                     f'<span class="compare-go" aria-hidden="true">→</span></a>')
        _n += 1
        if _n >= 6:
            break

    PURPOSE_ICON_JOB = ('<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                        '<path d="M12 3L2 8l10 5 10-5-10-5z"/><path d="M5 11v5c0 2.5 3.5 5 7 5s7-2.5 7-5v-5"/><path d="M22 8v6"/></svg>')
    PURPOSE_ICON_CHANGE = ('<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                           ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                           '<path d="M4 9h12l-3-3"/><path d="M20 9V5"/><path d="M20 15H8l3 3"/><path d="M4 15v4"/></svg>')
    PURPOSE_ICON_SKILL = ('<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                          ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                          '<path d="M4 18h16"/><path d="M7 15l4-6 3 3 5-7"/></svg>')

    body = f"""<section class="hero">
  <h1><span class="hero-h1-line">就職・転職・スキルアップの</span><span class="hero-h1-line">資格情報サイト</span></h1>
  <p class="hero-sub">日本国内の資格を <strong id="count">{len(rows):,}</strong> 件以上掲載。受験料・受験資格・試験形式・合格率・公式サイトを、公式の一次情報に基づいて整理しています。</p>
  <div class="hero-search">
    <span class="ico"><svg class="ico-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L21 21"/></svg></span>
    <input id="q" type="search" placeholder="資格名で検索（例: 簿記, 宅建, ITパスポート）" aria-label="資格名で検索">
  </div>
  <p class="hero-result" id="heroResult" hidden></p>
</section>

<section class="block block-band block-band--white" id="purpose">
  <div class="block-head"><h2>目的から探す</h2></div>
  <div class="purpose-grid">
    <a class="purpose-card" href="feature/job-hunting.html">
      <div class="icon">{PURPOSE_ICON_JOB}</div>
      <div class="purpose-card-body">
        <h3>就職</h3>
        <p class="purpose-card-for">就活・新卒・第二新卒で、はじめて資格を選ぶ方</p>
      </div>
    </a>
    <a class="purpose-card" href="feature/job-hunting.html">
      <div class="icon">{PURPOSE_ICON_CHANGE}</div>
      <div class="purpose-card-body">
        <h3>転職</h3>
        <p class="purpose-card-for">業界や職種を変えたい社会人向け</p>
      </div>
    </a>
    <a class="purpose-card" href="feature/working-adults.html">
      <div class="icon">{PURPOSE_ICON_SKILL}</div>
      <div class="purpose-card-body">
        <h3>スキルアップ</h3>
        <p class="purpose-card-for">今の仕事に活かせる資格を探す方</p>
      </div>
    </a>
  </div>
</section>

<section class="block block-inset" id="recentBlock" hidden>
  <div class="block-head"><h2>最近見た資格</h2></div>
  <ul class="recent-list" id="recentGrid"></ul>
</section>

<section class="block block-band block-band--gray">
  <div class="block-head"><h2>人気の資格</h2><p>受験者数の多い順</p></div>
  <div class="popular-grid">{pop_html}</div>
  <p class="popular-more"><a href="feature/popular.html">人気資格をすべて見る →</a></p>
</section>

<section class="block block-band block-band--white" id="fields">
  <div class="block-head"><h2>分野から探す</h2></div>
  <div class="field-grid">{fld_html}</div>
  <p class="field-more"><a href="#all-certs">すべての分野・条件で絞り込む →</a></p>
</section>

<section class="block block-band block-band--gray block-compare" id="compare">
  <div class="block-head"><h2>よく比較される資格</h2><p>2つ以上を並べて違いを確認</p></div>
  <div class="compare-grid">{cmp_html}</div>
</section>

<section class="block block-band block-band--white block-all-certs" id="all-certs">
  <div class="block-head"><h2>すべての資格から探す</h2><p>資格名・分野・学習時間・合格率・実施頻度で絞り込み</p></div>
  <div class="all-certs-filters">
    <div class="filter-field"><label for="list-q">資格名</label><input type="search" id="list-q" placeholder="例: 簿記、宅建" aria-label="資格名で絞り込み"></div>
    <div class="filter-field"><label for="major">分野</label><select id="major" aria-label="分野で絞り込み"><option value="">すべて</option></select></div>
    <div class="filter-field"><label for="study">学習時間</label><select id="study" aria-label="学習時間で絞り込み">
      <option value="">すべて</option>
      <option value="0-50">〜50時間</option>
      <option value="50-100">50〜100時間</option>
      <option value="100-300">100〜300時間</option>
      <option value="300-1000">300〜1000時間</option>
      <option value="1000-">1000時間以上</option>
    </select></div>
    <div class="filter-field"><label for="pass">合格率</label><select id="pass" aria-label="合格率で絞り込み">
      <option value="">すべて</option>
      <option value="80-">80%以上</option>
      <option value="60-80">60〜80%</option>
      <option value="40-60">40〜60%</option>
      <option value="20-40">20〜40%</option>
      <option value="0-20">20%未満</option>
      <option value="unknown">データなし</option>
    </select></div>
    <div class="filter-field"><label for="frequency">実施頻度</label><select id="frequency" aria-label="実施頻度で絞り込み">
      <option value="">すべて</option>
      <option value="anytime">通年・随時</option>
      <option value="once">年1回</option>
      <option value="twice">年2回</option>
      <option value="3plus">年3回以上</option>
      <option value="other">その他</option>
      <option value="unknown">データなし</option>
    </select></div>
    <div class="filter-field"><label for="sort">並び順</label><select id="sort" aria-label="並び順">
      <option value="app-desc" selected>受験者数が多い順</option>
      <option value="study-asc">学習時間が短い順</option>
      <option value="study-desc">学習時間が長い順</option>
      <option value="pass-desc">合格率が高い順</option>
      <option value="pass-asc">合格率が低い順</option>
    </select></div>
  </div>
  <label class="all-certs-check"><input type="checkbox" id="f-pub"> データ掲載のみ</label>
  <span class="muted" id="studynote" style="display:none">学習時間は編集部調べの目安（非公式）</span>
  <div class="results-bar"><button type="button" id="clearFilters" class="clear-filters" hidden>× 条件をクリア</button></div>
  <p class="all-certs-count" id="allCertsCount"></p>
  <div class="all-certs-table-wrap">
    <table class="all-certs-table all-certs-table--5col">
      <colgroup><col class="all-certs-col-name"><col class="all-certs-col-major"><col class="all-certs-col-study"><col class="all-certs-col-pass"><col class="all-certs-col-freq"></colgroup>
      <thead>
        <tr>
          <th scope="col">資格名</th>
          <th scope="col">分野</th>
          <th scope="col">学習時間</th>
          <th scope="col">合格率</th>
          <th scope="col">実施頻度</th>
        </tr>
      </thead>
      <tbody id="results"><tr><td colspan="5" class="muted">読み込み中…</td></tr></tbody>
    </table>
  </div>
  <nav class="pagination" id="pagination" aria-label="資格一覧のページ送り" hidden></nav>
</section>

<section class="block block-band block-band--gray" id="partners">
  <div class="block-head"><h2>おすすめの資格対策サイト</h2><p>当サイト運営者が制作している資格別の学習・対策サイト</p></div>
  <div class="partner-grid">{partner_cards_html()}</div>
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
  var q=document.getElementById('q'),listQ=document.getElementById('list-q'),
      majorSel=document.getElementById('major'),sortSel=document.getElementById('sort'),
      studySel=document.getElementById('study'),passSel=document.getElementById('pass'),
      freqSel=document.getElementById('frequency'),
      fPub=document.getElementById('f-pub'),
      studyNote=document.getElementById('studynote'),
      results=document.getElementById('results'),
      countEl=document.getElementById('allCertsCount'),
      pagination=document.getElementById('pagination'),
      count=document.getElementById('count'),
      heroResult=document.getElementById('heroResult'),
      clearBtn=document.getElementById('clearFilters');
  var DATA=[], activeTags=new Set(), currentPage=1, PAGE_SIZE=20, resetPage=true,TROPHY=__TROPHY_HTML__;
  var legacyType='',legacyIndustry='';
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function fmtN(n){return Number(n).toLocaleString('ja-JP');}
  function shortName(n){return (n||'').replace(/[（(][^）)]*[）)]/g,'').trim()||n;}
  function opt(sel,v){var o=document.createElement('option');o.value=v;o.textContent=v;sel.appendChild(o);}
  function passNum(x){var m=(x.pass_rate||'').replace(/,/g,'').match(/([0-9]+(?:\\.[0-9]+)?)\\s*%/);return m?parseFloat(m[1]):null;}
  function studyLow(x){var m=(x.study_hours||'').replace(/,/g,'').match(/([0-9]+)/);return m?parseInt(m[1],10):null;}
  function appNum(x){var m=(x.applicants||'').replace(/,/g,'').match(/([0-9]+)\\s*[人名]/);return m?parseInt(m[1],10):null;}
  function queryText(){return ((q&&q.value)||(listQ&&listQ.value)||'').trim().toLowerCase();}
  function syncQueryInputs(src){
    var v=src?src.value:'';
    if(q&&src!==q)q.value=v;
    if(listQ&&src!==listQ)listQ.value=v;
  }
  function freqBucket(f){
    f=(f||'').trim();
    if(!f)return 'unknown';
    if(/休止/.test(f))return 'other';
    if(/通年|随時|CBT|ネット/i.test(f))return 'anytime';
    if(/年5回|年6回|年複数|年[34]回/.test(f))return '3plus';
    if(/年2回/.test(f))return 'twice';
    if(/年1回/.test(f))return 'once';
    return 'other';
  }
  function passHit(x,band){
    var v=passNum(x);
    if(band==='unknown')return v===null;
    if(v===null)return false;
    if(band==='80-')return v>=80;
    var p=band.split('-'),lo=parseFloat(p[0],10),hi=p[1]===''?Infinity:parseFloat(p[1],10);
    return v>=lo&&v<hi;
  }
  function syncURL(){
    try{
      var p=new URLSearchParams();
      var qt=queryText();
      if(qt)p.set('q',qt);
      if(majorSel.value)p.set('major',majorSel.value);
      if(studySel.value)p.set('study',studySel.value);
      if(passSel&&passSel.value)p.set('pass',passSel.value);
      if(freqSel&&freqSel.value)p.set('frequency',freqSel.value);
      if(sortSel.value&&sortSel.value!=='app-desc')p.set('sort',sortSel.value);
      if(fPub.checked)p.set('pub','1');
      if(activeTags.size)p.set('tag',[].slice.call(activeTags).join(','));
      if(legacyType)p.set('type',legacyType);
      if(legacyIndustry)p.set('industry',legacyIndustry);
      if(currentPage>1)p.set('page',String(currentPage));
      var qs=p.toString();
      history.replaceState(null,'',qs?('?'+qs):location.pathname);
    }catch(e){}
  }
  function studyHit(x,band){
    var v=studyLow(x); if(v===null)return false;
    var p=band.split('-'),lo=parseInt(p[0],10),hi=p[1]===''?Infinity:parseInt(p[1],10);
    return v>=lo&&v<hi;
  }
  function renderPagination(total){
    if(!pagination)return;
    var pages=Math.max(1,Math.ceil(total/PAGE_SIZE));
    if(total<=PAGE_SIZE){pagination.innerHTML='';pagination.hidden=true;return;}
    pagination.hidden=false;
    if(currentPage>pages)currentPage=pages;
    var start=(currentPage-1)*PAGE_SIZE+1;
    var end=Math.min(currentPage*PAGE_SIZE,total);
    var links='';
    links+='<button type="button" class="pagination-btn'+(currentPage<=1?' is-disabled':'')+'" data-page="'+(currentPage-1)+'"'+(currentPage<=1?' aria-disabled="true"':'')+'>← 前へ</button>';
    var nums=[];
    for(var i=1;i<=pages;i++){
      if(i===1||i===pages||Math.abs(i-currentPage)<=1)nums.push(i);
      else if(nums[nums.length-1]!=='…')nums.push('…');
    }
    nums.forEach(function(n){
      if(n==='…')links+='<span class="pagination-ellipsis" aria-hidden="true">…</span>';
      else links+='<button type="button" class="pagination-num'+(n===currentPage?' is-current':'')+'" data-page="'+n+'"'+(n===currentPage?' aria-current="page"':'')+'>'+n+'</button>';
    });
    links+='<button type="button" class="pagination-btn'+(currentPage>=pages?' is-disabled':'')+'" data-page="'+(currentPage+1)+'"'+(currentPage>=pages?' aria-disabled="true"':'')+'>次へ →</button>';
    pagination.innerHTML='<span class="pagination-status">'+fmtN(start)+'–'+fmtN(end)+'件 / 全'+fmtN(total)+'件</span><div class="pagination-links">'+links+'</div>';
  }
  function render(){
    if(resetPage){currentPage=1;resetPage=false;}
    var t=queryText(),mj=majorSel.value,sk=sortSel.value||'app-desc',
        band=studySel.value,pBand=passSel?passSel.value:'',fBand=freqSel?freqSel.value:'';
    if(studyNote)studyNote.style.display=band?'inline':'none';
    var out=DATA.filter(function(x){
      if(mj&&x.major!==mj)return false;
      if(legacyType&&x.type!==legacyType)return false;
      if(t&&x.name.toLowerCase().indexOf(t)<0)return false;
      if(fPub.checked&&x.status!=='published')return false;
      if(legacyIndustry&&(x.industries||[]).indexOf(legacyIndustry)<0)return false;
      if(band&&!studyHit(x,band))return false;
      if(pBand&&!passHit(x,pBand))return false;
      if(fBand&&freqBucket(x.frequency)!==fBand)return false;
      if(activeTags.size){
        var tg=x.tags||[],ok=true;
        activeTags.forEach(function(a){if(tg.indexOf(a)<0)ok=false;});
        if(!ok)return false;
      }
      return true;
    });
    var key=sk.indexOf('app')===0?appNum:(sk.indexOf('study')===0?studyLow:(sk.indexOf('pass')===0?passNum:appNum)), asc=sk.indexOf('asc')>=0;
    out=out.slice().sort(function(a,b){
      var va=key(a),vb=key(b);
      if(va===null&&vb===null)return 0;
      if(va===null)return 1; if(vb===null)return -1;
      return asc?va-vb:vb-va;
    });
    var pages=Math.max(1,Math.ceil(out.length/PAGE_SIZE));
    if(currentPage>pages)currentPage=pages;
    var sliceStart=(currentPage-1)*PAGE_SIZE;
    var pageItems=out.slice(sliceStart,sliceStart+PAGE_SIZE);
    var anyFilter=t||mj||band||pBand||fBand||activeTags.size||fPub.checked||legacyType||legacyIndustry;
    if(clearBtn)clearBtn.hidden=!anyFilter;
    if(countEl){
      if(out.length){
        countEl.innerHTML='全 <strong>'+fmtN(out.length)+'</strong> 件 · '+fmtN(sliceStart+1)+'–'+fmtN(sliceStart+pageItems.length)+'件を表示';
      } else countEl.textContent='該当する資格はありません';
    }
    if(heroResult){
      if(anyFilter){
        heroResult.hidden=false;
        heroResult.innerHTML=(t?'「<strong>'+esc(t)+'</strong>」を含む資格 ':'絞り込み結果 ')+
          '<strong>'+fmtN(out.length)+'</strong> 件 <a href="#all-certs">一覧へ ↓</a>';
      } else { heroResult.hidden=true; heroResult.innerHTML=''; }
    }
    results.innerHTML=pageItems.map(function(x){
      var study=x.study_hours?esc(x.study_hours):'—';
      var pass=x.pass_rate?esc(x.pass_rate):'—';
      var freq=x.frequency?esc(x.frequency):'—';
      return '<tr class="cert-row" tabindex="0" data-href="c/'+esc(x.slug)+'.html">'+
        '<td class="all-certs-name"><span class="all-certs-name-inner">'+
        (x.popular?TROPHY:'')+
        '<span class="all-certs-name-text">'+esc(shortName(x.name))+'</span></span></td>'+
        '<td class="all-certs-cell">'+esc(x.major)+'</td>'+
        '<td class="all-certs-cell all-certs-num">'+study+'</td>'+
        '<td class="all-certs-cell all-certs-num">'+pass+'</td>'+
        '<td class="all-certs-cell all-certs-cell--freq">'+freq+'</td></tr>';
    }).join('')||'<tr><td colspan="5" class="empty-state">条件に一致する資格が見つかりませんでした。<br>キーワードを短くするか、上の「× 条件をクリア」で絞り込みを解除してください。</td></tr>';
    renderPagination(out.length);
    syncURL();
  }
  if(pagination)pagination.addEventListener('click',function(e){
    var btn=e.target.closest('[data-page]');
    if(!btn||btn.classList.contains('is-disabled'))return;
    var p=parseInt(btn.getAttribute('data-page'),10);
    if(!p||p===currentPage)return;
    currentPage=p; render();
    var sec=document.getElementById('all-certs'); if(sec)sec.scrollIntoView({behavior:'smooth',block:'start'});
  });
  if(results){
    results.addEventListener('click',function(e){
      var tr=e.target.closest('tr.cert-row');
      if(!tr)return;
      var href=tr.getAttribute('data-href');
      if(href)location.href=href;
    });
    results.addEventListener('keydown',function(e){
      if(e.key!=='Enter'&&e.key!==' ')return;
      var tr=e.target.closest('tr.cert-row');
      if(!tr)return;
      e.preventDefault();
      var href=tr.getAttribute('data-href');
      if(href)location.href=href;
    });
  }
  fetch('data/certifications.json').then(function(r){return r.json();}).then(function(all){
    DATA=all; if(count)count.textContent=fmtN(all.length);
    var majors={};
    all.forEach(function(x){majors[x.major]=1;});
    Object.keys(majors).sort().forEach(function(v){opt(majorSel,v);});
    var p=new URLSearchParams(location.search);
    if(p.get('q')){syncQueryInputs({value:p.get('q')});}
    if(p.get('major'))majorSel.value=p.get('major');
    if(p.get('study'))studySel.value=p.get('study');
    if(passSel&&p.get('pass'))passSel.value=p.get('pass');
    if(freqSel&&p.get('frequency'))freqSel.value=p.get('frequency');
    sortSel.value=p.get('sort')||'app-desc';
    if(p.get('pub')==='1')fPub.checked=true;
    if(p.get('page'))currentPage=Math.max(1,parseInt(p.get('page'),10)||1);
    if(p.get('tag')){p.get('tag').split(',').forEach(function(tg){activeTags.add(tg);});}
    if(p.get('type'))legacyType=p.get('type');
    if(p.get('industry'))legacyIndustry=p.get('industry');
    if(location.hash==='#all')location.hash='#all-certs';
    render();
  });
  function onFilter(){resetPage=true;render();}
  function onQueryInput(e){syncQueryInputs(e.target);onFilter();}
  if(q)q.addEventListener('input',onQueryInput);
  if(listQ)listQ.addEventListener('input',onQueryInput);
  [majorSel,sortSel,studySel,passSel,freqSel].forEach(function(el){if(el)el.addEventListener('input',onFilter);});
  fPub.addEventListener('change',onFilter);
  if(q)q.addEventListener('keydown',function(e){
    if(e.key==='Enter'){var a=document.getElementById('all-certs');if(a){e.preventDefault();a.scrollIntoView();}}
  });
  if(listQ)listQ.addEventListener('keydown',function(e){
    if(e.key==='Enter'){e.preventDefault();onFilter();}
  });
  if(clearBtn)clearBtn.addEventListener('click',function(){
    syncQueryInputs({value:''});
    majorSel.value='';studySel.value='';
    if(passSel)passSel.value='';
    if(freqSel)freqSel.value='';
    sortSel.value='app-desc';fPub.checked=false;
    legacyType='';legacyIndustry='';
    activeTags.clear();resetPage=true;render();
  });
  (function renderRecent(){
    try{
      var a=JSON.parse(localStorage.getItem('recent')||'[]');
      var blk=document.getElementById('recentBlock'),grid=document.getElementById('recentGrid');
      if(!blk||!grid||!a.length)return;
      grid.innerHTML=a.slice(0,8).map(function(x){
        return '<li><a href="c/'+esc(x.s)+'.html">'+esc(x.n)+'</a></li>';
      }).join('');
      blk.hidden=false;
    }catch(e){}
  })();
})();
"""

SEARCH_JS = SEARCH_JS.replace(
    "__TROPHY_HTML__",
    json.dumps(f'<span class="all-certs-trophy" aria-hidden="true">{ICON_TROPHY}</span>'))


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
    var h='<table class="cmp"><colgroup><col class="cmp-col-label">';
    items.forEach(function(){h+='<col class="cmp-col-cert">';});
    h+='</colgroup><thead><tr><th></th>';
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
--ink-deep:#1a1a1a;--ink:#1a1a1a;--muted:#666666;
--header-bg:#ffffff;
--on-dark:#c4c4c4;--on-dark-muted:#888888;
--gray-300:#c4c4c4;--gray-200:#dcdcdc;--gray-100:#f0f0f0;--gray-50:#f7f7f7;
--table-head-bg:#ebebeb;--table-border:#d2d2d2;--table-hover-bg:#e3e3e3;
--gray-800:#434343;--gray-700:#525252;--gray-400:#7f7f7f;--white:#fff;--page-bg:#eef0f1;
--accent:#236f64;--accent-hover:#1c5a51;--accent-light:#e6f1ef;--accent-ring:rgba(35,111,100,.22);
--radius:8px;
/* テキスト色: ink-deep=見出し / ink=本文・表・通常リンク / muted=補足。on-dark*=ヘッダー等 */
/* タイプスケール: xl=大見出し / lg=セクション見出し(20px) / md=本文 / sm=補助・メタ / table=表(15px) */
--text-xl:clamp(1.375rem,4vw,2.25rem);--text-lg:1.25rem;--text-md:1.0625rem;--text-sm:0.875rem;--text-table:0.9375rem;
/* フォントウェイト: regular=本文 / semibold=ラベル・カード名・h3 / bold=見出し・強調 */
--fw-regular:400;--fw-semibold:600;--fw-bold:700;--page-gutter:32px}
*{box-sizing:border-box}
html{font-size:16px}
body{margin:0;min-height:100vh;display:flex;flex-direction:column;font-family:"Noto Sans JP",system-ui,-apple-system,"Hiragino Kaku Gothic ProN",Meiryo,sans-serif;font-size:var(--text-md);font-weight:var(--fw-regular);color:var(--ink);background:var(--page-bg);line-height:1.7;-webkit-font-smoothing:antialiased;overflow-wrap:break-word}
h2{font-size:var(--text-lg);font-weight:var(--fw-bold);color:var(--ink-deep)}
h3{font-size:var(--text-lg);font-weight:var(--fw-semibold);color:var(--ink-deep)}
a{color:var(--ink)}a:hover{text-decoration:underline}
img{max-width:100%}
:focus-visible{outline:3px solid var(--accent-ring);outline-offset:2px}
.skip-link{position:absolute;left:-9999px}.skip-link:focus{left:8px;top:8px;background:#fff;padding:8px 12px;z-index:50;border-radius:6px}

/* Header */
.site-header{background:var(--header-bg);color:var(--ink);border-bottom:1px solid var(--gray-200);position:sticky;top:0;z-index:30;box-shadow:0 1px 0 rgba(0,0,0,.04)}
@media(prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}
html{scroll-padding-top:64px}
.header-inner{max-width:1200px;margin:0 auto;padding:12px var(--page-gutter);display:flex;align-items:center;gap:16px;min-width:0}
.header-brand{flex-shrink:0;display:flex;align-items:center}
.logo{display:flex;align-items:center;gap:9px;text-decoration:none;color:var(--ink-deep);flex-shrink:0}
.logo-mark{min-width:54px;min-height:36px;padding:6px 10px 5px;border-radius:4px;background:var(--ink-deep);display:inline-flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;flex-shrink:0;color:#fff;box-sizing:border-box;transition:opacity .15s}
.logo-mark-line{display:block;font-size:12px;font-weight:700;line-height:1.05;text-align:center;white-space:nowrap;letter-spacing:.02em}
.logo-mark-line--sub{font-size:11px;letter-spacing:.04em}
.logo-stack{display:flex;flex-direction:column;align-items:flex-start;gap:1px;line-height:1.15;min-width:0}
.logo-text{font-size:16px;font-weight:700;letter-spacing:-0.01em;white-space:nowrap;color:var(--ink-deep)}
.logo-sub{font-size:10px;font-weight:600;color:var(--muted);letter-spacing:0;line-height:1.25;white-space:normal;max-width:min(240px,52vw)}
.logo:hover{text-decoration:none;color:var(--ink-deep)}
.logo:hover .logo-mark{opacity:.88}
.site-tagline{color:var(--muted);font-size:var(--text-sm);font-weight:400;line-height:1.3}
.ico-svg{width:18px;height:18px;display:block;flex-shrink:0}
.header-nav{display:flex;align-items:center;flex-wrap:wrap;margin-left:auto;min-width:0}
.header-nav a:not(.header-nav-cta){color:var(--ink);font-size:var(--text-sm);text-decoration:none;padding:6px 8px;white-space:nowrap;border-radius:4px}
.header-nav a:not(.header-nav-cta):hover{color:var(--ink-deep);background:var(--gray-50);text-decoration:none}
.header-nav a.is-current{color:var(--ink-deep);font-weight:600}
.header-nav-cta{margin-left:8px;padding:7px 12px;background:var(--accent);color:#fff !important;font-size:var(--text-sm);font-weight:600;border-radius:var(--radius);line-height:1.2;text-decoration:none}
.header-nav a.header-nav-cta:hover,.header-nav a.header-nav-cta:focus-visible{background:var(--accent-hover);color:#fff !important;text-decoration:none}
.header-nav-sep{color:var(--gray-400);font-size:var(--text-sm);user-select:none;padding:0 1px}
.header-actions{display:none;align-items:center;gap:2px;margin-left:auto;flex-shrink:0}
.header-icon-btn{display:inline-flex;align-items:center;justify-content:center;background:transparent;border:none;color:var(--ink);cursor:pointer;padding:8px;border-radius:6px;line-height:0;font-family:inherit}
.header-icon-btn:hover{color:var(--ink-deep);background:var(--gray-100)}
.header-search-panel,.header-menu-panel{display:none;border-top:1px solid var(--gray-200);background:var(--header-bg)}
.site-header--search-open .header-search-panel{display:block}
.site-header--menu-open .header-menu-panel{display:flex}
.header-search-panel{padding:12px var(--page-gutter) 14px}
.header-search-form{max-width:1200px;margin:0 auto;display:flex;gap:8px;min-width:0}
.header-search-form input{flex:1;min-width:0;padding:10px 14px;border:1px solid var(--gray-300);border-radius:var(--radius);background:#fff;color:var(--ink);font-size:var(--text-md);font-family:inherit}
.header-search-form input::placeholder{color:var(--muted)}
.header-search-form button{padding:10px 16px;background:var(--accent);color:#fff;border:none;border-radius:var(--radius);font-family:inherit;font-weight:600;cursor:pointer;white-space:nowrap}
.header-search-form button:hover{background:var(--accent-hover)}
.header-menu-panel{flex-direction:column;max-width:1200px;margin:0 auto;padding:4px var(--page-gutter) 10px;width:100%}
.header-menu-panel a{color:var(--ink);text-decoration:none;padding:12px 4px;border-bottom:1px solid var(--gray-200);font-size:var(--text-md)}
.header-menu-panel a:last-child{border-bottom:none}
.header-menu-panel a:hover{color:var(--ink-deep);background:var(--gray-50);text-decoration:none}
@media(max-width:768px){.header-nav{display:none}.header-actions{display:flex}.header-inner{padding:10px 16px;--page-gutter:16px}.logo-mark{min-width:48px;min-height:32px;padding:5px 8px 4px}.logo-mark-line{font-size:11px}.logo-mark-line--sub{font-size:10px}.logo-text{font-size:15px}.logo-sub{font-size:9px;max-width:min(200px,58vw)}.site-tagline{display:none}.container{padding:20px 16px 36px}.block-band{margin-left:-16px;margin-right:-16px;padding:32px 16px 36px}.block-all-certs{padding:40px 16px 44px}}

.container{max-width:1200px;margin:0 auto;padding:28px var(--page-gutter) 36px;width:100%;flex:1 0 auto;min-width:0;background:#fff;box-shadow:0 0 24px rgba(0,0,0,.05)}

/* Hero */
.hero{padding:32px 0 20px;margin-bottom:0}
.hero h1{font-weight:700;line-height:1.4;margin:0 0 12px;letter-spacing:.02em}
.hero-h1-line{display:block;font-size:var(--text-xl);font-weight:700;color:var(--ink-deep);letter-spacing:.02em}
.hero-h1-line+.hero-h1-line{margin-top:2px}
.hero-sub{font-size:var(--text-md);color:var(--ink);line-height:1.75;max-width:40em;margin:0}
.hero-sub #count{color:var(--accent);font-weight:700;text-decoration:underline;text-underline-offset:3px}
.hero-search{margin-top:18px;max-width:520px;position:relative}
.hero-search input{width:100%;padding:12px 16px 12px 42px;border:1px solid var(--gray-300);border-radius:var(--radius);font-size:var(--text-md);background:#fff;color:var(--ink);font-family:inherit}
.hero-search input::placeholder{color:var(--muted)}
.hero-search input:focus,.hero-search input:focus-visible{border-color:var(--accent);outline:3px solid var(--accent-ring);outline-offset:2px}
.hero-search .ico{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--muted);display:flex}
.hero-result{margin-top:12px;font-size:var(--text-sm);color:var(--muted)}
.hero-result a{color:var(--accent);font-weight:600;text-decoration:underline;text-underline-offset:2px}
.hero-result strong{color:var(--ink-deep)}

/* Blocks */
.block{margin-bottom:28px}.block-primary{margin-bottom:40px}.block-secondary{margin-bottom:34px}
.block-band{margin-left:calc(-1*var(--page-gutter));margin-right:calc(-1*var(--page-gutter));padding:40px var(--page-gutter) 44px;border-top:1px solid var(--gray-200);margin-bottom:0}
.hero+.block-band{border-top:none}
.block-band--gray{background:var(--gray-50)}
.block-band--white{background:#fff}
.block-inset{margin:8px 0 20px;padding:0 2px}
.block-head{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:18px;gap:8px;flex-wrap:wrap}
.block-head h2{font-size:var(--text-lg);font-weight:700;color:var(--ink-deep);margin:0}
.block-head p{font-size:var(--text-sm);color:var(--muted);margin:0}
.block-all-certs{padding:52px var(--page-gutter) 56px;margin-bottom:0}
.block-all-certs .block-head{margin-bottom:24px}
.card-link{position:relative}
.card-link::after{content:"→";position:absolute;right:12px;top:14px;font-size:var(--text-sm);font-weight:600;color:var(--muted);opacity:0;transition:opacity .15s,color .15s;pointer-events:none}
.card-link:hover::after,.card-link:focus-visible::after{opacity:1;color:var(--accent)}
.card-link:hover,.card-link:focus-visible{background:var(--accent-light);border-color:var(--accent);text-decoration:none}


/* Popular */
.popular-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.pop-card{display:flex;flex-direction:column;background:#fff;color:var(--ink);border-radius:var(--radius);padding:14px 32px 12px 13px;text-decoration:none;border:1px solid var(--gray-200);transition:border-color .15s,background .15s}
.pop-card-head{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.pop-card-trophy{flex-shrink:0;width:36px;height:36px;display:flex;align-items:center;justify-content:center;background:#f7f3e8;border-radius:var(--radius);color:#b8860b}
.pop-card-trophy .icon-svg{width:20px;height:20px}
.pop-card-name{font-size:var(--text-md);font-weight:var(--fw-semibold);line-height:1.35;color:var(--ink-deep);margin:0;flex:1;min-width:0}
.pop-card-facts{list-style:none;margin:auto 0 0;padding:6px 0 0;display:flex;flex-direction:column;gap:5px}
.pop-card-facts li{display:grid;grid-template-columns:4.8em 1fr;gap:4px;font-size:var(--text-sm);line-height:1.45}
.pop-card-facts .k{color:var(--muted)}.pop-card-facts .v{color:var(--ink);font-weight:600}
@media(max-width:720px){.popular-grid{grid-template-columns:repeat(2,1fr);gap:10px}.pop-card--more{display:none}.popular-more{display:block}}
.popular-more,.field-more,.compare-more{margin-top:12px;text-align:right;display:none}
.popular-more a,.field-more a,.compare-more a{font-size:var(--text-sm);font-weight:var(--fw-semibold);color:var(--ink);text-decoration:underline;text-underline-offset:2px}
@media(max-width:720px){.popular-more{display:block}}
.purpose-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media(max-width:640px){.purpose-grid{grid-template-columns:1fr}}
.purpose-card{display:flex;align-items:flex-start;gap:12px;background:#fff;border:1px solid var(--gray-200);border-radius:var(--radius);padding:16px 36px 16px 14px;text-decoration:none;color:inherit;transition:border-color .15s,background .15s;position:relative}
.purpose-card .icon{flex-shrink:0;width:44px;height:44px;display:flex;align-items:center;justify-content:center;background:var(--gray-100);border-radius:var(--radius);color:var(--muted)}
.purpose-card .icon-svg{width:26px;height:26px}
.purpose-card-body{min-width:0;flex:1}
.purpose-card h3{font-size:var(--text-lg);font-weight:var(--fw-bold);margin:0 0 4px;color:var(--ink-deep)}
.purpose-card-for{font-size:var(--text-sm);color:var(--muted);line-height:1.5;margin:0}
.purpose-card::after{content:"→";position:absolute;right:12px;top:14px;font-size:var(--text-sm);font-weight:600;color:var(--muted);opacity:0;transition:opacity .15s,color .15s;pointer-events:none}
.purpose-card:hover::after,.purpose-card:focus-visible::after{opacity:1;color:var(--accent)}
.purpose-card:hover,.purpose-card:focus-visible{border-color:var(--muted);background:var(--accent-light);text-decoration:none}
.recent-list{list-style:none;display:flex;flex-wrap:wrap;gap:8px;margin:0;padding:0}
.recent-list a{display:inline-block;padding:8px 12px;border:1px solid var(--gray-200);border-radius:var(--radius);font-size:var(--text-sm);font-weight:600;color:var(--ink-deep);text-decoration:none;background:#fff}
.recent-list a:hover{border-color:var(--muted);text-decoration:none}
.all-certs-filters{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:14px 12px;margin-bottom:16px}
.block-all-certs .filter-field label{display:block;font-size:var(--text-sm);color:var(--muted);margin-bottom:6px;font-weight:600}
.block-all-certs .filter-field select,.block-all-certs .filter-field input[type=search]{width:100%;padding:8px 10px;border:1px solid var(--gray-300);border-radius:4px;font-size:var(--text-sm);font-family:inherit;background:#fff;color:var(--ink)}
.block-all-certs .all-certs-check{display:inline-flex;align-items:center;gap:6px;font-size:var(--text-sm);color:var(--ink);margin-bottom:20px;cursor:pointer}
.all-certs-check input{width:15px;height:15px;accent-color:var(--accent)}
.block-all-certs .all-certs-count{font-size:var(--text-sm);color:var(--muted);margin-bottom:12px}
.all-certs-table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--table-border);border-radius:var(--radius);background:#fff}
.all-certs-table{width:100%;border-collapse:collapse;background:#fff;border:none;border-radius:0;font-size:var(--text-table);color:var(--ink);table-layout:fixed}
.all-certs-table--4col col.all-certs-col-name{width:34%}
.all-certs-table--4col col.all-certs-col-study{width:16%}
.all-certs-table--4col col.all-certs-col-pass{width:12%}
.all-certs-table--4col col.all-certs-col-freq{width:38%}
.all-certs-table--5col col.all-certs-col-name{width:28%}
.all-certs-table--5col col.all-certs-col-major{width:14%}
.all-certs-table--5col col.all-certs-col-study{width:14%}
.all-certs-table--5col col.all-certs-col-pass{width:10%}
.all-certs-table--5col col.all-certs-col-freq{width:34%}
.all-certs-table thead th{text-align:left;padding:11px 14px;background:var(--table-head-bg);color:var(--ink);font-weight:var(--fw-regular);font-size:var(--text-table);border-bottom:1px solid var(--table-border);white-space:nowrap}
.all-certs-table tbody td{padding:11px 14px;border-bottom:1px solid var(--table-border);vertical-align:middle;line-height:1.5;white-space:nowrap;font-size:var(--text-table);color:var(--ink)}
.all-certs-table tbody tr.cert-row{cursor:pointer;transition:background-color .12s ease}
.all-certs-table tbody tr.cert-row:hover td{background:var(--accent-light)}
.all-certs-table tbody tr.cert-row:focus-visible{outline:2px solid var(--accent-ring);outline-offset:-2px}
.all-certs-table tbody tr:last-child td{border-bottom:none}
.all-certs-name{min-width:12em}
.all-certs-name-inner{display:inline-flex;align-items:center;gap:6px;max-width:100%}
.all-certs-trophy{flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;color:#b8860b;background:#f7f3e8;border-radius:4px}
.all-certs-trophy .icon-svg{width:14px;height:14px}
.all-certs-name-text{white-space:nowrap;font-weight:var(--fw-semibold);color:var(--ink-deep)}
.all-certs-table tbody tr.cert-row:hover .all-certs-name-text{color:var(--accent)}
.all-certs-cell{font-weight:400;color:var(--ink)}
.all-certs-num{font-variant-numeric:tabular-nums;color:var(--ink)}
.all-certs-table .empty-state{white-space:normal;text-align:center;color:var(--muted);background:var(--gray-50);padding:22px 16px;line-height:1.75;font-size:var(--text-sm)}
.pagination{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;margin-top:28px;padding-top:4px}
.block-all-certs .pagination-status{font-size:var(--text-sm);color:var(--muted)}
.pagination-links{display:flex;flex-wrap:wrap;align-items:center;gap:6px}
.block-all-certs .pagination-btn,.block-all-certs .pagination-num{font-size:var(--text-sm);color:var(--ink)}
.pagination-btn,.pagination-num{display:inline-flex;align-items:center;justify-content:center;min-width:34px;min-height:34px;padding:0 9px;font-size:var(--text-sm);font-weight:600;border:1px solid var(--gray-200);border-radius:4px;background:#fff;color:var(--ink-deep);text-decoration:none;line-height:1;cursor:pointer;font-family:inherit}
.pagination-btn:hover,.pagination-num:hover{border-color:var(--muted);text-decoration:none}
.pagination-num.is-current{background:var(--ink-deep);color:#fff;border-color:var(--ink-deep)}
.pagination-btn.is-disabled,.pagination-num.is-disabled{opacity:.4;pointer-events:none}
.pagination-ellipsis{font-size:var(--text-sm);color:var(--muted);padding:0 2px}
@media(max-width:1024px){.all-certs-filters{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:720px){.all-certs-filters{grid-template-columns:repeat(2,minmax(0,1fr))}.pagination{flex-direction:column;align-items:stretch}.pagination-links{justify-content:center}}

/* 分野別・目的別ガイド（トップの資格一覧表と同じデザイン） */
.page-bunya .all-certs-table-wrap,
.page-feature .all-certs-table-wrap{margin-top:8px}
.page-feature .hub-grp + .all-certs-table-wrap{margin-top:4px}
.page-bunya .all-certs-cell--cat,
.page-feature .all-certs-cell--cat{white-space:normal;min-width:8em;max-width:14em}

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
.field-card h3{font-size:var(--text-md);font-weight:var(--fw-semibold);line-height:1.35;color:var(--ink-deep);margin:0}
.field-count{flex-shrink:0;margin-top:1px;padding:3px 7px;border-radius:4px;font-size:var(--text-sm);font-weight:600;color:var(--muted);background:var(--gray-100);border:1px solid var(--gray-200);line-height:1.2;white-space:nowrap}
.field-examples{font-size:var(--text-sm);color:var(--muted);line-height:1.45;margin:0}

/* Compare cards */
.compare-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
@media(max-width:900px){.compare-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:560px){.compare-grid{grid-template-columns:1fr}}
.compare-card{display:flex;flex-direction:column;position:relative;background:#fff;border:1px solid var(--gray-200);border-radius:10px;padding:14px 40px 14px 14px;text-decoration:none;color:inherit;transition:border-color .15s,background .15s}
.compare-card:hover,.compare-card:focus-visible{background:var(--accent-light);border-color:var(--accent);text-decoration:none}
.compare-tag{font-size:var(--text-sm);font-weight:600;color:var(--muted);letter-spacing:.04em;margin-bottom:6px}
.compare-names{font-size:var(--text-md);font-weight:var(--fw-semibold);line-height:1.45;color:var(--ink-deep);margin:0;flex:1}
.compare-names em{font-style:normal;color:var(--muted);font-weight:400;font-size:var(--text-sm)}
.compare-go{position:absolute;right:14px;top:50%;transform:translateY(-50%);font-size:var(--text-md);font-weight:600;color:var(--accent);line-height:1}
.compare-card:hover .compare-go,.compare-card:focus-visible .compare-go{color:var(--accent-hover)}

/* Buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;background:var(--accent);color:#fff;padding:9px 18px;border-radius:var(--radius);font-size:var(--text-md);font-weight:600;text-decoration:none;border:none;cursor:pointer;font-family:inherit}
.btn:hover{background:var(--accent-hover);text-decoration:none}
.btn-outline{background:#fff;color:var(--accent);border:1px solid var(--accent)}
.btn-outline:hover{background:var(--gray-100)}

/* Lists / search */
h1{font-size:var(--text-xl);margin:.1em 0 .35em;color:var(--ink-deep);font-weight:var(--fw-bold)}
h2{color:var(--ink-deep)}
.lead{color:var(--ink);font-size:var(--text-md);margin:0 0 14px;line-height:1.75}
.lead p{margin:0 0 .75em;color:inherit}
.lead p:last-child{margin-bottom:0}
.lead strong{color:var(--accent);font-weight:var(--fw-semibold);text-decoration:underline;text-underline-offset:2px}
.controls{display:flex;gap:10px 14px;flex-wrap:wrap;margin:16px 0;align-items:flex-end}
.controls input,.controls select{padding:10px 12px;border:1px solid var(--gray-300);border-radius:var(--radius);font-size:var(--text-md);font-family:inherit;background:#fff;color:var(--ink)}
.controls input{flex:1 1 260px}.controls select{cursor:pointer}
.ctl{display:inline-flex;flex-direction:column;gap:3px;min-width:0}
.ctl-l{font-size:var(--text-sm);font-weight:600;color:var(--muted);letter-spacing:.02em}
.ctl select{width:100%;min-width:130px}
@media(max-width:560px){.ctl{flex:1 1 44%}}
.filters{display:flex;flex-wrap:wrap;gap:14px;margin:-6px 0 6px;font-size:var(--text-sm);color:var(--muted)}
.filters label{display:inline-flex;align-items:center;gap:5px;cursor:pointer}
.results{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:7px}
.results li{background:#fff;border:1px solid var(--gray-200);border-radius:11px;padding:11px 14px}
.results li a{font-weight:600;color:var(--ink);text-decoration:none}
.results li a:hover{color:var(--accent)}
/* 資格の一覧・ランキングリスト */
.cert-list{list-style:none;padding:0;margin:.5em 0 0;display:flex;flex-direction:column;gap:8px}
.cl-item{display:flex;align-items:stretch;gap:10px}
.cl-rank{flex-shrink:0;display:flex;align-items:center;justify-content:center;min-width:30px;font-weight:700;font-size:var(--text-lg);color:var(--muted);font-variant-numeric:tabular-nums;line-height:1}
.cl-rank--top{color:var(--accent)}
.cl-link{flex:1;min-width:0;display:flex;flex-direction:column;gap:5px;background:#fff;border:1px solid var(--gray-200);border-radius:10px;padding:12px 14px;text-decoration:none;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,.06);transition:border-color .15s,background .15s}
.cl-link:hover,.cl-link:focus-visible{border-color:var(--accent);background:var(--accent-light);text-decoration:none}
.cl-name{font-size:var(--text-md);font-weight:var(--fw-semibold);color:var(--ink);line-height:1.4}
.cl-link:hover .cl-name{color:var(--accent-hover)}
.cl-meta{display:flex;flex-wrap:wrap;align-items:center;gap:5px 9px;font-size:var(--text-sm);color:var(--muted);line-height:1.4}
.cl-major,.cl-cat{color:var(--muted)}
.cl-data{color:var(--muted);font-weight:600}
.cert-list--ranked .cl-rank{min-width:34px}
@media(max-width:480px){.cl-rank{min-width:22px;font-size:var(--text-md)}.cert-list--ranked .cl-rank{min-width:26px}}
.results .meta{display:block;color:var(--muted);font-size:var(--text-sm);margin-top:3px}
.hint{font-size:var(--text-sm);margin:4px 0 10px;color:var(--muted)}
.results-bar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:2px 0 2px}
.results-bar #status{margin:0}
.clear-filters{background:none;border:none;color:var(--accent);font-family:inherit;font-size:var(--text-sm);font-weight:600;cursor:pointer;padding:0;text-decoration:underline;text-underline-offset:2px}
.clear-filters:hover{color:var(--accent-hover)}
.muted,.note-muted{color:var(--muted)}
.pop-card,.field-card,.compare-card,.faq-item,table.spec,.results li,.occ-list li{box-shadow:0 1px 3px rgba(0,0,0,.07)}
.crumbs{font-size:var(--text-sm);color:var(--muted);margin-bottom:10px}
.crumbs a{color:var(--ink)}

/* Badges (subtle) */
.badge{display:inline-block;padding:1px 8px;border-radius:4px;font-size:var(--text-sm);font-weight:600;border:1px solid var(--gray-300);color:var(--muted);background:var(--gray-100);vertical-align:middle}
.badge-national,.b-国家{color:#9a3b32;background:#fbeeec;border-color:#eccfca}
.badge-public,.b-公的{color:var(--accent-hover);background:var(--accent-light);border-color:rgba(42,122,110,.22)}
.badge-private,.b-民間{color:#3a6b46;background:#eef5f0;border-color:#cfe2d5}
.badge-unknown,.b-要確認{color:var(--muted);background:var(--gray-100);border-color:var(--gray-300)}
.badge-overseas{color:#6a4a8a;background:#f3eef8;border-color:#ddd0ea}

/* Spec table (detail) */
table.spec{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--table-border);border-radius:var(--radius);overflow:hidden;font-size:var(--text-table);font-weight:var(--fw-regular);color:var(--ink)}
.spec-wrap{border:1px solid var(--table-border);border-radius:var(--radius);overflow:hidden;background:#fff}
.spec-wrap table.spec{border:none;border-radius:0}
table.spec tr:last-child th,table.spec tr:last-child td{border-bottom:none}
table.spec th,table.spec td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--table-border);vertical-align:middle;line-height:1.55}
table.spec th{width:34%;background:var(--table-head-bg);color:var(--ink);font-weight:var(--fw-regular);font-size:var(--text-table);white-space:nowrap}
@media(max-width:480px){table.spec th,table.spec td{display:block;width:auto}table.spec th{white-space:normal;border-bottom:none;padding:9px 14px 1px}table.spec td{padding:1px 14px 11px}}
.related{margin-top:24px}.related ul{padding-left:1.1em}
.official-cta{margin:16px 0 6px}
.btn-official{display:inline-block;background:var(--accent);color:#fff;font-weight:var(--fw-semibold);padding:11px 20px;border-radius:var(--radius)}
.btn-official:hover{background:var(--accent-hover);text-decoration:none}
.provenance{font-size:var(--text-sm);color:var(--muted);background:var(--gray-50);border:1px solid var(--gray-200);border-radius:var(--radius);padding:11px 14px;margin:10px 0 0}
.feat-list{margin:.2em 0 .6em;padding-left:1.1em}.feat-list li{margin:2px 0}
.feat-list a{color:var(--ink)}
.updated{font-size:var(--text-sm);color:var(--muted);margin:.1em 0 .6em}.updated .muted{margin-left:.4em}
.tag-chip{display:inline-block;background:var(--gray-100);color:var(--muted);border:1px solid var(--gray-200);border-radius:12px;padding:2px 10px;margin:2px 4px 2px 0;font-size:var(--text-sm)}
.tag-ind{background:var(--accent-light);color:var(--accent-hover);border-color:rgba(42,122,110,.18)}
a.tag-chip{text-decoration:none;cursor:pointer;transition:border-color .12s,background .12s}
a.tag-chip:hover{border-color:var(--accent);background:var(--accent-light);text-decoration:none}
.diff-badge{display:inline-block;font-weight:700;font-size:var(--text-sm);padding:2px 9px;border-radius:6px;color:#fff}
.diff-veryhard{background:#9a3b32}.diff-hard{background:#b5642f}.diff-mid{background:#caa53c;color:#3a2c00}
.diff-easy{background:#3a6b46}.diff-veryeasy{background:var(--accent)}
.diff-rank{display:inline-block;font-weight:700;font-size:var(--text-sm);padding:2px 10px;border-radius:6px;background:var(--gray-700);color:#fff;margin:1px 2px 1px 0}
.diff-rank-field{background:var(--accent-hover)}
.diff-meta{font-size:var(--text-sm);margin-top:3px}
.roadmap{margin:.4em 0 .8em}.roadmap h3{font-size:var(--text-lg);font-weight:var(--fw-bold);margin:.7em 0 .5em;color:var(--ink-deep)}
.rm-track{list-style:none;display:flex;flex-wrap:wrap;align-items:stretch;gap:12px 20px;padding:0;margin:.2em 0}
.rm-step{display:flex;align-items:center;gap:10px;background:#fff;border:1px solid var(--gray-300);border-radius:10px;padding:10px 14px;position:relative;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.rm-num{flex-shrink:0;display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:var(--gray-200);color:var(--muted);font-size:var(--text-sm);font-weight:700;font-variant-numeric:tabular-nums}
.rm-name{font-weight:600;line-height:1.3}
a.rm-name{color:var(--accent);text-decoration:none}
a.rm-name:hover{text-decoration:underline}
.rm-step:not(:last-child)::after{content:"›";position:absolute;right:-14px;top:50%;transform:translateY(-50%);color:var(--muted);font-weight:700;font-size:1.3rem;line-height:1}
.rm-cur{background:var(--accent-light);border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
.rm-cur .rm-num{background:var(--accent);color:#fff}
.rm-cur .rm-name{color:var(--ink-deep);font-weight:700}
.rm-badge{flex-shrink:0;font-size:var(--text-sm);font-weight:700;color:#fff;background:var(--accent);border-radius:4px;padding:2px 7px;white-space:nowrap}
@media(max-width:560px){.rm-track{flex-direction:column;gap:18px 0}.rm-step{width:100%}.rm-step:not(:last-child)::after{content:"▾";right:auto;left:25px;top:auto;bottom:-15px;transform:translateX(-50%)}}
.careers-sec,.materials-sec,.rel-certs,.rel-links{margin:18px 0 0;border-top:1px solid var(--gray-200);padding-top:12px}
.careers-sec h2,.materials-sec h2,.rel-certs h2,.rel-links h2,.occ-work h2,.occ-salary h2{font-size:var(--text-lg);font-weight:var(--fw-bold);margin:.2em 0 .4em}
.careers,.rel-certs ul,.rel-links ul{margin:.2em 0;padding-left:1.1em}.careers li{margin:2px 0}
.careers-src{font-size:var(--text-sm);margin:.3em 0 0}
.occ-list{columns:2;column-gap:22px}.occ-list li{break-inside:avoid;background:#fff;border:1px solid var(--gray-200);border-radius:8px;padding:8px 11px;margin-bottom:7px}
@media(max-width:560px){.occ-list{columns:1}}
.jobtag{margin:.5em 0 0;font-size:var(--text-sm)}
.pr-badge{display:inline-block;background:var(--gray-400);color:#fff;font-size:var(--text-sm);font-weight:700;padding:1px 6px;border-radius:4px;margin-left:8px;vertical-align:middle;letter-spacing:.05em}
.ad-disclosure{font-size:var(--text-sm);color:var(--muted);background:#fbf6ee;border:1px solid #efe1c8;border-radius:8px;padding:9px 12px;margin:0 0 10px}
.materials{list-style:none;padding:0;margin:.2em 0}
.materials li{display:flex;gap:10px;align-items:flex-start;background:#fff;border:1px solid var(--gray-200);border-radius:8px;padding:9px 12px;margin-bottom:7px}
.mat-kind{flex:0 0 auto;background:var(--accent-light);color:var(--accent-hover);border:1px solid rgba(42,122,110,.18);border-radius:6px;font-size:var(--text-sm);font-weight:var(--fw-semibold);padding:2px 8px;margin-top:2px}
.mat-body{flex:1}.mat-note{display:block;color:var(--muted);font-size:var(--text-sm);margin-top:2px}
.materials a{color:var(--accent);font-weight:var(--fw-semibold);text-decoration:underline;text-underline-offset:2px}
.materials a:hover{color:var(--accent-hover)}
.mat-foot{font-size:var(--text-sm);margin:.4em 0 0}
.rel-certs h3{font-size:var(--text-lg);font-weight:var(--fw-semibold);margin:.7em 0 .2em;color:var(--ink-deep)}
.occ-meta{background:var(--gray-50);border:1px solid var(--gray-200);border-radius:8px;padding:10px 13px;margin:10px 0}
.occ-stats{margin:0 0 6px}.occ-fields{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px}
.occ-stats-label{font-size:var(--text-sm);color:var(--muted);font-weight:600;margin-right:4px}
.occ-stat{display:inline-block;background:var(--accent-light);color:var(--accent-hover);border:1px solid rgba(42,122,110,.18);border-radius:6px;font-size:var(--text-sm);padding:1px 8px;margin-right:6px}
.occ-work{margin:14px 0 0}.occ-work p{margin:.2em 0}
.occ-salary{margin:14px 0 0}
.salary-range{font-size:var(--text-lg);font-weight:700;color:var(--accent);margin:.1em 0}
.occ-salary-note{font-size:var(--text-sm)}
.occ-skills{display:flex;flex-wrap:wrap;gap:2px 0}
.hub-grp{font-size:var(--text-lg);font-weight:var(--fw-bold);margin:1.1em 0 .3em;color:var(--ink-deep)}
.vs-table{width:100%;border-collapse:collapse;margin:14px 0;font-size:var(--text-table);color:var(--ink);table-layout:fixed;--vs-label-w:9rem}
.vs-table col.vs-col-label{width:var(--vs-label-w)}
.vs-table th,.vs-table td{border:1px solid var(--gray-200);padding:10px 14px;text-align:left;vertical-align:top;overflow-wrap:break-word;font-size:var(--text-table);line-height:1.5}
.vs-table thead th{background:var(--gray-100);color:var(--ink-deep);text-align:center}
.vs-table tbody th{background:var(--gray-50);white-space:nowrap;width:var(--vs-label-w)}
.vs-cta{margin:14px 0;display:flex;gap:10px;flex-wrap:wrap}
.feature-nav{margin-top:0;padding-top:0}
.feature-nav h2{font-size:var(--text-lg);margin:.6em 0 .3em}
.feature-nav h3{font-size:var(--text-lg);font-weight:600;color:var(--ink);margin:.9em 0 .3em}
.feature-nav ul{margin:.2em 0 .6em;padding-left:1.1em}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{display:inline-block;padding:5px 11px;border:1px solid var(--gray-300);background:#fff;border-radius:999px;font-size:var(--text-sm);color:var(--ink)}
.chip:hover{background:var(--accent-light);border-color:var(--accent);text-decoration:none}

/* Compare bar + table */
.cmp-add{margin-right:9px;cursor:pointer}.cmp-add input{width:16px;height:16px;vertical-align:middle;cursor:pointer}
.cmpbar{position:fixed;left:0;right:0;bottom:0;background:var(--ink-deep);color:#fff;display:none;z-index:20;border-top:1px solid var(--gray-800)}
.cmpbar.on{display:block}
.cmpbar-inner{max-width:1200px;margin:0 auto;padding:10px var(--page-gutter);display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.cmpbar-lbl{font-size:var(--text-sm);color:var(--on-dark-muted)}
.cmpbar .pill{display:inline-flex;align-items:center;gap:5px;background:var(--gray-800);padding:4px 10px;border-radius:999px;font-size:var(--text-sm);border:1px solid var(--gray-700);color:#fff}
.cmpbar .pill button{background:none;border:none;color:var(--on-dark-muted);cursor:pointer;font:inherit;padding:0 0 0 2px;line-height:1}
.cmpbar .pill button:hover{color:#fff}
.cmpbar .btn{margin-left:auto}
body.cmp-open{padding-bottom:76px}
.cmpbar .btn{background:var(--accent);color:#fff;font-weight:var(--fw-semibold);padding:7px 16px;border-radius:var(--radius)}
.cmpbar .btn:hover{background:var(--accent-hover)}
.cmpbar .btn-ghost{background:transparent;color:var(--on-dark);border:1px solid var(--gray-700);padding:6px 13px;border-radius:var(--radius);cursor:pointer;font:inherit;font-size:var(--text-sm)}
.cmpbar .btn-ghost:hover{background:rgba(255,255,255,.08)}
.cmp-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
table.cmp{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--gray-200);border-radius:10px;table-layout:fixed;--cmp-label-w:9rem;font-size:var(--text-table);color:var(--ink)}
table.cmp col.cmp-col-label{width:var(--cmp-label-w)}
table.cmp th,table.cmp td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--gray-200);border-right:1px solid var(--gray-200);vertical-align:top;font-size:var(--text-table);color:var(--ink);line-height:1.5;overflow-wrap:break-word}
table.cmp thead th{background:var(--gray-100);color:var(--ink-deep);font-weight:700}
table.cmp tbody th{background:var(--gray-50);color:var(--ink);white-space:nowrap;width:var(--cmp-label-w)}

/* Footer */
.site-footer{background:var(--gray-50);border-top:1px solid var(--gray-200);margin-top:auto;color:var(--muted)}
.site-footer-inner{max-width:1200px;margin:0 auto;padding:24px var(--page-gutter) 20px}
.site-footer-brand{font-size:var(--text-md);font-weight:700;color:var(--ink-deep);margin:0 0 10px}
.site-footer-nav{display:flex;flex-wrap:wrap;gap:6px 18px;margin-bottom:12px}
.site-footer-nav a{font-size:var(--text-sm);color:var(--muted);text-decoration:none}
.site-footer-nav a:hover{color:var(--ink);text-decoration:underline;text-underline-offset:2px}
.site-footer-copy{font-size:var(--text-sm);color:var(--muted);line-height:1.5;margin:0}
.site-footer-partners{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px;padding:12px 0;margin:0 0 12px;border-top:1px solid var(--gray-200);border-bottom:1px solid var(--gray-200)}
.sfp-label{font-size:var(--text-sm);font-weight:var(--fw-semibold);color:var(--muted)}
.sfp-links{display:flex;flex-wrap:wrap;gap:4px 14px}
.site-footer-partners a{font-size:var(--text-sm);color:var(--accent);text-decoration:none;font-weight:600}
.site-footer-partners a:hover{text-decoration:underline;text-underline-offset:2px}
/* Partner sites (おすすめ対策サイト) */
.partner-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
@media(max-width:720px){.partner-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:460px){.partner-grid{grid-template-columns:1fr}}
.partner-card{display:flex;flex-direction:column;gap:2px;min-width:0;overflow:hidden;background:#fff;border:1px solid var(--gray-200);border-radius:var(--radius);padding:10px 11px;text-decoration:none;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,.07);transition:border-color .15s,background .15s}
.partner-card:hover{border-color:var(--accent);background:var(--accent-light)}
.partner-card-name,.partner-card-tag{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.partner-card-name{font-size:var(--text-sm);font-weight:var(--fw-semibold);color:var(--ink-deep);line-height:1.35}
.partner-card-tag{font-size:var(--text-sm);color:var(--muted);line-height:1.45}
.partner-ext{font-size:.78em;color:var(--accent);margin-left:5px;font-weight:700}
.partner-detail{margin:0 0 22px;background:var(--accent-light);border:1px solid rgba(35,111,100,.2);border-radius:var(--radius);padding:14px 16px}
.partner-detail .detail-section-title{margin-bottom:8px}
.partner-detail-grid{display:flex;flex-wrap:wrap;gap:10px}
.partner-detail-card{display:flex;flex-direction:column;gap:2px;flex:1 1 220px;background:#fff;border:1px solid rgba(35,111,100,.25);border-radius:var(--radius);padding:11px 13px;text-decoration:none;color:inherit;transition:border-color .15s}
.partner-detail-card:hover{border-color:var(--accent)}
.pd-name{font-size:var(--text-md);font-weight:var(--fw-semibold);color:var(--accent-hover)}
.pd-tag{font-size:var(--text-sm);color:var(--muted);line-height:1.45}
.partner-note{font-size:var(--text-sm);margin:8px 0 0}
/* Detail */
.detail-title{font-size:var(--text-xl);font-weight:700;color:var(--ink-deep);line-height:1.35;margin:.1em 0 8px}
.detail-title-inner{display:inline-flex;align-items:center;gap:10px}
.detail-title-trophy{flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;color:#b8860b;background:#f7f3e8;border-radius:var(--radius)}
.detail-title-trophy .icon-svg{width:18px;height:18px}
.detail-audience{font-size:var(--text-md);color:var(--muted);line-height:1.65;margin:0 0 18px}
.detail-official{margin-top:28px;padding-top:24px;border-top:1px solid var(--gray-200)}
.detail-official .btn{padding:10px 18px;font-size:var(--text-sm)}
.detail-nav{margin-top:36px;padding-top:32px;border-top:1px solid var(--gray-200)}
.detail-nav-block+.detail-nav-block{margin-top:32px;padding-top:32px;border-top:1px solid var(--gray-200)}
.detail-nav-heading,.detail-nav-head{font-size:var(--text-lg);font-weight:var(--fw-bold);color:var(--ink-deep);margin:0 0 18px;line-height:1.35}
.detail-nav-subhead{font-size:var(--text-lg);font-weight:var(--fw-semibold);color:var(--muted);margin:0 0 10px}
.detail-nav-subhead-title{font-size:var(--text-lg);font-weight:var(--fw-bold);color:var(--ink-deep);margin:0 0 12px}
.detail-nav-subhead+.detail-nav-subhead,.detail-link-list+.detail-nav-subhead,.detail-link-grid+.detail-nav-subhead,.detail-compare-row+.detail-nav-subhead{margin-top:22px}
.detail-link-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px}
.detail-link-item{font-size:var(--text-sm);line-height:1.55;color:var(--muted)}
.detail-link-item a{color:var(--accent);font-weight:600;text-decoration:none}
.detail-link-item a:hover{text-decoration:underline;text-underline-offset:2px}
.detail-link-desc{color:var(--muted);font-weight:400}
.detail-link-grid{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 20px}
.detail-link-grid a{display:block;font-size:var(--text-sm);font-weight:600;color:var(--accent);text-decoration:none;line-height:1.45;padding:2px 0}
.detail-link-grid a:hover{text-decoration:underline;text-underline-offset:2px}
.detail-compare-row{font-size:var(--text-sm);color:var(--muted);line-height:1.65;margin:0}
.detail-compare-label{color:var(--muted);font-weight:400}
.detail-compare-row a{color:var(--accent);font-weight:600;text-decoration:none}
.detail-compare-row a:hover{text-decoration:underline;text-underline-offset:2px}
.detail-nav-note{font-size:var(--text-sm);color:var(--muted);margin-top:12px;line-height:1.55}
@media(max-width:560px){.detail-link-grid{grid-template-columns:1fr}}
.detail-facts{margin-bottom:18px}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px}
.fact{background:var(--gray-50);border-radius:8px;padding:9px 11px;border:1px solid var(--gray-200)}
.fact .l{font-size:var(--text-sm);color:var(--muted)}
.fact .v{font-size:var(--text-md);font-weight:var(--fw-semibold);color:var(--ink-deep)}
.detail-actions{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:22px;align-items:center}
.detail-actions .official-cta{margin:0}
.detail-section-title{font-size:var(--text-lg);font-weight:var(--fw-bold);color:var(--ink-deep);margin:0 0 10px}
.detail-related{margin:18px 0 0;border-top:1px solid var(--gray-200);padding-top:14px}
.detail-related h3{font-size:var(--text-lg);font-weight:var(--fw-semibold);margin:.9em 0 .35em;color:var(--ink-deep)}
.detail-related h3:first-of-type{margin-top:.2em}
.detail-related ul{margin:.2em 0;padding-left:1.1em}
.detail-related .more-compare p{margin:.2em 0;line-height:1.55;color:var(--muted);font-size:var(--text-md)}
.detail-related .more-compare a{color:var(--accent);font-weight:600}
.detail-related .more-same ul{columns:2;column-gap:22px}
.detail-related .more-same li{break-inside:avoid;margin:2px 0}
@media(max-width:560px){.detail-related .more-same ul{columns:1}}
.detail-spec{margin-bottom:4px}
.spec-sections{display:flex;flex-direction:column;gap:24px;--spec-label-w:14.5rem}
.spec-section{margin:0}
.page-detail .spec-sections table.spec{table-layout:fixed;width:100%}
.page-detail .spec-sections table.spec col.spec-col-label{width:var(--spec-label-w)}
.page-detail .spec-sections table.spec col.spec-col-value{width:auto}
.page-detail .spec-sections table.spec th{width:var(--spec-label-w);box-sizing:border-box}
.page-detail .spec-sections table.spec td{box-sizing:border-box;width:auto}
.spec-section-title{font-size:var(--text-md);font-weight:var(--fw-semibold);color:var(--ink-deep);margin:0 0 8px;line-height:1.4}
.detail-source{margin-top:22px;padding:14px 0 0;border-top:1px solid var(--gray-200);font-size:var(--text-sm);color:var(--muted);line-height:1.65}
.detail-source p{margin:0 0 5px}.detail-source .k{font-weight:600;color:var(--muted)}
.detail-source a{color:var(--ink);text-decoration:underline;text-underline-offset:2px}
.detail-source-note{margin-top:8px;color:var(--muted);font-size:var(--text-sm)}
.detail-points{margin:0 0 22px}
.point-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:7px}
.point-list li{position:relative;padding:8px 12px 8px 32px;background:var(--accent-light);border:1px solid rgba(42,122,110,.15);border-radius:var(--radius);font-size:var(--text-md);color:var(--ink);line-height:1.55}
.point-list li::before{content:"✓";position:absolute;left:12px;top:8px;color:var(--accent);font-weight:700}
.detail-faq{margin:0 0 22px}
.faq-item{border:1px solid var(--gray-200);border-radius:var(--radius);margin-bottom:8px;background:#fff;overflow:hidden}
.faq-item summary{cursor:pointer;padding:12px 14px;font-weight:600;color:var(--ink-deep);font-size:var(--text-md);list-style:none;position:relative;padding-right:36px}
.faq-item summary::-webkit-details-marker{display:none}
.faq-item summary::after{content:"＋";position:absolute;right:14px;top:12px;color:var(--accent);font-weight:700}
.faq-item[open] summary::after{content:"−"}
.faq-item summary:hover{background:var(--gray-50)}
.faq-a{padding:0 14px 13px;color:var(--muted);line-height:1.7;font-size:var(--text-sm)}
.btn-sm{padding:7px 14px;font-size:var(--text-sm)}
/* 一覧の行＋比較ボタン */
.results li{display:flex;gap:12px;align-items:center}
.results li.empty-state{display:block;text-align:center;color:var(--muted);background:var(--gray-50);border:1px dashed var(--gray-300);padding:22px 16px;line-height:1.75}
.result-main{flex:1;min-width:0}
.result-label{display:inline-block;font-size:var(--text-sm);font-weight:600;color:var(--muted);background:var(--gray-100);border:1px solid var(--gray-300);border-radius:4px;padding:1px 6px;margin-left:6px;vertical-align:middle}
.cmp-add-btn{flex-shrink:0;min-width:78px;padding:8px 10px;font-size:var(--text-sm);font-weight:600;line-height:1.2;border:1px solid var(--accent);border-radius:8px;background:var(--white);color:var(--accent);cursor:pointer;font-family:inherit;text-align:center;transition:border-color .15s,background .15s,color .15s}
.cmp-add-btn:hover{background:var(--gray-50)}
.cmp-add-btn.is-active{background:var(--accent);border-color:var(--accent);color:#fff}
/* 比較ページの結論カード */
.cmp-verdict{margin:2px 0 18px}
.cmp-verdict-title{font-size:var(--text-sm);font-weight:600;color:var(--ink-deep);margin:0 0 10px}
.cmp-verdict-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}
.cmp-verdict-card{border:1px solid var(--gray-200);border-radius:var(--radius);padding:12px 14px;background:var(--white)}
.cmp-verdict-card .pick{font-size:var(--text-sm);font-weight:700;color:var(--accent-hover);margin-bottom:4px}
.cmp-verdict-card .pickname{font-size:var(--text-md);font-weight:var(--fw-semibold);color:var(--ink-deep);line-height:1.4}
.cmp-verdict-card .pickname a{color:var(--ink-deep);text-decoration:underline;text-underline-offset:2px}
.cmp-verdict-card .why{font-size:var(--text-sm);color:var(--muted);margin-top:3px;line-height:1.5}
/* Detail page typography（詳細ページのフォント・色統一） */
.page-detail{font-size:var(--text-md);color:var(--ink);line-height:1.7;font-weight:var(--fw-regular)}
.page-detail .detail-title{font-size:var(--text-xl);color:var(--ink-deep);margin:.1em 0 6px}
.page-detail .detail-audience{font-size:var(--text-md);color:var(--ink);line-height:1.7;margin:0 0 16px}
.page-detail .crumbs{font-size:var(--text-sm);color:var(--muted);margin-bottom:8px}
.page-detail .crumbs a{color:var(--ink)}
.page-detail .note-muted,.page-detail .muted{font-size:inherit;color:var(--muted);font-weight:400}
.page-detail .fact .l{font-size:var(--text-sm);color:var(--muted)}
.page-detail .fact .v{font-size:var(--text-md);font-weight:600;color:var(--ink)}
.page-detail table.spec{font-size:var(--text-table);color:var(--ink);line-height:1.55}
.page-detail table.spec th{background:var(--table-head-bg);color:var(--ink);font-weight:var(--fw-regular);font-size:var(--text-table)}
.page-detail table.spec th .spec-th-inner{display:inline-flex;align-items:center;gap:7px}
.page-detail table.spec th .spec-th-icon{flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;color:var(--ink);opacity:.55}
.page-detail table.spec th .spec-th-icon .icon-svg{width:15px;height:15px}
.page-detail table.spec th .spec-th-text{font-weight:inherit;line-height:inherit}
.page-detail table.spec td{color:var(--ink);font-size:var(--text-table);font-weight:var(--fw-regular);vertical-align:middle;line-height:1.55}
.page-detail table.spec tr.spec-row{cursor:pointer;transition:background-color .12s ease}
.page-detail table.spec tr.spec-row:hover th,.page-detail table.spec tr.spec-row:hover td{background:var(--table-hover-bg)}
.page-detail table.spec tr.spec-row.is-active th,.page-detail table.spec tr.spec-row.is-active td{background:var(--accent-light)}
.page-detail table.spec tr.spec-row:focus-visible{outline:2px solid var(--accent-ring);outline-offset:-2px}
.page-detail table.spec .badge,.page-detail table.spec .badge-national,.page-detail table.spec .badge-public,.page-detail table.spec .badge-private,.page-detail table.spec .badge-unknown,.page-detail table.spec .badge-overseas{color:var(--ink);background:#fff;border-color:var(--table-border);font-size:inherit;font-weight:var(--fw-regular)}
.page-detail table.spec .tag-chip,.page-detail table.spec .tag-ind{font-size:inherit;font-weight:var(--fw-regular);color:var(--ink);background:var(--gray-100);border-color:var(--table-border)}
.page-detail table.spec a.tag-chip:hover{background:var(--table-hover-bg);border-color:var(--table-border);color:var(--ink)}
.page-detail table.spec .spec-list{list-style:disc;margin:.15em 0 .3em;padding-left:1.25em;font-size:inherit}
.page-detail table.spec .spec-list li{margin:2px 0;line-height:inherit;font-size:inherit;color:var(--ink)}
.page-detail table.spec .materials{margin:.15em 0 .25em;font-size:inherit}
.page-detail table.spec .materials li{display:block;background:none;border:none;border-radius:0;padding:2px 0;margin:0 0 4px;line-height:inherit;font-size:inherit;font-weight:var(--fw-regular);color:var(--ink)}
.page-detail table.spec .materials a{color:var(--accent);font-weight:var(--fw-semibold);font-size:inherit;text-decoration:underline;text-underline-offset:2px}
.page-detail table.spec .spec-list a,.page-detail table.spec .jobtag a{color:var(--ink);font-weight:var(--fw-regular);font-size:inherit;text-decoration:underline;text-underline-offset:2px}
.page-detail table.spec .materials a:hover{color:var(--accent-hover);opacity:1}
.page-detail table.spec .spec-list a:hover,.page-detail table.spec .jobtag a:hover{color:var(--ink);opacity:.85}
.page-detail table.spec .mat-kind{display:inline;background:none;border:none;padding:0;margin:0;font-weight:var(--fw-regular);font-size:inherit;color:var(--ink)}
.page-detail table.spec a{font-weight:var(--fw-regular);color:var(--ink)}
.page-detail table.spec .mat-kind::after{content:"："}
.page-detail table.spec .muted,.page-detail table.spec .note-muted{font-size:inherit;font-weight:var(--fw-regular);color:var(--muted)}
.page-detail table.spec .materials .muted,.page-detail table.spec .materials .note-muted{font-size:inherit;font-weight:var(--fw-regular);color:var(--muted)}
.page-detail table.spec .mat-foot,.page-detail table.spec .careers-src,.page-detail table.spec .jobtag,.page-detail table.spec .detail-source-note{margin-top:6px;font-size:inherit;font-weight:var(--fw-regular);color:var(--muted);line-height:inherit}
.page-detail table.spec .ad-disclosure{margin:0 0 6px;padding:8px 10px;font-size:inherit;font-weight:var(--fw-regular);color:var(--muted);line-height:inherit;background:var(--table-head-bg);border:1px solid var(--table-border);border-radius:var(--radius)}
.page-detail .tag-chip{font-size:var(--text-sm);background:var(--gray-50);color:var(--ink);border-color:var(--gray-200)}
.page-detail .tag-ind{background:var(--gray-50);color:var(--ink);border-color:var(--gray-200)}
.page-detail a.tag-chip:hover{background:var(--gray-100);border-color:var(--gray-300)}
.page-detail .point-list li{font-size:var(--text-md);color:var(--ink);background:var(--gray-50);border-color:var(--gray-200)}
.page-detail .point-list li::before{color:var(--muted)}
.page-detail .faq-item summary{font-size:var(--text-md);color:var(--ink)}
.page-detail .faq-a{font-size:var(--text-md);color:var(--muted)}
.page-detail .detail-link-item,.page-detail .detail-link-grid a,.page-detail .detail-compare-row{font-size:var(--text-sm);color:var(--muted)}
.page-detail .detail-link-desc,.page-detail .detail-nav-note,.page-detail .detail-source-note{font-size:var(--text-sm);color:var(--muted)}
.page-detail .detail-source{font-size:var(--text-sm);color:var(--muted)}
.page-detail .careers-sec,.page-detail .materials-sec{margin-top:20px;padding-top:14px}
.page-detail .careers-sec h2,.page-detail .materials-sec h2{margin:.2em 0 .5em}
.page-detail .careers li,.page-detail .jobtag{font-size:var(--text-md);color:var(--ink)}
.page-detail table.spec .careers li,.page-detail table.spec .jobtag{font-size:inherit;color:var(--ink)}
.page-detail .careers-src,.page-detail .mat-foot{font-size:var(--text-sm);color:var(--muted)}
.page-detail .mat-kind{background:var(--gray-100);color:var(--muted);border-color:var(--gray-200);font-size:var(--text-sm)}
.page-detail .mat-body{font-size:var(--text-md)}
.page-detail .mat-note{font-size:var(--text-sm);color:var(--muted)}
.page-detail .ad-disclosure{font-size:var(--text-sm);color:var(--muted);background:var(--gray-50);border-color:var(--gray-200)}
.page-detail .pd-name{font-size:var(--text-md);font-weight:var(--fw-semibold);color:var(--ink)}
.page-detail .pd-tag{font-size:var(--text-sm);color:var(--muted)}
.page-detail .partner-note{font-size:var(--text-sm);color:var(--muted)}
.page-detail .detail-roadmap{margin:0 0 20px}
.page-detail .detail-roadmap .roadmap{margin:0}
.page-detail .detail-roadmap .roadmap h3{margin:0 0 10px}
.page-detail .detail-related .more-compare p{font-size:var(--text-sm);color:var(--muted)}
.page-detail .provenance{font-size:var(--text-sm);color:var(--muted)}
.page-detail .updated{font-size:var(--text-sm);color:var(--muted)}
/* ===== モバイル最適化（可読性・余白・タップ領域） ===== */
@media(max-width:600px){
  /* 小さめの文字を底上げして読みやすく（キャプション・メタ・バッジ等） */
  :root{--text-sm:0.9375rem}
  /* ヒーロー：余白を詰め、本文を読みやすいサイズに */
  .hero{padding:22px 0 14px}
  .hero h1{margin-bottom:10px}
  .hero-sub{font-size:var(--text-md);line-height:1.7}
  .hero-search{margin-top:14px;max-width:none}
  /* セクション間隔をモバイル向けに調整 */
  .block{margin-bottom:24px}.block-primary{margin-bottom:30px}.block-secondary{margin-bottom:26px}
  .block-head{margin-bottom:10px}
  /* 人気の資格は1列にして各カードの情報を見やすく */
  .popular-grid{grid-template-columns:1fr;gap:10px}
  .pop-card{padding:14px 16px}
  .pop-card-facts li{grid-template-columns:5.5em 1fr}
  /* 比較カードのタイトルが詰まらないように */
  .compare-names{font-size:var(--text-md)}
  /* 一覧・ランキングのタップ領域と余白 */
  .cl-link{padding:13px 14px}
  /* 詳細：本文サイズと余白 */
  .page-detail .detail-audience{font-size:var(--text-md);line-height:1.7}
  .page-detail .point-list li{font-size:var(--text-md)}
  .page-detail .faq-item summary,.page-detail .faq-a{font-size:var(--text-md)}
  /* 比較バーが内容に被らないよう余白を増やす */
  body.cmp-open{padding-bottom:96px}
}

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
    _pop_ranked = sorted((r for r in indexable if applicants_num(r) is not None),
                         key=lambda r: (-(applicants_num(r) or 0), r["name"]))
    popular_set = {r["slug"] for r in _pop_ranked[:80]}
    payload = [{
        "popular": (r["slug"] in popular_set),
        "slug": r["slug"], "name": r["name"], "major": r["major_category"],
        "category": r["category"], "type": r["type"],
        "authority": r["authority"], "official_url": r["official_url"],
        "eligibility": r["eligibility"], "exam_format": r["exam_format"],
        "fee": fmt_nums_in_text(r["fee"]), "pass_rate": pass_rate_display(r["pass_rate"]),
        "frequency": r["frequency"],
        "status": r.get("status", ""),
        "tags": cert_tags(r),
        "industries": industry_tags(r),
        "difficulty": _diff_label(r),
        "applicants": fmt_nums_in_text((EXAM.get(r["slug"], {}) or {}).get("applicants", "")),
        "study_hours": fmt_nums_in_text((STUDY.get(r["slug"], {}) or {}).get("study_hours", "")),
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
        (SITE / "c" / f'{r["slug"]}.html').write_text(build_detail(r, popular_set), encoding="utf-8")

    # 集約: 分野別一覧
    (SITE / "bunya").mkdir()
    cat_pages = build_category_pages(indexable, popular_set)
    for slug, htmlc in cat_pages.items():
        (SITE / "bunya" / f"{slug}.html").write_text(htmlc, encoding="utf-8")

    # 特集
    (SITE / "feature").mkdir()
    feat_pages = build_feature_pages(indexable, popular_set)
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
<p>掲載内容は参考情報です。受験料・合格率・制度・日程等は変更される場合があるため、出願前に各資格の公式情報で必ずご確認ください。各詳細ページに最終確認日と情報源を表示しています。本サイトの情報の利用により生じたいかなる損害についても責任を負いかねます。</p></section>

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
