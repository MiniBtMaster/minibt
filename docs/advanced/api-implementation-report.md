# Lightweight Charts v5.2 API 复现报告

> 引擎：TradingView Lightweight Charts™ **v5.2.1**（内嵌于 `pylightcharts/js/lightweight-charts.js`）。
> 上游类型声明：`jslib/node_modules/lightweight-charts/dist/typings.d.ts`。
> 覆盖率工具：`scripts/check_api_coverage.py`（基线 `scripts/api_coverage_baseline.json`）。
> 统计口径：按 `typings.d.ts` 中 15 个关键接口的成员计数；"options / 类型别名"通过 `**options` 全透传，单独说明。

## 1. 结论

| 指标 | 结果 |
|---|---|
| 接口方法覆盖率 | **150 / 150 = 100.0%** |
| 枚举 | 11 / 11（`Lib.enums` 导出 + `pylightcharts.constants` 镜像） |
| 顶层函数/常量 | `createChart` `createChartEx` `createOptionsChart` `createYieldCurveChart` `createSeriesMarkers` `createUpDownMarkers` `createTextWatermark` `createImageWatermark` `version` `isBusinessDay` `isUTCTimestamp` `defaultHorzScaleBehavior` `customSeriesDefaultOptions` 全部可达 |
| options / 类型别名（≈120） | 100% 透传（`apply_options(**kwargs)`、`series.apply_options`、`add_series(**options)` 等，snake_case 自动转 camelCase） |
| 函数式 options | 通过「注册 JS 回调 + 按路径注入」实现（`register_js_callback` / `set_option_callback` / `set_tick_mark_formatter` / `set_price_format_formatter` / `set_autoscale_info_provider`） |
| v5 插件生命周期 | markers / up-down / text watermark / image watermark 全生命周期可用 |
| Primitive | `ISeriesPrimitive` / `IPanePrimitive` 可由 Python 声明式构造（paneViews/axisViews/autoscaleInfo/hitTest/生命周期） |
| 自定义系列 | `ICustomSeriesPaneView` / `ICustomSeriesPaneRenderer` 全成员（含 `hitTest`、`conflationReducer`、`destroy`） |
| 自定义水平轴 | `IHorzScaleBehavior` 全部 13 个方法 |

> **本报告对应源码状态**：`tests/test_api_coverage.py` 44/44 通过；`pylightcharts/js/bundle.js` 与
> `jslib/dist/bundle.js` md5 一致；Edge 无头渲染出有效 PNG。

## 2. 逐接口覆盖明细

下表由 `scripts/check_api_coverage.py` 的 manifest 生成，"实现位置"列给出对应的 Python 方法或
JS 侧对象（`Lib.*`）。

### `IChartApiBase`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `remove` | ✅ | AbstractChart.remove |
| `resize` | ✅ | AbstractChart.resize |
| `addCustomSeries` | ✅ | AbstractChart.add_custom_series |
| `addSeries` | ✅ | AbstractChart.add_series |
| `removeSeries` | ✅ | *.delete |
| `subscribeClick` | ✅ | Events.click |
| `unsubscribeClick` | ✅ | JSEmitter.unsubscribe |
| `subscribeDblClick` | ✅ | Events.dblclick |
| `unsubscribeDblClick` | ✅ | JSEmitter.unsubscribe |
| `subscribeCrosshairMove` | ✅ | Events.crosshair_move |
| `unsubscribeCrosshairMove` | ✅ | JSEmitter.unsubscribe |
| `priceScale` | ✅ | AbstractChart.get_price_scale |
| `timeScale` | ✅ | AbstractChart.time_scale* |
| `applyOptions` | ✅ | AbstractChart.apply_options |
| `options` | ✅ | AbstractChart.chart_options |
| `takeScreenshot` | ✅ | AbstractChart.screenshot |
| `addPane` | ✅ | AbstractChart.add_pane |
| `panes` | ✅ | AbstractChart.pane_* |
| `removePane` | ✅ | AbstractChart.remove_pane |
| `swapPanes` | ✅ | AbstractChart.swap_panes |
| `autoSizeActive` | ✅ | AbstractChart.auto_size_active |
| `chartElement` | ✅ | AbstractChart.chart_element |
| `setCrosshairPosition` | ✅ | AbstractChart.set_crosshair_position |
| `clearCrosshairPosition` | ✅ | AbstractChart.clear_crosshair_position |
| `paneSize` | ✅ | AbstractChart.pane_size |
| `horzBehaviour` | ✅ | AbstractChart.horz_behavior |

