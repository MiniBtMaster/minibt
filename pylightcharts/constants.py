"""Lightweight Charts v5 常量 / 枚举的 Python 镜像。

上游把枚举放在模块作用域，泛型 RPC（``Lib.invoke``）无法访问，因此这里提供
与 ``lightweight-charts@5.2.x`` **逐值一致** 的 Python 常量，供用户与框架内部使用：

.. code-block:: python

    from pylightcharts.constants import LineStyle, PriceScaleMode, CrosshairMode

    chart.time_scale_options(ticks_visible=True)
    chart.price_scale(mode=PriceScaleMode.Logarithmic)
    series.apply_options(lineStyle=LineStyle.Dashed)

这些值同时由 JS 桥导出（``Lib.ColorType`` / ``Lib.LineStyle`` …，见
``jslib/src/general/exports.ts``）。若需要校验与内嵌引擎是否一致，可在任意图表上调用
:func:`verify`：

.. code-block:: python

    from pylightcharts.constants import verify
    verify(chart)      # 返回不一致的 (枚举名, 期望值, 实际值) 列表，空表示一致
"""

from __future__ import annotations

from enum import Enum, IntEnum

__all__ = [
    "ColorType", "CrosshairMode", "LastPriceAnimationMode", "LineStyle",
    "LineType", "MismatchDirection", "PriceLineSource", "PriceScaleMode",
    "TickMarkType", "TrackingModeExitMode", "MarkerSign", "SeriesType",
    "VERSION", "ENUMS", "verify",
]

#: 内嵌的 Lightweight Charts 版本（须与 ``pylightcharts/js/lightweight-charts.js`` 一致）
VERSION = "5.2.1"


class ColorType(str, Enum):
    """``layout.background.type``。"""
    Solid = "solid"
    VerticalGradient = "gradient"


class CrosshairMode(IntEnum):
    Normal = 0
    Magnet = 1
    Hidden = 2
    MagnetOHLC = 3


class LastPriceAnimationMode(IntEnum):
    Disabled = 0
    Continuous = 1
    OnDataUpdate = 2


class LineStyle(IntEnum):
    Solid = 0
    Dotted = 1
    Dashed = 2
    LargeDashed = 3
    SparseDotted = 4


class LineType(IntEnum):
    Simple = 0
    WithSteps = 1
    Curved = 2


class MismatchDirection(IntEnum):
    NearestLeft = -1
    # `None` 是 Python 关键字，无法作为属性名；保留 None_ 作为别名
    None_ = 0
    NearestRight = 1


class PriceLineSource(IntEnum):
    LastBar = 0
    LastVisible = 1


class PriceScaleMode(IntEnum):
    Normal = 0
    Logarithmic = 1
    Percentage = 2
    IndexedTo100 = 3


class TickMarkType(IntEnum):
    Year = 0
    Month = 1
    DayOfMonth = 2
    Time = 3
    TimeWithSeconds = 4


class TrackingModeExitMode(IntEnum):
    OnTouchEnd = 0
    OnNextTap = 1


class MarkerSign(IntEnum):
    """``SeriesMarker`` 的 ``sign``（上游 ``const enum``，运行时被擦除）。"""
    Negative = -1
    Neutral = 0
    Positive = 1


class SeriesType(str, Enum):
    """``SeriesType`` 字符串联合。"""
    Line = "Line"
    Area = "Area"
    Bar = "Bar"
    Baseline = "Baseline"
    Candlestick = "Candlestick"
    Histogram = "Histogram"
    Custom = "Custom"


#: 所有 `IntEnum`/`str Enum` 的注册表，供 :func:`verify` 遍历。
ENUMS = {
    "ColorType": ColorType,
    "CrosshairMode": CrosshairMode,
    "LastPriceAnimationMode": LastPriceAnimationMode,
    "LineStyle": LineStyle,
    "LineType": LineType,
    "MismatchDirection": MismatchDirection,
    "PriceLineSource": PriceLineSource,
    "PriceScaleMode": PriceScaleMode,
    "TickMarkType": TickMarkType,
    "TrackingModeExitMode": TrackingModeExitMode,
}


def verify(chart) -> list[tuple[str, object, object]]:
    """把本地常量与图表内嵌的 ``Lib`` 枚举逐值对比。

    :param chart: 任意 ``AbstractChart`` / ``Window``（内部会用它执行 JS）。
    :returns: 不一致列表 ``[(枚举名, 本地值, 引擎值), ...]``，空表示完全一致。
    """
    win = getattr(chart, "win", chart)
    mismatches: list[tuple[str, object, object]] = []
    for name, enum_cls in ENUMS.items():
        for member in enum_cls:
            actual = win.eval_js(f"Lib.{name}.{_js_member(name, member.name)}")
            if actual != member.value:
                mismatches.append((f"{name}.{member.name}", member.value, actual))
    return mismatches


def _js_member(enum_name: str, member_name: str) -> str:
    """Python 侧成员名 → JS 侧成员名（仅 MismatchDirection.None_ 需要改写）。"""
    if enum_name == "MismatchDirection" and member_name == "None_":
        return "None"
    return member_name
