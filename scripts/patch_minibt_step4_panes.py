"""Step 4: minibt's indicator sub-charts move from `create_subchart` to native panes.

The two files keep every call site, they just get an `IndicatorPane` adapter that
quacks like the old sub-chart but lives in a *pane* of the main chart. That gives
one webview / one time axis, removes the hand-rolled webview resizing, and makes
removing an indicator drop its series, its legend row and the emptied pane.

Run from the repo root:  python scripts/patch_minibt_step4_panes.py
"""
import ast
import pathlib
import re

REPO = pathlib.Path('minibt/strategy')
DESKTOP = pathlib.Path('C:/Users/Lenovo/Desktop/minibt/strategy')

ADAPTER = '''
class IndicatorPane:
    """指标副图：以前是 ``create_subchart(...)`` 出来的独立图表，现在落在主图的
    **原生 pane**（lightweight-charts v5）上 —— 一条 webview、共享时间轴与十字线。

    保留原来副图对象的方法名，所以上层业务代码基本不用改：

    * 建序列：``create_line`` / ``create_histogram`` / ``set``（OHLC → 蜡烛图）；
    * 更新：``update`` / ``update_from_tick``（转发给本 pane 的"主序列"）；
    * 样式：``layout`` / ``grid`` / ``legend`` / ``crosshair`` / ``watermark``
      （pane 与主图共用同一个 chart，所以转发给主图即可）；
    * ``resize`` 是空实现：高度由引擎按 pane 自动分配，不再手工算每个 webview；
    * ``remove()``：逐个 ``series.delete()``，最后一个删掉后空 pane 由引擎自动去掉；
    * ``is_pane = True``：主图里那些"按图表切分 DOM / 固定价格轴宽度"的老逻辑会跳过它。
    """

    #: 让主图的 DOM / 坐标轴相关老逻辑认得它
    is_pane = True

    def __init__(self, wrapper, name: str = ''):
        self._wrapper = wrapper
        self._chart = wrapper.chart              # pylightcharts 的 QtChart
        self.name = name or 'indicator'
        self.pane = self._chart.add_pane()
        self.series = []                         # 本 pane 里的所有序列
        self.main = None                         # 第一个（"主"）序列

    # ---- 身份 / 桥接 ---------------------------------------------------
    @property
    def id(self) -> str:
        return self._chart.id

    @property
    def win(self):
        return self._chart.win

    @property
    def run_script(self):
        return self._chart.run_script

    def get_webview(self):
        return self._chart.get_webview()

    @property
    def _last_bar(self):
        """本 pane 主序列的最后一根 K 线（``is_changing``/``is_key_changing`` 用）。"""
        series = self.main
        if series is None:
            return {}
        if getattr(series, '_last_bar', None) is None:
            frame = getattr(series, 'data', None)
            if frame is not None and len(frame):
                series._last_bar = frame.iloc[-1]
        last = getattr(series, '_last_bar', None)
        # `_last_bar` is a pandas Series: `or {}` would raise on its truth value
        return {} if last is None else last

    def __repr__(self):
        return (f'<IndicatorPane {self.name!r} pane={self.pane} '
                f'series={len(self.series)}>')

    # ---- 建序列 --------------------------------------------------------
    def _add(self, kind: str, name: str = '', **options):
        if not name:
            # 名字留空：图例文本由 `setSubChartTheme`/`legend` 给
            name = ''
        series = self._chart.pane_add_series(self.pane, kind, name=name,
                                             **options)
        self.series.append(series)
        if self.main is None:
            self.main = series
        return series

    def create_line(self, name='', color='rgba(214, 237, 255, 0.6)',
                    style='solid', width=2, price_line=True, price_label=True,
                    price_scale_id=None, **options):
        if price_scale_id:
            options.setdefault('price_scale_id', price_scale_id)
        return self._add(
            'Line', name, color=color, line_width=width,
            # 'solid' 这类字符串必须转成引擎要的数字（solid → 0）：直接传字符串会
            # 让 applyOptions 抛错，而脚本是批量下发的，一个 JS 错误会把同一批后面
            # 的语句（包括主图数据）全部跳过 —— 表现就是"图表一片空白"
            line_style=util.as_enum(style, util.LINE_STYLE),
            price_line_visible=price_line,
            last_value_visible=price_label, **options)

    def create_histogram(self, name='', color='rgba(214, 237, 255, 0.6)',
                         price_line=True, price_label=True,
                         scale_margin_top=0.0, scale_margin_bottom=0.0,
                         price_scale_id=None, **options):
        if price_scale_id:
            options.setdefault('price_scale_id', price_scale_id)
        series = self._add('Histogram', name, color=color,
                           price_line_visible=price_line,
                           last_value_visible=price_label, **options)
        if scale_margin_top or scale_margin_bottom:
            # keyword names, not positional: the repo's signature guard test reads
            # positional forwards like this one as suspicious
            series.set_scale_margins(top=scale_margin_top,
                                     bottom=scale_margin_bottom)
        return series

    def set(self, df=None, **kwargs):
        """OHLC 数据 → 蜡烛图主序列；否则用单值 Line 主序列。

        （副图的蜡烛图指标走这里，和以前 ``chart.set(candles_df)`` 一样；单值
        序列本文件里都是 ``create_line``/``create_histogram``，不走 ``set``。）
        """
        if self.main is not None:
            self.main.set(df, **kwargs)
            return self.main
        if df is None or len(df) == 0:
            return None
        columns = {str(column).lower() for column in df.columns}
        kind = 'Candlestick' if {'open', 'high', 'low', 'close'} <= columns else 'Line'
        series = self._add(kind, '')
        series.set(df, **kwargs)
        return series

    # ---- 更新 ----------------------------------------------------------
    UPDATE_INDEX = ('time', 'open', 'high', 'low', 'close', 'volume')

    def update(self, row):
        """更新本 pane 的主序列（完整的一根 K 线/一个点）。

        ``SeriesCommon.update`` 收的是 pandas Series（内部按标签取列），传 dict
        会在 ``_series_datetime_format`` 里炸，所以这里统一转一下。
        """
        if self.main is None:
            return None
        if isinstance(row, dict):
            row = pd.Series(row)
        return self.main.update(row)

    def update_from_tick(self, row, cumulative_volume: bool = False):
        """像主图那样把 tick 合并进主序列的最后一根 K 线。

        旧实现是 "tick 先合并进最后一根（high/low/close），时间推进时才开新 bar"，
        这里保持同一语义；时间统一过一遍 ``_single_datetime_format``，避免把
        纳秒时间戳直接塞给引擎。
        """
        series = self.main
        if series is None:
            return None
        values = dict(row)
        price = values.get('price', values.get('close'))
        time_value = values.get('time')
        if time_value is not None:
            time_value = self._chart._single_datetime_format(time_value)
        frame = getattr(series, 'data', None)
        if frame is None or not len(frame) or time_value is None:
            return series.update(pd.Series(values))
        # `series._last_bar` is the bar that is still open: `update()` keeps the
        # running high/low there and only writes it into `series.data` once the
        # next bar arrives, so merging from `data` would lose them
        last_frame = getattr(series, '_last_bar', None)
        if last_frame is None or len(last_frame) == 0:
            last_frame = frame.iloc[-1]
        last = dict(last_frame)
        if time_value != last.get('time'):
            # 新的一根：open/high/low/close 都从 tick 价格开始
            bar = {'time': time_value, 'open': price, 'high': price,
                   'low': price, 'close': price}
        else:
            bar = dict(last)
            bar['high'] = max(last.get('high', price), price)
            bar['low'] = min(last.get('low', price), price)
            bar['close'] = price
        if 'volume' in values:
            if cumulative_volume:
                bar['volume'] = last.get('volume', 0) + values['volume']
            else:
                bar['volume'] = values['volume']
        return series.update(pd.Series(bar))

    # ---- 样式：pane 与主图共用一个 chart，转发 --------------------------
    def layout(self, **options):
        self._chart.layout(**options)

    def grid(self, **options):
        self._chart.grid(**options)

    def legend(self, *args, **options):
        """图例是 chart 级的（pane 与主图共用），转发即可，重复调用幂等。"""
        self._chart.legend(*args, **options)

    def crosshair(self, **options):
        self._chart.crosshair(**options)

    def watermark(self, *args, **options):
        self._chart.watermark(*args, **options)

    def time_scale(self, **options):
        self._chart.time_scale(**options)

    def fit(self):
        """时间轴与主图共用，拟合交给主图（``Chart.fit``/``_fit_chart``）。"""

    def resize(self, *args, **kwargs):
        """空实现：pane 的高度由引擎自动分配，不再手工算 webview 高度。"""

    # ---- 移除 ----------------------------------------------------------
    def remove(self):
        """逐个删掉本 pane 的序列，最后一个删掉后空 pane 由引擎自动去掉。"""
        for series in list(self.series):
            try:
                series.delete()
            except Exception as error:       # 已经删过 / 图表已销毁
                print(f'[minibt] 移除副图序列失败: {error}')
        self.series.clear()
        self.main = None
'''


