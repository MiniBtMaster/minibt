# Lightweight Charts v5.2 API 覆盖度与补齐路线图

> 对照对象：TradingView Lightweight Charts™ **v5.2.1**（`pylightcharts/js/lightweight-charts.js` 内嵌版本）。
> 上游类型声明：`jslib/node_modules/lightweight-charts/dist/typings.d.ts`（5041 行）。
> 本文盘点 `pylightcharts` 当前的**功能缺口**，并给出把 v5.2 全部公开 API 在 pylightcharts 框架内复现的分阶段计划。
>
> 结论先行：**“实例方法 + options” 覆盖面已很高（≈90%），真正的系统性缺口集中在
> ①只读查询方法的 Python 封装、②事件订阅、③v5 插件生命周期、④枚举/常量导出、
> ⑤函数式 options 回调、⑥从 Python 构造 primitive / 自定义系列。**
> 其中 ①②④ 是低成本补齐，⑤⑥ 需要新增 JS 胶水与新的 Python 协议。

---

## 1. 架构与能力边界

```
Python API  ──►  JSON / JS 桥  ──►  Lib.Handler / Lib.invoke (TS)  ──►  Lightweight Charts v5
   (pylightcharts/*.py)      (pylightcharts/js/bundle.js)          (lightweight-charts.js)
```

桥的核心是 `jslib/src/general/rpc.ts` 的**泛型 RPC**：

| 能力 | 说明 |
|---|---|
| `lookup(handle)` | 先查 registry，再按 `.` 从 `globalThis` 解析（支持数组下标） |
| `register(handle, obj)` / `unregister` | 让 Python 用字符串句柄引用活对象 |
| `resolveRefs` | 把 `{"$ref": handle}` 递归换成活对象 |
| `invoke(handle, method, args, storeAs?)` | 调用**任意可达对象的任意方法**，`storeAs` 登记返回值 |
| `applyOptions(handle, options)` | `invoke(...'applyOptions')` |

**能到达**：任意实例方法、嵌套/数组路径、`$ref` 传活对象、`storeAs` 留句柄。
**到达不了（需要新增 TS 胶水）**：

1. `new` / 构造器、模块作用域符号（**枚举**、`version`、`isBusinessDay` …）；
2. **函数参数/闭包**（所有函数式 option）；
3. 直接读**非函数属性**（`target[method]` 必须是函数）；
4. `await Promise`、活对象 round-trip 回传；
5. 纯 Python 构造 `ISeriesPrimitive` / `ICustomSeriesPaneView` / `IHorzScaleBehavior` 的方法体。

因此“补齐 API”分两类：
**(A) 只需 Python 封装**（实例方法/查询/事件）与 **(B) 需新增 TS↔JSON 协议**（函数/primitive/behavior）。

---

## 2. 覆盖率总览（对照 v5.2.1）

> 口径：接口成员按 `typings.d.ts` 计数；“已封装”指有**命名 Python 方法**（泛型 `invoke_get` 可达但无封装的仍计为缺口，因为不符合“pythonic 覆盖”的目标）。

