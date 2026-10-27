# pylightcharts 进展报告

> Custom Series 协议实现、覆盖率盘点与后续路线图

---

## ✅ Custom Series：Python→JS 渲染协议

### 核心设计

难点是 `draw()` **每帧同步执行**，Python 无法参与。所以把工作拆成两半：

```
┌─ Python（数据更新时算一次）────────┐   ┌─ JS（每帧执行）──────────────┐
│ 每根 bar 附带 shapes 描述          │ → │ 通用渲染器：把 shape 映射成像素 │
│ shapes.range_bar(low, high)       │   │ x ← bar.x + offset×barSpacing │
│ shapes.box_plot(...)              │   │ y ← priceConverter(price)     │
└───────────────────────────────────┘   └───────────────────────────────┘
```

**关键洞察**：`CustomBarItemData.originalData` 会原样带回数据项的额外字段，所以 shape 描述**随数据一起下发**，无需 RPC。JS 侧只需一个通用渲染器。

### API

```python
from pylightcharts import shapes

series = chart.add_custom_series('range bars', pane_index='new')
series.set(df, shapes=lambda row: shapes.range_bar(row['low'], row['high']))
```

**7 种图元**：`rect` `band` `line` `circle` `text` `polyline`（+ 竖直锚点用价格、水平锚点用 bar 单位）
**3 个预设**：`range_bar` `box_plot` `error_bar`

```python
shapes.box_plot(low, q1, median, q3, high)
shapes.polyline([(0.0,1.0),(0.4,2.0)], fill_color='rgba(0,0,0,0.2)')
shapes.text(price, 'label'); shapes.circle(price, offset=0.2, radius=4)
```

数据项支持 `value` / `low` / `high`（自动缩放 + 最新价）、`color`、`shapes`。

### 验证

| 测试 | 结果 |
|---|---|
| 单元测试 | **86 passed**（新增 `test_custom_series.py` 10 项） |
| 浏览器 e2e | `customSeries:true`，非黑像素占比 **0.1501 → 0.1683** |
| 无头渲染 | 新增测试：断言自定义图形确实产生了红色像素（>200px） |
| 全栈 pywebview | `FULL_STACK_OK` |

### 更新后的覆盖率

| API 组 | 覆盖率 |
|---|---|
| IChartApi | 25/26 (96%) |
| ISeriesApi | 23/25 (92%) |
| ITimeScaleApi | 21/24 (88%) |
| IPriceScaleApi | 6/6 (100%) |
| IPaneApi | 12/15 (80%) |
| IPriceLine | 2/2 (100%) |
| **合计** | **≈ 91%** |

---

## 后续完善建议

### 🔴 P0 — 工程质量（当前最大短板）

| 项 | 现状 | 建议 |
|---|---|---|
| **CI** | 全靠手动 | GitHub Actions：`npm run build` → `pytest` → headless e2e（ubuntu/windows/macos） |
| **打包** | `pyproject` 写好但未验证 wheel 是否含 `js/` 资源 | 加 `python -m build` + 安装 wheel 后跑一遍 e2e 的检查；`twine` 发布 |
| **返回值队列脆弱** | `Window._return_q` 是**单个共享 mp.Queue**，多窗口/多线程 `invoke_get` 会串台 | 改成 **请求 id 关联**（`{id, result}` + 每请求独立 Future） |
| **启动忙等** | `while not run_script_and_get('document.readyState...')` 是 CPU 忙轮询 | 换成 webview 的 `loaded` 事件 + `threading.Event` |
| **错误暴露** | JS 异常只给原始 message | 解析 `{name,line,message}`，附上出错的脚本片段 + Python 调用栈 |
| **PyWV 异常处理** | 只捕获 `KeyError`，其它异常会杀掉消息循环 | 全量捕获、回传错误、保持循环存活 |
| **剩余事件** | 缺 `subscribeDataChanged` / `subscribeSizeChange` / `subscribeVisibleTimeRangeChange` | 复用现成 `JSEmitter`，各 ~10 行 |

### 🟠 P1 — 功能与性能

1. **绘图工具补齐**：Andrew 音叉、Gann 扇形、Fibonacci 扩展/投影、长/短仓位工具、箭头/椭圆/矩形填充 —— 全部复用 `SimpleTwoPointDrawing`，每个 ~120 行
2. **指标扩展 + 自动更新**：Ichimoku / ADX / OBV / CCI / Williams %R / Supertrend / PSAR / Keltner；再做一层 `Indicator` 抽象，让指标在 `update()` / `new_bar` 时**自动重算**（目前是手动）
3. **`update()` 批量刷新**：tick 级更新目前每次一条 `evaluate_js`；应聚合成帧级 flush
4. **Conflation**：v5 的 `conflation` 选项能处理超大数据集，暴露即可
5. **Custom Series 的 shapes 压缩**：目前走 JSON，嵌套 dict 体积大；可设计紧凑二进制编码（复用 `decodeData` 思路）
6. **拆分 `abstract.py`**：已 ~1400 行、职责过多（series/chart/panes/indicators/events）。建议拆成 `series.py` / `chart.py` / `panes.py`，注意循环导入
7. **文档站**：mkdocs + API 参考 + 截图 gallery

### 🟢 P2 — 锦上添花

- `createYieldCurveChart` / `createOptionsChart`（专用图表入口）
- 函数式 `priceFormatter` / `timeFormatter` 回调（需 JS 侧 shim + 同步约束）
- 自定义水平轴行为（`IHorzScaleBehavior`，复杂、小众）
- JS 层单元测试（vitest 测 `rpc.ts` / `data.ts` 纯函数；目前只有浏览器 e2e）

### ⚠️ 开发中踩到的「规则」，建议写进 CONTRIBUTING

| 坑 | 规则 |
|---|---|
| `evaluate_js` 会序列化返回值 | fire-and-forget 一律走 `Window.invoke`（底层已 `;undefined`）；**任何返回对象的方法必须用 `store_as` 或 `invoke_get`（且只用于基本类型）** |
| 单队列 | 不要在多个线程同时 `invoke_get`（见 P0 修复） |
| MRO 遮蔽 | 图表与序列同名方法（如 `apply_options`）会互相遮蔽，命名要显式区分（已用 `series_options`/`data_points` 规避） |
| 上游升级 | 固定 LWC 版本；升级流程 = `npm pack lightweight-charts@X` → 迁移 breaking change → `npm run build` → 跑 e2e。建议做成 `scripts/upgrade-lwc.sh` |

---

## 结论

功能层面已接近完整（**91% 方法覆盖 / 100% 选项覆盖 / 独有指标+绘图+无头+大数据**）；下一个真正该投入的是 **CI + 打包发布 + 队列可靠性**，这三项决定它能不能从「能跑的工程」变成「能发布的库」。

---

## ✅ P0 完成记录（本轮）

| 项 | 实现 |
|---|---|
| **返回值队列加固** | `run_script_and_get` 改为 **请求 id 关联**（`_~_~RETURN~_~_<id>~|~<expr>`）+ 往返串行化（webview 本就是单线程），旧请求的迟到回包会被丢弃，不会串台 |
| **JS 错误传播** | JS 异常现在抛 `pylightcharts.util.BridgeError`（附解析后的 `Name/line/column/message` + 出错脚本片段），不再静默返回 `None` |
| **消息循环健壮性** | `PyWV.loop` 不再只捕获 `KeyError`，任何异常都不会杀掉循环；fire-and-forget 的 JS 错误打到 stderr |
| **忙等消除** | `on_js_load` 里的 `while not run_script_and_get(...)` CPU 忙轮询，改为带超时的有界等待 |
| **CI** | `.github/workflows/ci.yml`：`js`（构建 + 校验已提交产物是最新的）、`test`（ubuntu/windows/macos × py3.9/3.12）、`e2e`（Playwright + headless + smoke）、`package`（构建 wheel + 校验 js 资源 + 干净环境 import） |
| **打包验证** | `tests/test_packaging.py`：js 资源存在性、index.html 引用完整性、bundle 导出的桥接符号、**wheel 内含 `pylightcharts/js/*`** |
| **测试运行器** | 新增 `tests/e2e/smoke.py`（Playwright 优先，回退 CLI），`run-smoke.sh` 委托给它 |

### 顺带修掉的真实 bug

- `click` / `dblclick` / `range_change` 的事件 handler 之前用 `let` 声明；`evaluate_js` 的 `let` **不会跨调用持久化**，导致 `unsubscribe()` 时 `ReferenceError`。已全部改挂到 `window.*`（新增回归测试）。

### 验证

- 单元测试 **91 passed**（新增 packaging 4 项 + 事件作用域回归 1 项）
- 全栈 pywebview：`FULL_STACK_OK`，并确认 JS 错误确实抛出 `BridgeError`
- 浏览器 smoke：`RESULT_OK`
- wheel 构建：`pylightcharts/js/*` 全部存在

---

## ✅ P1 进展（本轮）

### 指标自动更新

- 新增 `_IndicatorBinding`：把「计算函数 + 目标 series」绑定到图表数据。
  - `chart.set(df)` → **全量重算**（≥2000 行走二进制传输）
  - `chart.update(bar)` → **只推最后一个点**，用 `tail_window`（默认 1000）做热启动重算，递归指标（EMA/RSI/ATR/MACD）与全量结果**数值一致**（测试断言到 1e-9）
  - VWAP 是累计量，标记 `full_only=True` 始终全量
- `add_computed_series(compute, name, ...)`：用户可注册自己的自动更新指标
- 指标实现从「先 set 数据再算」改为「注册即算 + 数据变化自动跟随」

### 性能：`_rma` 向量化

Wilder 平滑原本是 Python 循环（10 万行会卡）。改为「SMA 种子 + pandas ewm 续推」：

| | 之前 | 现在 |
|---|---|---|
| RSI 200k 行 | 秒级 | **21 ms** |
| 与 TA-Lib 偏差 | — | **5.7e-14** |

### `chart.batch()`

```python
with chart.batch():
    for tick in ticks:
        chart.update(tick)     # 所有桥接调用合成一条脚本发出
```

异常时也会在 `__exit__` 刷新（测试覆盖）。

### 指标扩展（7 个，全部与 TA-Lib 交叉验证）

`obv` `cci` `williams_r` `adx` `keltner` `roc` `mfi`
→ 对应 `add_obv` `add_cci` `add_williams_r` `add_adx` `add_keltner` `add_roc` `add_mfi`

| 指标 | 与 TA-Lib 最大偏差 |
|---|---|
| OBV / CCI / %R / ROC / MFI | **0**（浮点精度内） |
| ADX / +DI / -DI | ~0.1（Wilder 累积浮点差异；首值索引已与 TA-Lib 对齐到 `2n-1`） |

### 绘图工具：仓位/风险回报工具

`Position` primitive（`SimpleTwoPointDrawing` 子类）：

```python
chart.position(entry_time, entry_price, target_time, target_price, risk_ratio=1.5)
chart.long_position(...)   # 别名
chart.short_position(...)  # 别名
```

渲染盈利区/止损区、入场-目标-止损三条带标签的价位线，方向由点位自动推断。已接入工具栏（Alt+P）。

### Conflation

`enableConflation` / `precomputeConflationOnInit` 等本就是 series 选项，桥接已覆盖，只需文档。

### 测试

**120 passed**（新增 `test_indicator_updates.py` 9 项、`test_indicators_extended.py` 18 项、Position 3 项）
真实 webview 全栈验证：`chart.update()` 后 RSI 序列 106 → 107 点，确认自动跟随。

---

## ✅ P1 续：3 点绘制 + 模块拆分 + 文档站

### 3 点绘制支持

绘图框架原本只支持 2 点。现在 `DrawingTool` 通过 `requiredPoints` 支持任意点数（逐点落点、悬停拖动、端点拖动）：

- 新增 `ThreePointDrawing` / `ThreePointDrawingPaneView` / `ThreePointDrawingPaneRenderer`（JS）
- `DrawingTool.beginDrawing(type, options?)`，`_placePoint(point, index)` 通用化

新工具：

```python
chart.andrews_pitchfork(t1, p1, t2, p2, t3, p3)   # 中线 + 两条平行线 + 填充
chart.triangle(t1, p1, t2, p2, t3, p3)            # 三角形
```

→ 共 **11 种绘图工具**，已接入工具栏（`Alt+A` / `Alt+G`）。

### 模块拆分

`abstract.py` 2010 → **1662 行**，抽出两个关注点清晰的模块：

| 新模块 | 内容 |
|---|---|
| `pylightcharts/indicators_api.py` | `_IndicatorBinding` + `IndicatorMixin`（全部 `add_*`、`add_computed_series`、`_refresh_indicators`、`_compute*`） |
| `pylightcharts/price_scale.py` | `PriceScale`、`PriceLine` |

`AbstractChart(IndicatorMixin, Candlestick, Pane)`；`abstract.py` 继续 re-export，向后兼容。

### 文档站（mkdocs）

- `mkdocs.yml`（material 主题，5 个导航分组）
- `docs/`：index / installation / guide（charts, indicators, drawings, custom-series, panes, options, events）/ advanced（bridge, bulk-data, headless）
- `docs/api.md` **自动生成**（`scripts/gen_api_docs.py` 反射生成 2700+ 行 API 参考）
- CI 新增 `docs` job：校验 `docs/api.md` 是最新的 + `mkdocs build --strict`

### 测试

**124 passed**（新增 3 点绘制 4 项）；全栈 webview 验证 3 点绘制渲染
（非黑像素占比 0.2189 → **0.2222**）。

---

## ✅ P2 完成（本轮）

按顺序执行了 P2 清单：

### 1. 数值横轴图表：`createYieldCurveChart` / `createOptionsChart`

- `Lib.Handler` 新增 `kind` 参数（`'time'` / `'yield-curve'` / `'options'` / `'custom:<name>'`）；
  数值轴图表不再创建蜡烛/成交量序列与 legend（`this.legend?` 全部加保护）
- Python：`YieldCurveChart` / `OptionsChart`（桌面，继承 `Chart`）与
  `AbstractYieldCurveChart` / `AbstractOptionsChart`（后端无关）
- 数据模型：`time` 保持为**数字**（月数/行权价），`SeriesCommon.set` 通过
  `_time_based()` 跳过 epoch 转换；`chart.set(df)` 抛清晰的 `TypeError`
- 其余全部 API（panes/options/drawings/custom series/formatters）照常可用

### 2. 函数式 priceFormatter / timeFormatter

JS 侧回调是同步的，Python 无法直接提供函数，因此采用**声明式 spec + 可注册 JS 函数**：

```python
chart.set_price_formatter(decimals=2, thousands=True, prefix='$', compact=True)
chart.set_time_formatter('YYYY-MM-DD HH:mm')      # 支持 YYYY YY MMM MM DD HH mm ss
chart.register_js_formatter('eur', "value => '€' + value.toFixed(2)")
chart.set_price_formatter(name='eur')
```

### 3. 自定义水平轴行为（`IHorzScaleBehavior`）

提供逃生舱 + 文档化用法：
- JS：`Lib.registerHorzScaleBehavior(name, instance)` + `kind='custom:<name>'` 走 `createChartEx`
- Python：`Window.preload(script)` 在 handler 创建**之前**注入 JS（带顺序保证与 `loaded` 检查）
- 文档 `docs/advanced/custom-scale.md` 说明该接口较重，需参照上游 `HorzScaleBehaviorPrice`

### 4. JS 层单元测试（vitest）

`jslib/test/` 三个文件、**32 个测试**，覆盖 `rpc`（handles / `$ref` / storeAs / deepMerge）、
`data.decodeData`（列主序、NaN→whitespace、字符串列、5000 行）、`formatters`。

> 顺带修掉一个真实缺陷：`lookup()` 对未知单段路径会静默返回 `undefined`，现在抛错；
> `TradingView` 的 `createChartEx` 也已接入。

CI 的 `js` job 新增 `npm test`。

### 5. 3 点投影类工具

```python
chart.fibonacci_extension(t1, p1, t2, p2, t3, p3)   # 脉冲腿 + 回撤点投影
chart.gann_fan(t1, p1, t2, p2, ratios=..., extension=3)  # 1x1 及更陡/更缓射线
```

