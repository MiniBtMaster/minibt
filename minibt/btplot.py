from __future__ import annotations
from bokeh.io import reset_output
from .utils import np, Callable, TYPE_CHECKING, Union, FILED, Literal
from bokeh.embed import file_html
from bokeh.resources import INLINE, CDN
from copy import deepcopy
import warnings
from bokeh.palettes import Category10
import os
import bokeh.colors.named as bcn
from itertools import cycle
from functools import partial
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
    LabelSet,
)
from bokeh.layouts import column
from bokeh.io import show
from bokeh.plotting import figure as _figure
from bokeh.models.glyphs import VBar
setattr(_figure, '_main_ohlc', False)
setattr(_figure, '_candles', False)
warnings.filterwarnings("ignore", category=UserWarning)
reset_output()
if TYPE_CHECKING:
    from indicators import KLine, Line, IndSeries, IndFrame
IS_JUPYTER_NOTEBOOK = 'JPY_INTERRUPT_EVENT' in os.environ

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
    fig.add_tools(HoverTool(
        point_policy='follow_mouse',
        renderers=renderers, formatters=formatters,
        tooltips=tooltips, mode='vline' if vline else 'mouse'),
    )


def new_bokeh_figure(height=300) -> Callable:
    return partial(
        _figure,
        x_axis_type='linear',
        height=height,
        sizing_mode='stretch_width',
        width_policy='max',
        tools="xpan,xwheel_zoom,box_zoom,undo,redo,reset,save",  # ,crosshair
        active_drag='xpan',
        active_scroll='xwheel_zoom')