| API 组 | 成员 | 已封装 | 缺口 | 覆盖率 |
|---|---|---|---|---|
| `IChartApi(+Base)` | 26 | 23 | `options()` `chartElement()` `horzBehaviour()` | 88% |
| `ISeriesApi` | 25 | 20 | `priceFormatter()` `priceLines()` `update(historicalUpdate)` `subscribe/unsubscribeDataChanged` `getPane()`(返回对象) | 80% |
| `ITimeScaleApi` | 24 | 19 | `options()` `subscribe/unsubscribeVisibleTimeRangeChange` `subscribe/unsubscribeSizeChange` | 79% |
| `IPriceScaleApi` | 6 | 5 | `options()` | 83% |
| `IPaneApi` | 15 | 11 | `getHTMLElement()` `getSeries()`(列表) `moveTo()` `addSeries` `addCustomSeries` | 73% |
| `IPriceLine` | 2 | 2 | — | 100% |
| `ISeriesMarkersPluginApi` | 4 | 1 | `markers()` `detach()` `applyOptions()` | 25% |
| `ISeriesUpDownMarkerPluginApi` | 8 | 1 | `setData` `update` `markers` `setMarkers` `clearMarkers` `detach` `applyOptions` | 13% |
| `ITextWatermarkPluginApi` | 3 | 1 | `applyOptions()` `detach()` `getPane()` | 33% |
| `IImageWatermarkPluginApi` | 3 | 1 | 同上 | 33% |
| `ISeriesPrimitiveBase` | 10 | 0 | 全部（只能 attach 预注册 JS 对象） | ~0% |
| `IPanePrimitiveBase` | 5 | 0 | 全部 | ~0% |
| `ICustomSeriesPaneView` | 7 | 4 | `renderer` 定制 `priceValueBuilder` `hitTest` `conflationReducer` | ~57% |
| `IHorzScaleBehavior` | 12 | 0 | 全部（仅 `preload` 拼 JS） | ~0% |
| 枚举（11） | 11 | 0 | 全部（Python 靠猜整数） | 0% |
| 顶层函数/常量（12） | 12 | 7 | `createChartEx`(无 py API) `version` `isBusinessDay` `isUTCTimestamp` `defaultHorzScaleBehavior` `customSeriesDefaultOptions` | 58% |
| 类型别名 / options（≈120） | ≈120 | ≈120 | 无（`**options` 全透传 + `deepMerge`） | ≈100% |
| 数据接口（12） | 12 | 12 | 无（dict / `update_raw` 透传） | 100% |

**已知实现 Bug（必须先修）**

| 位置 | 问题 |
|---|---|
| `SeriesCommon.vertical_span` | 调用 v4 已移除的 `chart.addHistogramSeries`，v5.2 下必报错 |
| `VerticalLine.update` | 引用未定义变量 `price` |

---

## 3. 缺口清单（按类别）

### C1 只读查询方法（低成本）
- `IChartApi.options()`、`chartElement()`、`horzBehaviour()`
- `ITimeScaleApi.options()`
- `IPriceScaleApi.options()`
- `ISeriesApi.priceFormatter()`、`priceLines()`（JS 真实集合，非 Python 自记）
- `IPaneApi.getHTMLElement()`、`getSeries()`（返回序列对象列表）、`pane.addSeries/addCustomSeries`、`moveTo()`
- `ISeriesApi.getPane()` 返回 `IPaneApi` 对象（现只返回 index）

### C2 事件订阅（低成本）
- `ITimeScaleApi.subscribeVisibleTimeRangeChange` / `unsubscribe…`
- `ITimeScaleApi.subscribeSizeChange` / `unsubscribe…`
- `ISeriesApi.subscribeDataChanged` / `unsubscribe…`
- `IChartApi.subscribeDblClick` 的**扇出**（现直接调原生，多订阅者互相覆盖）
- 统一的 `unsubscribeClick/DblClick/CrosshairMove` 命名方法

### C3 v5 插件生命周期（中成本，纯封装）
- Markers：`markers()`、`detach()`、`applyOptions()`
- UpDownMarkers：`setData`、`update`、`markers`、`setMarkers`、`clearMarkers`、`detach`、`applyOptions`
- Text/Image Watermark：`applyOptions()`、`detach()`、`getPane()`

### C4 枚举 / 常量 / 函数导出（低成本，需改 TS）
- 11 个枚举：`MarkerSign ColorType CrosshairMode LastPriceAnimationMode LineStyle LineType MismatchDirection PriceLineSource PriceScaleMode TickMarkType TrackingModeExitMode`
- `version()`、`isBusinessDay`、`isUTCTimestamp`、`defaultHorzScaleBehavior`、`customSeriesDefaultOptions`
- `createChartEx` 的 Python 入口

### C5 函数式 options（中成本，需 JS 回调协议）
- `localization.priceFormatter` / `timeFormatter`（当前为声明式，需支持原始函数）
- `localization.dateFormat`
- `timeScale.tickMarkFormatter`
- `series.priceFormat.formatter`（per-series）
- `series.autoscaleInfoProvider`
- `layout` 的 `CustomColorParser`

### C6 Primitive 构造（高成本，需 JS 工厂 + 新协议）
- `ISeriesPrimitiveBase`：`paneViews/priceAxisViews/timeAxisViews/priceAxisPaneViews/timeAxisPaneViews/autoscaleInfo/updateAllViews/attached/detached/hitTest`
- `IPanePrimitiveBase`：`paneViews/updateAllViews/attached/detached/hitTest`
- `ISeriesPrimitiveAxisView`、`PrimitiveHoveredItem`

