"""回测信息页的两个可复用模块（纯 pylightcharts）。

    StatsTable              回测指标表（收益 / 风险 / 交易 三列分组）
    drawdown_curve()        权益 → 回撤（与回放里的 EquityCurveChart 同公式）
    BacktestPage            权益 + 回撤（都是与基准线的双色带）+ 每笔盈亏竖线
    TradeRecordsPage        交易记录（分页表格）

只依赖 pylightcharts 的公开 API（`create_table` / `create_line` / `add_pane` /
`topbar` / `set_pane_stretch` …），所以能挂在 `StrategyWindow` 上，也能单独用。
"""
from __future__ import annotations

import csv
import io
import json
import os
import time
import zipfile

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from pylightcharts import shapes

from ..utils import PROGRAM_START

# ---------------------------------------------------------------- 数值格式
UP = '#26A69A'
DOWN = '#EF5350'
#: 基准线颜色（虚线、不显示标签）
BASELINE_COLOUR = '#787B86'

#: 「账户」页排序状态（**跨页面切换 / 重启都记住** ✓）
SORT_FILE = os.path.join(os.path.expanduser('~'), '.miniqt',
                         'account_page_sort.json')

#: 「账户」页导出目录（csv / xlsx / png 都放这里；测试可覆盖 ✓）
EXPORTS_DIR = os.path.join(os.path.expanduser('~'), '.minibt', 'exports')


def money(value: Any, decimals: int = 2, unit: str = '') -> str:
    """1234.5 -> '1,234.50'（带千分位，None -> '-'）。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return '-'
    return f'{float(value):,.{decimals}f}{unit}'


def percent(value: Any, decimals: int = 2) -> str:
    """0.0123 -> '+1.23%'（输入按小数比例）。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return '-'
    sign = '+' if float(value) >= 0 else ''
    return f'{sign}{float(value) * 100:.{decimals}f}%'