→ 共 **13 种绘图工具**；已接入工具栏（`Alt+X` / `Alt+N`）。
像素级验证：非黑像素占比 0.2222 → **0.2272**。

### 6. git 初始化与提交

- `git init` + 2 个提交（首个提交 181 个文件；参考仓库/`node_modules`/构建中间产物均被忽略）
- `.gitattributes` 固定 LF 并把 `pylightcharts/js/*` 标为 binary
- 验证**构建可复现**：重新构建后 `git diff --exit-code -- pylightcharts/js` 为空
  → CI 的「产物新鲜度」校验成立

### 测试总计

**Python 142 passed** · **JS 32 passed** · 浏览器 smoke `RESULT_OK` · 无头渲染 4 ·
wheel 打包 1 · 全栈 pywebview `FULL_STACK_OK`

---

## ✅ 图表工作台（P0）+ minibt 适配器验证（P5a）

### 背景：为什么不直接在 miniqt 里改

`miniqt/app/windows/chart_interface.py`（`Chart`，173 个方法 / 4534 行）与
`light_chart_replay.py`（`ReplayChart`）已经是**互相复制的两份实现**（82% 方法同名）。
再改一份就是第 4 个平行实现。所以先抽出可复用的**图表工作台**。

### 三个端口（唯一的接缝）

```
pylightcharts/workbench/
├── ports.py        BarRequest · BarSource · IndicatorOutput · IndicatorProvider · DrawingStore
├── session.py      ChartSession · IndicatorState（to_dict / save / load）
├── controller.py   ChartController（加载 / 实时 / 增删改指标）
├── providers.py    PandasBarSource · BuiltinIndicatorProvider
└── widgets/
    └── workspace.py  ChartWorkspace = ChartPanel + ChartController + ChartSession
```

关键约定：**`IndicatorOutput` 是 provider → 图表之间唯一的契约**，provider 只返回数据、
永不接触图表对象 —— 这样 minibt 的 `KLine` / `IndFrame` / `IndSeries` 数学可以完全留在
minibt 里（适配器在 `minibt/charting/adapter.py`）。

### 适配器实测结果

| | |
|---|---|
| 指标目录 | **474 个** / 6 类（`BtInd` 34、`PandasTa` 159、`TaLib` 92、`TqFunc` 12、`TqTa` 63、`TradingView` 114） |
| 参数表单 | 从各指标**自身签名**反射默认值（含 `talib=True` 这类布尔开关） |
| 渲染验证 | `tests/e2e/minibt_workbench.py`：500 根 K 线 + 5 个真实 minibt 指标 → 15 条序列 / 6 个窗格 / 27 个 canvas / `RESULT_OK` |

`IndicatorOutput` 覆盖了 minibt 的全部输出形态，端口只新增了一个 `markers` 字段：

| 指标 | 输出 |
|---|---|
| `PandasTa.bbands` | 3 条叠加主图 + 2 条独立窗格 |
| `PandasTa.macd` | 同一窗格内 2 条线 + 按正负着色的柱状图 |
| `TradingView.ADX_and_DI` | 3 线独立窗格 |
| `TradingView.SuperTrend` | 2 条叠加 + 1 窗格 + **11 个信号 marker** |
| `PandasTa.rsi` / `.sma` | 单线；独立窗格 vs 主图叠加 |

### 验证适配器时发现的 5 个真实 bug

1. **控制器忽略了 provider 的逐输出窗格**：只看 `spec.separate_pane`，于是 minibt 按列给出的
   `overlap` 判断被丢弃，所有振荡指标都画到了主图上。
2. **信号 marker 全为空**：`pd.DataFrame({col: values}, index=times)` 会把 minibt 的 0 基索引
   与 epoch 索引**对齐**成整列 `NaN`，必须用 numpy 数组构造。
3. **`IndSeries` 与 `IndFrame` 的列不是同一种形状**：`IndFrame` 的列把 `overlap`/`isplot` 报成
   **整张按列映射**，而单线 `PandasTa` 返回的裸 `IndSeries` 报的是**标量**。共用一条代码路径会把
   SMA/EMA（`overlap=True`）错误地塞进独立窗格。
4. **`marker_position` 对 v5 拼写静默返回 `None`**：只认 `'below'` 不认 `'belowBar'`，
   marker 会以 `"position": null` 到达图表。现在两种词表都接受。
5. **minibt 的 `line_color` 本就是 `None`**（由它自己的图表在绘制时配色），导致同一指标的
   所有线都是图表默认色。适配器现在复刻那条配色循环，同时**让柱状图保持无色**以便按正负着色。

### 顺带挖出的宿主级隐患（严重）

`minibt/indicators/core.py` 末尾执行：

```python
pd.DataFrame.__call__ = _call_
pd.Series.__call__ = _call_
```

这让**每个 Series 都变成可调用对象**。而 pandas 的 `where` / `clip` / `mask` 会把条件交给
`pandas.core.common.apply_if_callable`，后者看到"可调用"就**真的调用它** —— 布尔掩码被替换成
一个错位的对象，结果静默出错：

```
(close.diff().iloc[1:]).clip(lower=0).min()   # 期望 0，实际 -1.65
```

无异常、无警告。`pylightcharts.indicators` 的 `rsi` / `adx` / `mfi` 正好用了这些调用，
因此**只要进程里 import 过 minibt，它们就会被污染**（RSI 算出 `-991` 和 `395`）。

- 已把这些实现改成 numpy 直算（不写回视图），并加 `tests/test_pandas_traps.py`
  做**不依赖 minibt** 的复现守卫（`callable(series)` 不允许改变任何结果）。
- 真正的修法在 minibt 侧：删掉那两行 `__call__` 赋值。任何在同一进程里使用 pandas
  `where`/`clip`/`mask` 的代码都可能中招。

### 测试

**Python 257 passed**（新增 `test_workbench.py` 44 · `test_workbench_widgets.py` 8 ·
`test_bt_adapter.py` 17 · `test_pandas_traps.py` 5）· **JS 32 passed** ·
`examples/12_workbench/workbench.py` `RESULT_OK` · `tests/e2e/minibt_workbench.py` `RESULT_OK`

### 下一步

P1 实时 UI 开关（控制器已支持 `BarSource.subscribe`）→ P2 `ReplayClock` + 回放工具条 →
P3 指标面板 → P4 自选列表 + 多图布局 → P5b 把 miniqt 的两个窗口切到工作台。

---

## ✅ 实时模式（P1）

### 新增接口

```python
ChartController(..., dispatch=...)   # 宿主提供的线程切换
ChartController.on_live(cb)          # 订阅开始 / 停止
ChartController.on_error(cb)         # 某根 bar 无法应用
ChartController.restart_live()       # 切换 symbol/周期后重新订阅
ChartWorkspace.live_button           # 工具栏 Live 开关（不支持时禁用）
ChartWorkspace.live_changed          # signal(bool)
ManualBarSource                      # 可以自己 push bar 的数据源
```

### 三条新契约

1. **实时回调跑在别人的线程上。** `subscribe(on_bar)` 通常来自 websocket 线程，
   因此控制器接受可选的 `dispatch(action, *args)`；工作台传入的实现把 bar 重新
   发成 Qt 信号（`_bar_received`，队列连接），从而在 GUI 线程应用。非 Qt 宿主传
   自己的。默认内联，保证控制器无需 Qt 即可测试。
2. **坏 bar 不能弄死行情源。** `_on_bar` 同时包住派发与应用，任何异常都转成
   `on_error`（工作台再转发到 `error_occurred`），订阅继续存活 —— 理由同 P0：
   异常逃出 Qt 槽会**静默终止进程**。
3. **一个订阅只属于一个 symbol + 周期。** `start_live` 从会话构造请求，因此
   切换成功后会调用 `restart_live()`；而**切换失败时故意不重启** —— 图表这时
   仍显示旧数据，旧订阅才是对的。

### P1 顺带挖出的真实 bug

- **`controller.frame` 每根 bar 都会变陈旧。** `chart.update()` 用 `pd.concat`
  把 `chart.candle_data` **重新绑定**为新对象，而不是原地追加，于是控制器在加载
  时抓到的那份 frame 不再是图表的那份。指标本身没问题（图表把自己的 frame 传给
  `add_computed_series`），但任何读取 `controller.frame` / `len(...)` 的宿主会看到
  旧数据。现在 `update()` 会重新接管图表的副本，与 `reload` / `set_frame` 保持同
  一条不变式。
- **重写 `apply_theme` 是个坑。** `ChartPanel.__init__` 会应用主题，于是回调进
  工作台的 `_refresh_live_label` —— 而那时 live 控件还不存在。现在该刷新函数能
  容忍半成品状态。

`ManualBarSource` 是这一阶段的产物：没有它，实时模式就必须依赖网络才能测试；
而 P2 的回放需要的正是同一个「往里 push bar」的形状。

### 测试

**Python 275 passed**（新增实时相关 18 项：控制器层 12 + UI 层 6）·
`examples/12_workbench/workbench.py` 现在覆盖静态 + 实时：

```
live started  : True | mode live
live bars     : 3 | rows 900 -> 903
live stopped  : False | mode static
RESULT_OK
```

### 下一步

P2 `ReplayClock` + 回放工具条（步进 / 倍速 / 暂停）→ P3 指标面板 →
P4 自选列表 + 多图布局 → P5b 把 miniqt 的两个窗口切到工作台。

---

## ✅ 修掉 minibt 的 `pd.Series.__call__` 隐患

`minibt/indicators/core.py` 末尾为了让 `df(...)` 能造出 `KLine`/`IndFrame`/`IndSeries`，
赋值了 `pd.DataFrame.__call__` / `pd.Series.__call__`。这让**每个** Series 都可调用，而 pandas
的 `where` / `mask` / `clip` 会把布尔条件送进 `pandas.core.common.apply_if_callable`，后者
**只要对象可调用就会调用它** —— 掩码被替换，结果静默出错：

```
(close.diff().iloc[1:]).clip(lower=0).min()   # 期望 0，实际 -1.65
```

无异常、无警告。影响面是 minibt 自身的 `.clip(` 30 处 / `.where(` 344 处 / `.mask(` 4 处，
外加 miniqt 的 2 个文件；`pylightcharts.indicators` 的 `rsi`/`adx`/`mfi` 也会被污染。

### 修复（保留语法糖）

1. **`_call_` 收到位置参数时原样返回。** pandas 调用条件时一定是 `cond(self)` 这种带位置参数
   的形式；而 `df(...)` 语法糖与本库自己的 `IndicatorsBase.__call__(self, **kwargs)` 一样
   **只接受关键字参数**，所以位置参数必然不是用户调用。
2. **包裹 `pandas.core.common.apply_if_callable`，永不调用 Series/DataFrame。** 原生 pandas 里
   两者本来就不是可调用对象，"把 Series 当回调"永远不是有效用法 —— 排除它们等价于恢复上游
   语义，且不依赖 `_call_` 怎么实现。

### 验证

| 检查 | 结果 |
|---|---|
| `clip` / `where` / `mask` 的最小值 | 全部回到 **0.0000**（修复前 `clip` 为 `-1.65`） |
| `df(...)` 语法糖 | `frame()` → `KLine`、`series()` → `IndSeries`、`frame[['close']]()` → `IndFrame` |
| minibt 自身指标 | `PandasTa.sma`、`TradingView.SuperTrend` 正常 |
| 适配器 / 工作台 e2e | 17 → **18 passed**；`minibt_workbench.py` `RESULT_OK` |
| 真实 miniqt 集成 | `tests/e2e/miniqt_chart_check.py` `RESULT_OK` |

`pylightcharts` 侧依旧保持 numpy 直算（`tests/test_pandas_traps.py` 用**不依赖 minibt** 的
复现守住），所以即使宿主没修也不会被污染。

### 补丁脚本（minibt 无版本控制）

minibt/miniqt 都**不在 Git 下**，所以这次修改没有版本保护。补丁因此做成了可重复执行的
脚本而不是一次性编辑：

```
python scripts/patch_minibt.py            # 打补丁 + 备份 core.py.bak + 自检
python scripts/patch_minibt.py --check    # 未打补丁时退出码 1（可进 CI）
```

它是**幂等**的，并会在子进程里 import minibt 后断言 `clip`/`where`/`mask` 结果正确、
且 `df(...)` 仍能造出 `IndSeries`。`tests/test_pandas_traps.py` 额外验证了两件事：
脚本产出的文本与磁盘上的文件**逐字节一致**，以及它写入的守卫能**当场中和一个活的陷阱**。

---

## ✅ 修复 miniqt 在 minibt 1.2.8 下的三个 BUG

### BUG 1：添加指标的 "too many values to unpack (expected 13)"

minibt 1.2.8 给 `IndicatorsBase._get_plot_datas()` 增加了第 14 个返回值 `bandstyle`，
但消费方仍在解包 13 个。全仓扫描（minibt + miniqt 共 19 个调用点）发现**4 处漏改**：

| 位置 | 修复 |
|---|---|
| `miniqt/app/windows/chart_interface.py:3948` | 补 `band`（**你看到的报错**） |
| `miniqt/app/windows/light_chart_replay.py:1726` | 补 `band` |
| `miniqt/app/windows/light_chart_replay.py:1798` | 补 `band` |
| `minibt/strategy/base.py:1154` | 补 `bandstyle`（minibt 自身也漏了，回测绘图路径会炸） |

对照 minibt 已更新的同源文件（`strategy/light_chart.py`、`strategy/light_chart_replay.py`、
`btplot.py`）确认：第 14 个值**只接收、不被使用**，所以补名即可，其余逻辑无需改动。

**主力合约陈旧**（你提的第 1 项）：根因比"没刷新"更具体 —— `save_symbol_info` 只按
`instrument_id` 覆盖，而 `CONT_MAIN` 是"当前主力"的**子集标签**，每月都变，于是上个月的主力
永远留在表里。修复：

- `DatabaseManager` 新增 `get_meta` / `set_meta`（复用 `database_meta` 表）与
  `delete_symbol_info(ins_class=..., exchange_id=...)`；
- `MarketQuoteInterface.refresh_contracts_from_tq()`：登录天勤后**每天全量刷新一次**
  （QTimer 分段 + 同步写库，不阻塞 UI、不与 DuckDB 争写），先把 `CONT_MAIN` 行清空再写入当前
  主力，完成后把日期写进 `database_meta`；同一天再次登录直接读库；
- `__update_table` 增加兜底：已登录天勤且今天尚未刷新时**绕过内存缓存**直接取实时数据。

### BUG 2：图表打开后键盘精灵失效

`current_widget` 只在**鼠标点击板块**时才更新，而新建的图表在被点击前它仍是 `None`。全局事件
过滤器的条件（`current_widget is not None`）因此不成立，空格键被 `LightChartWindow` 的事件过滤器
吃掉（`center_on_latest()`），精灵再也打不开。修复：

- 新增 `MarketQuoteWindow.active_chart_widget()`：依次回退 `current_widget` →
  `last_clicked_widget` → splitter 里的第一个图表（并对已销毁的 C++ 对象做保护）；
- 全局过滤器与 `keyPressEvent` 改用它；
- `show_key_elf()` 增加**脏标志自愈**：若没有活着的精灵窗口就把 `key_elf_enabled` 复位，
  并连接 `destroyed` 信号，避免窗口被异常销毁后快捷键永久失效；
- `KeyElfWindow` 选中指标时也用同一个目标解析，不再依赖 `current_widget`。

### BUG 3：删除首个指标后画线工具不能画线

**这是本轮最有价值的发现。** LWC 的 `subscribeClick` / `subscribeCrosshairMove` 都是**单槽**订阅，
而四个使用方在抢同一个主图：图例（`legend.ts`）、画线工具（`drawing-tool.ts`）、副图同步
（`handler.ts`）以及宿主应用（`util.py` 的 `events.click` / `events.crosshair_move`）。
**谁最后订阅谁赢。**

minibt/miniqt 在图表加载完成后执行 `self.events.click += self.on_chart_click`，删除指标时又通过
`reset_cursor_change` 重绑 —— 每次都把画线工具的订阅顶掉，于是点击落不到点上、"橡皮筋"预览也停了。

