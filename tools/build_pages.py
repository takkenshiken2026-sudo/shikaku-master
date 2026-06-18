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
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "certifications.csv"
CAREERS_CSV = ROOT / "data" / "careers.csv"
SITE = ROOT / "site"
BRAND = ROOT / "brand"

# 厚労省 職業情報提供サイト（job tag）— 関連職業の公式ディスカバリ導線
JOBTAG_URL = "https://shigoto.mhlw.go.jp/User/Search/Top"

SITE_NAME = "資格カタログ"
SITE_DESC = "日本の資格を「探せる・絞れる・比べられる」資格データベース。受験料・試験形式・受験資格・合格率・実施団体・公式サイトを公式の一次情報に基づき掲載。"
BASE_URL = "https://shikaku-master.jp"
CUSTOM_DOMAIN = "shikaku-master.jp"
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


def page_shell(title: str, body: str, depth: int, noindex: bool = True,
               desc: str = "", path: str = "", jsonld=None) -> str:
    base = "../" * depth
    robots = ('<meta name="robots" content="noindex">\n' if noindex else "")
    desc = desc or SITE_DESC
    canon = BASE_URL + "/" + path
    og = (f'<link rel="canonical" href="{esc(canon)}">\n'
          f'<meta property="og:type" content="website">\n'
          f'<meta property="og:site_name" content="{esc(SITE_NAME)}">\n'
          f'<meta property="og:title" content="{esc(title)}">\n'
          f'<meta property="og:description" content="{esc(desc)}">\n'
          f'<meta property="og:url" content="{esc(canon)}">\n'
          f'<meta property="og:locale" content="ja_JP">\n'
          f'<meta name="twitter:card" content="summary">\n')
    ld = ""
    if jsonld:
        for obj in (jsonld if isinstance(jsonld, list) else [jsonld]):
            ld += f'<script type="application/ld+json">{json.dumps(obj, ensure_ascii=False)}</script>\n'
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0d47a1">
{robots}<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{og}<link rel="icon" href="{base}assets/favicon.ico" sizes="32x32">
<link rel="icon" href="{base}assets/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{base}assets/apple-touch-icon.png">
<link rel="stylesheet" href="{base}assets/app.css">
{ld}</head>
<body>
<header class="site-header"><a href="{base}index.html" class="logo">{esc(SITE_NAME)}</a>
<span class="tagline">日本の資格を探せる・絞れる・比べられる</span></header>
<main class="container">
{body}
</main>
<footer class="site-footer">出典: 厚生労働省 ハローワーク「免許・資格コード一覧」を正本シードに、各資格の公式の一次情報に基づき整備。
最新の制度・受験料・日程・合格率は各資格の公式サイトで必ずご確認ください。</footer>
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
    diff = difficulty(row)
    if diff:
        dlabel, dcls = diff
        spec.append(("難易度の目安",
                     f'<span class="diff-badge {dcls}">{esc(dlabel)}</span>'
                     f' <span class="muted">（公表合格率 {esc(row["pass_rate"])} に基づく簡易目安）</span>'))
    src = row.get("source_checked_at", "")
    if src:
        spec.append(("情報確認日", esc(src) + ' <span class="muted">（公式の一次情報に基づき確認）</span>'))
    rows_html = "".join(f"<tr><th>{esc(k)}</th><td>{v}</td></tr>" for k, v in spec)

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

    # ユニーク本文（概要）
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

    # 活かせる仕事・キャリア（ハイブリッド: キュレーション + job tag 導線）
    cur = CAREERS.get(row["slug"])
    if cur:
        jobs = [c.strip() for c in cur["careers"].split("、") if c.strip()]
        jobs_html = "".join(f"<li>{esc(j)}</li>" for j in jobs)
        src_html = ""
        if cur["source"]:
            src_html = (f'<p class="muted careers-src">出典: '
                        f'<a href="{esc(cur["source"])}" rel="nofollow noopener" target="_blank">'
                        f'公式・job tag 等</a></p>')
        careers_body = f'<ul class="careers">{jobs_html}</ul>{src_html}'
    else:
        careers_body = ('<p class="muted">この資格を要件・推奨とする職業は個別に精査中です。'
                        '関連する職業は、厚生労働省の職業情報提供サイト（job tag）で'
                        '資格名から検索できます。</p>')
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
    rel += [("../feature/cheap.html", "受験料が安い資格ランキング"),
            ("../feature/high-pass.html", "合格率が高い資格")]
    rel_links = ('<nav class="rel-links"><h2>関連リンク</h2><ul>'
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
    if row["frequency"]:
        qa.append((f"{name}はいつ実施されますか？", row["frequency"]))
    if row["authority"]:
        qa.append((f"{name}の実施団体はどこですか？", row["authority"]))
    faq = ({"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q,
                            "acceptedAnswer": {"@type": "Answer", "text": a}}
                           for q, a in qa]} if qa else None)

    body = f"""<nav class="crumbs"><a href="../index.html">トップ</a> ›
<a href="../index.html?major={esc(major)}">{esc(major)}</a> › {esc(name)}</nav>
<h1>{esc(name)}</h1>
{updated_html}<p class="lead">{lead}</p>
{fact_p}
<table class="spec">{rows_html}</table>
{cta}{provenance}
{careers_section}
{rel_links}
<section class="related"><h2>同じカテゴリの資格</h2><ul id="related"></ul></section>
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
"""
    bits = [b for b in (("受験料" + row["fee"]) if row["fee"] else "",
                        ("合格率" + row["pass_rate"]) if row["pass_rate"] else "") if b]
    desc = (f"{name}（{major}分野・{label}）の試験情報。"
            + ("／".join(bits) + "。" if bits else "")
            + "受験料・試験形式・受験資格・合格率・実施団体・公式サイトを掲載。")
    breadcrumb = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "トップ", "item": BASE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": major,
             "item": f"{BASE_URL}/bunya/{bslug}.html"},
            {"@type": "ListItem", "position": 3, "name": name},
        ],
    }
    ld = [breadcrumb] + ([faq] if faq else [])
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


