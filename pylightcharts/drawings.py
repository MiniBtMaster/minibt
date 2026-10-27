import asyncio
import json
import pandas as pd

from typing import Union, Optional

from pylightcharts.util import js_json, jbool

from .util import NUM, Pane, as_enum, LINE_STYLE, TIME, snake_to_camel

def make_js_point(chart, time, price):
    formatted_time = chart._single_datetime_format(time)
    return f'''{{
        "time": {formatted_time},
        "logical": {chart.id}.chart.timeScale()
                    .coordinateToLogical(
                        {chart.id}.chart.timeScale()
                        .timeToCoordinate({formatted_time})
                    ),
        "price": {price}
    }}'''


def _series_alive(series) -> bool:
    """Whether `series` still exists in the chart (its JS handle wasn't deleted).

    Spans/fills are primitives *attached to a series*; if that series was
    already deleted, `detachPrimitive` would reference a dead handle and the
    bridge logs "cannot resolve ...series". Skip the detach in that case.
    """
    chart = getattr(series, '_chart', None)
    lines = getattr(chart, '_lines', None)
    if lines is None:
        return True
    return series is chart or series in lines


def _price_anchors(low, high):
    """``(prices, filled)`` from the (low, high) arguments of a horizontal span."""
    if high is not None:
        return [low, high], True
    if isinstance(low, (list, tuple, pd.Series, pd.Index)):
        return list(low), False
    return [low], False


class Drawing(Pane):
    def __init__(self, chart, func=None):
        super().__init__(chart.win)
        self.chart = chart

    def update(self, *points):
        formatted_points = []
        for i in range(0, len(points), 2):
            formatted_points.append(make_js_point(self.chart, points[i], points[i + 1]))
        self.run_script(f'{self.id}.updatePoints({", ".join(formatted_points)})')

    def delete(self):
        """
        Irreversibly deletes the drawing.
        """
        self.run_script(f'{self.id}.detach()')

    def options(self, color='#1E80F0', style='solid', width=4):
        self.run_script(f'''{self.id}.applyOptions({{
            lineColor: '{color}',
            lineStyle: {as_enum(style, LINE_STYLE)},
            width: {width},
        }})''')

class ThreePointDrawing(Drawing):
    """Base for drawings that need three anchor points."""

    def __init__(self, drawing_type, chart, t1, v1, t2, v2, t3, v3, options=None, func=None):
        super().__init__(chart, func)
        options_string = '\n'.join(f'{key}: {val},' for key, val in (options or {}).items())
        self.run_script(f'''
        {self.id} = new Lib.{drawing_type}(
            {make_js_point(self.chart, t1, v1)},
            {make_js_point(self.chart, t2, v2)},
            {make_js_point(self.chart, t3, v3)},
            {{
                {options_string}
            }}
        )
        {chart.id}.series.attachPrimitive({self.id})
        ''')


class TwoPointDrawing(Drawing):
    def __init__(
        self,
        drawing_type,
        chart,
        start_time: TIME,
        start_value: NUM,
        end_time: TIME,
        end_value: NUM,
        round: bool,
        options: dict,
        func=None
    ):
        super().__init__(chart, func)



        options_string = '\n'.join(f'{key}: {val},' for key, val in options.items())

        self.run_script(f'''
        {self.id} = new Lib.{drawing_type}(
            {make_js_point(self.chart, start_time, start_value)},
            {make_js_point(self.chart, end_time, end_value)},
            {{
                {options_string}
            }}
        )
        {chart.id}.series.attachPrimitive({self.id})
        ''')