修复（在 pylightcharts 的 JS 侧，属于库的正确设计）：

- `Handler` 自己**独占**这两个槽，内部维护 `_clickListeners` / `_crosshairListeners` 并做分发；
- 新增 `addClickListener` / `removeClickListener` / `addCrosshairListener` /
  `removeCrosshairListener`（**可叠加**，而不是替换）；
- 图例、画线工具、副图同步、`util.py` 的 emitter 全部改走这套接口；
- `DrawingTool` 改为接收结构化的 `DrawingEventSource`（避免与 `handler.ts` 形成运行时循环导入）；
- `util.py` 的 emitter 改为**先移除再添加**，因此重复 `+=` 是幂等的（不会叠加多个回调）。

验证：`tests/e2e/drawing_events_check.py` 在真实图表上断言主机订阅前后、退订后
`toolClickBound` / `toolMoveBound` **始终为 true**。

### 顺带查清的两件事

1. **`chart_interface.py:2169` 的 `Qt.CustomContextMenu` 等 73 处扁平枚举不是 BUG。**
   `qtpy.enums_compat.promote_enums()`（由 qfluentwidgets 依赖的 `qtpy` 触发）会把枚举成员
   `setattr` 到真实 PyQt6 类上，恢复 PySide6 风格的扁平访问。`scripts/scan_qt_enums.py` 已改为
   先加载该兼容层再扫描，避免 73 条误报（现在为 0）。注意这是**第三方垫片**在兜底，属于潜在脆弱点。
2. **miniqt 用的是 pylightcharts，不是 lightweight_charts。** `install_alias()` 的
   meta-path finder 把 `lightweight_charts` 整体映射到 pylightcharts，实测：
   `lightweight_charts.__file__` 指向 `pylightcharts/__init__.py`，
   `ci.Line is pylightcharts.abstract.Line`、`get_chart_class() is pylightcharts.widgets.QtChart`
   均为 True。site-packages 里那份真的 `lightweight_charts` 从未被导入。
   前提是 `install_alias()` 在任何 `import lightweight_charts` 之前执行（`__main__.py` 已保证）。

### 测试

**Python 279 passed** · **JS 32 passed** · 浏览器 smoke `RESULT_OK` · 全栈 `FULL_STACK_OK` ·
`miniqt_chart_check.py` `RESULT_OK` · `miniqt_indicator_check.py` `RESULT_OK`（6 种指标形态全部
通过真实的 `Chart.add_indicator`）· `drawing_events_check.py` `RESULT_OK` ·
`minibt_workbench.py` `RESULT_OK`

---

## ✅ 修复 DuckDB 致命错误 + 统一使用 pylightcharts

### DuckDB `database has been invalidated`（并发写损坏索引）

```
_duckdb.FatalException: FATAL Error: database has been invalidated because of a
previous fatal error.
Original error: "Invalid Input Error: Failed to delete all rows from index.
Only deleted 67 out of 95 rows."
```

**根因**：`DatabaseManager` 的 `_lock` 只保护**单例创建**，写操作完全没有串行化。而
`save_symbol_info` 是 **DELETE + INSERT 两条语句**（非原子），且被多个 `SaveSymbolInfoThread`
和主线程的填充循环并发调用。DuckDB 的连接**不支持多线程并发写**：两个线程删同一批 id 再各自
插入 → `Duplicate key ... violates primary key`；ART 索引随之与数据失配 → 整个库被标记为
invalidated，之后必须重开连接。

已用一个独立压测脚本证实（8 线程 × 12 轮交叠 upsert）：

| 模式 | 结果 |
|---|---|
| 旧：无锁 DELETE + INSERT | **BROKEN**（`Duplicate key violates primary key`） |
| 加写锁 | clean |
| 写锁 + `INSERT OR REPLACE` | clean |

**修复**：

- `DatabaseManager.__init__` 新增 `self._write_lock = threading.RLock()`，所有写方法
  （`save_symbol_info` / `delete_symbol_info` / `set_meta` / `mark_database_populated` /
  `save_exchange_symbols` / `save_ins_class_map` / `save_exchange_id_map` / 搜索表重建）全部
  持锁执行；
- `save_symbol_info` 的两步 DELETE+INSERT 改为**单语句 `INSERT OR REPLACE ... SELECT`**
  （原子，且不再有索引删除过程）；
- 新增 `_recover_connection()`：识别 invalidated/fatal 后**重开连接**（保留数据文件）并重试一次 ——
  原来的恢复分支只在 WAL 损坏时生效，而且会**删库文件**，不能用于这里；
- `refresh_contracts_from_tq` 的「清空 CONT_MAIN」改为**按交易所、仅在抓取成功后**执行，
  抓取失败不会误删该交易所的主力合约。

回归测试：`tests/test_miniqt_db.py`（8 线程并发 save、以及 save 与 delete/set_meta 混跑，
断言无异常且库仍可用）。

### 静默调试输出

按你的要求，把本轮新增的 `[合约全量刷新]`、`[DatabaseManager] 读取/写入元数据`、
`[DatabaseManager] 删除合约信息` 等打印注释掉；`save_symbol_info` 失败时也不再抛完整
traceback（只留一行简短信息）。

### `chart_interface.py` 直接使用 pylightcharts

你的疑问完全正确 —— 之前那 5 行 `from lightweight_charts import ...` 只是**别名**，容易误解。
现在 `miniqt/app/windows/chart_interface.py` 全部改为直接导入 `pylightcharts`：

- 顶部 5 条导入 → `from pylightcharts import util` / `.util` / `.abstract` / `.drawings` / `.toolbox`；
- `get_chart_class()` 里的 monkey-patch 目标 → `pylightcharts` / `pylightcharts.widgets`
  （`using_pyside6`、`QWebEngineView`、`Qt`、`Bridge`、`QtChart` …）；
- `TYPE_CHECKING` 下的类型导入同步更新。

这**更健壮**：即使 `install_alias()` 没有先执行，也不会误拿到 site-packages 里那份真的
`lightweight_charts`。其它文件（`light_chart_replay.py`、`strategy_backtest_window.py`、
minibt 的 `strategy/light_chart.py`）仍用别名，所以 `__main__.py` 里的 `install_alias()` 保留。

### 验证

**Python 281 passed**（新增 `tests/test_miniqt_db.py` 2 项）· `miniqt_chart_check.py` `RESULT_OK` ·
`miniqt_indicator_check.py` `RESULT_OK`（含 `ChartClass module = pylightcharts.widgets`）·
`drawing_events_check.py` `RESULT_OK`

---

## ✅ 修复登录后闪退（DuckDB 原生崩溃）+ 无效合约代码

### 闪退的真凶：DuckDB 原生层硬崩溃

`~/.miniqt/crash.log` 是 **0 字节**（没有 Python 异常、也没有 faulthandler 输出），所以去查了
Windows 事件日志：

```
错误应用程序: python.exe
错误模块:     _duckdb.cp312-win_amd64.pyd
异常代码:     0xc0000409   (STATUS_STACK_BUFFER_OVERRUN / __fastfail)
```

这是 **C++ 层的 `abort`**，进程直接消失、不留任何 Python 痕迹 —— 所以"闪退且无任何提示"。

**根因**：上一轮我只给**写**操作加了锁，**读**没有。而同一个 DuckDB 连接被多处并发使用：
主线程的合约刷新/保存，加上 `DatabaseInitThread`、`_on_db_init_finished`、键盘精灵的
`get_search_table` 等**子线程里的读**。DuckDB 的连接不支持并发使用 —— 读写交叠会让原生
扩展 `__fastfail`。这同时解释了上一轮那个 `database has been invalidated` 报错（同一个根因）。

**修复**：把整条连接包起来，**所有** execute / fetch / close / connect 都串行化：

```python
class _LockedConnection:   # 包住 duckdb.connect() 的结果
    def execute(...):      # 持锁执行，返回 _LockedResult
class _LockedResult:       # fetchone/fetchall/fetchdf 也持锁
```

一处改动覆盖了文件里全部 50 个 `self.connection.execute(...)` ✓

### 顺带修掉的两个问题

1. **包装层破坏了 DuckDB 的 replacement scan**：该特性靠**当前调用帧的局部变量名**解析表名，
   包一层之后报 `Table with name symbol_info_df does not exist`。改为显式
   `register('_pylightcharts_df', df)` + `unregister`，不再依赖调用栈（`_execute_with_df`）。
2. **DuckDB 是单实例文件锁**：第二个 miniqt 实例打不开库文件，而 `get_db_manager()` 在很多
   Qt 槽里被直接调用 —— 抛异常就会静默 abort。现在 `_connect()` **不再向上抛**，改为保持
   `connection = None` 并打印清晰提示（"数据库文件正被另一个 miniqt 实例占用…"）。
   > 现场就有一个 16:36 启动后仍在运行的实例（PID 31200）占着库文件。

### 新报错：`contains non-existent instrument: FUTURE`

双击合约/右键菜单创建图表时，把**「类型」列的值** `FUTURE` 当成了合约代码传给天勤。
`on_cell_double_clicked` / `show_context_menu` 原来**写死列号**（第 1 列=代码，第 3 列=类型），
列集合一旦变化（不同数据来源）就会错位取到相邻列。

修复：改为**按表头名字取列**（`_column_index` / `_cell_text` / `_symbol_at`），并校验取到的值
形如 `SHFE.rb2610`（含 `.`），否则忽略并打印是哪一行取到了什么；`start_minibt_chart` 入口也加了
同样的校验，用 InfoBar 提示而不是抛出天勤的一大段堆栈。

### 另外

- `miniqt/__main__.py` 安装**崩溃日志**（`~/.miniqt/crash.log`：`sys.excepthook` +
  `threading.excepthook` + `faulthandler`，并直接写 fd 2 绕过 minibt 的输出重定向）。
  这类"静默闪退"以后至少能拿到堆栈。
- 新增 `tests/e2e/miniqt_login_flow.py`：用**空对象 TqApi** 驱动真实 `MainWindow` 走完整条
  登录后链路（`update_cont_quotes` → 分类/定时器 → 每日刷新 → 表格填充）。没有账号也能验证
  这条路径，而且因为崩溃是原生 abort，它同时也是一条数据库串行化的冒烟测试。
- 新增 `tests/_duckdb_mixed_load.py` + `tests/test_miniqt_db.py` 的子进程用例：读写混跑，
  原生崩溃会让测试失败而不是弄死 pytest。
- 新增 `tests/test_miniqt_columns.py`：列顺序变化时仍能取对合约代码。

### 验证

**Python 284 passed** · `miniqt_chart_check.py` `RESULT_OK` · `miniqt_indicator_check.py` `RESULT_OK` ·
`drawing_events_check.py` `RESULT_OK` · `miniqt_login_flow.py` `RESULT_OK`（含
`update_cont_quotes → 刷新 → 表格` 全链路，无异常）· `minibt_workbench.py` `RESULT_OK`

---

## ✅ 修复「主力合约停在旧合约」（中金所/上期所）

### 根因：主力列表在特定交易所为空时「静默跳过」

天勤的 `query_cont_quotes(exchange_id)` 内部依赖**主连合约（KQ.m@）的 underlying 边**。
中金所/上期所这条边缺失时它返回**空列表**，而 `_get_from_tq_api` 的流程是：

```python
if 键存在:                 # '主力'/'中金所' 存在，但值是 []
    symbol_list = ...
    if symbol_list:        # 空 → 不进入
        return ...         # ← 拿不到就什么都不返回
else:
    ...退化分支...          # ← 这里反而会把"该交易所全部期货"当成主力写库
```

于是这两个交易所**既不刷新也不报错**（do nothing），数据库里就一直是最早写进去的旧合约；
其它交易所列表正常 → 每次刷新都对 ✓ 完全对上现象。

### 修复

1. **主力合约改为多路获取**（`_main_contract_symbols`）：
   - ① `query_cont_quotes(exchange)`
   - ② **主连合约的 `underlying_symbol`**（`query_quotes(ins_class="CONT")` +
     `query_symbol_info`，与 ① 同源但走不同实现，① 返回空时 ② 通常可用）—— 实测
     中金所/上期所经此路径拿到了当前主力；
   - **拿不到就返回空并保留数据库原内容**，绝不退化成"全部期货"。
2. **删掉那条污染路径**：`_get_from_tq_api` 里把 `CONT_MAIN` 当 `FUTURE` 过滤的分支已移除，
   并在 `CONT_MAIN` 上一开始就返回，后续代码不会再有机会写坏主力表。
3. **诊断日志** `~/.miniqt/contracts.log`：每次刷新按「类型/交易所」记录结果，
   并注明主力列表来自哪个来源、拿到几个。以后一眼就能区分"没刷新"和"天勤没返回数据"。
4. **逻辑版本号** `CONTRACTS_REFRESH_VERSION`：改动取数口径就 +1，
   升级后第一次登录会**强制再全量刷新一次**——所以**不需要手动删库**；
   同一天内重复启动仍然走数据库（每天只全量一次）。

### 验证

`tests/e2e/miniqt_login_flow.py` 现在用一个「`query_cont_quotes` 返回空」的桩模拟中金所/上期所，
断言主力表经「主连 underlying」兜底被正确写入：

```
CONT_MAIN/CFFEX: ['CFFEX.IF2610']
CONT_MAIN/SHFE : ['SHFE.rb2610']
RESULT_OK
```

**Python 284 passed** · `miniqt_chart_check` / `miniqt_indicator_check` / `drawing_events_check` /
`minibt_workbench` 全部 `RESULT_OK`

---

## ✅ 修复画线工具最后一个图标（江恩扇形）不可见

### 根因（两个叠加的缺陷）

工具箱给图标上色是靠给 `<g>` 设 `fill`：

```ts
group.setAttribute("fill", window.pane.color)
```

而 **`GANN_SVG` 的三条 path 全是 `fill="none"` 且没有 `stroke`** —— 于是整个图标**完全不可见**
（按钮还在、还能点，就是没图）。另外它只画了 **3 条**射线，而这个工具实际是**从一个点发出
9 条射线**（江恩角度线 1x8 … 8x1），图标本身也不符。

同样的缺陷也影响 Fibonacci 扩展图标里那条折线（`fill="none"` + 无 `stroke` → 少一条线）。

### 修复

1. 图标容器额外设置 `color`：
   ```ts
   group.setAttribute("color", window.pane.color)
   ```
   这样需要用描边的图标写 `stroke="currentColor"` 就能拿到同一个颜色，
   而且**不影响其余 12 个填充型图标**（它们不设 `stroke`，外观完全不变）。
2. `GANN_SVG` 重画为**一个点 + 9 条射线**：原点圆点（`circle`，填充）+ 9 条 `stroke="currentColor"`
   的射线（1x8 / 1x4 / 1x3 / 1x2 / **1x1（加粗，江恩平衡线）** / 2x1 / 3x1 / 4x1 / 8x1）。
3. 顺手给 Fibonacci 扩展的折线补上 `stroke="currentColor"`。

### 验证

新增 `tests/e2e/toolbox_icons_check.py`：在真实工具箱里逐个按钮询问浏览器
「这个图标有几个图形、其中几个**真的被着色**」（`getComputedStyle` 会解析 `currentColor`，
并且把全透明视为未着色），所以空白图标会直接让检查失败 —— 这个检查在修复前必然报错。

```
drawing tools: 13
  ...
  12 shapes=10 painted=10 inked=10  stroke=rgb(216, 217, 219)   ← 江恩扇形
RESULT_OK
```

同时该脚本顺手纠正了一个测试写法：`toolbox=True` 已经会创建工具箱，
再手动 `ToolBox(chart)` 会渲染出**两套**按钮（26 个）。

**Python 284 passed** · jslib 32 passed · 浏览器 smoke `RESULT_OK` ·
`drawing_events_check` / `miniqt_chart_check` / `toolbox_icons_check` 全部 `RESULT_OK` ·
JS bundle 已重建且通过 CI 新鲜度校验

---

## ✅ 删除 qtcharts / workbench（-5673 行）

### 背景