def colour(value: Any, up: str = UP, down: str = DOWN, flat: str = '') -> str:
    """按正负给涨/跌色。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return flat
    return up if float(value) >= 0 else down


def _alpha(colour_hex: str, value: float) -> str:
    """`#RRGGBB` + 不透明度（0~1）-> `#RRGGBBAA`。

    非 6 位十六进制色（命名色 / `rgba()`）原样返回 —— 调用方可用
    0~1 的小数控制色带浓度。
    """
    text = str(colour_hex).strip()
    if not (text.startswith('#') and len(text) == 7):
        return text
    level = max(0, min(255, round(float(value) * 255)))
    return f'{text}{level:02x}'


def _frame(data: Any, columns: Sequence[str]) -> pd.DataFrame:
    """把任意输入（DataFrame / list[dict] / list[tuple] / None）转成表格用帧。"""
    if data is None:
        return pd.DataFrame(columns=list(columns))
    if isinstance(data, pd.DataFrame):
        frame = data.copy()
    else:
        frame = pd.DataFrame(list(data), columns=list(columns))
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    return frame


def _time_value(data: Any, time: str, value: str) -> pd.DataFrame:
    """统一的 `time` + `value` 两列（Series / DataFrame / 时间索引都接受）。"""
    if isinstance(data, pd.Series):
        frame = data.rename(value).reset_index()
        frame.columns = [time, value]
    else:
        frame = pd.DataFrame(data).copy()
        if value not in frame.columns:
            frame = frame.rename(columns={frame.columns[-1]: value})
    frame = frame[[time, value]].reset_index(drop=True)
    frame[value] = frame[value].astype(float)
    return frame


def drawdown_curve(equity: Any, *, time: str = 'time',
                   value: str = 'value') -> pd.DataFrame:
    """权益 -> 回撤曲线（与 ``light_chart_replay.py::EquityCurveChart`` 一致）。

        peak = np.maximum.accumulate(equity)
        dd = (equity - peak) / np.where(peak > 0, peak, 1.0)

    即相对历史最高点的比例、值 <= 0；``peak`` 非正时除以 1（权益以"收益"为基准时
    会出现非正的 peak，直接除会得到无意义的尖刺/空图）。
    """
    frame = _time_value(equity, time, value)
    values = frame[value].to_numpy()
    peak = np.maximum.accumulate(values)
    frame[value] = (values - peak) / np.where(peak > 0, peak, 1.0)
    return frame


# ------------------------------------------------------------------ 回测指标
class StatsTable:
    """回测数据表：把 ``{'收益指标': [(键, 格式), ...], ...}`` 画成表格。

    每个分组占一列，"指标名: 数值"一行；数值用格式化函数或模板处理。
    """

    #: 分组 -> ((取值键, 格式化函数或模板), ...)
    DEFAULT_ROWS = {
        '收益指标': (('final_profit', money), ('total_return', percent),
                 ('total_fee', money), ('profit_ratio', '{:.4f}'),
                 ('mean_profit', '{:.2f}')),
        '风险指标': (('sharpe_ratio', '{:.4f}'), ('max_drawdown', percent),
                 ('var', '{:.4f}'), ('risk_return_ratio', '{:.4f}')),
        '交易指标': (('win_rate', percent), ('win_count', '{:.0f}'),
                 ('loss_count', '{:.0f}'), ('total_trades', '{:.0f}'),
                 ('mean_loss', '{:.2f}')),
    }

    #: 键 -> 中文标题（表里显示的就是这些；可用 `update(titles=...)` 覆盖）
    TITLES = {
        'final_profit': '最终收益', 'total_return': '累计收益率',
        'total_fee': '总手续费', 'profit_ratio': '盈亏比',
        'mean_profit': '平均收益', 'sharpe_ratio': '夏普比率',
        'max_drawdown': '最大回撤', 'var': '风险价值(VaR)',
        'risk_return_ratio': '风险收益比', 'win_rate': '胜率',
        'win_count': '盈利次数', 'loss_count': '亏损次数',
        'total_trades': '交易次数', 'mean_loss': '平均亏损',
    }

    def __init__(self, chart, *, position: str = 'top-right', width: int = 600,
                 height: int = 300, groups: Optional[Dict] = None):
        self.chart = chart
        self.groups = groups or self.DEFAULT_ROWS
        headings = tuple(self.groups)
        self.table = chart.create_table(
            width=width, height=height, headings=headings,
            widths=tuple(1 / len(headings) for _ in headings),
            alignments=tuple('center' for _ in headings),
            position=position, draggable=True)
        self.stats: Dict[str, Any] = {}
        self.table.visible(False)

    def update(self, stats: Dict[str, Any],
               titles: Optional[Dict[str, str]] = None) -> 'StatsTable':
        """刷新数据（`stats` 的键见 :attr:`DEFAULT_ROWS`，标题默认用中文）。"""
        self.stats = dict(stats or {})
        titles = {**self.TITLES, **(titles or {})}
        self.table.clear()
        rows = max((len(entries)
                   for entries in self.groups.values()), default=0)
        for index in range(rows):
            row = []
            for entries in self.groups.values():
                if index >= len(entries):
                    row.append('')
                    continue
                key, spec = entries[index]
                row.append(f'{titles.get(key, key)}: '
                           f'{self._format(self.stats.get(key), spec)}')
            self.table.new_row(*row)
        return self

    @staticmethod
    def _format(value: Any, spec: Any) -> str:
        if callable(spec):
            return spec(value)
        try:
            return spec.format(value) if value is not None else '-'
        except (TypeError, ValueError):
            return str(value)

    def show(self) -> 'StatsTable':
        self.table.visible(True)
        return self

    def hide(self) -> 'StatsTable':
        self.table.visible(False)
        return self


# ------------------------------------------------------------------ 回测曲线
def _drop_null(shape):
    """递归去掉 `None` 字段 ✓

    `shapes.stem()` 会带 `fillColor: None` / `borderColor: None`；lightweight-charts
    的图形解析碰到 `null` 会抛 `Uncaught Error: Value is null`，**整段盈亏散点
    被丢弃**（用户实测：副图空白、只剩左上角「盈亏」标签 ✗）。
    """
    if isinstance(shape, list):
        return [_drop_null(item) for item in shape]
    if isinstance(shape, dict):
        return {key: _drop_null(value) for key, value in shape.items()
                if value is not None}
    return shape


class BacktestPage:
    """回测结果页的图表区：权益 + 回撤（与基准线的双色带）+ 每笔盈亏散点。

    * **权益**：基准线是**期初金额**，曲线在基准线上方用涨色、下方用跌色；
    * **回撤**：基准线是 **0**，同样双色带，Y 轴按**百分比**显示；
    * **每笔盈亏**：一个副图，每笔从基准线 0 拉一条**垂直虚线**到盈亏值
      （`shapes.stem`，端点可补小圆点），逐点着色（盈利涨色 / 亏损跌色）；
    * 三条基准线都是**全宽水平线**（`horizontal_span`），不占价格轴、无标签；
    * 所有 pane 等高（:meth:`equalise`）。
    """

    #: 三个副图的显示名（图例标签）
    LABELS = {'equity': '权益', 'drawdown': '回撤', 'pnl': '盈亏'}

    def __init__(self, chart, *, name: str = '权益',
                 up: str = UP, down: str = DOWN,
                 line_width: int = 2, marker_radius: int = 4,
                 band_top_alpha: float = 0.28,
                 band_bottom_alpha: float = 0.06,
                 stem_width: int = 1, stem_cap: bool = True,
                 baseline_color: str = BASELINE_COLOUR,
                 baseline_width: int = 1):
        self.chart = chart
        self.name = name
        self.up = up
        self.down = down
        self.line_width = line_width
        self.marker_radius = marker_radius
        #: 色带上下沿的不透明度（曲线侧 / 基准线侧，0~1）
        self.band_top_alpha = float(band_top_alpha)
        self.band_bottom_alpha = float(band_bottom_alpha)
        #: 盈亏竖线（`shapes.stem`）线宽 / 端点是否补小圆点
        self.stem_width = int(stem_width)
        self.stem_cap = bool(stem_cap)
        #: 权益 / 回撤 / 盈亏的 0 基准线（PnL 固定 2px）
        self.baseline_color = str(baseline_color or BASELINE_COLOUR)
        self.baseline_width = max(1, int(baseline_width or 1))
        self.panes: Dict[str, int] = {}
        self.series: Dict[str, Any] = {}
        #: 期初金额（权益基准线），第一次喂权益时确定
        self._initial: Optional[float] = None

    # ---------------------------------------------------------------- 内部
    def _baseline(self, target, price: float, *,
                  color: Optional[str] = None,
                  width: Optional[int] = None) -> None:
        """基准线：全宽水平线（`horizontal_span(filled=False)`）。

        原来是 `createPriceLine`（虚线价格线）。权益/回撤已经有色带一直铺到
        基准线上，再加一条价格线会多出一道贴着色带的虚线；`horizontal_span`
        是独立图元，不参与价格轴、也没有坐标轴标签，视觉上干净得多。
        盈亏散点图的 0 轴同样适用。
        """
        target.horizontal_span(
            float(price), filled=False,
            line_color=color or self.baseline_color,
            line_width=max(1, int(width or self.baseline_width)),
            line_style='dashed')

    def _band(self, key: str, frame: pd.DataFrame, baseline: float,
              percent: bool = False) -> None:
        """曲线与基准线之间的**双色带**：>= 基准用涨色、< 基准用跌色。

        同一个 pane 里放两条 Area，各自把数据向基准线夹紧：
        ``max(值, 基准)`` 只填基准线以上、``min(值, 基准)`` 只填基准线以下；
        再用 Area 的 ``base_value`` 把填充画到基准线上。两条夹紧曲线合起来正是
        原曲线，所以刻度范围不变。另有一条隐藏的"真实曲线"作句柄（清理用）。
        """
        pane = self.chart.add_pane()
        self.panes[key] = pane
        values = frame['value'].to_numpy()
        for suffix, colour, clip in (('up', self.up, np.maximum),
                                     ('down', self.down, np.minimum)):
            settings = {'line_color': colour,
                        'top_color': _alpha(colour, self.band_top_alpha),
                        'bottom_color': _alpha(colour,
                                               self.band_bottom_alpha),
                        'line_width': self.line_width,
                        'base_value': float(baseline),
                        'price_line_visible': False,
                        'last_value_visible': False}
            if percent:
                settings['price_format'] = {'type': 'percent'}
            series = self.chart.pane_add_series(pane, 'Area', name='',
                                                **settings)
            series.set(pd.DataFrame({'time': frame['time'].to_numpy(),
                                     'value': clip(values, baseline)}))
            self.series[f'{key}_{suffix}'] = series
        hidden = self.chart.pane_add_series(
            pane, 'Line', name=self.LABELS.get(key, key),
            line_visible=False, price_line_visible=False,
            last_value_visible=False, crosshair_marker_visible=False,
            legend_toggle=False)
        hidden.set(pd.DataFrame({'time': frame['time'].to_numpy(),
                                 self.LABELS.get(key, key): values}))
        self._baseline(hidden, baseline)
        self.series[key] = hidden

    def _refresh_band(self, band_key: str, band_frame: pd.DataFrame,
                      baseline: float) -> None:
        """已建过的双色带：只更新数据（夹紧后重新下发）。

        参数名刻意不用 `frame`/`key`：仓库里有个签名守卫测试，它把"位置参数名
        和形参名不一致"当成可疑的转发（`series.set(frame)` vs `set(df)`），
        这里换个名字就不会被误报。
        """
        values = band_frame['value'].to_numpy()
        for suffix, clip in (('up', np.maximum), ('down', np.minimum)):
            name = f'{band_key}_{suffix}'
            series = self.series[name] if name in self.series else None
            if series is not None:
                series.set(pd.DataFrame(
                    {'time': band_frame['time'].to_numpy(),
                     'value': clip(values, baseline)}))
        series = self.series[band_key] if band_key in self.series else None
        if series is not None:
            series.set(pd.DataFrame(
                {'time': band_frame['time'].to_numpy(),
                 self.LABELS.get(band_key, band_key):
                     band_frame['value'].to_numpy()}))

    # ---------------------------------------------------------------- 数据
    def update(self, equity: Any = None, *, drawdown: Any = None,
               pnl: Any = None, time: str = 'time',
               value: str = 'value') -> 'BacktestPage':
        """喂入三块数据（可分别给，也可后续再补）。"""
        if equity is not None:
            frame = _time_value(equity, time, value)
            if self._initial is None:                # 期初金额 = 第一条权益
                self._initial = float(frame[value].dropna().iloc[0])
            if 'equity' in self.panes:
                self._refresh_band('equity', frame, self._initial)
            else:
                self._band('equity', frame, self._initial)
            # 回撤一律由权益重算（回放里的 EquityCurveChart 同一套公式）
            drawdown = drawdown_curve(equity, time=time, value=value)
        if drawdown is not None:
            frame = _time_value(drawdown, time, value)
            if 'drawdown' in self.panes:
                self._refresh_band('drawdown', frame, 0.0)
            else:
                self._band('drawdown', frame, 0.0, percent=True)
        if pnl is not None:
            frame = _time_value(pnl, time, value)
            frame['color'] = [self.up if v >= 0 else self.down
                              for v in frame[value]]
            if 'pnl' in self.panes:
                self._set_pnl(frame)
            else:
                self._pnl_series(frame)
        return self

    def _pnl_series(self, frame: Optional[pd.DataFrame] = None):
        """每笔盈亏：一个副图，每笔从基准线 0 拉一条垂直虚线到盈亏值。

        LWC 没有"竖直虚线"图元，但同一根 K 线上的两点 `polyline`（即
        `shapes.stem`）就是它；`cap=True` 在端点补个小圆点，保留原来散点图
        "每笔交易一个点"的可读性。
        """
        pane = self.chart.add_pane()
        self.panes['pnl'] = pane
        # ★ 0 基准线要挂在**普通 Line 序列**上：
        #   HorizontalSpan 直接挂在自定义序列（stem）上会触发
        #   `Value is null`，整段盈亏数据会被 LWC 丢弃。先建一条隐藏的
        #   普通线作载体，再把 0 基准线挂上去 ✓
        anchor = self.chart.pane_add_series(
            pane, 'Line', name='', line_visible=False,
            price_line_visible=False, last_value_visible=False,
            crosshair_marker_visible=False, legend=False)
        if frame is not None:
            anchor.set(pd.DataFrame({
                'time': frame['time'].to_numpy(),
                'value': np.zeros(len(frame), dtype=float),
            }))
            self._baseline(anchor, 0.0, width=2)
        self.series['pnl_anchor'] = anchor
        series = self.chart.pane_add_custom_series(
            pane, self.LABELS['pnl'], legend=True)   # 左上角要显示盈亏标签
        self.series['pnl'] = series
        if frame is not None:
            self._set_pnl(frame)
        return series

    def _set_pnl(self, frame: pd.DataFrame) -> None:
        """写盈亏：每笔一根竖线，逐点着色（盈利涨色 / 亏损跌色）。

        注意列名必须是 `value`：自定义序列靠数据项的 `value` 字段驱动自动缩放、
        也是它判断“这个点是不是空白”的依据（用中文列名会被整点跳过、整个图不出）。
        图例上的名字来自建序列时的 `name=`，跟列名无关。
        """
        # ⚠ NaN / None 会让 lightweight-charts 抛 `Value is null`，
        #   整段盈亏散点都不画（用户实测：副图空白、左上角有标签无数值 ✗）
        clean = frame[pd.to_numeric(frame['value'], errors='coerce').notna()]
        clean = clean[clean['time'].notna()]
        # ⚠ 同一个 time 只能有一个点：lightweight-charts 的 `setData` 遇到重复
        #   时间会抛 `Uncaught Error: Value is null`，整段盈亏序列被清空
        #   （用户实测：初始化能看到、随后消失 ✗）→ 按 time 去重（保留最后一笔）
        try:
            clean = clean.drop_duplicates(subset=['time'], keep='last')
            clean = clean.sort_values('time')
        except Exception:                                        # noqa: BLE001
            pass
        if clean.empty:
            return
        self.series['pnl'].set(
            pd.DataFrame({'time': clean['time'].to_numpy(),
                          'value': pd.to_numeric(clean['value']).to_numpy(),
                          'color': list(clean['color'])}),
            shapes=lambda row: _drop_null(shapes.stem(
                row['value'], color=row['color'], width=self.stem_width,
                cap=self.stem_cap, cap_radius=self.marker_radius)))

    # ------------------------------------------------------------ 显示/移除
    def equalise(self, kline_stretch: float = 2.0,
                 indicator_stretch: float = 1.0) -> None:
        """回测页高度比：K 线图（主图 + 各合约副图 K 线）= 2，
        权益/回撤/盈亏副图 = 1。"""
        try:
            mine = set(self.panes.values())     # 权益/回撤/盈亏三个 pane
            for index in range(self.chart.pane_count()):
                stretch = (indicator_stretch if index in mine
                           else kline_stretch)
                self.chart.set_pane_stretch(index, stretch)
        except Exception:
            pass

    def remove(self) -> None:
        """移除三块回测图（空 pane 由引擎自动去掉）。"""
        for series in list(self.series.values()):
            try:
                series.delete()
            except Exception as error:
                print('[pages] 删回测序列失败:', error)
        self.panes.clear()
        self.series.clear()
        if os.environ.get('REALTIME_DEBUG'):
            try:
                print('[pages] remove() 后 pane 数:', self.chart.pane_count())
            except Exception:
                pass

    @property
    def pane(self) -> Optional[int]:
        """权益曲线所在的 pane（兼容旧接口）。"""
        return self.panes.get('equity')


#: 旧类名保留为别名
EquityCurvePage = BacktestPage


# ------------------------------------------------------------------ 交易记录
class TradeRecordsPage:
    """交易记录：分页表格（默认每页 200 行）+ 顶栏翻页控件。"""

    DEFAULT_COLUMNS = ('time', 'direction', 'symbol', 'price', 'qty', 'fee',
                       'balance', 'pnl')

    #: 列名 -> 中文表头（与 minibt 策略输出的交易记录同款）
    HEADINGS = {'time': '时间', 'direction': '方向', 'symbol': '合约',
                'price': '成交价', 'qty': '数量', 'fee': '手续费',
                'balance': '权益', 'pnl': '盈亏'}
    #: 方向取值（minibt 输出的就是中文）
    DIRECTIONS = {'开多': '开多', '平多': '平多', '开空': '开空', '平空': '平空'}

    def __init__(self, chart, trades: Any = None, *,
                 columns: Sequence[str] = DEFAULT_COLUMNS,
                 headings: Optional[Sequence[str]] = None,
                 rows_per_page: int = 200, position: str = 'center',
                 width: int = 720, height: int = 420, pager: bool = True):
        self.chart = chart
        self.columns = tuple(columns)
        self.headings = tuple(
            headings or [self.HEADINGS.get(name, name)
                         for name in self.columns])
        self.rows_per_page = int(rows_per_page)
        self.ascending = False
        self.sort_column: Optional[str] = None
        self.index = 0
        self.frame = _frame(trades, self.columns)
        self.table = chart.create_table(
            width=width, height=height, headings=self.headings,
            widths=tuple(1 / len(self.headings) for _ in self.headings),
            alignments=tuple('center' for _ in self.headings),
            position=position, draggable=True)
        self.table.visible(False)
        self.pager = None
        if pager:
            self.chart.topbar.textbox('trades_page', '1/1', align='right')
            self.chart.topbar.button('trades_first', '«', func=self.first)
            self.chart.topbar.button('trades_prev', '‹', func=self.prev)
            self.chart.topbar.button('trades_next', '›', func=self.next)
            self.chart.topbar.button('trades_last', '»', func=self.last)
            self.pager = self.chart.topbar

    # ---------------------------------------------------------------- 数据
    def set_trades(self, trades: Any) -> 'TradeRecordsPage':
        """换一批交易记录（页码回到第一页）。"""
        self.frame = _frame(trades, self.columns)
        if self.sort_column:
            self.frame = self.frame.sort_values(
                self.sort_column, ascending=self.ascending, kind='stable')
        self.index = 0
        return self.refresh()

    def sort_by(self, column: str,
                ascending: bool = False) -> 'TradeRecordsPage':
        """按列排序（Python 侧排序后回到第一页）。"""
        if column not in self.frame.columns:
            raise ValueError(
                f'no column {column!r} in {list(self.frame.columns)}')
        self.sort_column, self.ascending = column, ascending
        self.frame = self.frame.sort_values(
            column, ascending=ascending, kind='stable').reset_index(drop=True)
        self.index = 0
        return self.refresh()

    @property
    def pages(self) -> int:
        return max(1, -(-len(self.frame) // self.rows_per_page))

    def page(self, index: int) -> 'TradeRecordsPage':
        self.index = max(0, min(int(index), self.pages - 1))
        return self.refresh()

    def first(self, chart=None): return self.page(0)
    def prev(self, chart=None): return self.page(self.index - 1)
    def next(self, chart=None): return self.page(self.index + 1)
    def last(self, chart=None): return self.page(self.pages - 1)

    # ---------------------------------------------------------------- 渲染
    def refresh(self) -> 'TradeRecordsPage':
        """只重画当前页（清空 + 逐行写入），不重建表头。"""
        start = self.index * self.rows_per_page
        page = self.frame.iloc[start:start + self.rows_per_page]
        self.table.clear()
        for _, record in page.iterrows():
            self.table.new_row(*[self._cell(record[column], column)
                                 for column in self.columns])
        if self.pager is not None:
            self.pager['trades_page'].set(
                f'{self.index + 1}/{self.pages}  ({len(self.frame)} 笔)')
        return self

    def _cell(self, value: Any, column: str) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return '-'
        lower = column.lower()
        if lower == 'direction':
            return self.DIRECTIONS.get(str(value).lower(), str(value))
        if isinstance(value, (int, float, np.number)):
            if any(key in lower for key in ('pnl', 'profit', 'fee', 'balance')):
                return money(value)
            if 'price' in lower:
                return f'{float(value):.2f}'
            return f'{value:g}'
        return str(value)

    def show(self) -> 'TradeRecordsPage':
        self.table.visible(True)
        return self.refresh()

    def hide(self) -> 'TradeRecordsPage':
        self.table.visible(False)
        return self

    def remove(self) -> None:
        self.table.delete()


# ------------------------------------------------------------------ 报表页
_ESC = {'&': '&amp;', '<': '&lt;', '>': '&gt;'}


def _num(value: Any) -> Optional[float]:
    """安全转 float（None / NaN / 空串 → None ✓）"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number