class HorizontalLine(Drawing):
    def __init__(self, chart, price, color, width, style, text, axis_label_visible, func,
                 label_visible=False, label_background_color=None,
                 label_text_color=None, label_font=None):
        super().__init__(chart, func)
        self.price = price
        option_lines = [
            f"lineColor: '{color}'",
            f"lineStyle: {as_enum(style, LINE_STYLE)}",
            f"width: {width}",
            f"text: `{text}`",
            f"axisLabelVisible: {jbool(bool(axis_label_visible))}",
        ]
        if label_visible:
            option_lines.append('labelVisible: true')
        if label_background_color:
            option_lines.append(
                f"labelBackgroundColor: '{label_background_color}'")
        if label_text_color:
            option_lines.append(f"labelTextColor: '{label_text_color}'")
        if label_font:
            option_lines.append(f"labelFont: `{label_font}`")
        options_string = ',\n                '.join(option_lines)
        self.run_script(f'''

        {self.id} = new Lib.HorizontalLine(
            {{price: {price}}},
            {{
                {options_string}
            }},
            callbackName={f"'{self.id}'" if func else 'null'}
        )
        {chart.id}.series.attachPrimitive({self.id})
        ''')
        if not func:
            return

        def wrapper(p):
            self.price = float(p)
            func(chart, self)

        async def wrapper_async(p):
            self.price = float(p)
            await func(chart, self)

        self.win.handlers[self.id] = wrapper_async if asyncio.iscoroutinefunction(func) else wrapper
        self.run_script(f'{chart.id}.toolBox?.addNewDrawing({self.id})')

    def update(self, price: float):
        """
        Moves the horizontal line to the given price.
        """
        self.run_script(f'{self.id}.updatePoints({{price: {price}}})')
        # self.run_script(f'{self.id}.updatePrice({price})')
        self.price = price

    def options(self, color='#1E80F0', style='solid', width=4, text='',
                label_visible=None, axis_label_visible=None,
                label_background_color=None, label_text_color=None,
                label_font=None):
        super().options(color, style, width)
        extra = [f'text: `{text}`']
        if label_visible is not None:
            extra.append(f'labelVisible: {jbool(bool(label_visible))}')
        if axis_label_visible is not None:
            extra.append(
                f'axisLabelVisible: {jbool(bool(axis_label_visible))}')
        if label_background_color is not None:
            extra.append(
                f"labelBackgroundColor: '{label_background_color}'")
        if label_text_color is not None:
            extra.append(f"labelTextColor: '{label_text_color}'")
        if label_font is not None:
            extra.append(f'labelFont: `{label_font}`')
        options = '{' + ', '.join(extra) + '}'
        self.run_script(f'{self.id}.applyOptions({options})')


class VerticalLine(Drawing):
    def __init__(self, chart, time, color, width, style, text, func=None):
        super().__init__(chart, func)
        self.time = time
        self.run_script(f'''

        {self.id} = new Lib.VerticalLine(
            {{time: {self.chart._single_datetime_format(time)}}},
            {{
                lineColor: '{color}',
                lineStyle: {as_enum(style, LINE_STYLE)},
                width: {width},
                text: `{text}`,
            }},
            callbackName={f"'{self.id}'" if func else 'null'}
        )
        {chart.id}.series.attachPrimitive({self.id})
        ''')

    def update(self, time: TIME):
        self.time = time
        self.run_script(
            f'{self.id}.updatePoints({{time: {self.chart._single_datetime_format(time)}}})')

    def options(self, color='#1E80F0', style='solid', width=4, text=''):
        super().options(color, style, width)
        self.run_script(f'{self.id}.applyOptions({{text: `{text}`}})')


class RayLine(Drawing):
    def __init__(self,
        chart,
        start_time: TIME,
        value: NUM,
        round: bool = False,
        color: str = '#1E80F0',
        width: int = 2,
        style: LINE_STYLE = 'solid',
        text: str = '',
        func = None,
    ):
        super().__init__(chart, func)
        self.run_script(f'''
        {self.id} = new Lib.RayLine(
            {{time: {self.chart._single_datetime_format(start_time)}, price: {value}}},
            {{
                lineColor: '{color}',
                lineStyle: {as_enum(style, LINE_STYLE)},
                width: {width},
                text: `{text}`,
            }},
            callbackName={f"'{self.id}'" if func else 'null'}
        )
        {chart.id}.series.attachPrimitive({self.id})
        ''')