`pylightcharts.qtcharts`（TradingView 风格 Qt 面板 + 指标选择器 + 主题 + 指标参数表）
与 `pylightcharts.workbench`（三个端口 + 会话/控制器 + 静态·回放·实时工作台）是为
「把 miniqt 的三个图表窗口统一抽出来」这个**不再进行**的迁移而写的。miniqt 保留自己的窗口，
所以这两个包成了死代码。

### 删除前的依赖核查（全仓扫描）

| | |
|---|---|
| miniqt / minibt | 只有我为工作台写的 `minibt/charting/adapter.py` 引用它们 |
| `pylightcharts/__init__.py` | 9 个懒导出 + 一处 eager `import workbench` |
| `pylightcharts/widgets.py` | 一处报错文案提到 `qtcharts.prepare_qt()` |
| tests / examples / docs | 4 个测试文件、2 个示例、3 篇文档、mkdocs nav、`gen_api_docs.py` |
| 打包 | `[tool.setuptools] packages = ["pylightcharts"]` 是**静态单包列表** → 这两个包**从未进过 wheel**，只在源码检出里可用 |

### 保留 / 迁移

- **`prepare_qt` 迁移到 `pylightcharts/qt.py`**：它不是控件，只是解决
  「QtWebEngineWidgets 必须在 QApplication 之前导入」这个真问题。4 个 e2e 检查与示例在用它。
- `pylightcharts.qtcharts.specs`（17 个指标的参数表）随之删除 —— miniqt 的指标目录来自 minibt，
  没有用它。
- `docs/api.md` 重新生成（-362 行）；README 删掉对应章节；`.gitignore` 清掉失效条目。

### 恢复方式

```bash
git checkout 4e0de3d^ -- pylightcharts/qtcharts pylightcharts/workbench
```

### 验证

**Python 174 passed**（减少的 110 项全部是被删包的测试）· jslib 32 passed ·
浏览器 smoke / `attribution_check` / `toolbox_icons_check` / `drawing_events_check` /
`miniqt_chart_check` / `miniqt_indicator_check`（6 种指标形态）/ `miniqt_login_flow` 全部 `RESULT_OK` ·
JS bundle 新鲜度校验通过 · `import pylightcharts` 依旧**不加载任何 Qt**

### 顺带

同一次提交还包含了**隐藏 TradingView 署名 logo**（默认关闭，主图+副图；
`pylightcharts.set_attribution_logo(True)` 可开回来，但它是**创建期**选项 ——
Lightweight Charts 只在创建图表时读取该选项）。可用
`tests/e2e/attribution_check.py` 验证（默认 0 个、开启后主图 1 个+副图 2 个、再关回 0 个）。

---

## ✅ miniqt：键盘精灵可用、关闭标签回退、DuckDB 自愈

### 1. 键盘精灵窗口（行情窗口）

`KeyElfWindow` 之前「能弹出来但用不了」：

- **回车失效**：焦点在 `KeyElfLineEdit`（QLineEdit）里，Enter 被 QLineEdit 先消费，
  窗口的 `keyPressEvent` 收不到；上下键在部分实现里也会被吃掉。现在把
  确认 / 上下选择 / PgUp·PgDn / Esc / 左右键统一收敛到 `KeyElfWindow._handle_key()`，
  输入框的 `keyPressEvent` 转发过去。
- **切换合约没实现**：`_on_double_click` 里原先只 `print("暂未实现")`。现在调用
  `MarketWatchWindow.switch_chart_symbol(symbol, type, widget=当前图表)`
  （该方法新增 `widget` 参数与 `bool` 返回值），成功才关闭精灵。
- **首次登录后搜不到合约**：`symbol_search_table` 只在启动时重建一次，而全新数据库是
  「启动时为空 → 登录后全量填充」，于是整个第一次会话里搜索表都是空的。
  现在 `save_symbol_info()` 在写 `symbol_info` 的同时同步 `symbol_search_table`。
- 打开精灵时若内存里还没有搜索数据会再读一次；表格行用 `setCurrentCell` 真正设为当前行；
  `WA_DeleteOnClose`，关闭 / 销毁都能正确复位快捷键标志。
- **右上角两个“X”**：`setWindowFlags(Qt.Tool | WindowStaysOnTopHint)` 是**整体替换**标志。
  qt6.10+ 的 `AcrylicWindow` 用 `Qt.WindowType.NoTitleBarBackgroundHint`（不再是
  `FramelessWindowHint`）去掉原生标题栏，直接覆盖会把这条 hint 抹掉，于是多出一个
  系统原生的“X”，和自定义标题栏的“X”并存。改为 `self.windowFlags() | ...` 叠加即可。

### 2. 关闭标题栏标签后回到上一页

`CustomTitleBar.removeTab()` 原先先 `stackedWidget.removeWidget()`，再 `tabBar.removeTab()`。
而 `TabBar.removeTab()` 内部才会调用 `qrouter.remove()` 清理返回历史并 `goToTop()`；
顺序反了以后 `QStackedWidget` 会先跳到相邻页面（常常是首页 / 设置），历史也被写脏，
于是「关哪个窗口都回首页」。现在：

- 先 `tabBar.removeTab()`（清理路由历史、切回上一页），再 `removeWidget()` / `close()`；
- 删掉写死的「没有标签就回首页」，新增 `_last_page` 记录最近浏览的导航页作为兜底；
- 关闭后台标签（当前不是它）不会改变当前页面。

### 3. DuckDB 损坏自愈

报错链是 `Failed to delete all rows from index … database has been invalidated`。
根因是旧版本并发写弄坏了**磁盘上的 ART 索引**；之后重连也没用 —— DuckDB 在进程内
按路径缓存 `DatabaseInstance`，坏实例会被一直复用，于是满屏 `重新连接失败`、数据补不全。

修复：

- `_recover_connection()` 改为**重建库文件**：关连接 → `gc.collect()` → 把 `.duckdb` / `.wal`
  改名成 `.corrupt-<时间戳>` → 重新建表。库只是行情缓存，重建后登录会重新填充。
- `_connect()` 除「被另一个进程占用」外的打开 / 初始化失败都走重建（原先只处理 WAL）。
- 删掉 `_migrate_table()` 里「迁移失败就删库文件」的危险分支（连接还开着就删文件，
  本身就是损坏来源）。
- 连接失败 / 重建只打印一次，不再每个合约批次刷屏；读方法在 `connection is None` 时
  安静返回空值。
- `save_symbol_info()` 的 upsert 抽成 `_upsert_symbol_info_df()`，顺手同步搜索表，
  恢复后重试一次。

### 验证

- `tests/test_miniqt_db.py` 新增 3 项：搜索表同步、致命错误重建文件（保留 `.corrupt-*`）、
  非致命错误不重建；
- 用真实 `MainWindow` + 桩 `TqApi` 跑 `miniqt_login_flow`，并**故意放一个损坏的
  `.duckdb`**：启动即重建，之后表格 / 主力合约全部正常，`RESULT_OK`；
- 离屏跑键盘精灵：输入过滤、上下选择、回车切换合约全部通过；
- 离屏跑 `CustomTitleBar`：关图表回行情页、关后台标签不影响当前页，均通过。

---

## ✅ 修复 `不能在协程中调用 wait_update`（行情/指标更新停摆）

`~/.miniqt/crash.log` 里刷了 **3700+ 条**同一个异常：

```
Exception: 不能在协程中调用 wait_update, 如需在协程中等待业务数据更新请使用 register_update_notify
  File "miniqt/app/view/main_window.py", line 883, in wait_update
    is_update = self.main_window.tq_api.wait_update(1)
```

tqsdk 的 `wait_update` 开头会判断 `self._loop.is_running()`，为真就抛这个错。

### 根因：工作线程在驱动 TqApi 的 loop

`Chart._fetch_kline_data()` 跑在 `ChartUpdateManager` 的**线程池**里，它调用

```python
self.api.get_kline_serial(self.symbol, self.cycle, len(self.chart.candle_data))
```

tqsdk 的序列是**按 `(symbol, duration, data_length, adj_type)` 缓存的**。这里传的是
`len(self.chart.candle_data)`，随着新 K 线不断增加，长度一直在变 → **每次都在新建序列** →
`get_kline_serial` 内部为新序列执行

```python
while not self._loop.is_running() and not serial["init"]:
    self.wait_update(deadline=...)
```

于是 TqApi 的 loop 被工作线程占住（最长 25+60 秒），主线程的 `TqApiQTimer` 每 50ms 调
一次 `wait_update` 就抛一次；`update_status_changed` 也永远发不出去，
`ChartUpdateManager.is_update_status` 卡死 → **行情/指标停止更新**。

### 修复

1. **固定 `data_length`**：`_fetch_kline_data` 与 `get_new_kline` 改用建序列时的
   `self.length`（与 `_init_chart_data` 一致），命中已有序列，工作线程不再触发
   `wait_update`。
2. **`TqApiQTimer` 加固**（`main_window.py`）：`init_update`/`wait_update` 调用前先
   `_api_loop_is_running()`，发现 loop 正忙就跳过本轮；`wait_update` 的异常一律吞掉并
   **同一个错误 30 秒只提示一次**，不再从 Qt 槽里逃出去刷 crash.log，也不再把更新状态锁死。
   `_api_loop_is_running()` 对没有 `_loop` 的测试桩 / slave 返回 False。
3. **崩溃日志去重 + 控制台不再乱码**（`__main__.py`）：
   - 同一异常 30 秒内只记一次完整堆栈，重复只计数，结束时补一条「重复 N 次」，
     避免再出现 3700 条同样的堆栈；
   - 写 fd 2 时按控制台/本地编码（Windows 中文是 GBK）而不是 UTF-8，中文提示不再变乱码。

### 验证

- 新增 `tests/test_miniqt_timer.py`：loop 运行中时定时器跳过、`wait_update` 报错被吞掉；
- 真实 `MainWindow` + 桩 `TqApi` 的 `miniqt_login_flow` 仍 `RESULT_OK`；
- 已有的 `~/.miniqt/crash.log` 可以手动删除，新的日志不会再刷屏。

---

## ✅ 真正修复：实时指标不更新（`self._kline` 快照从不刷新）

上一轮只把 `wait_update` 的异常吞掉，行情/指标不再报错，但**指标仍然不更新**。用户实测确认。

### 根因

`Chart._init_chart_data()` 里：

```python
self._kline = self.api.get_kline_serial(self.symbol, self.cycle, self.length).copy()
```

`self._kline` 是**打开图表那一刻的一次性 `.copy()`**，之后再也没有被刷新过。而：

- `Chart._fetch_indicator_data()` 直接 `return self.kline`（即 `self._kline.copy()`）；
- `Chart.datetime / new_datetime / last_datetime` 也全部读 `self._kline`。

所以：

- K 线本身通过 `_fetch_kline_data()` 每次都重新 `get_kline_serial(...).copy()` 拿到最新数据 → 看起来在更新；
- 指标却永远基于打开图表那一刻的 K 线计算 → **K 线在动、指标不动**，而且因为值不变，`line.update()` 写回同一个点，所以既不报错也不更新。

### 修复

把「活的实时序列」和「快照」分开：

- `Chart.__init__`：新增 `self._kline_serial = None`；
- `_init_chart_data()`：`self._kline_serial = self.api.get_kline_serial(...)`（tqsdk 的序列 DataFrame 会随 `wait_update` **原地更新**，
  是活对象），`self._kline = self._kline_serial.copy()` 只做快照；
- 新增 `Chart._refresh_kline_snapshot()`：`self._kline = self._kline_serial.copy()`；
- `_fetch_kline_data()`：改用 `self._kline_serial` 判断变化，并在有变化时刷新 `self._kline` 快照；
- `_fetch_indicator_data()`：返回前先 `_refresh_kline_snapshot()`，保证指标拿到最新数据；
- `get_new_kline()`（新增指标时的首屏计算）：同样从实时序列刷新；
- `cleanup()` 里一并清掉 `_kline_serial`。

### 顺带

- `_on_chart_updater_error()` 不再静默：指标/计算错误会打印出来；
- `_update_kline_ui_from_worker()` 的裸 `except: ...` 改为打印异常，K 线更新出错不再被吞；
- 指标链路加了诊断打印，默认关闭：启动前设 `MINIQT_DEBUG_INDICATOR=1` 可以看到
  `[indicator]` 的取数 / 计算 / UI 更新每一步。

### 验证

用户实测：**SMA 均线开始实时更新**。

### 后续可查

若某些指标仍不动，可开 `MINIQT_DEBUG_INDICATOR=1`，日志应能看到：

```
[indicator] ChartUpdateManager tick -> SHFE.rb2610 (charts=1)
[indicator] ChartUpdater 取数 SHFE.rb2610 rows=1000 -> worker
[indicator] worker 计算完成 1 个指标: [0]
[indicator] UI 更新 SHFE.rb2610 type=dict keys=[0]
```

其中 `fetch ... last=...` 的 `last` 应随时间推进；若它不动，说明实时序列没有推进（行情侧问题）。

---

## ✅ 修复：副图十字线与主图错开 N 根 K 线

用户反馈主图十字竖线与副图竖线错开 2 根（主图当前 K 线往前第 2 根才是副图竖线的位置）。

### 根因：副图时间轴比主图短（起点晚）

- 指标是用**实时序列**算的，序列只有最后 `self.length` 根 K 线（会滚动）；
- 主图 `chart.candle_data` 从打开图表那一刻起通过 `chart.update` **一直累积**，
  比序列多 `k` 根（`k` = 图表打开到添加指标之间形成的 K 线数）；
- 副图与主图用 `Lib.Handler.syncCharts` 按**逻辑范围**（bar 下标）同步，
  十字线却按**时间**放置。副图第一条数据比主图晚 `k` 根，于是同一个时间在副图上
  落在 `k` 个下标之前 —— 视觉上就是副图竖线左偏 `k` 根，而且 `k` 固定不变。

### 修复

在 `Chart.add_indicator()` 里把指标数据对齐到主图完整时间轴（`chart_interface.py`）：

- 新增 `_main_aligned_times(df)`：用 `self.chart.candle_data["time"]` 找出主图比
  实时序列更早的那些时间点，返回需要前补的行数与对齐后的纳秒时间轴；
- 新增 `_aligned_indicator_column(df, name, values)`：给指标列前面补 NaN 空行
  （NaN 经 `js_data` 后只剩 `{time}`，即 LWC 的 whitespace 点，只撑开时间轴、不画线）；
- 新增 `_aligned_indicator_candles(df, indicator)`：蜡烛图副图同理；
- `add_indicator` 里 4 处 `pd.concat([df["time"], indicator[col]], axis=1)`
  （2 处 line、2 处 histogram）和蜡烛图副图全部改用这三个 helper。

这样主/副图时间轴一致，按时间放置的十字线也就对齐了。

### 验证

单元验证（本地，绑定真实方法到桩对象）：

```
主图 10 根：0,60,...,540s
指标/序列只有后 7 根（主图下标 3..9）
pad = 3, aligned len = 10
sma 列：前 3 行 NaN，后 7 行 [0..6]
蜡烛图对齐后 len=10, columns=[time, open, high, low, close]
```

`ALIGN_OK`。K 线/指标实时更新链路不受影响。

---

## ✅ 去掉指标图例里的「眼睛」图标

指标标签原本是「色块 + 名称 + 数值 + 眼睛图标（隐藏时眼睛加斜线）」。因为 miniqt 已经把
「显示/隐藏指标线」做进了指标参数窗口（鼠标移到标签上弹出），图例里的眼睛是重复入口，去掉。

改动：

- `jslib/src/general/legend.ts`：
  - `LineElement` 去掉 `toggle` 字段；
  - `makeSeriesRow()` 不再创建 eye SVG / `toggle` 元素，也不再注册点击切换
    （原来点击会 `series.applyOptions({visible})`）。保留色块 + 名称 + 数值那一行。
- `jslib/src/general/styles.css`：删掉不再使用的 `.legend-toggle-switch` 规则。
- 重新 `npm run build`，`pylightcharts/js/bundle.js` 与 `styles.css` 已更新
  （bundle 里不再有 eye path / `legend-toggle-switch`）。