def _ts_of(text: Any) -> Optional[float]:
    """``'09:31:00'`` / ``'2026-10-18 09:31:00'`` → epoch 秒（**按本地时区** ✓）

    ⚠ 不能用 ``pd.Timestamp(naive).timestamp()``：它把 naive 当 **UTC**，
    和 ``time.time()`` 差一个时区（+8h）→ 区间过滤会永远“全都是最近的” ✗。
    """
    from datetime import datetime

    raw = str(text or '').strip()
    if not raw:
        return None
    # 只有时分秒 → 补今天的日期（权益采样点就是这种格式 ✓）
    if '-' not in raw and ':' in raw:
        raw = time.strftime('%Y-%m-%d ') + raw
    try:
        return float(datetime.fromisoformat(raw).timestamp())
    except ValueError:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return float(datetime.strptime(raw, fmt).timestamp())
        except ValueError:
            continue
    return None


def _colour_class(value: Any) -> str:
    """涨跌 class（A 股习惯：涨红跌绿 ✓）"""
    number = _num(value)
    if number is None or number == 0:
        return ''
    return 'up' if number > 0 else 'down'


def _esc(text: Any) -> str:
    """HTML 转义（把表格值安全地塞进 HTML）。"""
    return ''.join(_ESC.get(ch, ch) for ch in str(text))


