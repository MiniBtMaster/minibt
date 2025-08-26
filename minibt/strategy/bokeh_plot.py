from __future__ import annotations
import html  # 新增导入
# import flet as ft
from copy import deepcopy
import warnings
from bokeh.palettes import Category10
from .strategy import Strategy
import os
import bokeh.colors.named as bcn
# from bokeh.colors.named import (
#     lime as BULL_COLOR,
#     tomato as BEAR_COLOR
# )
from itertools import cycle
from ..indicators import pd, np, Callable
from functools import partial
from bokeh.models import Tabs
from bokeh.transform import factor_cmap
from bokeh.models import (
    CrosshairTool,
    CustomJS,
    ColumnDataSource,
    NumeralTickFormatter,
    Span,
    HoverTool,
    Range1d,
    WheelZoomTool,
    Styles,
    PreText,
    LinearAxis,
    Div
)
# from bokeh.models import Div
# from bokeh.models.widgets import CheckboxGroup, Slider, RangeSlider
from bokeh.layouts import gridplot, column, row, layout
from bokeh.io import output_file, show, save  # , curdoc
from bokeh.plotting import figure as _figure
setattr(_figure, '_main_ohlc', False)
setattr(_figure, '_candles', False)

try:  # 版本API有变
    from bokeh.models import TabPanel as Panel
except:
    from bokeh.models import Panel
warnings.filterwarnings("ignore", category=UserWarning)
# 'JPY_PARENT_PID' in os.environ
IS_JUPYTER_NOTEBOOK = 'JPY_INTERRUPT_EVENT' in os.environ
FILED = ['open', 'high', 'low', 'close']
_FILED = ['datetime', 'open', 'high', 'low', 'close', 'volume']
_FILED = ['datetime', 'open', 'high', 'low', 'close', 'volume']
_factors_plot: Callable = None
# https://blog.csdn.net/d1240673769/article/details/118806884
# https://blog.csdn.net/bingbangx/article/details/125874865
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
    height: 100vh;
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


def ffillnan(arr: np.ndarray) -> np.ndarray:
    if len(arr.shape) > 1:
        arr = pd.DataFrame(arr)
    else:
        arr = pd.Series(arr)
    arr.fillna(method='ffill', inplace=True)
    arr.fillna(method='bfill', inplace=True)
    return arr.values


def set_tooltips(fig: _figure, tooltips=(), vline=True, renderers=(), if_datetime: bool = True, if_date=False) -> None:
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
    fig.add_tools(HoverTool(
        point_policy='follow_mouse',
        renderers=renderers, formatters=formatters,
        tooltips=tooltips, mode='vline' if vline else 'mouse'),
    )