显示与隐藏现在只通过指标参数窗口 → `Line.hide_data()` / `show_data()`
（内部 `_toggle_data` → `series.applyOptions({visible})`）完成。

### 验证

- `jslib` 单测：**32 passed**；
- `tests/e2e/miniqt_indicator_check.py`：6 种指标形态全部 `ok`，`RESULT_OK`
  （走的就是 `create_line/create_histogram → makeSeriesRow` 这条路径）；
- 检查新 bundle：`legend-toggle-switch` 0 处、眼睛 SVG 0 处。

---

## ✅ 修复指标参数窗口的三个问题

### 1. 线型选了不生效

`set_line_style` 把 LWC 的数字枚举用引号包了起来：

```python
lineStyle: '{as_enum(style, LINE_STYLE)}'   # -> lineStyle: '2'（字符串）
```

LWC 的 `lineStyle` 只认数字（0=solid … 4=sparse_dotted），字符串会被忽略。
去掉引号即可：`lineStyle: {as_enum(style, LINE_STYLE)}`。

### 2. 初始颜色按钮与指标线颜色不一致

`IndicatorParamsCard._parse_rgb_string()` 只会解析 `rgb(...)`。而指标线颜色来自
minibt 的 hex（`#RRGGBB`）或调色板的 CSS 颜色名（`fuchsia`/`lime`…），解析失败后
一律回退成蓝色，于是打开参数窗口时颜色按钮是蓝的、线却是别的颜色；手动选一次颜色后
因为存成了 `rgb(...)` 才变正常。

改为统一用 `QColor` 解析（hex / CSS 颜色名），并额外兼容 `rgb()/rgba()`（含 alpha）。
另外 `set_line_color` 现在会同步图例里那个小方块的颜色。

### 3. `price_line` / `price_label` 开关不生效

`set_price_visible` 设的是不存在的选项：

```python
series.applyOptions({ priceVisible: ... })   # LWC 没有 priceVisible
```

LWC 正确名称是 `priceLineVisible`（价格线）和 `lastValueVisible`（价格标签）。
现在按传入的项名映射：

- `price_line`  -> `priceLineVisible`
- `price_label` -> `lastValueVisible`

`_on_price_visible_changed` 也把具体项名传给每一根线。这样开关是即时生效的，
**不需要重载/删除指标**。顺带修了「其它设置」的开关初始勾选状态（之前只设了文字、
没设 `setChecked`，重新打开窗口会显示成关闭）。

### 顺带

- `create_line_style_group` 对 `vbar` 等非线型值做了保护（`items.index(value)`
  原先会抛 `ValueError`）。
- 柱子（vbar）分支里引用了未定义的 `price_line/price_label`，改用指标级
  `price_visible` 默认值，避免潜在 `NameError`。
- `_replay_indicator_params` 里重设指标数据也改用 `_aligned_indicator_column`，
  以免点「确认」后副图时间轴重新错位。

### 验证

- 颜色解析单测：`fuchsia`/`#ff8800`/`#80ff0000`/`rgb`/`rgba`/非法值 全部正确；
- JS 选项单测：`set_line_style('dashed')` → `lineStyle: 2`；
  `set_price_visible('price_line', True)` → `priceLineVisible: true`；
  `set_price_visible('price_label', True)` → `lastValueVisible: true`；
- `tests/e2e/miniqt_indicator_check.py` 仍 `RESULT_OK`。

---

## ✅ 修复：指标弹出菜单省略号里的按钮越点越多

`createIndicatorCardMenu` 的「显示/隐藏」按钮实现是：

```python
view.removeAction(action)
new_action = Action(...)
view.bar.insertAction_from_index(1, new_action)
```

两个叠加的 bug：

1. `_CommandViewBar.insertAction_from_index` 先 `self._createButton(action)` + `_insertWidgetToLayout`，
   又调用 `super().addAction(action)` → `CommandBar.addAction`，后者会**再建一个按钮**，
   同一个 action 变成两个按钮；
2. `CommandBar.removeAction` 只把按钮控件从 `_widgets` 移除并 `deleteLater()`，
   **没有把 action 从 `QWidget.actions()` 移除**，于是 `removeAction` 只删掉「一个」按钮。

净效果：每点一次显示/隐藏，按钮净增 1 个，都堆到省略号（溢出菜单）里；重新打开才恢复。

修复：

- `createIndicatorCardMenu` 改为**单个 toggle action 原地更新**图标/文字：
  `CommandButton` 的 `setAction` 连了 `action.changed -> _onActionChanged`，
  所以 `setIcon/setText` 会立即刷新按钮，不再 remove/insert；
- 顺手修 `_CommandViewBar.insertAction_from_index`：只 `QWidget.addAction` 登记 action，
  不再走 `CommandBar.addAction` 重复建按钮；
- 给 `_CommandViewBar` 补 `removeAction`：`super().removeAction()` 之后再
  `QWidget.removeAction(self, action)`，避免 action 残留。

### 验证

离屏单测：初始 2 个按钮，连续 5 次「remove + insertAction_from_index」后
仍然是 2 个按钮、溢出隐藏 0 个、每个 action 只有 1 个按钮 → `CMDBAR_NO_ACCUMULATION_OK`。

---

## ✅ 新增：指标价格可见默认设置 + 指标「代码」源码查看

### 1. 图表设置新增「指标价格线 / 指标价格标签」

- `menuqt/app/common/chart_config.py` 新增两个配置项：
  `indicatorPriceLine` / `indicatorPriceLabel`（section `Chart`，默认 `False`），
  并加入 `DEFAULT_CONFIG` 与 `resetToDefault()`。
- `miniqt/app/view/setting_interface.py` 的 `ChartSettingInterface` 新增「指标设置」分组 +
  两个 `SwitchSettingCard`；切换时保存配置，并通过 `_main_window()` 向上找到 `MainWindow`，
  调用 `apply_indicator_price_defaults()` 立即应用到已打开图表。
- `miniqt/app/view/main_window.py` 新增 `MainWindow.apply_indicator_price_defaults()`：
  遍历 `chart_update_manager.charts`，对每条指标线调用
  `set_price_visible('price_line'/'price_label', ...)`，并同步 `Indicator.price_visible`。
- `miniqt/app/windows/chart_interface.py` 的 `add_indicator()`：
  `price_visible` 改为读全局默认值；4 处 `create_line` / `create_histogram`
  不再写死 `price_line=price_label=False`，改用 `price_visible[...]`。
  顺带把 `last_indicator.price_visible=...` 移进 `if last_indicator:`，避免指标管理器为空时崩。

### 2. 指标「代码」按钮

新增 `miniqt/app/common/indicator_source.py`：`resolve_indicator_source(class_name, name)`
按三层解析源码（解析失败的层自动跳过）：

1. **minibt 定义** `PandasTa.sma` —— `inspect.getsource(method.__wrapped__)`；
2. **minibt 调度** `CoreFunc.pta_sma` —— 由类的 `_perfixes`（`pta_`/`finta_`/`ti_`…）拼出
   `CoreFunc` 上的方法；
3. **底层实现** —— 用 `ast` 解析调度层的 `return pta.sma(...)`，从函数 `__globals__`
   取到真正的库模块，再 `inspect.getsource`（如 `pandas_ta.overlap.sma`）。

`TradingView` 等没有走 `@tobtind` 的指标，方法体本身就是实现，只返回第 1 层。

新增 `miniqt/app/windows/indicator_source_window.py`：`IndicatorSourceDialog`
（基于 `MessageBoxBase`）展示多层源码，支持下拉切换、复制、在系统编辑器中打开；
无 Python 源码（C 扩展）时给出说明。

`createIndicatorCardMenu` 里省略号的「代码」按钮接上了 `show_indicator_source(...)`。

### 验证

- `resolve_indicator_source`：`PandasTa.sma` 3 层（含 `pandas_ta/overlap/sma.py`）、
  `PandasTa.macd` 3 层、`TuLip.sma` 2 层、`TradingView.ADX_and_DI` 1 层；
- 对话框离屏构造/切层/无源码分支均通过；
- 设置页两张卡片构造/切换/保存通过；`apply_indicator_price_defaults` 桩测试通过；
- 实时 `add_indicator` 在配置开/关下 `price_visible` 分别为 `{True,True}` / `{False,False}`；
- `tests/e2e/miniqt_indicator_check.py` 仍 `RESULT_OK`。

---

## ✅ 修复：关闭指标源码窗口时无提示闪退（access violation）

`~/.miniqt/crash.log` 末尾：

```
Windows fatal exception: access violation
  (主线程停在 app.exec()，其它线程是 ChartUpdateManager 线程池 / winpty)
```

### 根因：从菜单 action 里开模态对话框（嵌套事件循环）

指标弹出菜单省略号里的「代码」按钮是在 `RoundMenu` 的事件处理里被触发的。
旧实现直接：

```python
def show_source():
    show_indicator_source(parent, ...)   # 内部 dialog.exec() —— 嵌套事件循环
```

`exec()` 会开一个嵌套事件循环。菜单/弹出层在嵌套循环期间被销毁（`deleteLater` 等），
等嵌套循环退出、回到菜单的事件处理时就会访问已销毁的 C++ 对象 → access violation。
对照：同一菜单里的「参数」按钮用的是**非模态 Flyout**，所以一直没事。

### 修复

- `indicator_card_window.py`：`代码` 的 action handler 用
  `QTimer.singleShot(0, _open)` 推迟一拍，等菜单处理完再开；
- `indicator_source_window.py`：`show_indicator_source()` 用**窗口模态、非阻塞**的
  `dialog.open()`（`finished → deleteLater`）代替 `exec()`，不再有嵌套事件循环；
  并在 `closeEvent` 里显式移除 `MaskDialogBase` 装在 window/windowMask/widget 上的事件过滤器；
- `market_watch_window.py`：「自定义周期」对话框也是从 `RoundMenu` action 里 `exec()`，
  同样加了 `QTimer.singleShot(0, ...)` 延迟打开。

### 验证

离屏用真实 `MainWindow` 连续 open/close（accept + reject）两次，无 faulthandler 输出、
`EXIT_OK`；`indicator_source_window.py` / `indicator_card_window.py` / `market_watch_window.py`
均编译通过。

---

## ✅ 新增：画线持久化（同合约同周期重开自动恢复）

### 现状盘点（骨架有、最后一公里没接上）

- `common/chart_data.py` 的 `ChartDataManager` 已有 `drawings`/`price_alerts` 与落盘，
  但 `CustomToolBox._save_drawings` **只更新内存**，从不调 `set_drawings`
  → `chart_data.json` 永远是空的；
- tag 用的是 `current_contract`（只有合约、没有周期）；
- `save_settings` / `save_default_settings` 被调用但根本没定义；
- 路径是相对的 `app/config/chart_data.json`（从别处启动会另建一份）；
- JS `loadDrawings` 只还原 5/13 种画线，且 `Ctrl+Z` 撤销后不回调保存。

### 实现

1. **存储键**：`common/chart_data.py` 新增 `drawing_key(symbol, cycle) -> "symbol|cycle"`，
   数据文件改为绝对路径，`save_data()` 改为 **临时文件 + `os.replace`** 原子写，
   `get_drawings(key, legacy_key)` 兼容旧的只用合约作键的数据，`validate_data` 过滤脏条目。
2. **写入点**：`CustomToolBox._save_drawings` → `chart_data_manager.set_drawings(tag, list)`，
   同时维护本地缓存；静态/回测图表跳过。tag 由 `CustomToolBox._drawing_tag()`
   （`chart.symbol` + `chart.cycle`）计算。
3. **读取点**：`CustomToolBox.load_drawings()` 默认按当前 tag 从 manager 读；
   `LightChartWindow` 新增 `drawing_tag` 属性，`load_settings` 只缓存当前 tag。
4. **时机**：`_init_chart_data` 里 `set(df)` 之后用 `reload_drawings()`（先清画布再加载），
   换周期也会切到新 tag；`init_toolbox` 创建工具箱后 `load_drawings()`。
5. **清除**：`clear_drawings` / `_clear_all_symbol_drawings` / `_clear_all_drawings`
   同步清 manager；去掉两个未定义的 `save_settings` 调用。
6. **JS**（`jslib/src/general/toolbox.ts`，已重新 build bundle）：
   `loadDrawings` 用 builders 映射补齐全部 13 种类型（斐波那契、斐波那契扩展、测量、
   通道、仓位、叉形线、三角形、江恩扇形…），未知类型只 `console.warn`；
   `Ctrl+Z` 撤销后补 `saveDrawings()`。

### 验证

- `tests/test_miniqt_drawings.py`：`drawing_key`、`"symbol|cycle"` round-trip、
  legacy 回退、clear、原子写无残留、脏数据过滤；
- `tests/e2e/miniqt_drawings_check.py`：真实 pylightcharts 工具箱把 13 种画线全部
  `loadDrawings` 回来，`hasToolbox: True | types restored: 13 / 13`，`RESULT_OK`；
- `miniqt_indicator_check` / `drawing_events_check` 仍 `RESULT_OK`，jslib 单测 32 passed。

---

## ✅ 修复：首次打开图表偶发 `reading 'callback'/'series'/'legend'` 报错、图表空白

### 根因：QWebChannel 桥就绪与脚本 flush 的竞态（在 pylightcharts）

错误链：

```
Critical: Uncaught TypeError: Cannot read properties of undefined (reading 'callback')
Critical: Uncaught TypeError: Cannot read properties of undefined (reading 'series')
Critical: Uncaught TypeError: Cannot read properties of undefined (reading 'volumeSeries')
Critical: Uncaught TypeError: Cannot read properties of undefined (reading 'legend')
```

`QtChart.__init__` 在 `loadFinished` 里动态插入 `qwebchannel.js`，脚本 `onload` 后才把
`window.pythonObject` 设好；而 flush 队列脚本只是
`loadFinished -> QTimer.singleShot(200, win.on_js_load)`。**冷启动**时 200ms 内桥还没就绪，
队列第一段 `window.callbackFunction = window.pythonObject.callback` 抛 TypeError；
`Window.on_js_load` 把队列拼成**一整段** JS 执行，前面一抛，后面的
`new Lib.Handler(...)` 也被跳过 → `{id}` 未创建 → 之后所有 `run_script` 都读到 undefined。
再开一次正常是因为 `qwebchannel.js` 已经缓存、桥很快就好。

### 修复（`pylightcharts/widgets.py`）

新增 `QtChart._on_load_finished()`：轮询
`typeof window.pythonObject !== 'undefined' && window.pythonObject !== null`，
就绪后再调 `win.on_js_load()`；最多等 8 秒兜底。`loadFinished` 改接它，不再用固定 200ms。

### 验证

`drawing_events_check` / `miniqt_drawings_check`（13/13 画线恢复）/ `miniqt_indicator_check`
全部 `RESULT_OK`；反复冷启动不再出现上述 TypeError。

---

## ✅ 登录后闪退（第三次）：DuckDB ART 索引损坏

### 最终定位

事件日志再次指向 `_duckdb.cp312-win_amd64.pyd` / `0xc0000409`（原生 `__fastfail`，所以
`crash.log` 里什么都没有）。拿你那份库**在副本上**稳定复现出真正的错误：

```
_duckdb.FatalException: FATAL Error: Invalid Input Error:
Failed to delete all rows from index. Only deleted 7 out of 27 rows.
```

即 `symbol_info` 的**主键（ART）索引与表数据不一致** —— 这是加写锁之前那次并发写留下的。

### 一组对照实验（都在损坏库的副本上跑）

| 操作 | 结果 |
|---|---|
| `SELECT` / 主键点查 | 正常（所以读、键盘精灵都没问题） |
| 裸 `DELETE`（autocommit） | **FAIL** |
| `BEGIN; DELETE; ROLLBACK` | OK（回滚掉了，不算数） |
| `BEGIN; DELETE; **COMMIT**` | **FAIL** ← 真正提交时才报错 |
| `CHECKPOINT` / `CHECKPOINT + VACUUM` | **FAIL**（修不好） |
| **重建表**（DROP + 从数据重建索引） | **OK** ✓ |

