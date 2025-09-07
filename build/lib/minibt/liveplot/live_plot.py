
import os
import warnings
from iteration_utilities import flatten
from random import randint
from ast import literal_eval
from typing import List, Dict, Iterable, Callable
from bokeh.application.handlers.function import FunctionHandler
from bokeh.application import Application
from bokeh.server.server import Server
from tornado.ioloop import IOLoop
from bokeh.palettes import Category10
from bokeh.events import PointEvent, Tap
import argparse
import pickle
import bokeh.colors.named as bcn
from itertools import cycle
from functools import partial
from bokeh.models import Tabs
from bokeh.transform import factor_cmap
import numpy as np
import pandas as pd
from bokeh.models import (
    CrosshairTool,
    CustomJS,
    ColumnDataSource,
    NumeralTickFormatter,
    Label,
    Span,
    HoverTool,
    Range1d,
    # DatetimeTickFormatter,
    WheelZoomTool,
    PreText,
    Button
    # LinearColorMapper,
)
from copy import deepcopy
from bokeh.layouts import gridplot, column, row
from bokeh.plotting import figure as _figure
from bokeh.models.glyphs import VBar
# 现在可以用绝对导入替代相对导入
# from bokeh.colors.named import (
#     lime as BULL_COLOR,
#     tomato as BEAR_COLOR
# )
# from bokeh.colors import RGB
setattr(_figure, '_main_ohlc', False)
try:  # 版本API有变
    from bokeh.models import TabPanel as Panel
except:
    from bokeh.models import Panel
# from bokeh.io.state import curstate
# from colorsys import hls_to_rgb, rgb_to_hls
# from typing import Callable, List, Union
warnings.filterwarnings('ignore')
FILED = ['open', 'high', 'low', 'close']
_FILED = ['datetime', 'open', 'high', 'low', 'close', 'volume']
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DARK_TABS_CSS = """
    :host(.dark-tabs) {
        background-color: #1a1a1a;
        border-color: #333;
    }
    :host(.dark-tabs) .bk-tabs-header {
        background-color: #333;
    }
    :host(.dark-tabs) .bk-tab {
        color: #ccc;
        border-color: #666;
    }
    :host(.dark-tabs) .bk-active {
        background-color: #1a1a1a;
        color: #fff;
    }
    """
panel_CUSTOM_CSS = """
:host {
    height: 100%;
}
.bk-Column {
    display: flex;
    flex-direction: column;
    height: 100%;  /* 从100vh改为100% */
}
.bk-Column > * {
    flex: 1 1 auto;
}
.bk-Column > .candle-chart {
    flex: 4 1 auto;  /* 主K线图占比 */
}
.bk-Column > .volume-chart {
    flex: 0.8 1 auto;  /* 成交量图占比 */
}
.bk-Column > .value-chart {
    flex: 1.5 1 auto;  /* 资金曲线占比 */
}
"""
parser = argparse.ArgumentParser()
parser.add_argument('--black_sytle', '-bs', type=literal_eval, default=False)
parser.add_argument('--plot_width', '-pw', type=int, default=0)
parser.add_argument('--period_milliseconds', '-pm', type=int, default=0)
parser.add_argument("--click_policy", '-cp', type=str, default='hide')
ispoint = True
args = parser.parse_args()


def ffillnan(arr: np.ndarray) -> np.ndarray:
    if len(arr.shape) > 1:
        arr = pd.DataFrame(arr)
    else:
        arr = pd.Series(arr)
    arr.fillna(method='ffill', inplace=True)
    arr.fillna(method='bfill', inplace=True)
    return arr.values


def storeData(data, filename='examplePickle'):
    try:
        with open(filename, 'wb') as f:
            pickle.dump(data, f)
    except:
        ...


def loadData(filename='examplePickle'):
    try:
        with open(filename, 'rb') as f:
            db = pickle.load(f)
        return db
    except EOFError:
        ...


def on_mouse_move(event: PointEvent):
    global ispoint
    ispoint = False if ispoint else True


def set_tooltips(fig: _figure, tooltips=(), vline=True, renderers=(), if_datetime: bool = True, if_date=True, mouse: bool = False):
    tooltips = list(tooltips)
    renderers = list(renderers)

    if if_datetime:
        formatters = {'@datetime': 'datetime'}
        if if_date:
            tooltips += [("Datetime", "@datetime{%Y-%m-%d}")]
        else:
            tooltips += [("Datetime", "@datetime{%Y-%m-%d %H:%M:%S}")]
    else:
        formatters = {}
    # tooltips = [("Date", "@datetime")] + tooltips
    hover_tool = HoverTool(
        point_policy='follow_mouse',
        renderers=renderers, formatters=formatters,
        tooltips=tooltips, mode='vline' if vline else 'mouse')
    fig.add_tools(hover_tool)
    if mouse:
        fig.on_event(Tap, on_mouse_move)


def new_bokeh_figure(plot_width, height=300) -> Callable:
    return partial(
        _figure,
        x_axis_type='linear',
        width_policy='max',
        width=plot_width,
        height=height,
        tools="xpan,xwheel_zoom,box_zoom,undo,redo,reset,save",  # ,crosshair
        active_drag='xpan',
        active_scroll='xwheel_zoom')


def new_bokeh_figure_main(plot_width, height=150) -> Callable:
    return partial(
        _figure,
        x_axis_type='linear',
        width_policy='max',
        width=plot_width,
        height=height,
        tools="xpan,xwheel_zoom",  # ,crosshair
        active_drag='xpan',
        active_scroll='xwheel_zoom')


def new_indicator_figure(new_bokeh_figure: partial, fig_ohlc: _figure, plot_width, height=80, **kwargs) -> _figure:
    # kwargs.setdefault('height', height)
    height = int(height) if height and height > 10 else 80
    fig = new_bokeh_figure(plot_width, height)(x_range=fig_ohlc.x_range,
                                               active_scroll='xwheel_zoom',
                                               active_drag='xpan',
                                               **kwargs)
    # fig = new_bokeh_figure(x_range=fig_ohlc.x_range,
    #                        active_scroll='xwheel_zoom',
    #                        active_drag='xpan',
    #                        **kwargs)
    fig.xaxis.visible = False
    fig.yaxis.minor_tick_line_color = None
    return fig


def search_index(ls: list[list], name) -> tuple[int]:
    for i, ls1 in enumerate(ls):
        for j, ls2 in enumerate(ls1):
            if ls2 == name:
                return i, j
    assert False, "找不到索引"


def colorgen():
    yield from cycle(Category10[10])


def callback_strategy(attr, old, new):
    global strategy_id
    strategy_id = new


def callback_strategy(attr, old, new):
    global data_index
    data_index = new


strategy_id: int = 0
data_index: int = 0
click_policy = args.click_policy
init_datas_dir = f"{BASE_DIR}/init_datas"
trade_datas_dir = f"{BASE_DIR}/trade_datas"
update_datas_dir = f"{BASE_DIR}/update_datas"
account_info_dir = f"{BASE_DIR}/account_info"
# storeData(None,trade_datas_dir)
storeData(None, update_datas_dir)
init_datas = loadData(init_datas_dir)
account_info = loadData(account_info_dir)
black_sytle = args.black_sytle
plot_width = None  # args.plot_width
source: List[List[List[ColumnDataSource]]] = None
trade_source: List[List[List[ColumnDataSource]]] = None

# index=100