### C7 自定义系列 paneView（中高成本）
- `ICustomSeriesPaneView.renderer()` 自定义绘制
- `priceValueBuilder()`、`isWhitespace()`、`defaultOptions()`、`destroy()`、`conflationReducer()`
- `ICustomSeriesPaneRenderer.hitTest()`

### C8 自定义水平轴行为（高成本，小众）
- `IHorzScaleBehavior` 全 12 个方法的 Python 注册 API

### C9 数据细节 / 顶层导出（低成本）
- `ISeriesApi.update(bar, historicalUpdate)`
- whitespace data 的显式支持
- `pylightcharts.__init__` 顶层导出 `HeadlessChart/Table/ToolBox/TopBar/PolygonAPI/drawings/各 Series 类/constants`

---

## 4. 实施计划（分阶段）

### Phase 0 — 地基（0.5 周）
**目标**：为后续阶段提供稳定协议，且不改变现有行为。

| 步骤 | 文件 | 内容 |
|---|---|---|
| 0.1 | `jslib/src/index.ts` | re-export LWC 的枚举、`version`、`isBusinessDay`、`isUTCTimestamp`、`defaultHorzScaleBehavior`、`customSeriesDefaultOptions`；压缩进 `Lib.enums` / `Lib.fn` |
| 0.2 | `pylightcharts/constants.py`（新增） | Python 侧枚举常量（从 `Lib.enums` 读取 + 本地兜底），替换 `util.as_enum` / `marker_shape` 的“猜整数” |
| 0.3 | `jslib/src/general/rpc.ts` | 新增 `readPath(handle, path)`（读非函数属性）与 `invokeGet` 的类型化包装；`Window.read_property()` Python 入口 |
| 0.4 | `scripts/check_api_coverage.py`（新增） | 解析 `typings.d.ts` 的接口成员 + 读取 `docs/_generated/coverage.json`，输出覆盖率表并可在 CI 中 gate |
| 0.5 | 契约文档 | 在 `docs/advanced/bridge.md` 增补“能力边界”与 `$ref`/`store_as` 规则 |

**验收**：`Lib.enums.LineStyle.Solid === 0`；`chart.read_property('...chart', 'options')` 可回读；覆盖率脚本能跑出 §2 的表。

---

### Phase 1 — 实例方法与查询补齐 + Bug 修复（1 周）
**目标**：把 §2 中 `IChartApi/ISeriesApi/ITimeScaleApi/IPriceScaleApi/IPaneApi` 的缺口全部补上。

| 步骤 | 文件 | 内容 |
|---|---|---|
| 1.1 | `abstract.py` | `Chart.options()`、`chart_element()`（返回句柄，不序列化 DOM）、`horz_behavior()` |
| 1.2 | `abstract.py` | `TimeScale`: `options()`、`visible_time_range()`、`subscribe_visible_time_range_change()`、`size_change()` + 对应 `unsubscribe` |
| 1.3 | `price_scale.py` | `PriceScale.options()`、`PriceScale.price_scale_id` 已有；补 `is_visible()`（`width>0`） |
| 1.4 | `abstract.py` | `SeriesCommon`: `price_formatter()`、`price_lines()`（`invoke_get` 读 JS 集合）、`update(..., historical_update=False)`、`subscribe_data_changed()`/`unsubscribe_data_changed()`、`get_pane()`（返回 `Pane` 句柄） |
| 1.5 | `abstract.py` | `Pane`: `get_htmlelement()`、`get_series()`（列表）、`move_to()`、pane 级 `add_series()`/`add_custom_series()` |
| 1.6 | `util.py` + `jslib/src/general/handler.ts` | 给双击做与 click 相同的**扇出**（`add/removeDblClickListener`）；统一 `JSEmitter.unsubscribe()` 覆盖全部事件 |
| 1.7 | `abstract.py` | **修复** `vertical_span`（改用 `series.attachPrimitive`/`band` 或新增 `VerticalSpan` primitive）与 `VerticalLine.update` 的 `price` 变量 |