class Box(TwoPointDrawing):
    def __init__(self,
        chart,
        start_time: TIME,
        start_value: NUM,
        end_time: TIME,
        end_value: NUM,
        round: bool,
        line_color: str,
        fill_color: str,
        width: int,
        style: LINE_STYLE,
        func=None):

        super().__init__(
            "Box",
            chart,
            start_time,
            start_value,
            end_time,
            end_value,
            round,
            {
                "lineColor": f'"{line_color}"',
                "fillColor": f'"{fill_color}"',
                "width": width,
                "lineStyle": as_enum(style, LINE_STYLE)
            },
            func
        )


class TrendLine(TwoPointDrawing):
    def __init__(self,
        chart,
        start_time: TIME,
        start_value: NUM,
        end_time: TIME,
        end_value: NUM,
        round: bool,
        line_color: str,
        width: int,
        style: LINE_STYLE,
        func=None):

        super().__init__(
            "TrendLine",
            chart,
            start_time,
            start_value,
            end_time,
            end_value,
            round,
            {
                "lineColor": f'"{line_color}"',
                "width": width,
                "lineStyle": as_enum(style, LINE_STYLE)
            },
            func
        )


class Fibonacci(TwoPointDrawing):
    """Fibonacci retracement between two points."""

    def __init__(self, chart, start_time, start_value, end_time, end_value,
                 line_color='#787B86', width=1, style='solid',
                 levels=(0, 0.236, 0.382, 0.5, 0.618, 0.786, 1),
                 show_labels=True, fill_background=True,
                 background_color='rgba(41, 98, 255, 0.08)', text_color='#9598A1',
                 func=None):
        levels_js = '[' + ', '.join(str(float(level)) for level in levels) + ']'
        super().__init__(
            "FibonacciRetracement",
            chart,
            start_time,
            start_value,
            end_time,
            end_value,
            False,
            {
                "lineColor": f'"{line_color}"',
                "width": width,
                "lineStyle": as_enum(style, LINE_STYLE),
                "levels": levels_js,
                "showLabels": jbool(show_labels),
                "fillBackground": jbool(fill_background),
                "backgroundColor": f'"{background_color}"',
                "textColor": f'"{text_color}"',
            },
            func
        )


class Measure(TwoPointDrawing):
    """Measurement tool: price delta, percentage and bar count."""

    def __init__(self, chart, start_time, start_value, end_time, end_value,
                 line_color='#2962FF', width=1, style='solid',
                 fill_color='rgba(41, 98, 255, 0.18)', text_color='#FFFFFF',
                 background_color='rgba(41, 98, 255, 0.85)', show_time_range=True,
                 func=None):
        super().__init__(
            "Measure",
            chart,
            start_time,
            start_value,
            end_time,
            end_value,
            False,
            {
                "lineColor": f'"{line_color}"',
                "width": width,
                "lineStyle": as_enum(style, LINE_STYLE),
                "fillColor": f'"{fill_color}"',
                "textColor": f'"{text_color}"',
                "backgroundColor": f'"{background_color}"',
                "showTimeRange": jbool(show_time_range),
            },
            func
        )


class ParallelChannel(TwoPointDrawing):
    """A line through two points plus a parallel line offset by ``offset`` price units."""

    def __init__(self, chart, start_time, start_value, end_time, end_value,
                 offset=0.0, line_color='#2962FF', width=2, style='solid',
                 fill_color='rgba(41, 98, 255, 0.12)', fill_enabled=True, func=None):
        super().__init__(
            "ParallelChannel",
            chart,
            start_time,
            start_value,
            end_time,
            end_value,
            False,
            {
                "lineColor": f'"{line_color}"',
                "width": width,
                "lineStyle": as_enum(style, LINE_STYLE),
                "channelOffset": float(offset),
                "fillColor": f'"{fill_color}"',
                "fillEnabled": jbool(fill_enabled),
            },
            func
        )

    def set_offset(self, offset: float):
        """Move the parallel line by ``offset`` price units."""
        self.run_script(f'{self.id}.applyOptions({{channelOffset: {float(offset)}}})')