结论：**坏索引是粘性的，只有重建表能修**；而且一旦出过一次 fatal，DuckDB 在**进程内按路径
缓存**的 DatabaseInstance 就永久报废 —— 重连同一路径拿回来的还是它，**本进程内无法恢复**。

### 闪退的真正机制

不是"第一次失败"，而是**失败之后的连锁**：登录后要跑 **45 个刷新任务**，代码在第一个
`DELETE` 失败后仍然继续对那个废实例发语句（后面的 `DELETE`/`INSERT`，以及重建路径里的
`CREATE TABLE IF NOT EXISTS`），撞到某一次就在原生层 `__fastfail` → 无 traceback 的闪退。

### 修复

`DatabaseManager`：

1. **fatal 后立刻停用数据库**（`_disabled = True` + 关掉连接）→ 后续所有调用变成静默 no-op，
   **不再往废实例发任何语句** → 不闪退（本次运行降级为"不用数据库"，合约表走天勤实时接口）。
2. 同时在数据文件旁写一个 `.suspect` 标记：**下次启动**时没有任何实例占着这个文件，
   正好把它改名挪走（`.corrupt-<时间戳>`）并新建一个干净库，合约数据自动重新从天勤拉取。
3. 删掉了上一轮加的"进程内探针"（实测**检测不到**这类损坏：只读连接不加载 ART 索引，
   事务里回滚的 DELETE 也不会触发），避免留下无效防线。

### 你机器上的即时处理

那份损坏的库已经**改名**（没有删除）：

```
~/.miniqt/miniqt.duckdb.corrupt      70.8 MB
~/.miniqt/miniqt.duckdb.wal.corrupt   6.5 MB
```

所以**下次启动会自动新建并重新拉取合约**。确认一切正常后这两个 `.corrupt` 文件可以删掉。

### 新增测试（`tests/test_miniqt_db.py`，共 10 项）

| 测试 | 钉住的行为 |
|---|---|
| `test_a_fatal_error_disables_the_database_and_marks_it_for_rebuild` | fatal → 停用 + 标记 + 后续调用 no-op，下次启动重建 |
| `test_no_statement_is_issued_after_a_fatal_error` | **链条测试**：模拟 45 个刷新任务，断言失败后**只发出过 1 条 DELETE**、且再无任何写语句 |
| `test_the_next_start_rebuilds_a_marked_database` | 标记生效：第二次启动改名重建、恢复可写 |
| `test_the_real_corrupted_database_recovers_across_two_starts` | 用**真实损坏文件**跑完整两次启动（本机有该文件时才跑） |

### 仍然建议：换 SQLite

这次把 DuckDB 的两个致命弱点暴露得很彻底：**坏索引只能靠重建表修**、**实例按路径在进程内
缓存导致无法就地恢复**、以及这份 11,348 行的合约缓存竟然占 **70.8 MB + 6.5 MB WAL**。
SQLite 在这些方面都更合适（stdlib 自带、多进程安全、损坏时报错而不是 `abort`、同数据量约几 MB）。
要不要我迁移，你说一声即可。

### 验证

**Python 189 passed** · `miniqt_login_flow`（真实 MainWindow 走完整登录链路）`RESULT_OK` ·
`miniqt_chart_check` / `miniqt_indicator_check` `RESULT_OK`

---

## ✅ 数据库从 DuckDB 重构为 SQLite

### 为什么换

这次的三连崩把 DuckDB 在这个场景下的三个硬伤暴露完了：

| | DuckDB | SQLite |
|---|---|---|
| **多进程** | 单实例文件锁，第二个 miniqt 连打开都不行（连复制/查看都不行） | WAL：一个写 + 多个读，**第二个实例可读可写**（已实测） |
| **文件损坏** | ART 索引坏了只能重建表；实例按路径在**进程内缓存**，坏掉后重连拿回的还是它 → 本进程内无法恢复 | `PRAGMA quick_check` **确定性检测**；损坏是可捕获异常 → 直接重建文件继续 |
| **崩溃方式** | 原生层 `__fastfail`（0xc0000409），**无 traceback** → 静默闪退 | 抛出 `sqlite3.DatabaseError`，可捕获 |
| **体积** | 11,348 行合约 = **70.8 MB + 6.5 MB WAL** | 同样数据量 **几 MB**（测试断言 < 4 MB） |
| **依赖** | 需要 `duckdb` 包 | **stdlib 自带** |

### 改动

`miniqt/app/common/database_manager.py` 整体重写（**公开 API 一个都没变**，调用方无需改动）：

- **连接**：`sqlite3.connect(..., check_same_thread=False, isolation_level=None)` +
  `journal_mode=WAL` / `synchronous=NORMAL` / `busy_timeout=30000`；
- **默认库路径**：`~/.miniqt/miniqt.sqlite3`（新的文件名，旧的 duckdb 残留不受影响）；
- **串行化**：保留 `_LockedConnection` / `_LockedCursor`（所有访问持同一把 `RLock`），
  读写都不再有机会交叠；
- **事务**：新增 `_transaction()`（`BEGIN IMMEDIATE … COMMIT`，异常自动 `ROLLBACK`），
  「先清后写」这类成组操作现在真正原子；
- **DataFrame 写入**：DuckDB 的 replacement scan（`FROM symbol_info_df`）换成
  `executemany` + 值转换 `_clean()`（NaN/NaT/pd.Timestamp/numpy 标量 → sqlite3 能绑定的类型）；
- **读取**：手写 `fetchall()` + 列名构造 DataFrame（不再用 `fetchdf()`），并把 `expired`
  的 0/1 还原成 `True/False`（与 DuckDB 时代界面显示一致）；
- **DDL**：`VARCHAR/DOUBLE/BOOLEAN/TIMESTAMP` → `TEXT/REAL/INTEGER/TEXT`；
  `DESCRIBE` / `information_schema` → `PRAGMA table_info`；
- **损坏处理**：`PRAGMA quick_check` + 打开时的异常都会识别为「文件级损坏」→
  关连接、把文件挪成 `.corrupt-<时间戳>`、重建、**并在本进程内重试**（SQLite 做得到，
  DuckDB 做不到）；锁冲突等暂时性问题只记一行日志、**不重建**；
- `_disabled` + `.suspect` 标记保留为最后兜底（连重建都失败时本次运行降级为不用数据库）。

### 验证

| 项 | 结果 |
|---|---|
| `tests/test_miniqt_db.py`（重写，17 项） | **17 passed**，且更快（4.2s vs 15s） |
| 多进程共存 | 子进程同时打开/读/写，父进程随后看到对方写入的行 ✓ |
| 损坏自愈 | 往文件里写垃圾 → 重新打开时检出 `database disk image is malformed` → 自动重建，坏文件保留为 `.corrupt-*` ✓ |
| 值转换 | NaN/NaT/Timestamp/numpy 标量/bool 全部正确落库 ✓ |
| 真实 App 启动 | 创建 `miniqt.sqlite3`（4 KB，WAL），**崩溃日志无新增** ✓ |
| 全量测试 | **Python 196 passed** |
| 集成 | `miniqt_login_flow`（真实 MainWindow 走完整登录+刷新链路）`RESULT_OK`；`miniqt_chart_check` / `miniqt_indicator_check` `RESULT_OK` |

删掉的 DuckDB 专属测试：那份真实损坏库的两次启动恢复（已由「写垃圾 → 自愈」这个**确定性**测试取代）、
以及 ART 索引风暴测试（SQLite 没有这个失效模式，改为「损坏时进程内恢复」+「禁用后静默 no-op」两项）。

### 收尾

`~/.miniqt/` 下还留着旧引擎的残留，确认新库工作正常后可以删除：

```
miniqt.duckdb.corrupt       70.8 MB   （之前那次损坏的库，我先改名保留下来的）
miniqt.duckdb.wal.corrupt    6.5 MB
```

### 修复：列表字段让整批写入失败（SQLite 重构的收尾）

```
[DatabaseManager] 保存合约信息失败: Error binding parameter 33: type 'list' is not supported
```

`parameter 33` = **`trading_time_night`** —— 天勤把交易时段给成**字符串列表**
（`['21:01-02:30', '09:00-10:15']`）。DuckDB 有 LIST 类型所以以前能存，SQLite 只认标量。

更严重的是：**一行里有一个无法绑定的值，整个 `executemany` 批次都会失败** —— 所以那 45 组里
有 16 组合约**完全没落库**（日志里连续 16 条失败），这也是"合约数据全量填充完成: 29 成功"背后的真相。

修复：`_clean()` 对**非标量一律做兜底** —— list/tuple/set/dict 存成 **JSON 字符串**
（可读、可还原），其它自定义对象退化为 `str()`。这样任何一个值都不可能再让整批失败。

另外把 `CONTRACTS_REFRESH_VERSION` 提到 **3**：每日刷新今天已经跑过，版本号变化会强制
再全量刷新一次，把那 16 组补回来（不需要手动删库）。

验证：`tests/test_miniqt_db.py` 新增 2 项（列表存成 JSON、单个异常值不拖垮整批），共 **19 passed**；
`miniqt_login_flow` 的桩现在也返回列表字段，**0 次保存失败**、9 行落库、`RESULT_OK`。

---

## ✅ 修复：右键菜单删除画线没有持久化（画线"复活"）

### 现象与根因

右键菜单 → **Delete Drawing**：图形立刻消失，但**宿主保存的那份没有变**，于是重新加载画线工具时它又出现了。

`ContextMenu` 里删除只调了 `drawingTool.delete(...)`，**没有调用 `saveDrawings()`**：

```ts
let onClickDelete = () => this.drawingTool.delete(Drawing.lastHoveredObject);   // ← 少了一次保存
```

同一菜单里的 **Line Color / Line Style / Text Color** 走 `ColorPicker` / `StylePicker`，它们**是**会调用
`saveDrawings()` 的（实测 payload 里带着改后的 `lineColor` / `lineStyle`）。也就是说
"颜色、线型也没保存"的表象，其实是被"删除没保存 → 恢复的是旧快照"给掩盖了。

### 修复：把变更通知下沉到唯一的收口处

给 `DrawingTool` 增加 `changeCallback`，并在 `delete()` 里触发（`ToolBox` 传入
`() => this.saveDrawings()`）。这样**右键菜单、Ctrl+Z、以后新增的任何删除入口都会自动保存**，
不可能再漏 —— 这正是这次 bug 的教训：不要依赖每个调用点记得通知。

顺带修掉两处连带问题：

1. **Ctrl+Z 既不 detach 也不保存**：撤销时先把对象 `pop()` 出数组再调 `delete()`，于是
   `indexOf(d) == -1` 直接 return —— 图形留在画布上（没 detach）、保存也没发生。
   现在不再预 pop，统一交给 `delete()`（移除 + detach + 通知保存）。
2. 工作表里已在的改动一并保留：`loadDrawings` 补全 13 种画线类型；恢复时不回声发送保存
   （实测 `saves while loading: 0`）。

### 验证

新增 `tests/e2e/toolbox_drawings_check.py`：在真实工具箱里 stub `window.callbackFunction`
捕获宿主收到的保存内容，逐项断言：

| 检查 | 结果 |
|---|---|
| 恢复 2 根画线 | `saves while loading: 0`（不回写） |
| 改 Line Color + Line Style | payload 中 `lineColor="#123456"`、`lineStyle=2` ✓ |
| 删除 1 根 | `saves on delete: 1`，payload 只剩未被删的那根 ✓ |
| 删除最后一根 | payload 为 `[]` ✓ ← 所以不会再"复活" |
| Ctrl+Z | 1 次保存、正确 detach、剩 1 根 ✓ |

`tests/test_miniqt_drawings.py`（存储层 8 项）与 `tests/e2e/miniqt_drawings_check.py` 均通过；
全量 **Python 198 passed**、浏览器 smoke `RESULT_OK`、`toolbox_icons_check` / `drawing_events_check` `RESULT_OK`。

---

## ✅ 修复：跨周期画线位置不对

### 现象

在小时图画的线，切到日线后位置跑到别处（常常是最左边）；再切回去也不对。

### 根因（两处叠加）

1. **渲染的 x 锚在 `logical`**：`drawing/pane-view.ts` 是
   `return timeScale.logicalToCoordinate(p.logical)` —— 而 `logical` 是**bar 序号**，
   只在**保存它的那个周期**里成立。
2. 切周期后本应拿 `time` 把 `logical` 重算，但 `repositionOnTime()` 用的是

   ```ts
   this._chart.timeScale().coordinateToLogical(
       this._chart.timeScale().timeToCoordinate(point.time) || 0)   // ← 问题在这
   ```

   `timeToCoordinate()` **只认「正好是某根 bar 的时间」**。1 小时图上的 13:00 在日线上
   根本不存在对应 bar，它返回 `null`，于是 `|| 0` 把这些点**全甩到坐标 0（最左边）**。

### 保存格式：不需要改

格式本来就是 `{type, points: [{time, logical, price}], options}` ——
**`time` 才是跨周期的锚**，`logical` 只是"当前周期下的缓存"。所以：

- **不改格式、不迁移数据**；
- 要做的是**每次换周期/换数据后，用 `time` 把 `logical` 重算一遍**，并且
  **不要把 `point.time` 覆盖成当前周期的 bar 时间**（否则跨周期来回切会累积漂移）。

### 修复

- `drawing/data-source.ts` 新增 `timeToLogical()`：
  1. 先试**精确命中**（`timeToCoordinate` 有值就用它）；
  2. 没命中就在相邻两根 bar 之间**按时间线性插值** —— 于是小时图 13:00 的线在日线上落在
     「第 300 天 + 13/24」的位置，**时间段保持一致**；
  3. 早于首根 / 晚于末根则吸附到两端（不再跳到 0）。
- `repositionOnTime()` 改用它，并保持 `point.time` 原值不变。
- `ToolBox.loadDrawings()` 结束时**自动调用一次 `repositionOnTime()`** ——
  "恢复画线"这个入口自带对齐。miniqt 的切周期路径正是
  `reload_drawings()` → `load_drawings()` → `loadDrawings()`（`chart_interface.py:3626`），
  另一条 `set(df, keep_drawings=True)` 已经会调 `repositionOnTime()`，两条都覆盖了。

### 验证

新增 `tests/e2e/drawing_timeframe_check.py`：小时图（14400 根）里取 **index 7213**（13:00）造一根画线，
保存后切到日线（600 根）再恢复，最后切回小时图：

| 步骤 | 结果 |
|---|---|
| 小时图取点 | index 7213 → 时间 1730034000（13:00） |
| **切日线后恢复** | `logical = 300.5417` = **300 + 13/24** ✓（同一日期、同一时刻比例）<br>修复前这里会是 `0`（最左边） |
| 再切回小时图 | `logical = 7213.0000` ✓ 精确回到原 bar |
| 画线数量 | 两次切换后都还在（1 根） |

**Python 198 passed** · `drawing_timeframe_check` / `toolbox_drawings_check` / `drawing_events_check` /
`miniqt_drawings_check` 全部 `RESULT_OK` · bundle 新鲜度校验通过

---

## ✅ 修复：切周期后"四方框"画线丢失（点是点在 bar 空隙上的）

### 现象

1 分钟周期画了 2 根线，切到 5 分钟，**那根方框不见了**（另一根正常）。

### 根因：手画的点可能没有**时间**，只有 bar 序号

LWC 的回调里，当光标落在**两根 bar 之间**时 `param.time` 是 `undefined`（1 分钟图缩略时点进空隙里很常见）。
原来的 `_eventToPoint` 写的是 `time: param.time || null` —— 于是那个点**只存了 bar 序号**，没有时间锚。

而 `logical`（bar 序号）**只在保存它的那个周期里成立**：1 分钟图的第 300 根，放到 5 分钟图
（总共 120 根）上已经远在右侧之外 → 画线被画到可见范围之外 → 看起来就是"丢了"。
这也解释了为什么**只有其中一根**丢：另一根的两个点恰好都落在 bar 上。

顺带发现我上一轮引入的一个**精度回归**：`clampLogical` 里做了 `Math.round`，
把跨周期插值出来的小数序号抹成整数 —— 日线上整整差一天。已被 e2e 抓出来并修掉。