def new_indicator_figure(new_bokeh_figure: Callable, fig_ohlc: _figure, height=80, **kwargs) -> _figure:
    height = int(height) if height and height > 10 else 80
    fig = new_bokeh_figure(height)(x_range=fig_ohlc.x_range,
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


def btplot(indicator: Union[KLine, Line, IndSeries, IndFrame],
           include: Literal["all", "last"] = "all",
           black_style: bool = False,
           open_browser: bool = False,
           plot_cwd: str = "",
           plot_name: str = "",
           save_plot: bool = False) -> None:
    """
    Like much of GUI code everywhere, this is a mess.
    """
    dtype = [_type in type(indicator).__name__ for _type in [
        "KLine", "Line", "IndSeries", "IndFrame"]]
    assert any(dtype), print(f"只支持minibt框架内置指标数据图表,指标数据格式为{type(indicator)}")
    global IS_JUPYTER_NOTEBOOK
    base_dir = indicator._base_dir
    black_color = "white" if black_style else "black"
    white_color = "black" if black_style else "white"
    COLORS = [bcn.tomato, bcn.lime]
    inc_cmap = factor_cmap('inc', COLORS, ['0', '1'])
    new_colors = {'bear': bcn.tomato, 'bull': bcn.lime}
    BAR_WIDTH = .8  # K宽度
    NBSP = '\N{NBSP}' * 4
    lines_setting = dict(line_dash='solid', line_width=1.3)
    with open(f'{base_dir}/strategy/autoscale_cb.js', encoding='utf-8') as _f:
        _AUTOSCALE_JS_CALLBACK = _f.read()
    indicators: list[Union[KLine, Line, IndSeries, IndFrame]] = []
    is_kline = dtype[0]
    df = None
    if is_kline:
        df = indicator
    else:
        indicators.append(indicator)
    cond = True
    if indicators:
        while cond or len(indicators) < 100:
            try:
                if "KLine" in type(indicators[-1]._dataset.source_object).__name__:
                    df = indicators[-1]._dataset.source_object
                    break
                else:
                    indicators.append(
                        indicators[-1]._dataset.source_object)
            except:
                cond = False

        if include == "last":
            indicators = indicators[:1]

    if df is None:
        print("只支持由KLine创建的指标显示")
        return

    df_columns = df.columns
    # 检查是否为OHLCV格式
    is_ohlcv = all(col in df_columns for col in [
                   'open', 'high', 'low', 'close'])
    if not is_ohlcv:
        print("数据不符合OHLC格式")
        return
    is_datetime = "datetime" in df_columns
    is_volume = "volume" in df_columns
    _df = df.copy()[FILED.ALL]
    index = _df.index
    pad = (index[-1] - index[0]) / 20
    if "volume" in df_columns:
        _df['volume5'] = _df.volume.rolling(5).mean()
        _df['volume10'] = _df.volume.rolling(10).mean()
    _df["inc"] = (_df.close >=
                  _df.open).values.astype(np.uint8).astype(str)
    _df["Low"] = _df[['low', 'high']].min(1)
    _df["High"] = _df[['low', 'high']].max(1)
    CDS = ColumnDataSource(_df)
    #
    # K线图
    fig_ohlc: _figure = new_bokeh_figure(df.height)(
        x_range=Range1d(index[0], index[-1],
                        min_interval=10,
                        bounds=(index[0] - pad,
                                index[-1] + pad)) if index.size > 1 else None)
    fig_ohlc.css_classes = ["candle-chart"]
    _colors = df.candle_style
    if _colors:
        _COLORS = list(_colors.values())
        inc_cmap = factor_cmap('inc', _COLORS, ['0', '1'])
    # 上下影线
    fig_ohlc.segment('index', 'high', 'index', 'low',
                     source=CDS, color=black_color)
    # # 实体线
    ohlc_bars = fig_ohlc.vbar('index', BAR_WIDTH, 'open', 'close', source=CDS,
                              line_color=black_color, fill_color=inc_cmap)
    # 提示格式
    ohlc_tooltips = [
        ('x, y', NBSP.join(('$index',
                            '$y{0,0.0[0000]}'))),
        ('OHLC', NBSP.join(('@open{0,0.0[0000]}',
                            '@high{0,0.0[0000]}',
                            '@low{0,0.0[0000]}',
                            '@close{0,0.0[0000]}'))),
    ]
    if is_volume:
        ohlc_tooltips.append(('Volume', '@volume{0,0}'))

    spanstyle = df.span_style
    for ohlc_span in spanstyle:
        fig_ohlc.add_layout(Span(**ohlc_span))

    indicator_figs = []
    indicator_h: list[str] = []
    indicator_l: list[str] = []
    for ind in indicators:
        plot_id, isplot, name, lines, _lines, ind_name, is_overlay, category, indicator, doubles, plotinfo, span, _signal = ind._get_plot_datas(
            ind.ind_name)
        ind_name = ind.ind_name
        indicator_candles_index = []
        ohlc_colors = colorgen()
        ic = 0
        lineinfo: dict = plotinfo.get('linestyle', {})
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
                            new_bokeh_figure, fig_ohlc, plotinfo.get('height', 150))
                        indicator_figs.append(fig)
                        _mulit_ind = len(
                            indicator[ids].shape) > 1
                        CDS.add(
                            np.max(indicator[ids][:, np.arange(len(isplot[ids]))[isplot[ids]]], axis=1) if _mulit_ind else indicator[ids], f"{legend_label}_h")
                        CDS.add(
                            np.min(indicator[ids][:, np.arange(len(isplot[ids]))[isplot[ids]]], axis=1) if _mulit_ind else indicator[ids], f"{legend_label}_l")
                        indicator_h.append(f"{legend_label}_h")
                        indicator_l.append(f"{legend_label}_l")
                        ic += 1
                    _doubles_fig.append(fig)

                    if not is_candles:
                        if_vbar = False
                        for j in range(len(isplot[ids])):
                            if isplot[ids][j]:
                                _lines_name = _lines[ids][j]
                                ind = indicator[ids][:, j]
                                color = next(colors)
                                source_name = lines[ids][j]
                                if ind.dtype == bool:
                                    ind = ind.astype(
                                        np.float64)
                                CDS.add(ind, source_name)
                                tooltips.append(
                                    f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                                _lineinfo = deepcopy(
                                    lines_setting)
                                if _lines_name in lineinfo:
                                    _lineinfo = {
                                        **_lineinfo, **lineinfo[_lines_name]}
                                if _lineinfo.get("line_color", None) is None:
                                    _lineinfo.update(
                                        dict(line_color=color))
                                if "price_line" in _lineinfo:
                                    del _lineinfo["price_line"]
                                if "price_label" in _lineinfo:
                                    del _lineinfo["price_label"]
                                if is_overlay[ids]:
                                    fig.line(
                                        'index', source_name, source=CDS,
                                        legend_label=source_name, **_lineinfo)
                                else:
                                    if lineinfo and _lines_name in lineinfo and lineinfo[_lines_name].get('line_dash', None) == 'vbar':
                                        if_vbar = True
                                        if "zeros" not in CDS.column_names:
                                            CDS.add(
                                                [0.,]*len(ind), "zeros")
                                        _line_inc = np.where(ind > 0., 1, 0).astype(
                                            np.uint8).astype(str).tolist()
                                        CDS.add(
                                            _line_inc, f"{_lines_name}_inc")
                                        _line_inc_cmap = lineinfo[_lines_name]["line_color"]
                                        if _line_inc_cmap is None:
                                            _line_inc_cmap = factor_cmap(
                                                f"{_lines_name}_inc", COLORS, ['0', '1'])
                                        r = fig.vbar('index', BAR_WIDTH, 'zeros', source_name, source=CDS,
                                                     line_color='black', fill_color=_line_inc_cmap)
                                    else:
                                        r = fig.line(
                                            'index', source_name, source=CDS,
                                            legend_label=source_name, **_lineinfo)
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
                        if is_overlay[ids]:
                            ohlc_tooltips.append(
                                (legend_label, NBSP.join(tuple(tooltips))))
                        else:
                            set_tooltips(
                                fig, [(legend_label, NBSP.join(tooltips))], vline=True, renderers=[r])
                            fig.yaxis.axis_label = legend_label
                            fig.yaxis.axis_label_text_color = black_color
                            if fig_ohlc._main_ohlc:
                                fig.yaxis.visible = False
                            else:
                                fig.yaxis.visible = True
                            if len(lines) == 1:
                                fig.legend.glyph_width = 0
        else:
            if any(isplot):
                is_candles = category == 'candles'
                if is_candles and len(lines) < 4:
                    is_candles = False
                tooltips = []
                colors = cycle(
                    ohlc_colors if is_overlay else colorgen())
                legend_label = name  # 初始化命名的名称
                if is_overlay and not is_candles:  # 主图叠加
                    fig = fig_ohlc
                elif is_candles:  # 副图是蜡烛图
                    indicator_candles_index.append(ic)
                    assert len(lines) >= 4
                    lines = list(
                        map(lambda x: x.lower(), lines))
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
                        CDS.add(indicator[:,
                                          ie], lines[ie])
                    index = np.arange(indicator.shape[0])
                    pad = (index[-1] - index[0]) / 20
                    fig_ohlc_ = new_indicator_figure(
                        new_bokeh_figure, fig_ohlc, plotinfo.get('height', 100))
                    fig_ohlc_.segment(
                        'index', lines[filed_index[1]], 'index', lines[filed_index[2]], source=CDS, color=black_color)
                    ohlc_bars_ = fig_ohlc_.vbar('index', BAR_WIDTH, lines[filed_index[0]], lines[filed_index[3]], source=CDS,
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
                                CDS.add(ind,
                                        source_name)
                                tooltips.append(
                                    f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                                _lineinfo = deepcopy(lines_setting)
                                if _lines_name in lineinfo:
                                    _lineinfo = {
                                        **_lineinfo, **lineinfo[_lines_name]}
                                if _lineinfo.get("line_color", None) is None:
                                    _lineinfo.update(
                                        dict(line_color=color))
                                if "price_line" in _lineinfo:
                                    del _lineinfo["price_line"]
                                if "price_label" in _lineinfo:
                                    del _lineinfo["price_label"]
                                fig_ohlc_.line(
                                    'index', source_name, source=CDS,
                                    legend_label=source_name, **_lineinfo)
                                ohlc_tooltips_.append(
                                    (_lines_name, NBSP.join(tuple(tooltips))))
                    set_tooltips(fig_ohlc_, ohlc_tooltips_,
                                 vline=True, renderers=[ohlc_bars_])
                    indicator_figs.append(fig_ohlc_)
                    ic += 1
                    _mulit_ind = len(indicator.shape) > 1
                    CDS.add(np.max(indicator[:, np.arange(len(isplot))[isplot]], axis=1) if _mulit_ind else indicator,
                            f"{legend_label}_h")
                    CDS.add(np.min(indicator[:, np.arange(len(isplot))[isplot]], axis=1) if _mulit_ind else indicator,
                            f"{legend_label}_l")
                    indicator_h.append(f"{legend_label}_h")
                    indicator_l.append(f"{legend_label}_l")

                else:
                    __fig = fig_ohlc
                    fig = new_indicator_figure(
                        new_bokeh_figure, __fig, plotinfo.get('height', 150))
                    indicator_figs.append(fig)
                    ic += 1
                    _mulit_ind = len(indicator.shape) > 1
                    CDS.add(np.max(indicator[:, np.arange(len(isplot))[isplot]], axis=1) if _mulit_ind else indicator,
                            f"{legend_label}_h")
                    CDS.add(np.min(indicator[:, np.arange(len(isplot))[isplot]], axis=1) if _mulit_ind else indicator,
                            f"{legend_label}_l")
                    indicator_h.append(f"{legend_label}_h")
                    indicator_l.append(f"{legend_label}_l")

                if not is_candles:
                    if_vbar = False
                    for j in range(len(isplot)):
                        if isplot[j]:
                            _lines_name = _lines[j]
                            ind = indicator[:, j]
                            color = next(colors)
                            source_name = lines[j]
                            if ind.dtype == bool:
                                ind = ind.astype(int)
                            CDS.add(ind,
                                    source_name)
                            tooltips.append(
                                f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                            _lineinfo = deepcopy(lines_setting)
                            if _lines_name in lineinfo:
                                _lineinfo = {
                                    **_lineinfo, **lineinfo[_lines_name]}
                            if _lineinfo.get("line_color", None) is None:
                                _lineinfo.update(
                                    dict(line_color=color))
                            if "price_line" in _lineinfo:
                                del _lineinfo["price_line"]
                            if "price_label" in _lineinfo:
                                del _lineinfo["price_label"]
                            if is_overlay:
                                fig.line(
                                    'index', source_name, source=CDS,
                                    legend_label=source_name, **_lineinfo)
                            else:
                                if lineinfo and _lines_name in lineinfo and lineinfo[_lines_name].get('line_dash', None) == 'vbar':
                                    if_vbar = True
                                    if "zeros" not in CDS.column_names:
                                        CDS.add(
                                            [0.,]*len(ind), "zeros")
                                    _line_inc = np.where(ind > 0., 1, 0).astype(
                                        np.uint8).astype(str).tolist()
                                    CDS.add(
                                        _line_inc, f"{_lines_name}_inc")
                                    _line_inc_cmap = lineinfo[_lines_name]["line_color"]
                                    if _line_inc_cmap is None:
                                        _line_inc_cmap = factor_cmap(
                                            f"{_lines_name}_inc", COLORS, ['0', '1'])
                                    r = fig.vbar('index', BAR_WIDTH, 'zeros', source_name, source=CDS,
                                                 line_color='black', fill_color=_line_inc_cmap)
                                else:
                                    r = fig.line(
                                        'index', source_name, source=CDS,
                                        legend_label=source_name, **_lineinfo)
                    else:
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

                    if is_overlay:
                        ohlc_tooltips.append(
                            (ind_name, NBSP.join(tuple(tooltips))))
                    else:
                        set_tooltips(
                            fig, [(legend_label, NBSP.join(tooltips))], vline=True, renderers=[r])
                        fig.yaxis.axis_label = ind_name
                        fig.yaxis.axis_label_text_color = black_color
                        if len(lines) == 1:
                            fig.legend.glyph_width = 0
                        if fig_ohlc._main_ohlc:
                            fig.yaxis.visible = False
                        else:
                            fig.yaxis.visible = True
        if signal_info:
            for k, v in signal_info.items():
                signalkey, signalcolor, signalmarker, signaloverlap, signalshow, signalsize, signallabel = list(
                    v.values())

                if signalshow:
                    signaldata: np.ndarray
                    islabel = isinstance(signallabel, dict)
                    if islabel:
                        label_text = signallabel.pop("text", k)
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
                    if islabel:
                        signal_source_ = ColumnDataSource(dict(
                            index=signal_index,
                            datetime=signal_datetime,
                            price=signal_price,
                            size=[float(signalsize),] *
                            len(signal_index),
                            text=[label_text] *
                            len(signal_index),  # 标签文字列表
                        ))
                    else:
                        signal_source_ = ColumnDataSource(dict(
                            index=signal_index,
                            datetime=signal_datetime,
                            price=signal_price,
                            size=[float(signalsize),] *
                            len(signal_index),
                        ))

                    r = signal_fig.scatter(x='index', y='price', source=signal_source_, fill_color=signalcolor,
                                           marker=signalmarker, line_color='black', size="size")
                    if islabel:
                        signallabel.update(
                            dict(background_fill_alpha=0.1, background_fill_color="white" if black_style else "black"))
                        labels = LabelSet(
                            x='index',
                            y='price',
                            text='text',
                            source=signal_source_,
                            **signallabel,
                        )
                        signal_fig.add_layout(labels)  # 将标签添加到图形中
                    tooltips = [(k, "@price{0.00}"),]
                    set_tooltips(signal_fig, tooltips,
                                 vline=False, renderers=[r,])
    set_tooltips(fig_ohlc, ohlc_tooltips,
                 vline=True, renderers=[ohlc_bars], if_datetime=is_datetime)
    fig_ohlc.yaxis.axis_label = f"{df.ind_name}"
    fig_ohlc.yaxis.axis_label_text_color = black_color
    custom_js_args = dict(ohlc_range=fig_ohlc.y_range, indicator_range=[indicator_figs[_ic].y_range for _ic in range(len(indicator_figs))],
                          indicator_h=indicator_h, indicator_l=indicator_l, source=CDS)
    plots: list[_figure] = [fig_ohlc]
    if is_volume:
        # 成交量
        fig_volume = new_indicator_figure(
            new_bokeh_figure, fig_ohlc, y_axis_label="volume", height=60)
        fig_volume.css_classes = ["volume-chart"]
        fig_volume.xaxis.formatter = fig_ohlc.xaxis[0].formatter
        if fig_ohlc._main_ohlc:
            fig_volume.yaxis.visible = False
        else:
            fig_volume.yaxis.visible = True
        fig_volume.xaxis.visible = True
        fig_ohlc.xaxis.visible = False  # Show only Volume's xaxis
        r_volume = fig_volume.vbar(
            'index', BAR_WIDTH, 'volume', source=CDS, color=inc_cmap)
        colors = cycle(colorgen())
        r_volume5 = fig_volume.line('index', 'volume5', source=CDS,
                                    legend_label='volume5', line_color=next(colors),
                                    line_width=1.3)
        r_volume10 = fig_volume.line('index', 'volume10', source=CDS,
                                     legend_label='volume10', line_color=next(colors),
                                     line_width=1.3)
        set_tooltips(fig_volume, [
                    ('volume', '@volume{0.00}'), ('volume5', '@volume5{0.00}'), ('volume10', '@volume10{0.00}'),], renderers=[r_volume])
        fig_volume.yaxis.formatter = NumeralTickFormatter(
            format="0 a")  # format="0"
        fig_volume.yaxis.axis_label_text_color = black_color

        custom_js_args.update(volume_range=fig_volume.y_range)
        fig_ohlc.x_range.js_on_change('end', CustomJS(args=custom_js_args,
                                                      code=_AUTOSCALE_JS_CALLBACK))
        plots.append(fig_volume)
    if indicator_figs:
        plots += indicator_figs
    layout = column(
        children=plots,
        sizing_mode='stretch_both',
        css_classes=["dynamic-column"],
        stylesheets=[panel_CUSTOM_CSS],  # 注入自定义CSS
    )

    linked_crosshair = CrosshairTool(
        dimensions='both', line_color=black_color)

    for f in plots:
        if f.legend:
            f.legend.nrows = 1
            f.legend.label_height = 6
            f.legend.visible = True
            f.legend.location = 'top_left'
            f.legend.border_line_width = 0
            f.legend.padding = 1
            f.legend.spacing = 0
            f.legend.margin = 0
            f.legend.label_text_font_size = '8pt'
            f.legend.label_text_line_height = 1.2
            f.legend.click_policy = 'hide'  # 'mute'

        f.min_border_left = 0
        f.min_border_top = 0  # 3
        f.min_border_bottom = 6
        f.min_border_right = 10
        f.outline_line_color = '#666666'

        if black_style:
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

            # 成交量图特殊处理
            if f == fig_volume:
                f.background_fill_alpha = 0.5  # 半透明效果
                f.border_fill_alpha = 0.5
        f.add_tools(linked_crosshair)
        wheelzoom_tool = next(
            wz for wz in f.tools if isinstance(wz, WheelZoomTool))
        wheelzoom_tool.maintain_focus = False
        if f._main_ohlc:
            f.yaxis.visible = False
            f.tools.visible = False

    if open_browser:
        IS_JUPYTER_NOTEBOOK = False
    INLINE.css_raw.append(panel_CUSTOM_CSS)  # 确保CSS被包含
    if IS_JUPYTER_NOTEBOOK:
        from bokeh.io import output_notebook
        notebook_handle = True
        open_browser = False
        output_notebook(INLINE)
    else:
        notebook_handle = False
        open_browser = True
    # 保存图表
    if plot_name and isinstance(plot_name, str):
        if not plot_name.endswith('.html'):
            plot_name += '_btplot.html'
    else:
        plot_name = 'btplot.html'
    plot_cwd = plot_cwd if isinstance(
        plot_cwd, str) and plot_cwd else os.path.join(base_dir, "strategy", "plots")
    if not os.path.exists(plot_cwd):
        os.makedirs(plot_cwd, exist_ok=True)
    FileName = os.path.join(plot_cwd, plot_name)
    html = file_html(layout, CDN, "Bt Plot")
    if save_plot or IS_JUPYTER_NOTEBOOK:
        with open(FileName, 'w', encoding='utf-8') as f:
            f.write(html)
    # 显示图表
    try:
        show(layout, browser=None if open_browser else 'none',
             notebook_handle=notebook_handle)
    except Exception as e:
        if IS_JUPYTER_NOTEBOOK:
            from IPython.display import display, HTML
            # 读取保存的 HTML 文件内容
            with open(FileName, 'r', encoding='utf-8') as f:
                html_content = f.read()
            # 在 Jupyter 中显示 HTML 内容
            display(HTML(html_content))
        else:
            import webbrowser
            # 在默认浏览器中打开 HTML 文件
            webbrowser.open('file://' + os.path.abspath(FileName))