### `ISeriesApi`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `priceFormatter` | ✅ | SeriesCommon.price_formatter |
| `priceToCoordinate` | ✅ | SeriesCommon.price_to_coordinate |
| `coordinateToPrice` | ✅ | SeriesCommon.coordinate_to_price |
| `barsInLogicalRange` | ✅ | SeriesCommon.bars_in_logical_range |
| `applyOptions` | ✅ | SeriesCommon.apply_options |
| `options` | ✅ | SeriesCommon.options |
| `priceScale` | ✅ | SeriesCommon.price_scale_options |
| `setData` | ✅ | SeriesCommon.set |
| `update` | ✅ | SeriesCommon.update |
| `pop` | ✅ | SeriesCommon.pop |
| `dataByIndex` | ✅ | SeriesCommon.data_by_index |
| `data` | ✅ | SeriesCommon.data_points |
| `subscribeDataChanged` | ✅ | SeriesCommon.subscribe_data_changed |
| `unsubscribeDataChanged` | ✅ | SeriesCommon.unsubscribe_data_changed |
| `createPriceLine` | ✅ | SeriesCommon.create_price_line |
| `removePriceLine` | ✅ | PriceLine.remove |
| `priceLines` | ✅ | SeriesCommon.js_price_lines |
| `seriesType` | ✅ | SeriesCommon.series_type |
| `lastValueData` | ✅ | SeriesCommon.last_value_data |
| `attachPrimitive` | ✅ | SeriesCommon.attach_primitive |
| `detachPrimitive` | ✅ | SeriesCommon.detach_primitive |
| `moveToPane` | ✅ | SeriesCommon.move_to_pane |
| `seriesOrder` | ✅ | SeriesCommon.series_order |
| `setSeriesOrder` | ✅ | SeriesCommon.set_series_order |
| `getPane` | ✅ | SeriesCommon.get_pane_index |

### `ITimeScaleApi`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `scrollPosition` | ✅ | AbstractChart.scroll_position |
| `scrollToPosition` | ✅ | AbstractChart.scroll_to_position |
| `scrollToRealTime` | ✅ | AbstractChart.scroll_to_real_time |
| `getVisibleRange` | ✅ | AbstractChart.get_visible_range |
| `setVisibleRange` | ✅ | AbstractChart.set_visible_range |
| `getVisibleLogicalRange` | ✅ | AbstractChart.get_visible_logical_range |
| `setVisibleLogicalRange` | ✅ | AbstractChart.set_visible_logical_range |
| `resetTimeScale` | ✅ | AbstractChart.reset_time_scale |
| `fitContent` | ✅ | AbstractChart.fit |
| `logicalToCoordinate` | ✅ | AbstractChart.logical_to_coordinate |
| `coordinateToLogical` | ✅ | AbstractChart.coordinate_to_logical |
| `timeToIndex` | ✅ | AbstractChart.time_to_index |
| `timeToCoordinate` | ✅ | AbstractChart.time_to_coordinate |
| `coordinateToTime` | ✅ | AbstractChart.coordinate_to_time |
| `width` | ✅ | AbstractChart.time_scale_width |
| `height` | ✅ | AbstractChart.time_scale_height |
| `subscribeVisibleTimeRangeChange` | ✅ | Events.visible_time_range_change |
| `unsubscribeVisibleTimeRangeChange` | ✅ | JSEmitter.unsubscribe |
| `subscribeVisibleLogicalRangeChange` | ✅ | Events.range_change |
| `unsubscribeVisibleLogicalRangeChange` | ✅ | JSEmitter.unsubscribe |
| `subscribeSizeChange` | ✅ | Events.size_change |
| `unsubscribeSizeChange` | ✅ | JSEmitter.unsubscribe |
| `applyOptions` | ✅ | AbstractChart.time_scale_options |
| `options` | ✅ | AbstractChart.time_scale_settings |

