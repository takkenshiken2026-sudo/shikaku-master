#!/usr/bin/env python3
"""OGP/Twitter カード用の共有画像（1200×630 PNG）を生成する。

site/assets/og-default.png を出力。build_pages.py が OG_IMAGE で参照する。
日本語フォントは Noto CJK → IPAゴシック の順に探索する。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
# 正本は brand/ に置く。build_pages.py が site/assets/ へコピーする
# （ビルドで site/ を作り直すため、site/ 直書きだと消える）。
OUT = ROOT / "brand" / "og-default.png"

W, H = 1200, 630
BG = (13, 71, 161)        # #0d47a1
BG2 = (7, 45, 107)        # 下部の濃色（簡易グラデ用）
ACCENT = (255, 255, 255)
SUB = (191, 211, 240)

SITE_NAME = "資格カタログ"
TAGLINE = "日本の資格を 探せる・絞れる・比べられる"
SUBLINE = "受験料・試験形式・受験資格・合格率・公式情報を一次情報で整備"

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
]


def load_font(size: int):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main() -> int:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # 簡易縦グラデーション（上→下を少し濃く）
    for y in range(H):
        t = y / H
        c = tuple(round(BG[i] + (BG2[i] - BG[i]) * t) for i in range(3))
        draw.line([(0, y), (W, y)], fill=c)

    # 左上の角丸バッジ「資」
    bsize = 150
    bx, by = 90, 90
    draw.rounded_rectangle((bx, by, bx + bsize, by + bsize), radius=34,
                           fill=(255, 255, 255))
    gfont = load_font(96)
    gb = draw.textbbox((0, 0), "資", font=gfont)
    gw, gh = gb[2] - gb[0], gb[3] - gb[1]
    draw.text((bx + (bsize - gw) / 2 - gb[0], by + (bsize - gh) / 2 - gb[1]),
              "資", font=gfont, fill=BG)

    # サイト名
    name_font = load_font(104)
    draw.text((90, 280), SITE_NAME, font=name_font, fill=ACCENT)

    # タグライン
    tag_font = load_font(46)
    draw.text((92, 410), TAGLINE, font=tag_font, fill=ACCENT)

    # サブライン
    sub_font = load_font(32)
    draw.text((92, 488), SUBLINE, font=sub_font, fill=SUB)

    # 下部アクセントライン
    draw.rectangle((0, H - 14, W, H), fill=(25, 118, 210))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG")
    print(f"wrote {OUT.relative_to(ROOT)} ({W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