def new_bokeh_figure(plot_width, height=300) -> Callable:
    return partial(
        _figure,
        x_axis_type='linear',
        width=plot_width,
        height=height,
        width_policy='max',
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


def new_indicator_figure(new_bokeh_figure: Callable, fig_ohlc: _figure, plot_width, height=80, **kwargs) -> _figure:
    height = int(height) if height and height > 10 else 80
    fig = new_bokeh_figure(plot_width, height)(x_range=fig_ohlc.x_range,
                                               active_scroll='xwheel_zoom',
                                               active_drag='xpan',
                                               **kwargs)
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


def plot(strategys: list[Strategy],
         trade_signal: bool = True,
         filename: str = 'bokeh_plot',
         plot_width: int = None,
         black_sytle: bool = False,
         open_browser: bool = False,
         save_plot: bool = True,
         cwd: str = "./Plots",
         ** kwargs) -> None:
    """
    Like much of GUI code everywhere, this is a mess.
    """
    from bokeh.io import reset_output
    reset_output()
    global IS_JUPYTER_NOTEBOOK, _factors_plot
    # DARK_TABS_CSS = f"""
    # :host(.dark-tabs) {{
    #     border-color: {border_color};
    # }}
    # """
    # curdoc().theme = 'dark_minimal'
    black_color = "white" if black_sytle else "black"
    white_color = "black" if black_sytle else "white"
    num = len(strategys)
    s_name: list[str] = [t.__class__.__name__ for t in strategys]
    results: list[list[pd.DataFrame]] = [t.get_results()
                                         for t in strategys]  # 回测结果
    datas: list[list[pd.DataFrame]] = [
        [data for data in t.get_btdatasset().values()] for t in strategys]  # 原始数据
    btind_main = [
        [data.ismain for data in t.get_btdatasset().values()] for t in strategys]
    btind_info = [t.get_plot_datas()[4]
                  for t in strategys]
    dir = strategys[0].get_base_dir()  # 路径
    indicator_datas: list[list[list]] = [t.get_plot_datas()[2]
                                         for t in strategys]  # 指标数据indicator
    datas_num: list[int] = [
        t.get_btdatasset().num for t in strategys]  # 合约个数
    symbols: list[list[str]] = [
        [data.symbol for data in t.get_btdatasset().values()] for t in strategys]  # 合约名称
    symbol_multi_cycle: list[list[int]] = [
        [data.cycle for data in t.get_btdatasset().values()] for t in strategys]  # 周期
    start_value: list[float] = [t.config.value for t in strategys]  # 开始回测价值
    profit_plot: list[bool] = [t.config.profit_plot for t in strategys]
    click_policy: list[str] = [t.config.click_policy for t in strategys]
    # K线颜色
    # COLORS = [BEAR_COLOR, BULL_COLOR]
    COLORS = [bcn.tomato, bcn.lime]
    inc_cmap = factor_cmap('inc', COLORS, ['0', '1'])
    new_colors = {'bear': bcn.tomato, 'bull': bcn.lime}
    BAR_WIDTH = .8  # K宽度
    NBSP = '\N{NBSP}' * 4
    # 'solid', 'dashed', 'dotted', 'dotdash', 'dashdot'

    lines_setting = dict(line_dash='solid', line_width=1.3)

    factors_dfs = [[] for _ in strategys]
    factors_names = [[] for _ in strategys]
    with open(f'{dir}/strategy/autoscale_cb.js', encoding='utf-8') as _f:
        _AUTOSCALE_JS_CALLBACK = _f.read()

    value_source: list[list] = [[] for _ in range(num)]  # 价值数据

    if trade_signal:
        long_source: list[list] = [[] for _ in range(num)]
        short_source: list[list] = [[] for _ in range(num)]
        long_flat_source: list[list] = [[] for _ in range(num)]
        short_flat_source: list[list] = [[] for _ in range(num)]
        long_segment_source: list[list] = [[] for _ in range(num)]
        short_segment_source: list[list] = [[] for _ in range(num)]
    ohlc_extreme_values: list[list] = [[] for _ in range(num)]  # 范围数据
    source: list[list[ColumnDataSource]] = [[] for _ in range(num)]  # K线数据
    figs_ohlc: list[list[_figure]] = [[] for _ in range(num)]
    ts: list[Tabs] = []
    fig_ohlc_list = [{} for i in range(num)]  # K线数据
    # signal_main_data_source : list[list]= [[] for i in range(num)]  # K线数据
    signal_ind_data_source: list[list[list]] = [[] for i in range(num)]  # K线数据

    for i, rs in enumerate(results):
        for j, trades in enumerate(rs):
            _td = datas[i][j]
            symbol = symbols[i][j]
            if trade_signal:
                _long_source, _short_source, _long_flat_source, _short_flat_source, \
                    _long_segment_source, _short_segment_source = get_trades_source(
                        _td, trades, symbol, False)
                long_source[i].append(_long_source)
                short_source[i].append(_short_source)
                long_flat_source[i].append(_long_flat_source)
                short_flat_source[i].append(_short_flat_source)
                long_segment_source[i].append(_long_segment_source)
                short_segment_source[i].append(_short_segment_source)
            value_source[i].append(ColumnDataSource(dict(
                index=trades.index,
                datetime=_td.datetime.values,
                # value=trades['_'.join([symbol, 'total_profit'])].values,
                value=trades.total_profit.values,
                level=np.ones(_td.shape[0])*start_value[i],
            )))

    for ik, _datas in enumerate(datas):
        panel = []
        all_plots = []
        for id, df in enumerate(_datas):
            # isoverlap = df.overlap
            # io = df.id.resample_id
            # plot_index = df._plot_index
            factors_dfs[ik].append(getattr(df, "factors_df", None))
            factors_names[ik].append(df.sname)
            df = df.pandas_object
            signal_ind_data_source[ik].append([])
            df.reset_index(drop=True, inplace=True)

            index = df.index
            pad = (index[-1] - index[0]) / 20
            df = df[_FILED]
            # if isoverlap:
            #     df["plot_index"] = plot_index
            #     print(df.head())
            df['volume5'] = df.volume.rolling(5).mean()
            df['volume10'] = df.volume.rolling(10).mean()
            source[ik].append(ColumnDataSource(df))
            # 涨跌颜色数据
            source[ik][id].add((df.close >=
                                df.open).values.astype(np.uint8).astype(str), 'inc')
            ohlc_extreme_values[ik].append(
                df[['high', 'low']].copy(deep=False))

            # if isoverlap:
            #     source[ik][id].add(plot_index, "plot_index")
            #     # 上下影线
            #     figs_ohlc[ik][io].segment('plot_index', 'high', 'plot_index', 'low',
            #                               source=source[ik][id], color=black_color)
            #     # 实体线
            #     ohlc_bars = figs_ohlc[ik][io].vbar('plot_index', 0.4, 'open', 'close', source=source[ik][id],
            #                                        line_color=black_color, fill_color=inc_cmap)

            #     # 提示格式
            #     ohlc_tooltips = [
            #         ('x, y', NBSP.join(('$index',
            #                             '$y{0,0.0[0000]}'))),
            #         ('OHLC', NBSP.join(('@open{0,0.0[0000]}',
            #                             '@high{0,0.0[0000]}',
            #                             '@low{0,0.0[0000]}',
            #                             '@close{0,0.0[0000]}'))),
            #         ('Volume', '@volume{0,0}')]
            #     set_tooltips(figs_ohlc[ik][io], ohlc_tooltips,
            #                  vline=True, renderers=[ohlc_bars])

            # K线图
            if btind_main[ik][id] and id != 0:
                fig_ohlc: _figure = new_bokeh_figure_main(plot_width, btind_info[ik][id].get('height', 150))(
                    x_range=Range1d(index[0], index[-1],
                                    min_interval=10,
                                    bounds=(index[0] - pad,
                                            index[-1] + pad)) if index.size > 1 else None)
                fig_ohlc._main_ohlc = True
                # fig_ohlc.css_classes = ["candle-chart"]
            else:
                fig_ohlc: _figure = new_bokeh_figure(plot_width, btind_info[ik][id].get('height', 300))(
                    x_range=Range1d(index[0], index[-1],
                                    min_interval=10,
                                    bounds=(index[0] - pad,
                                            index[-1] + pad)) if index.size > 1 else None)
            fig_ohlc.css_classes = ["candle-chart"]
            _colors = btind_info[ik][id].get('candlestyle', new_colors)
            if _colors and id == 0:
                # COLORS = [getattr(bcn, _colors.get('bear', 'tomato')), getattr(
                #     bcn, _colors.get('bull', 'lime'))]
                _COLORS = list(_colors.values())
                inc_cmap = factor_cmap('inc', _COLORS, ['0', '1'])
            # 上下影线
            fig_ohlc.segment('index', 'high', 'index', 'low',
                             source=source[ik][id], color=black_color)
            # 实体线
            # fig_ohlc.segment('datetime', 'high', 'index', 'low',
            #                  source=source[ik][id], color=black_color)
            # # 实体线
            ohlc_bars = fig_ohlc.vbar('index', BAR_WIDTH, 'open', 'close', source=source[ik][id],
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

            spanstyle = btind_info[ik][id].get('spanstyle', [])
            for ohlc_span in spanstyle:
                fig_ohlc.add_layout(Span(**ohlc_span))

            # 指标数据
            indicators_data = indicator_datas[ik][id]
            indicator_candles_index = []
            indicator_figs = []
            indicator_h: list[str] = []
            indicator_l: list[str] = []

            if indicators_data:
                ohlc_colors = colorgen()
                ic = 0
                for ind_index, (isplot, name, lines, _lines, ind_name, is_overlay, category, indicator, doubles, plotinfo, span, _signal) in enumerate(indicators_data):
                    lineinfo: dict = plotinfo.get('linestyle', {})
                    datainfo = plotinfo.get('source', "")
                    signal_info: dict = plotinfo.get('signalstyle', {})

                    if doubles:
                        _doubles_fig = []
                        for ids in range(2):
                            if any(isplot[ids]):
                                is_candles = category[ids] == 'candles'
                                tooltips = []
                                colors = cycle(
                                    ohlc_colors if is_overlay[ids] else colorgen())
                                legend_label = name[ids]  # 初始化命名的名称
                                if is_overlay[ids] and not is_candles:  # 主图叠加
                                    fig = fig_ohlc
                                else:
                                    fig = new_indicator_figure(
                                        new_bokeh_figure, fig_ohlc, plot_width, plotinfo.get('height', None))
                                    indicator_figs.append(fig)
                                    _mulit_ind = len(
                                        indicator[ids].shape) > 1
                                    source[ik][id].add(
                                        np.max(indicator[ids], axis=1) if _mulit_ind else indicator[ids], f"{legend_label}_h")
                                    source[ik][id].add(
                                        np.min(indicator[ids], axis=1) if _mulit_ind else indicator[ids], f"{legend_label}_l")
                                    indicator_h.append(f"{legend_label}_h")
                                    indicator_l.append(f"{legend_label}_l")
                                    ic += 1
                                _doubles_fig.append(fig)

                                if not is_candles:
                                    # print(isplot, indicator)
                                    # for j in range(indicator.shape[1]):
                                    for j in range(len(isplot[ids])):
                                        if isplot[ids][j]:
                                            _lines_name = _lines[ids][j]
                                            ind = indicator[ids][:, j]
                                            color = next(colors)
                                            source_name = lines[ids][j]
                                            if ind.dtype == bool:
                                                ind = ind.astype(
                                                    np.float64)
                                            source[ik][id].add(ind,
                                                               source_name)
                                            tooltips.append(
                                                f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                                            # tooltips.append(f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                                            _lineinfo = deepcopy(
                                                lines_setting)
                                            if _lines_name in lineinfo:
                                                _lineinfo = {
                                                    **_lineinfo, **lineinfo[_lines_name]}
                                            # if 'line_color' not in _lineinfo:
                                            if _lineinfo.get("line_color", None) is None:
                                                _lineinfo.update(
                                                    dict(line_color=color))
                                            if is_overlay[ids]:
                                                fig.line(
                                                    'index', source_name, source=source[ik][id],
                                                    legend_label=source_name, **_lineinfo)
                                                # , line_color=color,
                                                # line_width=1.3)
                                            else:
                                                if lineinfo and _lines_name in lineinfo and lineinfo[_lines_name].get('line_dash', None) == 'vbar':
                                                    if "zeros" not in source[ik][id].column_names:
                                                        source[ik][id].add(
                                                            [0.,]*len(ind), "zeros")
                                                    _line_inc = np.where(ind > 0., 1, 0).astype(
                                                        np.uint8).astype(str).tolist()
                                                    source[ik][id].add(
                                                        _line_inc, f"{_lines_name}_inc")
                                                    if "line_color" in lineinfo[_lines_name]:
                                                        _line_inc_cmap = lineinfo[_lines_name]["line_color"]
                                                    else:
                                                        _line_inc_cmap = factor_cmap(
                                                            f"{_lines_name}_inc", COLORS, ['0', '1'])
                                                    r = fig.vbar('index', BAR_WIDTH, 'zeros', source_name, source=source[ik][id],
                                                                 line_color='black', fill_color=_line_inc_cmap)
                                                else:
                                                    r = fig.line(
                                                        'index', source_name, source=source[ik][id],
                                                        legend_label=source_name, **_lineinfo)
                                                # line_color=color,
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
                                                #                         line_width=.5))

                                    else:
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

                                    if is_overlay[ids]:
                                        # ohlc_tooltips.append((ind_name, NBSP.join(tooltips)))
                                        ohlc_tooltips.append(
                                            (ind_name[ids], NBSP.join(tuple(tooltips))))
                                    else:
                                        # set_tooltips(fig, [(ind_name, NBSP.join(tooltips))], vline=True, renderers=[r])
                                        set_tooltips(
                                            fig, [(legend_label, NBSP.join(tooltips))], vline=True, renderers=[r])
                                        fig.yaxis.axis_label = ind_name[ids]
                                        fig.yaxis.axis_label_text_color = black_color
                                        if fig_ohlc._main_ohlc:
                                            fig.yaxis.visible = False
                                        else:
                                            fig.yaxis.visible = True
                                        # If the sole indicator line on this figure,
                                        # have the legend only contain text without the glyph
                                        if len(lines) == 1:
                                            fig.legend.glyph_width = 0
                            # if signal_info:
                            #     for _sting in _signal:
                            #         if (ids == 0 and signal_overlaps_.get(_sting)) or (ids == 1 and signal_overlaps_.get(_sting) == False):
                            #             r = fig.scatter(x='index', y='price', source=signal_ind_data_source[ik][id][ind_index].get(_sting), fill_color=signal_colors_.get(_sting),
                            #                             marker=signal_markers_.get(_sting), line_color='black', size=signal_sizes.get(_sting, "size"))  #
                            #             tooltips = [(_sting, "@price{0.00}"),]
                            #             set_tooltips(fig, tooltips,
                            #                          vline=False, renderers=[r,])
                    else:
                        if any(isplot):

                            # is_overlay = category == 'overlap'
                            is_candles = category == 'candles'
                            if is_candles and len(lines) < 4:
                                is_candles = False
                            tooltips = []
                            colors = cycle(
                                ohlc_colors if is_overlay else colorgen())
                            legend_label = name  # 初始化命名的名称
                            if is_overlay and not is_candles:  # 主图叠加
                                # print(fig_ohlc_list[ik]
                                #       [id], datainfo, ind_name)

                                if datainfo in fig_ohlc_list[ik]:  # 副图
                                    fig = fig_ohlc_list[ik].get(
                                        datainfo)
                                else:
                                    fig = fig_ohlc
                            elif is_candles:  # 副图是蜡烛图
                                # if any(isplot):
                                indicator_candles_index.append(ic)
                                assert len(lines) >= 4
                                lines = list(
                                    map(lambda x: x.lower(), lines))
                                # 按open,high,low,volume进行排序
                                filed_index = []
                                missing_index = []
                                for ii, file in enumerate(FILED):
                                    is_missing = True
                                    for n in lines:
                                        if file in n:
                                            filed_index.append(
                                                lines.index(n))
                                            is_missing = False
                                    else:
                                        if is_missing:
                                            missing_index.append(ii)
                                assert not missing_index, f"数据中缺失{[FILED[ii] for ii in missing_index]}字段"
                                for ie in filed_index:
                                    source[ik][id].add(indicator[:,
                                                                 ie], lines[ie])

                                # source[ik][id][-1].add(indicator[:,
                                #                        1], 'H')
                                # source[ik][id][-1].add(indicator[:,
                                #                        2], 'L')

                                index = np.arange(indicator.shape[0])
                                pad = (index[-1] - index[0]) / 20
                                fig_ohlc_ = new_indicator_figure(
                                    new_bokeh_figure, fig_ohlc, plot_width, plotinfo.get('height', 100))
                                fig_ohlc_.segment(
                                    'index', lines[filed_index[1]], 'index', lines[filed_index[2]], source=source[ik][id], color=black_color)
                                ohlc_bars_ = fig_ohlc_.vbar('index', BAR_WIDTH, lines[filed_index[0]], lines[filed_index[3]], source=source[ik][id],
                                                            line_color=black_color, fill_color=inc_cmap)
                                ohlc_tooltips_ = [
                                    ('x, y', NBSP.join(('$index',
                                                        '$y{0,0.0[0000]}'))),
                                    ('OHLC', NBSP.join((f"@{lines[filed_index[0]]}{'{'}0,0.0[0000]{'}'}",
                                                        f"@{lines[filed_index[1]]}{'{'}0,0.0[0000]{'}'}",
                                                        f"@{lines[filed_index[2]]}{'{'}0,0.0[0000]{'}'}",
                                                        f"@{lines[filed_index[3]]}{'{'}0,0.0[0000]{'}'}")))]

                                fig_ohlc_.yaxis.axis_label = ind_name
                                fig_ohlc_.yaxis.axis_label_text_color = black_color
                                if fig_ohlc._main_ohlc:
                                    fig_ohlc_.yaxis.visible = False
                                else:
                                    fig_ohlc_.yaxis.visible = True
                                fig_ohlc_list[ik].update(
                                    {ind_name: fig_ohlc_})

                                for j in range(len(lines)):
                                    if j not in filed_index:
                                        if isplot[j]:
                                            tooltips = []
                                            _lines_name = _lines[j]
                                            ind = indicator[:, j]
                                            color = next(colors)
                                            source_name = lines[j]
                                            if ind.dtype == bool:
                                                ind = ind.astype(int)
                                            source[ik][id].add(ind,
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
                                                'index', source_name, source=source[ik][id],
                                                legend_label=source_name, **_lineinfo)
                                            ohlc_tooltips_.append(
                                                (_lines_name, NBSP.join(tuple(tooltips))))
                                set_tooltips(fig_ohlc_, ohlc_tooltips_,
                                             vline=True, renderers=[ohlc_bars_])
                                indicator_figs.append(fig_ohlc_)
                                ic += 1
                                _mulit_ind = len(indicator.shape) > 1
                                source[ik][id].add(np.max(indicator, axis=1) if _mulit_ind else indicator,
                                                   f"{legend_label}_h")
                                source[ik][id].add(np.min(indicator, axis=1) if _mulit_ind else indicator,
                                                   f"{legend_label}_l")
                                indicator_h.append(f"{legend_label}_h")
                                indicator_l.append(f"{legend_label}_l")

                            else:
                                if datainfo in fig_ohlc_list[ik]:  # 副图
                                    __fig = fig_ohlc_list[ik].get(
                                        datainfo)
                                else:
                                    __fig = fig_ohlc
                                fig = new_indicator_figure(
                                    new_bokeh_figure, __fig, plot_width, plotinfo.get('height', None))
                                indicator_figs.append(fig)
                                ic += 1
                                _mulit_ind = len(indicator.shape) > 1
                                source[ik][id].add(np.max(indicator, axis=1) if _mulit_ind else indicator,
                                                   f"{legend_label}_h")
                                source[ik][id].add(np.min(indicator, axis=1) if _mulit_ind else indicator,
                                                   f"{legend_label}_l")
                                indicator_h.append(f"{legend_label}_h")
                                indicator_l.append(f"{legend_label}_l")

                            if not is_candles:
                                # print(isplot, indicator)
                                # for j in range(indicator.shape[1]):
                                for j in range(len(isplot)):
                                    if isplot[j]:
                                        _lines_name = _lines[j]
                                        ind = indicator[:, j]
                                        color = next(colors)
                                        source_name = lines[j]
                                        if ind.dtype == bool:
                                            ind = ind.astype(int)
                                        source[ik][id].add(ind,
                                                           source_name)
                                        tooltips.append(
                                            f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                                        # tooltips.append(f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                                        _lineinfo = deepcopy(lines_setting)
                                        if _lines_name in lineinfo:
                                            _lineinfo = {
                                                **_lineinfo, **lineinfo[_lines_name]}
                                        # if 'line_color' not in _lineinfo:
                                        if _lineinfo.get("line_color", None) is None:
                                            _lineinfo.update(
                                                dict(line_color=color))
                                        if is_overlay:
                                            fig.line(
                                                'index', source_name, source=source[ik][id],
                                                legend_label=source_name, **_lineinfo)
                                            # ,line_color=color,
                                            #     line_width=1.3)
                                        else:
                                            # if category and isinstance(category, dict) and _lines_name in category:
                                            if lineinfo and _lines_name in lineinfo and lineinfo[_lines_name].get('line_dash', None) == 'vbar':
                                                if "zeros" not in source[ik][id].column_names:
                                                    source[ik][id].add(
                                                        [0.,]*len(ind), "zeros")
                                                _line_inc = np.where(ind > 0., 1, 0).astype(
                                                    np.uint8).astype(str).tolist()
                                                source[ik][id].add(
                                                    _line_inc, f"{_lines_name}_inc")
                                                # if f"{_lines_name}_color" in category:
                                                #     _line_inc_cmap = category[f"{_lines_name}_color"]
                                                if "line_color" in lineinfo[_lines_name]:
                                                    _line_inc_cmap = lineinfo[_lines_name]["line_color"]
                                                else:
                                                    _line_inc_cmap = factor_cmap(
                                                        f"{_lines_name}_inc", COLORS, ['0', '1'])
                                                r = fig.vbar('index', BAR_WIDTH, 'zeros', source_name, source=source[ik][id],
                                                             line_color='black', fill_color=_line_inc_cmap)
                                            else:
                                                r = fig.line(
                                                    'index', source_name, source=source[ik][id],
                                                    legend_label=source_name, **_lineinfo)

                                else:
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

                                if is_overlay:
                                    # ohlc_tooltips.append((ind_name, NBSP.join(tooltips)))
                                    ohlc_tooltips.append(
                                        (ind_name, NBSP.join(tuple(tooltips))))
                                else:
                                    # set_tooltips(fig, [(ind_name, NBSP.join(tooltips))], vline=True, renderers=[r])
                                    set_tooltips(
                                        fig, [(legend_label, NBSP.join(tooltips))], vline=True, renderers=[r])
                                    fig.yaxis.axis_label = ind_name
                                    fig.yaxis.axis_label_text_color = black_color
                                    # If the sole indicator line on this figure,
                                    # have the legend only contain text without the glyph
                                    if len(lines) == 1:
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
                                        _lines, k)
                                    signaldata = indicator[index1][:, index2]
                                else:
                                    signaldata = indicator[:, _lines.index(
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
                                                _lines, signalkey)
                                            price_data = indicator[index1][:, index2]
                                        else:
                                            price_data = indicator[:, _lines.index(
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
                                signal_ind_data_source[ik][id].append(
                                    signal_ind_data_)

                                r = signal_fig.scatter(x='index', y='price', source=signal_ind_data_source[ik][id][-1].get(k), fill_color=signalcolor,
                                                       marker=signalmarker, line_color='black', size="size")
                                tooltips = [(k, "@price{0.00}"),]
                                set_tooltips(signal_fig, tooltips,
                                             vline=False, renderers=[r,])

            # if not if_tick:
            set_tooltips(fig_ohlc, ohlc_tooltips,
                         vline=True, renderers=[ohlc_bars])
            fig_ohlc.yaxis.axis_label = f"{symbols[ik][id]}_{symbol_multi_cycle[ik][id]}"
            fig_ohlc.yaxis.axis_label_text_color = black_color

            source[ik][id].add(ohlc_extreme_values[ik]
                               [id].min(1), 'Low')
            source[ik][id].add(ohlc_extreme_values[ik]
                               [id].max(1), 'High')
            custom_js_args = dict(ohlc_range=fig_ohlc.y_range, indicator_range=[indicator_figs[_ic].y_range for _ic in range(len(indicator_figs))],
                                  indicator_h=indicator_h, indicator_l=indicator_l, source=source[ik][id])

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
                'index', BAR_WIDTH, 'volume', source=source[ik][id], color=inc_cmap)
            colors = cycle(colorgen())
            r_volume5 = fig_volume.line('index', 'volume5', source=source[ik][id],
                                        legend_label='volume5', line_color=next(colors),
                                        line_width=1.3)
            r_volume10 = fig_volume.line('index', 'volume10', source=source[ik][id],
                                         legend_label='volume10', line_color=next(colors),
                                         line_width=1.3)
            set_tooltips(fig_volume, [
                        ('volume', '@volume{0.00}'), ('volume5', '@volume5{0.00}'), ('volume10', '@volume10{0.00}'),], renderers=[r_volume])
            fig_volume.yaxis.formatter = NumeralTickFormatter(format="0")
            fig_volume.yaxis.axis_label_text_color = black_color

            custom_js_args.update(volume_range=fig_volume.y_range)
            fig_ohlc.x_range.js_on_change('end', CustomJS(args=custom_js_args,
                                                          code=_AUTOSCALE_JS_CALLBACK))
            # custom_js_args_ = dict(
            #     candles_range=[indicator_figs[ic].y_range for ic in indicator_candles_index], source=source[ik][id][-1])
            # fig_ohlc.x_range.js_on_change('end', CustomJS(args=custom_js_args_,
            #                                                 code=_AUTOSCALE_JS_CALLBAC_))
            # 主图交易信号和权益曲线
            if id == 0:
                if trade_signal:
                    r1 = fig_ohlc.scatter(x='index', y='price', source=long_source[ik][id], fill_color=COLORS[0],
                                            marker='triangle', line_color='black', size='size')
                    r2 = fig_ohlc.scatter(x='index', y='price', source=short_source[ik][id], fill_color=COLORS[1],
                                            marker='inverted_triangle', line_color='black', size='size')
                    r3 = fig_ohlc.scatter(x='index', y='price', source=long_flat_source[ik][id], fill_color=COLORS[0],
                                            marker='inverted_triangle', line_color='black', size='size')
                    r4 = fig_ohlc.scatter(x='index', y='price', source=short_flat_source[ik][id], fill_color=COLORS[1],
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
                                        source=long_segment_source[ik][id], color='yellow' if black_sytle else "blue", line_width=3, line_dash="4 4")
                    fig_ohlc.segment(x0='index', y0='price', x1='flat_index', y1='flat_price',
                                        source=short_segment_source[ik][id], color='yellow' if black_sytle else "blue", line_width=3, line_dash="4 4")
                plots: list[_figure] = [
                    fig_ohlc, fig_volume]+indicator_figs
                if profit_plot[ik]:
                    # 权益曲线
                    source_key = 'value'
                    fig_value = new_indicator_figure(new_bokeh_figure, fig_ohlc, plot_width,
                                                     y_axis_label=source_key,
                                                     height=90)
                    fig_value.css_classes = ["value-chart"]
                    fig_value.tags = ["profit_plot"]  # ✅ 使用Bokeh内置tags属性标记
                    # fig_value.profit_plot = True
                    fig_value.patch('index', 'level',
                                    source=value_source[ik][id],
                                    fill_color='#ffffea', line_color='#ffcb66', line_dash='dashed')
                    r_value = fig_value.line(
                        'index', source_key, source=value_source[ik][id], legend_label='value', line_color='blue', line_width=2, line_alpha=1)
                    tooltip_format = f'@{source_key}{{+0,0.[00]}}'
                    tick_format = '0,0.[00]'
                    set_tooltips(
                        fig_value, [(source_key, tooltip_format)], renderers=[r_value,])

                    fig_value.yaxis.formatter = NumeralTickFormatter(
                        format=tick_format)
                    fig_value.yaxis.axis_label = 'Value'
                    fig_value.yaxis.axis_label_text_color = black_color
                    plots.insert(0, fig_value)

            else:
                plots = [fig_ohlc, fig_volume]+indicator_figs
            figs_ohlc[ik].append(fig_ohlc)
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
                    f.legend.click_policy = click_policy[ik]

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
            # kwargs = dict(sizing_mode='stretch_both')  # 'stretch_width')
            kwargs = dict(
                ncols=1,
                toolbar_location='right',
                sizing_mode='stretch_both',  # ✅ 统一在此处定义
                toolbar_options=dict(logo=None),
                merge_tools=True
            )
            all_plots.append(plots)

            # carrier_selection = CheckboxGroup(active=[0, 1])
            # binwidth_select = Slider(start=1, end=30,
            #                          step=1, value=5,
            #                          title='Delay Width (min)')
            # range_select = RangeSlider(start=-60, end=180, value=(-60, 120),
            #                            step=5, title='Delay Range (min)')
            # controls = row(div, carrier_selection,
            #                binwidth_select, range_select, width_policy='max')
            # if ix == 0 and id == 0:
            #     div = PreText(text='test', height=20)
            #     div.update(text="1000000")
            #     _lay = column(div, figs, width_policy='max')
            # # [Panel(child=controls, title='Delay Histogram'),] +
            #     panel.append(
            #         Panel(child=_lay, title=f"{symbols[ik][id]}_{symbol_multi_cycle[ik][id][ix]}"))
            # else:
        ismain = btind_main[ik][1:]
        _ip = 0
        if any(ismain):
            _all_plots = [_p for _ip, _p in enumerate(
                all_plots[1:]) if not ismain[_ip]]
            first_plot = all_plots[0]
            row_plots = []
            for _ismain, _plots in list(zip(ismain, all_plots[1:])):
                if _ismain:
                    _ip += 1
                    # [setattr(__plots, 'height', 150)
                    # for __plots in _plots if __plots._ohlc]
                    # _plots.yaxis.visible = False
                    figs = gridplot(
                        _plots,
                        # ncols=1,
                        # toolbar_location='right',
                        # toolbar_options=dict(logo=None),
                        # merge_tools=False,
                        # sizing_mode='stretch_both',  # 添加全屏拉伸
                        ** kwargs
                    )
                    row_plots.append(figs)
            controls = row(*row_plots, width_policy='max')
            figs = gridplot(
                first_plot,
                # ncols=1,
                # toolbar_location='right',
                # toolbar_options=dict(logo=None),
                # merge_tools=True,
                # sizing_mode='stretch_both',  # 添加全屏拉伸
                ** kwargs
            )
            # [setattr(mult_fig.yaxis.visible , False) for _imf , mult_fig in enumerate(figs) if _imf]
            _lay = column(controls, figs, width_policy='max')
            name_ = '_'.join(
                [symbols[ik][id], *(str(symbol_multi_cycle[ik][__ip]) for __ip in range(_ip+1))])
            panel.append(
                Panel(child=_lay, title=name_))
            # _all_plots.insert(0,first_plot)
            all_plots = _all_plots
        # total_height = 1200
        panels = []
        for _ips, __plots in enumerate(all_plots):
            layout = column(
                children=__plots,
                sizing_mode='stretch_both',
                css_classes=["dynamic-column"],
                stylesheets=[panel_CUSTOM_CSS],  # 注入自定义CSS
                # spacer=spacer
            )

            panels.append(
                Panel(
                    child=layout, title=f"{symbols[ik][_ips]}_{symbol_multi_cycle[ik][_ips]}")
            )
        # 添加因子分析图表作为新的Panel
        for fi, factors_df in enumerate(factors_dfs[ik]):
            if factors_df is not None:
                if _factors_plot is None:
                    from .factors_plot import factors_plot
                    _factors_plot = factors_plot
                factor_layout = _factors_plot(factors_df)  # 生成因子分析布局
                # 加入当前策略的panels
                panels.append(Panel(child=factor_layout,
                              title=f"{factors_names[ik][fi]}因子分析"))

        ts.append(Tabs(tabs=panels,
                  width=plot_width if plot_width else None, width_policy='max',
                  sizing_mode='stretch_both',
                       css_classes=["dark-tabs"] if black_sytle else [],
                       stylesheets=[DARK_TABS_CSS] if black_sytle else []
                       ))
        # if factors_df is not None:
        #     from .factors_plot import factors_plot
        #     ts.append(factors_plot(factors_df))
    tabs = Tabs(tabs=[Panel(child=t, title=s_name[i]) for i, t in enumerate(ts)],
                background=white_color, width=plot_width if plot_width else None, width_policy='max',
                sizing_mode='stretch_both',
                css_classes=["dark-tabs"] if black_sytle else [],
                stylesheets=[DARK_TABS_CSS] if black_sytle else []
                )
    if open_browser:
        IS_JUPYTER_NOTEBOOK = False

    if IS_JUPYTER_NOTEBOOK:
        from bokeh.resources import INLINE
        from bokeh.io import output_notebook
        notebook_handle = True
        open_browser = False
        # curstate().output_notebook()
        output_notebook(INLINE)
    else:
        notebook_handle = False
        open_browser = True

    if save_plot:
        # save(tabs)
        # 保存的路径

        if filename and isinstance(filename, str):
            if not filename.endswith('.html'):
                filename += '.html'
            # _path=os.path.join(dir,"Plots",filename)
            # filename = f"{dir}/Plots/{filename}"
            # print(filename)
        else:
            filename = 'bokeh_plot.html'
        cwd = cwd if isinstance(
            cwd, str) and cwd else "./Plots/"
        if not os.path.exists(cwd):
            os.makedirs(cwd, exist_ok=True)
        FileName = os.path.join(dir, filename)
        # save(tabs, FileName)
        # output_file(FileName)
        # ft.app(main)

        from bokeh.embed import file_html
        from bokeh.resources import INLINE, CDN
        INLINE.css_raw.append(panel_CUSTOM_CSS)  # 确保CSS被包含

        html = file_html(tabs, CDN, "Strategy Plot")
        # html = html.replace('<head>', f'<head>{custom_css}')
        with open(FileName, 'w') as f:
            f.write(html)

    try:
        show(tabs, browser=None if open_browser else 'none',
             notebook_handle=notebook_handle)
    except Exception as e:
        # print(e)
        if IS_JUPYTER_NOTEBOOK:
            from IPython.display import IFrame, display
            # # 方案一：直接文件路径（需浏览器允许本地文件）
            # # display(IFrame(f'file://{FileName}', width=1000, height=600))

            # # 或方案二：通过 Jupyter 服务路径
            notebook_path = os.path.abspath(os.getcwd())
            file_url = f"/files/{os.path.relpath(FileName, notebook_path)}"
            display(IFrame(file_url, width=1000, height=600))
            # show(ts[0], browser=None if open_browser else 'none',
            #      notebook_handle=notebook_handle)
    return tabs


def get_trades_source(data: pd.DataFrame, trades: pd.DataFrame, symbol: str, if_tick: bool) -> tuple[ColumnDataSource]:
    datetime = data.datetime.values
    high = data.high.values
    low = data.low.values
    close = data.close.values
    # position = trades['_'.join([symbol, 'positions'])].values
    position = trades.positions.values
    sizes = trades.sizes.values
    ps = position*sizes
    float_profit = trades.float_profits.values
    short_ticks = []
    long_ticks = []
    long_flat_ticks = []
    short_flat_ticks = []
    long_profit = []
    short_profit = []
    pre_pos = 0
    for i, pos_ in enumerate(position):
        fp = float_profit[i]
        if pos_ == -1 and pre_pos == 0:
            short_ticks.append(i)
            pre_fp = fp
        elif pos_ == 1 and pre_pos == 0:
            long_ticks.append(i)
            pre_fp = fp
        elif pos_ == 0:
            if pre_pos == 1:
                long_flat_ticks.append(i)
                long_profit.append(fp-pre_fp)
            elif pre_pos == -1:
                short_flat_ticks.append(i)
                short_profit.append(fp-pre_fp)
        else:
            if pos_ != pre_pos and pre_pos != 0:
                if pos_ == 1:
                    short_flat_ticks.append(i)
                    short_profit.append(fp-pre_fp)

                    long_ticks.append(i)
                    pre_fp = fp
                else:
                    long_flat_ticks.append(i)
                    long_profit.append(fp-pre_fp)
                    short_ticks.append(i)
                    pre_fp = fp
        pre_pos = pos_

    # long
    long_source = ColumnDataSource(dict(
        index=long_ticks,
        datetime=datetime[long_ticks],
        price=low[long_ticks],
        pos=ps[long_ticks],
        size=[12.,]*len(long_ticks)
    ))
    short_source = ColumnDataSource(dict(
        index=short_ticks,
        datetime=datetime[short_ticks],
        price=high[short_ticks],
        pos=ps[short_ticks],
        size=[12.,]*len(short_ticks)
    ))
    long_flat_source = ColumnDataSource(dict(
        index=long_flat_ticks,
        datetime=datetime[long_flat_ticks],
        price=high[long_flat_ticks],
        pos=ps[long_flat_ticks],
        profit=long_profit,
        size=[12.,]*len(long_flat_ticks)
    ))

    short_flat_source = ColumnDataSource(dict(
        index=short_flat_ticks,
        datetime=datetime[short_flat_ticks],
        price=low[short_flat_ticks],
        pos=ps[short_flat_ticks],
        profit=short_profit,
        size=[12.,]*len(short_flat_ticks)
    ))
    if len(long_ticks) != len(long_flat_ticks):
        long_ticks = long_ticks[:-1]
    if len(short_ticks) != len(short_flat_ticks):
        short_ticks = short_ticks[:-1]

    long_segment_source = ColumnDataSource(dict(
        index=long_ticks,
        price=close[long_ticks],
        flat_index=long_flat_ticks,
        flat_price=close[long_flat_ticks],
    ))
    short_segment_source = ColumnDataSource(dict(
        index=short_ticks,
        price=close[short_ticks],
        flat_index=short_flat_ticks,
        flat_price=close[short_flat_ticks],
    ))

    return long_source, short_source, long_flat_source, short_flat_source, long_segment_source, short_segment_source