### `IPriceScaleApi`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `applyOptions` | ✅ | PriceScale.apply_options |
| `options` | ✅ | PriceScale.options |
| `width` | ✅ | PriceScale.width |
| `setVisibleRange` | ✅ | PriceScale.set_visible_range |
| `getVisibleRange` | ✅ | PriceScale.get_visible_range |
| `setAutoScale` | ✅ | PriceScale.set_auto_scale |

### `IPaneApi`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `getHeight` | ✅ | AbstractChart.pane_height |
| `setHeight` | ✅ | AbstractChart.set_pane_height |
| `moveTo` | ✅ | AbstractChart.pane_move_to |
| `paneIndex` | ✅ | AbstractChart.pane_* |
| `getSeries` | ✅ | AbstractChart.pane_series_handle |
| `getHTMLElement` | ✅ | AbstractChart.pane_get_htmlelement |
| `attachPrimitive` | ✅ | AbstractChart.attach_pane_primitive |
| `detachPrimitive` | ✅ | AbstractChart.detach_pane_primitive |
| `priceScale` | ✅ | AbstractChart.pane_price_scale |
| `setPreserveEmptyPane` | ✅ | AbstractChart.set_pane_preserve_empty |
| `preserveEmptyPane` | ✅ | AbstractChart.pane_preserve_empty |
| `getStretchFactor` | ✅ | AbstractChart.pane_stretch_factor |
| `setStretchFactor` | ✅ | AbstractChart.set_pane_stretch |
| `addCustomSeries` | ✅ | AbstractChart.pane_add_custom_series |
| `addSeries` | ✅ | AbstractChart.pane_add_series |

### `IPriceLine`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `applyOptions` | ✅ | PriceLine.apply_options |
| `options` | ✅ | PriceLine.options |

### `ISeriesMarkersPluginApi`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `setMarkers` | ✅ | SeriesMarkersPlugin.set_markers |
| `markers` | ✅ | SeriesMarkersPlugin.markers |
| `detach` | ✅ | SeriesMarkersPlugin.detach |

### `ISeriesUpDownMarkerPluginApi`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `applyOptions` | ✅ | UpDownMarkersPlugin.apply_options |
| `setData` | ✅ | UpDownMarkersPlugin.set_data |
| `update` | ✅ | UpDownMarkersPlugin.update |
| `markers` | ✅ | UpDownMarkersPlugin.markers |
| `setMarkers` | ✅ | UpDownMarkersPlugin.set_markers |
| `clearMarkers` | ✅ | UpDownMarkersPlugin.clear_markers |

### `ITextWatermarkPluginApi`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `applyOptions` | ✅ | TextWatermarkPlugin.apply_options |
| `detach` | ✅ | TextWatermarkPlugin.detach |
| `getPane` | ✅ | TextWatermarkPlugin.get_pane |

### `IImageWatermarkPluginApi`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `applyOptions` | ✅ | ImageWatermarkPlugin.apply_options |
| `detach` | ✅ | ImageWatermarkPlugin.detach |
| `getPane` | ✅ | ImageWatermarkPlugin.get_pane |

### `ISeriesPrimitiveBase`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `updateAllViews` | ✅ | CallbackPrimitive.updateAllViews |
| `priceAxisViews` | ✅ | CallbackPrimitive.priceAxisViews |
| `timeAxisViews` | ✅ | CallbackPrimitive.timeAxisViews |
| `paneViews` | ✅ | CallbackPrimitive.paneViews |
| `priceAxisPaneViews` | ✅ | CallbackPrimitive.priceAxisPaneViews |
| `timeAxisPaneViews` | ✅ | CallbackPrimitive.timeAxisPaneViews |
| `autoscaleInfo` | ✅ | CallbackPrimitive.autoscaleInfo |
| `attached` | ✅ | CallbackPrimitive.attached |
| `detached` | ✅ | CallbackPrimitive.detached |
| `hitTest` | ✅ | CallbackPrimitive.hitTest |