class Position(TwoPointDrawing):
    """Risk / reward tool: entry -> target, with an implied stop-loss.

    The stop sits on the opposite side of the entry, ``risk_ratio`` times the
    entry->target distance. Direction (long/short) is inferred from the points.
    """

    def __init__(self, chart, start_time, start_value, end_time, end_value,
                 risk_ratio=1.0, line_color='#787B86', width=1, style='solid',
                 profit_fill_color='rgba(38, 166, 154, 0.25)',
                 loss_fill_color='rgba(239, 83, 80, 0.25)',
                 profit_line_color='#26A69A', loss_line_color='#EF5350',
                 text_color='#FFFFFF', show_labels=True, func=None):
        super().__init__(
            "Position",
            chart,
            start_time,
            start_value,
            end_time,
            end_value,
            False,
            {
                "lineColor": f'"{line_color}"',
                "width": width,
                "lineStyle": as_enum(style, LINE_STYLE),
                "riskRatio": float(risk_ratio),
                "profitFillColor": f'"{profit_fill_color}"',
                "lossFillColor": f'"{loss_fill_color}"',
                "profitLineColor": f'"{profit_line_color}"',
                "lossLineColor": f'"{loss_line_color}"',
                "textColor": f'"{text_color}"',
                "showLabels": jbool(show_labels),
            },
            func,
        )

    def set_risk_ratio(self, risk_ratio: float):
        """Resize the stop-loss zone."""
        self.run_script(f'{self.id}.applyOptions({{riskRatio: {float(risk_ratio)}}})')


class AndrewsPitchfork(ThreePointDrawing):
    """Andrew's pitchfork: median line plus two parallels (3 points)."""

    def __init__(self, chart, t1, v1, t2, v2, t3, v3,
                 line_color='#2962FF', width=1, style='solid',
                 fill_color='rgba(41, 98, 255, 0.08)', fill_enabled=True,
                 extension=4, func=None):
        super().__init__('AndrewsPitchfork', chart, t1, v1, t2, v2, t3, v3, {
            'lineColor': f'"{line_color}"',
            'width': width,
            'lineStyle': as_enum(style, LINE_STYLE),
            'fillColor': f'"{fill_color}"',
            'fillEnabled': jbool(fill_enabled),
            'extension': extension,
        }, func)


class Triangle(ThreePointDrawing):
    """A filled / outlined triangle through three anchor points."""

    def __init__(self, chart, t1, v1, t2, v2, t3, v3,
                 line_color='#2962FF', width=1, style='solid',
                 fill_color='rgba(41, 98, 255, 0.15)', fill_enabled=True, func=None):
        super().__init__('Triangle', chart, t1, v1, t2, v2, t3, v3, {
            'lineColor': f'"{line_color}"',
            'width': width,
            'lineStyle': as_enum(style, LINE_STYLE),
            'fillColor': f'"{fill_color}"',
            'fillEnabled': jbool(fill_enabled),
        }, func)


class FibonacciExtension(ThreePointDrawing):
    """Fibonacci extension: impulse leg p1->p2, projected from the retracement p3."""

    def __init__(self, chart, t1, v1, t2, v2, t3, v3,
                 line_color='#787B86', width=1, style='solid',
                 levels=(0, 0.382, 0.618, 1, 1.272, 1.618, 2, 2.618),
                 show_labels=True, text_color='#9598A1', extension=0.5, func=None):
        levels_js = '[' + ', '.join(str(float(level)) for level in levels) + ']'
        super().__init__('FibonacciExtension', chart, t1, v1, t2, v2, t3, v3, {
            'lineColor': f'"{line_color}"',
            'width': width,
            'lineStyle': as_enum(style, LINE_STYLE),
            'levels': levels_js,
            'showLabels': jbool(show_labels),
            'textColor': f'"{text_color}"',
            'extension': float(extension),
        }, func)