**验收**：`tests/test_api_coverage.py` 对每个新方法断言生成的 JS；e2e 增加双击扇出、`price_lines()` 回读、`options()` 回读三条。

---

### Phase 2 — v5 插件生命周期（1 周）
**目标**：把 markers / updown / 水印从“只能创建”升级为“完整可操作”。

| 步骤 | 文件 | 内容 |
|---|---|---|
| 2.1 | `handler.ts` | `setMarkers` 返回并 `register` marker primitive 句柄；新增 `getMarkers(series)` |
| 2.2 | `abstract.py` | `MarkersPlugin` Python 包装：`markers()` `set_markers()` `detach()` `apply_options()`；`SeriesCommon.markers_plugin` |
| 2.3 | `abstract.py` | `UpDownMarkersPlugin`：`set_data()` `update()` `markers()` `set_markers()` `clear_markers()` `detach()` `apply_options()` |
| 2.4 | `handler.ts` | `setWatermark` 注册 `_watermark` 句柄；新增 `getWatermark()` |
| 2.5 | `abstract.py` | `WatermarkPlugin` / `ImageWatermarkPlugin`：`apply_options()` `detach()` `get_pane()` |
| 2.6 | `toolbox.ts`? | 无 |

**验收**：单测断言 `createUpDownMarkers` 后 `setData/clearMarkers` 调用链；e2e 断言 updown 标记增删。

---

### Phase 3 — 函数式 options（回调注入协议）（1.5 周）
**目标**：让 Python 能设置所有函数型 option，而无需用户手写 `preload`。

**协议设计**（沿用现有 `registerFormatter` 思路）：
```text
Python: chart.register_js_callback(name, params=[...], body="return ...;")
        chart.set_option_callback('<handle>.chart', 'timeScale.tickMarkFormatter', name)
JS:     registerCallback(name, params, body) -> new Function(...params, body)
        setOptionCallback(handle, dottedPath, name) -> 在对象上按路径写入函数
```

| 步骤 | 文件 | 内容 |
|---|---|---|
| 3.1 | `jslib/src/general/callbacks.ts`（新增） | `registerCallback`、`lookupCallback`、`setOptionCallback(handle, path, name)`；用 `new Function` 编译 body |
| 3.2 | `handler.ts` | 暴露 `setOptionCallback`；对 `localization.*`、`timeScale.tickMarkFormatter`、series `priceFormat.formatter`、`autoscaleInfoProvider` 做路径校验 |
| 3.3 | `abstract.py` | `register_js_callback()`、`set_option_callback()` 通用入口 |
| 3.4 | `formatters.ts` | 声明式 formatter 与函数式 formatter 统一（`name=` 引用已注册回调） |
| 3.5 | `util.py` | `as_enum` 弃用，改用 Phase 0 常量 |

**注意**：回调在 **JS 侧同步执行**，不能回调 Python（避免阻塞渲染帧）。`autoscaleInfoProvider` 需在 JS 内返回对象，故只能用注册的 JS 函数体。

**验收**：单测 + e2e：`tickMarkFormatter` 返回自定义字符串、per-series `priceFormat.formatter` 生效。

---

### Phase 4 — Primitive 与自定义系列（从 Python 构造）（2.5 周）
**目标**：让用户仅用 Python（+可选 JS 函数体）就能定义 `ISeriesPrimitive` / `IPanePrimitive` / `ICustomSeriesPaneView`。

**JS 工厂设计**：
```ts
// jslib/src/primitives/declarative.ts
makeSeriesPrimitive(spec)  // spec: { paneViews:[{zOrder,draw,paneViewType}], priceAxisViews:[...], autoscaleInfo?, hitTest?, attached?, detached? }
makePanePrimitive(spec)
makeCustomSeriePaneView(spec) // spec: { renderer:{draw,hitTest}, priceValueBuilder, isWhitespace, defaultOptions, conflationReducer }
```
其中 `draw`/`hitTest`/`autoscaleInfo`/`priceValueBuilder` 用 **Phase 3 注册的 JS 函数名** 或内联 body 字符串，经 `new Function` 编译。