### 修复

1. **新画的点一定带时间**：`_eventToPoint` 在 `param.time` 为空时**吸附到最近的 bar** 取时间；
   拖动（`_addDiffToPoint`）超出数据范围时**保留原时间**，不再抹成 `null`。
   → 以后新画的画线天然是跨周期安全的。
2. **已有的无时间锚的画线不再"消失"**：`repositionOnTime()` 里，这类点只能沿用旧周期的 bar 序号，
   于是**整根画线按溢出量左移**回到可见范围 —— 特意不是逐点夹取，否则方框的两个点会一起贴到
   最后一根 bar 上、变成一条线（形状要保住）。
3. **跨周期映射改为不依赖布局**：`timeToLogical()` 现在**只用当前周期的 bar 时间数组做二分
   查找**（精确命中 → 命中；落在两根之间 → 按时间线性插值；超出范围 → 吸附两端）。
   之前先试 `timeScale().timeToCoordinate()`，而它在图表尚未渲染、尺子宽度为 0 时会返回
   一个**错误的坐标（实测是 0）而不是 `null`**，于是点被映射到任意位置。

### 验证

`tests/e2e/drawing_timeframe_check.py` 现在同时覆盖两种情况：

| 步骤 | 结果 |
|---|---|
| 小时图取 index 7213（13:00）造一根**有时间**的趋势线 | — |
| 另造一根**没有时间锚**的方框（`time: null`，logical 2000/2100，只在小时图上成立） | — |
| 切到日线（600 根）后恢复 | 趋势线 `logical = 300.5417`（= 300 + 13/24，**精度未被取整**）✓ |
| | 方框被滑回范围内（0 ≤ logical ≤ 599）且**宽度仍为 100**（形状未丢）✓ |
| 再切回小时图 | 趋势线 `logical = 7213.0000`；方框仍是 2000/2100 ✓ |

断言里明确包含"**不能跑到图外**"与"**形状不能塌缩**"两条 —— 前者就是这次"画线消失"的判据。

**Python 198 passed** · `drawing_timeframe_check` / `toolbox_drawings_check` / `drawing_events_check` /
`miniqt_drawings_check` / `toolbox_icons_check` 全部 `RESULT_OK` · 浏览器 smoke `RESULT_OK`

---

## ✅ 处理启动时刷屏的 Chromium SSL 报错

```
[30184:14768:...] handshake failed; returned -1, SSL error code 1, net_error -101
```

**先确认这不是我们的问题**：把图表页面的全部资源扫了一遍，`index.html` 只引用了本地的
`styles.css` / `lightweight-charts.js` / `bundle.js`，bundle 里的"URL"只有 XML 命名空间
（`http://www.w3.org/...`）和注释里的 Apache 许可链接 —— **整个页面不发起任何外部请求**。

那几行来自 **QtWebEngine 里 Chromium 自己的后台联网**：组件更新、域名可靠性、安全浏览查询、
崩溃上报等，只要第一张页面加载就会去连 Google 的端点；网络被拦截/离线时就刷出握手失败。

修复（`miniqt/__main__.py`，沿用既有的 `--ignore-certificate-errors` 那一处）：

```python
os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = ' '.join([
    '--ignore-certificate-errors',
    '--disable-background-networking',            # 组件更新 / 域名可靠性 / 各种 ping
    '--disable-component-update',
    '--disable-domain-reliability',
    '--disable-client-side-phishing-detection',   # 安全浏览查询
    '--disable-breakpad',                         # 崩溃上报
    '--disable-sync', '--no-pings',
    '--no-first-run', '--no-default-browser-check',
    '--disable-features=Translate,OptimizationHints,MediaRouter',
])
```

同时把这段做法写进 `pylightcharts/qt.py` 的 `prepare_qt()` 文档 —— 任何用 pylightcharts 的
Qt 应用都会遇到同一件事。若仍有零星输出，再补一个 `--log-level=3` 可以彻底静音 Chromium
自己的日志（代价是连真正的 GPU 警告也看不到，文档里注明了）。

验证：本机启动输出里 `handshake|net_error|ssl` 计数为 **0**；`miniqt_chart_check`、
`drawing_timeframe_check`、浏览器 smoke 全部 `RESULT_OK`；**Python 198 passed** —— 这些 flag
不影响渲染。

---

## ✅ 修复：画线改回严格按「合约 + 周期」分开（切周期不再串）

### 你指出的问题

存储键其实**已经是** `合约|周期`（`drawing_key(symbol, cycle)`、`_drawing_tag()` 都用它），
但**切周期这条路把两套混在了一起**，表现就是"只按合约存"：

1. `_init_chart_data()` 里用的是 `self.set(df, True)`（`keep_drawings=True`）——
   切周期时把**旧周期的画线留在了画布上**。此后在新周期上做的任何编辑（拖动 / 改色 / 删除 /
   甚至只是画一根新线）都会存进 **新周期的键**，两个周期的画线于是合并 ✗。
2. 切周期后**没有加载新周期自己那一套** —— 只有 `_use_default_data()`（无数据兜底路径）
   才会去 `reload_drawings()`。

### 修复（`miniqt/app/windows/chart_interface.py`）

- `Chart.reload_chart(cycle)`：切换期间置 `self._switching_cycle = True`，数据就绪后
  再 `self.toolbox.reload_drawings()` —— 即"**先清画布（不动已存数据）→ 再按新周期加载**"。
- 新增 `Chart._keep_drawings_on_set` 属性：**同一周期重新拉数据 → 保留**（画线不闪、并按时间
  重新对齐）；**切周期 → 不保留**。5 处 `self.set(df, True)` 全部改为
  `self.set(df, self._keep_drawings_on_set)`。
- 清画布走的是 pylightcharts 的 `keep_drawings=False` → JS `toolBox.clearDrawings()`，
  **只清画布、不碰存储**（所以旧周期那一套安然无恙）。

于是现在的行为正是你要的：**同一合约的每个周期各有一套画线**，互不干扰，各自持久化。

### 验证

新增 `tests/e2e/miniqt_drawings_cycle_check.py`，三层断言：

| 检查 | 结果 |
|---|---|
| `DEMO|60` 与 `DEMO|300` 各存一套 | 相互独立 ✓；重开后两套都在 ✓；清空其中一个不动另一个 ✓ |
| 某个周期没存过（`DEMO|900`） | 返回空 ✓（不会回退到别的周期）|
| `_drawing_tag()` | 随当前周期 → `DEMO|300` ✓ |
| `_keep_drawings_on_set` | 平时 `True`、切周期时 `False` ✓ |
| 真实工具箱：载入 1 根 → `set(..., keep_drawings=False)` | 画布 **0 根** ✓、**0 次保存** ✓（旧周期数据未被写坏）|

**Python 198 passed** · `miniqt_drawings_cycle_check` / `drawing_timeframe_check` /
`toolbox_drawings_check` / `miniqt_login_flow` / `miniqt_chart_check` 全部 `RESULT_OK`

---

## ✅ minibt 图表改用 pylightcharts（实时 / 回放 / 静态回测图）

`minibt/strategy/light_chart.py`（**实时**）和 `minibt/strategy/light_chart_replay.py`
（**回放 + 静态回测图**——`Bt().run(gui=Gui.LightChart)` 走的是 `_strategy_light_chart_display`
→ `display_only=True`，所以教程 `tutorials/strategy/cci.py` 其实是这个文件）以前是这样用图表库的：

```python
_builtins.__import__ = _blocked_import          # 拦掉 PySide6
from lightweight_charts.abstract import Line, Candlestick, AbstractChart
_builtins.__import__ = _original_import
...
lightweight_charts.using_pyside6 = False
lightweight_charts.widgets.QWebEngineView = QWebEngineView   # 逐个替换成 PyQt6 的对象
```

即"拦 import + 导入后替换模块全局变量"来强制 PyQt6。改用 `pylightcharts` 后这些都不需要：
它用 `$PYLIGHTCHARTS_QT` 选绑定，`prepare_qt('PyQt6')` 就是"选定绑定 + 导入 QtWebEngineWidgets"。

### 一个必须遵守的顺序

Qt 拒绝在 `QApplication` 之后导入 `QtWebEngineWidgets`：

```
ImportError: QtWebEngineWidgets must be imported or Qt.AA_ShareOpenGLContexts
must be set before a QCoreApplication instance is created
```

而 `pylightcharts.widgets` 在 import 时就会导入它。原代码之所以没踩到，是因为 `main()` 里
**先** `from PyQt6.QtWebEngineWidgets import QWebEngineView` 再建 app。所以两个文件都在
建 app **之前**调用 `prepare_qt('PyQt6')`。

### 改动（每个文件 4 处，均已应用）

| # | 位置 | 原 | 现 |
|---|---|---|---|
| 1 | 模块顶部 import 段 | `_builtins` 拦 PySide6 + `from lightweight_charts...` | 删除拦截，改 `from pylightcharts.{util,abstract,drawings,toolbox} import ...`（名字不变） |
| 2 | `get_chart_class()` | 建 app → 导入 PyQt6 webengine → 定义 `Bridge` → 替换 `lightweight_charts.widgets.*` | `prepare_qt('PyQt6')` → 建 app → `from pylightcharts.widgets import QtChart` |
| 3 | `main()` | app 前 `from PyQt6.QtWebEngineWidgets ...` | app 前 `from pylightcharts.qt import prepare_qt; prepare_qt('PyQt6')` |
| 4 | `main()` 建窗口前 | `import lightweight_charts.widgets` | `import pylightcharts.widgets` |

`light_chart.py` 的 `class Chart` docstring 也顺手从 "lightweight_charts Chart类" 改成
"pylightcharts Chart类"。除 import 与 `get_chart_class()` 外**没有改任何业务逻辑**。

### 实时图为什么不在自动检查里

实时窗口需要天勤账号：`Bt(live=True).run()` 会 assert `Bt._api`，策略向它要 account/position，
而窗口读的 `dataset.tq_object` 只有真实 `TqApi` 才会持续更新（本地数据那条路径里它是 `None`）。
所以自动化只覆盖到 import 边界（模块确实来自 pylightcharts、`get_chart_class()` 返回
`pylightcharts.widgets.QtChart`），**实时窗口本身由你用真实账号验证**。

### 验证

`tests/e2e/minibt_charts.py`（新增）：走**真实入口**，只在 `MainWindow.show` 外面包一层，
等窗口出来后读 JS 的 canvas 数、再读 `chart.chart.candle_data` / `._lines` 断言。

| 模式 | 入口 | 结果 |
|---|---|---|
| static | `Bt().run(gui=Gui.LightChart)` | `ReplayChart` · 10000 根K线 · 2 条指标线 · 14 canvas · `RESULT_OK` |
| replay | `Bt(replay=True).run(period_milliseconds=200, gui=...)` | `ReplayChart` · 300 根 · 2 条 · 14 canvas · `RESULT_OK`（截图 850×412 真图）|
| live | `light_chart.get_chart_class()` | `chart module = pylightcharts.widgets` · `RESULT_OK` |

- 三种模式 `ALL_MODES_OK`；静态模式下图表所在 web view 不在最前（`visible False`），
  截图是细条，所以以 candles/series/canvas 计数为准。
- `tests/test_lwc_compat.py` 新增守卫 `test_migrated_minibt_charts_import_pylightcharts_directly`：
  断言这两个文件不再 import `lightweight_charts`、确实 import `pylightcharts`、调了
  `prepare_qt('PyQt6')`、且不再用 `using_pyside6` 强绑（别名会让回归静默通过，所以要专门守）。
- **Python 205 passed**；`miniqt_chart_check`（走 `install_alias` 别名路径）`RESULT_OK`。

### ⚠️ 环境陷阱：两个 minibt 副本

`git check-ignore` 确认 `minibt/` 被忽略，所以这些改动**只存在于你的工作区**（不在 git 里，
本文件即变更凭据）。同时 `python`（git bash 默认解析到 hermes venv）**另外**还装了一份
未修改的 minibt 1.2.8 在 site-packages：

```
tutorials/*.py 直接跑        → 命中 site-packages 那份（带旧的 lightweight_charts）✗
经 miniqt 启动 / 带 PYTHONPATH → 命中仓库那份 ✓
```

所以单独跑教程要 `PYTHONPATH=<仓库>`，或把 site-packages 那份卸掉/同步，否则会以为迁移没生效。

---

## 约定：未完善功能集中记录

`docs/advanced/deferred.md`（**Deferred features and known gaps**）用于集中记录
"能做但暂时不做"的功能与已知边界：多图表布局的触屏拖动、网格布局、
销毁图表、`zOrder`、引擎 1px pane 分隔线、`Lib.invokeOptional`、
`Window.handlers` 类属性共享、Qt/wx/Jupyter/Streamlit 未验证项、以及那条
既有失败测试 `tests/test_phase2.py::test_precision_and_hide_data`（条目 11）。

每条包含：现象 / 为什么暂缓 / 代码位置 / 实现思路 / 验证方式。以后同类问题
先记到该文档（README 的 *Development → Deferred work*、`docs/index.md`、
mkdocs 导航、API 覆盖路线图都有入口），不要在源码里留无上下文的 `TODO`。

---

## ✅ 倒挂图标 / 整站主题 / 图例眼睛 / 十字线提示

本轮四个改动，都已经有测试与文档：

1. **价格倒挂时 ZigZag 图标反了**：marker 的位置是屏幕相对的（`aboveBar` /
   `belowBar`），倒挂后高点画在下方，箭头却还朝下。现在 Python 侧记住
   `invertScale`（`price_scale(invert_scale=)` / `PriceScale.invert()` /
   `apply_options(rightPriceScale={'invertScale': True})` 三条路径都会记），
   `mark_swings` / `add_zigzag` 会同时翻转标记的**位置与箭头**，并且倒挂发生在
   ZigZag 之后时会自动重画（`_remark_scaled_markers`）。`inverted=` 可显式覆盖。
2. **整站浅色 / 深色主题**：`chart.win.theme('light'|'dark')`（或 `chart.theme(...)`）
   一次套用根 CSS 变量（顶栏 / 图例 / 菜单 / 悬停态）+ 每张图的背景 / 网格 /
   十字线 / K 线 / 成交量 / 分隔条 / 坐标轴，后建的图自动继承，已有表格由
   `Table.set_colors` 重新上色（显式传色的表格不跟随）。调色板在
   `pylightcharts/themes.py`（`LIGHT` / `DARK` / `resolve`），之后任何单项 setter
   都会覆盖主题。示例 `examples/11_api_tour/15_themes.py` 顶栏 switcher 可运行时切换。
3. **图例眼睛图标**：原来描边写死 `#FFF`，浅色主题白底白图标看不见。改成
   `stroke: currentColor`，跟随 `legend(color=...)` / 主题文字色；悬停底色仍用
   `--hover-bg-color`。e2e smoke 断言 `legendEyeColor`。
4. **十字线提示**：按官方 tutorials/how_to/tooltips 实现了 **tracking**（跟随光标、
   靠边自动翻边）与 **magnifier**（贴窗格顶部、只沿时间轴滑动、半透明竖条），
   第三种 floating 按需求不做（见 `docs/advanced/deferred.md` 条目 25）。
   用法：`series.tracking_tooltip(...)` / `series.magnifier_tooltip(...)`（`chart.`
   作用于主 K 线）；选项 `title` / `fields='auto'` / `field_labels` / `decimals` /
   `time_format` / `color_by_candle` / 尺寸与配色；运行期 `apply_options` /
   `set_title` / `set_fields` / `set_mode` / `show` / `hide` / `visible` / `options` /
   `remove`。背景与数值默认取主题 CSS 变量，标题与边框默认取序列颜色。示例
   `examples/11_api_tour/16_tooltips.py`，文档 `docs/guide/tooltips.md`。

