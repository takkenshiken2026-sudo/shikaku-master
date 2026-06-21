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
ACCENT = (42, 122, 110)     # teal #2a7a6e
WHITE = (255, 255, 255)
GRAY = (185, 185, 185)

BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
]
REG_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
