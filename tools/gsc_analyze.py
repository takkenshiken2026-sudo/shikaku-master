#!/usr/bin/env python3
"""Google Search Console のデータを読み込んで SEO 分析レポートを生成する。

標準ライブラリのみで動作する（google-* 等の外部依存なし）。入力は 2 通りに対応:

1. tools/gsc_fetch.py が API から出力した CSV（列: page/query/clicks/impressions/
   ctr/position、CTR は 0〜1 の割合）。
2. GSC 管理画面から手動エクスポートした CSV（日本語/英語ヘッダの両方に対応。
   例: 「上位のクエリ,クリック数,表示回数,CTR,掲載順位」/ "Top pages,Clicks,...")。

data/gsc/ 配下の *.csv を自動判別して読み込む（--input で個別指定も可）。
CTR は表記ゆれを避けるため clicks/impressions から再計算する。掲載順位のみ
入力値を用いる。

出力（既定: data/gsc/report.md）:
  - サマリ（合計クリック/表示/平均CTR/平均掲載順位）
  - 資格ページ単位の集計（URL→slug→資格名 で紐づけ、上位/下位ランキング）
  - SEO 改善候補
      * ストライキングディスタンス（掲載順位 5〜20 位・表示回数が多い＝あと一歩）
      * 低 CTR（上位表示なのにクリックが取れていない＝機会損失）
  - クエリ分析（上位クエリ、資格名を含まない需要語、ページ×クエリの内訳）

使い方:
  python3 tools/gsc_analyze.py
  python3 tools/gsc_analyze.py --input data/gsc/Queries.csv data/gsc/Pages.csv
  python3 tools/gsc_analyze.py --out report.md --min-impressions 30
"""
import argparse
import csv
import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GSC_DIR = ROOT / "data" / "gsc"
CERTS = ROOT / "data" / "certifications.csv"
SITE_HOST = "shikaku-master.jp"

# 掲載順位ごとの想定 CTR（業界平均のおおよそのベンチマーク。機会損失の目安に使う）
CTR_BENCHMARK = {
    1: 0.28, 2: 0.15, 3: 0.10, 4: 0.07, 5: 0.05,
    6: 0.04, 7: 0.03, 8: 0.025, 9: 0.02, 10: 0.018,
}
CTR_BENCHMARK_TAIL = 0.01  # 11 位以降

# ヘッダ名（小文字化・前後空白除去して照合）→ 正規化キー
HEADER_ALIASES = {
    "page": {"page", "top pages", "pages", "上位のページ", "ページ", "url"},
    "query": {"query", "top queries", "queries", "上位のクエリ", "クエリ",
              "検索キーワード", "キーワード"},
    "clicks": {"clicks", "click", "クリック数", "クリック"},
    "impressions": {"impressions", "impression", "表示回数"},
    "ctr": {"ctr", "click through rate"},
    "position": {"position", "avg. position", "average position",
                 "掲載順位", "平均掲載順位"},
}


def _canon_header(name):
    key = name.strip().lower().lstrip("﻿")
    for canon, aliases in HEADER_ALIASES.items():
        if key in aliases:
            return canon
    return None