| 步骤 | 文件 | 内容 |
|---|---|---|
| 4.1 | `jslib/src/primitives/declarative.ts`（新增） | 建 `ISeriesPrimitive` / `IPanePrimitive`，支持 paneViews / axis views / autoscaleInfo / hitTest / attached / detached |
| 4.2 | `jslib/src/primitives/renderers.ts`（新增） | 通用 `PrimitivePaneRenderer`：把声明式绘制指令（复用 `shapes.py` 的图元）映射到 canvas |
| 4.3 | `handler.ts` | `createSeriesPrimitive(spec, handle)` / `createPanePrimitive(spec, handle)` / `attachPrimitive(seriesOrPane, ref)` |
| 4.4 | `pylightcharts/primitives.py`（新增） | Python `SeriesPrimitive` / `PanePrimitive` 类（`attach_to(series|pane)`、`detach()`、`update()`） |
| 4.5 | `custom-series.ts` + `handler.ts` | `createCustomSeries` 支持传入 `paneView` spec（renderer/priceValueBuilder/isWhitespace/defaultOptions） |
| 4.6 | `shapes.py` | 图元协议升为“可被 primitive 复用”的统一绘制指令集 |
| 4.7 | `toolbox` 无关 | 现有 13 个绘图 primitive 可迁移为声明式（可选，减小 JS 体积） |

**验收**：e2e 用纯 Python 定义“价格轴标签 primitive”“自定义 K 线渲染器”，断言像素变化与命中测试。

---

### Phase 5 — 自定义水平轴 `IHorzScaleBehavior`（1 周，小众）
**目标**：Python 可注册并使用自定义横轴（收益率曲线/期权图已内建）。

| 步骤 | 文件 | 内容 |
|---|---|---|
| 5.1 | `horz-scale.ts` | `registerHorzScaleBehavior(name, spec)`：spec 内各方法用注册的 JS 函数体 |
| 5.2 | `abstract.py` | `register_horz_scale_behavior(name, **methods)`；`Chart(kind='custom:<name>')` |
| 5.3 | `numeric.py` | 内建 `YieldCurveChart`/`OptionsChart` 改为走该统一入口 |

**验收**：e2e 注册一个“周序号”横轴并正确格式化刻度。

---

### Phase 6 — 顶层导出、类型与文档（0.5 周）
| 步骤 | 文件 | 内容 |
|---|---|---|
| 6.1 | `pylightcharts/__init__.py` | 补 `HeadlessChart/Table/ToolBox/TopBar/PolygonAPI/drawings/Line/Candlestick/Area/Bar/Baseline/CustomSeries/constants/primitives` 到 `_LAZY`/`__all__` |
| 6.2 | `docs/api.md` | 按接口分节补齐 API 参考（含新增方法） |
| 6.3 | `mkdocs.yml` | 新增本页与 `api.md` 子节导航 |
| 6.4 | `PROGRESS.md` | 记录覆盖率从 ~90% → 100% 的里程碑 |

---

### Phase 7 — 测试 / CI / 发布（贯穿）
| 步骤 | 内容 |
|---|---|
| 7.1 | 每个新封装必须有 Python 单测（断言生成的 JS 字符串） |
| 7.2 | JS 新增模块加 vitest（`rpc.ts`/`callbacks.ts`/`primitives`） |
| 7.3 | e2e 逐特性增加场景（双击、插件生命周期、回调、primitive、自定义轴） |
| 7.4 | CI gate：`check_api_coverage.py` 覆盖率不得下降；`npm run build` 后校验 `pylightcharts/js/bundle.js` 与 `jslib/dist/bundle.js` 一致 |
| 7.5 | 升级流程脚本 `scripts/upgrade-lwc.sh`（固定版本 → 迁移 breaking change → 重建 → e2e） |

---

## 5. 里程碑与工作量估算

| 阶段 | 内容 | 工作量 | 累计覆盖率（估） |
|---|---|---|---|
| P0 | 地基协议 + 枚举导出 + 覆盖率脚本 | 0.5 周 | ≈93% |
| P1 | 实例方法/查询 + 2 个 bug | 1 周 | ≈97% |
| P2 | 插件生命周期 | 1 周 | ≈98% |
| P3 | 函数式 options | 1.5 周 | ≈99% |
| P4 | Primitive / 自定义系列 | 2.5 周 | ≈99.5% |
| P5 | 自定义横轴 | 1 周 | ≈100% |
| P6 | 导出 / 文档 | 0.5 周 | 100%（方法级） |
| P7 | 测试 / CI | 贯穿 | — |
| **合计** | | **≈8 周** | |