### `IPanePrimitiveBase`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `updateAllViews` | ✅ | CallbackPanePrimitive.updateAllViews |
| `paneViews` | ✅ | CallbackPanePrimitive.paneViews |
| `attached` | ✅ | CallbackPanePrimitive.attached |
| `detached` | ✅ | CallbackPanePrimitive.detached |
| `hitTest` | ✅ | CallbackPanePrimitive.hitTest |

### `ICustomSeriesPaneView`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `renderer` | ✅ | CustomSeriesPaneView |
| `update` | ✅ | CustomSeriesPaneView |
| `priceValueBuilder` | ✅ | SpecCustomSeriesPaneView.priceValueBuilder |
| `isWhitespace` | ✅ | SpecCustomSeriesPaneView.isWhitespace |
| `defaultOptions` | ✅ | SpecCustomSeriesPaneView.defaultOptions |
| `destroy` | ✅ | SpecCustomSeriesPaneView.destroy |
| `conflationReducer` | ✅ | SpecCustomSeriesPaneView.conflationReducer |

### `ICustomSeriesPaneRenderer`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `draw` | ✅ | CustomSeriesRenderer |
| `hitTest` | ✅ | CallbackCustomSeriesRenderer.hitTest |

### `IHorzScaleBehavior`

| 成员 | 状态 | 实现位置 |
|---|---|---|
| `options` | ✅ | registerHorzScaleBehaviorSpec.options |
| `setOptions` | ✅ | registerHorzScaleBehaviorSpec.setOptions |
| `preprocessData` | ✅ | registerHorzScaleBehaviorSpec.preprocessData |
| `convertHorzItemToInternal` | ✅ | registerHorzScaleBehaviorSpec.convertHorzItemToInternal |
| `createConverterToInternalObj` | ✅ | registerHorzScaleBehaviorSpec.createConverterToInternalObj |
| `key` | ✅ | registerHorzScaleBehaviorSpec.key |
| `cacheKey` | ✅ | registerHorzScaleBehaviorSpec.cacheKey |
| `updateFormatter` | ✅ | registerHorzScaleBehaviorSpec.updateFormatter |
| `formatHorzItem` | ✅ | registerHorzScaleBehaviorSpec.formatHorzItem |
| `formatTickmark` | ✅ | registerHorzScaleBehaviorSpec.formatTickmark |
| `maxTickMarkWeight` | ✅ | registerHorzScaleBehaviorSpec.maxTickMarkWeight |
| `fillWeightsForPoints` | ✅ | registerHorzScaleBehaviorSpec.fillWeightsForPoints |
| `shouldResetTickmarkLabels` | ✅ | registerHorzScaleBehaviorSpec.shouldResetTickmarkLabels |

**合计：150 / 150 = 100.0%**

---

## 3. 枚举与常量

上游把枚举放在模块作用域，泛型 RPC 无法访问。`jslib/src/general/exports.ts` 把它们挂到 `Lib`
全局，`pylightcharts/constants.py` 提供逐值一致的 Python 镜像：

| 枚举 | Python | 枚举 | Python |
|---|---|---|---|
| `ColorType` | `constants.ColorType` | `PriceLineSource` | `constants.PriceLineSource` |
| `CrosshairMode` | `constants.CrosshairMode` | `PriceScaleMode` | `constants.PriceScaleMode` |
| `LastPriceAnimationMode` | `constants.LastPriceAnimationMode` | `TickMarkType` | `constants.TickMarkType` |
| `LineStyle` | `constants.LineStyle` | `TrackingModeExitMode` | `constants.TrackingModeExitMode` |
| `LineType` | `constants.LineType` | `MarkerSign` | `constants.MarkerSign`（上游 `const enum`，运行时擦除） |
| `MismatchDirection` | `constants.MismatchDirection` | `SeriesType` | `constants.SeriesType` |

`constants.verify(chart)` 可把本地值与引擎逐值对拍。