class GannFan(TwoPointDrawing):
    """Gann fan: the p1 -> p2 line is the 1x1, plus steeper and shallower rays."""

    def __init__(self, chart, t1, v1, t2, v2,
                 line_color='#2962FF', width=1, style='solid', ratios=None,
                 extension=3.0, highlight_color='#FF9800', show_labels=False,
                 text_color='#9598A1', func=None):
        if ratios is None:
            ratios = (1 / 8, 1 / 4, 1 / 3, 1 / 2, 1, 2, 3, 4, 8)
        ratios_js = '[' + ', '.join(str(float(ratio)) for ratio in ratios) + ']'
        super().__init__(
            'GannFan',
            chart,
            t1,
            v1,
            t2,
            v2,
            False,
            {
                'lineColor': f'"{line_color}"',
                'width': width,
                'lineStyle': as_enum(style, LINE_STYLE),
                'ratios': ratios_js,
                'extension': float(extension),
                'highlightColor': f'"{highlight_color}"',
                'showLabels': jbool(show_labels),
                'textColor': f'"{text_color}"',
            },
            func,
        )

# TODO reimplement/fix
class LineFill(Pane):
    """Shaded band between two series lines (v5 series primitive).

    Built by :meth:`SeriesCommon.fill_between`; both series must live on the same
    pane and price scale (e.g. the upper/lower lines of Bollinger bands).

    ``opacity`` applies to the fill only (``None`` → keep the colour's own
    alpha); ``line_color``/``line_width``/``line_style`` draw an optional outline.
    """

    def __init__(self, chart: 'AbstractChart', upper: 'SeriesCommon',
                 lower: 'SeriesCommon',
                 color: str = '#2962FF',
                 opacity: Optional[float] = 0.15,
                 line_color: Optional[str] = None,
                 line_width: int = 1,
                 line_style: LINE_STYLE = 'solid'):
        self._chart = chart
        self._upper = upper
        super().__init__(chart.win)

        stroke = f"'{line_color}'" if line_color else 'null'
        alpha = 'null' if opacity is None else float(opacity)
        self.run_script(f'''
        {self.id} = new Lib.LineFill(
            "{lower.id}.series",
            {{fillColor: '{color}', opacity: {alpha},
              lineColor: {stroke},
              width: {line_width}, lineStyle: {as_enum(line_style, LINE_STYLE)}}}
        )
        {upper.id}.series.attachPrimitive({self.id})
        ''')

    def apply_options(self, **options):
        """Update the fill/stroke options at runtime (snake_case is camelCased).

        ``line_style='dashed'`` and friends are converted to the numeric
        ``LineStyle`` the JS side expects.
        """
        for key in ('line_style', 'lineStyle'):
            if key in options:
                options[key] = as_enum(options[key], LINE_STYLE)
        self.win.invoke(self.id, 'applyOptions', options)

    def delete(self):
        """Irreversibly deletes the band.

        It is a v5 series primitive (`PluginBase`), so it is removed with
        `series.detachPrimitive(primitive)` - plugins have no `detach()` of
        their own (the old call raised "...detach is not a function").
        """
        if _series_alive(self._upper):
            self._upper.detach_primitive(self.id)