---

## 6. 验证策略

1. **覆盖率可量化**：`scripts/check_api_coverage.py` 解析 `typings.d.ts` 成员，与 Python 导出清单（`docs/_generated/coverage.json`）比对，CI 中输出表格并 gate。
2. **三层对拍**：Python 单测断言“Python 调用 → 生成 JS 字符串”；vitest 断言“JS 纯函数行为”；e2e（headless Chromium）断言“渲染像素/交互”。
3. **不回归**：Phase 1/2 的改动全部是新增方法，不触碰现有调用路径；`tests/test_lwc_compat.py` 保证 `lightweight_charts` 兼容名不变。
4. **契约固定**：所有新 RPC 协议写进 `docs/advanced/bridge.md`；`$ref`/`store_as`/回调命名规则统一。

---

## 7. 风险与注意事项

| 风险 | 缓解 |
|---|---|
| 函数式回调无法回调 Python（同步执行） | 回调只允许“已注册的 JS 函数体”，文档明确禁止在回调里等 Python |
| `new Function` 编译用户 body 有安全/打包约束 | 仅在本地桌面/自托管场景；文档标注，不在服务端多租户使用 |
| Primitive 每帧执行 draw，跨 JSON 传数据会卡 | 绘制指令随 `setData` 一起下发（沿用 CustomSeries 的 `originalData` 方案），draw 不发起 RPC |
| 上游升级 breaking change | 固定 LWC 版本 + `upgrade-lwc.sh` + 覆盖率 gate |
| `abstract.py` 过大（≈1800 行） | Phase 1/2 顺手拆分 `series.py`/`panes.py`/`plugins.py`（注意循环导入） |
| 自定义横轴/primitive 属小众 | 排在 P4/P5，可作为“可选增强”，不阻塞主线发布 |

---

## 8. 建议的立即动作（Next Actions）

1. **P0.1 + P0.2**：在 `jslib/src/index.ts` 导出枚举与常量，Python 建 `constants.py` —— 半天内消除“猜整数”隐患。
2. **P1.7**：先修 `vertical_span` / `vertical_line.update` 两个必崩 bug。
3. **P1.1–P1.5**：一次性补齐全部 `options()`/查询类方法（纯封装，风险最低）。
4. **P0.4**：落地覆盖率脚本，把 §2 的表变成可自动生成的产物。

---

## 9. 执行进度（滚动更新）