def _list_items(items, depth):
    """資格カードのリストHTML。publishedは受験料/合格率を併記し★表示。"""
    base = "../" * depth
    out = []
    for r in items:
        pub = r.get("status") == "published"
        extra = ""
        if pub:
            bits = [b for b in (r.get("fee"), (("合格率" + r["pass_rate"]) if r.get("pass_rate") else "")) if b]
            extra = ('<span class="meta">★データ掲載 ' + esc(" / ".join(bits)) + "</span>") if bits else '<span class="meta">★データ掲載</span>'
        else:
            extra = f'<span class="meta">{esc(r["category"])}</span>'
        out.append(
            f'<li><a href="{base}c/{esc(r["slug"])}.html">{esc(r["name"])}</a> '
            f'{_badge(r["type"])}{extra}</li>'
        )
    return '<ul class="results">' + "".join(out) + "</ul>"


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
        pages[slug] = page_shell(
            f"{major}の資格一覧｜{SITE_NAME}", body, depth=1, noindex=False,
            desc=f"「{major}」分野の資格 {len(items)} 件（うち公式データ掲載 {npub} 件）。"
                 f"受験料・試験形式・受験資格・合格率を一覧・比較できます。",
            path=f"bunya/{slug}.html")
    return pages


# 特集・ランキングページの定義（トップのナビとも共有）
FEATURE_NAV = [
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


def build_feature_pages(indexable):
    """特集・ランキングページ（site/feature/<slug>.html）。"""
    pub = [r for r in indexable if r["status"] == "published"]
    pages = {}

    def page(slug, title, h1, intro, items, desc):
        body = (
            f'<nav class="crumbs"><a href="../index.html">トップ</a> › 特集</nav>'
            f"<h1>{esc(h1)}</h1>"
            f'<p class="lead">{intro}</p>'
            + _list_items(items, depth=1)
            + '<p class="muted" style="margin-top:14px">※受験料・合格率は公式の一次情報に基づきますが、'
              '最新の金額・制度・日程は各資格の公式サイトで必ずご確認ください。</p>'
        )
        pages[slug] = page_shell(f"{title}｜{SITE_NAME}", body, depth=1,
                                 noindex=False, desc=desc,
                                 path=f"feature/{slug}.html")

    # 受験料が安い順（代表額のあるものを昇順・上位120）
    cheap = sorted((r for r in pub if fee_yen(r) is not None),
                   key=lambda r: (fee_yen(r), r["name"]))[:120]
    page("cheap", "受験料が安い資格ランキング", "受験料が安い資格ランキング",
         f"受験料（代表額）が安い順に並べた資格ランキング。データ掲載分の上位 {len(cheap)} 件。"
         "受験料は級・方式で異なる場合があります。",
         cheap, "受験料が安い資格を安い順にランキング。受験料・合格率・公式情報を掲載。")

    # 合格率が高い順
    hi = sorted((r for r in pub if pass_pct(r) is not None),
                key=lambda r: (-pass_pct(r), r["name"]))[:120]
    page("high-pass", "合格率が高い資格", "合格率が高い資格",
         f"公表されている合格率が高い順に並べた資格一覧（上位 {len(hi)} 件）。"
         "合格率は実施回・年度により変動します。",
         hi, "合格率が高い資格を高い順に一覧。受験料・合格率・公式情報を掲載。")

    # 合格率が低い順（難関）
    lo = sorted((r for r in pub if pass_pct(r) is not None),
                key=lambda r: (pass_pct(r), r["name"]))[:120]
    page("hard", "合格率が低い難関資格", "合格率が低い難関資格",
         f"公表されている合格率が低い（難易度が高い）順に並べた資格一覧（上位 {len(lo)} 件）。",
         lo, "合格率が低い難関資格を一覧。受験料・合格率・公式情報を掲載。")

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
    return pages


def build_index(rows) -> str:
    pub = sum(1 for r in rows if r.get("status") == "published")
    majors = sorted({r["major_category"] for r in rows})
    cat_links = " ".join(
        f'<a class="chip" href="bunya/{MAJOR_SLUGS.get(m, "other")}.html">{esc(m)}</a>'
        for m in majors)
    feat_links = "".join(
        f'<li><a href="feature/{slug}.html">{esc(label)}</a></li>'
        for slug, label in FEATURE_NAV)
    body = f"""<h1>日本の資格カタログ</h1>
<p class="lead">資格名で検索、または分野・区分で絞り込み・並び替えできます。現在 <strong id="count">-</strong> 件を収録（うち公式データ掲載 {pub} 件）。受験料・試験形式・受験資格・合格率・公式サイトを掲載しています。</p>
<div class="controls">
  <input id="q" type="search" placeholder="資格名で検索（例: 簿記, 電気, ボイラー）">
  <select id="major"><option value="">分野（すべて）</option></select>
  <select id="type"><option value="">区分（すべて）</option></select>
  <select id="sort">
    <option value="">並び順（標準）</option>
    <option value="fee-asc">受験料が安い順</option>
    <option value="fee-desc">受験料が高い順</option>
    <option value="pass-desc">合格率が高い順</option>
    <option value="pass-asc">合格率が低い順</option>
  </select>
</div>
<div class="filters">
  <label><input type="checkbox" id="f-pub"> データ掲載のみ</label>
  <label><input type="checkbox" id="f-noreq"> 受験資格なし</label>
  <label><input type="checkbox" id="f-cbt"> CBT・ネット試験</label>
</div>
<p id="status" class="muted"></p>
<p class="muted hint">行頭のチェックを入れて資格を選ぶと、最大4件まで並べて比較できます。</p>
<ul id="results" class="results"></ul>
<div id="cmpbar" class="cmpbar"></div>
<section class="feature-nav">
  <h2>特集・ランキング</h2>
  <ul class="feat-list">{feat_links}</ul>
  <h2>分野から探す</h2>
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
         "logo": BASE_URL + "/assets/favicon.svg"},
    ]
    return page_shell(SITE_NAME, body, depth=0, noindex=False,
                      desc=SITE_DESC, path="", jsonld=site_ld)


def build_compare() -> str:
    body = """<nav class="crumbs"><a href="index.html">トップ</a> › 比較</nav>
<h1>資格を比較</h1>
<p class="lead">選択した資格を並べて比較します（最大4件）。数値・制度は各資格の公式情報で必ずご確認ください。</p>
<div id="cmp" class="cmp-wrap"></div>
<p style="margin-top:18px"><a href="index.html">← 検索に戻って選び直す</a></p>
<script src="assets/compare.js"></script>
"""
    return page_shell(f"資格を比較｜{SITE_NAME}", body, depth=0, noindex=False,
                      desc="選んだ資格を受験料・試験形式・受験資格・合格率などで横並びに比較できます。",
                      path="compare.html")


SEARCH_JS = """(function(){
  var q=document.getElementById('q'),majorSel=document.getElementById('major'),
      typeSel=document.getElementById('type'),sortSel=document.getElementById('sort'),
      fPub=document.getElementById('f-pub'),fNoreq=document.getElementById('f-noreq'),
      fCbt=document.getElementById('f-cbt'),results=document.getElementById('results'),
      status=document.getElementById('status'),count=document.getElementById('count'),
      bar=document.getElementById('cmpbar');
  var DATA=[], MAX=4, selected=loadSel();
  function loadSel(){try{return new Set(JSON.parse(localStorage.getItem('cmp')||'[]'));}catch(e){return new Set();}}
  function saveSel(){try{localStorage.setItem('cmp',JSON.stringify([].slice.call(selected)));}catch(e){}}
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function opt(sel,v){var o=document.createElement('option');o.value=v;o.textContent=v;sel.appendChild(o);}
  function feeNum(x){var m=(x.fee||'').replace(/,/g,'').match(/([0-9]+)\\s*円/);return m?parseInt(m[1],10):null;}
  function passNum(x){var m=(x.pass_rate||'').replace(/,/g,'').match(/([0-9]+(?:\\.[0-9]+)?)\\s*%/);return m?parseFloat(m[1]):null;}
  function isNoreq(x){return /受験資格なし|受験(資格)?(の)?制限なし|誰でも|制限なし/.test(x.eligibility||'');}
  function isCbt(x){return /CBT|ネット試験|IBT/.test(x.exam_format||'');}
  function render(){
    var t=(q.value||'').trim().toLowerCase(),mj=majorSel.value,tp=typeSel.value,sk=sortSel.value;
    var out=DATA.filter(function(x){
      if(mj&&x.major!==mj)return false;
      if(tp&&x.type!==tp)return false;
      if(t&&x.name.toLowerCase().indexOf(t)<0)return false;
      if(fPub.checked&&x.status!=='published')return false;
      if(fNoreq.checked&&!isNoreq(x))return false;
      if(fCbt.checked&&!isCbt(x))return false;
      return true;
    });
    if(sk){
      var key=sk.indexOf('fee')===0?feeNum:passNum, asc=sk.indexOf('asc')>=0;
      out=out.slice().sort(function(a,b){
        var va=key(a),vb=key(b);
        if(va===null&&vb===null)return 0;
        if(va===null)return 1; if(vb===null)return -1;
        return asc?va-vb:vb-va;
      });
    }
    status.textContent=out.length+' 件';
    results.innerHTML=out.slice(0,300).map(function(x){
      var ck=selected.has(x.slug)?' checked':'';
      var extra=x.status==='published'?[feeNum(x)!==null?esc(x.fee):'',passNum(x)!==null?'合格率'+esc(x.pass_rate):''].filter(Boolean).join(' / '):'';
      return '<li><label class="cmp-add" title="比較に追加"><input type="checkbox" data-slug="'+x.slug+'"'+ck+'></label>'+
        '<a href="c/'+x.slug+'.html">'+esc(x.name)+'</a>'+
        '<span class="meta"><span class="badge b-'+x.type+'">'+x.type+'</span> '+esc(x.major)+' / '+esc(x.category)+(extra?' ・ '+extra:'')+'</span></li>';
    }).join('')||'<li class="muted">該当なし</li>';
    if(out.length>300) results.innerHTML+='<li class="muted">…他 '+(out.length-300)+' 件（絞り込んでください）</li>';
  }
  function updateBar(){
    if(!bar)return;
    var n=selected.size;
    if(!n){bar.classList.remove('on');bar.innerHTML='';return;}
    bar.classList.add('on');
    bar.innerHTML='<span>'+n+' 件を選択中（最大'+MAX+'）</span>'+
      '<a class="btn" href="compare.html?ids='+[].slice.call(selected).join(',')+'">比較する</a>'+
      '<button type="button" id="cmpclear" class="btn-ghost">クリア</button>';
    document.getElementById('cmpclear').onclick=function(){selected.clear();saveSel();render();updateBar();};
  }
  results.addEventListener('change',function(e){
    var cb=e.target;
    if(!cb||cb.tagName!=='INPUT')return;
    var slug=cb.getAttribute('data-slug');
    if(cb.checked){
      if(selected.size>=MAX&&!selected.has(slug)){cb.checked=false;alert('比較は最大'+MAX+'件までです');return;}
      selected.add(slug);
    } else selected.delete(slug);
    saveSel();updateBar();
  });
  fetch('data/certifications.json').then(function(r){return r.json();}).then(function(all){
    DATA=all; count.textContent=all.length;
    var majors={},types={};
    all.forEach(function(x){majors[x.major]=1;types[x.type]=1;});
    Object.keys(majors).sort().forEach(function(v){opt(majorSel,v);});
    ['国家','公的','民間','要確認'].forEach(function(v){if(types[v])opt(typeSel,v);});
    var p=new URLSearchParams(location.search);
    if(p.get('q'))q.value=p.get('q');
    if(p.get('major'))majorSel.value=p.get('major');
    render();updateBar();
  });
  [q,majorSel,typeSel,sortSel].forEach(function(el){el.addEventListener('input',render);});
  [fPub,fNoreq,fCbt].forEach(function(el){el.addEventListener('change',render);});
})();
"""


COMPARE_JS = """(function(){
  var p=new URLSearchParams(location.search);
  var ids=(p.get('ids')||'').split(',').filter(Boolean);
  var root=document.getElementById('cmp');
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  if(!ids.length){root.innerHTML='<p class="muted">比較する資格が選択されていません。<a href="index.html">トップ</a>で資格にチェックを入れて選んでください。</p>';return;}
  var FIELDS=[['区分','type'],['分野','major'],['カテゴリ','category'],
    ['実施団体','authority'],['受験資格','eligibility'],['試験形式','exam_format'],
    ['受験料','fee'],['合格率','pass_rate'],['実施頻度','frequency']];
  fetch('data/certifications.json').then(function(r){return r.json();}).then(function(all){
    var map={};all.forEach(function(x){map[x.slug]=x;});
    var items=ids.map(function(s){return map[s];}).filter(Boolean);
    if(!items.length){root.innerHTML='<p class="muted">該当する資格データが見つかりませんでした。</p>';return;}
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

APP_CSS = """*{box-sizing:border-box}body{margin:0;padding-bottom:64px;font-family:system-ui,-apple-system,"Hiragino Kaku Gothic ProN",Meiryo,sans-serif;color:#1b2430;line-height:1.7;background:#f7f8fa}
a{color:#1565c0;text-decoration:none}a:hover{text-decoration:underline}
.site-header{background:#0d47a1;color:#fff;padding:14px 20px;display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.site-header .logo{color:#fff;font-weight:700;font-size:1.15rem}.tagline{color:#cfe0fb;font-size:.85rem}
.container{max-width:920px;margin:0 auto;padding:22px 18px}
h1{font-size:1.5rem;margin:.2em 0 .4em}.lead{color:#43505f}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}
.controls input,.controls select{padding:10px 12px;border:1px solid #c5ccd6;border-radius:8px;font-size:1rem}
.controls input{flex:1 1 260px}
.results{list-style:none;padding:0;margin:0}
.results li{background:#fff;border:1px solid #e6e9ef;border-radius:10px;padding:12px 14px;margin-bottom:8px}
.results li a{font-weight:600}.results .meta{display:block;color:#6b7682;font-size:.82rem;margin-top:3px}
.badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:.75rem;font-weight:700;color:#fff;vertical-align:middle}
.badge-national,.b-国家{background:#c62828}.badge-public,.b-公的{background:#1565c0}
.badge-private,.b-民間{background:#2e7d32}.badge-unknown,.b-要確認{background:#8a939e}.badge-overseas{background:#6a1b9a}
.crumbs{font-size:.85rem;color:#6b7682;margin-bottom:8px}
table.spec{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e6e9ef;border-radius:10px;overflow:hidden}
table.spec th,table.spec td{text-align:left;padding:10px 14px;border-bottom:1px solid #eef1f5;vertical-align:top}
table.spec th{width:34%;background:#f2f5fa;color:#3a4757;font-weight:600;white-space:nowrap}
.muted{color:#98a1ad}.related{margin-top:24px}.related ul{padding-left:1.1em}
.official-cta{margin:16px 0 6px}
.btn-official{display:inline-block;background:#0d47a1;color:#fff;font-weight:700;padding:11px 20px;border-radius:8px}
.btn-official:hover{background:#0b3c8a;text-decoration:none}
.provenance{font-size:.82rem;color:#6b7682;background:#f2f5fa;border:1px solid #e1e8f2;border-radius:8px;padding:11px 14px;margin:10px 0 0}
.feat-list{margin:.2em 0 .6em;padding-left:1.1em}.feat-list li{margin:2px 0}
.updated{font-size:.82rem;color:#6b7682;margin:.1em 0 .6em}.updated .muted{margin-left:.4em}
.diff-badge{display:inline-block;font-weight:700;font-size:.82rem;padding:2px 9px;border-radius:11px;color:#fff}
.diff-veryhard{background:#b71c1c}.diff-hard{background:#e65100}.diff-mid{background:#f9a825;color:#3a2c00}
.diff-easy{background:#388e3c}.diff-veryeasy{background:#1565c0}
.careers-sec{margin:18px 0 0;border-top:1px solid #e6e9ef;padding-top:12px}
.careers-sec h2{font-size:1.05rem;margin:.2em 0 .4em}
.careers{margin:.2em 0;padding-left:1.1em}.careers li{margin:2px 0}
.careers-src{font-size:.8rem;margin:.3em 0 0}
.jobtag{margin:.5em 0 0;font-size:.92rem}
.rel-links{margin:18px 0 0;border-top:1px solid #e6e9ef;padding-top:12px}
.rel-links h2{font-size:1.05rem;margin:.2em 0 .3em}
.rel-links ul{margin:.2em 0;padding-left:1.1em}.rel-links li{margin:2px 0}
.site-footer{max-width:920px;margin:30px auto;padding:16px 18px;color:#7a838f;font-size:.8rem;border-top:1px solid #e6e9ef}
.feature-nav{margin-top:28px;border-top:1px solid #e6e9ef;padding-top:14px}
.feature-nav h2{font-size:1.05rem;margin:.6em 0 .3em}
.feature-nav ul{margin:.2em 0 .6em;padding-left:1.1em}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{display:inline-block;padding:5px 11px;border:1px solid #c5d3ea;background:#eef4fc;border-radius:999px;font-size:.85rem}
.chip:hover{background:#dce9fb;text-decoration:none}
.hint{font-size:.82rem;margin:4px 0 10px}
.filters{display:flex;flex-wrap:wrap;gap:14px;margin:-6px 0 6px;font-size:.9rem;color:#43505f}
.filters label{display:inline-flex;align-items:center;gap:5px;cursor:pointer}
.controls select{cursor:pointer}
.cmp-add{margin-right:9px;cursor:pointer}.cmp-add input{width:16px;height:16px;vertical-align:middle;cursor:pointer}
.cmpbar{position:fixed;left:0;right:0;bottom:0;background:#0d47a1;color:#fff;padding:11px 18px;display:none;align-items:center;gap:14px;flex-wrap:wrap;box-shadow:0 -2px 10px rgba(0,0,0,.18);z-index:20}
.cmpbar.on{display:flex}
.cmpbar .btn{background:#fff;color:#0d47a1;font-weight:700;padding:7px 16px;border-radius:8px}
.cmpbar .btn:hover{background:#e8f0fe;text-decoration:none}
.cmpbar .btn-ghost{background:transparent;color:#cfe0fb;border:1px solid #4f7ec4;padding:6px 13px;border-radius:8px;cursor:pointer;font:inherit;font-size:.9rem}
.cmpbar .btn-ghost:hover{background:#1257b8}
.cmp-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
table.cmp{border-collapse:collapse;background:#fff;border:1px solid #e6e9ef;border-radius:10px;min-width:100%}
table.cmp th,table.cmp td{text-align:left;padding:10px 14px;border-bottom:1px solid #eef1f5;border-right:1px solid #eef1f5;vertical-align:top;font-size:.9rem;min-width:150px}
table.cmp thead th{background:#f2f5fa;color:#1b2430;font-weight:700}
table.cmp tbody th{background:#f7f9fc;color:#3a4757;white-space:nowrap;min-width:110px;width:110px}
"""


def main() -> int:
    rows = load_rows()
    indexable = [r for r in rows
                 if r["is_bucket"] == "0" and r["is_duplicate"] == "0"
                 and r["scope"] == "domestic"]

    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "c").mkdir(parents=True)
    (SITE / "data").mkdir()
    (SITE / "assets").mkdir()

    # JSON（検索＋比較用。比較で使う事実値も含める）
    payload = [{
        "slug": r["slug"], "name": r["name"], "major": r["major_category"],
        "category": r["category"], "type": r["type"],
        "authority": r["authority"], "official_url": r["official_url"],
        "eligibility": r["eligibility"], "exam_format": r["exam_format"],
        "fee": r["fee"], "pass_rate": r["pass_rate"], "frequency": r["frequency"],
        "status": r.get("status", ""),
    } for r in indexable]
    payload.sort(key=lambda x: (x["major"], x["category"], x["name"]))
    (SITE / "data" / "certifications.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    (SITE / "assets" / "app.css").write_text(APP_CSS, encoding="utf-8")
    (SITE / "assets" / "search.js").write_text(SEARCH_JS, encoding="utf-8")
    (SITE / "assets" / "compare.js").write_text(COMPARE_JS, encoding="utf-8")
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

    # sitemap.xml（index対象 = トップ・比較・分野別・特集・インデックス対象の詳細のみ）
    # noindex のページは sitemap に入れない（インデックス衛生・整合性）。
    from datetime import date
    today = date.today().isoformat()
    # (path, lastmod, priority)
    entries = [("", today, "1.0"), ("compare.html", today, "0.7")]
    entries += [(f"bunya/{s}.html", today, "0.8") for s in cat_pages]
    entries += [(f"feature/{s}.html", today, "0.8") for s in feat_pages]
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

    # カスタム 404（GitHub Pages が未検出時に配信）
    nf_body = ('<h1>ページが見つかりません（404）</h1>'
               '<p class="lead">お探しのページは移動または削除された可能性があります。'
               'トップから資格名で検索してください。</p>'
               '<p><a href="/">▶ トップページへ</a></p>')
    (SITE / "404.html").write_text(
        page_shell(f"404 ページが見つかりません｜{SITE_NAME}", nf_body, depth=0,
                   noindex=True, desc="ページが見つかりません。", path="404.html"),
        encoding="utf-8")

    print(f"built site at {SITE.relative_to(ROOT)}")
    print(f"  index + {len(indexable)} detail pages")
    print(f"  sitemap urls: {len(entries)} (index対象詳細: {len(idx_details)})")
    print(f"  分野別一覧: {len(cat_pages)}  特集: {len(feat_pages)}")
    print(f"  excluded: bucket/duplicate/overseas = {len(rows)-len(indexable)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
