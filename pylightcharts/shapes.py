"""Shape descriptors for declarative custom series (see
`jslib/src/custom-series/custom-series.ts`).

A shape is a plain dict. Vertical anchors are **prices**; horizontal anchors are
offsets in **bar-spacing units** from the item's centre, where ``-0.4 .. 0.4``
spans one bar.

    df['shapes'] = [[shapes.rect(row.low, row.high, fill_color='#26a69a')]
                    for row in df.itertuples()]

or pass a builder to ``series.set(df, shapes=lambda row: [...])``.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

_LINE_STYLE_INDEX = {
    'solid': 0,
    'dotted': 1,
    'dashed': 2,
    'large_dashed': 3,
    'sparse_dotted': 4,
}


def _style(style: Union[str, int]) -> int:
    if isinstance(style, int):
        return style
    return _LINE_STYLE_INDEX.get(style, 0)


def rect(from_price: float, to_price: float, left: float = -0.4, right: float = 0.4,
         fill_color: Optional[str] = None, border_color: Optional[str] = None,
         border_width: int = 1) -> dict:
    """A filled and/or outlined rectangle spanning two prices."""
    return {
        'type': 'rect',
        'from': float(from_price),
        'to': float(to_price),
        'left': left,
        'right': right,
        'fillColor': fill_color,
        'borderColor': border_color,
        'borderWidth': border_width,
    }


def band(from_price: float, to_price: float, left: float = -0.4, right: float = 0.4,
         fill_color: Optional[str] = None) -> dict:
    """A filled band (rectangle without a border)."""
    return {
        'type': 'band',
        'from': float(from_price),
        'to': float(to_price),
        'left': left,
        'right': right,
        'fillColor': fill_color,
    }


def line(price: float, left: float = -0.4, right: float = 0.4, color: Optional[str] = None,
         width: int = 1, style: Union[str, int] = 'solid') -> dict:
    """A horizontal segment at `price`."""
    return {
        'type': 'line',
        'price': float(price),
        'left': left,
        'right': right,
        'color': color,
        'width': width,
        'style': _style(style),
    }


def circle(price: float, offset: float = 0.0, radius: int = 3, color: Optional[str] = None,
           border_color: Optional[str] = None, border_width: int = 0) -> dict:
    """A circle centred on the bar at `offset`."""
    return {
        'type': 'circle',
        'price': float(price),
        'offset': offset,
        'radius': radius,
        'color': color,
        'borderColor': border_color,
        'borderWidth': border_width,
    }


def marker(price: float, marker: str = 'circle', offset: float = 0.0,
           size: int = 10, color: Optional[str] = None,
           border_color: Optional[str] = None) -> dict:
    """A pixel-sized marker glyph centred (or tipped) at `price`.

    Unlike :func:`circle` (whose `offset` is in bar-spacing units) both `offset`
    and `size` are **pixels**, so the glyph keeps its size at every zoom level.
    `marker` is a minibt ``Markers`` name: ``triangle``, ``inverted_triangle``,
    ``arrow_up``, ``arrow_down``, ``circle``, ``circle_cross``, ``circle_dot``,
    ``circle_x``, ``circle_y``, ``square``, ``dot``, ``dash``, ``cross``,
    ``asterisk`` or ``triangle_dot``.
    """
    return {
        'type': 'marker',
        'price': float(price),
        'marker': str(marker),
        'offset': float(offset),
        'size': float(size),
        'color': color,
        'borderColor': border_color,
    }


def text(price: float, text: str, offset: float = 0.0, color: Optional[str] = None,
         font_size: int = 12, align: str = 'center', baseline: str = 'middle',
         line_height: float = 1.2, *, offset_x: float = 0.0,
         offset_y: float = 0.0, font_family: Optional[str] = None,
         font_weight: Optional[str] = None, font_style: Optional[str] = None,
         background_color: Optional[str] = None,
         background_alpha: Optional[float] = None,
         border_color: Optional[str] = None,
         border_alpha: Optional[float] = None,
         border_width: float = 1.0, padding: float = 4.0) -> dict:
    """A text label at `price`.

    Newlines in `text` are rendered as **multiple lines** (same idea as bokeh's
    `LabelSet`), spaced `line_height` x `font_size` apart and anchored on
    `baseline`: ``'top'`` grows downwards, ``'bottom'`` upwards and
    ``'middle'`` keeps the whole block centred on `price`::

        shapes.text(row['price'], 'BUY
CCI
RSI')
    """
    shape = {
        'type': 'text',
        'price': float(price),
        'text': str(text),
        'offset': offset,
        'color': color,
        'fontSize': font_size,
        'align': align,
        'baseline': baseline,
        'lineHeight': float(line_height),
    }
    # 可选样式：为 None / 默认值时**不写进数据**（渲染端自带同样的默认）
    optional = {
        'offsetX': offset_x or None,
        'offsetY': offset_y or None,
        'fontFamily': font_family,
        'fontWeight': font_weight,
        'fontStyle': font_style,
        'backgroundColor': background_color,
        'backgroundAlpha': background_alpha,
        'borderColor': border_color,
        'borderAlpha': border_alpha,
    }
    shape.update({k: v for k, v in optional.items() if v is not None})
    if border_color is not None:
        shape['borderWidth'] = float(border_width)
        shape['padding'] = float(padding)
    elif background_color is not None and padding != 4.0:
        shape['padding'] = float(padding)
    return shape


def polyline(points: Sequence[Tuple[float, float]], color: Optional[str] = None,
             width: int = 1, style: Union[str, int] = 'solid',
             fill_color: Optional[str] = None) -> dict:
    """An arbitrary path of ``(barOffset, price)`` points."""
    return {
        'type': 'polyline',
        'points': [[float(offset), float(price)] for offset, price in points],
        'color': color,
        'width': width,
        'style': _style(style),
        'fillColor': fill_color,
    }


# --------------------------------------------------------------------------
# reusable render presets
# --------------------------------------------------------------------------

def range_bar(low: float, high: float, color: str = 'rgba(41, 98, 255, 0.6)') -> List[dict]:
    """A simple low..high bar - the classic "range" custom series."""
    return [rect(low, high, fill_color=color, border_color=color)]


def box_plot(low: float, q1: float, median: float, q3: float, high: float,
             color: str = 'rgba(41, 98, 255, 0.35)', line_color: str = '#2962FF') -> List[dict]:
    """Box-and-whisker: IQR box, median and high/low whiskers."""
    return [
        line(high, left=0.0, right=0.0, color=line_color, width=1),
        line(q1, left=-0.25, right=0.25, color=line_color, width=1),
        line(q3, left=-0.25, right=0.25, color=line_color, width=1),
        rect(q1, q3, left=-0.25, right=0.25, fill_color=color, border_color=line_color),
        line(median, left=-0.25, right=0.25, color=line_color, width=2),
    ]


def stem(price: float, baseline: float = 0.0, color: Optional[str] = None,
         width: int = 1, style: Union[str, int] = 'dashed',
         cap: bool = False, cap_radius: int = 3) -> List[dict]:
    """A vertical stick from `baseline` to `price` (a "lollipop").

    Handy whenever per-bar values read better as a stick up/down from a
    common base - per-trade PnL, deviation from a moving average, volume at
    price::

        series.set(df, shapes=lambda row: shapes.stem(row['pnl']))

    `style` defaults to ``'dashed'``; pass ``cap=True`` to put a small circle
    on the tip (keeps the stick readable when the value is close to the
    baseline). Either way the item's `value` still drives the autoscale, so
    the pane range is unchanged.
    """
    result = [polyline([(0.0, float(baseline)), (0.0, float(price))],
                       color=color, width=width, style=style)]
    if cap:
        result.append(circle(price, radius=cap_radius, color=color))
    return result


def error_bar(value: float, lower: float, upper: float,
              color: str = '#2962FF') -> List[dict]:
    """A point with a symmetric error bar."""
    return [
        line(lower, left=0.0, right=0.0, color=color, width=1),
        line(upper, left=0.0, right=0.0, color=color, width=1),
        circle(value, radius=3, color=color),
    ]