| 阶段 | 状态 | 说明 |
|---|---|---|
| P0.1 | ✅ | `jslib/src/general/exports.ts`：`Lib` 导出 11 个枚举 + `version/isBusinessDay/isUTCTimestamp/defaultHorzScaleBehavior/customSeriesDefaultOptions` 及 `create*` 工厂；Node 运行时校验 **15/15** 通过、`Lib.version()==5.2.1` |
| P0.2 | ✅ | 新增 `pylightcharts/constants.py`（枚举 Python 镜像 + `verify(chart)` 运行时对拍） |
| P0.3 | ✅ | `Window.read_property(handle, path)`（经 `Lib.lookup` 读属性/零参调用） |
| P0.4 | ✅ | 新增 `scripts/check_api_coverage.py`（解析 `typings.d.ts` + manifest，CI 可 gate）+ `scripts/api_coverage_baseline.json` |
| P1.7 | ✅ | 新增 `Lib.VerticalSpan` primitive（v5），修复 `VerticalLine.update` 的未定义变量 |
| P1.1 | ✅ | `chart_options()` `chart_element()` `horz_behavior()` |
| P1.2 | ✅ | `time_scale_settings()`；`events.visible_time_range_change`、`events.size_change`（含 unsubscribe） |
| P1.3 | ✅ | `PriceScale.options()` |
| P1.4 | ✅ | `SeriesCommon.price_formatter()` `js_price_lines()` `update(historical_update=)` `subscribe_data_changed()` / `unsubscribe_data_changed()` `get_pane()` |
| P1.5 | ✅ | `pane_get_htmlelement()` `pane_series_handle()` `pane_move_to()` `pane_add_series()` `pane_add_custom_series()` |
| P1.6 | ✅ | `Handler` 双击扇出 `add/removeDblClickListener`，`events.dblclick` 改走扇出 |
| P2.1 | ✅ | `Handler.setMarkers(..., handle)` 注册 marker primitive；`SeriesMarkersPlugin`（`set_markers/markers/apply_options/detach/get_series`） |
| P2.2 | ✅ | `UpDownMarkersPlugin`（`set_data/update/markers/set_markers/clear_markers/apply_options/detach/get_series`），工厂 `SeriesCommon.up_down_markers_plugin()` |
| P2.3 | ✅ | `Handler.setWatermark(..., handle)` 注册水印；`TextWatermarkPlugin` / `ImageWatermarkPlugin`（`apply_options/detach/get_pane`） |
| P3.1 | ✅ | 新增 `jslib/src/general/callbacks.ts`：`registerCallback` / `lookupCallback` / `listCallbacks` / `setOptionCallback` / `setPriceFormatFormatter`（Node 运行时验证：flat / nested / merge-safe / 未知名报错） |
| P3.2 | ✅ | Python：`register_js_callback()` `set_option_callback()` `set_tick_mark_formatter()` `set_price_formatter_callback()` `set_time_formatter_callback()` |
| P3.3 | ✅ | 系列级 `set_price_format_formatter()` / `set_autoscale_info_provider()`（per-series 函数式 option，merge-safe） |
| P4.1 | ✅ | 新增 `jslib/src/primitives/declarative.ts`：`CallbackPrimitive` / `CallbackPanePrimitive` / `createSeriesPrimitive` / `createPanePrimitive`；覆盖 `paneViews/priceAxisPaneViews/timeAxisPaneViews/priceAxisViews/timeAxisViews/autoscaleInfo/hitTest/attached/detached/updateAllViews`（含 Node 运行时验证） |
| P4.2 | ✅ | 新增 `pylightcharts/primitives.py`：`SeriesPrimitive` / `PanePrimitive`（`attach_to` / `detach_from` / `apply_options` / `options` / `request_update`），工厂 `create_series_primitive()` / `create_pane_primitive()` |
| P4.3 | ✅ | `SpecCustomSeriesPaneView`：`rendererDraw` / `rendererHitTest` / `priceValueBuilder` / `isWhitespace` / `defaultOptions` / `destroy` / `conflationReducer`；`add_custom_series(spec=...)` |
| P5.1 | ✅ | `jslib/src/general/horz-scale.ts` 新增 `registerHorzScaleBehaviorSpec(name, spec)`：13 个 `IHorzScaleBehavior` 方法由注册回调驱动，缺省方法有 identity/字符串兼底（Node 运行时验证） |
| P5.2 | ✅ | Python `AbstractChart.register_horz_scale_behavior(name, spec)` + `_horz_scale_name` / `_horz_scale` 类属性（自动在 Handler 创建前注册）；spec 值可为回调名或 `(params, body)` |

**覆盖率（`scripts/check_api_coverage.py`）：150 / 150 = 100.0%**（起点 84 / 150 = 56.0%）。
全部 15 个接口（含三个 v5 插件、`ISeriesPrimitiveBase`/`IPanePrimitiveBase`、
`ICustomSeriesPaneView`/`ICustomSeriesPaneRenderer`、`IHorzScaleBehavior`）均 **100%**。
P3 的函数式 options 不属于“方法计数”，不计入该百分比。

**验证**：`tests/test_api_coverage.py` 全量通过（**44/44**）；JS 回调、primitive 工厂、自定义水平轴 behavior 均已在 Node 中实测。首阶段的 **P0–P5 全部完成**。

---

## 附：已实现但暂缓的功能 / 已知边界

上面 P0–P5 是"上游 API 覆盖"这条线。另一类工作 - **能做、但不是现在必须做**
的功能（触屏拖动布局分隔条、网格化布局、销毁图表、primitive `zOrder`、
引擎 1px pane 分隔线、桥的 `invokeOptional` 等）以及已知的粗糙边界，统一记录在：

- [`deferred.md`](deferred.md) —— 每条都写明：现象 / 为什么暂缓 / 代码位置 /
  实现思路 / 怎么验证。

新发现同类问题时请加进该文档，而不是在源码里留一个光秃秃的 `TODO`。
