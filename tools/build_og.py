#!/usr/bin/env python3
"""OGP用の共有画像 site/assets/og.png（1200x630）を生成する。

CIでのみ実行（Pillow と CJK フォントが必要）。失敗してもサイトビルドは継続させる
（pages.yml 側で非致命的に呼び出す）。ローカルに Pillow が無い場合はスキップ。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "assets" / "og.png"

W, H = 1200, 630
INK = (34, 34, 34)          # charcoal #222
ACCENT = (26, 79, 143)      # navy #1a4f8f
WHITE = (255, 255, 255)
GRAY = (185, 185, 185)

BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
]
REG_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
]

SITE_NAME = "資格マスター"
TAGLINE = "就職・転職・スキルアップの資格情報サイト"
SUBLINE = "国内の資格を1,000件以上掲載。受験料・受験資格・合格率・公式サイトを横断検索・比較。"
URL = "shikaku-master.jp"


def _font(cands, size):
    from PIL import ImageFont
    for p in cands:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def main() -> int:
    try:
        from PIL import Image, ImageDraw
    except Exception as e:
        print(f"[build_og] Pillow not available, skip: {e}")
        return 0

    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)

    # 左の縦アクセントバー
    d.rectangle((0, 0, 16, H), fill=ACCENT)
    # 角の資格バッジ風
    d.rounded_rectangle((80, 86, 188, 194), radius=24, fill=ACCENT)
    badge_font = _font(BOLD_CANDIDATES, 76)
    d.text((134, 140), "資", font=badge_font, fill=WHITE, anchor="mm")

    title_font = _font(BOLD_CANDIDATES, 104)
    tag_font = _font(BOLD_CANDIDATES, 46)
    sub_font = _font(REG_CANDIDATES, 32)
    url_font = _font(BOLD_CANDIDATES, 30)

    d.text((80, 250), SITE_NAME, font=title_font, fill=WHITE)
    d.text((84, 384), TAGLINE, font=tag_font, fill=(220, 235, 232))

    # サブ説明（必要なら手動で1回折り返し）
    sub = SUBLINE
    if len(sub) > 30:
        cut = sub.rfind("。", 0, 32)
        if cut == -1:
            cut = 30
        line1, line2 = sub[:cut + 1], sub[cut + 1:]
    else:
        line1, line2 = sub, ""
    d.text((84, 452), line1, font=sub_font, fill=GRAY)
    if line2:
        d.text((84, 496), line2, font=sub_font, fill=GRAY)

    d.text((84, 560), URL, font=url_font, fill=ACCENT)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="PNG", optimize=True)
    print(f"[build_og] wrote {OUT.relative_to(ROOT)}")

    # 資格ごとの個別OG画像（index対象のみ）
    try:
        n = build_cert_images()
        print(f"[build_og] wrote {n} per-cert OG images")
    except Exception as e:
        print(f"[build_og] per-cert OG skipped: {e}")
    return 0


def _indexable(r):
    if r.get("status") != "published":
        return False
    has_key = bool(r.get("fee", "").strip() or r.get("pass_rate", "").strip()
                   or r.get("eligibility", "").strip())
    n_facts = sum(1 for k in ("fee", "pass_rate", "eligibility", "exam_format", "frequency")
                  if r.get(k, "").strip())
    return has_key and n_facts >= 2


def build_cert_images() -> int:
    """index対象の資格ごとに 1200x630 のOG画像を site/assets/ogp/<slug>.png に生成する。"""
    import csv
    from PIL import Image, ImageDraw

    csv_path = ROOT / "data" / "certifications.csv"
    if not csv_path.exists():
        return 0
    with csv_path.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)
                if r.get("is_bucket") == "0" and r.get("is_duplicate") == "0"
                and r.get("scope") == "domestic" and _indexable(r)]

    out_dir = ROOT / "site" / "assets" / "ogp"
    out_dir.mkdir(parents=True, exist_ok=True)

    f_xl = _font(BOLD_CANDIDATES, 88)
    f_lg = _font(BOLD_CANDIDATES, 68)
    f_md = _font(BOLD_CANDIDATES, 52)
    f_sub = _font(REG_CANDIDATES, 34)
    f_brand = _font(BOLD_CANDIDATES, 30)

    TYPE_LABEL = {"国家": "国家資格", "公的": "公的資格", "民間": "民間資格",
                  "要確認": "資格", "海外": "海外資格"}

    count = 0
    for r in rows:
        name = r["name"]
        img = Image.new("RGB", (W, H), INK)
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 16, H), fill=ACCENT)
        d.text((80, 70), SITE_NAME, font=f_brand, fill=(220, 235, 232))
        ln = len(name)
        tf = f_xl if ln <= 9 else f_lg if ln <= 14 else f_md
        max_w = W - 160
        if d.textlength(name, font=tf) <= max_w:
            d.text((80, 250), name, font=tf, fill=WHITE)
        else:
            mid = len(name) // 2
            for sep in ("（", "(", "・", "／", "/"):
                p = name.find(sep, 3, len(name) - 2)
                if p != -1:
                    mid = p
                    break
            l1, l2 = name[:mid], name[mid:]
            d.text((80, 196), l1, font=tf, fill=WHITE)
            d.text((80, 196 + tf.size + 12), l2, font=tf, fill=WHITE)
        sub = f"{r.get('major_category','')}　|　{TYPE_LABEL.get(r.get('type',''), '資格')}"
        d.text((84, 470), sub, font=f_sub, fill=GRAY)
        d.text((84, 560), URL, font=f_brand, fill=ACCENT)
        img.save(out_dir / f"{r['slug']}.png", format="PNG", optimize=True)
        count += 1
    return count


if __name__ == "__main__":
    raise SystemExit(main())
