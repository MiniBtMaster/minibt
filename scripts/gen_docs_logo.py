"""生成文档站的两个 logo：

* ``minibt_docs/docs/plot/minibt.png`` —— 表头用的**横版**（图标 + ``minibt``）；
* ``minibt_docs/docs/plot/minibt copy.png`` —— **纯图标**版（蓝色**圆角方图**，
  没有文字；favicon / 应用图标 / 纯图形位用）。

设计（都取自 **minibt desk** 顶栏 LOGO，见 ``jslib/src/desk/logo.ts``）：

  * 背景 = 文档站表头蓝 ``#2094F3`` + 圆角（横版沿用原图 745×271 / r55，
    方图 r ≈ 20% 边长）；
  * 图形 = desk 的「4 根蜡烛 + 上升趋势线」；文字 = Segoe UI Bold 的
    ``minibt``（去掉 ``desk`` 字样）；
  * 4 根蜡烛 **2 涨 2 跌**，涨跌色 = TradingView 默认的 ``#089981`` /
    ``#f23645``（与 ``pylightcharts/themes.py`` 的 LIGHT 主题一致）；
    烛体描边只比本体深一点点（混黑 12%，压在蓝底上刚好有轮廓 ✓）。

用法::

    py -3.12 scripts/gen_docs_logo.py                  # 横版（表头 logo）
    py -3.12 scripts/gen_docs_logo.py --icon-only \
        --out "minibt_docs/docs/plot/minibt copy.png"  # 纯图标（圆角方图）
    py -3.12 scripts/gen_docs_logo.py --preview        # 额外输出预览图
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "minibt_docs" / "docs" / "plot" / "minibt.png"

BG = (32, 148, 243)          # #2094F3 与 mkdocs theme primary blue 一致
CANVAS = (745, 271)          # 沿用原图尺寸（表头布局不变）
RADIUS = 55                  # 沿用原图圆角
SS = 4                       # 超采样倍数，保证圆角 / 曲线边缘平滑

FONT_PATH = Path("C:/Windows/Fonts/segoeuib.ttf")  # Segoe UI Bold（desk 顶栏同款）

# 趋势线：近白偏蓝（压在 #2094F3 上仍清晰）
COL_LINE = (231, 246, 255, 235)
# TradingView 默认涨跌色（pylightcharts LIGHT 主题同款）
UP = (8, 153, 129, 255)      # #089981
DOWN = (242, 54, 69, 255)    # #f23645
COL_CANDLES = [               # 4 根蜡烛（左→右）：2 跌 2 涨，跟随趋势线走高
    DOWN,
    UP,
    DOWN,
    UP,
]
# 蜡烛描边：同色系的深色版，压在蓝底上轮廓更清楚（用户要求：**再淡一点** ✓）
OUTLINE_DARKEN = 0.12        # 向黑色混 12%（只比烛体深一点点）
OUTLINE_W = 0.26             # 描边宽度（virtual；蜡烛宽 3）
COL_TEXT = (255, 255, 255, 255)

# ---- desk LOGO 的矢量参数（viewBox 22 高，见 jslib/src/desk/logo.ts）----
LINE_PTS = [(2.0, 18.5), (8.5, 13.2), (14.0, 15.2), (21.5, 5.6)]
LINE_W = 1.6
CANDLES = [  # x, y, w, h, rx
    (1.5, 8.0, 3.0, 8.0, 1.0),
    (6.5, 4.5, 3.0, 10.0, 1.0),
    (11.5, 9.5, 3.0, 7.0, 1.0),
    (16.5, 3.5, 3.0, 8.0, 1.0),
]
TEXT = "minibt"
TEXT_X = 27.0                # 文字左边距（virtual）
TEXT_BASELINE = 16.0         # 基线（virtual）
TEXT_SIZE = 14.5             # 字号（virtual）
TEXT_TRACK = -0.2            # 字距（virtual）

# 横版内容留白
PAD_X = 56
PAD_Y = 34

#: 纯图标版（圆角方图）的尺寸 / 圆角 / 内容占比 ✓
ICON_SIZE = 512
ICON_RADIUS = 104            # ≈ 20% 边长，与横版 logo 的圆角比例一致
ICON_FILL = 0.78             # 图形占边长的比例（留白适中，缩到 32px 仍清楚）


def _text_width(font: ImageFont.FreeTypeFont, tracking: float,
                text: str = TEXT) -> float:
    return sum(font.getlength(ch) for ch in text) + tracking * (len(text) - 1)


def _darken(color, k: float = OUTLINE_DARKEN):
    """同色系深色版：向黑色混 ``k``，用作烛体描边。"""
    r, g, b = color[:3]
    return (int(r * (1 - k)), int(g * (1 - k)), int(b * (1 - k)), color[3])


def _draw_icon(d: ImageDraw.ImageDraw, scale: float,
               ox: float = 0.0, oy: float = 0.0) -> None:
    """画 desk LOGO 的图形部分（4 根蜡烛 + 上升趋势线，virtual 坐标 0..22 ✓）。

    ``ox`` / ``oy`` 是像素偏移（横版 logo / 圆角方图各用自己的居中量 ✓）。
    """

    def px(v: float) -> float:
        return v * scale

    # 趋势线（圆角端点 + 圆角折点）
    lw = max(1, int(round(px(LINE_W))))
    pts = [(ox + px(x), oy + px(y)) for x, y in LINE_PTS]
    d.line(pts, fill=COL_LINE, width=lw, joint="curve")
    for x, y in (pts[0], pts[-1]):
        r = lw / 2
        d.ellipse([x - r, y - r, x + r, y + r], fill=COL_LINE)

    # 4 根蜡烛（fill + 淡淡的一圈描边）
    lw_out = max(1, int(round(px(OUTLINE_W))))
    for (cx, cy, cw, ch, crx), col in zip(CANDLES, COL_CANDLES):
        d.rounded_rectangle(
            [ox + px(cx), oy + px(cy), ox + px(cx + cw), oy + px(cy + ch)],
            radius=max(1, int(round(px(crx)))),
            fill=col,
            outline=_darken(col),
            width=lw_out,
        )


def _draw_content(scale: float, font: ImageFont.FreeTypeFont,
                  tracking: int) -> Image.Image:
    """按 virtual 坐标 * scale 画出「图标 + minibt」，返回透明底图层。"""
    pad = 4
    w = int((TEXT_X + _text_width(font, tracking) / scale + pad) * scale)
    h = int((22 + pad * 2) * scale)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    oy = pad * scale  # 让 virtual y=0 落在 pad 处
    _draw_icon(d, scale, 0.0, oy)

    # 文字（逐字绘制以支持负字距）
    x = TEXT_X * scale
    baseline = oy + TEXT_BASELINE * scale
    for i, ch in enumerate(TEXT):
        d.text((x, baseline), ch, font=font, fill=COL_TEXT, anchor="ls")
        x += font.getlength(ch) + (tracking if i < len(TEXT) - 1 else 0)

    return layer


def _icon_ink_box() -> tuple:
    """图形在 virtual 坐标里的 ink 范围 ``(left, top, right, bottom)`` ✓"""
    half = LINE_W / 2
    xs = ([x for x, _ in LINE_PTS] + [c[0] for c in CANDLES]
          + [c[0] + c[2] for c in CANDLES])
    ys = ([y for _, y in LINE_PTS] + [c[1] for c in CANDLES]
          + [c[1] + c[3] for c in CANDLES])
    return (min(xs) - half, min(ys) - half, max(xs) + half, max(ys) + half)


def build_icon(size: int = ICON_SIZE) -> Image.Image:
    """**纯图标**版：蓝色圆角方块 + desk 的「4 根蜡烛 + 趋势线」（无文字 ✓）。

    用于 favicon / 应用图标 / 文档里的纯图形位（``minibt copy.png``）。
    """
    side = int(size)
    radius = int(round(ICON_RADIUS * side / ICON_SIZE))
    big = Image.new("RGBA", (side * SS, side * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle(
        [0, 0, side * SS - 1, side * SS - 1], radius=radius * SS,
        fill=BG + (255,),
    )
    left, top, right, bottom = _icon_ink_box()
    ink_w, ink_h = right - left, bottom - top
    scale = side * SS * ICON_FILL / max(ink_w, ink_h)
    # 让 ink 的中心落在画布中心 ✓
    ox = side * SS / 2 - scale * (left + right) / 2
    oy = side * SS / 2 - scale * (top + bottom) / 2
    _draw_icon(d, scale, ox, oy)
    return big.resize((side, side), Image.LANCZOS)


def build() -> Image.Image:
    """横版（表头 logo）：蓝色圆角块 + 图标 + ``minibt`` ✓"""
    cw, ch = CANVAS

    # 1) 背景：圆角蓝色块
    big = Image.new("RGBA", (cw * SS, ch * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle(
        [0, 0, cw * SS - 1, ch * SS - 1], radius=RADIUS * SS, fill=BG + (255,)
    )

    # 2) 迭代求合适缩放：先按高度估算，再按宽度收敛
    scale = (ch - 2 * PAD_Y) / 20.0
    for _ in range(6):
        size = max(8, int(round(TEXT_SIZE * scale * SS)))
        font = ImageFont.truetype(str(FONT_PATH), size)
        tracking = TEXT_TRACK * scale * SS
        layer = _draw_content(scale * SS, font, tracking)
        bbox = layer.getbbox()
        ink_w, ink_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        fit = min(
            (cw * SS - 2 * PAD_X * SS) / ink_w,
            (ch * SS - 2 * PAD_Y * SS) / ink_h,
        )
        if abs(fit - 1.0) < 0.01:
            break
        scale *= min(fit, 1.2)

    # 最终图层
    size = max(8, int(round(TEXT_SIZE * scale * SS)))
    font = ImageFont.truetype(str(FONT_PATH), size)
    layer = _draw_content(scale * SS, font, TEXT_TRACK * scale * SS)
    bbox = layer.getbbox()
    ink = layer.crop(bbox)

    # 3) 居中合成
    x = (cw * SS - ink.width) // 2
    y = (ch * SS - ink.height) // 2
    big.alpha_composite(ink, (x, y))

    return big.resize((cw, ch), Image.LANCZOS)


def preview(img: Image.Image, path: Path) -> None:
    """拼一张预览：表头尺寸 / 半尺寸 / 32px 圆角方图。"""
    head_h = 90
    canvas = Image.new("RGB", (760, head_h + 170), (255, 255, 255))
    header = Image.new("RGB", (760, head_h), BG)
    logo_small = img.resize(
        (round(img.width * 30 / img.height), 30), Image.LANCZOS)
    header.paste(logo_small, (16, (head_h - 30) // 2), logo_small)
    d = ImageDraw.Draw(header)
    d.text((70, head_h // 2), "MiniBT 量化交易知识库", fill=(255, 255, 255),
           anchor="lm")
    canvas.paste(header, (0, 0))
    half = img.resize((372, 135), Image.LANCZOS)
    canvas.paste(half, (16, head_h + 18))
    icon = build_icon(128)
    canvas.paste(icon, (410, head_h + 30), icon)
    icon_small = build_icon(32)
    canvas.paste(icon_small, (560, head_h + 90), icon_small)
    canvas.save(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--preview", action="store_true", help="额外输出 /tmp 预览图")
    ap.add_argument("--icon-only", action="store_true",
                    help="只画图标（蓝色圆角方图，无 minibt 文字 ✓）")
    ap.add_argument("--size", type=int, default=ICON_SIZE,
                    help=f"--icon-only 时的边长（默认 {ICON_SIZE}）")
    args = ap.parse_args()

    img = build_icon(args.size) if args.icon_only else build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    img.save(args.out)
    print(f"wrote {args.out}  {img.size}")
    if args.preview:
        prev = Path(tempfile.gettempdir()) / "docs_logo_preview.png"
        preview(img, prev)
        print(f"preview {prev}")


if __name__ == "__main__":
    main()
