"""声明式 primitives：用注册的 JS 回调拼出 ISeriesPrimitive / IPanePrimitive。

覆盖的 API：
- AbstractChart.register_js_callback（draw / drawBackground / autoscaleInfo /
  hitTest / attached / detached / updateAllViews，以及轴视图的 coordinate / text /
  textColor / backColor / visible / tickVisible）
- AbstractChart.create_series_primitive -> SeriesPrimitive
  （paneViews / priceAxisPaneViews / timeAxisPaneViews / priceAxisViews /
   timeAxisViews / autoscaleInfo / hitTest / attached / detached / updateAllViews
   + attach_to / apply_options / options / request_update / detach_from）
- AbstractChart.create_pane_primitive -> PanePrimitive（attach_to / detach_from）
- chart.legend(True)：打开图例（默认关闭），显示 OHLC 区块与序列标签行

注意：`options()` 是 readback，需要真实窗口；因此 `main()` 先 `show(block=False)`，
读取 spec 后再 `show(block=True)` 阻塞显示。

运行：
    python examples/11_api_tour/10_primitives.py
"""
import numpy as np
import pandas as pd

from pylightcharts import Chart


def make_data(rows: int = 300) -> pd.DataFrame:
    """自包含的合成 OHLCV，避免依赖外部 csv。"""
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.standard_normal(rows))
    return pd.DataFrame({
        'time': pd.date_range('2023-01-01', periods=rows, freq='D'),
        'open': close + rng.normal(0, 0.4, rows),
        'high': close + rng.uniform(0.3, 2.0, rows),
        'low': close - rng.uniform(0.3, 2.0, rows),
        'close': close,
        'volume': rng.integers(1_000, 50_000, rows),
    })


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    df = make_data()
    # 先建一条与 close 同名的折线，chart.set() 会自动把该列灌进去
    series = chart.create_line(name='close', color='#FF9800', width=2)
    # 灌入主 K 线与成交量
    chart.set(df)
    # legend(True)：打开图例（默认关闭），叠加序列才会有标签行
    chart.legend(True)

    # ------------------------------------------------------------------
    # 1) 注册 JS 回调（primitive 的钩子在渲染帧里同步执行，绝不回调 Python）
    # ------------------------------------------------------------------
    # pane 视图的 draw：在 target.useBitmapCoordinateSpace 里画一条水平虚线
    chart.register_js_callback(
        'prim_draw',
        ['target', 'priceConverter', 'view', 'prim'],
        """
        target.useBitmapCoordinateSpace(scope => {
            const ctx = scope.context;
            const y = scope.bitmapSize.height / 2;
            ctx.save();
            ctx.strokeStyle = 'rgba(41, 98, 255, 0.9)';
            ctx.lineWidth = 2 * scope.horizontalPixelRatio;
            ctx.setLineDash([6 * scope.horizontalPixelRatio, 4 * scope.horizontalPixelRatio]);
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(scope.bitmapSize.width, y);
            ctx.stroke();
            ctx.restore();
        });
        """)

    # pane 视图的 drawBackground：在左侧铺一条半透明色带
    chart.register_js_callback(
        'prim_draw_bg',
        ['target', 'priceConverter', 'view', 'prim'],
        """
        target.useBitmapCoordinateSpace(scope => {
            const ctx = scope.context;
            ctx.save();
            ctx.fillStyle = 'rgba(41, 98, 255, 0.06)';
            ctx.fillRect(0, 0, scope.bitmapSize.width * 0.25, scope.bitmapSize.height);
            ctx.restore();
        });
        """)

    # autoscaleInfo：读系列数据，把价格区间上下各放宽 5%
    chart.register_js_callback(
        'prim_autoscale',
        ['startTimePoint', 'endTimePoint', 'prim'],
        """
        const data = prim.series ? prim.series.data() : [];
        let lo = Infinity;
        let hi = -Infinity;
        for (const item of data) {
            const value = item.close !== undefined ? item.close : item.value;
            if (value === undefined || value === null) continue;
            if (value < lo) lo = value;
            if (value > hi) hi = value;
        }
        if (!isFinite(lo) || !isFinite(hi)) return null;
        const pad = (hi - lo) * 0.05;
        return { priceRange: { minValue: lo - pad, maxValue: hi + pad } };
        """)

    # hitTest：返回 PrimitiveHoveredItem（这里简化成整块都算命中）
    chart.register_js_callback(
        'prim_hit',
        ['x', 'y', 'prim'],
        "return { externalId: 'api-tour-hline', zOrder: 'top', cursorStyle: 'pointer' };")

    # attached / detached：挂载、卸载时的生命周期回调
    chart.register_js_callback(
        'prim_attached', ['param', 'prim'],
        "window.__apiTourPrimitiveAttached = true;")
    chart.register_js_callback(
        'prim_detached', ['prim'],
        "window.__apiTourPrimitiveAttached = false;")

    # updateAllViews：视图需要重算时被调用
    chart.register_js_callback('prim_update_views', [
                               'prim'], "return undefined;")

    # 轴视图回调：coordinate 返回坐标、text 返回标签，外加颜色 / 可见性
    chart.register_js_callback(
        'axis_coord', ['prim'],
        "return prim.series ? prim.series.priceToCoordinate(100) : 0;")
    chart.register_js_callback('axis_text', ['prim'], "return '100.00';")
    # 时间轴视图单独一组回调：x 取时间轴宽度中点，文字用 'T'
    chart.register_js_callback(
        'time_axis_coord', ['prim'],
        "return prim.chart ? prim.chart.timeScale().width() / 2 : 0;")
    chart.register_js_callback('time_axis_text', ['prim'], "return 'T';")

    chart.register_js_callback(
        'axis_text_color', ['prim'], "return '#FFFFFF';")
    chart.register_js_callback(
        'axis_back_color', ['prim'], "return '#2962FF';")
    chart.register_js_callback('axis_visible', ['prim'], "return true;")
    chart.register_js_callback('axis_tick_visible', ['prim'], "return true;")

    # pane primitive 的 draw / drawBackground：不依赖 series，只画右下角方框
    chart.register_js_callback(
        'pane_draw',
        ['target', 'priceConverter', 'view', 'prim'],
        """
        target.useBitmapCoordinateSpace(scope => {
            const ctx = scope.context;
            const w = 70 * scope.horizontalPixelRatio;
            const h = w * 0.6;
            ctx.save();
            ctx.strokeStyle = 'rgba(255, 152, 0, 0.9)';
            ctx.lineWidth = 2 * scope.horizontalPixelRatio;
            ctx.strokeRect(scope.bitmapSize.width - w - 8, 8, w, h);
            ctx.restore();
        });
        """)
    chart.register_js_callback(
        'pane_draw_bg',
        ['target', 'priceConverter', 'view', 'prim'],
        """
        target.useBitmapCoordinateSpace(scope => {
            const ctx = scope.context;
            ctx.save();
            ctx.fillStyle = 'rgba(255, 152, 0, 0.05)';
            ctx.fillRect(0, 0, scope.bitmapSize.width, scope.bitmapSize.height * 0.5);
            ctx.restore();
        });
        """)

    # ------------------------------------------------------------------
    # 2) create_series_primitive：覆盖全部 spec 字段
    # ------------------------------------------------------------------
    primitive = chart.create_series_primitive({
        # 主 pane 视图：背景 pass + 前景 pass，各带 zOrder
        'paneViews': [
            {'zOrder': 'bottom', 'drawBackground': 'prim_draw_bg'},
            {'zOrder': 'top', 'draw': 'prim_draw'},
        ],
        # 价格轴 / 时间轴上的 pane 视图（复用同一批 draw 回调）
        'priceAxisPaneViews': [{'zOrder': 'top', 'draw': 'prim_draw'}],
        'timeAxisPaneViews': [{'zOrder': 'normal', 'draw': 'prim_draw'}],
        # 价格轴 / 时间轴刻度视图：每个字段都指向一个已注册回调
        'priceAxisViews': [{
            'coordinate': 'axis_coord', 'text': 'axis_text',
            'textColor': 'axis_text_color', 'backColor': 'axis_back_color',
            'visible': 'axis_visible', 'tickVisible': 'axis_tick_visible',
        }],
        'timeAxisViews': [{
            'coordinate': 'time_axis_coord', 'text': 'time_axis_text',
            'textColor': 'axis_text_color', 'backColor': 'axis_back_color',
            'visible': 'axis_visible', 'tickVisible': 'axis_tick_visible',
        }],
        # 其余钩子
        'autoscaleInfo': 'prim_autoscale',
        'hitTest': 'prim_hit',
        'attached': 'prim_attached',
        'detached': 'prim_detached',
        'updateAllViews': 'prim_update_views',
    })
    # 挂到折线系列上（series.attachPrimitive）
    primitive.attach_to(series)
    # 浅合并更新 spec（JS 侧 applyOptions）
    primitive.apply_options(hitTest='prim_hit')
    # 请求重绘（primitive.requestUpdate）
    primitive.request_update()
    # 从系列卸载，再挂回，保证示例窗口里仍然可见
    primitive.detach_from(series)
    primitive.attach_to(series)

    # ------------------------------------------------------------------
    # 3) create_pane_primitive：挂在 pane 0 上
    # ------------------------------------------------------------------
    pane_primitive = chart.create_pane_primitive({
        'paneViews': [
            {'zOrder': 'bottom', 'drawBackground': 'pane_draw_bg'},
            {'zOrder': 'top', 'draw': 'pane_draw'},
        ],
        'hitTest': 'prim_hit',
        'attached': 'prim_attached',
        'detached': 'prim_detached',
        'updateAllViews': 'prim_update_views',
    })
    # 挂到 pane 0 / 从 pane 0 卸载，最后再挂回保持可见
    pane_primitive.attach_to(chart, 0)
    pane_primitive.detach_from(chart, 0)
    pane_primitive.attach_to(chart, 0)

    # 句柄暂存到 chart 上，供 report 阶段读回 spec 后再卸载
    chart._tour_primitives = {'series': primitive, 'pane': pane_primitive}


def report(chart) -> None:
    """读取 primitive 状态 —— options() 是 readback，需要已加载的真实窗口。"""
    primitives = chart._tour_primitives
    # options()：读回 SeriesPrimitive 当前的 spec
    print('series primitive spec keys:', sorted(
        primitives['series'].options().keys()))
    # options()：读回 PanePrimitive 当前的 spec
    print('pane primitive spec keys  :', sorted(
        primitives['pane'].options().keys()))


def main() -> None:
    chart = Chart(width=1100, height=750,
                  title='pylightcharts - declarative primitives')
    build(chart)
    # 先非阻塞显示，待窗口加载完成后再读回 primitive 的 spec
    chart.show(block=False)
    report(chart)
    # 继续阻塞，直到用户关闭窗口
    chart.show(block=True)


if __name__ == '__main__':
    main()