class HorizontalSpan(Pane):
    """Shaded horizontal band between two prices (v5 series primitive).

    * ``high`` given → a filled band spanning ``[low, high]`` (a support /
      resistance zone, drawn across the whole pane);
    * ``high`` omitted → one full-width horizontal line per price in ``low``
      (a single price, or a list / ``Series`` of prices).

    ``filled`` (default ``None`` → a band when ``high`` is given, single lines
    otherwise) forces either form: ``horizontal_span(98, 108, filled=False)``
    draws the two lines without the fill, ``filled=True`` fills the range between
    the outermost prices even for a list.

    The band is drawn in the pane of the series it is attached to; build it with
    :meth:`SeriesCommon.horizontal_span` (``pane_index=`` targets a pane
    directly).

    ``opacity`` is applied to the fill only (``None`` → use the alpha the colour
    already carries), so ``color='#7E57C2', opacity=0.2`` looks the same as
    ``color='rgba(126, 87, 194, 0.2)'``.

    ``autoscale=True`` makes these prices participate in the pane's auto-scaling,
    so the band cannot be scrolled out of view.
    """

    def __init__(self, series: 'SeriesCommon',
                 low: Union[NUM, tuple, list],
                 high: Optional[NUM] = None,
                 color: str = '#7E57C2',
                 opacity: Optional[float] = 0.2,
                 line_color: str = 'rgba(126, 87, 194, 0.90)',
                 line_width: int = 1,
                 line_style: LINE_STYLE = 'solid',
                 autoscale: bool = False,
                 filled: Optional[bool] = None):
        self._chart = series._chart
        self._series = series
        super().__init__(self._chart.win)

        anchors, auto_filled = _price_anchors(low, high)
        filled = auto_filled if filled is None else bool(filled)
        alpha = 'null' if opacity is None else float(opacity)
        prices = ', '.join(f'{{price: {float(price)}}}' for price in anchors)
        self.run_script(f'''
        {self.id} = new Lib.HorizontalSpan(
            [{prices}],
            {{fillColor: '{color}', opacity: {alpha},
              lineColor: '{line_color}',
              width: {line_width}, lineStyle: {as_enum(line_style, LINE_STYLE)},
              filled: {jbool(filled)}, autoscale: {jbool(autoscale)}}}
        )
        {series.id}.series.attachPrimitive({self.id})
        ''')

    def set_prices(self, low: Union[NUM, tuple, list], high: Optional[NUM] = None):
        """Move the band (same arguments as the constructor)."""
        anchors, _ = _price_anchors(low, high)
        self.win.invoke(self.id, 'setPrices',
                        [{'price': float(price)} for price in anchors])

    def apply_options(self, **options):
        """Update the fill/line options at runtime (snake_case is camelCased).

        ``line_style='dashed'`` and friends are converted to the numeric
        ``LineStyle`` the JS side expects (other keys are passed through).
        """
        for key in ('line_style', 'lineStyle'):
            if key in options:
                options[key] = as_enum(options[key], LINE_STYLE)
        self.win.invoke(self.id, 'applyOptions', options)

    def delete(self):
        """Irreversibly deletes the horizontal span.

        v5 primitive: detach it from the series it was attached to (skip if
        that series is already gone).
        """
        if _series_alive(self._series):
            self._series.detach_primitive(self.id)


class VerticalSpan(Pane):
    """Shaded vertical band between two times (v5 series primitive).

    * ``end_time`` given → a filled band spanning ``[start_time, end_time]``;
    * ``end_time`` omitted → one vertical line per anchor in ``start_time``
      (a single time, or a list / ``DatetimeIndex`` of times).
    """

    def __init__(self, series: 'SeriesCommon', start_time: Union[TIME, tuple, list],
                 end_time: Optional[TIME] = None,
                 color: str = 'rgba(252, 219, 3, 0.2)',
                 opacity: Optional[float] = None):
        self._chart = series._chart
        self._series = series
        super().__init__(self._chart.win)

        if end_time is not None:
            anchors, filled = [start_time, end_time], True
        elif isinstance(start_time, (list, tuple, pd.DatetimeIndex)):
            anchors, filled = list(start_time), False
        else:
            anchors, filled = [start_time], False

        points = ', '.join(
            f'{{time: {self._chart._single_datetime_format(t)}}}' for t in anchors
        )
        self.run_script(f'''
        {self.id} = new Lib.VerticalSpan(
            [{points}],
            {{fillColor: '{color}', filled: {jbool(filled)},
              opacity: {'null' if opacity is None else float(opacity)}}}
        )
        {series.id}.series.attachPrimitive({self.id})
        ''')

    def delete(self):
        """Irreversibly deletes the vertical span.

        v5 primitive: detach it from the series it was attached to (skip if
        that series is already gone).
        """
        if _series_alive(self._series):
            self._series.detach_primitive(self.id)