## 4. 顶层函数 / 常量

`Lib.version()` / `Lib.isBusinessDay()` / `Lib.isUTCTimestamp()` / `Lib.defaultHorzScaleBehavior` /
`Lib.customSeriesDefaultOptions` 以及全部 `create*` 工厂均由 `exports.ts` 导出。
`AbstractChart.version()` 读取版本；`createChartEx` 的 Python 入口是自定义水平轴（见 §9）。

## 5. 函数式 options（回调）明细

| 上游 option | Python 入口 |
|---|---|
| `localization.priceFormatter` | `chart.set_price_formatter(...)`（声明式）或 `set_price_formatter_callback(name)` |
| `localization.timeFormatter` | `chart.set_time_formatter(...)` 或 `set_time_formatter_callback(name)` |
| `timeScale.tickMarkFormatter` | `chart.set_tick_mark_formatter(name)` |
| `series.priceFormat.formatter` | `series.set_price_format_formatter(name)`（merge-safe） |
| `series.autoscaleInfoProvider` | `series.set_autoscale_info_provider(name)` |
| 任意 `obj.method({path: fn})` | `chart.set_option_callback(handle, method, path, name)` |

回调用 `chart.register_js_callback(name, params, body)` 注册（`new Function(...params, body)`）。
**回调在 JS 侧同步执行，绝不回调 Python**（渲染帧不可阻塞）。

## 6. v5 插件生命周期

| 插件 | Python 工厂 | 类 |
|---|---|---|
| series markers | `series.markers_plugin()` | `SeriesMarkersPlugin`（`set_markers` `markers` `apply_options` `detach` `get_series`） |
| up/down markers | `series.up_down_markers_plugin()` | `UpDownMarkersPlugin`（`set_data` `update` `markers` `set_markers` `clear_markers` `apply_options` `detach` `get_series`） |
| text watermark | `chart.text_watermark_plugin()` | `TextWatermarkPlugin`（`apply_options` `detach` `get_pane`） |
| image watermark | `chart.image_watermark_plugin()` | `ImageWatermarkPlugin`（`apply_options` `detach` `get_pane`） |

## 7. Primitive 规格

`chart.create_series_primitive(spec)` → `SeriesPrimitive`；`chart.create_pane_primitive(spec)` → `PanePrimitive`。
spec 字段（值为已注册回调名）：

```
paneViews / priceAxisPaneViews / timeAxisPaneViews : [{ zOrder, draw, drawBackground }]
priceAxisViews / timeAxisViews                     : [{ coordinate, text, textColor, backColor, visible, tickVisible }]
autoscaleInfo / hitTest / attached / detached / updateAllViews
```

## 8. 自定义系列 paneView 规格

`chart.add_custom_series(spec={...})`：

```
rendererDraw / rendererHitTest / priceValueBuilder / isWhitespace / defaultOptions / destroy / conflationReducer
```

未提供时退回内置的「声明式 shapes 渲染器」（`shapes.rect/band/line/circle/text/polyline` + 预设）。

## 9. 自定义水平轴

```python
class MonthChart(Chart):
    _horz_scale_name = 'month'
    _horz_scale = {
        'formatTickmark': (['tickMark', 'loc'], "return 'M' + tickMark"),
        'formatHorzItem': (['item'], "return 'M' + item"),
    }
```

`AbstractChart.register_horz_scale_behavior(name, spec)` 负责把 13 个方法注册为回调并交给
`Lib.registerHorzScaleBehaviorSpec`；未提供的方法有 identity/字符串兜底。

## 10. 未实现 / 有意不同的部分

覆盖率 100% 指**接口成员**都已可用。以下几点不是"缺方法"，而是需要了解的使用约束：

1. **函数式回调不能回调 Python**：所有 `*Formatter` / `*Provider` 都是 JS 回调，逻辑必须写成 JS 片段
   （`register_js_callback`）。这是渲染时序决定的，不是缺陷。
2. **`new Function` 需要允许 `unsafe-eval`**：桌面 / Jupyter webview 默认允许；CSP 收紧的宿主请在
   `Window.preload()` 里用原生 JS 注册，再用 `set_option_callback` 注入。