def _to_float(s):
    if s is None:
        return 0.0
    s = str(s).strip().replace(",", "").replace("%", "").replace("　", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _to_int(s):
    return int(round(_to_float(s)))


def load_cert_names():
    """slug -> 資格名 の辞書。certifications.csv が無くても動く。"""
    names = {}
    if not CERTS.exists():
        return names
    with CERTS.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            slug = (r.get("slug") or "").strip()
            if slug:
                names[slug] = (r.get("name") or "").strip()
    return names


def slug_from_url(url):
    """https://.../c/<slug>.html → <slug>。資格詳細ページ以外は None。"""
    if not url:
        return None
    m = re.search(r"/c/([^/.]+)\.html", url)
    return m.group(1) if m else None


def read_csv_rows(path):
    """CSV を読み、正規化した行 dict のリストと、含まれる列種別集合を返す。"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        # 区切り文字を推定（GSC は基本カンマ、TSV も一応許容）
        sample = f.read(4096)
        f.seek(0)
        delim = "\t" if sample.count("\t") > sample.count(",") else ","
        reader = csv.reader(f, delimiter=delim)
        try:
            header = next(reader)
        except StopIteration:
            return [], set()
        cols = [_canon_header(h) for h in header]
        present = {c for c in cols if c}
        if not ({"page", "query"} & present):
            return [], set()  # 対象外の CSV（Devices, Dates 等）はスキップ
        rows = []
        for raw in reader:
            if not raw:
                continue
            rec = {}
            for c, v in zip(cols, raw):
                if c:
                    rec[c] = v
            rows.append(rec)
        return rows, present


def normalize_rows(rows):
    """clicks/impressions を数値化し、CTR は clicks/impressions で再計算。"""
    out = []
    for r in rows:
        clicks = _to_int(r.get("clicks"))
        impr = _to_int(r.get("impressions"))
        pos = _to_float(r.get("position"))
        rec = {
            "page": (r.get("page") or "").strip(),
            "query": (r.get("query") or "").strip(),
            "clicks": clicks,
            "impressions": impr,
            "ctr": (clicks / impr) if impr else 0.0,
            "position": pos,
        }
        out.append(rec)
    return out


def classify(rows, present):
    """CSV の種別を返す: page_query / pages / queries。"""
    if "page" in present and "query" in present:
        return "page_query"
    if "page" in present:
        return "pages"
    return "queries"


def load_all(inputs):
    """入力 CSV 群を種別ごとに集約して返す。"""
    data = {"pages": [], "queries": [], "page_query": []}
    used = []
    for path in inputs:
        rows, present = read_csv_rows(path)
        if not rows:
            continue
        kind = classify(rows, present)
        data[kind].extend(normalize_rows(rows))
        used.append((path, kind, len(rows)))
    return data, used


def benchmark_ctr(position):
    p = int(round(position)) if position else 999
    return CTR_BENCHMARK.get(p, CTR_BENCHMARK_TAIL if p >= 11 else CTR_BENCHMARK[1])


def fmt_pct(x):
    return f"{x * 100:.1f}%"


def aggregate_by_slug(pages, names):
    """ページ行を slug 単位に集約（同一 slug の別 URL・パラメタ違いを合算）。"""
    agg = {}
    for r in pages:
        slug = slug_from_url(r["page"])
        if not slug:
            continue
        a = agg.setdefault(slug, {"slug": slug, "clicks": 0, "impressions": 0,
                                  "pos_weight": 0.0})
        a["clicks"] += r["clicks"]
        a["impressions"] += r["impressions"]
        a["pos_weight"] += r["position"] * max(r["impressions"], 1)
    for a in agg.values():
        a["ctr"] = (a["clicks"] / a["impressions"]) if a["impressions"] else 0.0
        a["position"] = (a["pos_weight"] / a["impressions"]) if a["impressions"] else 0.0
        a["name"] = names.get(a["slug"], "")
    return list(agg.values())


# ---- レポート整形 ----------------------------------------------------------

def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def build_report(data, names, min_impressions, top_n):
    lines = []
    add = lines.append

    add("# Search Console 分析レポート\n")

    # ---- サマリ ----
    src = data["pages"] or data["page_query"] or data["queries"]
    total_clicks = sum(r["clicks"] for r in src)
    total_impr = sum(r["impressions"] for r in src)
    avg_ctr = (total_clicks / total_impr) if total_impr else 0.0
    pos_rows = [r for r in src if r["impressions"] > 0 and r["position"] > 0]
    avg_pos = (sum(r["position"] * r["impressions"] for r in pos_rows)
               / sum(r["impressions"] for r in pos_rows)) if pos_rows else 0.0
    add("## サマリ\n")
    add(md_table(
        ["指標", "値"],
        [["合計クリック", f"{total_clicks:,}"],
         ["合計表示回数", f"{total_impr:,}"],
         ["平均CTR", fmt_pct(avg_ctr)],
         ["平均掲載順位", f"{avg_pos:.1f}"]]))
    add("")

    # ---- 資格ページ単位の集計 ----
    if data["pages"]:
        slugs = aggregate_by_slug(data["pages"], names)
        add("## 資格ページ単位の集計\n")
        add(f"対象資格ページ: **{len(slugs)}** 件\n")

        top_click = sorted(slugs, key=lambda a: a["clicks"], reverse=True)[:top_n]
        add("### クリック上位\n")
        add(md_table(
            ["資格", "slug", "クリック", "表示", "CTR", "掲載順位"],
            [[a["name"] or "(不明)", a["slug"], f'{a["clicks"]:,}',
              f'{a["impressions"]:,}', fmt_pct(a["ctr"]), f'{a["position"]:.1f}']
             for a in top_click]))
        add("")

        # 表示は多いがクリックが少ない（＝伸びしろ）
        buried = sorted(
            [a for a in slugs if a["impressions"] >= min_impressions],
            key=lambda a: (a["clicks"], -a["impressions"]))[:top_n]
        add("### 表示が多いのにクリックが少ない資格ページ（伸びしろ）\n")
        add(md_table(
            ["資格", "slug", "クリック", "表示", "CTR", "掲載順位"],
            [[a["name"] or "(不明)", a["slug"], f'{a["clicks"]:,}',
              f'{a["impressions"]:,}', fmt_pct(a["ctr"]), f'{a["position"]:.1f}']
             for a in buried]))
        add("")

    # ---- SEO 改善候補 ----
    add("## SEO 改善候補\n")

    # 分析対象は「ページ×クエリ」があればそれを優先、無ければクエリ、無ければページ
    if data["page_query"]:
        rows, unit = data["page_query"], "page_query"
    elif data["queries"]:
        rows, unit = data["queries"], "query"
    else:
        rows, unit = data["pages"], "page"

    def label(r):
        if unit == "page_query":
            slug = slug_from_url(r["page"])
            nm = names.get(slug, slug or r["page"])
            return f'{r["query"]} @ {nm or r["page"]}'
        if unit == "query":
            return r["query"]
        slug = slug_from_url(r["page"])
        return names.get(slug, slug or r["page"]) or r["page"]

    # ストライキングディスタンス: 掲載順位 5〜20 位・表示多め＝あと一歩で上位化
    striking = [r for r in rows
                if 4.5 <= r["position"] <= 20.5 and r["impressions"] >= min_impressions]
    striking.sort(key=lambda r: r["impressions"], reverse=True)
    add("### ストライキングディスタンス（掲載順位5〜20位・あと一歩）\n")
    add("順位を少し押し上げれば流入が伸びる見込みの語・ページ。内部リンク・見出し・"
        "本文の充実が効きやすい。\n")
    if striking:
        add(md_table(
            ["対象", "表示", "クリック", "CTR", "掲載順位"],
            [[label(r), f'{r["impressions"]:,}', f'{r["clicks"]:,}',
              fmt_pct(r["ctr"]), f'{r["position"]:.1f}']
             for r in striking[:top_n]]))
    else:
        add("_該当なし（min-impressions を下げて再実行してください）_")
    add("")

    # 低 CTR: 上位表示（10位以内）なのにベンチマークよりクリックが取れていない
    lost = []
    for r in rows:
        if r["position"] and r["position"] <= 10.5 and r["impressions"] >= min_impressions:
            bench = benchmark_ctr(r["position"])
            gap = bench - r["ctr"]
            if gap > 0:
                r = dict(r)
                r["lost"] = gap * r["impressions"]
                r["bench"] = bench
                lost.append(r)
    lost.sort(key=lambda r: r["lost"], reverse=True)
    add("### 低CTR（上位表示なのにクリックが取れていない＝機会損失）\n")
    add("掲載順位10位以内で、想定CTRより低いもの。タイトル・メタディスクリプションの"
        "改善が効きやすい。「想定クリック増」は想定CTRとの差×表示回数の概算。\n")
    if lost:
        add(md_table(
            ["対象", "表示", "掲載順位", "実CTR", "想定CTR", "想定クリック増"],
            [[label(r), f'{r["impressions"]:,}', f'{r["position"]:.1f}',
              fmt_pct(r["ctr"]), fmt_pct(r["bench"]), f'+{r["lost"]:.0f}']
             for r in lost[:top_n]]))
    else:
        add("_該当なし_")
    add("")

    # ---- クエリ分析 ----
    if data["queries"] or data["page_query"]:
        qrows = data["queries"] or data["page_query"]
        # クエリ単位に集約
        qagg = {}
        for r in qrows:
            q = r["query"]
            if not q:
                continue
            a = qagg.setdefault(q, {"query": q, "clicks": 0, "impressions": 0,
                                    "pos_weight": 0.0})
            a["clicks"] += r["clicks"]
            a["impressions"] += r["impressions"]
            a["pos_weight"] += r["position"] * max(r["impressions"], 1)
        for a in qagg.values():
            a["ctr"] = (a["clicks"] / a["impressions"]) if a["impressions"] else 0.0
            a["position"] = (a["pos_weight"] / a["impressions"]) if a["impressions"] else 0.0
        qlist = list(qagg.values())

        add("## クエリ分析\n")
        add(f"ユニーククエリ数: **{len(qlist)}**\n")

        top_q = sorted(qlist, key=lambda a: a["clicks"], reverse=True)[:top_n]
        add("### クリック上位クエリ\n")
        add(md_table(
            ["クエリ", "クリック", "表示", "CTR", "掲載順位"],
            [[a["query"], f'{a["clicks"]:,}', f'{a["impressions"]:,}',
              fmt_pct(a["ctr"]), f'{a["position"]:.1f}']
             for a in top_q]))
        add("")

        # 資格名を含まない需要語（未カバーの検索意図の手がかり）
        name_tokens = set()
        for nm in names.values():
            if nm:
                name_tokens.add(nm)
        def is_generic(q):
            return not any(tok and tok in q for tok in name_tokens)
        generic = sorted(
            [a for a in qlist if is_generic(a["query"]) and a["impressions"] >= min_impressions],
            key=lambda a: a["impressions"], reverse=True)[:top_n]
        add("### 資格名を含まない需要語（コンテンツ拡充のヒント）\n")
        add("カタログの資格名に直接一致しない検索語。特集ページや横断コンテンツの"
            "ネタになりうる。\n")
        if generic:
            add(md_table(
                ["クエリ", "表示", "クリック", "CTR", "掲載順位"],
                [[a["query"], f'{a["impressions"]:,}', f'{a["clicks"]:,}',
                  fmt_pct(a["ctr"]), f'{a["position"]:.1f}']
                 for a in generic]))
        else:
            add("_該当なし_")
        add("")

    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="GSC データの SEO 分析レポート生成")
    ap.add_argument("--input", nargs="*", default=None,
                    help="読み込む CSV（省略時は data/gsc/*.csv を自動検出）")
    ap.add_argument("--out", default=str(GSC_DIR / "report.md"),
                    help="出力先 Markdown（既定: data/gsc/report.md）")
    ap.add_argument("--min-impressions", type=int, default=20,
                    help="改善候補・需要語の表示回数しきい値（既定: 20）")
    ap.add_argument("--top", type=int, default=30,
                    help="各ランキングの表示件数（既定: 30）")
    args = ap.parse_args()

    if args.input:
        inputs = args.input
    else:
        inputs = sorted(glob.glob(str(GSC_DIR / "*.csv")))
    inputs = [p for p in inputs if Path(p).name != "report.md"]
    if not inputs:
        print(f"入力 CSV が見つかりません: {GSC_DIR}/*.csv\n"
              f"  tools/gsc_fetch.py で取得するか、GSC管理画面のエクスポートCSVを"
              f"置いてください。", file=sys.stderr)
        return 1

    names = load_cert_names()
    data, used = load_all(inputs)
    if not any(data.values()):
        print("有効なデータ行がありません（対象は page/query を含む CSV）。",
              file=sys.stderr)
        return 1

    report = build_report(data, names, args.min_impressions, args.top)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    print("読み込んだファイル:")
    for path, kind, n in used:
        print(f"  - {Path(path).name}  [{kind}]  {n} 行")
    print(f"\nレポートを書き出しました: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