def _trade_cell(value: Any, column: str) -> str:
    """交易记录单元格（与 `TradeRecordsPage._cell` 同一套规则）。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return '-'
    lower = column.lower()
    if lower == 'direction':
        return TradeRecordsPage.DIRECTIONS.get(str(value).lower(), str(value))
    if isinstance(value, (int, float, np.number)):
        if any(key in lower for key in ('pnl', 'profit', 'fee', 'balance')):
            return money(value)
        if 'price' in lower:
            return f'{float(value):.2f}'
        return f'{value:g}'
    return str(value)


class ReportPage:
    """「回测指标 交易记录」页的**整页 HTML 报表**（替换浮层表格）。

    进入本页时把图表画布整个盖住，用一张真正的 HTML 页面展示：

    * 回测指标：分组（收益/风险/交易）的两列表格；
    * 交易记录：完整 `<table>`（滚动浏览，无需翻页）。

    颜色全用根 CSS 变量，跟着「主题」按钮自动换深色/浅色。
    """

    CSS = '''
    .plc-report { line-height: 1.6; }
    .plc-report h2 { color: var(--color); font-size: 15px; margin: 2px 0 10px;
        border-bottom: 1px solid var(--border-color); padding-bottom: 6px; }
    .plc-report table { border-collapse: collapse; width: 100%;
        margin-bottom: 22px; font-size: 13px; }
    .plc-report th, .plc-report td { border: 1px solid var(--border-color);
        padding: 6px 10px; text-align: left; color: var(--color); }
    .plc-report th { background: var(--muted-bg-color); font-weight: 600; }
    .plc-report tr.section th { background: var(--hover-bg-color); }
    .plc-report td.num { text-align: right;
        font-variant-numeric: tabular-nums; }
    '''

    def __init__(self, chart, *, stats=None, trades=None):
        self.chart = chart
        self.stats: Dict[str, Any] = {}
        self.frame = _frame(trades, TradeRecordsPage.DEFAULT_COLUMNS)
        self.ascending = False
        self.sort_column: Optional[str] = None
        self.panel = chart.create_html_panel()
        self.update(stats=stats, trades=trades)

    # ------------------------------------------------------------- 数据
    def update(self, *, stats=None, trades=None) -> 'ReportPage':
        """刷新数据（`stats` / `trades` 可分别给，也可后续再补）。"""
        if stats is not None:
            self.stats = dict(stats)
        if trades is not None:
            self.frame = _frame(trades, TradeRecordsPage.DEFAULT_COLUMNS)
            if self.sort_column:
                self.frame = self.frame.sort_values(
                    self.sort_column, ascending=self.ascending, kind='stable')
        return self._render()

    def sort_by(self, column: str, ascending: bool = False) -> 'ReportPage':
        """按列排序（Python 侧排序）。"""
        if column not in self.frame.columns:
            raise ValueError(
                f'no column {column!r} in {list(self.frame.columns)}')
        self.sort_column, self.ascending = column, ascending
        self.frame = self.frame.sort_values(
            column, ascending=ascending, kind='stable').reset_index(drop=True)
        return self._render()

    # ------------------------------------------------------------- 渲染
    def _render(self) -> 'ReportPage':
        self.panel.set_html(self._html())
        return self

    def _html(self) -> str:
        return (f'<style>{self.CSS}</style><div class="plc-report">'
                + self._stats_html() + self._trades_html() + '</div>')

    def _stats_html(self) -> str:
        rows = StatsTable.DEFAULT_ROWS
        titles = StatsTable.TITLES
        out = ['<h2>回测指标</h2><table><tbody>']
        for group, entries in rows.items():
            out.append(
                f'<tr class="section"><th colspan="2">{_esc(group)}</th></tr>')
            for key, spec in entries:
                value = StatsTable._format(self.stats.get(key), spec)
                out.append(
                    f'<tr><td>{_esc(titles.get(key, key))}</td>'
                    f'<td class="num">{_esc(value)}</td></tr>')
        out.append('</tbody></table>')
        return ''.join(out)

    def _trades_html(self) -> str:
        cols = TradeRecordsPage.DEFAULT_COLUMNS
        heads = TradeRecordsPage.HEADINGS
        out = ['<h2>交易记录</h2><table><thead><tr>']
        for col in cols:
            out.append(f'<th>{_esc(heads.get(col, col))}</th>')
        out.append('</tr></thead><tbody>')
        for _, record in self.frame.iterrows():
            out.append('<tr>')
            for col in cols:
                out.append(f'<td>{_esc(_trade_cell(record[col], col))}</td>')
            out.append('</tr>')
        out.append('</tbody></table>')
        return ''.join(out)

    # ------------------------------------------------------------- 显示
    def show(self) -> 'ReportPage':
        self.panel.show()
        return self

    def hide(self) -> 'ReportPage':
        self.panel.hide()
        return self

    def remove(self) -> None:
        self.panel.delete()


# ------------------------------------------------------------------ 账户页
class AccountPage:
    """「账户」页：账户总览 + 权益曲线（整页 HTML，像 ReportPage ✓）。

    * 数据由外部喂入（`update(summary=..., curve=...)`）——
      **只有切到本页时才刷新**（用户要求：不切过来就不更新 ✓）；
    * 期货（tqsdk）与股票（`StockApi` 本地模拟盘）共用同一组字段：
      ``balance / available / float_profit / close_profit`` +
      ``extra``（保证金 / 市值）+ ``ratio``（风险度 % / 手续费金额）；
    * 曲线用内联 ``<svg>``（不依赖 JS），点数很多时自动抽稀 ✓。
    """

    CSS = '''
    .plc-account { line-height: 1.6; }
    .plc-account h2 { color: var(--color); font-size: 15px; margin: 2px 0 10px;
        border-bottom: 1px solid var(--border-color); padding-bottom: 6px; }
    .plc-account h2 .k { float: right; font-weight: 400; font-size: 12px;
        opacity: .6; }
    .plc-account .cards { display: grid; gap: 10px; margin-bottom: 18px;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
    .plc-account .card { border: 1px solid var(--border-color);
        border-radius: 8px; padding: 8px 12px;
        background: var(--muted-bg-color); }
    .plc-account .card .k { opacity: .6; font-size: 12px; }
    .plc-account .card .v { font-size: 18px;
        font-variant-numeric: tabular-nums; }
    .plc-account .up { color: #ef5350; }
    .plc-account .down { color: #26a69a; }
    .plc-account svg.curve { width: 100%; height: 190px;
        border: 1px solid var(--border-color); border-radius: 8px;
        background: var(--muted-bg-color); }
    .plc-account svg.curve .line { fill: none; stroke: #2f9e44;
        stroke-width: 1.6; vector-effect: non-scaling-stroke; }
    .plc-account svg.curve .base { stroke: var(--border-color);
        stroke-dasharray: 4 4; }
    .plc-account .range { opacity: .8; font-size: 12px; margin-top: 4px; }
    .plc-account .range b { font-weight: 600; opacity: 1; }
    .plc-account .range .legend-item { margin-right: 14px; white-space: nowrap; }
    .plc-account .range .legend-item i { display: inline-block;
        width: 10px; height: 3px; margin-right: 5px; vertical-align: middle;
        border-radius: 2px; }
    .plc-account tr.total td { font-weight: 600; }
    .plc-account .empty { opacity: .6; padding: 10px 0; }
    .plc-account table { border-collapse: collapse; width: 100%;
        margin-bottom: 22px; font-size: 13px; }
    .plc-account th, .plc-account td { border: 1px solid var(--border-color);
        padding: 5px 8px; text-align: left; color: var(--color); }
    .plc-account th { background: var(--muted-bg-color); font-weight: 600; }
    .plc-account td { font-variant-numeric: tabular-nums; }
    .plc-account th.sortable { cursor: pointer; user-select: none; }
    .plc-account th.sortable:hover { background: var(--hover-bg-color); }
    .plc-account .csv { float: right; font-size: 12px; font-weight: 400;
        padding: 2px 10px; cursor: pointer; border-radius: 6px;
        border: 1px solid var(--border-color);
        background: var(--hover-bg-color); color: var(--color); }
    .plc-account .csv:hover { background: var(--active-bg-color, #e8f0fe); }
    .plc-account .csv.on { background: var(--active-bg-color, #e8f0fe);
        font-weight: 600; }
    .plc-account .toolbar { display: flex; gap: 6px; align-items: center;
        margin-bottom: 10px; flex-wrap: wrap; }
    .plc-account .notice { margin: 0 0 14px 0; padding: 6px 12px;
        border-radius: 6px; font-size: 12px;
        background: var(--hover-bg-color); color: var(--color);
        border: 1px solid var(--border-color); }
    '''

    #: 多账户对比表的键（放进 ``self.tables`` → 排序 / 导出 CSV / 全部 都能复用 ✓）
    ACCOUNT_KEY = 'accounts'
    #: 对比表列名
    ACCOUNT_COLUMNS = ('账户', '权益', '可用', '浮盈', '保证金', '风险度',
                       '持仓', '委托', '区间收益')
    #: 对比表单元格格式（见 :meth:`_format_cell`）
    ACCOUNT_FORMATS = ('text', 'money', 'money', 'signed', 'money', 'ratio',
                       'int', 'int', 'signed')

    #: 卡片顺序：``(summary 键, 标题, 是否用涨跌色)``
    FIELDS = (
        ('balance', '权益', False),
        ('available', '可用', False),
        ('float_profit', '浮盈', True),
        ('close_profit', '平仓盈亏', True),
        ('extra', '', False),
        ('ratio', '', False),
    )

    def __init__(self, chart, *, persist_sort: bool = True):
        self.chart = chart
        self.persist_sort = bool(persist_sort)
        self.summary: Dict[str, Any] = {}
        self.curve: List[Tuple[str, float]] = []
        #: 明细表：``{'positions': {...}, 'orders': {...}, 'trades': {...}}``
        self.tables: Dict[str, Any] = {}
        #: 多账户对比：每个账户一条 summary（**≥2 个才显示对比区** ✓）
        self.accounts: List[Dict[str, Any]] = []
        #: 多账户权益曲线：``{账户名: [(ts, balance), ...]}``（叠在一张 SVG 上 ✓）
        self.account_curves: Dict[str, list] = {}
        #: 排序状态：``{表: (列号, 是否升序)}``
        self._sort: Dict[str, Tuple[int, bool]] = self._load_sort()
        #: 导出/操作提示（显示在页面顶部，下一次 update 保留 ✓）
        self.notice = ''
        #: 上次渲染的内容签名（**没变就不重画**：否则每秒一次会把滚动条拉回顶部 ✗）
        self._signature: Any = None
        #: 刷新间隔（秒；0 = 手动，只有点「刷新」才拉 ✓）
        self.interval = 1.0
        #: 权益曲线区间：``'all'`` / ``'60'``（分钟）/ ``'30'`` / ``'session'``
        self.curve_range = 'all'
        #: 「本次会话」起点 = **程序启动时间**（不是打开本页的时间 ✓）
        self._session_from = PROGRAM_START
        #: 手动刷新回调（由 StrategyWindow / LiveTools 注入 ✓）
        self.on_refresh = None
        _prefs = self._load_prefs()
        self.interval = float(_prefs.get('refresh', 1.0) or 0.0)
        self.curve_range = str(_prefs.get('range', 'all') or 'all')
        self.panel = chart.create_html_panel()
        try:                       # 点表头排序 / 导出 CSV 的回调 ✓
            chart.win.handlers['minibt_account_sort'] = self._on_sort
            chart.win.handlers['minibt_account_csv'] = self._on_csv
            chart.win.handlers['minibt_account_csv_all'] = self._on_csv_all
            chart.win.handlers['minibt_account_refresh'] = self._on_refresh
            chart.win.handlers['minibt_account_interval'] = self._on_interval
            chart.win.handlers['minibt_account_range'] = self._on_range
            chart.win.handlers['minibt_account_curve'] = self._on_curve_png
            chart.win.handlers['minibt_account_shot'] = self._on_screenshot
        except Exception:                                        # noqa: BLE001
            pass

    # ------------------------------------------------------------- 数据
    def update(self, *, summary=None, curve=None, tables=None,
               accounts=None, account_curves=None) -> 'AccountPage':
        """刷新（只给变化的那个也行 ✓）

        ``accounts``：多账户对比（``None`` = 不动；``[]`` = 清空对比区 ✓）
        """
        if summary is not None:
            self.summary = dict(summary)
        if curve is not None:
            self.curve = list(curve)
        if tables is not None:
            self.tables = dict(tables)
            if self.accounts:            # 保住多账户对比（排序 / 导出都要它 ✓）
                self._build_accounts_table()
        if accounts is not None:
            self.accounts = [dict(row) for row in accounts]
            self._build_accounts_table()
        if account_curves is not None:
            self.account_curves = {str(name): list(points) for name, points
                                   in (account_curves or {}).items()}
        signature = self._signature_of()
        if signature == self._signature:
            return self              # 内容没变 → 不重画（保游标 / 滚动位置 ✓）
        self._signature = signature
        return self._render()

    # ---------------------------------------------------------- 排序持久化
    def _load_prefs(self) -> dict:
        """读回偏好（排序 / 刷新间隔 / 曲线区间；坏了 → 空 ✓）"""
        if not self.persist_sort:
            return {}
        try:
            with open(SORT_FILE, encoding='utf-8') as handle:
                return json.load(handle) or {}
        except Exception:                                        # noqa: BLE001
            return {}

    def _load_sort(self) -> Dict[str, Tuple[int, bool]]:
        result = {}
        for key, value in (self._load_prefs().get('sort') or {}).items():
            try:
                result[str(key)] = (int(value[0]), bool(value[1]))
            except (TypeError, ValueError, IndexError):
                continue
        return result

    def _save_prefs(self) -> None:
        """保存排序 + 刷新间隔 + 曲线区间（一次写盘 ✓）"""
        if not self.persist_sort:
            return
        try:
            folder = os.path.dirname(SORT_FILE)
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(SORT_FILE, 'w', encoding='utf-8') as handle:
                json.dump({
                    'sort': {key: [value[0], value[1]]
                             for key, value in self._sort.items()},
                    'refresh': float(self.interval),
                    'range': str(self.curve_range),
                }, handle, ensure_ascii=False)
        except Exception:                                        # noqa: BLE001
            pass

    def _save_sort(self) -> None:
        self._save_prefs()

    def _signature_of(self):
        """内容指纹（summary / curve / tables / 排序 / 提示）"""
        def freeze(value):
            if isinstance(value, dict):
                return tuple(sorted((str(k), freeze(v))
                                    for k, v in value.items()))
            if isinstance(value, (list, tuple)):
                return tuple(freeze(item) for item in value)
            return value

        return freeze((self.summary, self.curve, self.tables, self._sort,
                       self.notice, self.interval, self.curve_range,
                       self.accounts, tuple(sorted(self.account_curves))))

    # ------------------------------------------------------------- 交互
    def _on_sort(self, key=None, column=None) -> None:
        try:
            self.sort_by(str(key), int(column))
        except Exception as error:                               # noqa: BLE001
            print(f'[AccountPage] 排序失败: {error!r}')

    def sort_by(self, key: str, column: int) -> 'AccountPage':
        """点表头排序（同一列再点一次反向 ✓；只影响显示顺序，不改原数据）"""
        data = (self.tables or {}).get(key)
        if not isinstance(data, dict):
            return self
        current = self._sort.get(key)
        ascending = (not current[1]) if current and current[0] == column             else True
        self._sort[key] = (column, ascending)
        rows = list(data.get('rows') or [])
        rows.sort(key=lambda row: self._sort_key(row, column),
                  reverse=not ascending)
        self._save_sort()
        self.tables = dict(self.tables or {})
        self.tables[key] = {**data, 'rows': rows}
        return self._render()        # 排序是用户动作 → 强制重画 ✓

    @staticmethod
    def _sort_key(row, column: int):
        try:
            text = str(row[column])
        except (IndexError, TypeError):
            return (1, '')
        cleaned = text.replace(',', '').replace('%', '').replace('+', '')
        number = _num(cleaned) if cleaned else None
        if number is not None:
            return (0, number)
        return (1, text)

    def _on_csv(self, key=None) -> None:
        try:
            path = self.export_csv(str(key))
        except Exception as error:                               # noqa: BLE001
            self.notice = f'导出失败：{error}'
            self._render()
            return
        if path:
            self.notice = f'已导出：{path}'
            self._render()

    def _on_curve_png(self, *_args) -> None:
        """「导出曲线图（PNG）」：把**当前区间**的曲线存成图片 ✓"""
        try:
            path = self.export_curve_png()
        except Exception as error:                               # noqa: BLE001
            self.notice = f'导出曲线图失败：{error}'
            self._render()
            return
        if path:
            self.notice = f'曲线图已导出：{path}'
        else:
            self.notice = '曲线点不足（至少 2 个点才能导出）'
        self._render()

    def _on_screenshot(self, *_args) -> None:
        """「截图（PNG）」：整页截图；环境不支持 → 退回曲线图 ✓"""
        try:
            path = self.screenshot()
        except Exception as error:                               # noqa: BLE001
            self.notice = f'截图失败：{error}'
            self._render()
            return
        if path:
            self.notice = f'截图已导出：{path}'
        else:
            fallback = None
            try:
                fallback = self.export_curve_png()
            except Exception:                                    # noqa: BLE001
                fallback = None
            self.notice = (f'（当前环境不支持整页截图，已导出曲线图：{fallback}）'
                           if fallback else '（当前环境不支持截图）')
        self._render()

    def screenshot(self) -> Optional[str]:
        """整页截图（Qt ``widget.grab()``；拿不到窗口 → None ✓）"""
        widget = (getattr(self.chart, 'win', None)
                  or getattr(self.chart, 'window', None))
        grab = getattr(widget, 'grab', None)
        if not callable(grab):
            return None
        try:
            pixmap = grab()
        except Exception:                                        # noqa: BLE001
            return None
        saver = getattr(pixmap, 'save', None)
        if pixmap is None or not callable(saver):
            return None
        try:
            os.makedirs(EXPORTS_DIR, exist_ok=True)
            path = os.path.join(
                EXPORTS_DIR,
                f'账户_截图_{time.strftime("%Y%m%d_%H%M%S")}.png')
            return path if saver(path, 'PNG') else None
        except Exception:                                        # noqa: BLE001
            return None

    def export_curve_png(self) -> Optional[str]:
        """当前区间的权益曲线 → PNG（`matplotlib` + `FigureCanvasAgg`，
        不碰全局 backend ✓；无需 pyplot）"""
        points = self._filtered_curve()
        if len(points) < 2:
            return None
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        from matplotlib.ticker import StrMethodFormatter

        values = [float(value) for _, value in points]
        labels = [str(stamp) for stamp, _ in points]
        x = list(range(len(values)))
        figure = Figure(figsize=(9.0, 3.2), dpi=120)
        FigureCanvasAgg(figure)                     # 绑定 Agg 渲染器 ✓
        axes = figure.add_subplot(111)
        axes.plot(x, values, color='#2f9e44', linewidth=1.4)
        axes.axhline(values[0], color='#9aa0a6', linestyle='--',
                     linewidth=0.8)
        stats = self._curve_stats() or {}
        axes.set_title('minibt account equity  [%s]' % self.curve_range,
                       fontsize=10, loc='left')
        if stats:
            axes.text(
                0.995, 0.99,
                'origin {origin:,.2f}   latest {latest:,.2f}\n'
                'PnL {profit:+,.2f} ({rate:+.2f}%)   MDD {drawdown:.2f}%'
                .format(**stats),
                transform=axes.transAxes, ha='right', va='top',
                fontsize=8, color='#3c4043',
                bbox=dict(boxstyle='round,pad=0.3', fc='#f8f9fa',
                          ec='#dadce0', lw=0.6))
        axes.grid(True, linestyle=':', alpha=0.35)
        axes.tick_params(labelsize=7)
        step = max(1, len(points) // 6)
        ticks = list(range(0, len(points), step))
        axes.set_xticks(ticks)
        axes.set_xticklabels([labels[i][-8:] for i in ticks])
        axes.yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
        folder = EXPORTS_DIR
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(
            folder, f'账户_权益曲线_{time.strftime("%Y%m%d_%H%M%S")}.png')
        figure.savefig(path, bbox_inches='tight')
        return path

    def export_all(self) -> Optional[str]:
        """导出**全部三张表**：优先多 sheet ``.xlsx``，不行就 zip（3 个 csv）✓"""
        tables = self.tables or {}
        folder = EXPORTS_DIR
        os.makedirs(folder, exist_ok=True)
        stamp = time.strftime('%Y%m%d_%H%M%S')
        frames = []
        accounts = tables.get(self.ACCOUNT_KEY) or {}
        if accounts.get('rows'):
            frames.append(('多账户对比', list(accounts.get('columns') or []),
                           list(accounts.get('rows') or [])))
        for key, title in self.TABLE_ORDER:
            data = tables.get(key) or {}
            frames.append((title, list(data.get('columns') or []),
                           list(data.get('rows') or [])))
        # ① 多 sheet xlsx（需要 openpyxl / xlsxwriter）
        try:
            import pandas as _pd
            path = os.path.join(folder, f'账户_全部_{stamp}.xlsx')
            with _pd.ExcelWriter(path) as writer:
                wrote = False
                for title, columns, rows in frames:
                    if not columns and not rows:
                        continue
                    _pd.DataFrame(rows, columns=columns).to_excel(
                        writer, sheet_name=title[:31], index=False)
                    wrote = True
                if not wrote:
                    _pd.DataFrame({'提示': ['没有可导出的数据']}).to_excel(
                        writer, sheet_name='账户', index=False)
            return path
        except Exception as error:                               # noqa: BLE001
            print(f'[AccountPage] xlsx 导出不可用（改用 zip）：{error!r}')
        # ② 兜底：zip 里放 3 个 csv（utf-8-sig，Excel 直接开 ✓）
        path = os.path.join(folder, f'账户_全部_{stamp}.zip')
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as bundle:
            for title, columns, rows in frames:
                buffer = io.StringIO()
                writer = csv.writer(buffer)
                if columns:
                    writer.writerow(columns)
                writer.writerows(rows)
                bundle.writestr(f'账户_{title}.csv',
                                ('﻿' + buffer.getvalue()).encode('utf-8'))
        return path

    def _on_refresh(self, *_args) -> None:
        """「刷新」：手动拉一次（不受间隔限制 ✓）"""
        callback = self.on_refresh
        if callable(callback):
            callback()
            return
        self.notice = '已刷新（无实时数据源）'
        self._render()

    def _on_interval(self, value=None, *_args) -> None:
        try:
            self.interval = float(value)
        except (TypeError, ValueError):
            return
        self._save_prefs()
        self._render()

    def _on_range(self, value=None, *_args) -> None:
        self.curve_range = str(value or 'all')
        self._save_prefs()
        self._render()

    def _on_csv_all(self, *_args) -> None:
        try:
            path = self.export_all()
        except Exception as error:                               # noqa: BLE001
            self.notice = f'导出失败：{error}'
            self._render()
            return
        if path:
            self.notice = f'已导出全部：{path}'
            self._render()

    def export_csv(self, key: str) -> Optional[str]:
        """把某张表（**全部行**，不受显示前 N 条限制）导出到
        ``~/.minibt/exports/账户_<表名>_<时间>.csv`` ✓"""
        data = (self.tables or {}).get(key)
        if not isinstance(data, dict):
            return None
        titles = {table_key: title for table_key, title in self.TABLE_ORDER}
        titles[self.ACCOUNT_KEY] = '多账户对比'
        title = titles.get(key, key)
        rows = data.get('rows') or []
        folder = EXPORTS_DIR
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(
            folder, f'账户_{title}_{time.strftime("%Y%m%d_%H%M%S")}.csv')
        with open(path, 'w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(list(data.get('columns') or []))
            for row in rows:
                writer.writerow(list(row))
        return path

    # ------------------------------------------------------------- 渲染
    def _render(self) -> 'AccountPage':
        # 保住滚动位置：排序 / 刷新后不要跳回顶部 ✓
        try:
            self.panel.run_script(
                f'window.__plcAccountScroll = {self.panel.id}.scrollTop;')
        except Exception:                                        # noqa: BLE001
            pass
        self.panel.set_html(self._html())
        try:
            self.panel.run_script(
                'if (window.__plcAccountScroll) {'
                f' {self.panel.id}.scrollTop = window.__plcAccountScroll; }}')
        except Exception:                                        # noqa: BLE001
            pass
        return self

    def _html(self) -> str:
        notice = (f'<div class="notice">{_esc(self.notice)}</div>'
                  if self.notice else '')
        def callback(name, *args) -> str:
            payload = ';;;'.join(str(item) for item in args)
            return "window.callbackFunction('%s_~_%s')" % (name, payload)

        def button(name, value, text, active=False):
            cls = 'csv on' if active else 'csv'
            return (f'<button class="{cls}" '
                    f'onclick="{callback(name, value)}">{text}</button>')

        buttons = [button('minibt_account_csv_all', 'all',
                          '导出全部（Excel / ZIP）'),
                   button('minibt_account_curve', 'png',
                          '导出曲线图（PNG）'),
                   button('minibt_account_shot', 'png', '截图（PNG）'),
                   button('minibt_account_refresh', 'now', '刷新')]
        for value, text in ((1, '1s'), (2, '2s'), (5, '5s'), (0, '手动')):
            buttons.append(button('minibt_account_interval', value, text,
                                  float(self.interval or 0) == float(value)))
        notice += '<div class="toolbar">' + ''.join(buttons) + '</div>'
        range_buttons = ['<span class="k">曲线区间</span>']
        for value, text in (('all', '全部'), ('60', '1小时'),
                            ('30', '30分'), ('session', '本次')):
            range_buttons.append(button('minibt_account_range', value, text,
                                        str(self.curve_range) == value))
        notice += ('<div class="toolbar">' + ''.join(range_buttons)
                   + '</div>')
        return (f'<style>{self.CSS}</style><div class="plc-account">'
                + notice + self._cards_html() + self._accounts_html()
                + self._multi_curve_html() + self._curve_html()
                + self._tables_html() + '</div>')

    @staticmethod
    def _money(value: Any) -> str:
        number = _num(value)
        return '--' if number is None else f'{number:,.2f}'

    def _build_accounts_table(self) -> None:
        """``self.accounts`` → ``self.tables['accounts']``（原始数值，便于导出 ✓）"""
        rows = []
        for row in self.accounts or []:
            if not row:
                continue
            rows.append([
                str(row.get('account') or '--'),
                _num(row.get('balance')), _num(row.get('available')),
                _num(row.get('float_profit')), _num(row.get('extra')),
                _num(row.get('ratio')), _num(row.get('positions')),
                _num(row.get('orders')), _num(row.get('range_profit')),
            ])
        if not rows:
            self.tables.pop(self.ACCOUNT_KEY, None)
            return
        # 记住的排序（点表头后重启也记得 ✓）
        state = self._sort.get(self.ACCOUNT_KEY)
        if state:
            rows.sort(key=lambda item: self._sort_key(item, state[0]),
                      reverse=not state[1])
        percent = bool((self.accounts or [{}])[0].get('ratio_percent'))
        formats = list(self.ACCOUNT_FORMATS)
        formats[5] = 'pct' if percent else 'money'
        total = ['合计',
                 sum(_num(row[1]) or 0.0 for row in rows),
                 '', '', '', '', '', '',
                 sum(_num(row[8]) or 0.0 for row in rows)]
        self.tables = dict(self.tables or {})
        self.tables[self.ACCOUNT_KEY] = {
            'columns': self.ACCOUNT_COLUMNS, 'rows': rows,
            'total': len(rows), 'limit': len(rows),
            'formats': tuple(formats), 'total_row': total,
        }

    @staticmethod
    def _format_cell(value: Any, kind: str) -> str:
        """``money`` / ``signed`` / ``pct`` / ``int`` / ``text`` → 显示文本 ✓"""
        if kind == 'text':
            text = '' if value is None else str(value)
            return _esc(text or '--')
        number = _num(value)
        if number is None:
            return '--'
        if kind == 'money':
            return f'{number:,.2f}'
        if kind == 'signed':
            return f'{number:+,.2f}' if number else '0.00'
        if kind == 'pct':
            return f'{number:.2f}%'
        if kind == 'int':
            return f'{int(number)}'
        return _esc(str(value))

    def _accounts_html(self) -> str:
        """**多账户对比表**（只有 ≥2 个账户才显示 ✓）

        列：账户 / 权益 / 可用 / 浮盈 / 保证金 / 风险度 / 持仓 / 委托 / 区间收益
        （「区间收益」来自**落盘库**的历史首末差，没落盘就留空）
        表头可排序、可导出 CSV（数据在 ``self.tables['accounts']`` ✓）
        """
        data = (self.tables or {}).get(self.ACCOUNT_KEY) or {}
        rows = list(data.get('rows') or [])
        if len(rows) < 2:
            return ''
        formats = data.get('formats') or self.ACCOUNT_FORMATS
        columns = data.get('columns') or self.ACCOUNT_COLUMNS
        csv_cb = ("window.callbackFunction('minibt_account_csv_~_%s')"
                  % self.ACCOUNT_KEY)
        out = [f'<h2>多账户对比 <span class="k">{len(rows)} 个账户</span>'
               f'<button class="csv" onclick="{csv_cb}">导出 CSV</button></h2>'
               '<table><thead><tr>']
        state = self._sort.get(self.ACCOUNT_KEY)
        for index, column in enumerate(columns):
            mark = ''
            if state and state[0] == index:
                mark = ' ▲' if state[1] else ' ▼'
            sort_cb = ("window.callbackFunction("
                       "'minibt_account_sort_~_%s;;;%d')"
                       % (self.ACCOUNT_KEY, index))
            out.append(f'<th class="sortable" onclick="{sort_cb}">'
                       f'{_esc(column)}{mark}</th>')
        out.append('</tr></thead><tbody>')
        for row in rows:
            cells = []
            for index, value in enumerate(row):
                kind = formats[index] if index < len(formats) else 'text'
                text = self._format_cell(value, kind)
                if kind == 'signed':
                    cells.append(f'<td class="{_colour_class(value)}">'
                                 f'{text}</td>')
                else:
                    cells.append(f'<td>{text}</td>')
            out.append('<tr>' + ''.join(cells) + '</tr>')
        total = data.get('total_row')
        if total and any(value not in (None, '') for value in total[1:]):
            cells = []
            for index, value in enumerate(total):
                kind = formats[index] if index < len(formats) else 'text'
                text = self._format_cell(value, kind) if value != '' else ''
                cells.append(f'<td>{text}</td>')
            out.append('<tr class="total">' + ''.join(cells) + '</tr>')
        out.append('</tbody></table>')
        return ''.join(out)

    def _multi_curve_html(self) -> str:
        """**多账户收益对比**（≥2 条曲线才画；都按「相对首点」折算成 % ✓）"""
        series = []
        for name, points in (self.account_curves or {}).items():
            clean = [(str(ts), float(value)) for ts, value in (points or [])
                     if _num(value) is not None]
            if len(clean) < 2 or not float(clean[0][1]):
                continue
            base = float(clean[0][1])
            series.append((name, [(ts, (float(value) / base - 1.0) * 100.0)
                                  for ts, value in clean]))
        if len(series) < 2:
            return ''
        palette = ('#2f9e44', '#1e88e5', '#e65100', '#8e24aa', '#00838f',
                   '#c62828', '#6d4c41', '#546e7a')
        width, height, pad = 900, 170, 12
        lows = [value for _, points in series for _, value in points]
        high, low = max(lows), min(lows)
        span = (high - low) or 1.0
        usable = height - pad * 2

        def y_of(value: float) -> float:
            return height - pad - (value - low) / span * usable

        out = [f'<h2>多账户收益对比 <span class="k">{len(series)} 条曲线 · '
               f'相对首点 %</span></h2>'
               f'<svg class="curve" viewBox="0 0 {width} {height}" '
               f'preserveAspectRatio="none">']
        zero = y_of(0.0)
        out.append(f'<line class="base" x1="0" y1="{zero:.1f}" '
                   f'x2="{width}" y2="{zero:.1f}"/>')
        for index, (name, points) in enumerate(series):
            colour = palette[index % len(palette)]
            step = width / max(len(points) - 1, 1)
            coords = ' '.join(f'{i * step:.1f},{y_of(value):.1f}'
                              for i, (_ts, value) in enumerate(points))
            out.append(f'<polyline class="line" style="stroke:{colour}" '
                       f'points="{coords}"/>')
        out.append('</svg><div class="range">')
        for index, (name, points) in enumerate(series):
            colour = palette[index % len(palette)]
            last = points[-1][1]
            cls = 'up' if last > 0 else ('down' if last < 0 else '')
            out.append(f'<span class="legend-item">'
                       f'<i style="background:{colour}"></i>'
                       f'{_esc(name)} <b class="{cls}">{last:+.2f}%</b></span>')
        out.append('</div>')
        return ''.join(out)

    @staticmethod
    def _ratio_text(row: Dict[str, Any]) -> str:
        number = _num(row.get('ratio'))
        if number is None:
            return '--'
        if row.get('ratio_percent') is False:
            return f'{number:,.2f}'
        return f'{number:.2f}%'

    def _cards_html(self) -> str:
        summary = self.summary or {}
        kind = _esc(summary.get('kind') or '账户')
        name = _esc(summary.get('account') or '')
        label = f'{kind} · {name}' if name else kind
        out = [f'<h2>账户总览 <span class="k">{label}</span></h2>'
               '<div class="cards">']
        labels = {'extra': summary.get('extra_label') or '保证金',
                  'ratio': summary.get('ratio_label') or '风险度',
                  'close_profit': summary.get('close_label') or '平仓盈亏'}
        for key, title, colored in self.FIELDS:
            value = summary.get(key)
            if key == 'extra':
                text = self._money(value)
            elif key == 'ratio':
                number = _num(value)
                if number is None:
                    text = '--'
                elif summary.get('ratio_percent') is False:
                    text = f'{number:,.2f}'
                else:
                    text = f'{number:.2f}%'
            elif key in ('positions', 'orders'):
                text = str(int(_num(value) or 0))
            else:
                text = self._money(value)
            cls = ''
            if colored:
                number = _num(value)
                if number:
                    cls = ' up' if number > 0 else ' down'
            out.append(
                f'<div class="card"><div class="k">{_esc(labels.get(key, title))}</div>'
                f'<div class="v{cls}">{_esc(text)}</div></div>')
        out.append('<div class="card"><div class="k">持仓 / 未完成委托</div>'
                   f'<div class="v">{int(_num(summary.get("positions")) or 0)}'
                   f' / {int(_num(summary.get("orders")) or 0)}</div></div>')
        out.append('</div>')
        return ''.join(out)

    #: 明细表顺序：``(tables 键, 标题)``
    TABLE_ORDER = (('positions', '持仓'), ('orders', '委托'),
                   ('trades', '成交'))

    def _tables_html(self) -> str:
        tables = self.tables or {}
        out: List[str] = []
        for key, title in self.TABLE_ORDER:
            data = tables.get(key) or {}
            columns = data.get('columns') or ()
            rows = data.get('rows') or []
            total = int(_num(data.get('total')) or len(rows))
            limit = int(_num(data.get('limit')) or len(rows))
            note = f'{total} 条'
            if total > limit and limit:
                note += f'（显示前 {limit}）'
            # 导出按钮 / 可排序表头：都走 window.callbackFunction ✓
            csv_cb = ("window.callbackFunction('minibt_account_csv_~_%s')"
                      % key)
            out.append(
                f'<h2>{title} <span class="k">{note}</span>'
                f'<button class="csv" onclick="{csv_cb}">导出 CSV</button></h2>')
            if not rows:
                out.append('<div class="empty">（暂无）</div>')
                continue
            shown = rows[:limit] if limit else rows
            out.append('<table><thead><tr>')
            state = self._sort.get(key)
            for index, column in enumerate(columns):
                mark = ''
                if state and state[0] == index:
                    mark = ' ▲' if state[1] else ' ▼'
                sort_cb = ("window.callbackFunction("
                           "'minibt_account_sort_~_%s;;;%d')" % (key, index))
                out.append(f'<th class="sortable" onclick="{sort_cb}">'
                           f'{_esc(column)}{mark}</th>')
            out.append('</tr></thead><tbody>')
            for row in shown:
                out.append('<tr>'
                           + ''.join(f'<td>{_esc(cell)}</td>' for cell in row)
                           + '</tr>')
            out.append('</tbody></table>')
        return ''.join(out)

    def _filtered_curve(self):
        """按「曲线区间」过滤（全部 / 1小时 / 30分钟 / 本次会话）✓"""
        points = [(str(ts), float(value)) for ts, value in (self.curve or [])
                  if _num(value) is not None]
        mode = str(self.curve_range or 'all')
        if mode == 'all' or not points:
            return points
        if mode == 'session':
            kept = [item for item in points
                    if (_ts_of(item[0]) or 0) >= self._session_from]
            return kept or points[-1:]
        try:
            minutes = float(mode)
        except (TypeError, ValueError):
            return points
        cutoff = time.time() - minutes * 60.0
        kept = [item for item in points if (_ts_of(item[0]) or 0) >= cutoff]
        return kept or points[-1:]

    def _curve_stats(self) -> Optional[Dict[str, float]]:
        """曲线统计：期初 / 最新 / 收益 / 收益率% / 最大回撤%（没数据 → None）"""
        points = self._filtered_curve()
        if not points:
            return None
        values = [float(value) for _, value in points]
        origin, latest = values[0], values[-1]
        profit = latest - origin
        peak, worst = values[0], 0.0
        for value in values:
            peak = max(peak, value)
            if peak:
                worst = min(worst, (value - peak) / peak * 100.0)
        return {'origin': origin, 'latest': latest, 'profit': profit,
                'rate': (profit / origin * 100.0) if origin else 0.0,
                'drawdown': worst, 'count': float(len(values)),
                'low': min(values), 'high': max(values)}

    def _curve_html(self) -> str:
        points = self._filtered_curve()
        if len(points) < 2:
            return ('<h2>权益曲线</h2><div class="empty">'
                    '（暂无曲线数据：停留本页几秒后开始累积；'
                    '股票模拟盘会读取已持久化的历史 ✓）</div>')
        stats = self._curve_stats() or {}
        # 点数太多 → 等间隔抽稀到 ~200 个（SVG 不至于长到卡 ✓）
        if len(points) > 200:
            step = len(points) / 200.0
            points = [points[min(int(i * step), len(points) - 1)]
                      for i in range(200)] + [points[-1]]
        values = [value for _, value in points]
        # 期初资金也进缩放 → **基准线永远在画面内** ✓
        origin = float(stats.get('origin', values[0]))
        low = min(min(values), origin)
        high = max(max(values), origin)
        span = (high - low) or max(abs(high), 1.0)
        width, height = 900, 190
        pad = 12
        usable = height - pad * 2

        def y_of(value: float) -> float:
            return height - pad - (value - low) / span * usable

        step_x = width / max(len(values) - 1, 1)
        coords = ' '.join(f'{i * step_x:.1f},{y_of(value):.1f}'
                          for i, value in enumerate(values))
        base = y_of(origin)
        profit = float(stats.get('profit', 0.0))
        cls = 'up' if profit > 0 else ('down' if profit < 0 else '')
        return (
            f'<h2>权益曲线 <span class="k">{_esc(points[0][0])} ~ '
            f'{_esc(points[-1][0])} · {len(points)} 点</span></h2>'
            f'<svg class="curve" viewBox="0 0 {width} {height}" '
            f'preserveAspectRatio="none">'
            f'<line class="base" x1="0" y1="{base:.1f}" '
            f'x2="{width}" y2="{base:.1f}"/>'
            f'<polyline class="line" points="{coords}"/></svg>'
            f'<div class="range">期初 <b>{origin:,.2f}</b> · 最新 '
            f'<b>{values[-1]:,.2f}</b> · '
            f'<span class="{cls}">{profit:+,.2f}'
            f'（{float(stats.get("rate", 0.0)):+.2f}%）</span> · '
            f'最大回撤 {float(stats.get("drawdown", 0.0)):.2f}% · '
            f'最低 {low:,.2f} · 最高 {high:,.2f}</div>')

    # ------------------------------------------------------------- 显示
    def show(self) -> 'AccountPage':
        self.panel.show()
        return self

    def hide(self) -> 'AccountPage':
        self.panel.hide()
        return self

    def remove(self) -> None:
        self.panel.delete()