def make_document(doc):
    black_color, white_color = black_sytle and (
        "white", "black") or ("black", "white")
    # K线颜色
    # COLORS = [BEAR_COLOR, BULL_COLOR]
    COLORS = [bcn.tomato, bcn.lime]
    inc_cmap = factor_cmap('inc', COLORS, ['0', '1'])
    lines_setting = dict(line_dash='solid', line_width=1.3)
    BAR_WIDTH = .8  # K宽度
    NBSP = '\N{NBSP}' * 4
    pad = 2000
    trade_signal = False

    new_colors = {'bear': bcn.tomato, 'bull': bcn.lime}
    # new_bokeh_figure = partial(
    #     _figure,
    #     x_axis_type='linear',
    #     width_policy='max',
    #     width=plot_width,
    #     height=300,
    #     tools="xpan,xwheel_zoom,box_zoom,undo,redo,reset,save",  # ,crosshair
    #     active_drag='xpan',
    #     active_scroll='xwheel_zoom')
    # new_bokeh_figure_main = partial(
    #     _figure,
    #     x_axis_type='linear',
    #     width_policy='max',
    #     width=plot_width,
    #     height=150,
    #     tools="xpan,xwheel_zoom",  # ,crosshair
    #     active_drag='xpan',
    #     active_scroll='xwheel_zoom')
    with open(f'{BASE_DIR}/autoscale_cb.js', encoding='utf-8') as _f:
        _AUTOSCALE_JS_CALLBACK = _f.read()
    # with open(f'{BASE_DIR}/autoscale_x.js', encoding='utf-8') as _f:
    #     _AUTOSCALE_JS_CALLBACK_X = _f.read()
    ts: List[Tabs] = []
    snum = len(init_datas)
    long_source: list[list] = [[] for _ in range(snum)]
    short_source: list[list] = [[] for _ in range(snum)]
    long_flat_source: list[list] = [[] for _ in range(snum)]
    short_flat_source: list[list] = [[] for _ in range(snum)]
    long_segment_source: list[list] = [[] for _ in range(snum)]
    short_segment_source: list[list] = [[] for _ in range(snum)]
    ohlc_extreme_values: list[list] = [[] for _ in range(snum)]  # 范围数据
    symbols = [[] for _ in range(snum)]
    cycles = [[] for _ in range(snum)]
    source: List[List[ColumnDataSource]] = [[]
                                            for _ in range(snum)]
    trade_source: List[List[Dict[str, ColumnDataSource]]] = [[]
                                                             for _ in range(snum)]
    figs_ohlc: List[List[List[_figure]]] = [[] for _ in range(snum)]
    ts: list[Tabs] = []
    signal_ind_data_source: list[list[list]] = [[] for i in range(snum)]
    all_plots: List[List[List[_figure]]] = [[] for _ in range(snum)]
    # min_cycle: List[List[int]] = [[] for _ in range(snum)]
    spans: List[List[List[Span]]] = [[] for _ in range(snum)]
    symbol_multi_cycle: List[List[List[int]]] = [[]
                                                 for _ in range(snum)]
    fig_ohlc_list: list[dict] = [{} for _ in range(snum)]
    ohlc_span: list[list[list[Span]]] = [[] for _ in range(snum)]
    snames: list[str] = []
    lines_setting = dict(line_dash='solid', line_width=1.3)
    for i, (sname, datas, inds, btind_info) in enumerate(init_datas):
        snames.append(sname)
        panel = []
        for j, df in enumerate(datas):
            df: pd.DataFrame
            df.reset_index(drop=True, inplace=True)
            signal_ind_data_source[i].append([])
            symbols[i].append(df.symbol.iloc[0])
            cycles[i].append(df.duration.iloc[0])
            df = df[_FILED]
            df['volume5'] = df.volume.rolling(5).mean()
            df['volume10'] = df.volume.rolling(10).mean()
            df["inc"] = (df.close >=
                         df.open).values.astype(np.uint8).astype(str)
            df["Low"] = df[['low', 'high']].min(1)
            df["High"] = df[['low', 'high']].max(1)
            source[i].append(ColumnDataSource(df))
            # # 涨跌颜色数据
            # source[i][j].add((df.close >=
            #                   df.open).values.astype(np.uint8).astype(str), 'inc')
            # ohlc_extreme_values[i].append(
            #     df[['high', 'low']].copy(deep=False))
            # data = ColumnDataSource(dict(
            #     index=list(df.index),
            #     datetime=df.datetime.to_list(),
            #     open=df.open.to_list(),
            #     high=df.high.to_list(),
            #     low=df.low.to_list(),
            #     close=df.close.to_list(),
            #     volume=df.volume.to_list(),
            #     inc=(df.close >= df.open).values.astype(
            #         np.uint8).astype(str).tolist(),
            #     Low=df[['low', 'high']].min(1).tolist(),
            #     High=df[['low', 'high']].max(1).tolist(),
            # ))
            # source[i].append(data)
            index = df.index
            # K线图
            if btind_info[i]["ismain"] and j != 0:
                fig_ohlc: _figure = new_bokeh_figure_main(plot_width, btind_info[j].get('height', 150))(
                    x_range=Range1d(index[0], index[-1],
                                    min_interval=10,
                                    bounds=(index[0] - pad,
                                            index[-1] + pad)) if index.size > 1 else None)
                # fig_ohlc = new_bokeh_figure_main(
                #     x_range=Range1d(index[0], index[-1],
                #                     min_interval=10,
                #                     bounds=(index[0] - pad,
                #                             index[-1] + pad)) if index.size > 1 else None)
                fig_ohlc._main_ohlc = True
            else:
                fig_ohlc: _figure = new_bokeh_figure(plot_width, btind_info[j].get('height', 300))(
                    x_range=Range1d(index[0], index[-1],
                                    min_interval=10,
                                    bounds=(index[0] - pad,
                                            index[-1] + pad)) if index.size > 1 else None)
                # fig_ohlc = new_bokeh_figure(
                #     x_range=Range1d(index[0], index[-1],
                #                     min_interval=10,
                #                     bounds=(index[0] - 20,
                #                             index[-1] + pad)) if index.size > 1 else None)
            fig_ohlc.css_classes = ["candle-chart"]
            _colors = btind_info[j].get('candlestyle', new_colors)
            if _colors and j == 0:
                # COLORS = [getattr(bcn, _colors.get('bear', 'tomato')), getattr(
                #     bcn, _colors.get('bull', 'lime'))]
                # inc_cmap = factor_cmap('inc', COLORS, ['0', '1'])
                _COLORS = list(_colors.values())
                inc_cmap = factor_cmap('inc', _COLORS, ['0', '1'])
            # 上下影线
            fig_ohlc.segment('index', 'high', 'index',
                             'low', source=source[i][j], color=black_color)
            # 实体线
            ohlc_bars = fig_ohlc.vbar('index', BAR_WIDTH, 'open', 'close', source=source[i][j],
                                      line_color=black_color, fill_color=inc_cmap)
            # 提示格式
            ohlc_tooltips = [
                ('x, y', NBSP.join(('$index',
                                    '$y{0,0.0[0000]}'))),
                ('OHLC', NBSP.join(('@open{0,0.0[0000]}',
                                    '@high{0,0.0[0000]}',
                                    '@low{0,0.0[0000]}',
                                    '@close{0,0.0[0000]}'))),
                ('Volume', '@volume{0,0}')]

            #
            spanstyle = btind_info[j].get("spanstyle", [])
            for ohlc_spanstyle in spanstyle:
                fig_ohlc.add_layout(Span(**ohlc_spanstyle))

            pos = 1

            if pos:
                span_color = 'red' if pos > 0. else 'green'
                for spanstyle_ in spanstyle:
                    bt_span = Span(**spanstyle_)
                    ohlc_span[i].append(bt_span)
                    fig_ohlc.add_layout(bt_span)
            else:
                bt_span = Span(location=0., dimension='width',
                               line_color='#666666', line_dash='dashed',
                               line_width=.8)
                bt_span.visible = False
                ohlc_span[i].append(bt_span)
                fig_ohlc.add_layout(bt_span)

            # 指标数据
            indicators_data = inds[j]
            indicator_candles_index = []
            indicator_figs = []
            indicator_h: list[str] = []
            indicator_l: list[str] = []
            if indicators_data:
                ohlc_colors = colorgen()
                ic = 0
                for isplot, name, names, __lines, ind_name, is_overlay, category, indicator, doubles, plotinfo, span, _signal in indicators_data:
                    lineinfo = plotinfo.get('linestyle', {})
                    print(lineinfo)
                    datainfo = plotinfo.get('source', "")
                    signal_info: dict = plotinfo.get('signalstyle', {})
                    if doubles:
                        _doubles_fig = []
                        for ids in range(2):
                            if any(isplot[ids]):
                                is_candles = category[ids] == 'candles'
                                tooltips = []
                                colors = cycle([next(ohlc_colors)]
                                               if is_overlay[ids] else colorgen())
                                legend_label = name[ids]  # 初始化命名的名称
                                if is_overlay[ids] and not is_candles:  # 主图叠加
                                    fig = fig_ohlc
                                else:
                                    fig = new_indicator_figure(
                                        new_bokeh_figure, fig_ohlc, plot_width, plotinfo.get('height', 150))
                                    indicator_figs.append(fig)
                                    _indicator = ffillnan(indicator[ids])
                                    _mulit_ind = len(
                                        _indicator.shape) > 1
                                    source[i][j].add(
                                        np.max(_indicator, axis=1).tolist() if _mulit_ind else _indicator.tolist(), f"{ind_name[ids]}_h")
                                    source[i][j].add(
                                        np.min(_indicator, axis=1).tolist() if _mulit_ind else _indicator.tolist(), f"{ind_name[ids]}_l")
                                    indicator_h.append(
                                        f"{ind_name[ids]}_h")
                                    indicator_l.append(
                                        f"{ind_name[ids]}_l")
                                    ic += 1
                                _doubles_fig.append(fig)

                                if not is_candles:
                                    if_vbar = False
                                    for jx in range(indicator[ids].shape[1]):
                                        if isplot[ids][jx]:
                                            _lines_name = __lines[ids][jx]
                                            ind = indicator[ids][:, jx]
                                            color = next(colors)
                                            source_name = names[ids][jx]
                                            if ind.dtype == bool:
                                                ind = ind.astype(int)
                                            source[i][j].add(
                                                ind.tolist(), source_name)
                                            tooltips.append(
                                                f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                                            _lineinfo = deepcopy(
                                                lines_setting)
                                            if _lines_name in lineinfo:
                                                _lineinfo = {
                                                    **_lineinfo, **(lineinfo[_lines_name])}
                                            if _lineinfo.get("line_color", None) is None:
                                                _lineinfo.update(
                                                    dict(line_color=color))
                                            if is_overlay[ids]:
                                                fig.line(
                                                    'index', source_name, source=source[i][j],
                                                    legend_label=source_name, **_lineinfo)
                                                # fig.line(
                                                #     'index', source_name, source=source[i][j],
                                                #     legend_label=source_name, line_color=color,
                                                #     line_width=1.3)

                                            else:
                                                # if category and isinstance(category, dict) and _lines_name in category:
                                                if lineinfo and _lines_name in lineinfo and lineinfo[_lines_name].get('line_dash', None) == 'vbar':
                                                    if_vbar = True
                                                    if "zeros" not in source[i][j].column_names:
                                                        source[i][j].add(
                                                            [0.,]*len(ind), "zeros")
                                                    _line_inc = np.where(ind > 0., 1, 0).astype(
                                                        np.uint8).astype(str).tolist()
                                                    source[i][j].add(
                                                        _line_inc, f"{_lines_name}_inc")
                                                    _line_inc_cmap = lineinfo[_lines_name]["line_color"]
                                                    if _line_inc_cmap is None:
                                                        _line_inc_cmap = factor_cmap(
                                                            f"{_lines_name}_inc", COLORS, ['0', '1'])
                                                    # if "line_color" in lineinfo[_lines_name]:
                                                    #     _line_inc_cmap = lineinfo[_lines_name]["line_color"]
                                                    # else:
                                                    #     _line_inc_cmap = factor_cmap(
                                                    #         f"{_lines_name}_inc", COLORS, ['0', '1'])
                                                    r = fig.vbar('index', BAR_WIDTH, 'zeros', source_name, source=source[i][j],
                                                                 line_color='black', fill_color=_line_inc_cmap)
                                                else:
                                                    r = fig.line(
                                                        'index', source_name, source=source[i][j],
                                                        legend_label=source_name, **_lineinfo)
                                                    # r = fig.line(
                                                    #     'index', source_name, source=source[i][j],
                                                    #     legend_label=source_name, line_color=color,
                                                    #     line_width=1.3)
                                                    # Add dashed centerline just because
                                                # if np.isnan(span):
                                                #     mean = ind.mean()
                                                #     if not np.isnan(mean) and (abs(mean) < .1 or
                                                #                                round(abs(mean), 1) == .5 or
                                                #                                round(abs(mean), -1) in (50, 100, 200)):
                                                #         fig.add_layout(Span(location=float(mean), dimension='width',
                                                #                             line_color='#666666', line_dash='dashed',
                                                #                             line_width=.8))
                                                # else:
                                                #     if isinstance(span, dict):
                                                #         if _lines_name in span:
                                                #             fig.add_layout(Span(location=float(span.get(_lines_name)), dimension='width',
                                                #                                 line_color='#666666', line_dash='dashed',
                                                #                                 line_width=.8))
                                    # else:
                                    #     if (not np.isnan(span)) and isinstance(span, float):
                                    #         fig.add_layout(Span(location=span, dimension='width',
                                    #                             line_color='#666666', line_dash='dashed',
                                    #                             line_width=.8))
                                    else:
                                        if if_vbar:
                                            renderers = fig.renderers.copy()
                                            fig.renderers = list(
                                                sorted(renderers, key=lambda x: not isinstance(x.glyph, VBar)))

                                        if span:
                                            for ind_span in span:
                                                if np.isnan(ind_span["location"]) and not all(is_overlay):
                                                    ind = ind.astype(
                                                        np.float32)
                                                    mean = ind[~np.isnan(
                                                        ind)].mean()
                                                    if not np.isnan(mean) and (abs(mean) < .1 or
                                                                               round(abs(mean), 1) == .5 or
                                                                               round(abs(mean), -1) in (50, 100, 200)):
                                                        fig.add_layout(Span(location=float(mean), dimension='width',
                                                                            line_color='#666666', line_dash='dashed',
                                                                            line_width=.8))
                                                else:
                                                    fig.add_layout(
                                                        Span(**ind_span))
                                        else:
                                            ind = ind.astype(np.float32)
                                            mean = ind[~np.isnan(
                                                ind)].mean()
                                            if not np.isnan(mean) and (abs(mean) < .1 or
                                                                       round(abs(mean), 1) == .5 or
                                                                       round(abs(mean), -1) in (50, 100, 200)):
                                                fig.add_layout(Span(location=float(mean), dimension='width',
                                                                    line_color='#666666', line_dash='dashed',
                                                                    line_width=.8))
                                        # if isinstance(span, float):
                                        #     if np.isnan(span):
                                        #         mean = ind.mean()
                                        #         if not np.isnan(mean) and (abs(mean) < .1 or
                                        #                                    round(abs(mean), 1) == .5 or
                                        #                                    round(abs(mean), -1) in (50, 100, 200)):
                                        #             fig.add_layout(Span(location=float(mean), dimension='width',
                                        #                                 line_color='#666666', line_dash='dashed',
                                        #                                 line_width=.8))
                                        #     else:
                                        #         fig.add_layout(Span(location=span, dimension='width',
                                        #                             line_color='#666666', line_dash='dashed',
                                        #                             line_width=.8))
                                        # elif isinstance(span, list):
                                        #     for _span_ in span:
                                        #         fig.add_layout(Span(location=float(_span_), dimension='width',
                                        #                             line_color='#666666', line_dash='dashed',
                                        #                             line_width=.8))
                                        # elif isinstance(span, dict) and 'value' in span:
                                        #     span_color = span.get(
                                        #         'line_color', '#666666')
                                        #     span_dash = span.get(
                                        #         'line_dash', 'dashed')
                                        #     span_width = span.get(
                                        #         'line_width', .8)
                                        #     _lines_value = span.get(
                                        #         'value')
                                        #     if isinstance(_lines_value, list):
                                        #         for _span_ in _lines_value:
                                        #             fig.add_layout(Span(location=float(_span_), dimension='width',
                                        #                                 line_color=span_color, line_dash=span_dash,
                                        #                                 line_width=span_width))
                                        #     else:
                                        #         fig.add_layout(Span(location=float(_lines_value), dimension='width',
                                        #                             line_color=span_color, line_dash=span_dash,
                                        #                             line_width=span_width))

                                    if is_overlay[ids]:
                                        ohlc_tooltips.append(
                                            (ind_name[ids], NBSP.join(tuple(tooltips))))
                                    else:

                                        set_tooltips(
                                            fig, [(legend_label, NBSP.join(tooltips))], vline=True, renderers=[r])
                                        fig.yaxis.axis_label = ind_name[ids]
                                        fig.yaxis.axis_label_text_color = 'white' if black_sytle else 'black'
                                        if fig_ohlc._main_ohlc:
                                            fig.yaxis.visible = False
                                        else:
                                            fig.yaxis.visible = True
                                        # If the sole indicator line on this figure,
                                        # have the legend only contain text without the glyph
                                        # if len(names[ids]) == 1:
                                        #     fig.legend.glyph_width = 0
                                        if len(names) == 1:
                                            fig.legend.glyph_width = 0
                    else:
                        if any(isplot):
                            is_candles = category == 'candles'
                            if is_candles and len(names) < 4:
                                is_candles = False
                            tooltips = []
                            colors = cycle([next(ohlc_colors)]
                                           if is_overlay else colorgen())
                            legend_label = name  # 初始化命名的名称
                            if is_overlay and not is_candles:  # 主图叠加
                                if datainfo in fig_ohlc_list[i]:  # 副图
                                    fig = fig_ohlc_list[i].get(
                                        datainfo)
                                else:
                                    fig = fig_ohlc
                            elif is_candles:  # 副图是蜡烛图

                                indicator_candles_index.append(ic)
                                assert len(names) >= 4
                                names = list(
                                    map(lambda x: x.lower(), names))
                                # 按open,high,low,volume进行排序
                                filed_index = []
                                missing_index = []
                                for ii, file in enumerate(FILED):
                                    is_missing = True
                                    for n in names:
                                        if file in n:
                                            filed_index.append(
                                                names.index(n))
                                            is_missing = False
                                    else:
                                        if is_missing:
                                            missing_index.append(ii)
                                assert not missing_index, f"数据中缺失{[FILED[ii] for ii in missing_index]}字段"
                                for ie in filed_index:
                                    source[i][j].add(
                                        indicator[:, ie].tolist(), names[ie])
                                index = np.arange(indicator.shape[0])
                                fig_ohlc_ = new_indicator_figure(
                                    new_bokeh_figure, fig_ohlc, plot_width, plotinfo.get('height', 100))
                                fig_ohlc_.segment('index', names[filed_index[1]], 'index', names[filed_index[2]],
                                                  source=source[i][j], color=black_color)
                                ohlc_bars_ = fig_ohlc_.vbar('index', BAR_WIDTH, names[filed_index[0]], names[filed_index[3]], source=source[i][j],
                                                            line_color=black_color, fill_color=inc_cmap)
                                ohlc_tooltips_ = [
                                    ('x, y', NBSP.join(('$index',
                                                        '$y{0,0.0[0000]}'))),
                                    ('OHLC', NBSP.join((f"@{names[filed_index[0]]}{'{'}0,0.0[0000]{'}'}",
                                                        f"@{names[filed_index[1]]}{'{'}0,0.0[0000]{'}'}",
                                                        f"@{names[filed_index[2]]}{'{'}0,0.0[0000]{'}'}",
                                                        f"@{names[filed_index[3]]}{'{'}0,0.0[0000]{'}'}")))]
                                for lj in range(len(names)):
                                    if lj not in filed_index:
                                        if isplot[lj]:
                                            tooltips = []
                                            _lines_name = __lines[lj]
                                            ind = indicator[:, lj]
                                            color = next(colors)
                                            source_name = names[lj]
                                            if ind.dtype == bool:
                                                ind = ind.astype(int)
                                            source[i][j].add(ind,
                                                             source_name)
                                            tooltips.append(
                                                f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                                            # tooltips.append(f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                                            _lineinfo = deepcopy(lines_setting)
                                            if _lines_name in lineinfo:
                                                _lineinfo = {
                                                    **_lineinfo, **lineinfo[_lines_name]}
                                            # if 'line_color' in _lineinfo and _lineinfo["line_color"] is not None:
                                            #     ...
                                            # else:
                                            if _lineinfo.get("line_color", None) is None:
                                                _lineinfo.update(
                                                    dict(line_color=color))
                                            # if is_overlay:
                                            fig_ohlc_.line(
                                                'index', source_name, source=source[i][j],
                                                legend_label=source_name, **_lineinfo)
                                            ohlc_tooltips_.append(
                                                (_lines_name, NBSP.join(tuple(tooltips))))

                                set_tooltips(
                                    fig_ohlc_, ohlc_tooltips_, vline=True, renderers=[ohlc_bars_])
                                fig_ohlc_.yaxis.axis_label = ind_name
                                fig_ohlc_.yaxis.axis_label_text_color = black_color
                                if fig_ohlc._main_ohlc:
                                    fig_ohlc_.yaxis.visible = False
                                else:
                                    fig_ohlc_.yaxis.visible = True
                                indicator_figs.append(fig_ohlc_)
                                fig_ohlc_list[i].update(
                                    {ind_name: fig_ohlc_})
                                ic += 1
                                _indicator = ffillnan(indicator)
                                _mulit_ind = len(
                                    _indicator.shape) > 1
                                source[i][j].add(
                                    np.max(_indicator, axis=1).tolist() if _mulit_ind else _indicator.tolist(), f"{ind_name}_h")
                                source[i][j].add(
                                    np.min(_indicator, axis=1).tolist() if _mulit_ind else _indicator.tolist(), f"{ind_name}_l")
                                indicator_h.append(
                                    f"{ind_name}_h")
                                indicator_l.append(
                                    f"{ind_name}_l")
                                # custom_js_args_ = dict(ohlc_range=fig_ohlc_.y_range, candles_range=[indicator_figs[ic].y_range for ic in indicator_candles_index],
                                #                        source=source[i][j])
                                # custom_js_args_.update(
                                #     volume_range=fig_volume.y_range)
                                # fig_ohlc_.x_range.js_on_change('end', CustomJS(args=custom_js_args_,
                                #                                                code=_AUTOSCALE_JS_CALLBACK))
                            else:
                                if datainfo in fig_ohlc_list[i]:  # 副图
                                    __fig = fig_ohlc_list[i].get(
                                        datainfo)
                                else:
                                    __fig = fig_ohlc
                                fig = new_indicator_figure(
                                    new_bokeh_figure, __fig, plot_width, plotinfo.get('height', 150))
                                indicator_figs.append(fig)
                                ic += 1
                                _indicator = ffillnan(indicator)
                                _mulit_ind = len(
                                    _indicator.shape) > 1
                                source[i][j].add(
                                    np.max(_indicator, axis=1).tolist() if _mulit_ind else _indicator.tolist(), f"{ind_name}_h")
                                source[i][j].add(
                                    np.min(_indicator, axis=1).tolist() if _mulit_ind else _indicator.tolist(), f"{ind_name}_l")
                                indicator_h.append(
                                    f"{ind_name}_h")
                                indicator_l.append(
                                    f"{ind_name}_l")

                            if not is_candles:
                                if_vbar = False
                                for jx in range(len(isplot)):
                                    if isplot[jx]:
                                        _lines_name = __lines[jx]
                                        ind = indicator[:, jx]
                                        color = next(colors)
                                        source_name = names[jx]
                                        if ind.dtype == bool:
                                            ind = ind.astype(np.float64)
                                        source[i][j].add(
                                            ind.tolist(), source_name)
                                        tooltips.append(
                                            f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                                        _lineinfo = deepcopy(lines_setting)

                                        if _lines_name in lineinfo:
                                            _lineinfo = {
                                                **_lineinfo, **(lineinfo[_lines_name])}
                                        if _lineinfo.get("line_color", None) is None:
                                            _lineinfo.update(
                                                dict(line_color=color))
                                        if is_overlay:
                                            fig.line(
                                                'index', source_name, source=source[i][j],
                                                legend_label=source_name, **_lineinfo)
                                            # fig.line(
                                            #     'index', source_name, source=source[i][j],
                                            #     legend_label=source_name, line_color=color,
                                            #     line_width=1.3)
                                        else:
                                            # if category and isinstance(category, dict) and _lines_name in category:
                                            if lineinfo and _lines_name in lineinfo and lineinfo[_lines_name].get('line_dash', None) == 'vbar':
                                                if_vbar = True
                                                if "zeros" not in source[i][j].column_names:
                                                    source[i][j].add(
                                                        [0.,]*len(ind), "zeros")

                                                _line_inc = np.where(ind > 0., 1, 0).astype(
                                                    np.uint8).astype(str).tolist()
                                                source[i][j].add(
                                                    _line_inc, f"{_lines_name}_inc")
                                                # if f"{_lines_name}_color" in category:
                                                #     _line_inc_cmap = category[f"{_lines_name}_color"]
                                                # if "line_color" in lineinfo[_lines_name]:
                                                _line_inc_cmap = lineinfo[_lines_name]["line_color"]
                                                if _line_inc_cmap is None:
                                                    _line_inc_cmap = factor_cmap(
                                                        f"{_lines_name}_inc", COLORS, ['0', '1'])
                                                r = fig.vbar('index', BAR_WIDTH, 'zeros', source_name, source=source[i][j],
                                                             line_color='black', fill_color=_line_inc_cmap)

                                                # if "line_color" in lineinfo[_lines_name]:
                                                #     _line_inc_cmap = lineinfo[_lines_name]["line_color"]
                                                # else:
                                                #     _line_inc = np.where(ind > 0., 1, 0).astype(
                                                #         np.uint8).astype(str).tolist()
                                                #     source[i][j].add(
                                                #         _line_inc, f"{_lines_name}_inc")
                                                #     _line_inc_cmap = factor_cmap(
                                                #         f"{_lines_name}_inc", COLORS, ['0', '1'])
                                                # r = fig.vbar('index', BAR_WIDTH, 'zeros', source_name, source=source[i][j],
                                                #              line_color='black', fill_color=_line_inc_cmap)
                                            else:
                                                r = fig.line(
                                                    'index', source_name, source=source[i][j],
                                                    legend_label=source_name, **_lineinfo)
                                            # r = fig.line(
                                            #     'index', source_name, source=source[i][j],
                                            #     legend_label=source_name, line_color=color,
                                            #     line_width=1.3)
                                            # Add dashed centerline just because
                                            # mean = float(
                                            #     pd.Series(ind).mean())
                                            # mean = ind.mean()
                                            # if not np.isnan(mean) and (abs(mean) < .1 or
                                            #                            round(abs(mean), 1) == .5 or
                                            #                            round(abs(mean), -1) in (50, 100, 200)):
                                            #     fig.add_layout(Span(location=float(mean), dimension='width',
                                            #                         line_color='#666666', line_dash='dashed',
                                            #                         line_width=.8))
                                #             if np.isnan(span):
                                #                 mean = ind.mean()
                                #                 if not np.isnan(mean) and (abs(mean) < .1 or
                                #                                            round(abs(mean), 1) == .5 or
                                #                                            round(abs(mean), -1) in (50, 100, 200)):
                                #                     fig.add_layout(Span(location=float(mean), dimension='width',
                                #                                         line_color='#666666', line_dash='dashed',
                                #                                         line_width=.8))
                                #             else:
                                #                 if isinstance(span, dict):
                                #                     if _lines_name in span:
                                #                         fig.add_layout(Span(location=float(span.get(_lines_name)), dimension='width',
                                #                                             line_color='#666666', line_dash='dashed',
                                #                                             line_width=.8))
                                # else:
                                #     if (not np.isnan(span)) and isinstance(span, float):
                                #         fig.add_layout(Span(location=span, dimension='width',
                                #                             line_color='#666666', line_dash='dashed',
                                #                             line_width=.8))
                                else:
                                    # if (not np.isnan(span)) and isinstance(span, float):
                                    #     fig.add_layout(Span(location=span, dimension='width',
                                    #                         line_color='#666666', line_dash='dashed',
                                    #                         line_width=.8))
                                    if if_vbar:
                                        renderers = fig.renderers.copy()
                                        fig.renderers = list(
                                            sorted(renderers, key=lambda x: not isinstance(x.glyph, VBar)))
                                    if span:
                                        for ind_span in span:
                                            if np.isnan(ind_span["location"]) and not is_overlay if isinstance(is_overlay, bool) else not all(is_overlay):
                                                ind = ind.astype(np.float32)
                                                mean = ind[~np.isnan(
                                                    ind)].mean()
                                                if not np.isnan(mean) and (abs(mean) < .1 or
                                                                           round(abs(mean), 1) == .5 or
                                                                           round(abs(mean), -1) in (50, 100, 200)):
                                                    fig.add_layout(Span(location=float(mean), dimension='width',
                                                                        line_color='#666666', line_dash='dashed',
                                                                        line_width=.8))
                                            else:
                                                fig.add_layout(
                                                    Span(**ind_span))
                                    else:
                                        ind = ind.astype(np.float32)
                                        non_nan_ind = ind[~np.isnan(ind)]
                                        mean = non_nan_ind.mean() if len(non_nan_ind) > 0 else np.nan
                                        if not np.isnan(mean) and (abs(mean) < .1 or
                                                                   round(abs(mean), 1) == .5 or
                                                                   round(abs(mean), -1) in (50, 100, 200)):
                                            fig.add_layout(Span(location=float(mean), dimension='width',
                                                                line_color='#666666', line_dash='dashed',
                                                                line_width=.8))
                                    # if isinstance(span, float):
                                    #     if np.isnan(span):
                                    #         mean = ind.mean()
                                    #         if not np.isnan(mean) and (abs(mean) < .1 or
                                    #                                    round(abs(mean), 1) == .5 or
                                    #                                    round(abs(mean), -1) in (50, 100, 200)):
                                    #             fig.add_layout(Span(location=float(mean), dimension='width',
                                    #                                 line_color='#666666', line_dash='dashed',
                                    #                                 line_width=.8))
                                    #     else:
                                    #         fig.add_layout(Span(location=span, dimension='width',
                                    #                             line_color='#666666', line_dash='dashed',
                                    #                             line_width=.8))
                                    # elif isinstance(span, list):
                                    #     for _span_ in span:
                                    #         # fig.add_layout(Span(location=float(_span_), dimension='width',
                                    #         #                     line_color='#666666', line_dash='dashed',
                                    #         #                     line_width=.8))
                                    #         if not np.isnan(_span_["location"]):
                                    #             fig.add_layout(Span(*(_span_)))
                                    # elif isinstance(span, dict) and 'value' in span:
                                    #     span_color = span.get(
                                    #         'line_color', '#666666')
                                    #     span_dash = span.get(
                                    #         'line_dash', 'dashed')
                                    #     span_width = span.get(
                                    #         'line_width', .8)
                                    #     _lines_value = span.get(
                                    #         'value')
                                    #     if isinstance(_lines_value, list):
                                    #         for _span_ in _lines_value:
                                    #             fig.add_layout(Span(location=float(_span_), dimension='width',
                                    #                                 line_color=span_color, line_dash=span_dash,
                                    #                                 line_width=span_width))
                                    #     else:
                                    #         fig.add_layout(Span(location=float(_lines_value), dimension='width',
                                    #                             line_color=span_color, line_dash=span_dash,
                                    #                             line_width=span_width))

                                if is_overlay:
                                    ohlc_tooltips.append(
                                        (ind_name, NBSP.join(tuple(tooltips))))
                                else:

                                    set_tooltips(
                                        fig, [(legend_label, NBSP.join(tooltips))], vline=True, renderers=[r])
                                    fig.yaxis.axis_label = ind_name
                                    fig.yaxis.axis_label_text_color = 'white' if black_sytle else 'black'
                                    # If the sole indicator line on this figure,
                                    # have the legend only contain text without the glyph
                                    if len(names) == 1:
                                        fig.legend.glyph_width = 0
                                    if fig_ohlc._main_ohlc:
                                        fig.yaxis.visible = False
                                    else:
                                        fig.yaxis.visible = True

                    if signal_info:
                        signal_ind_data_ = dict(
                            long_signal=None, exitlong_signal=None, short_signal=None, exitshort_signal=None)
                        for k, v in signal_info.items():
                            signalkey, signalcolor, signalmarker, signaloverlap, signalshow, signalsize = list(
                                v.values())
                            if signalshow:
                                signaldata: np.ndarray
                                if doubles:
                                    index1, index2 = search_index(
                                        names, k)
                                    signaldata = indicator[index1][:, index2]
                                else:
                                    signaldata = indicator[:, names.index(
                                        k)]
                                signal_index = np.argwhere(
                                    signaldata > 0)[:, 0]
                                if signaloverlap:
                                    price_data = df[signalkey].values
                                    signal_fig = fig_ohlc
                                else:
                                    signal_fig = fig
                                    try:
                                        if doubles:
                                            index1, index2 = search_index(
                                                names, signalkey)
                                            price_data = indicator[index1][:, index2]
                                        else:
                                            price_data = indicator[:, names.index(
                                                signalkey)]
                                    except:
                                        price_data = signaldata.copy()
                                signal_price = price_data[signaldata > 0]
                                signal_datetime = df.datetime.values[signaldata > 0]
                                signal_source_ = ColumnDataSource(dict(
                                    index=signal_index,
                                    datetime=signal_datetime,
                                    price=signal_price,
                                    size=[float(signalsize),] *
                                    len(signal_index),
                                ))
                                signal_ind_data_.update(
                                    {k: signal_source_})
                                signal_ind_data_source[i][j].append(
                                    signal_ind_data_)

                                r = signal_fig.scatter(x='index', y='price', source=signal_ind_data_source[i][j][-1].get(k), fill_color=signalcolor,
                                                       marker=signalmarker, line_color='black', size="size")
                                tooltips = [(k, "@price{0.00}"),]
                                set_tooltips(signal_fig, tooltips,
                                             vline=False, renderers=[r,])
            set_tooltips(fig_ohlc, ohlc_tooltips,
                         vline=True, renderers=[ohlc_bars], mouse=True)
            fig_ohlc.yaxis.axis_label = f"{symbols[i][-1]}"
            fig_ohlc.yaxis.axis_label_text_color = black_color
            # custom_js_args = dict(ohlc_range=fig_ohlc.y_range, candles_range=[indicator_figs[ic].y_range for ic in indicator_candles_index],
            #                       source=source[i][j])
            custom_js_args = dict(ohlc_range=fig_ohlc.y_range, indicator_range=[indicator_figs[_ic].y_range for _ic in range(len(indicator_figs))],
                                  indicator_h=indicator_h, indicator_l=indicator_l, source=source[i][j])
            # 成交量
            fig_volume = new_indicator_figure(
                new_bokeh_figure, fig_ohlc, plot_width, y_axis_label="volume", height=60)
            fig_volume.css_classes = ["volume-chart"]
            fig_volume.xaxis.formatter = fig_ohlc.xaxis[0].formatter
            if fig_ohlc._main_ohlc:
                fig_volume.yaxis.visible = False
            else:
                fig_volume.yaxis.visible = True
            fig_volume.xaxis.visible = True
            fig_ohlc.xaxis.visible = False  # Show only Volume's xaxis
            r_volume = fig_volume.vbar(
                'index', BAR_WIDTH, 'volume', source=source[i][j], color=inc_cmap)
            colors = cycle(colorgen())
            r_volume5 = fig_volume.line('index', 'volume5', source=source[i][j],
                                        legend_label='volume5', line_color=next(colors),
                                        line_width=1.3)
            r_volume10 = fig_volume.line('index', 'volume10', source=source[i][j],
                                         legend_label='volume10', line_color=next(colors),
                                         line_width=1.3)
            # set_tooltips(
            #     fig_volume, [('volume', '@volume{0.00 a}')], renderers=[r_volume])
            set_tooltips(fig_volume, [
                        ('volume', '@volume{0.00}'), ('volume5', '@volume5{0.00}'), ('volume10', '@volume10{0.00}'),], renderers=[r_volume])
            fig_volume.yaxis.formatter = NumeralTickFormatter(
                format="0 a")
            fig_volume.yaxis.axis_label_text_color = black_color

            custom_js_args.update(volume_range=fig_volume.y_range)
            fig_ohlc.x_range.js_on_change('end', CustomJS(args=custom_js_args,
                                                          code=_AUTOSCALE_JS_CALLBACK))
            # 主图交易信号
            # if j == 0:
            if j == 0:
                if trade_signal:
                    r1 = fig_ohlc.scatter(x='index', y='price', source=long_source[i][j], fill_color=COLORS[0],
                                            marker='triangle', line_color='black', size='size')
                    r2 = fig_ohlc.scatter(x='index', y='price', source=short_source[i][j], fill_color=COLORS[1],
                                            marker='inverted_triangle', line_color='black', size='size')
                    r3 = fig_ohlc.scatter(x='index', y='price', source=long_flat_source[i][j], fill_color=COLORS[0],
                                            marker='inverted_triangle', line_color='black', size='size')
                    r4 = fig_ohlc.scatter(x='index', y='price', source=short_flat_source[i][j], fill_color=COLORS[1],
                                            marker='triangle', line_color='black', size='size')
                    tooltips = [
                        ("position", "@pos{0,0}"), ("price", "@price{0.00}")]
                    # if 'count' in trades:
                    #     tooltips.append(("Count", "@count{0.00}"))
                    set_tooltips(fig_ohlc, tooltips,
                                 vline=False, renderers=[r1,])
                    set_tooltips(fig_ohlc, tooltips,
                                 vline=False, renderers=[r2,])
                    set_tooltips(fig_ohlc, tooltips + [("P/L", "@profit{0.00}")],
                                 vline=False, renderers=[r3,])
                    set_tooltips(fig_ohlc, tooltips + [("P/L", "@profit{0.00}")],
                                 vline=False, renderers=[r4,])
                    fig_ohlc.segment(x0='index', y0='price', x1='flat_index', y1='flat_price',
                                        source=long_segment_source[i][j], color='yellow' if black_sytle else "blue", line_width=3, line_dash="4 4")
                    fig_ohlc.segment(x0='index', y0='price', x1='flat_index', y1='flat_price',
                                        source=short_segment_source[i][j], color='yellow' if black_sytle else "blue", line_width=3, line_dash="4 4")

            figs_ohlc[i].append(fig_ohlc)
            plots = [fig_ohlc, fig_volume]+indicator_figs
            all_plots[i].append(plots)
            linked_crosshair = CrosshairTool(
                dimensions='both', line_color=black_color)
            for f in plots:
                if f.legend:
                    f.legend.nrows = 1
                    f.legend.label_height = 6
                    f.legend.visible = True
                    f.legend.location = 'top_left'
                    f.legend.border_line_width = 0
                    # f.legend.border_line_color = '#333333'
                    f.legend.padding = 1
                    f.legend.spacing = 0
                    f.legend.margin = 0
                    f.legend.label_text_font_size = '8pt'
                    f.legend.label_text_line_height = 1.2
                    # "hide"  # "mute"  #
                    f.legend.click_policy = click_policy

                f.min_border_left = 0
                f.min_border_top = 0  # 3
                f.min_border_bottom = 6
                f.min_border_right = 10
                f.outline_line_color = '#666666'

                if black_sytle:
                    # hover_style = Styles(
                    #     styles={
                    #         ":host": {
                    #             "--hover-bg": "rgba(40, 40, 40, 0.95)",
                    #             "--hover-text": "#eeeeee",
                    #             "--hover-border": "#666"
                    #         }
                    #     }
                    # )
                    # f.styles = [hover_style]
                    # 图表全局样式
                    f.background_fill_color = "#1a1a1a"  # 更柔和的深灰色
                    f.border_fill_color = "#1a1a1a"
                    f.outline_line_color = "#404040"  # 边框线颜色

                    # 坐标轴样式
                    f.xaxis.major_label_text_color = "#cccccc"
                    f.xaxis.axis_label_text_color = "#cccccc"
                    f.xaxis.major_tick_line_color = "#666666"
                    f.xaxis.minor_tick_line_color = "#444444"
                    f.xaxis.axis_line_color = "#666666"

                    f.yaxis.major_label_text_color = "#cccccc"
                    f.yaxis.axis_label_text_color = "#cccccc"
                    f.yaxis.major_tick_line_color = "#666666"
                    f.yaxis.minor_tick_line_color = "#444444"
                    f.yaxis.axis_line_color = "#666666"

                    # 网格线样式
                    f.xgrid.grid_line_color = "#333333"
                    f.xgrid.grid_line_alpha = 0.3
                    f.ygrid.grid_line_color = "#333333"
                    f.ygrid.grid_line_alpha = 0.3

                    # 图例样式
                    f.legend.background_fill_color = "#333333"
                    f.legend.background_fill_alpha = 0.7
                    f.legend.label_text_color = "#ffffff"
                    f.legend.border_line_color = "#555555"

                    # 标题样式（如果图表有标题）
                    if f.title:
                        f.title.text_color = "#ffffff"
                        f.title.text_font_style = "bold"

                    # 工具提示样式增强
                    # for tool in f.tools:
                    #     if isinstance(tool, HoverTool):
                    #         # 保留原始工具提示内容，只添加样式包装
                    #         original_content = tool.tooltips
                    #         tool.tooltips = f"""
                    #         <div style="
                    #             background: rgba(40,40,40,0.95) !important;
                    #             color: #eeeeee !important;
                    #             border: 1px solid #666;
                    #             padding: 5px;
                    #         ">
                    #             {original_content}
                    #         </div>
                    #         """
                    #         tool.line_policy = "interp"

                    # 成交量图特殊处理
                    if f == fig_volume:
                        f.background_fill_alpha = 0.5  # 半透明效果
                        f.border_fill_alpha = 0.5
                    # f.background_fill_color = "black"
                    # f.border_fill_color = 'black'
                    # f.background_fill_alpha = 0.5
                    # f.xgrid.grid_line_color = None
                    # f.xaxis.major_label_text_color = 'white'
                    # f.yaxis.major_label_text_color = 'white'
                    # f.ygrid.grid_line_color = None
                    # f.legend.background_fill_color = "navy"
                    # f.legend.background_fill_alpha = 0.5
                    # f.title.text_color = 'white'
                    # f.legend.label_text_color = 'white'
                    # f.ygrid.grid_line_alpha = 0.5
                    # f.ygrid.grid_line_dash = [6, 4]
                f.add_tools(linked_crosshair)
                wheelzoom_tool = next(
                    wz for wz in f.tools if isinstance(wz, WheelZoomTool))
                wheelzoom_tool.maintain_focus = False
                if f._main_ohlc:
                    f.yaxis.visible = False
                    f.tools.visible = False
            # for f in plots:
            #     if f.legend:
            #         f.legend.nrows = 1
            #         f.legend.label_height = 6
            #         f.legend.visible = True
            #         f.legend.location = 'top_left'
            #         f.legend.border_line_width = 0
            #         # f.legend.border_line_color = '#333333'
            #         f.legend.padding = 1
            #         f.legend.spacing = 0
            #         f.legend.margin = 0
            #         f.legend.label_text_font_size = '8pt'
            #         f.legend.label_text_line_height = 1.2
            #         f.legend.click_policy = click_policy  # "hide"  # "mute"  #

            #     f.min_border_left = 0
            #     f.min_border_top = 0  # 3
            #     f.min_border_bottom = 6
            #     f.min_border_right = 10
            #     f.outline_line_color = '#666666'

            #     if black_sytle:
            #         f.background_fill_color = "black"
            #         f.border_fill_color = 'black'
            #         f.background_fill_alpha = 0.5
            #         f.xgrid.grid_line_color = None
            #         f.xaxis.major_label_text_color = 'white'
            #         f.yaxis.major_label_text_color = 'white'
            #         f.ygrid.grid_line_color = None
            #         f.legend.background_fill_color = "navy"
            #         f.legend.background_fill_alpha = 0.5
            #         f.title.text_color = 'white'
            #         f.legend.label_text_color = 'white'
            #         # f.ygrid.grid_line_alpha = 0.5
            #         # f.ygrid.grid_line_dash = [6, 4]

            #     f.add_tools(linked_crosshair)
            #     wheelzoom_tool = next(
            #         wz for wz in f.tools if isinstance(wz, WheelZoomTool))
            #     wheelzoom_tool.maintain_focus = False
            #     if f._main_ohlc:
            #         f.yaxis.visible = False
            #         f.tools.visible = False
            # kwargs = dict(sizing_mode='stretch_width')
            kwargs = dict(
                ncols=1,
                toolbar_location='right',
                sizing_mode='stretch_both',  # ✅ 统一在此处定义
                toolbar_options=dict(logo=None),
                merge_tools=True
            )
        ismain = [info["ismain"] for info in btind_info]
        ismain = ismain[1:] if len(ismain) > 1 else [False,]
        # _all_plots = all_plots[i]
        # [setattr(___ps.xaxis, "visible", btind_info[_ips].get('xaxis', True))
        #  for _ips, __ps in enumerate(_all_plots) for _jps, ___ps in enumerate(__ps) if _jps != 0]
        # [setattr(___ps.yaxis, "visible", btind_info[_ips].get('yaxis', True))
        #  for _ips, __ps in enumerate(_all_plots) for _jps, ___ps in enumerate(__ps)]

        if any(ismain):
            _ip = 0
            _all_plots = [_p for _ip, _p in enumerate(
                all_plots[1:]) if not ismain[_ip]]
            first_plot = all_plots[0]
            # [setattr(__fps.yaxis,"visible",btind_info.get('yaxis',True)) for __fps in first_plot]
            row_plots = []
            _panel_name = [symbols[i][0], str(cycles[i][0]),]
            for _ismain, _ps in list(zip(ismain, all_plots[1:])):
                if _ismain:
                    _ip += 1
                    # [setattr(__plots, 'height', 150)
                    # for __plots in _plots if __plots._ohlc]
                    # [setattr(__ps.yaxis,"visible",btind_info.get('yaxis',True)) for __ps in _ps]
                    # [setattr(__ps.xaxis,"visible",btind_info.get('xaxis',True)) for _ips,__ps in enumerate(_ps) if _ips!=0]
                    figs = gridplot(
                        _ps,
                        # ncols=1,
                        # toolbar_location='right',
                        # toolbar_options=dict(logo=None),
                        # merge_tools=False,
                        **kwargs
                    )
                    row_plots.append(figs)
                    if _panel_name[0] != symbols[i][_ip]:
                        _panel_name.append(symbols[i][_ip])
                    _panel_name.append(str(cycles[i][_ip]))
            controls = row(*row_plots, width_policy='max')
            figs = gridplot(
                first_plot,
                # ncols=1,
                # toolbar_location='right',
                # toolbar_options=dict(logo=None),
                # merge_tools=True,
                **kwargs
            )
            _lay = column(controls, figs, width_policy='max',
                          sizing_mode='stretch_both')
            # name_ = '_'.join(
            #     [symbols[i][j], *(str(symbol_multi_cycle[i][j][__ip]) for __ip in range(_ip+1))])
            panel.append(
                Panel(child=_lay, title='_'.join(_panel_name)))  # name_))
            # _all_plots.insert(0,first_plot)
            all_plots = _all_plots

        if all_plots:
            for ips, _ps in enumerate(all_plots):
                # 检查_ps是否是列表，如果是则解包
                if isinstance(_ps, list):
                    layout = column(
                        *(_ps),  # 使用*解包列表元素
                        sizing_mode='stretch_both',
                        css_classes=["dynamic-column"],
                        stylesheets=[panel_CUSTOM_CSS],
                    )
                else:
                    layout = column(
                        _ps,  # 如果不是列表则直接使用
                        sizing_mode='stretch_both',
                        css_classes=["dynamic-column"],
                        stylesheets=[panel_CUSTOM_CSS],
                    )
                # layout = column(
                #     children=_ps,
                #     sizing_mode='stretch_both',
                #     css_classes=["dynamic-column"],
                #     stylesheets=[panel_CUSTOM_CSS],  # 注入自定义CSS
                #     # spacer=spacer
                # )
                panel.append(
                    Panel(
                        child=layout, title=f"{symbols[i][ips]}_{cycles[i][ips]}"))
                # )
                # __index = _all_plots.index(_ps)
                # figs = gridplot(
                #     _ps,
                #     ncols=1,
                #     toolbar_location='right',
                #     toolbar_options=dict(logo=None),
                #     merge_tools=True,
                #     **kwargs
                # )
                # panel.append(
                #     Panel(child=figs, title=f"{symbols[i][__index]}_{cycles[i][__index]}"))

        # figs = gridplot(
        #     plots,
        #     ncols=1,
        #     toolbar_location='right',
        #     toolbar_options=dict(logo=None),
        #     merge_tools=True,
        #     **kwargs
        # )
        # panel.append(
        #     Panel(child=figs, title=f"{df.symbol.iloc[0]}_{df.duration.iloc[0]}"))
        # ts.append(Tabs(tabs=panel, background='black' if black_sytle else 'white',
        #           width=plot_width if plot_width else None, width_policy='max'))
        ts.append(Tabs(tabs=panel,
                  width=plot_width if plot_width else None, width_policy='max',
                  sizing_mode='stretch_both',
                       css_classes=["dark-tabs"] if black_sytle else [],
                       stylesheets=[DARK_TABS_CSS] if black_sytle else []
                       ))

        # ts[-1].legend.label_text_color ='white'# if black_sytle else 'black'
    # [pl.on_change('active', callbacks=callback_strategy)
    #  for pl in ts]
    div = PreText(text=account_info if account_info else 'test', height=20)
    # symbol_text = PreText(text=symbols[0][0], height=20, width=100)
    # buy_button = Button(label="Buy", height=20, width=40)
    # sell_button = Button(label="Sell", height=20, width=40)
    # cover_button = Button(label="Cover", height=20, width=40)
    # button = row(symbol_text, buy_button, sell_button, cover_button)
    # tabs = Tabs(tabs=[Panel(child=t, title=snames[it]) for it, t in enumerate(ts)],
    #             background='black' if black_sytle else 'white', width=plot_width if plot_width else None, width_policy='max')
    tabs = Tabs(tabs=[Panel(child=t, title=snames[it]) for it, t in enumerate(ts)],
                background=white_color, width=plot_width if plot_width else None, width_policy='max',
                sizing_mode='stretch_both',
                css_classes=["dark-tabs"] if black_sytle else [],
                stylesheets=[DARK_TABS_CSS] if black_sytle else []
                )
    # [ta.on_change('active', callbacks=callback_strategy)
    # for ta in tabs]
    _lay = column(div, tabs, width_policy='max', sizing_mode='stretch_both')
    doc.add_root(_lay)

    def update(event=None):
        update_datas = loadData(update_datas_dir)
        trade_datas = loadData(trade_datas_dir)
        account_info = loadData(account_info_dir)
        # trade_signal=False if trade_datas is None else all(trade_datas)
        if update_datas:
            for i, update_data in enumerate(update_datas):
                # if i==tabs.active:
                for j, data in enumerate(update_data):
                    _source_data = source[i][j].data
                    source_datetime = _source_data['datetime']
                    last_source_datetime = source_datetime[-1]
                    update_datetime = data['datetime']
                    # data_lentgh = len(update_datetime)
                    soruce_datas = {}
                    if last_source_datetime in update_datetime:

                        index = update_datetime.index(
                            last_source_datetime)
                        for k, v in _source_data.items():
                            if k != 'index':
                                _v = v[:-1]
                                _v.extend(data[k][index:])
                                soruce_datas.update({k: _v})
                    else:
                        for k, v in _source_data.items():
                            if k != 'index':
                                v.extend(data[k])
                                soruce_datas.update({k: v})

                    update_length = len(soruce_datas['close'])
                    soruce_datas.update(
                        {'index': list(range(update_length))})
                    source[i][j].data = soruce_datas

                    # print(j,soruce_datas['datetime'][-2:],soruce_datas['index'][-2:],soruce_datas['close'][-2:])
                    # _length=len(source_datetime)
                    if update_length != len(source_datetime) and ispoint:
                        for fig in all_plots[i][j]:
                            fig.x_range.update(end=update_length+20)
                        # figs_ohlc[i][j][ix].x_range.update(end=update_length+20)
            storeData(None, update_datas_dir)
        # if trade_datas and any(list(flatten(trade_datas))):
        # print(trade_datas)
        if trade_datas:
            for i, trade_source_ in enumerate(trade_datas):
                for j, trade_data in enumerate(trade_source_):
                    # for j, datas in enumerate(trade_data):
                    # print(datas)
                    if len(trade_data) > 1:
                        pos, price = trade_data
                        _span = ohlc_span[i][j]
                        if _span.location != price:
                            if pos:
                                if not _span.visible:
                                    _span.visible = True
                                _span.location = float(price)
                                if pos > 0:
                                    _span.line_color = 'green'
                                else:
                                    _span.line_color = 'red'
                            else:
                                _span.location = 0.
                                _span.visible = False
                        # if isinstance(datas[0], Iterable):
                        #     pos, price = datas[0]
                        #     _span = spans[i][j][0]
                        #     if pos:
                        #         _span.visible = True
                        #         _span.location = float(price)
                        #         if pos > 0:
                        #             _span.line_color = 'green'
                        #         else:
                        #             _span.line_color = 'red'
                        #     else:
                        #         _span.visible = False
                            # span.location=float(0.)

            storeData(None, trade_datas_dir)
        if account_info:
            div.update(text=account_info)
            storeData(None, account_info_dir)
    doc.add_periodic_callback(update, args.period_milliseconds)


apps = {'/': Application(FunctionHandler(make_document))}
io_loop = IOLoop.current()
port = randint(1000, 9999)
server = Server(applications=apps, io_loop=io_loop, port=port)
print(f"| live_plot : localhost:{port}")
server.start()
server.show('/')
io_loop.start()