5. **双标的 / 双价格刻度 + 蜡烛叠加**（官方 Two Price Scales 教程）：新增
   `pylightcharts/overlay.py` 与 `chart.add_symbol(name, data, kind=, scale='left',
   margins=, up_color=, down_color=, color=, line_width=, price_line=, price_label=,
   legend_toggle=)`：自动把目标刻度设为可见、序列建在该刻度上、用 `price_line(title=)`
   给「最后一价」标签写上标的名称；`chart.scale_margins(right=, left=)` 控制两条刻度
   的上下占比（重叠 or 上下分割）。K 线保持在右刻度（按使用习惯），另一标的在左刻度；
   `kind='candles'` 即为蜡烛叠加（border/wick 跟随涨跌色）。顺带放开 `SeriesCommon.set()`
   的一个限制：OHLC 数据 + 标的名现在可以共存（单值序列仍按列名匹配、报错保留）。
   示例 `examples/11_api_tour/17_two_symbols.py`，文档 `docs/guide/two-price-scales.md`。

6. **左侧刻度出现时左上角图例重叠**：LWC 的 pane 元素（`getHTMLElement()`）**横跨两侧
   价格刻度**，所以图例原来固定 `left: 10px` 会压在左刻度的数字上；同样地，tooltip 的
   `_paneBox` 也把「窗格绘图区」当成了整个 pane 元素（`param.point` 是相对绘图区的，
   左侧刻度可见时整体偏左约 64px）。现在两者都按「pane 元素原点 + 左侧刻度宽度」和
   `chart.paneSize()` 计算绘图区：图例锚在刻度右侧，`Legend.updatePosition()` 会在
   每次十字线移动、`reSize()`、以及 pane / 容器布局变化（ResizeObserver +
   MutationObserver，同一值不重复写以免自触发）时重新校准。e2e smoke 新增
   `legendClearsLeftScale` 与 `tooltipAccountsForLeftScale` 两条精确断言；布局实测
   数据见 `_diag_legend_anchor.py`。

修的两个 tooltip bug（都已加 smoke 防回归断言）：

- tracking 框原来写死 `height: 80px`（教程只有三行内容），加了 OHLC 行后内容
  136px 被裁掉一半 → 改成默认 `height: auto` 随内容自适应，显式 `height=` 才固定；
- 下边框从来没画出来：`style.border = ...` 之后再 `style.borderBottom = ''` 会
  **删除**下边框 longhand（而不是回退到简写）→ 现在显式写全四边；顺带把放大镜
  竖条圆角按教程改成 `4px 4px 0 0`。

7. **无限历史**（官方 demos/infinite-history）：新增 `pylightcharts/history.py` 与
   `chart.infinite_history(loader, page=, threshold=, spinner=, on_load=,
   on_exhausted=, max_requests=, autostart=)`。触发用的是仓库自带的
   `events.range_change`（就是 `barsInLogicalRange().barsBefore`，已节流）：可见区
   左边剩余不足 `threshold` 根时，向 `loader(count[, before])` 要至少 `page` 根更早的
   数据，prepend 后重新下发（引擎锚定的是可见**时间**区间，所以视口不跳）。`before`
   是当前最早一根的 `pd.Timestamp`；返回 DataFrame / Series / `None`（== 没有更早的了，
   置 `exhausted`）；与现有数据重叠的 bar 以现有为准，合并后按时间排序。
   **指标会自动跟随**：主图（`add_sma`）走的是 `chart.set(frame, keep_drawings=True)`
   → `_refresh_indicators(full=True)`，把每个指标按**整段**数据重算并重发，所以主图
   指标和副图指标（如 `add_rsi(pane_index=1)`）都一直往前延伸，且拼接口附近的指标由
   "半截窗口"变成完整窗口的准确值；成交量重发、工具箱画线保留。示例
   `examples/11_api_tour/18_infinite_history.py`（主图 SMA 50 + 副图 RSI 14 +
   顶栏文本框显示已加载根数），文档 `docs/guide/infinite-history.md`。已知边界见
   `docs/advanced/deferred.md` #28（loader 跑在回调线程上，慢查询会卡住窗口）。

8. **方向键向下（缩小）在最后一根 K 线可见时不再向右扩张**：新增
   `Handler._rightmostBarX()`（用 `dataByIndex(MAX, NearestLeft)` 取最右一根 +
   `timeToCoordinate` 映射到窗格坐标，因此数字 / 字符串 / business-day 时间都通
   用），向下缩小时若最右一根已经在可视区内（`0 <= x <= paneWidth`），就把 `to`
   固定在当前右边缘、把新增宽度全部给左侧；最后一根在右边界外时仍是原来的"以窗口
   中心缩放"。e2e smoke 新增 `arrowZoomRightClamp`（先验证真实坐标在窗格内，再分别
   用 spy 造出"在里面 / 在外面"两种情况断言调用参数），既有 `arrowKeys` 断言同步
   调整为"右边缘不动 + 宽度 ×(1+step)"。文档 `docs/guide/events.md` 与 README 行
   已更新。

9. **指标副图改用原生 pane + 正常移除指标**：`series.delete()`（Line / Histogram /
   BridgeSeries 三处）现在会连**图例标签**一起摘掉（`removeSeries` 传的是 handle 引用，
   这点之前修过），并通知图表做 pane 记账：pane 里最后一个序列被摘掉后，引擎会自动
   把清空的 pane 去掉（`chart-model.ts:1277`，`preserveEmptyPane` 的除外），因此
   `_pane_count` 递减、后面的 pane 与 `series.pane_index` 自动上移；`add_pane` 现在
   记住 `preserve_empty` 的 pane，`remove_pane(index)` 也会同步记账。新增
   `SeriesCommon.pane_index`、`AbstractChart.remove_series()/`_forget_series`/
   `_shift_panes_up`。案例 `examples/11_api_tour/19_indicator_panes.py`（顶栏 switcher
   切换 RSI / MACD / CCI / none，按钮对比"保留空 pane"），测试 `tests/test_panes.py`
   （12 个）+ e2e smoke `paneLifecycle`（真实引擎：建 pane+序列 → 删序列 → 图例行与空
   pane 一起消失），文档 `docs/guide/panes.md` 新增"Removing an indicator"一节。
   另外 `tests/e2e/smoke.py` 现在自己把仓库根加到 `sys.path`，从任何目录都能跑。

10. **19 号案例加了"删除最后一个副图"按钮**：`remove_last_pane()` 先按 pane 索引找出该
   pane 里的序列逐个 `series.delete()`（最后一个删掉时空 pane 由引擎自动去掉），若这个
   pane 是 `add_pane(preserve_empty=True)` 建的（还留着）再 `remove_pane(index)`，并同步
   `SUBPLOT` 记账；返回是否真的删掉了。顶栏三个控件现在是：`indicator` switcher（RSI /
   MACD / CCI / none）、`keep` 按钮（对比保留空 pane）、`remove_pane` 按钮。测试
   `tests/test_panes.py` 加到 15 个（含保留空 pane 也一起被删掉、只剩主图时返回 False、
   按钮确实被注册），文档 `docs/guide/panes.md` 与 tour README 同步。

11. **minibt：1/2/3 已落地（两份副本保持一致）**。`Desktop\minibt\strategy` 与
   `pylightcharts\minibt\strategy` 的 `light_chart.py` / `light_chart_replay.py`
   现在**逐字节相同**：

   * **清理**：`Chart` 里 12 个被后面同名定义覆盖的死方法删掉（用 AST 定位、保留最后
     一份；注意 `@property` + `@x.setter` 这类同名访问器不能删，第一次跑就踩到了
     `@price_alert.setter` 找不到 getter 的 NameError，已改成"属性访问器整组保留"）；
     `light_chart_replay.py` 删掉已停用的 `SeriesCommon.set` NaN 分段补丁（118 行）、
     从未实例化的 `CustomToolBox`（100 行）和随之无用的 `SeriesCommon`/`ToolBox`/`lw_json`
     导入；两份副本同步了 `create_histogram` 的新签名（第 5/6 个位置参数是价格轴上下
     边距，不是 `price_scale_id`）。
   * **键盘**：`Chart.__init__` 里把窗口的事件过滤器装到 **webview** 上（原来装在窗口
     自己身上，Qt 把按键发给焦点控件，`obj == webview` 那支是死代码）+ `setFocus()`；
     事件过滤器只保留 pylightcharts 没有的键（`+`/`=`/`-`/空格），方向键交给页面内的
     内置导航（缩放锚中心、平移按 `keyboard_step`，语义一致，返回 True 会吞掉事件所以
     不能拦）；`light_chart_replay.py` 里补了 `setFocusPolicy` + `setFocus()`。
   * **自检**：两个模块各加 `check_environment()`（启动时打印 pylightcharts / minibt
     来自哪个文件、bundle 里有没有 `_handleArrowKey`、`add_pane`/`remove_pane` 是否存在），
     在 `main()` 里 `prepare_qt` 之前调用。实测输出 `version 0.1.0 / keyboard True /
     panes True`，并且两个模块都能正常 import。

   剩下的第 4 步（副图 `create_subchart` → 原生 pane）还没动，见下一条。

12. **修掉"指标线画到 1970 年"的根因（epoch 单位推断）**：19 号案例的副图指标原来把
   `chart.candle_data['time']`（**epoch 秒**）回传给 `series.set()`，而 `_set_interval`
   / `_df_datetime_format` 里 `pd.to_datetime(裸数字)` 会当成**纳秒**，于是指标线跑到
   第一根 K 线之前（1970），页面上就只剩图例色块、线看不见。现在把单位推断抽成
   `util.infer_time_unit()`（秒 / 毫秒 / 微秒 / 纳秒按量级判断），`_set_interval`
   （真正第一次解释 time 的地方）、`_df_datetime_format`、`_single_datetime_format`
   与 `history.to_datetimes` 全部复用它 —— 于是"把 `candle_data['time']` 原样回传"
   这条最常见的写法终于正确。验证：`tests/test_time_units.py`（9 个：四种单位同一时刻、
   candle_data 往返、datetime 字符串、datetime 索引、helper 本身）+ 19 号案例新增
   "指标时间轴与 K 线对齐" 两个测试；渲染实测 RSI 颜色像素 2932 个都落在副图区
   （底部 152px），中间区域 0 个（`_diag_pane_indicator.py`）。文档
   `docs/guide/charts.md` 新增 "Time column units" 一节。

13. **minibt 第 4 步：副图 `create_subchart` → 原生 pane（两份副本同步）**。加了
   `IndicatorPane` 适配器（`light_chart.py` 与 `light_chart_replay.py` 各一份），
   保留原副图对象的方法名，上层业务代码基本不用改：

   * 建序列：`create_line` / `create_histogram` / `set`（OHLC → 蜡烛图主序列）；
   * 更新：`update` / `update_from_tick`（tick 合并进本 pane 的"打开中"那根 K 线）；
   * 样式：`layout` / `grid` / `legend` / `crosshair` / `watermark` 转发给主图
     （pane 与主图共用一个 chart）；`resize`/`fit` 变成空实现；
   * `remove()`：逐个 `series.delete()`，最后一个删掉后空 pane 由引擎自动去掉；
   * `is_pane = True`：主图里"按图表切分 DOM / 固定价格轴宽度 / 只留最后一根 X 轴"、
     `add_chart_separator_lines`、`_resizes` 等老逻辑遇到它自动跳过（pane 模式下没有
     意义：一条 webview、一条时间轴、引擎自带分隔条）；`_indicator_pane()` 里用
     `set_pane_stretch(0, 3.0)` 保持原来"主图 3 : 每个副图 1"的高度比例。

   替换了 `light_chart.py` 4 处、`light_chart_replay.py` 5 处 `create_subchart('bottom',
   sync=True)`；清理逻辑对 pane 改为 `subchart.remove()`；`self.subcharts` 键名不变
   （值换成适配器），type 注释改成 `dict[str, object]`。补丁脚本
   `scripts/patch_minibt_step4_panes.py` 留档。

   验证（本机无法起 QtWebEngine，所以用"假 wrapper + HeadlessChart"直接跑适配器）：
   `_diag_minibt_pane.py` 覆盖建线/建柱/`set` 蜡烛/tick 合并/样式转发/移除，并在过程中
   抓出并修掉三个 bug —— ① `_last_bar or {}` 对 pandas Series 取真值报
   "truth value is ambiguous"；② `SeriesCommon.update` 收 pandas Series，传 dict 会在
   `_series_datetime_format` 里炸；③ tick 合并原来从 `series.data` 取"最后一根"，而
   `update()` 只把打开中的那根放在 `_last_bar`（`data` 要等下一根才写回），会丢掉
   运行中的 high/low。现在结果：`high 101 -> 123 / close 201 -> 123`，连续第二个 tick
   `high kept: True`，`after remove: panes 3 -> 1 | series left: 0`。另外 `py_compile`、
   真实 `import`（两个模块）、两份副本逐字节一致都已确认。

14. **"图表一片空白"的两个 JS 级根因（第 4 步的收尾）**：minibt 的 `gui='light_chart'`
   实测空白，排查到适配器里两处会把整批脚本打断的调用 —— 这套桥接是**批量下发**的
   （同一批里一条 JS 报错，后面的语句全部跳过，包括主图数据），所以：

   * `create_line(style='solid')` 原样把字符串枚举传给引擎（`lineStyle: 'solid'`），
     LWC 的 `lineStyle` 要数字（`solid` → 0），`applyOptions` 直接抛错 → 现在用
     `util.as_enum(style, util.LINE_STYLE)` 转换（实测发出的脚本是 `"lineStyle":2`）；
   * `_indicator_pane()` 里那次 `set_pane_stretch(0, 3.0)` 是多余的一次
     fire-and-forget 调用，pane 默认比例本来就是主图 2 : 副图 1，一旦它出错就会连累
     同一批 → 已删除（要 3:1 的话可以在建完图、webview 加载后单独调
     `chart.set_pane_stretch(...)`）。

   同时补一句给排查用：minibt `main()` 里的 `qInstallMessageHandler` 会打印 JS 控制台
   错误（形如 `JS: ...`），空白/异常时先看有没有这类行。

15. **空白图根因（QtWebEngine 的 QWebChannel 桥）+ 三档注入**：表现是"窗口在、图全白"，
   探针（纯 pylightcharts + QtChart）就能复现，和 minibt、和我的改动都无关。定位过程：
   页面 `loadFinished success=True` + `readback: None` + `js: Uncaught SyntaxError:
   Unexpected token '}'`，而**同一份 index.html + bundle.js 在 Edge 里没有任何 JS 错误**，
   `node --check` 也通过；`PyQt6.QtCore.QFile(':/qtwebchannel/qwebchannel.js')` 能读出
   16,509 字符（内容完好）。真正的问题在**把桥交给页面的方式**：

   * 旧代码往页面插 `<script src="qrc:///qtwebchannel/qwebchannel.js">` —— 跨源，
     出错只报一句跨源的 `Script error.`（`ONERROR Script error. @ ?:0:0`），
     `window.pythonObject` 永远不存在；
   * 接着队列里的**第一条**语句 `window.callbackFunction = window.pythonObject.callback`
     抛错，而脚本是**批量**下发的 —— 同一批里的 `new Lib.Handler(...)`/`setData`
     全被跳过，于是白屏。

   修法（`pylightcharts/widgets.py` + `abstract.py`）：

   1. 默认：从 Qt 资源读出 `qwebchannel.js` 文本，**落到包目录** `pylightcharts/js/
      qwebchannel.js`，页面用同源 `<script src="./qwebchannel.js">` 引入（`runJavaScript`
      只发 4 行），既不受跨源限制也不受载荷大小限制；
   2. `PYLIGHTCHARTS_QWC_URL=0` → 直接注入 16KB 文本；
   3. `PYLIGHTCHARTS_QWC_FALLBACK=1` → 退回旧的 `qrc://` 方式；
   4. 桥赋值那句包了一层 try/catch：桥没就绪只影响回调，**图表照常渲染**（`console.warn
      "pylightcharts: web bridge not ready"`）。

   用户实测三档**都能出图**（控制台里剩下的是浏览器扩展的噪声，与页面无关）。另外
   `jslib/tsconfig.json` 的 `target` 从 `ESNext` 降到 `ES2018`（QtWebEngine 的 Chromium
   与 Edge 版本不同，语法降级更稳），bundle 已按新 target 重建（`keyboard: True`）。