3. **声明式 primitive 的绘制逻辑用 JS 回调表达**：Python 负责"画什么/何时更新"，逐帧绘制在 JS。
4. **数值轴图表（`YieldCurveChart`/`OptionsChart`）没有 K 线/成交量**：用 `add_curve`/`add_series`。
5. **`createChartEx` 不单独暴露**：等价能力通过自定义水平轴（`kind='custom:<name>'`）提供。
6. **`ISHorzScaleBehavior.shouldResetTickmarkLabels`** 为可选方法，已实现但 LWC 不总会调用。
7. **`PolygonChart` / `PolygonAPI`** 需要 Polygon.io API key，属数据接入而非 LWC API，未在此报告范围内。
8. **遗留模块 `minibt/tradingview_.py`** 与本包无关。
9. **键盘缩放只锚定"窗口中心"**：内置方向键（`ArrowUp`/`ArrowDown`）放大/缩小时
   以可视窗口中点为锚点，左右边缘同时向中间（缩小则向两边）推进，与鼠标滚轮一致。
   没有实现"锚定十字线位置 / 锚定鼠标位置"的缩放 —— 当前行为就是常用习惯；
   若以后需要，做法是取 `timeScale.coordinateToLogical(x)` 作为锚点，
   再按同一步长收放区间（记录在 `docs/advanced/deferred.md` 的
   *Keyboard navigation* 一节）。
10. **内置方向键的其它可选键位未实现**：`+`/`-` 缩放别名、鼠标滚轮方向的
    一致性校验、以及"按固定根数而非百分比步进"的模式，都记录在
    `docs/advanced/deferred.md`（同上）。
11. **波段高低点不是 LWC 自带功能**：引擎只提供"画标记"（`setMarkers` /
    `createSeriesMarkers`），没有波段识别。`pylightcharts` 补了纯函数
    `indicators.swing_points`（length 根分形）与 `chart/series.mark_swings(...)`
    （高点标最高价、低点标最低价）；ZigZag（按最小涨跌幅交替）记录在
    `docs/advanced/deferred.md`（*ZigZag-style swing detection*）。
12. **浏览器查看**：`BrowserChart` 两种模式，都是**零新依赖**（引擎 + 桥 + 样式
    内联在包里）——
    * 静态：`to_html()` / `save_html()` / `open_in_browser()`（`show()` 落盘 +
      打开），单文件 HTML，控件回调派发 `pylightcharts-callback` DOM 事件；
    * 实时：`BrowserChart(live=True)` + `pylightcharts.server.LiveServer`
      （标准库 `http.server` + Server-Sent Events），`set`/`update`/
      `apply_options` 等一边调用一边推到所有标签页，控件回调 `POST` 回 Python，
      **不写磁盘**；新标签/刷新时用 `resync`（默认开）重发一次当前内存数据。
    实时模式不支持 readback（`chart_options()`/`screenshot()`/
    `constants.verify()` 等需要同步回执，浏览器标签没有回执通道，与
    `HeadlessChart` 相同）。React 教程本身是组件架构
    （`createContext`/`useEffect` 顺序），在 Python 侧不需要 —— chart/series
    就是普通对象；SSE 方案见 `docs/advanced/deferred.md`（*A live browser <-> Python bridge*，已实现）。

## 11. 如何验证

```bash
python scripts/check_api_coverage.py            # 打印 150/150 明细
python scripts/check_api_coverage.py --check    # CI gate（覆盖率不得下降）

# 单测（断言生成的 JS / JS 侧行为）
python -m pytest tests/test_api_coverage.py

# 端到端（真实浏览器）
python tests/e2e/smoke.py
python examples/11_api_tour/01_chart_and_data.py   # 逐个可视化验证
```

`tests/test_api_coverage.py` 覆盖：枚举、查询方法、四类事件、`VerticalSpan`、pane 级建系列、
四个插件生命周期、函数式 options、primitive 工厂、自定义系列 spec、自定义水平轴。