def sub(text, old, new, label):
    assert text.count(old) == 1, f'{label}: found {text.count(old)}'
    return text.replace(old, new, 1)


def patch(src: str, filename: str) -> str:
    wrapper = 'Chart' if filename == 'light_chart.py' else 'ReplayChart'

    # 1) the adapter, right before the wrapper class
    anchor = f'\nclass {wrapper}'
    if anchor not in src:
        anchor = f'\nclass {wrapper}('
    assert src.count(anchor) == 1, f'{filename}: wrapper class anchor'
    src = src.replace(anchor, ADAPTER + f'\nclass {wrapper}', 1) \
        if anchor == f'\nclass {wrapper}' \
        else src.replace(anchor, ADAPTER + f'\nclass {wrapper}(', 1)

    # 2) the factory, next to `create_subchart`
    old = """    def create_subchart(self, position='left', width=0.5, height=0.5, sync=None,"""
    new = '''    def _indicator_pane(self, name: str = '') -> 'IndicatorPane':
        """指标副图：主图上的一个原生 pane（替代 create_subchart）。

        上层原来的写法——``chart = self.create_subchart('bottom', sync=True)`` 之后
        在 chart 上 ``create_line`` / ``create_histogram`` / ``set`` / ``update``——
        全部照旧，只是这个 ``chart`` 变成了 :class:`IndicatorPane`：一条 webview、
        共享时间轴与十字线，移除指标时连图例标签和空 pane 一起走。
        """
        # 注意：这里刻意不再调用 set_pane_stretch —— pane 的默认比例已经是
        # 主图 2 : 副图 1（引擎默认），而多一次 fire-and-forget 的 JS 调用一旦
        # 出错，会把同一批脚本后面的语句（包括主图数据）一起跳过，风险大于收益。
        return IndicatorPane(self, name)

    def _uses_panes(self) -> bool:
        """副图是否已经是原生 pane（``self.subcharts`` 里放的是 IndicatorPane）。"""
        return any(getattr(chart, 'is_pane', False)
                   for chart in self.subcharts.values())

    def create_subchart(self, position='left', width=0.5, height=0.5, sync=None,'''
    src = sub(src, old, new, f'{filename}: _indicator_pane factory')

    # 3) the creation sites: bottom sub-charts become panes
    pattern = re.compile(
        r"self\.create_subchart\(\s*'bottom',\s*sync=True\)")
    src, count = pattern.subn('self._indicator_pane()', src)
    print(f'  {filename}: {count} create_subchart("bottom") call(s) -> pane')
    assert count >= 3, f'{filename}: expected the bottom sub-chart sites'

    # 4) `_resizes`: panes share the main webview, nothing to resize
    old = """    def _resizes(self):
        \"\"\"指标窗口高度设置,主图占3,副图占1\"\"\""""
    new = """    def _resizes(self):
        \"\"\"指标窗口高度设置,主图占3,副图占1（pane 模式交给引擎自动分配）\"\"\"
        if self._uses_panes():
            # 副图现在是主图里的原生 pane：只有一个 webview，高度由引擎按 pane
            # 拉伸自动分配，原来的"每个副图一个 webview，手工算高度"不再需要
            self.resize(1, 1)
            return"""
    if src.count(old) == 1:
        src = src.replace(old, new, 1)
    else:                                     # replay 的注释不同
        old = """    def _resizes(self):
        \"\"\"副图高度分配\"\"\""""
        new = """    def _resizes(self):
        \"\"\"副图高度分配（pane 模式交给引擎自动分配）\"\"\"
        if self._uses_panes():
            self.resize(1, 1)
            return"""
        src = sub(src, old, new, f'{filename}: _resizes')

    # 5) the DOM helpers: a pane is not a separate webview / axis
    old = """    def add_chart_separator_lines(self):
        \"\"\"
        通过lightweight-charts的容器结构添加分隔线
        \"\"\"
        if not self.subcharts:
            return"""
    if src.count(old) == 1:
        src = src.replace(old, """    def add_chart_separator_lines(self):
        \"\"\"
        通过lightweight-charts的容器结构添加分隔线
        \"\"\"
        if not self.subcharts or self._uses_panes():
            # pane 模式：副图在主图内部，引擎自带 1px 分隔条，不需要这些 DOM 线
            return""", 1)
    old = """    def add_chart_separator_lines(self):
        if not self.subcharts:
            return"""
    if src.count(old) == 1:
        src = src.replace(old, """    def add_chart_separator_lines(self):
        if not self.subcharts or self._uses_panes():
            # pane 模式：副图在主图内部，引擎自带 1px 分隔条
            return""", 1)

    old = """    def set_only_last_chart_xaxis_visible(self):
        \"\"\"
        遍历所有主图+副图，仅最后一个图表显示X轴时间，其余隐藏X轴
        \"\"\"
        # 1. 收集所有图表：主图 + 所有副图"""
    if src.count(old) == 1:
        src = src.replace(old, """    def set_only_last_chart_xaxis_visible(self):
        \"\"\"
        遍历所有主图+副图，仅最后一个图表显示X轴时间，其余隐藏X轴
        \"\"\"
        if self._uses_panes():
            # pane 模式：所有 pane 共享同一个时间轴，本来就只有一条
            return
        # 1. 收集所有图表：主图 + 所有副图""", 1)
    old = """    def set_only_last_chart_xaxis_visible(self):
        all_charts = [self] + list(self.subcharts.values())"""
    if src.count(old) == 1:
        src = src.replace(old, """    def set_only_last_chart_xaxis_visible(self):
        if self._uses_panes():
            return
        all_charts = [self] + list(self.subcharts.values())""", 1)

    old = """    def set_price_scale_fixed_width(self, chart: AbstractChart, target_width: int = None):"""
    if src.count(old) == 1:
        src = src.replace(old, """    def set_price_scale_fixed_width(self, chart: AbstractChart, target_width: int = None):
        if getattr(chart, 'is_pane', False):
            # pane 模式：副图在主图内部，价格轴宽度由主图统一决定
            return""", 1)
    old = """    def set_price_scale_fixed_width(self, chart, target_width: int = None):"""
    if src.count(old) == 1:
        src = src.replace(old, """    def set_price_scale_fixed_width(self, chart, target_width: int = None):
        if getattr(chart, 'is_pane', False):
            return""", 1)

    old = """        bg = self.light_chart_window.mouse_label_color
        if bg:
            charts = [self, *self.subcharts.values()]
            for chart in charts:
                self.set_crosshair_label_background(chart, bg)"""
    if src.count(old) == 1:
        src = src.replace(old, """        bg = self.light_chart_window.mouse_label_color
        if bg:
            # pane 模式：十字线是 chart 级的，主图设一次就够了
            charts = [self] if self._uses_panes() else [self, *self.subcharts.values()]
            for chart in charts:
                self.set_crosshair_label_background(chart, bg)""", 1)

    # 6) cleanup: drop the pane series (the pane goes with them)
    old = """        for name, subchart in list(self.subcharts.items()):
            try:
                subchart_id = subchart.id"""
    if src.count(old) == 1:
        src = src.replace(old, """        for name, subchart in list(self.subcharts.items()):
            try:
                if getattr(subchart, 'is_pane', False):
                    # pane 模式：删掉序列，空 pane 由引擎自动去掉，没有额外的
                    # webview/事件需要清理
                    subchart.remove()
                    continue
                subchart_id = subchart.id""", 1)
    old = """        self.chart_indicators.clear()
        self.subcharts.clear()"""
    if src.count(old) == 1:
        src = src.replace(old, """        self.chart_indicators.clear()
        for subchart in self.subcharts.values():
            if getattr(subchart, 'is_pane', False):
                subchart.remove()
        self.subcharts.clear()""", 1)

    # 7) the type annotation now describes both kinds
    old = "    subcharts: dict[str, AbstractChart]"
    if src.count(old) == 1:
        src = src.replace(
            old, "    # 副图：pane 模式下是 IndicatorPane，旧路径下还是 AbstractChart\n"
                 "    subcharts: dict[str, object]")
    return src


def main() -> int:
    for folder in (REPO, DESKTOP):
        if not folder.is_dir():
            print('skip (missing):', folder)
            continue
        print('patching', folder)
        for filename in ('light_chart.py', 'light_chart_replay.py'):
            path = folder / filename
            src = path.read_text(encoding='utf-8')
            path.write_text(patch(src, filename), encoding='utf-8')
    for folder in (REPO, DESKTOP):
        if not folder.is_dir():
            continue
        for filename in ('light_chart.py', 'light_chart_replay.py'):
            ast.parse((folder / filename).read_text(encoding='utf-8'))
    print('RESULT_OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
