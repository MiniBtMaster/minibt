# minibt 更新日志

本文件记录 **minibt Python 包** 的发布信息；完整的产品更新（含 desk / miniqt /
VS Code 扩展）请同时参考：

- 官网更新日志：<https://www.minibt.cn/changelog/>
- 仓库完整记录：`minibt_docs/docs/changelog.md`

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

> 现状口径（**v1.3.9 收口**，历史轮次里的数字保留当时原样）：
> **MCP 工具 74 个**（新增 `desk_pi` / `desk_vscode`；`CORE_TOOLS` 34 个）·
> desk 命令 **277 条**（覆盖 227 / 🔒 只走专用工具 37 / 前端内部 13 / **待补 0**）·
> 测试 `pytest -k "desk or packaging"` **2131 passed / 1 skipped**。
> 生成器：`python scripts/desk_tool_matrix.py --write`。

## [1.3.9] - 2026-11-22

> **合并发布**：原 1.3.9（文档轮）+ 原 1.3.10（三版本支持 / Rust 指标库 /
> 交易系统 / 通达信 / desk 大修）→ 统一发布为 **1.3.9**。
> **Python 公共 API 零破坏**；配套前端 **`pylightcharts 0.2.3`**。
> 以下条目按主题归类，完整细节（原因 / 代码 / 测试数据）见
> `minibt_docs/docs/changelog.md` 的 v1.3.9 段（11 个分类、113 条）。

### 新增

- **6 个 Rust 指标库**（可选依赖，未装时 desk 分组自动消失）：
  `ferro-ta`（`kline.ferro.*`，225）、`tulip-rs`（`kline.tulip_rs.*`，88）、
  `vector-ta`（`kline.vta.*`，209）、`wickra`（`kline.wickra.*`，427）、
  `kand`（`kline.kand.*`，59）、`pta_rs`（`kline.pta_rs.*`，27，pandas_ta 的 Rust 版）；
- **`alpha` 指标库（py-alpha-lib）**：`kline.alpha.*` + **Alpha101 / Alpha191
  共 292 个因子**（`kline.alpha101.*` / `kline.alpha191.*`，支持横截面）；
- **交易系统 `minibt.tradingsymtem`**：`TradingSystemBase` 只出 `long_signal` /
  `short_signal`，不画指标线；`TradingSystem` 门面按 10 分类暴露 **31 个系统**，
  底层按 `vector_ta → tulip_rs → pta_rs` 取数；
- **通达信本地数据**：`.day` / `.lc5` / `.lc1` 进策略（`get_kline`）与 desk 本地图表；
- **Python 3.13 / 3.14**：`zigzag.core` 纯 Python 实现、
  `signal_profit_fallback.py`、`cython_functions.load()` 统一入口；
- **`scripts/check_dep_matrix.py`**：依赖轮子就绪度一览（3.12 / 3.13 / 3.14）。

### 修复

- **3.13+ 阻断级**：指标之间加减比较用 `exec` + `locals()`，PEP 667 后
  直接 `KeyError` → `signal_backtest` / 信号相减全废 → 改走 `operator` 表；
- **3.14 导入失败**：`iteration-utilities` 的 C 扩展编不过 → 加纯 Python 兜底；
- **只装部分指标库时 ADX 类交易系统永不出信号** → `LIB_TABLE` 补 pta_rs 兜底；
- `zigzag` 写死 `cp312` 扩展名 → 换 minor 即 `ImportError`；
- desk 终端一整轮修复（同合约多页隔离 10 轮收尾、首页分组管理 / 事件日历 /
  最近打开来源分流、编辑器 LSP / 临时文件另存、本地账户右键市价平仓、
  回放退出平仓、参数优化进度、成交量分布价格轴…）——
  逐条见 `minibt_docs/docs/changelog.md` 与 `minibt_docs/docs/changelog_simple.md`。

### 打包

- `pylightcharts>=0.2.3`（本版 desk 的修复需要新前端）；
- 三版本各一份 wheel：`cp312` / `cp313` / `cp314`（同一份 sdist 可复用于三版）。

## [1.3.9-doc] - 2026-11-14（同一版本的第一轮：文档与指标打磨）



### 文档：`1.6 get_kline` 补通达信；`kernel` 参数说明 + 校验

**① 文档** `minibt_docs/docs/minibt_basic/1.6minibt_strategy_data_retrieval.md`

* 概述 / 参数说明 / 总结 都补上**本地通达信**（`.day` / `.lc5` / `.lc1`）；
* 新增 **7.2 本地通达信数据**：先「盘后数据下载」→ 文件位置表
  （`lday/*.day`、`fzline/*.lc5`、`min/*.lc1`）→ **方式一（文件路径，按后缀自动解析）**
  → **方式二（`data_source='tdx'` + `tdx_root` / `tdx_period`，按 `duration_seconds` 推周期）**
  → 解析结果（`symbol=SH.600000`、`amount`、`price_tick` 默认 0.01）→ 高级用法
  （`scan_root / resolve / load / load_path`）；
* 注意事项补：日线价格整数 ×100、分钟线 float + 时间编码公式。

**② `kernel` 参数**（`minibt/indicators/vector_ta.py` 里 200+ 个方法都有）

* 它是 **vector-ta 的「计算内核」**（Rust 侧实现选择）：`None`/`'auto'` 自动挑、
  `'scalar'` 纯标量、`'avx2'` / `'avx512'` SIMD（**只有该 wheel 编进对应指令集**
  才可用，否则库抛 `AVX2 kernel not compiled in this build`）；
* **数值结果与内核无关**（实测最大差 0.0），只影响速度；本机 wheel 没编 SIMD
  → `auto` 与 `scalar` 基本同速（1M 根 SMA 约 1.6 ms）；
* 注意 `kernel=''` 会被库当非法值抛 `Unknown kernel: `（就是之前 desk 换参数
  报错的同一个坑）→ 生成代码里**非法值 / 空串一律回落默认** ✓
* 每个方法的 docstring 现在都带 `kernel` 的中文说明（`PARAM_DOCS`）。

测试新增 2 项（`kernel` 语义：`None/''/scalar/auto/垃圾值` 结果都一致；
docstring 必含 kernel 说明）。

### 1.3.9 文档轮细节（1）

### 修复：图表策略不交易（两个开关被旧版误写成 False）+ 有策略时禁换周期

用户 2026-11-22：`test_9.py` 加到图表后**不交易**；顺带要求"有策略时切换周期要提醒"。

**① 根因（策略不交易）**：`~/.minibt/desk_user_prefs.json` 里
`strategy_next_on_new_bar=False` + `strategy_run_next=False` —— 早期版本把这两个
desk 开关**照抄了 minibt 回测的 `config` 默认值**（都是 False），之后一直沿用；
而 `StrategyRunner.advance()` 开头 `if cfg.get('run_next') is False: return True`
→ `next()` 一次都不跑（`replay()` 不受影响，所以本地图表策略能交易，
**实时图表**全都不交易）✗

修法三处：

1. `runtime_config()`：这两个键**只认 desk 设置 / 单策略 override**，没设置过 → **True**
   （策略自带的 `config.run_next=False` 不再影响 desk）；
2. `user_prefs` 一次性迁移 `strategy_switches_migrated`：两个都关着（旧 bug 典型状态）
   → 打开一次并写标记；用户之后**显式**再关（`set_setting` 会写标记）就不再被改回 ✓
3. 加到图表时若 `run_next` 仍为 False → **明确提醒**（日志 + toast），不再静默不交易；
   `next_on_new_bar=False` 也给一条 info，说明"每拍都会跑" ✓

**② 账户跟随当前切换**：`StrategyRunner(account_provider=…)` 每次 `advance()` 前
重新解析账户（desk 传 `_strategy_live_context(cls, symbol)[2]`，也就是**这一页 /
这一格当前切换的账户**）；换了实例 → 更新 `strategy._live_account` + 每个 K 线
`TqObjs.account` 并重建 `Position` / `TargetPosTask`（策略下单立刻跟着换 ✓）

**③ 有策略时不许换周期**：`Desk._on_set_cycle()` 开头检查
`tabs[tab]['strategy']`，有策略 → **push_alert + toast + 日志**
「请先删除策略，再切换周期」，周期保持不变；`set_cycle()` 把这条具体原因透传给
工具 / 脚本（以前只会回"暂时切不过去"）。删掉策略后切换恢复 ✓

测试：`tests/test_minibt_desk_strategy_trade.py` **8 项**（默认开关为 True / 显式关闭
被尊重 / 迁移只做一次 / `advance()` 真的反手且有委托 / `run_next=False` 只算指标 /
`next_on_new_bar=True` 同根 K 线不重复跑 / 账户跟随切换 / 有策略时换周期被拒）。

### 1.3.9 文档轮细节（2）

### 新增：通达信本地 K 线（`.day` / `.lc5` / `.lc1`）内置支持

用户 2026-11-22：本地图表商品搜索要能读通达信本地数据（**不装 mootdx**，
自己移植解析），`get_kline` 也支持传文件路径。

**① 解析**（新模块 `minibt/data/tdx.py`，纯 `struct`，32 字节定长记录）

| 文件 | 目录 | 记录 |
|---|---|---|
| `.day` 日线 | `vipdoc/<market>/lday/` | `int32 date, o/h/l/c(×100), float32 amount, int32 volume, int32 _` |
| `.lc5` 5 分钟 | `vipdoc/<market>/fzline/` | `uint16 date, uint16 minute, float32 o/h/l/c/amount, uint32 volume, uint32 _` |
| `.lc1` 1 分钟 | `vipdoc/<market>/min/` | 同上 |

`date` = `(年-2004)*2048 + 月*100 + 日`、`minute` = `时*60+分`；对外接口
`read_tdx / load_path / load / scan_root / resolve / tdx_id / split_tdx_id /
roots_from`；id 形如 **`tdx:sh600000@lc5`**（desk 选中 / 缓存用）。

**② desk 本地图表**

* **设置 → 系统设置 → 本地文件** 新增「**通达信数据目录**」（填安装根如
  `E:/new_tdx`，也能用系统目录框选）；只接受含 `vipdoc/` 的目录 ✓
* 本地数据搜索（`数据名 🔍`）顶部多出市场 chips：
  「本地 CSV / 通达信日线 / 5 分钟 / 1 分钟」，**代码分页加载**
  （默认 50 条，滑到底自动取下一页，`SymbolSearch` 新增 `appendItems()` +
  `onMoreCallback`）；
* **`local_data` 补丁只给数量**（`tdx.counts`），几千个代码不会一次塞给前端；
  **选中才读文件**（`local_load {name:'tdx:…'}` → `LocalStore._tdx_frame`）✓
* 新命令：`local_tdx_list`（分页查询）、`local_tdx_root`（设置 / 清除根目录）

**③ 策略**

* `get_kline('/path/sh600000.day')` → 自动走通达信解析；
* `read_unknown_file('*.day/.lc5/.lc1')` 同样支持；
* `get_kline('600000', data_source='tdx', duration_seconds=86400)` →
  用设置里的根目录按代码取（周期按 `duration_seconds` 推 day/5m/1m，
  也可 `tdx_period='5m'`、`tdx_root='E:/new_tdx'`）。

测试：`tests/test_minibt_tdx_local.py` **7 项**（日线/分钟解析 + 日期时间解码、
id 生成解析、目录扫描与排序、`resolve/load`、`roots_from`、`LocalStore`
**分页**+`frame(tdx:…)`、desk 补丁与命令、`read_unknown_file`/`get_kline`）。
文档：`minibt_docs/.../13.30_desk_command_tool_matrix.md` 已重新生成（新命令）。

### 1.3.9 文档轮细节（3）

### 修复：desk 换参数报错（`vta_price_density_market_noise` = "Unknown kernel:"）

用户 2026-11-22 报：在 desk 改参数后重算失败
`ValueError: Unknown kernel: `。根因与修复：

| 问题 | 根因 | 修复 |
|---|---|---|
| 空串传给库 | `kernel` 默认是 `None`，但目录把它标成 `str` → 表单清空后传 `''` → 库报 "Unknown kernel: " | **`catalog._coerce_params()`**：空串 → 回落**默认值**；`None` → **不传**（用库默认） |
| 数字串传给库 | 旧偏好 / 表单可能存 `"20"` → `TypeError: 'str' object cannot be interpreted as an integer` | `_coerce_params()` 按参数类型把 `"20"` 转 `int` / `float`，`"false"` 转 `bool`；生成代码里 `_ext_apply` 同样兜底 |
| `default=None` 的参数类型标错 | `_params_of` 只看默认值 → `k` / `ema_length` 被标成 `str` | 生成方法**带上真类型注解**（`k: float \| None`、`ema_length: int \| None`），`_params_of` 读注解；生成器 `_kind_of()` 用注解 + 名字启发式 |

顺带（都属于"完善 NON_KLINE / 参数健壮性"）：

* `TaLib.MAMA` 默认值修正为 TA-Lib 规范（`fastlimit=0.5`、`slowlimit=0.05`，以前是 `0/0` → 必报 `TA_BAD_PARAM`）✓
* `PandasTa.NON_KLINE_INDICATORS` 补 `rolling_apply`（要传 callable）/ `vhm` / `ttm_trend`（本版 pandas_ta 自身计算失败）✓

**全量审计**（脚本化，1315 个指标 × 两种极端参数「全空串」「全默认值的字符串」）：
`kand / wickra / vta / ferro / tulip / pta_rs / alpha / alpha101 / alpha191 / pta / talib`
**0 失败** ✓（修复前 426 失败）

测试：`tests/test_minibt_ext_libs.py` 新增 3 项（空串/数字串参数、`default=None` 的真类型、
**所有库 × 所有参数** 的空串/数字串 compute 不崩）→ 27 项全通过。

### 1.3.9 文档轮细节（4）

### vector-ta / ferro-ta / tulip-rs：主副图、MACD 柱体线、NON_KLINE 完善

用户 2026-11-22 三点要求，都在 `scripts/gen_ext_libs.py` 里自动判定：

**① 主副图三种情况（纯主图 / 纯副图 / 混合）**

* 主图 = 线的值落在 K 线 `[最低×0.9, 最高×1.1]`（tulip 另用自带
  `display_type == 'Overlay'`）；全主图 `overlap=True`、全副图 `False`、
  混合 → **`{线名: bool}` 字典**（如 `vta.directional_imbalance_index`）✓
* 实测：`ferro.SMA`/`tulip.SMA`/`vta.sma` → True；`ferro.RSI`/`tulip.ATR` → False

**② MACD 类柱体线**

* 新增 `LINE_HINTS`：多输出指标按名字补线名（`macd*` → `macd/signal/histogram`、
  `bbands*` → `upper/middle/lower`、`stoch*` → `k/d`、`aroon*`、`dmi*`）——
  ferro 原来只会得到 `macd_1/macd_2/macd_3`，柱体线认不出来 ✗
* `HIST_LINES` 里的线自动加
  `linestyle=dict(histogram=LineStyle(line_dash=LineDash.vbar, vbar_base=0.0,
  vbar_up_color=Colors.bull_color, vbar_down_color=Colors.bear_color))`
* 实测：`ferro.MACD` / `tulip.MACD` 的 `histogram` → **vbar** ✓

**③ `NON_KLINE_INDICATORS` 完善**

| 类别 | 例子 | 处理 |
|---|---|---|
| 辅助数学（加减乘除 / 取整 / 三角） | `ferro.ADD` `SUB` `MUL` `ABS` `SIN` | 保留方法，进 NON_KLINE |
| 需要**第二条序列**（内置指标 / 同长 Series·ndarray） | `ferro.BETA` `CORREL` `CROSS` | 保留方法，进 NON_KLINE；**第一个序列参数=K 线 close**，其余默认 `None`，不传 → 可读 `ValueError`，传 `pd.Series`/`np.ndarray`/`IndSeries` → 自动转 float64 计算 ✓ |
| 形态 / 0-1 / 常数输出 | `ferro.CDL2CROWS` `wickra.WinRate` | 进 NON_KLINE（desk 不显示） |

生成器另外修的两个坑：

* **位置参数不能跳过**（`matype='sma'`、`kernel=None` 必须占位，否则后面参数错位）；
* **探测期给"第二序列"塞合成序列**（否则库直接报错 → 指标被整条丢掉 ✗）。

统计：`vta` 209 方法 / 207 进 desk、`ferro` 225 / 196、`tulip` 88 / 88；
NON_KLINE：ferro 29、vta 2、tulip 0。

测试：`tests/test_minibt_ext_libs.py` **24 项**（新增：MACD histogram 是 vbar、
主副图三种情况、NON_KLINE 覆盖数学与双序列、`BETA(real1=pd.Series)` 可算且
缺参报可读错误）。

### 1.3.9 文档轮细节（5）

### 方案 B：并行内置 **vector-ta / ferro-ta / tulip-rs**（不替换父类）

按可行性分析结论执行（**不动** `IndFrame/IndSeries` 的 `PandasTa`/`TaLib` 父类）：

| 库 | 访问器 | 命名 | 方法数 | desk | 备注 |
|---|---|---|---:|---:|---|
| **vector-ta** | `kline.vta` | **小写**（原生） | 210 | 208 | 函数式 `vta.sma(data, period)` |
| **ferro-ta** | `kline.ferro` | **大写**（TA-Lib 风格） | 193 | 176 | `fta.SMA(close, timeperiod)` |
| **tulip-rs** | `kline.tulip` | **大写**（生成包装） | 88 | 88 | 自带元数据：输入列 / 选项 / **线名** / Overlay |

**为什么这样**：实测引擎级只要 0.005–0.05 ms，而走 `@tobtind` 后是 0.5–3 ms
（100k 根时 `kline.pta.sma` 2.98 ms vs `vector_ta.sma` 0.047 ms）→ 换父类端到端
只有 **1–2%** 收益，却要丢 45–57% 指标名、破坏 `pta_sma:sma` 布局 key 和
`TradingView.SAR` 等内部实现；所以做"并行库 + 各自独立前缀"，零破坏 ✓

实现（都在 `scripts/gen_ext_libs.py`）：

* **前缀与模块名分离**：`vector_ta` 模块 → 前缀 `vta_`（`vta_sma`），
  `ferro_ta` → `ferro_`，`tulip_rs` → `tulip_`（目录 key / CoreFunc / 装饰器一致）；
* **位置参数严格对齐**：库里有默认值的参数一律按签名顺序传默认值
  （`matype='sma'`、`kernel=None` 这类**不能跳过**，否则后面参数错位 ✗）；
  只有 `*` 之后的关键字参数才省略；
* **周期参数**（`period/timeperiod/k_period…`）按指标名给标准默认
  （均线 20、振荡 14、`bbands` 20、`aroon` 25、`roc` 10…），其它参数用库默认；
* **输出三形态**：`tuple` / 一串 1-D 数组（可用 `_is_line_array` 区分
  `wickra.Matrix.tolist()` 的行）/ 2-D 矩阵（按"哪一维等于输入长度"决定转置）；
* **tulip 紧凑数组**（不补预热 NaN，各输出长度还不一样）→ 左补 NaN 对齐，
  线名直接取 `info()['outputs']`（`bbands_lower/middle/upper`、
  `macd_line/signal_line/histogram`），主副图取 `display_type == 'Overlay'` ✓

desk 合计 **1299 条**（vta 208 / ferro 176 / tulip 88 / kand 56 / wickra 315 /
pta_rs 27 / pta 160 / talib 91 / alpha 40 / alpha101 18 / alpha191 120），
`missing_indicators() == {}` ✓

测试：`tests/test_minibt_ext_libs.py` **19 项**（三个库的结构 / 全量跑通 /
封装透明 / 与 pandas_ta 对拍 / tulip 元数据线名 / 主副图 / NON_KLINE /
desk 计数 / 目录 compute）。

### 1.3.9 文档轮细节（6）

### 文档：`minibt_basic/1.34` 信号（signals）声明指南

新增 `minibt_docs/docs/minibt_basic/1.34minibt_signals_declaration.md`（260 行），
介绍"指标自带多/中立/空判断"的完整用法：

1. **四种声明方式** + 优先级（① `@tobtind(signals=…)` > ② 类级 `SIGNALS` 表 >
   ③ 全局 `BUILTIN_SIGNALS` > ④ 技术分析插件的建议信号）；
2. `Threshold` / `Compare` / `Custom` 三个信号类的参数与语义（含旧名 `Osc` / `Trend`）；
3. 方式①单指标示例、多线指标按线名声明；
4. 方式②类级表（`Wickra` 41 条 / `Kand` 23 条的自动规则：主图「高于前一根」、
   0..100 振荡量「50 上方」、其余「高于前一根」）；
5. 方式③全局表、方式④建议信号规则（主图 `Compare(-2)` / 副图 `Threshold(0)`）；
6. 目录字段 `has_signal` / `signal_spec`、混合主副图（`overlap` 字典）怎么配；
7. `spec_of` / `signal_from_spec` / `resolve_signal` / `evaluate_values` /
   `summarize` 一览；
8. FAQ（为什么目录没有却有箭头、`-1/0/1` 序列、`NON_KLINE` 里声明无效、缓存）。

`mkdocs.yml` nav 已加「1.34 指标信号（signals）声明指南」；文档里的代码片段
已实跑验证（`@tobtind(signals=…)`、类级表覆盖、`catalog.entry` 读到 `signal_spec`）✓
（按约定本轮**没有**跑 `mkdocs build`，发布时再建站）

### 1.3.9 文档轮细节（7）

### 信号声明：三种方式 + 类级 `SIGNALS` 表（Wickra / Kand 已用上）

用户 2026-11-22 问「TA 的建议信号怎么声明、Wickra 现在是怎么设的」。

**三层机制（优先级从高到低）**：

| 方式 | 写法 | 存哪儿 |
|---|---|---|
| ① 单个方法 | `@tobtind(..., signals={'rsi': Threshold(50, 1, label='50 上方看多')})` | `wrapper._decorator_args['signals']` |
| ② **类级表**（新增） | 类里写 `SIGNALS = {'RSI': {'RSI': Threshold(50, 1)}}` | 类的 `SIGNALS` 属性，目录直接读 |
| ③ 全局表 | `minibt/signals.py: BUILTIN_SIGNALS['pta_rsi'] = {...}` | 按 `前缀_名字` 登记 |
| ④ 兜底 | 都没声明 → TA 插件给**建议信号**：主图 `Compare(-2, 1)`、副图 `Threshold(0, 1)` | `signals.suggested_signal()` |

目录合并顺序：① > ② > ③ > （④ 只在 TA 插件里用，不写进目录）。

`Wickra` / `Kand` **之前一条信号都没声明**（所以 TA 里看到的是"建议信号"，
`LongLine` 那种 -1/0/1 的序列就被 `Threshold(0)` 判成频繁穿越）；
现在生成器会给**常用 41 个（wickra）/ 23 个（kand）**指标自动声明：

* 主图线 → `Compare(-2, 1)`「高于前一根看多」；
* 0..100 振荡量（RSI / MFI / 随机…）→ `Threshold(50, 1)`「50 上方看多」；
* 其余 → `Compare(-2, 1)`。

改信号只需改生成器里的 `SIGNAL_NAMES` / `signals_table()`，或者直接在类里覆盖
`SIGNALS`；全量 300+ 条自动声明会把技术分析选择器刷屏，所以只放常用的 ✓

顺带：`desk_ta` 的 `options` 输出瘦身（不重复带 `params`）+ JSON 上限放宽到 60KB，
避免"带信号指标变多后工具返回被截断"。

测试新增 2 项（类级 `SIGNALS` 表生效 / `@tobtind(signals=…)` 覆盖类级表）。

### 1.3.9 文档轮细节（8）

### 修复：Wickra/Kand 的主副图、空线、标志线、统计量归类（用户逐条反馈）

用户 2026-11-22 逐条点名，全部按"**数据说话**"的方式自动判定（生成器里做，
`scripts/gen_ext_libs.py`）：

| 反馈 | 处理 |
|---|---|
| `ZigZag` 没有指标线；第 2 条线全是 1 | 第 2 条是 `-1/0/1` **方向标志线** → 丢弃；第 1 条是稀疏拐点线 → **线性插值**（现在 100% 有值） |
| `YoyoExit` 只有一条水平线 | 它本来就是"阶梯型止损线"，判定为主图 ✓（值随区间变化，不是异常） |
| `WoodiePivots` 应该是主图 | 5 条线都落在价格区间 → `overlap=True` ✓ |
| `RollingVWAP` 主图 | ✓ 同上 |
| `KaseDevStop` 主副图都有应为字典 | 第 2 条是 `-1/1` 标志线 → 丢弃，剩 1 条主图线（比字典更干净） |
| `WinRate` 等应进 `NON_KLINE_INDICATORS` | 常数 / 统计量 → **112 个** wickra 指标进 `NON_KLINE`（`WinRate`、`Wedge`、`SortinoRatio`、`Doji`…） |
| `Wedge` 无指标线 | 0-1 形态识别 → `NON_KLINE`（desk 不显示，方法仍在） |
| `UpsidePotentialRatio` 恒定 0 | 它不是形态指标，是"上行/下行波动比"；在这套数据上恒 0 → 归入 `NON_KLINE` |
| `FibFan` / `FibArcs` / `AutoFib` 无值 | 斐波那契水平线原来是"只有几段有值"→ **插值**；`FibFan` 第 1 条超出价格区间 → `overlap` 变成 **字典**（`{1: False, 2: True, 3: True}`） |

**判定规则（自动、可复现）**：

1. 常数线（唯一值 ≤1）→ 丢；
2. 只有 `-1/0/1` 的线（唯一值 ≤3 且都在这三个里）→ 丢（方向标志）；
3. 一条线都不剩 → 进 `NON_KLINE_INDICATORS`（方法保留，desk 不显示）；
4. 剩下的线：值全部落在 K 线 `[最低×0.9, 最高×1.1]` 且中位数在区间内 → **主图**；
5. 全主图 → `overlap=True`；全副图 → `False`；混合 → **`{线名: bool}` 字典**；
6. 有值比例 < 2% 的稀疏线 → **线性插值**（拐点型指标才画得出来）。

统计：`wickra` 427 个方法 / **315 条**进 desk（112 个统计量·形态归类）；
`kand` 59 个方法 / **56 条**进 desk。

测试新增 4 项（主副图按价格判定 / 标志线被丢 / 稀疏线插值 / 统计量归 NON_KLINE）。

### 1.3.9 文档轮细节（9）

### 内置第三方指标库（P2）：**wickra** 427 个指标

| 项 | 值 |
|---|---|
| 前缀 | `wickra_`（CoreFunc：`wickra_SMA` …）|
| 入口 | `kline.wickra.SMA(period=20)` / `kline.wickra.BollingerBands()` |
| 覆盖 | **427 个类**（520 里过滤掉订单流 / 市场宽度 / 双序列 / 无 batch）|
| desk | 新分组「Wickra」**425 条**（`Doji` / `RunBars` 实测不稳 → `NON_KLINE_INDICATORS`）|

反射要点（都在 `scripts/gen_ext_libs.py`）：

* `wickra` 是 **C 扩展**：`__init__` 只有 `*args/**kwargs` → 构造参数从
  **`__text_signature__`** 解析（`ast.parse('def _f(period=20, multiplier=2.0)')`）；
* 数据列从 `batch` 的签名拿（`prices` / `open,high,low,close` / `high,low,close` …），
  并做列名别名映射（`prices/price/data/input/values → close`、`vol → volume`）；
* `_pick_kwargs`：C 扩展的"具名参数"为空 → **参数全部透传**（否则 `SMA(period=…)`
  会被过滤掉）；
* 输出形态三合一：`tuple`（多输出）/ `array.array`（单线）/ **`wickra.Matrix`**
  （`.tolist()` 后是行优先矩阵，按"哪一维等于输入长度"决定要不要转置）；
* 输出统一 `±inf → NaN`（如 `GainLossRatio` 会除零）。

测试：`tests/test_minibt_wickra.py` **6 项**（结构 427 / 全量跑通 / **封装透明**
（与直调 `wickra.*` 逐值一致）/ 与 pandas_ta 对拍 SMA·EMA·RSI / desk 425 条 /
目录 compute）✓

**累计**：`PtaRs 27` + `Alpha101 18` + `Alpha191 120` + `Alpha 40` +
**`Kand 57`** + **`Wickra 425`** —— desk 里第三方 Rust 库合计 **687 条指标**。

**下一步（P5）**：把 kand / wickra 列进基准报告（27 个共有指标四列对比）。

### 1.3.9 文档轮细节（10）

### 内置第三方指标库（P1）：**kand** 59 个指标

用户 2026-11-21：把 `kand` / `wickra` 内置进 minibt（先 kand，wickra 下一步）。

| 项 | 值 |
|---|---|
| 前缀 | `kand_`（CoreFunc：`kand_sma` …）|
| 入口 | `kline.kand.sma(period=20)`（数据源 = 调用它的 IndFrame ✓）|
| 覆盖 | **59**（ad/adosc/adx/adxr/aroon/aroonosc/atr/bbands/bop/cci/cdl_* × 7/dema/dx/ecl/ema/macd/max/medprice/mfi/midpoint/midprice/min/minus_di/minus_dm/mom/natr/obv/plus_di/plus_dm/rma/roc/rocp/rocr/rocr100/rsi/sar/sma/stddev/stoch/sum/supertrend/t3/tema/trange/trima/trix/typprice/var/vegas/vwap/wclprice/willr/wma）|
| desk | 新分组「Kand」**57 条**（`sar` / `vegas` 数据不全 → `NON_KLINE_INDICATORS`）|
| 生成 | `scripts/gen_ext_libs.py`：反射签名 → `_EXT_SPECS` 表 + 类文件 + CoreFunc |

实现要点：

* **统一运行器** `_ext_apply(core, lib, name, params)`（`core.py` 标记块）：
  按 spec 里的 `args` 把 `close/high/low/open/volume/timestamp` 从**调用它的数据**
  取出，其余按参数传；返回值 `tuple`（kand 会把内部中间量一起返回）→ 只取
  声明的线名（`bbands → upper/middle/lower`、`macd → macd/signal/histogram`）；
* `period` 默认值按指标名区分（均线 20、振荡 14、`bbands/stddev/var` 20、
  `aroon` 25、`roc` 10…）；
* **`None` 默认值的入参不传**（如 `kand.ema(..., k=None)` —— 传 `k=3` 会让
  序列发散，这个坑已修 ✓）；
* 可选依赖：没装 `kand` → 调用时抛可读错误，`import minibt` 不受影响 ✓

测试：`tests/test_minibt_kand.py` **8 项**（结构 59 / 生成器 spec 一致 /
59 个全跑通且无 `±inf` / **封装透明**（与直接调 `kand.*` 逐值一致）/
与 pandas_ta 对拍 sma·ema·rsi·atr / 多线指标线名 / desk 57 条 / 目录 compute）✓

**下一步（P2）**：`wickra`（520 个类，约 427 个可用；`price,size,is_buy` 订单流、
`snapshots`、市场宽度类进 `NON_KLINE_INDICATORS`），生成器已按同一套 spec 设计，
只需加一个 adapter + 反射过滤。

### 1.3.9 文档轮细节（11）

### PtaRs 第四轮：`skew` / `kurtosis` 换 numba JIT 滑窗

这两个指标上一轮是"MOMENT + STDDEV 组合"（口径准但比 pandas 慢 0.5×）。
现在：

* 优先走 **numba `njit(cache=True)` 的单遍滑窗**（一次循环同时算均值 / 二阶 /
  三阶 / 四阶中心矩），公式仍是 pandas 的 Fisher 修正口径；
* **没装 numba 或数据量小（<200 根）自动回落**原来的 MOMENT 组合 ✓
  （所以仍是可选依赖，不影响 `import minibt`）

| 指标 | 之前 | 现在 | pandas_ta |
|---|---:|---:|---:|
| skew | 56.9 ms / 0.5× | **32.6 ms / 1.2×** | 39.1 ms |
| kurtosis | 76.0 ms / 0.5× | **30.9 ms / 1.4×** | 44.0 ms |

（100 万根，3 次取最好；数值仍与 pandas_ta 一致：skew 1.6e-9、kurtosis 7.2e-7 ✓）

### 1.3.9 文档轮细节（12）

### PtaRs 第三轮：去隐形成本（`vwap` 0.5× → 5.7×、`batch()` 4.4×）

| 改动 | 效果（100 万根） |
|---|---|
| `_pta_rs_arrays` **不再算时间戳**（27 个里只有 `vwap` 要），挪到 `_pta_rs_day_stamps` | 每个指标省 **~17 ms**；`batch()` 在 5 000 根时 10 ms（逐个 45 ms）→ **4.4×** |
| `_pta_rs_ema` 换**种子线性修正**：对连续"视图"直接跑 Rust EMA，再用 `(1-α)^k` 修正开头几百个点（`(1-α)^k<1e-12` 之后可忽略） | `ema` 25.9 → **7.1 ms**（1.8×）、`macd` 89 → 34 ms、`trix` 81 → 33 ms |
| `_pta_rs_vwap` 换 **numpy 前缀和 + 按交易日分组**（`cumsum` 减去组起点前缀和） | 239 → **20.5 ms**，0.5× → **5.7×** ✓ |

现在的算法级加速（算法级 = 直调 `CoreFunc`）：`ts_argmax 61×` / `ts_argmin 51×` /
`sma 29×` / `wma 18×` / `bbands 10×` / `adx 7.0×` / **`vwap 5.7×`** / `atr 5.1×` /
`stdev 4.3×` / `stoch 3.1×` / `trix 2.1×` / `ema 1.8×` / `rma 1.9×`；
仍慢的是 `skew 0.5×` / `kurtosis 0.5×`（为了口径精度做组合）、`roc 0.7×`（只有一个减法）
和 `kc 0.8×`（两次 EMA）。

数值没变：27 个里 24 个与 pandas_ta 逐值一致，ATR/ADX 与 TA-Lib 逐值一致 ✓

测试：`tests/test_minibt_pta_rs.py` **14 项**（新增 `vwap` 按日重置 + 与 pandas_ta 对拍、
`ema` 种子修正不改数值、取数不再算时间戳）→ 全通过 ✓

### 1.3.9 文档轮细节（13）

### PtaRs 第二轮：+7 个高收益指标、减拷贝、`batch()` 批量接口

| 动作 | 结果 |
|---|---|
| 新增 7 个 | `ts_rank`（窗口排名百分比）、`quantile`、`skew`、`kurtosis`、`linreg`、`ts_argmax`、`ts_argmin` → 共 **27 个** |
| 减拷贝 | `_pta_rs_ema` / `_pta_rs_rma` 改"只拷一次 + 视图切片"（1M 根 EMA 59 ms → **9 ms**）|
| 批量接口 | `minibt.indicators.pta_rs.batch(frame, specs)` —— 绕过 `@tobtind`：500 根时 **2.5×**、5 000 根 1.6× |
| 窗口个数助手 | `_pta_rs_count()`（部分窗口也能算，`ts_rank/ts_argmax/ts_argmin` 用）|

**数值**（27 个里 24 个逐值一致）：新增的 7 个中 `ts_rank` / `quantile` /
`linreg` / `ts_argmax` / `ts_argmin` 都是 **0.0** 误差；`skew` 1.7e-9（用
MOMENT+STDDEV 组合，pandas 口径）；`kurtosis` 7.2e-7。`ts_argmax/ts_argmin`
并列极值取**最近**一次（pandas `rolling.apply(argmax)` 取最早，测试里按"最近"对拍）。

**速度（100 万根，算法级）**：`ts_argmax 61.1×`、`ts_argmin 60.8×`、`sma 37.6×`、
`wma 15.8×`、`bbands 9.9×`、`adx 6.1×`、`atr 5.4×`、`stdev 4.4×`、`stoch 3.3×`、
`quantile 1.7×`、`linreg 1.2×` …（`vwap 0.5×`、`skew 0.5×` 仍慢，原因见报告）

`PTA_RS_REPORT.md` 已更新（含 27 个值表、两级速度表、`batch()` 对比、
本轮优化记录）。测试：`tests/test_minibt_pta_rs.py` **11 项**全通过（新增
`batch()` 一致性、Rust 快路径检查）。

### 1.3.9 文档轮细节（14）

### 新增：PtaRs（pandas_ta 的 **Rust 版**，先做 20 个常用指标）

用户 2026-11-21 问「pandas_ta 有没有 Rust 版」→ 没有（纯 Python），于是用
`py-alpha-lib` 的 Rust 算子把公式 1:1 拼了一遍，做成 minibt 指标库：

| 项 | 值 |
|---|---|
| 前缀 | `pta_rs_`（CoreFunc：`pta_rs_sma` …）|
| 入口 | `kline.pta_rs.sma(length=20)`（数据源 = 调用它的 IndFrame ✓）|
| 覆盖 | sma / ema / wma / rma / stdev / bbands / macd / rsi / atr / donchian / kc / kdj / stoch / obv / mfi / vwap / adx / ao / roc / trix |
| desk | 新增分组「PtaRS」20 条（参数名与 pandas_ta 一致 ✓）|
| 生成 | `scripts/gen_pta_rs.py`（别手改产物）；报告 `PTA_RS_REPORT.md` |

**数值**：17 个与 `pandas_ta` **逐值一致**（最大相对误差 ≤1e-9，含 bbands/macd/
kdj/stoch/donchian/kc/trix 这些多线指标）；`atr / adx / dmp` 与 **TA-Lib**
（Wilder 标准口径）逐值一致 —— pandas_ta 自己的 `presma` 预热种子与 TA-Lib
差一根，只在预热段有差异、尾部收敛。

**速度（100 万根）**：

* **算法级**（直调 `CoreFunc`）：`sma 33×`、`wma 23×`、`bbands 8.5×`、`adx 5.4×`、
  `atr 5.2×`、`stdev 4.4×`、`stoch 2.8×` … `vwap 0.6×`；
* **指标级**（走 `@tobtind`）：0.1×–3.0× —— 框架包装固定 40–60 ms 占主导，
  数据量小时不如直接 pandas ✓（结论已写进报告，别再盲目"换 Rust"）。

**踩到并记录下来的口径坑**：`stdev` 的 ddof=1、`ema` 的 SMA 种子（presma）、
`rma` = `alpha.SMA(x,n,1)`、`alpha.REF` 补首值（要自己补 NaN）、`adx` 列序含
ADXR、`macd` 直方图在中间列、`stoch` 默认 sma / `kc` 默认 ema、
pandas_ta 对索引类型敏感（对比统一用 RangeIndex）。

测试：`tests/test_minibt_pta_rs.py` 9 项（20 个方法 + 主副图归属 + CoreFunc 齐 +
逐值对比 pandas_ta + ATR/ADX 对拍 TA-Lib + desk 目录 20 条 + 目录 compute +
生成器同步）→ 全通过 ✓

### 1.3.9 文档轮细节（15）

### 修复：`Alpha191.alpha028` 在 desk 上没有线（递归 SMA 中毒 + ±inf）

用户 2026-11-21：desk 上挂 `Alpha191.alpha028` **没有数值 / 看不到指标线**。

**根因（两段）**：

1. `#28` 的公式里第二条链是 `MAX(HIGH,9) - TSMAX(LOW,9)`（示例原样搬的、
   官方 txt 也是这么写的）—— 平价 K 线上 `HIGH == 最高 LOW` 时分母为 0 →
   比值 `±inf`；
2. 那个 `±inf` 进了**通达信式递归 `SMA`**（`y = (m·x + (n-m)·y_prev)/n`）——
   一旦中毒后面**永远是 inf/NaN** → 整条序列没有可画的点。

审计三套内置 K 线（8964 / 10000 / 10000 根）发现还有同类因子：
`wq101 #53`、`gtja191 #23 / #28 / #111 / #118 / #144 / #160 / #164 / #171 /
#174 / #190`（有的恒 NaN，有的带 `±inf`）。

**修法（都在 `_alpha_factors/context.py`，不动 vendor 公式）**：

* `_PanelContext.SMA`：**非有限样本跳过**（保持上一个值；首个有效值做种子）——
  输入全有限时仍然直接交给上游，数值**完全一致** ✓
* 输出层 `_clean()`：`±inf` → `NaN`（除零等极端值按「缺失」处理，图表才能画 ✓）

效果（三套数据 × 138 个纯时序因子）：**`±inf` 归零，有值比例全部 > 50%**；
`Alpha191.alpha028` 现在 `test` 数据 8964/8964 根都有值、desk 尾部 50 个点
有 45+ 个能画 ✓

测试：`tests/test_minibt_alpha_factors.py` 新增 3 项（递归 SMA 跳过非有限且
全有限时与上游逐值一致 / 三套内置 K 线 138 个因子无 `±inf` 且过半有值 /
`alpha028` 有值有变化且 desk compute 能出点）→ 21 项全通过 ✓

### 1.3.9 文档轮细节（16）

### 教程：`tutorials/test/alpha101.ipynb` + `alpha191.ipynb`

用户 2026-11-20：在两个家族各写一个测试教程，横截面案例用**内置的三套 K 线**
（`l2609_60` 1 分钟、`pp2609_60` 1 分钟、`test` 5 分钟）。

两个 notebook（各 24 个 cell，和 `alpha.ipynb` / `talib.ipynb` 同风格）：

1. **案例数据**：先打印三套内置 K 线的合约 / 周期 / 根数 / 时间范围 ——
   1 分钟两套先 `resample('5min')` 成 5 分钟，各取最后 800 根，按 bar 序号当
   `tradetime`，拼成 `securityid = 0/1/2` 的面板，再补一列 `indclass`
   （真实研究要换成同一时间段、同一周期的数据）；
2. **单标的**：`NON_KLINE_INDICATORS` 之外的纯时序因子逐个调
   `kline.<module>.alphaNNN()`，统计「有值 / 恒 NaN / 失败」；
3. **访问器 + 数据源**：`self.kline.alpha191.alpha002()`，
   换一套数据（5 分钟 → 1 分钟）因子值就变 ✓；
4. **横截面**：`minibt.factor.panel(panel, family, no)` 把**全部**因子跑一遍
   （`Alpha101` 100/101、`Alpha191` 190/191 跑通），失败的记录原生错误
   —— 例如 `wq101 #56` 缺 `cap` 列、`gtja191 #30` 上游 `DELAY` 少传参；
5. **与上游逐值比对**：直接调 vendor 的 `alphaNNN(ctx)` 对比，全部一致；
6. **无未来函数**：截断到前 60% 重叠区间值不变；
7. 抽样 6 个因子作图 + 公式速查 + 小结表。

实测（两套数据都跑通，0 个失败 cell）：

```
alpha101: 纯时序 18 个全有值；面板 2400 行（3 标的 × 800）；横截面 100/101 跑通
alpha191: 纯时序 118 有值 / 2 恒 NaN（alpha023 / alpha160，上游同款）；横截面 190/191
```

### 1.3.9 文档轮细节（17）

### Alpha101 / Alpha191 改版：完全按 alpha 的形式内置（数据源 = IndFrame 自己）

用户 2026-11-20 改主意：**不要** `AlphaFactor` 那套「138 个 + af_ 前缀」的折中，
按 alpha 的形态重新内置。

| 改版前（-57） | 改版后（-58） |
|---|---|
| `minibt/indicators/alpha_factor.py` → `class AlphaFactor` | **删除**，拆成 `alpha101.py`（`class Alpha101`）+ `alpha191.py`（`class Alpha191`） |
| 访问器 `kline.af` | `kline.alpha101` / `kline.alpha191` |
| 138 个纯时序因子方法 + `alpha101(no=)` 入口 | **全部 292 个因子**都是方法（`alpha001` … `alpha101` / `alpha191`） |
| 前缀 `af_` + 参数化 `no` | 前缀 **`alpha101_` / `alpha191_`**（`self.kline.alpha101.alpha001()`） |
| 单标的面板（`securityid` 固定 0） | **数据源就是调用它的 IndFrame 自己**：有 `securityid` / `tradetime` / `indclass` / `cap` 就用，没有就按单标的 |
| 横截面因子直接 `ValueError` 拦掉 | **不拦**：数据不对由 alpha 抛**原生错误**（框架不封装） |
| `NON_KLINE_INDICATORS` 没设（全在类里） | 两个类都设成「非纯时序」的因子（`Alpha101` 83 个 / `Alpha191` 71 个）→ desk 只显示纯时序部分 |
| desk：140 条（2 入口 + 138） | desk：**Alpha101 18 条 + Alpha191 120 条**（各一个新分组） |

要点：

* 全部因子**副图**（`overlap=False`），线名 = 方法名（`alpha002`）；
* `core.py` 对应 `alpha101_alpha001` … `alpha191_alpha191`（292 个），
  `self` **就是计算用的数据**（`_alpha_factor_apply(self, family, no)`）；
  旧的 `af_*` 函数全部清除；
* 计算仍复用上游 `alpha.context.ExecContext`（不重写 90 个算子），
  并修掉一处上下文泄漏（面板必须在 `Context` 内创建，否则 `groups`
  会漏到线程上下文里）；
* 纯时序因子清单保留为类属性 `PURE_INDICATORS`（编号），
  `NON_KLINE_INDICATORS` 与注册表 `kind != 'ts'` 严格一致 ✓

测试：`tests/test_minibt_alpha_factors.py` 重写为 18 项（注册表 292 / vendor
原样 / 两个类都含全部因子且全副图 / `NON_KLINE_INDICATORS` 与注册表一致 /
`core.py` 292 个方法且无 `af_` / 旧模块已删 / 138 个跑通 / 访问器路径 /
与上游逐值一致 / 无未来函数 / **数据换掉因子值就变** / 线程上下文还原 /
desk 只放纯时序 / 目录 compute / `minibt.factor.*` 辅助 / 中文注释）✓

### 1.3.9 文档轮细节（18）

### Alpha101 / Alpha191 因子内置（292 个，来自 py-alpha-lib 官方示例）

用户 2026-11-20：研究 `py-alpha-lib-main/examples` 里的 **WQ Alpha101** 与
**GTJA Alpha191** 怎么内置进 minibt。

**先看清结构**：示例里那两套因子是**多标的横截面**代码 ——

* 入口 `alpha_001(ctx)` … `alpha_101(ctx)` / `alpha_191(ctx)`，共 **292 个纯函数**；
* 数据是 `securityid × tradetime` 的**展平面板**，跨标的算子
  （`RANK` / `INDNEUTRALIZE`）靠 `alpha.set_ctx(groups=标的数)` 的线程上下文；
* `ctx` = 上游 `alpha.context.ExecContext`（90+ 算子 + 派生字段
  `RETURNS` / `ADV{n}` / `DTM` / `DBM` / `TR` / `HD` / `LD` / `INDCLASS.*`）；
* 这些算子 minibt **早就都有了**（`alpha_*` 78 个）—— 因子只是它们的组合表达式。

**按能否单标的计算自动分档**（扫 `RANK` / `INDNEUTRALIZE` / `SCALE` /
`INDCLASS` / `BANCHMARKINDEX` / `MKT`）：

| 家族 | 纯时序（单标的可算） | 横截面 | 缺外部数据 |
|---|---|---|---|
| WQ Alpha101 | **18** | 64 | 19 |
| GTJA Alpha191 | **120** | 66 | 5 |

**内置方式（不照抄 292 个指标）**：

1. **vendor**：`minibt/indicators/_alpha_factors/{wq101,gtja191}.py`
   —— 上游示例**原样搬运**（BSD-2-Clause，保留来源注释），不重写公式；
2. **执行环境**：`_alpha_factors/context.py` 把 K 线包成 `securityid` 恒定的
   面板（`securities = 1`）→ **直接复用上游 `ExecContext`**（省掉 90 个算子的
   重写），计算放在 `Context(groups=1)` 里跑、跑完还原线程上下文 ✓；
   字段映射：`vol = volume`、`vwap = amount/volume`（缺 amount → 典型价
   `(h+l+c)/3`）、`AMOUNT = 成交额`（缺 → 成交量）；
3. **138 个纯时序因子 = 独立指标方法**（`self.data.af.alpha191_002()`，
   `@tobtind(lib="af", overlap=False)`，副图一条线）+ **2 个参数化入口**
   （`alpha101(no=6)` / `alpha191(no=191)`，越界 / 横截面编号给可读报错）；
4. **横截面研究接口** `minibt.factor.panel(df, 'wq101', 101)`
   （多标的 DataFrame：`securityid`/`tradetime`/OHLCV），130 个横截面 +
   24 个缺数据因子在这里可用；`minibt.factor.available()` /
   `numbers()` / `formula()` 查清单与公式；
5. **desk**：新库「Alpha 因子」（前缀 `af_`，选择器新分组）：**140 条**
   （2 入口 + 138 因子），参数 `no` 带区间（1~101 / 1~191），全部副图 ✓
6. **生成器** `scripts/gen_alpha_factors.py`：反射上游文件 → vendor + 注册表
   （编号 / 公式 / 类型）+ `alpha_factor.py` + `core.py` 的 `af_*`
   （用标记块包裹，重复运行只替换标记之间）→ 上游升级后重跑即可 ✓
7. **教程** `tutorials/test/alpha_factors.ipynb`：清单 / 单因子 / 参数化 /
   138 个批量跑 / 与上游**逐值比对** / 横截面面板 / 公式速查 / 抽样作图。

实测：138 个纯时序因子全部可算（GTJA #23 / #160 / #174 这类用**递归 SMA** 且
种子是 NaN 的因子恒为 NaN —— 上游同行为）；与上游函数**逐值一致**；
截断前 N 根不改变重叠区间的值（无未来函数）✓

测试：`tests/test_minibt_alpha_factors.py` 13 项（注册表 292 / vendor 原样 /
138 个跑通 / 与上游逐值一致 / 无未来函数 / 访问器与报错 / 线程上下文还原 /
横截面 panel / `available` 等辅助 / desk 目录 140 条 / 目录 compute /
140 个方法都是 `@tobtind` + 中文注释）✓

### 1.3.9 文档轮细节（19）

### Alpha：78 个指标全部中文注释 + 主副图归属（17 主图 / 23 副图）

用户 2026-11-20：开放给用户的指标和方法还没有中文注释；另外 `overlap` 原来
**全是 True**（全都当主图），需要按指标性质区分主副图。

**① 中文注释**（参照 `py-alpha-lib` 的 `algo_gen.py` 原始英文说明逐条翻译，
版式和 `pandas_ta.py` 一致）：

新增 `scripts/alpha_docs.py`（78 条说明表：中文名 / 一句话用途 / 公式 /
参数 / 主副图），生成器 `scripts/gen_alpha_indicators.py` 用它生成
`minibt/indicators/alpha.py` 与 `CoreFunc.alpha_*` 的 docstring：

```
简单移动平均 (MA)
---------
    最基础的均线：窗口内收盘价的算术平均，用来平滑噪声、看趋势方向。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> MA(x, n) = sum(x, n) / n

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.ma(periods=20)

说明:
---------
    - 原生接口：`alpha.MA(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓
```

**② 主图 / 副图**（`overlap` 不再写死 True）：

| 归类 | 指标 | 数量 |
|---|---|---|
| 主图叠加 `overlap=True` | `ma / ma_v / ema / ema_v / sma / sma_v / lwma / lwma_v / dma / dma_v / hhv / hhv_v / llv / llv_v / ref / ref_v / intercept` | 17 |
| 副图 `overlap=False` | `stddev / var / zscore / rank / quantile / moment / skewness / kurtosis / sharpe / max_drawdown / min_max_diff / slope / corr / entropy / bins / sum / product / count / count_v / hhvbars / hhvbars_v / llvbars / llvbars_v` | 23 |
| 算子（不上图，`NON_KLINE_INDICATORS`） | 其余 38 个 | 38 |

desk 指标目录（`indicator_catalog`）直接读装饰器的 `overlap`：alpha 分类
**40 条**，主图 17 / 副图 23，`missing_indicators()` 仍为 `{}` ✓

测试：`tests/test_minibt_alpha_lib.py` 新增 5 项（每个方法都有中文 docstring、
`overlap` 与主副图清单一致、目录 `overlap` 与装饰器一致、说明表覆盖 78 个、
生成器不允许再写死 `overlap=True`）→ 15 项全通过 ✓

### 1.3.9 文档轮细节（20）

### Alpha：参数**顺序**与原指标一致 + `tutorials/test/alpha.ipynb` 全量测试

用户 2026-11-20：`CoreFunc.alpha_*` 之前把标量排在前面（`periods` 在
`benchmark` 前），和原指标签名不一致 —— 现在**按原签名顺序**生成
（第一个数组参数 = `FILED.C`（close），在 minibt 里省略）：

| 原指标 | minibt |
|---|---|
| `ALPHA(input, benchmark, periods)` | `alpha_alpha(benchmark=None, periods=20)` |
| `BW_SPLIT(price, dividend, transfer_shares, right_shares, right_price)` | `alpha_bw_split(dividend=None, transfer_shares=None, right_shares=None, right_price=None)` |
| `CORR2(x, y, periods)` | `alpha_corr2(y=None, periods=20)` |
| `REGRESI(y, x, periods)` | `alpha_regresi(x=None, periods=20)` |
| `FRET(open, close, is_calc, delay, periods)` | `alpha_fret(close=None, is_calc=None, delay=1, periods=20)` |

新增教程笔记本 **`tutorials/test/alpha.ipynb`**（和 `talib.ipynb` / `pandasta.ipynb`
同风格，20 个 cell）：

1. 全部 78 个函数 × 默认参数（打印 `lines` / 最后值 / 失败原因）；
2. 需要第二条序列的算子逐个传参（cross/corr2/beta/alpha/regresi/where/
   scan_*/sumif/group_*/拆股 …）；
3. 可画线 40 / 算子 38 的清单（`NON_KLINE_INDICATORS`）；
4. `kline.alpha.xxx` 与 `kline.ta.alpha_xxx` 等价性、IndSeries 上直接调用；
5. 参数顺序（和原指标签名对比）；
6. 与 pandas 对齐校验（`MA/SUM/HHV/LLV` 用 `min_periods=1`、
   `STDDEV/VAR/ZSCORE` 用 `ddof=1`，尾段比对）；
7. 失败清单（默认参数 54 通过 / 24 缺第二序列；补参数后 **0 失败**）。

### 1.3.9 文档轮细节（21）

### Alpha 库：**全部**方法统一 `@tobtind(lib="alpha")` + `IndSeries` + 函数体省略

用户 2026-11-20：`minibt/indicators/alpha.py` 里 `abs` 之后的算子（`cross` /
`where` / `beta` / `bw_split` / `group_rank` / `neutralize` … 共 38 个）以前是
普通方法（`-> pd.Series` + 内部 `_alpha_apply`）—— 虽然它们不画在 K 线上
（已在 `NON_KLINE_INDICATORS`），但**计算结果也必须返回内置指标格式**。

统一改为：

    @tobtind(lib="alpha")
    def cross(self, b=None, **kwargs) -> IndSeries:
        """alpha.CROSS（工具函数；计算在 CoreFunc）"""
        ...

* 装饰器统一 `@tobtind(lib="alpha")`（可画线的 40 个仍带 `overlap=True` + `lines`）；
* 返回类型统一 `IndSeries`；
* 函数体全部省略（`...`），真正计算集中在 `CoreFunc.alpha_xxx`。

实测：`kl.alpha.abs() / cross(b=...) / where(a=..., b=...) / beta(benchmark=...)`
全部返回 **`IndSeries`** ✓；desk 目录仍是 40 条（算子不进选择器）、
`missing_indicators()` 仍为 `{}` ✓。

### 1.3.9 文档轮细节（22）

### 新内置指标库：`alpha`（py-alpha-lib，Rust，**可选依赖**）

把 [py-alpha-lib](https://github.com/msd-rs/py-alpha-lib)（Rust/PyO3，因子算子库）
接成 minibt 的**第 11 个指标库**，前缀 `alpha_`：

| 层 | 改动 |
|---|---|
| ① `CoreFunc` | `minibt/core.py` 新增 **78 个 `alpha_xxx()`** + 模块级 `_alpha_apply()` / `_alpha_series()`（**惰性** `_LazyModule('alpha')`，没装时给可读错误）|
| ② 库适配类 | 新文件 `minibt/indicators/alpha.py`：`class Alpha`（`_perfixes='alpha_'`）+ 全部 78 个方法 + `NON_KLINE_INDICATORS`（38 个算子）|
| ③ 注册入口 | `minibt/indicators/core.py`：`IndicatorClass.Alpha = Alpha`；`base.py` 新增 `kline.alpha` 属性（`self.data.alpha.ma(...)`）|
| ④ desk 目录 | `indicator_catalog.py`：`LIBS` / `INDICATOR_CLASS_LIBS` / `CORE_PREFIXES` / `ACCESSOR_OF` / `AUDIT_LIBS` + `CATALOG_SCHEMA=10`；`app.py` 的 `_SECTION_OF` / 选择器分组加「Alpha」|

**分类**：40 个「单序列进 → 同长序列出」可画线（`ma/stddev/zscore/hhv/llv/…`），
38 个算子进 `NON_KLINE_INDICATORS`（`CROSS / CORR2 / COV / BETA / ALPHA / WHERE /
BINS / FILTER / GROUP_* / SCAN_* / 拆股 …`）—— 选择器里不出现，但策略里照样能用。

**参数约定（v1.3.9-53 修正，和 `pandas_ta` 完全一致）**：方法签名里**没有**
`input='close'` 这种参数 —— 数据源固定由 **`FILED.C`** 决定
（`arg, kwarg = self._get_column_(locals(), *FILED.C)`；KLine → `close`，
IndSeries → 它自己）。只有**需要第二条序列**的算子才列其余参数（默认 `None`）：

```python
def alpha_ma(self, periods: int = 20, **kwargs)       # 数据 = close
def alpha_alpha(self, periods: int = 20, benchmark=None, **kwargs)
def alpha_bw_split(self, dividend=None, transfer_shares=None,
                   right_shares=None, right_price=None, **kwargs)   # price = close
```

`periods` 按 alpha 自己的签名区分——`MA(input, periods:int)` 传标量；
`MA_V(input, periods:A)` 是数组 → 传标量时按长度广播成 `uint64`
（`weight` 之类浮点广播成 `float64`）✓

**安装**（不装也能正常用 minibt）::

    py -3.12 -m pip install "minibt[alpha]"      # 或 pip install py-alpha-lib

生成器：`scripts/gen_alpha_indicators.py`（反射 `alpha` 签名 → 自动生成两个文件，
不手抄 78 个方法 ✗）。测试：`tests/test_minibt_alpha_lib.py` 7 项。



### 修复：指标多出别的指标的线（G_Channels 凭空多 4 条）

用户 2026-11-19：`G_Channels`（`thresh=0`，本该只有 `a / b / avg` 三条线）
在 desk 上多出 `base_line / upper / lower / dsav` 4 条（隐藏状态）。

根因（`minibt/indicators/core.py` 的 `BtIndicator.__new__`）：

* `next()` 里的 `self` 是**源数据（KLine）**，`self.lines.xxx = ...` 写的是
  **同一个 KLine 实例上共享的** `_plotinfo.lines`；
* 上一个指标（`Twin_Range_Filter` 的 base_line/upper/lower、
  `DynamicSwingAnchoredVWAP` 的 dsav）写进去的线名**不会消失** →
  下一个指标跑出来就带上它们 ✗

修法：跑指标前把 `KLine._plotinfo.lines` 换成**本次指标的干净容器**
（原始列名 + 本次 `lines` + `__init__` 里 `self.lines.x = ...` 写入的**数据**），
跑完**还原**原来的对象：

* `G_Channels(thresh=0)` → 只有 `a/b/avg` ✓
* `thresh=0.5` → `a/b/avg/zig` ✓；再跑 `thresh=0` 不会残留 `zig` ✓
* KLine 自己的线名不再被污染 ✓
* `__init__` 里 `self.lines.open = ha.open` 这种写法**照旧可用** ✓

测试：`tests/test_minibt_indicator_lines_isolation.py` 3 项。



### 修复：逐点文本（DivergenceMany）不按换行分行

用户 2026-11-19：`DivergenceMany` 的逐点文本在 bokeh 里是**多行**（带换行符），
desk 上挤成一行。

根因：`jslib/src/custom-series/custom-series.ts` 的 `marker` 画法只做了一次
`ctx.fillText(text, ...)` —— canvas 的 `fillText` **不认换行符** ✗
（同文件的 `label` 画法早就逐行绘制了）

修法：`marker` 文字按 `
` 拆行，用已有的 `textLineOffsets()` 算行偏移
（`circleUp`/上箭头 → 文字在点**下方**逐行往下；`circleDown` → 在**上方**逐行往上），
行高 `fontPx * 1.18`，空行也占高度保持对齐 ✓

测试：`jslib/test/custom-series.test.ts` 新增「marker 文本多行」1 项
（`'A
B
C'` → 三次 `fillText`，且 y 递增）。



### 指标**参数持久化**（设置卡片「应用」→ 记住，下次默认用它）

用户 2026-11-19：把 `zigzag_support_resistance` 的 `up_thresh / down_thresh`
改成 0，重新加载指标后点⚙，卡片里还是**默认参数**。

新增设置项 **`indicator_params`**（`{指标key: {参数: 值}}`，已进
`user_prefs.SETTING_KEYS` 白名单）：

1. **落盘**：指标设置卡片 / 参数弹窗点应用 → 前端
   `set_setting indicator_params`（本地图表 + 实时图表都接 ✓）；
2. **加载即默认**：`_on_add_indicator()` / `_on_local_add_indicator()` 里
   `merged_params = {**saved_indicator_params(key), **前端传的}` →
   没传的参数自动用上次的；传了就 `remember_indicator_params()` 记住；
3. **卡片读取**：`_attach_indicator_params()` 三处调用都过
   `_with_saved_params()`，图例 ⚙ 卡片显示的就是上次保存的参数
   （没保存过才用目录默认 ✓）。

`0` 也照常保存（`up_thresh=0` 不会被当成"没设置"✗）。

测试：`tests/test_minibt_indicator_params_memory.py` 5 项、
`jslib/test/indicator-params-memory.test.ts` 4 项。



### 新增指标：ZigZag 支撑阻力线 `zigzag_support_resistance`

用户 2026-11-19 要求：基于 `minibt/zigzag` 的转折点（高低点）做一条**水平**
支撑 / 阻力指标，两条线、**3px 虚线**。

**规则**（与需求一致）：

| 最近转折点 | `support` | `resistance` |
|---|---|---|
| 低点（例 1000） | 从这根起 = 1000，直到下一个高点出现 | NaN |
| 高点（例 1100） | NaN | 从这根起 = 1100，直到下一个低点出现 |
| 还没有任何转折点 | NaN | NaN |

所以任何时刻图上只有**一条**水平线，转折出现的那一根就切换 ✓

三处入口（和现有 zigzag 系列同构）：

1. `minibt/ta.py` → `ZigZag.zigzag_support_resistance(high, low, close,
   up_thresh=0., down_thresh=0., multiplier=1.)`（另有短别名 `zigzag_sr`）；
2. `minibt/core.py` → `btind_zigzag_support_resistance(...)`
   （`args : high, low, close`，插在 `btind_zigzag_returns` 之后）；
3. `minibt/indicators/btind.py` → `@tobtind(lines=['support','resistance'],
   overlap=True, category='overlap', lib='btind',
   linestyle={support: LineStyle(#26a69a, width 3, dashed),
              resistance: LineStyle(#ef5350, width 3, dashed)})`
   + 完整文档（默认 `up_thresh=down_thresh=0.02`）。

指标名：**`zigzag_support_resistance`**（BtInd 组，目录里显示
`zigzag_support_resistance · BtInd`，主图叠加）。

顺带修了一条**过期断言**：`tests/test_indicator_plot_settings.py` 里
`thermo` 的线名早就改成 `long_signal/short_signal`（不是 `thermo_long`）✓



### 修复：本地图表的选择器不记忆位置 / `BandStyle.fill_alpha` 不生效

**① 位置记忆只改了实时图表，本地图表完全没生效**（用户 2026-11-19 实测）

`LocalChartPage.setPicker()` 还是老逻辑：`open(favorites.length ? 'favorites' : 'all')`
—— 写死回「收藏」✗ 而用户测的正是**本地图表**。

→ 新增共享模块 **`jslib/src/desk/picker-state.ts`**（两种图表页共用）：

* `readPickerState()` / `savePickerState()`：`{section, filter, key, scroll}`
  存 `localStorage` + 后端设置 `indicator_picker_state`（双保险，节流 1s）；
* `bindPickerState(picker)`：把 section / 滚动 / 光标停留 / 顶部筛选都接到存储；
* `restorePickerState(picker, fallback, knownSections)`：**顺序**
  `筛选 → open(section) → restoreState（指标优先，否则滚动）`，
  打开即播种（第一次就存，下次有得恢复）；
* `ChartPage` 与 `LocalChartPage` 都改成调这三个函数（删掉各自的旧实现）。

**② `BandStyle(fill_alpha=0.01, fill_color=Colors.limegreen)` 填充不透明**

`indicator_catalog._rgba()` 以前只认 `#rrggbb` → **命名色**（`limegreen`）原样返回，
**没有 alpha** → LWC 填不透明色，`fill_alpha` 看起来没生效 ✗

→ `_rgba()` 现在统一处理：命名色（内置表 + matplotlib 兜底）/ `#rgb` / `#rrggbb` /
`rgb()` / `rgba()`（0~255 alpha 也按我们的 alpha 重写）→ `rgba(r,g,b,alpha)` ✓
`AdaptiveTrendTrail` 的色带现在下发 `rgba(50,205,50,0.010)`。



### 指标选择器「上次位置」彻底生效（双保险 + 打开即播种）

用户 2026-11-19：还是每次都回到「收藏」—— 说明 `localStorage` 里的状态**压根没存**
（或读不到）。三处加固：

1. **打开即播种**：每次打开选择器后，把这次用的 `section` / 顶部筛选写回状态
   （以前只有"点过左侧分组 / 划过指标"才存 → 大多数情况下是空的 ✗）；
2. **双保险持久化**：
   * `localStorage['desk.indicatorPicker']`（快）；
   * 后端设置 `indicator_picker_state`（JSON，走 `set_setting` 落盘，
     **Qt webview 里 localStorage 偶发不可用也不怕**）；
   * 读取时 `{...后端, ...本地}` → 本地优先，后端兜底 ✓
   * 保存节流 1s（滚动不刷屏），`user_prefs.SETTING_KEYS` 已加该键 ✓
3. **诊断日志**：打开时 `console.info('[picker] 恢复位置', {saved, section, known})`
   —— 一眼看出"存的什么 / 用的什么 / 现有分组有哪些"（下次再有问题直接看这行）。

恢复顺序仍是：左侧 section（并滚到可见）→ 顶部筛选 →（光标停留的指标
→ 没停留才用滚动位置）✓



### 「上次位置」补齐：左侧导航选中项 + 顶部筛选（全部/主图叠加/副图）

用户 2026-11-19：只记滚动 / 指标还不够 —— 打开时必须**先恢复**

1. 左侧导航选中的那一项（`section`，并把它在树里滚到可见）；
2. 顶部筛选（全部 / 主图叠加 / 副图）—— 它决定列表里有哪些行；

**然后**才定位到"上次光标停留的指标"，没停留过才用滚动位置
（顺序错了行数不同 → 位置全错 ✗）。

* `IndicatorPicker.restoreState({section, filter, key, scroll})`：
  `section → 筛选 →（revealKey 或 restoreScroll）` 一次摆好 ✓
* `_renderTree()` 结束后把 `.pylc-ip-section.on` **滚到可见**
  （左侧导航很长时也能一眼看出上次打开的是哪一项 ✓）
* 顶部筛选也进 localStorage（`desk.indicatorPicker.filter`）；没存过 → 空串，
  让后端设置 `indicator_overlay_filter` 生效（首次打开也对齐 ✓）
* `ChartPage.setPicker()`：先对齐筛选 → `open(section)` → `restoreState(...)`



### 「上次位置」两者兼容：光标停留的指标优先，否则用滚动位置

用户 2026-11-18 追加要求：两种方式都要 —— **光标停在某个指标上就更准地定位它**，
没停留过（从没划过任何指标）才用纯滚动位置。

* `IndicatorPicker`：
  * 每一行带 `data-item-key`，`mouseenter` / 点击时记下 `focusedKey`
    （节流 300ms → `onFocusCallback(key)`）；
  * `revealKey(key)`：滚到该行（`scrollIntoView({block:'center'})`，老内核用
    `offsetTop` 兜底）+ **高亮闪 1.6s**（`.pylc-ip-row-focus`）；找不到 → 返回 false；
* `ChartPage`：状态从 `{section, scroll}` 扩到 `{section, scroll, key}`；
  打开时 **`key` 优先**（`revealKey` 成功就不再用滚动值），否则 `restoreScroll` ✓；
* 「指标和策略」页（`TvPage`）：同样 `mouseover` 代理记卡片 key
  （`onFocusCallback` → `localStorage['desk.tvPage.focus']`），打开时
  `setFocusKey()` → `setList()` 里 `revealKey()` 成功就不滚；
  卡片高亮样式 `.desk-tv-card-focus`（2px 描边 + 柔光）✓



### 记住「指标、衡量标准和策略」上次打开的位置

用户 2026-11-18 要求：指标选择器下次打开停在**上次的指标位置**（选中的分组 +
滚动位置），而不是每次都回到「收藏 / 全部指标」顶部。

* `IndicatorPicker`（`pylightcharts` 面板）新增：
  * `sectionKey` / `scrollTop` 读取；
  * `onSectionCallback(section)` / `onScrollCallback(top)`（滚动节流 400ms）；
  * `restoreScroll(top)`（渲染后 rAF + 60ms + 200ms 各设一次，图片加载后也对 ✓）；
  * `open(section = '')` —— **不传就保持上次的 section**（以前固定回 favorites ✗）。
* `ChartPage` 把 `{section, scroll}` 存 **localStorage**（`desk.indicatorPicker`）：
  * 打开时若保存的 section 仍在目录里 → 用它，否则回落到「收藏 / 全部指标」；
  * 然后 `restoreScroll(saved.scroll)` ✓。
* 「指标和策略」页（`TvPage`）：按 **分组 + 星标 + 搜索词** 记住滚动位置
  （`scrollMemory`），切回同一分组 / 重新打开都回到刚才的卡片位置 ✓。



### 修复：蜡烛型指标（CumulativeDeltaVolume）隐藏时**连标签一起消失**

用户实测 2026-11-18：上一轮修好"隐藏后再显示"的同时，把右上角**图例行也删了** →
眼睛没了，指标再也点不回来 ✗

原因：`_removePane()` 清蜡烛序列缓存时顺手调了 `_dropLegendRow()`。

修法：只清 **`candleSeries` 序列缓存**，图例行保持不动
（设计上"隐藏副图但保留标签 / 眼睛"，用户可以再点回来 ✓）。

测试：`jslib/test/candle-pane-visibility.test.ts` 第 3 项加了断言
"该清理块里**不允许**出现 `_dropLegendRow`"。



### 指标：`MachineLearningRSI` 副图分段改成柱体（vbar_base=50）

用户 2026-11-18 要求：RSI 分段原来是**折线**（颜色切换处还断 1 根 bar），
改成**柱体**表示，柱底基线固定 **50**（>50 向上、<50 向下），段色保留。

* 4 段（`rsi_bull` / `rsi_bear` / `rsi_neutral` / `rsi_gray`）的 `linestyle`
  统一用新工具 `_vbar_style(color)`：
  `line_dash=vbar` + `vbar_base=50` + `vbar_up_color=vbar_down_color=<段色>`
  （两侧同色，段色就是语义，不跟 K 线涨跌色 ✓；`price_line/price_label` 关掉）；
* 分段语义不变：每段只在属于它的区间有值（bull 全 >50、bear 全 <50 ✓）；
* `midline`（50 中轴）/ `upper`（70）/ `lower`（30）仍画折线 ✓；
* 文档同步（"输出 lines" 里注明是柱体）。

测试：`tests/test_minibt_indicator_ml_rsi_vbar.py` 2 项（柱体 + base=50 + 段色 /
分段不重叠且 bull ≥50、bear ≤50）。



### 修复：副图蜡烛型指标（CumulativeDeltaVolume）隐藏后再显示只剩空白副图

用户实测 2026-11-18：`CumulativeDeltaVolume` 是**蜡烛型**指标（`kind:'candles'`），
放在副图里；点左上角眼睛隐藏、再点显示 → **副图还在，但蜡烛没了**。

根因：只有这一根线的副图被隐藏时会**整块删掉**（`_syncPaneVisibility`），
pane 里的蜡烛序列被 LWC 一并删除；但 `candleSeries` 缓存仍指向**已被删的序列** →
再次显示时走"已存在"分支，往死序列 `setData` 静默失败 → 图上空白 ✗

修法：

1. `_removePane()` 删副图时，把 `candleSeries` 里属于这个 pane 的缓存**一并清掉**
   （同时摘掉对应图例行）→ 下次 `apply()` 重新创建 ✓；
2. `_applyCandleSeries()` 的 `setData` 如果抛错（序列已死）→ **自动丢弃缓存重建一次**
   （`retry` 只重试一次，避免递归）→ 别的路径漏清也不会再空白 ✓。

测试：`jslib/test/candle-pane-visibility.test.ts` 3 项（首次显示 / 死序列自动重建 /
删副图清缓存）。



### 修复：交易页按钮 / 右键菜单没作用在**当前账户**上（撤单最严重）

用户实测 2026-11-18：账户切换已经正常，但交易页里挂单 / 撤单**落到了实盘**账户
（界面写「天勤模拟」、tqsdk 通知却是 `901211729` 资金不足）——账户切换只是显示变了，
**交易调用没跟着换账户** ✗

根因（`minibt/desk/trading.py`）：

* `cancel_order()` 调 `api.cancel_order(order_id=…)` **完全没带 `account=`** →
  多账户模式下撤的是默认（实盘）账户，或者直接报「需要指定账户实例」✗
* 查持仓 / 查委托里还有几处用 `self.account_kwargs(symbol)`
  （可能拿到 `None`），而不是保证有实例的 `_order_account_kwargs()`

修法：

1. **撤单带上账户**：`canceller(order_id=…, **_order_account_kwargs(symbol))`
   （带 TypeError 逐级降级，兼容老 tqsdk）；
2. 查持仓 / 查委托 / 查单**统一**走 `_order_account_kwargs()`（保证真有实例 ✓）；
3. 撤单日志带上账户名：`[撤单] 天勤模拟 DCE.pp2701 123456`；
4. 新增两行定位日志（排查"界面账户 ≠ 下单账户"）：
   * 登录后：`账户列表：TqMultiAccount → TqKq, TqAccount/H宏源期货/901211729`
   * 下单后：`[委托账户] DCE.pp2701 → TqKq（key=kq）`

**结论**：交易页所有按钮（买开 / 卖开 / 平今 / 平昨 / 反手 / 全平 / 撤单 /
持仓与委托右键菜单）现在都只走 `Trading.insert/cancel_order/action`，
而它们统一从**页面 key** 取账户实例 ✓



### 账户切换已正常；新增「委托账户」定位日志

用户 2026-11-18 反馈：切换账户已经正常（实盘 / 快期模拟来回都生效），
但**当前显示快期模拟**时挂单，实际挂到了实盘账户（tqsdk 通知里是
`901211729`，还报「资金不足」）。

为了定位"界面账户 ≠ 下单账户"，加两行**只读日志**（不影响逻辑）：

* 登录成功后：`账户列表：TqMultiAccount → TqKq, TqAccount/H宏源期货/901211729`
  （多账户时到底注册了哪几个 tradeable 实例 ✓）
* 每次下单：`[委托账户] DCE.pp2701 → TqKq（key=kq）`
  （真正传给 `insert_order(account=…)` 的实例类型 + 页面 key ✓）

另外两处已修（本轮之前）：

* `AccountView.account_kwargs()` 不再返回 `{'account': None}`
  （tqsdk 多账户模式会抛「需要指定账户实例」）；
* `Trading._order_account_kwargs()` 下单 / 撤单 / 查单逐级兜底到真实实例。



### 修复：换合约后账户切换失灵 / 切到快期模拟平仓报「需要指定账户实例」

用户实测 2026-11-18：

1. 初始化实时图表时能自由切换实盘 / 快期模拟；**换合约后**就切不动；
2. 登录实盘后去平**快期模拟**的 pp2701 持仓 → tqsdk 报
   「多账户模式下，需要指定账户实例」。

两处根因：

**① 换合约后前端还在用旧页签 id**

`ChartPage.setSymbol()` 只改了 `options.symbol`，没改 `options.pageId` /
`dock.pageId` → 切账户命令仍发 `page='chart:旧合约'`，后端写进一个已经不用的页；
每秒补丁读 `chart:新合约#0`（旧账户）→ 按钮被顶回 ✗

**② `account_kwargs()` 会返回 `{'account': None}`**

`instance_for(key)` 取不到对应类型时返回 None，但 `account_kwargs` 仍然
`{'account': None}` → tqsdk 直接抛「多账户模式下，需要指定账户实例」✗

修法：

* `ChartPage.setSymbol()` 同步更新 `options.pageId = chart:<新合约>` 和
  `dock.pageId`（账户 / 买卖盘等按页路由的命令才对得上 ✓）；
* `AccountView.account_kwargs()`：取不到对应类型时**用列表里第一个真实账户兜底**
  （并记一次 warning），**绝不传 `None`** ✓；
* `Trading` 新增 `_order_account_kwargs()`：下单 / 撤单 / 查单逐级兜底
  （页面账户 → 该行情源第一个账户）→ 平仓、撤单在"已切换但类型缺"的情况下
  也能落到一个真实账户，不再报错 ✓。



### 修复：换到某个合约后切换账户「完全没反应」

用户实测 2026-11-18：开图时来回切换账户都正常；切到 pp2701（有限价挂单，
撤单后依旧）就切不动了 —— 只有下拉框闪一下，面板数据一动不动。

根因**不是挂单**，而是 **cell 过滤**：

* 后端推账户补丁时带 `cell`（焦点格，`_focus_symbols`）
* 前端 `case 'account'` 里 `patchCell !== activeCellIndex` 就**整包丢弃**
  （防止别的格的账户串台）

切到某个合约后焦点格和 `activeCellIndex` 分叉 → 用户主动切换推来的包被**丢掉**
→ 下拉框回弹、面板不变 ✗

修法：

1. `set_account_kind()` 推的 `account` / `trading` / `account_kind` 都带
   **`force: True`**（这是用户主动切换的结果，就是给这一页的）；
2. 前端 `case 'account'` / `case 'account_kind'`：`force` 的包**不看 cell**，
   直接应用到这一页 ✓（每秒的节拍补丁仍然按 cell 过滤，多格不串台）；
3. 账户读取改走 `_fast_account_payload()`：后台线程取数 + 最多等 1.5 秒 +
   失败用上一份缓存（标 `stale`）→ 实盘的 `get_order()` / `get_position()`
   再慢也不会把命令 / 节拍拖住（用户实测：有挂单时界面像"卡住不动" ✗）；
4. 切换后的持仓线 / 挂单线刷新也移到后台线程，命令立刻返回 ✓。



### 修复：挂单后切换账户「没反应 / 按钮又弹回去」

用户实测 2026-11-18：开实时图表切实盘正常；对 `pp2701` 挂单之后再切
「快期模拟」失败 —— 整个交易页面数据不变，只有下拉框闪一下又弹回实盘。

根因是**读写口径不一致**：

* 下拉框发来的 `cell` = 页面的 `activeCellIndex`（点过哪格就是哪格）
* 每秒账户补丁读的 `cell` = **焦点格**（`_focus_symbols`，来自 `focus_chart`）

挂单 / 点过别的格之后两者会分叉 → 写进 `page#1`、每秒却读 `page#0`（还是旧账户）
→ 下拉框被顶回去、面板不动 ✗

修法：

1. `set_account_kind()` 除了写请求的 `page#cell`，**同时写焦点格**
   （`_set_account_key(target_store, key, '同页焦点格')`）→ 读写永远一致 ✓；
2. 切换前**校验目标账户真的存在**（`view.instance_for(key, symbol)`）：
   登录的账号里没有「快期模拟」就明确拒绝 + toast + 恢复下拉框，
   不再出现"按钮变了、数据不变"的半截状态 ✓。



### 修复：切实盘后「很快就跳回快期模拟」—— 找到偷偷改 key 的地方

用户实测 2026-11-18：开实时图表不换合约，切实盘后数据**已经**变成实盘（权益
9,018.36），但一秒左右又跳回快期模拟。

两处静默改写：

1. **`active_account_key()` 悄悄改用户选择** —— 行情源短暂不可用（盘前 / 断线
   重连 / `_feed_online()` 为假）时走 fallback，顺手 `self._account_kind =
   fallback`（= kq）→ 用户选的实盘被改掉 ✗
   → 现在**只返回**"当下可用"的 key，用户的选择原样保留；
2. **账户 key 有 5 处写入**（用户切换 / 同页镜像 / 换标的自动 / 换合约搬 key /
   开图默认），出问题时完全看不出是谁改的 ✗
   → 新增唯一入口 **`_set_account_key(store, key, reason)`**，值**变化**时记一行
   `账户切换：chart:SHFE.ad2612#0 → kq（换标的自动）`，下次再出现直接看日志。

关于「告警」：核对过告警 / 风控 / 定时任务链路，**都不会**写账户 key
（只读 `account_key_for()`），所以告警本身不影响账户切换 ✓



### 账户切换：彻底关掉「自动切换」+ 持仓 / 挂单 / 交易跟着账户走

用户实测 2026-11-18（三条一起提的）：

1. 没有持仓的合约上切实盘 **成功**；
2. **切合约**时又被自动切回快期模拟 → 要求「账户只能通过切换按钮改」；
3. 有持仓的合约上切实盘失败（按钮闪一下实盘又跳回去），账户页数据一直是模拟；
4. 要求切账户后**交易 / 账户显示 / 持仓线 / 挂单线**全部跟着换。

修法：

* **`AUTO_ACCOUNT_ON_SWITCH = False`** —— 换标的**不再**按品种自动写
  `kq` / `futu`（以前这就是"按钮自动跳回快期模拟"的元凶 ✗）；
  `_auto_account_for_symbol()` 在这种情况下原样返回当前 key，绝不改；
* **持仓线 `position_payload()` 带上这一页 / 这一格的账户 key**
  （以前 `view.account_kwargs(symbol)` 不带 key → 永远查默认（模拟）账户，
  所以切了实盘持仓线还是模拟的 ✗）；
* **挂单线 `pending_orders()` 同样带 key**（`AccountView.pending_orders(symbol, key)`
  也改成按 key 取 `api` 与 `account=`）；
* **切完账户立刻重推**这一页所有格的持仓线 / 挂单线 / 交易状态
  （以前只推账户面板，图上的线和交易页要等下一拍 ✗）；
* 兼容旧的 `account_kwargs(symbol)` 签名（第三方 / 测试桩不会炸）。

测试：`test_switch_symbol_no_longer_overrides_account`（重写：切实盘后换标的仍保持实盘）、
新增 3 项（无自动切换 / 持仓与挂单按页 key / 切完重推）。



### 修复：LSP 只对第一个编辑器生效（实时图表页的编辑器拿不到 LSP 地址）

用户实测 2026-11-18：`minibt desk` 启动时打开的那个**本地图表**里的编辑器
LSP 可用；之后打开的**实时图表**页的编辑器全部「LSP 未启用」、红点闪烁，
手动重启也只看到后端日志 `LSP 已启动：ws://127.0.0.1:55221` 而前端连不上。

根因（**不是** LSP 服务单例，服务本身早就支持多连接）：

| 页面 | 建 `EditorPanel` 时有没有传 `lsp` |
|---|---|
| `local-chart-page.ts` | ✅ 有 `lsp: () => this.options.lsp?.()` |
| `chart-page.ts`（实时图表） | ❌ **漏了** —— 页面上根本没有 LSP 地址 |

`app.openChart()` 也没给 `ChartPage` 传 `lsp` → 实时图表页的编辑器
`createClient()` 直接返回 null（「LSP 未启用」）✗

修法：

1. `ChartPageOptions` 增加 `lsp?: () => { url; root } | undefined`；
2. `app.openChart()` 传 `lsp: () => this.lspInfo || undefined`；
3. `chart-page.ts` 建 `EditorPanel` 时传 `lsp: () => this.options.lsp?.()`。

至此三种页面（本地图表 / 实时图表 / PI 独立界面）的编辑器都能拿到同一个
LSP 地址，后端按**连接集合**各自收发（v1.3.9-28 已改），可以同时多开 ✓

测试：`jslib/test/editor-lsp-wiring.test.ts` 4 项、`tests/test_minibt_desk_editor_lsp_reconnect.py`
新增 `test_realtime_chart_page_passes_lsp`。



### 修复：交易账户页切到实盘后又自动跳回快期模拟

用户实测 2026-11-18：

```
[12:15:16] 「首页」交易账户 → TqAccount            ← 首页切换 ✓
[12:17:00] 「SHFE.ad2612」当前已是 TqAccount       ← 后端 key 已经是实盘
[12:17:00] 账户已生效：TqAccount｜权益 9,018.36
          但页面下拉框又跳回「快期模拟」，卡片还是模拟数据 ✗
```

根因：`_auto_account_for_symbol()`（**换标的**时按品种自动切账户）会
**无条件覆盖**用户手选的账户 —— 期货合约 → 强制写 `kq`，于是刚切的实盘
在切一次合约 / 重载后被顶回快期模拟 ✗（它的注释写着"用户手选的实盘也不覆盖"，
但代码里缺了这个判断）。

修法：

1. `set_account_kind()` 把「用户手动切过的页 / 格」记进 `_account_user`；
   `_auto_account_for_symbol()` 遇到它们**直接返回当前 key**，不再覆盖 ✓；
2. `_account_patch()` 在 key **变化**时记一行
   `账户补丁：chart:X#0 → real`（诊断"被顶回旧账户"一类问题，只在变化时输出，
   不刷屏）✓；
3. 前端 `account-dock` 的选中项变化时打一条 `console.info('[dock] 账户选中项 → …')`
   （带上补丁 key / 目录 active，一眼看出是谁顶回去的）✓。



### 修复：登录了实盘却提示「天勤里没有实盘账户」/ 切换后又被转回模拟

用户实测 2026-11-18 日志：

```
[11:27:00] 天勤里没有实盘账户（TqAccount），无法切到实盘
[11:27:23] 天勤账户里没有实盘（TqAccount）→ 已回到快期模拟
[11:29:31] 账户已生效：TqAccount｜权益 901,702.14   ← 数据其实已经对了
           然后又转回到快期模拟
```

三处根因：

1. **只看 `broker_id` / `account_id` 判"是不是实盘"** —— CTP 登录要好几秒才回填
   这两个字段，这期间 TqAccount 被判成"模拟"，于是用户选的实盘被打回模拟 ✗
   → `AccountView` 新增 `_looks_real()`：类型是 `TqAccount` / `TqCtp` / `TqRohon`…
   就算实盘（`TqKq` / `TqSim` 仍是模拟）；`identity_of()` 也用它 ✓
2. **首页切换先写 key 再核对身份** —— 核对失败 `return False` 之后
   `_home_key` / `_account_kind` 已经被改，下一秒核对又把界面打回模拟 ✗
   → 改成**先核对身份、再写 key**，失败时 `_restore_account_kind()` 复位 ✓
3. **`instance_for()` 找不到对应类型时回落到 `items[0]`** —— 登录的只有实盘时，
   选「快期模拟」显示的是实盘数据（标签却写模拟），反过来也一样 ✗
   → 类型不匹配直接 `None`，`summary()` 返回空（面板显示 `--`）；
   `account_catalog()` 也按**真实存在的账户类型**标可用（没登录的那种置灰），
   点到不可用的会明确提示「看盘账号里没有实盘 TqAccount → 请在登录里勾选实盘重连」✓



### 修复：切到实盘账户（TqAccount）没生效（交易账户页 + 首页账户卡）

用户实测 2026-11-18：交易账户页 / 首页右上角账户概览切「TqAccount」都失败 ——
日志有 `「SHFE.ad2612」交易账户 → TqAccount`，但面板还是快期模拟的数据；
再点一次只回「当前已是 TqAccount」。

根因是 **key 记账口径不一致**：

| 位置 | 写法 |
|---|---|
| `set_account_kind()` 单布局 | 只写 `chart:X`（不带 `#cell`） |
| 每秒的 `_account_patch()` | 读的是 `chart:X#0` |

读的那一侧拿不到新 key → 用首页默认（快期模拟）→ 前端下拉框 / 账户卡**每秒被
顶回**旧账户，看起来就是切不过去 ✗；再点一次后端发现 key 已经存了 → 「当前已是」。

修法：

1. 写主 key 之后**把另一种口径也补上**（`setdefault`，不覆盖）；
   ⚠ 多布局（一格一个账户）**不镜像**到 `page`（否则股票格被写成实盘 ✗）；
2. 前端「钉住」用户的选择：`account-dock.ts` / `home-page.ts` 都记
   `pendingKey`，5 秒内（或后端确认前）一直显示用户选的那个，不被每秒补丁顶回；
   下拉框切换后顺带请求一次 `account_kind`（让这一页的 `active` 对齐 ✓）；
3. 切完立刻回一行**实际生效的账户 + 权益**
   （`账户已生效：TqAccount｜权益 555,000.00`）—— 下次出问题能一眼看出是
   key 没换还是数据源没换 ✓。

测试：`tests/test_minibt_desk_account_switch.py` 3 项、`jslib/test/account-switch-pin.test.ts`
2 项；`tests/test_minibt_desk_ticket_cells.py` 的多布局隔离用例保持通过（镜像只对
单布局生效 ✓）。



### 修复：编辑器多开只有第一个连上 LSP / 手动重启卡在「启动中」

用户实测 2026-11-18：

* 编辑器多开时，**除第一个外**其它编辑器状态栏都是「LSP 未启用」；
* 点「重启 LSP」后端日志显示 `LSP 已启动：ws://127.0.0.1:60934`，但界面一直
  「启动中」，悬停 / 补全仍无效 —— 结论「LSP 服务不能多开」。

四处根因：

1. **后端只记最后一条 WebSocket**（`self._connection`）→ 第二个编辑器连上来就把
   第一个顶掉，回包也发给"最后那条"：第一个编辑器的请求永远等不到结果 ✗
   → 改成 `self._connections: set`（连接集合），每条连接各自收包 / 回包；
2. **诊断防抖定时器只按 `uri` 存** → 两条连接同开一个文件会互相取消 ✗
   → 改成按 `(id(连接), uri)` 存；
3. **前端退避重试被死守卫挡死**：`if (this.lspRetried) return;` —— `[]` 是 truthy
   → 重试从来没跑过 ✗ → 改成 `if (this.lspRetried.length) return;`；
4. **圆点只看"后端有端口"** → 后端早就在跑、这一页编辑器却没连上也显示绿灯
   ✗ → 改成看**真实连接状态**（`onLspStatus('ok')` 才算连上），红灯 + 可点；
   重启后 6.5 秒仍没连上 → 状态栏明说「LSP 连接超时（点红点重试）」。

另外：**切到任意一页（重新打开实时图表 / 本地图表）都会给该页编辑器补连 LSP**
（`activate()` → `panel.refreshLsp(true)`），不再只有第一个编辑器能用 ✓

测试：`tests/test_minibt_desk_lsp_multi_client.py` 2 项 —— 真起服务开**两条
WebSocket**，各自 `initialize` 都要收到自己的回包；`jslib/test/editor-lsp-retry.test.ts`
增到 7 项（重试守卫 / 页面切换补连 / 圆点按真实连接 / 超时提示）。



### 编辑器状态栏：LSP 状态圆点（可点重启）

状态栏 LSP 徽标右边加一个**圆点按钮**（无文字，tooltip「重启 LSP 服务」）：

| 状态 | 颜色 | 可点 |
|---|---|---|
| LSP 未启用 / 出错 / 断线 | 🔴 红点，**1.1s 呼吸闪烁** | ✅ 点一下 `lsp_start {restart:true}` → 后端 `stop()` + 重新 `start()`，随后自动补连编辑器 |
| LSP 已启用 | 🟢 绿点（常亮） | ❌ 禁用 |

* 圆点状态跟着 `_setLspStatus()` 实时同步（连上立刻变绿 ✓）；
* 后端 `_on_lsp_start()` 新增 `restart` 参数：先 `stop()` 再起，
  端口重新分配 → 前端发现 URL 变了会**强制重连**所有编辑器 ✓
  （`CodeEditor.attachLsp(lsp, force)` / `EditorPanel.refreshLsp(force)`）。



### 编辑器：状态栏「LSP 未启用」→ 悬停 / 补全全哑

用户实测 2026-11-18：编辑器状态栏显示「LSP 未启用」，正在编辑或已保存的文件
都没有悬停 / 补全。

根因：**编辑器在后端 `lsp` 补丁到达之前就建好了** —— `spec.lsp` 是空的，
`lspExtensions()` 直接返回 `[]`（徽标显示「LSP 未启用」），之后再也不会重连 ✗

修法：

1. `CodeEditor.hasLsp` / `attachLsp(lsp)`：能带上 LSP **原地重建**，
   内容 / 路径 / 主题不变 ✓；
2. `EditorPanel.refreshLsp()`：给**已打开但没有 LSP** 的编辑器补连，
   并把徽标刷成「LSP 已连接（jedi…）」；
3. 打开文件时若 LSP 还没就绪 → **退避重试** 600ms / 1.6s / 3.5s / 7s ✓；
4. `app.ts` 收到 `{type:'lsp', status:'ready'}` → 通知所有编辑器面板
   `refreshLsp()`（多页 / PI 界面都覆盖 ✓）。

顺带核对（后端 jedi 实测）：`Strategy.` 能列出 266 个成员、`BtStop.` 能列出
9 个止损策略、`self.stop.buy` 悬停能拿到 `minibt.strategy.base.StrategyBase.buy`
的文档 → **LSP 连上就有补全**，之前只是没连上 ✓

### 「＋ → 实时图表」在同一合约已打开时打不开新页

用户实测 2026-11-18：已经开着一个实时图表，再点「＋ → 实时图表」什么都不发生 ——
`openChart()` 按 `chart:<合约>` 去重，直接 `activate()` 了旧页 ✗

修法：

1. `openChart(symbol, {forceNew})` + `_uniqueChartId()` →
   同一合约可以开多页：`chart:X` / `chart:X~2` / `chart:X~3`…（标签带序号 ✓）；
2. 「＋ → 实时图表」（含未连行情时的空白页）一律 `forceNew`；
3. 补丁路由 `_chartPageFor()` **优先激活页**（多页时喂给看得见的那页 ✓），
   再按 `symbol` 找重复页；
4. 切到重复页 → 5 秒内补一次 `open_chart` 快照（否则是空图 ✓）；
5. 关掉其中一个重复页**不退订后端**（还有页在用这个合约 ✓）；
6. `_renameChart()` 支持 `~N` 的页签 id（重复页里切合约不会撞主页 ✓）。



### 修复：进出回放后 `bandstyle`（色带）等样式消失

用户实测 2026-11-17：`pp_l_2609_60` 布局里格 2 的 `AdaptiveTrendTrail`
有 `bandstyle` 色带，**进回放 / 退出回放后色带就没了**。

根因：`_dropEverything()`（换合约 / 进出回放时调用）只删了序列，**没清
「挂在序列上的样式」缓存**，而重建时这些方法都是「缓存里有 → 跳过」：

| 样式 | 缓存 | 现象 |
|---|---|---|
| `bandstyle` 色带 | `bands` | `bands.has(key)` → `continue` → 色带消失 ✗ |
| `spanstyle` 参考线 | `spans` / `spanSig` | signature 没变 → `continue` → 参考线消失 ✗ |
| `tablestyle` 小表格 | `tables` / `tableOffsets` | DOM 节点留着但序列已换 ✗ |
| `watermark` 水印 | `watermarks` | 同上 ✗ |

修法：

1. `_dropEverything()` 里把 `bands`（先 `detachPrimitive`）/ `spans` /
   `spanSig` / `tables` / `tableOffsets` / `watermarks` **一起清掉**；
2. `_applyBands()` 再加一道判断：缓存的填充如果挂在**已经不是当前**的上沿线
   序列上，就 `detachPrimitive` + 重建（就算别处漏清也能自愈 ✓）；
3. `_applySpans()`：载体序列变了（换合约 / 进出回放）也要重画，不能只比
   `spans` 的 signature；对比用新的 `_liveCarrier()`（**只查不建**，
   避免每拍多一条隐形载体 ✗）。

`color` / `lineWidth` / `lineStyle` / `visible` / `priceLine` / `priceLabel` /
`crosshairMarker` 本来每拍都会重新 `applyOptions`，不受影响 ✓（已核对）。

测试：`jslib/test/style-survives-drop.test.ts` 3 项（首次画上色带 /
换合约后色带重画 / 连续推送不重复叠加）；
`tests/test_minibt_desk_replay_styles_survive.py` 4 项（缓存清理清单 /
band 重建 / span 载体判断 / 后端 band 条目带 lowerKey+upperKey）。



### 修复：信号标签删了、图上的箭头还在（换合约清理没删序列）

用户实测 2026-11-17（`点回放时交易信号标签是删除了但原始的交易信号还保留在图表上.png`
/ `退出回放后隐藏指标交易信号但图表上还有交易信号.png`）：标签没了，但图上的
箭头还在；退出回放后把信号标签的眼睛关掉，箭头依然画着 —— 说明**信号序列
根本没被删**，只是从图例里摘掉了。

三处根因：

1. **`_dropEverything()` 只清 Map、不删序列** —— 交换约 / 进出回放时调用它，
   自定义信号序列（handler 里的 custom series）留在图上继续画箭头，图例眼睛
   也管不到它 ✗ → 现在用 `handler.removeSeries(entry)` **真删**，同时把
   `markerSeries` 载体也 `removeSeries`；
2. **`_dropEverything()` 也不删图例行**（只 `legendRows.clear()`）→ 每清一次
   图例里就多留一组无主的行 ✗ → 现在真删行并从 `legend._lines` 里摘掉；
3. **回放时每格都塞页签合约**（`symbol: this.replaySymbol`）→ 第 2 格的图层
   发现"合约变了"就 `_dropEverything()`，**每一拍**都拆一遍再重建
   （标签累积 + 信号残留 + 图例重排）✗ → 改成每格用自己的合约
   （`cellSymbol`），实时图表 / 本地图表两处同步；
4. 顺手补：箭头自定义序列 / 原生 markers 都跟随 `visible`
   （图例眼睛或设置里关掉 → 一条箭头都不画 ✓）。

测试：`jslib/test/signal-legend-rows.test.ts` 增到 6 项（新增「换合约清理后
图例行数与信号序列数都不涨」「隐藏后箭头系列 visible=false」）。



### 信号标签仍在叠：加「同名图例行收敛」这道硬闸门

上一轮把信号的自定义序列改成不自动建图例行，但用户实测**仍然**看到
进回放 2 组、退出后 3 组（截图 `点回放时.png` / `格2回放时处理不干净.png`）。

补上最后一道防线 —— `IndicatorLayer._dedupeNativeLegend()`：

* 每次 `apply()` 结束时扫一遍原生图例，**同名（`normalizeIndicatorKey`）多行只留一行**；
* 有多个同名行时保留「归我们管」的那行（带 ⚙ / 眼睛），把历史残留的
  自动行（`createCustomSeries(name)` 老代码留下的）摘掉；
* 从后往前扫 → 留下的是**最后建的那行**（当前在用的 ✓）；
* 这样即使页面在旧代码里已经攒了几组残留，**一进入回放 / 一次推送就会收敛成一行**，
  不用重启浏览器 ✓。

配套：`jslib/test/signal-legend-rows.test.ts` 增到 4 项（新增「历史残留同名行
一次 apply 收敛成一行」；测试用的假 `makeSeriesRow` 也要写进**当前**的
`_lines`，否则清扫换数组后它写的是旧数组）。



### 修复：回放里的**交易信号**标签叠 2~3 组 / 时段外也有信号

上一轮只修了指标线，交易信号（`kind:'marker'` + `shapeRows`，走自定义序列）
还有两条漏网的路径（用户实测 2026-11-17 截图：进回放已 2 组信号标签，
退出后 3 组；把信号标签全隐藏才看不到下面重复的箭头）：

1. `handler.createCustomSeries(item.label, …)` 会**自动**建一行原生图例 ——
   那行不归 `legendRows` 管，删序列时容易漏 → 改成**名字传空串**，
   由 `_syncLegendRow()` 统一建一行（带 ⚙ / 眼睛，家族名去重 ✓）；
2. `shapeSeries`（信号自定义序列）以前按**原始 key** 存，
   `tv:X:line` 与 `X.line` 各建一条序列 → 图例一行行往上叠、箭头画两套 ✗
   → 改按 `_family()` 存，剪枝也按 `aliveFamilies` 比；
3. `_pruneNativeLegend()` 不再动**我们自己的行**（否则每拍删了又建，
   行会闪、顺序乱），只清「不是我们的、且 series 已经不在 handler 序列清单里」
   那种残留行；
4. `_clipToBars()` 同时管自定义序列与原生 markers → 选择时段之外的
   交易信号不会再画到图上 ✓

新增 `jslib/test/signal-legend-rows.test.ts`（3 项：同一批 apply 两次行数不变、
key 口径来回切行数不变、信号从 payload 消失后图例行跟着删）。



### 修复：多布局回放时第 2 格图例叠三组 / 交易信号提前出现

用户实测 2026-11-17（截图 `多布局回放还是有问题.png`）：2×1 布局里反复进出
回放，第 2 格左上角出现**三组**同样的 `AdaptiveTrendTrail.*` 标签；交易信号
还会**提前**画在图上，随着回放往后挪，走到那根 K 线才落上去。

根因都在 `jslib/src/desk/indicator.ts`：

1. 图例行 / 信号箭头载体 / markers 图元的 Map 按**原始 key** 存 —— 回放用
   `tv:AdaptiveTrendTrail:trend`、实时推送用 `AdaptiveTrendTrail.trend`，两个
   key 各建一份行 / 一条载体，旧的没人删 → 每进出一次回放叠一组 ✗
   → 全部改按 **`_family()`（归一化家族名）** 存；
2. `handler.createCustomSeries(name, …)`（信号箭头）会**自动**建一行原生图例，
   而删序列走 `chart.removeSeries()`（不摘图例行）→ 那行永远留着 ✗
   → 新增 `_pruneNativeLegend()`：`_lines` 里只要它的 series 已经不在
   handler 的序列清单里就摘掉（同时清掉我们 Map 里的引用）；
3. 图例清扫以前拿原始 key 和 `aliveKeys` 比（家族名永远对不上）→ 每拍全删
   重建 ✗ → 改比 `aliveFamilies`；
4. `dedupeIndicatorItems()` 现在**确定**地选 key 口径（带来源冒号的
   `tv:X:line` 优先，与顺序无关），`normalizeIndicatorKey()` **不转小写**
   （`MA20` / `MACD_DIF` 是身份）；
5. 新增 `_clipToBars()`：信号箭头 / 原生 markers 一律剪掉
   `time > 本格最后一根 K 线` 的点 → 任何链路漏裁都不会画出"未来"的箭头 ✓



### 修复：回放反复切换时第 2 格指标越叠越多

用户实测 2026-11-17（截图 `K线回放.png`）：在「K线回放」里不断切换时段，
第 2 格左上角的指标标签重复出现（`AdaptiveTrendTrail.*` 叠了 4 遍）。

三处根因一起修：

1. **`setIndicators()` 回放分支不看 `payload.cell`** —— 所有格的实时指标补丁
   都写进**第 1 格**的回放指标（`replayIndicators`），换格就混两份 ✗
   → 现在按 `payload.cell` 找 `replayCells[cell]`，只更新那一格；
2. **同一指标两种 key 口径**（回放/布局 `tv:X:line`，实时推送 `X.line`）都进
   `items` → 图例两行同名指标 ✗ → 新增 `jslib/src/desk/indicator-key.ts`
   （`normalizeIndicatorKey()` / `dedupeIndicatorItems()`），
   `setCellIndicators()` 与 `_applyReplayIndicators()` 都先去重
   （同家族留最后一份 = 数据最新，位置按首次出现 ✓，框式指标的多条线不受影响）；
3. 后端侧加回归测试（连开 3 次回放，每格指标条数、布局记录都必须**不变** ✓）。

### 回放工具条：删掉「选择合约」，改名「选择K线时段」

回放本来就是针对**当前布局**（每格合约固定），「选择合约」点了没有作用
（用户实测 2026-11-17 ✗）：

* 按钮文字 / title：`选择K线` → **`选择K线时段`**；
* 二级菜单只留 **`选择时间段`**（10%–90%，原样保留 ✓）；
* 实时图表 / 本地图表两处工具条同步改。



### 布局管理：搜索框加高

布局管理的搜索框跟普通输入框一样高（30px），列表一多就显小 →
新增 `.desk-lg-search`（**height: 60px**，圆角 8px、字号 14px），
只作用于布局管理这一处，参数编辑等其它行内的输入框不受影响 ✓。



### 修复：布局管理窗口不跟主题 / 悬停卡片看不清指标

- **配色不再写死在 JS 里**：以前 `PALS.dark/light` + 建窗口时把 `--lg-*`
  内联一次 → 切换主题后布局管理窗口还是旧配色（用户实测 2026-11-17 ✗）。
  现在全部走 CSS 的 `var(--desk-*)`（`body.theme-light` 覆盖 `:root`），
  切主题**立刻**生效；`setTheme()` 保留但只清历史内联值。
- **悬停卡片一个指标一段**：后端新增 `_layout_tip_indicators()`
  （`_layout_tip_base()` / `_tip_params()` / `_tip_value()` 配合）——
  框式指标（IndFrame，如 `pta_adx` 的 adxx/adxr/dmp/dmn 四条线）合并成
  `pta_adx(14, 14, 100, rma, 1, 0)`；单线指标（IndSeries）保持
  `pta_sma:sma(10, true, 0)`；参数超过 6 个用 `…+N` 收尾。
  布局列表的每格带 `tipIndicators`，卡片按「合约 → 指标（每项一段）→ 策略」
  排版（等宽字体）。

### 修复：二级子菜单展开后收不起来

`menu.ts` 的二级菜单是挂在 `<body>` 上的独立元素，**只有一级行有
`mouseleave`** → 鼠标离开子菜单后永远不会收起，布局多的时候会一直挡住下面的
「布局管理…」等菜单项（用户实测 2026-11-17 截图 ✗）。

- 子菜单改为**按行登记**（`subMenus: Map<行, 子菜单>`）+ 统一的
  `closeSub()` / `closeSubsExcept()`；
- 子菜单自身也监听 `mouseenter/mouseleave`（160ms 宽限），离开就收；
- 移到**没有子菜单的兄弟行**立刻收；移到另一个带子菜单的行只留新的；
- ⚠ 这一条**只挂在一级菜单的行上**（`depth === 0`）：二级菜单自己的行也挂
  的话，鼠标一进子菜单里任意一项就把父级子菜单收掉、又立刻重新展开 →
  菜单疯狂闪烁（用户实测 2026-11-17 第二次反馈 ✗）；
- 仍在关闭菜单 / 点击外部时一起清掉。



### 修复：窗口最大化后 VP（成交量分布）不见了

VP 是 desk **自己画在 canvas 上**的（贴可视区右边缘 + 鼠标跟随），
而 `resize()` 里只重设了各格图表和指标层，**没通知 VP 覆盖层** →
窗口最大化 / 拖动分隔条后 canvas 还是旧尺寸，横条按旧坐标画到了可视区外
（用户实测 2026-11-16：初始化时能看到 VP，最大化后就没了 ✗）。

- 修法：`chart-page.ts` / `local-chart-page.ts` 的 `resize()` 里逐格调用
  **`vpOverlays[index]?.resize()`**；`vp-overlay.ts` 的 `resize()` 再在
  **下一帧补画一次**（最大化时布局 / `priceToCoordinate` 可能晚一帧才稳定）。



### 修复：VP 图例数值把价格轴拉爆（K 线全压在底部）

上一轮给 VP 图例加了数值（峰值成交量，如 `11690`），但那根**图例锚定序列**
挂在**主价格轴**上 → 成交量被当成"价格"参与自动缩放 → 价格轴被拉到 14000，
K 线只剩底部一条（用户实测 2026-11-16 截图 ✗；把数值那行眼睛关掉就正常）。

- 修法：给锚定序列一条**独立且隐藏**的价格轴（`priceScaleId: 'desk-vp-legend'`
  + `priceScale(...).applyOptions({visible:false})`），并声明
  `autoscaleInfoProvider: () => null` —— **不参与任何自动缩放**；
  图例数值仍从序列数据里读（`rowValue`），显示不受影响 ✓。



### 新增：VP 图例带数值 / 布局悬停卡片 / 事件圆点可点开来源

用户 2026-11-16 三条：

1. **VP（成交量分布）左上角标签只有名字、没有数值** —— 其它指标都有。
   → 把「每根 K 线所有柱体里最高的那根（橙色 POC 柱）」的成交量灌进 VP 的
   **图例锚定序列**（隐形折线，本来只为挂图例）：`priceFormat.precision=0`，
   原生图例自动显示 `name : 12,345`，悬停历史 K 线也会跟着变 ✓（`indicator.ts`）
2. **布局管理只显示合约、看不到指标 / 策略** —— 原生 `title` tooltip 也是合约。
   → **禁用原生 tooltip**，改成自绘悬停卡片（同 PI 圆点那种卡片）：每格
   `#1 DCE.l2701` + `指标：sma(120), macd` + `策略：KalmanFilterStrategy`
   （`layout-dialogs.ts` 的 `layoutTipRows()`，指标 key 去掉库前缀、参数保留）。
3. **圆点事件不能点开来源** → `info.symbol_events()` 现在给每条事件带
   `source` + `url`：股票公告 → 东财「该股票公告列表页」；期货日历 →
   财经日历来源页（数据源本身不给逐条链接，不生造 ✗）；前端卡片里带 url
   的行变可点（悬停高亮 + 下划线），点击走 `open_url`（系统浏览器 ✓）。

- 用例：`jslib/test/layout-tip.test.ts` **3 项**（合约 + 指标 + 策略 / 空格不出现空行 /
  策略只有 path 时显示文件名）；`tests/test_minibt_desk_event_links.py` **4 项**
  （代码提取 / 公告链接 / 无代码不造链接 / 期货日历来源页）。



### 修复：加载布局后**旧合约的 K 线**要停留一小会儿

用户实测（2026-11-16）：加载布局时，如果当前图上的合约不是布局里的，
**加载前的合约仍留在图上**，要等下一拍行情更新才消失（体验差）。

两个原因：

1. **后端指纹没作废**：`_refresh_tabs` 判"要不要全量替换"看
   `_kline_bars_len` / `_kline_first_time`；两个合约同为 1 分钟、根数相同、
   首根时间也相同（很常见）→ 判不出变化 → 只推**增量 2 根** → 旧蜡烛留着 ✗；
2. **前端把旧 K 线搬回新格**：`ChartPage.applyLayout()` 里
   `keepBars`（本意是"换布局预设但合约不变时画面别闪"）**换合约也照搬** ✗。

修法：

- 后端：应用布局 / 切合约都 `_reset_kline_state()` + 清 `_ind_cache` /
  `_cell_state` / `_cell_ind_at`；新增 **`_push_cell0_bars()`** 在应用布局时
  **立刻全量替换格 1**（不等下一拍）；格 2..N 由 `_push_cell_bars()` 全量推。
- 前端：`applyLayout()` 里旧 K 线**只在该格合约未变时**保留；合约变了就
  丢旧 bars 并 `_applyCellBars(index)` **立刻清空**（顺带清持仓线 / 缓存）。

- 用例：`tests/test_minibt_desk_layout_apply_fresh.py` **3 项**
  （格 1 全量替换 / 非 tab 合约带 `cell:0` / 应用布局作废全部指纹）。



### 修复：编辑器「刚打开正常，编辑中就失效」的悬停 / 补全

用户实测（2026-11-16）：打开文件时类 / 方法的悬停注释、类补全都正常，
**一开始编辑就失效**，保存后也不恢复，重新打开文件又好。两个根因：

1. **jedi 不是线程安全的**：诊断跑在 `threading.Timer` 线程，悬停 / 补全跑在
   WS 请求线程 → 两者同时用同一个 `jedi.Script` / `environment` 会偶发抛错，
   被 `except` 吞掉后返回空 ✗（所以"编辑时（诊断频繁触发）才坏"）。
   修法：新增 **`LspService.engine_lock`（RLock）**，把 `textDocument/*` 的
   全部智能功能和诊断统一串行化。
2. **文档同步只认全量**：`didChange` 只取 `contentChanges[-1]['text']`，客户端
   一旦发**增量**（带 `range`）改动，内存文本就被写成一小段 → jedi 解析失败 →
   悬停 / 补全全空；而 `didSave` 又被**忽略**，所以保存后也恢复不了 ✗。
   修法：`didChange` 兼容增量（新增 `_apply_range_change()`，按行 + 列把改动
   应用到当前文本）；`didSave` 以**磁盘为准**重新读入并重算诊断（自愈）。

- 用例：`tests/test_minibt_desk_lsp_sync.py` **6 项**（增量单行 / 多行 / 越界夹取、
  文档保持完整、锁可重入、并发 hover+diagnostics 不出空）。
- 顺带把 3 条"源码字面量"测试放宽（pyupgrade 把 `lambda` 换成 `def`、
  把长行折行之后它们失效）：`test_vbar_histogram_colors` / `test_minibt_desk_p89`。



### 修复：策略首次加载少副图 / 格 1 画线删不掉 / 编辑器 minibt 路径不生效

用户实测 2026-11-16：

1. 策略**第一次**加到图表 → 少一个副图指标（第二次才齐）；
2. 左右布局里**格 1** 右键「Delete Drawing」删不掉画线（格 2 正常，
   只能靠工具栏「删除所有画线」，但那会全清掉）；
3. 编辑器里类 / 方法的悬停注释、类补全异常；设置里填了 minibt 路径**不生效**。

**① 首次加载少副图 / 少策略线**
- `_ind_cache` 以「最后一根 K 线时间 + close」为键；策略刚挂上时同一根 K 线没变
  → `_refresh_indicators()` 直接 return，**新加的副图永远不推** ✗；
  应用策略结果后也没有推格 2..N 的策略线（要等下一拍）。
- 修法：应用策略结果（异步 `_apply_realtime_strategy_result` 与同步
  `_add_strategy_to_chart` 两条路）都 **作废 `_ind_cache`** 并**立刻**
  `_push_cell_indicators()`。

**② 格 1 右键删除画线无效**
- 画线保存回调是 `save_drawings<handlerId>_~_<json>`；重建格子 / 单格→多格后
  回调里的 id 可能与 `cellHandlerIds[0]` 的旧值不一致 → `SAVERS.get(id)` 落空
  → 删除结果被丢弃 ✗（"删除全部"走显式 `clear(key)` 所以有效）。
- 修法（`jslib/src/desk/drawings-sync.ts`）：额外按 **key** 注册保存器；
  未知 id 时用 `fallback()`（当前活跃格的键）兜底并记住；`chart-page.ts`
  传入 `fallback: () => ({id: _activeHandlerId(), key: _drawingKey()})`。

**③ 编辑器 minibt 路径填了不生效**
- `_editor_minibt_path()` 以前要求**再勾选** `editor_minibt_path_enabled`（默认关）
  → 用户以为"填了没用" ✗。现在**填了就生效**，该开关只用于临时停用（显式 false）；
  保存路径时自动把开关置 true。

- 用例：`tests/test_minibt_desk_strategy_first_push.py` **3 项**、
  `tests/test_minibt_desk_layout_contracts.py` 6 项、
  `jslib/test/drawings-sync.test.ts` **3 项**（已知 id / 旧 id 兜底 / 不同格不串键）；
  `pytest -k "desk or packaging"` **2165 passed**；`vitest` **149 passed**。



### 修复：已登录天勤却报「合约无法加载」+ 多布局策略线重复

用户实测（2026-11-16，已登录天勤）：

1. 应用**左右布局** → 「布局中的合约无法加载，已跳过 `DCE.l2701` / `DCE.pp2701`
   —— 天勤合约列表里没有这个合约」；
2. `test_8.py` **加到图表** → 第一次「天勤合约清单尚未加载，请稍后重试」，
   点第二次才成功；
3. 多布局里**两个格子挂了同一套策略指标**（单图加载正常）。

**根因 1（误杀合法合约）**：校验用 `api._data['symbols']`，而它是**懒加载**的
—— 用户只浏览过 CFFEX 时里面只有 CFFEX 的 28 行（状态栏也能看到
`FUT · CFFEX · 28 行`），DCE 一条都没有 → 直接被判"合约不存在" ✗。

- **修法**：`_ensure_realtime_contracts()`（布局）与
  `_validate_realtime_contracts()`（策略）遇到**清单为空**时改成
  **放行 + 后台重取**（新增 `_queue_contract_refresh()`，不阻塞主线程）；
  只有"清单非空且确实没有"才提示（保留防订阅错合约的保护 ✓）。

**根因 2（策略线画到所有格）**：`info['strategy_items']` 是 `collect()` 里
"线最多的那组"，配对策略里很可能是**另一格**合约的组；格 0 以前无条件画它
→ 左右两图都出现 `zscores` ✗。

- **修法**：新增 `_cell0_strategy_items()`：多布局时格 0 按**自己合约**
  精确取组（取不到就不画）；单图行为不变 ✓。

- 用例：`tests/test_minibt_desk_layout_contracts.py` **6 项**
  （清单为空不拦截 ×2、清单非空仍拦截 ×2、格 0 按自己合约取组、
  非本策略的格不画线）；`pytest -k "desk or packaging"` **2162 passed**。



### 清理与修复：本地模拟账户（`minibt/desk/local_data.py`）

- **删掉一行死代码**：`payload()` 里 `balance = self.cash + market_value`
  算了但**从未使用**（`values['balance']` 取的是 `_account_values()['equity']`，
  期货按保证金口径 = `cash + 浮动盈亏`）。留着容易误以为账户权益 =
  「现金 + 名义市值」✗ —— 已删除并留注释说明。
- **修掉「分析页」真 BUG**：`analysis()` 里格式串写成 `f'...: , .2f'`
  （逗号/点号两边带空格）→ `ValueError: Invalid format specifier`，
  只要有一个**平过仓**的合约，「本地模拟账户 → 分析」页就直接报错 ✗
  → 改成 `:,.2f`。
- **文本守护测试抗现代化**：仓库做了一次 pyupgrade（`Dict[...]` → `dict[...]`、
  `Optional[X]` → `X | None`），7 条"源码里必须出现某段字面量"的测试全红
  （`float_state` / `_book_watch` / `attachments` / `home_events` / `spark_values` …）
  → 改成**正则宽松匹配**（新旧拼写都认），行为没有变化。
- 用例：新增 `tests/test_minibt_desk_local_account_equity.py` **2 项**
  （`balance` 必须等于保证金口径的 equity，且 ≠ `现金+市值`；平仓后分析页能出表）。



### 修复：账户面板的小数位和报价页对不上（`decimals_of` 链路）

- **现象**：实盘 / 快期持仓里 `ag2612` 的持仓价、委托价、成交价显示
  `13,974.00`，而报价页（同一个合约）显示 `13,974` —— 同一份数据两套小数位。
- **根因**（`minibt/desk/accounts.py` 的 `decimals_of` 封装 + `Desk.decimals_of`）：
  1. `Desk.decimals_of()` 只认**报价行** `_last_rows`（= 自选 / 图表订阅过的合约）；
     持仓里没订阅的合约拿不到 `price_tick` → 一律退回 **2 位**；
  2. 兜底队列 `_decimals_queue` 在**实盘**会被 `_fill_decimals_step()` 直接清空
     （怕 `get_quote()` 阻塞、弄坏 `ins_query` 通道）→ 实盘**永远补不上** ✗；
  3. 封装本身 `int(getter(symbol))` + `except Exception: pass` → `int('x')` /
     `None` 抛错被静默吞掉，悄悄变 2 位且没有任何日志；`default` 也没法透传。
- **修法**：
  - 新增 **`Desk.local_price_tick(symbol)`**：报价行 → **tqsdk 已经下载好的合约
    字典** `api._data['symbols'] / ['quotes']`（`query_symbol_info` 自带
    `price_tick`）。**零请求、零阻塞**，实盘也能立刻拿到正确 tick ✓；
  - `AccountView.decimals_of(symbol, default=2)`：`default` 透传、结果必须
    在 **0~8** 之间（脏值退回 default）、真出错时**每个合约只记一次**运行日志；
    同时兼容「只接受 `(symbol)`」的 desk（先试两参，`TypeError` 再试一参）；
  - `Trading._decimals()` 同一套口径。
- 用例：`tests/test_minibt_desk_decimals_consistency.py` **8 项**
  （报价行命中 / 未订阅走本地字典 / 实盘不排队 / 未知合约排队 / default 透传 /
  脏值拒绝 / 异常只记一次 / 持仓表 `13,974` 不带 `.00`）。



> **一句话**：1.3.9（`-1 ~ -6`）只动**文档 + 一个指标**：两版升级须知、
> VS Code 扩展 0.3.12 说明、13.29 的 VS Code 用法，外加
> **ITG Scalper 按 Pine 原码复刻样式**（每个信号都写成交价）。
> **公共 API 零破坏**，依赖仍是 `pylightcharts >= 0.2.2`。

### 新增 / 修改

- **文档 `13.33 升级须知（v1.3.7 / v1.3.8）`**：升级步骤 + 版本对应表、
  9 条「会感觉变了」、能力地图（按场景查工具）、账户与下单口径
  （`PENDING` ≠ 成交 ≠ 排队）、PI 悬浮窗手势表、常见坑 8 条、三步排错；
- **`1.32 minibt-charts 扩展简介` 补到 0.3.12**：Codelens、状态栏端口、
  MCP 接 Copilot、PI 助手三种形态 + 会话树、`desk_vscode` 反向通道、
  CSV → desk 本地图表、启动行为变化、已移除的技术面面板；
- **`13.29` 新增 2.4（VS Code 里跟 PI 对话，含 `@minibt` 8 条斜杠命令）
  与 3.8（`desk_vscode` 五个 action + 三个开关）**；
- **`ITGScalper`（`minibt/indicators/tradingview.py`）**：
  - 位置挪到 `VolumeProfileMA` 下方；
  - TEMA 单色 aqua `#00FFFF` + 宽 2（**不做**原码 `cc=true` 的绿/红条件变色）；
  - 买点绿色正三角（锚 low）、卖点红色倒三角（锚 high），size 走引擎小号；
  - 新参数 `use_label`（原码 `uselabel`）+ `signal_text()`：**每个**信号都写
    成交价（`tostring(truncate(price, 8))`）；新增 `buyprice` / `sellprice` 两列；
  - `show_tema` / `show_signals` / `noise_filter` / `filter_*` 行为不变。

### 验证

- 新增 `tests/test_minibt_itg_scalper.py`（9 项）· `test_volume_profile.py`（8 项）；
- `mkdocs build --strict` **0 警告**；
- `pytest -k "desk or packaging or docs"` 全绿（历史 2 项与本版无关的失败另记）。

## [1.3.8] - 2026-11-13

> **一句话**：1.3.8（`-1 ~ -24`）是 **PI 助手**的一整轮：把 VS Code 面板做到和
> desk 的 PI 页基本一致，并让**两边的会话 / 目录 / 选项双向同步**；顺带修
> 多布局右格的 K 线 / 挂单线问题。**Python 公共 API 零破坏**，
> 配套前端 **`pylightcharts 0.2.2`**（`Requires-Dist: pylightcharts>=0.2.2`）。

### 新增

- **VS Code 扩展 `minibt-charts 0.3.12`**：PI 助手面板（会话列表 + 对话）、
  MCP 配置生成 / 自检、反向通道（`desk_vscode`）、技术面面板、左栏新图标。
- **PI 对话区照搬 desk**：思考折叠 → 工具卡 → 结论 markdown → 用量 + 复制；
  右侧圆点导航、`↓ 回到底部`、每轮 分支 / 重新生成、会话行右键菜单、
  图片缩略图 + 大图、desk 同款输入区（附件 / `@` / 模型 / 强度 / 权限 / 压缩）。
- **minibt 侧**：`tools.CORE_TOOLS` / `exposed_names()`（`MINIBT_MCP_TOOLS=core`
  → 32 个常用工具）；`desk_pi`（session / 选项 / 目录 / 技能 / 分支 / 重新生成 /
  导入共 22 个 action）；`desk_vscode`（state / open / read / insert / run）；
  `desk_open_ui{pi}`；`Desk._pi_sessions_payload()`（会话列表唯一数据源）；
  `pi_event` 环形缓冲（4000 条 / 会话，带 `seq`）；`MINIBT_AI_DIR`；
  新命令 `pi_branch` / `pi_regenerate`；`_session_view()` 带 `index`。

### 修复

- **多布局第 2 格 K 线慢 / 重影**：增量改按时间合并 + 尾部 `series.update()`；
  后端指纹补 `high/low`，策略后台计算暂停时写运行日志。
- **第 2 格挂单 / 持仓线不消失**：补丁带 `cell_symbol`，前端按真实格合约判断。
- **VS Code 里 desk 打不开（`code=1`）**：天勤 `sys.exit(1)` 会整进程退出 →
  登录改 `except BaseException`，**回退离线继续启动**，界面线程同样兜住。
- **启动不再自动拉起 desk**（只认 `minibt.desk.autoStart`）；PI 面板先 `/health`
  探活，不自动起 desk；左栏只是启动器。
- **PI 会话默认 `permission: full`**（否则 `desk_*` 工具全被过滤）；
  测试不再写真实会话目录（`MINIBT_AI_DIR`）。
- **PI 面板交互**：并发启动互相 kill（`ensureDeskBridge` 单飞）、按钮点了没反应
  （`ReferenceError`）、模型显示「未配置」（直读 `models.json`）、附件发不出 / ✕ 关不掉、
  两端会话列表不一致（改用 desk 的同一份）、对话顺序（**思考 → 工具卡 → 结论**）、
  圆点导航 / 用量条 / 输入区整块消失（残留 `if (skillsOpen)` 让渲染抛异常）。
- 删除扩展里「模型 / 技能」两个入口（VS Code 打不开 desk 的设置界面，
  配置与安装只在 desk）。

### 打包

- `minibt-1.3.8-cp312-cp312-win_amd64.whl` / `minibt-1.3.8.tar.gz`，`twine check` 双 PASSED，
  `scripts/check_dist_fresh.py` 与工作区逐字节一致，sha256 见 `dist/SHA256SUMS.txt`。
- 测试：`pytest -k "desk or packaging"` **2131 passed / 1 skipped**；
  `jslib` `vitest` **146 passed**；扩展 `npm test` **62 项**。

## [1.3.7] - 2026-11-11

> **一句话**：1.3.7 是 **desk（交易终端）+ PI 助手** 的一整轮迭代
> （2026-11-08 ~ 11-11，**110 轮**，`v1.3.7-1 ~ -110`）。先把「`import minibt`
> 直接崩」「指标目录少了很多」修死；再把**编辑器**按性价比补齐；然后做出
> **零 npm 的 PI 助手 + MCP 工具桥**（72 个工具，AI 能直接操控 desk）；
> 最后用**资讯中心 / 告警中心 / 定时任务 v2** 把终端做成"能自己盯盘"的东西。
> 本文件是分轮次的简版日志，完整版（按 A~H 分组、110 小节）在
> `minibt_docs/docs/changelog.md`。

> **本版已打包**：`__version__ = 1.3.7`（`pyproject.toml` / `__init__.py` /
> `README.md` 徽章三处一致，`tests/test_minibt_packaging.py` 校验）。
> 配套前端 **`pylightcharts 0.2.1`**（desk 的告警中心 / 定时任务页 / PI 助手 /
> TA 悬浮标签都在那边），建议先 `pip install -U pylightcharts==0.2.1` 再启动 desk。
> 产物：`minibt-1.3.7-cp312-cp312-win_amd64.whl` + `minibt-1.3.7.tar.gz`，
> `twine check` 双 PASSED，sha256 见 `dist/SHA256SUMS.txt`。

- **PI 会话两边不同步（VS Code 扩展 ↔ desk）**：扩展以前自己扫会话文件，
  desk 用 `_pi_sessions_payload()`（置顶排序 + 只显示当前目录 + pi 导入的会话）→
  个数 / 顺序都对不上；且扩展改完只有扩展刷新 ✗。现在：
  `desk_pi{sessions}` 直接返回 desk 的同一份 payload（含 `dir` / `pins`）；
  `new/pin/rename/delete/merge` 改完推 `pi_sessions` 补丁 → desk 的 PI 页立刻刷新；
  `desk_pi{new}` 用 desk 的 `_pi_root()` 建会话（否则被目录过滤掉），权限默认 `full`。
- **对话顺序**：PI 一轮的顺序改成 **思考 → 工具卡 → 结论在最后**
  （`pi-chat.ts` 的 `paintRound()`；扩展的 `pi-view.js` 同步）。

- **`desk_pi` 补齐 desk PI 页的入口**：`dir` / `set_dir`（切 PI 目录，写 `pi_root`
  并推 `pi_sessions`）、`options` / `set_options`（会话级 模型 / 强度 / 权限 / 压缩，
  推 `pi_session` + `pi_models`）、`skills_install`（包名 / 本地目录）；
  `send` 改为**复用 desk 的 `_on_pi_send`**（附件 / `refs` / 选项 / 排队全走同一条
  链路）；`history` 追加 `options / usage / context / window / percent`
  （VS Code 面板标题后的用量条用同一组数字）。

- **PI 补齐 desk 的可加项**：新命令 `pi_branch`（从某条消息分支）/
  `pi_regenerate`（重新生成上一条回答），`desk_pi` 新增 `branch` / `regen` /
  `import_sessions`；`_session_view()` 每条消息带 `index`（分支定位用）。

- **技能搜索加 GitHub 兜底**：`skills.sh` 的目录只收录「有人 `npx skills add` 装过」
  的仓库（官方 FAQ：leaderboard 来自安装 telemetry），刚发布的 skill 搜不到
  （用户实测搜 `minibt` 搜不到自己的 `minibt-strategy` ✗）。`search_skills()` 现在
  在 skills.sh 失败 / 空 / 没命中关键词时，改用 GitHub 搜索
  （`/search/repositories` + 逐个确认根目录有 `SKILL.md`）→ 直接给出可安装的
  `owner/repo`；结果缓存 10 分钟、支持 `MINIBT_GITHUB_TOKEN`（未登录 60 次/小时）；证书校验失败（公司代理 / 缺根证书）自动降级重试一次（`MINIBT_GITHUB_INSECURE=0` 可关）；限频 120 秒熔断，直接输 `owner/repo` 时**不探测、不打接口**。
- **`desk_pi{send}` / `{regen}` 返回起始事件序号 `seq`**：扩展从这里开始拉增量
  （以前每轮都从 0 拉环形缓冲 → 把**上一轮**的 user / delta / tool 重放一遍，
  用户截图：一句话出现两次、回答夹在中间 ✗）。
- **PI 面板细节修正（VS Code 侧）**：头部用量条 / 停止右对齐；「回到底部」改紧凑
  悬浮胶囊（让开圆点导航）；附件 ✕ 能真删；会话没存模型时用 desk 当前激活模型；
  模型菜单按供应商分组 + 「未配置 Key」提示 + 不透明背景；压缩默认值与 desk 对齐
  （`options.compress === true`）并以 `set_options` 返回值回填；删掉会话栏的
  「模型 / 技能」按钮（设置与安装只在 desk）。

- **VS Code PI 面板连带崩溃的修复**：删「模型 / 技能」入口后，`pi-view.js` 里残留
  `if (skillsOpen) renderSkills();` → 每次渲染 `ReferenceError`，圆点导航 / 用量条 /
  输入区（附件 · chips · 发送）全不显示、附件发不出去；已删除并补 webview 启动自检用例。

### 启动 / 登录

- **VS Code 里点「打开看盘终端」→ `进程退出（code=1）`**（用户实测）：
  天勤认证失败会 `sys.exit(1)`（`SystemExit`），而 `build_desk()` 的期货 / 股票
  登录只 `except Exception` → SystemExit 逃出去，**整个 desk 进程退出**，
  面板一直"没有就绪" ✗。改成 `except BaseException`（`KeyboardInterrupt` 除外）：
  记一条「期货连接失败：…（密码错误 / 账号在别处登录 / 网络…）」后
  **回退离线模式继续启动**，界面照常打开、可在登录框重试 ✓。
- `Desk._connect_futures` 的登录线程同样兜住 `BaseException` → 界面显示
  「天勤登录失败：…」，不再卡在"正在连接"✗。
- 用例：`tests/test_vscode_desk.py::test_build_desk_survives_tqsdk_sys_exit`
  （打桩 `tq_auth` 抛 `SystemExit` → 不抛、`futures_ok=False`、日志含
  「期货连接失败」+「离线模式」）。

### 指标与框架

- **`import minibt` 崩溃（阻断级）**：`minibt/indicators/tulip.py` 与
  `pine.py` 在 `@tobtind(... line_dash=LineDash.vbar)` 里用了 `LineStyle` /
  `LineDash`，但只 `import TYPE_CHECKING` → `NameError: name 'LineStyle' is
  not defined`；`talib.py` 缺 `np`、`pair.py` 缺 `np` / `pd`。全部补齐，
  `import minibt` 恢复正常 ✓。
- **导出 `RollingVolumeProfile`**（`minibt/__init__.py` + `__all__`）：
  用户脚本 `class X(RollingVolumeProfile)` 以前 `NameError` 被 desk 静默跳过。
- **`NON_KLINE_INDICATORS`（TuLip）补 13 个纯数学算子**：
  `asin/atan/cos/cosh/lag/ln/log10/max/min/sin/sinh/tan/tanh`（和已有的
  `abs/exp/sqrt` 同类，不是可画的 K 线指标）→ 有效指标 86 → 73。

### desk：指标目录

- **缓存戳加源码指纹**：`_modules_fingerprint()`（`minibt/indicators/*.py`
  + `indicator_catalog.py` 的 mtime / 大小 → sha1 前 12 位）拼进
  `schema_stamp()`，`CATALOG_SCHEMA` **7 → 8**。同版本号里追加指标也会重建
  缓存（用户实测「内置指标少了很多」的根因 ✗）。
- **`missing_indicators()`**：以 `minibt.<库>` 里带 `@tobtind` 的方法为准、
  减去各库 `NON_KLINE_INDICATORS`，逐库返回差集；`Desk.audit_indicators()`
  在启动时写运行日志。
- **选择器二级筛选不再静默藏指标**：chip 带计数、提示被筛掉多少、
  新增「显示全部」按钮（抽 `_sectionRows()` / `_visibleRows()`）。
- **`imported_indicator_entries()` 排除框架导出类**：`from minibt import *`
  的文件不再被误判成一堆指标（同一性判断 `getattr(minibt, name) is obj`）。

### desk：右键菜单 / 预警 / 编辑器

- **原生右键菜单禁用范围扩到浮层**：`.pylc-ip-mask`（指标、衡量标准和策略）、
  `.pylc-tp-mask`、`.pylc-al-mask`、`.pylc-ss-mask`、`.desk-menu`；
  输入框 / 编辑器保留（复制粘贴要用 ✓）。
- **预警记住 `page` / `cell` / `account`**：本地图表 = `local`（本地模拟），
  实时图表 = 该页 / 该格当前账户（`kq` / `futu` / `real`）；`_alert_view()`
  带 `account_label`，创建 toast 写明「触发按 X 下单」。
- **`alert_fired` 带账户 + `Trading.account_scope()`**：前端按
  `account === 'local'` 走 `local_order`，否则 `place_order` 带 `account` →
  后端把下单目标钉在该账户上（切页不再串账户 ✗）。
- **本地图表预警触发动作真的执行**：按 `buy` / `sell` / `close` 走
  `local_order`，平仓按持仓方向；价格改取 `LocalSim.prices`
  （本地数据文件没有行情源，以前永远不触发）；`app.ts` 不再把实时页预警
  灌进本地图表。
- **编辑器工具栏「符号」→「预览」**（功能不变：跨文件符号搜索）。

### desk：编辑器（v1.3.7）

- **分屏**：工具栏「分屏」/ `Ctrl+\`，左右各一个文件（同一文件不会重复挂）。
- **未保存保护**：关标签确认；关 desk 由 `beforeunload`（浏览器壳）与
  `DeskWindow` 的 `QEvent.Type.Close` 过滤器 + `QMessageBox`（桌面端）兜底，
  后端用 `editor_dirty` 记住未保存清单；**切页面不提醒** ✓。
- **断点调试**：`minibt/desk/debugger.py` + `debug_worker.py`（`sys.settrace`
  子进程 + JSON 行协议）：断点 / 继续 / 单步 / 步入 / 步出 / 停止 + 表达式求值，
  `debug_state` 补丁带调用栈与局部变量。
- **终端**：`minibt/desk/terminal.py`（shell 子进程 + 流式输出 + 行输入，
  `terminal_open/input/signal/restart/close/system` 命令）；「AI 对话」
  按钮执行设置里的 `terminal_ai_command`（默认 `pi`）✓。
  **`minibt/desk/ai.py` 与 `ai_chat` 命令已删除**（用户要求：AI 对话
  改在终端里进行）。
- **Python REPL**：`minibt/desk/repl.py`（常驻子进程，自动 `from minibt import *`，
  打印最后一个表达式，20 秒超时重启，traceback 过滤内部帧）。
- **片段库 / 重命名 / 引用 / 对比 / 选区格式化 / 字号 / 补全**
  （`editor-snippets.ts` + `editor-bundle.ts` + `editor-panel.ts`）：
  12 个片段、LSP 重命名与引用、Git HEAD 对比（`_git_head_text`）、
  dedent→ruff→reindent 的选区格式化、字号 = 设置 × 界面缩放、
  两级前缀（`kline.pta.`）指标函数补全。
- **新增测试** `tests/test_minibt_desk_editor_tools.py`（17 个用例）：
  片段清单、分屏 / 未保存（含「切页面不提醒」断言）、断点调试端到端
  （暂停 / 求值 / 报错）、AI 提示词与无密钥错误、REPL 命名空间与 traceback、
  选区格式化、Git HEAD 读取接口。

- **测试环境**：`tests/conftest.py` 新增 session 级 fixture，把 desk 的
  `personal.CONFIG_FILE` / `PERSONAL_ROOT` / `local_data.STATE_FILE` /
  `user_prefs.PREFS_FILE` 指到 tmp —— 测试不再 `exec` 用户真实的
  `~/.minibt/personal/indicators/*.py`（那些脚本的临时文件操作会把
  pytest 的 capture 文件关掉，导致后续用例
  `ValueError: I/O operation on closed file` ✗）。

- **调试 / REPL / 对比入口三处体验问题（2026-11-08 用户反馈 ✓）**：
  - 断点调试：加「输出」区（启动 / 用户脚本 print / 报错都在这里）、
    没有断点时明确提示「会直接跑完」、**文件有未保存改动时拒绝调试**
    （否则断点行号会和磁盘版本错位 ✗）、Windows 断点路径统一小写；
  - REPL：首次执行先回一句「正在启动解释器，首次约 1~3 秒…」，
    执行放**后台线程**（不卡行情 / 界面）；
  - 「对比 ▾」以前只在**有未保存改动**时才显示 → 现在**有文件就显示**。
### desk：编辑器第三轮（v1.3.7-3）

- **断点红点回归修复**：路径小写只用于断点表 key，查 tab 仍用原始路径。
- **终端对齐 VS Code**：ANSI 16 色渲染、切换 Shell（cmd / PowerShell / bash）、
  跟随输出（往上翻暂停）、500 行缓冲、历史 ↑↓、清屏 / 中断 / 重开 / 系统终端。
- **删除「对比」功能**（用户：没什么用处）：前端 MergeView + 后端
  `editor_diff` / `_git_head_text` 全部移除。
- **AI 助手 = pi-web 桥**（`minibt/desk/ai.py` 重写）：启动 pi-web（终端里跑
  配置的命令 + `/` 就绪探测）、`POST /api/agent/new` / `/api/agent/<id>`
  注入 prompt、`?session=<id>&sidebar=collapsed` iframe 只显示对话窗口；
  命令 `ai_open` / `ai_prompt` / `ai_context` / `ai_service_start|stop|status`
  （全部后台线程）。设置项 `ai_service_url` / `ai_service_command` /
  `ai_service_cwd`；旧 `ai_chat` + `ai_api_key` 已删除。
- **前提体检**：`ai.node_info()` 查 `node`/`npx` + 版本（≥22.19）；
  `_ai_ensure_service()` 在启动前先判，没装 Node 就给「装 Node + 网址」的
  可执行提示（不再等 30 秒报「没就绪」）。
- **新增测试** `tests/test_minibt_desk_ai_piweb.py`（11 个用例，用**假 pi-web**
  验证协议：probe / 新会话 / 续会话 / 上下文拼装 / URL 深链 / 前端入口）。

### desk：AI 助手（v1.3.7-4，零 npm）

- **移除 pi-web 桥**：`minibt/desk/ai.py`、`ai_service_*` 设置、网页页签 iframe
  全部删除 → **AI 功能不再需要 Node / npm** ✓
- **内置 AI 助手**：`minibt/desk/agent.py`（会话存储 + OpenAI 兼容流式 +
  工具循环）+ `jslib/src/desk/ai-page.ts`（会话列表 + 多开对话标签）。
  - 会话存 `~/.minibt/ai/sessions/*.json`（标题 / cwd / 消息，最多 400 条）；
  - 工具：`list_dir` / `read_file` / `grep` / `write_file` / `run_command`，
    沙箱在会话工作区内（越界拒绝、写 ≤200KB、命令 ≤25s）；
  - 命令：`ai_sessions` / `ai_new_session` / `ai_history` / `ai_send` /
    `ai_stop` / `ai_rename` / `ai_delete` / `ai_context` / `ai_status` /
    `ai_insert_code` / `log_tail`；
  - 设置：`ai_base_url` / `ai_model` / `ai_api_key` / `ai_tools` / `ai_max_turns`；
  - 前端：左栏会话（搜索 / 右键重命名删除）、顶部多开标签、流式消息、
    工具调用块、代码块一键插入编辑器、Ctrl+N / Ctrl+Enter。
- **新增测试** `tests/test_minibt_desk_ai_agent.py`（12 个用例，用**假 OpenAI**
  验证：会话 CRUD / 标题自动生成 / 工具沙箱 / 流式 + 工具循环 / 无 Key 提示 /
  取消 / 上下文注入 / 前端入口 + 「零 npm」断言）。

### desk：AI 助手（v1.3.7-5，成本 + 分支）

- **成本 / 上下文用量**：`agent.cost_of()` / `estimate_tokens()` /
  `messages_tokens()` / `MODEL_PRICES` / `MODEL_WINDOWS`；
  `chat_once()` 带 `stream_options.include_usage`（服务不认就自动重试），
  `AgentRun.track_usage()` 累计每个会话的 prompt/completion/total/cost/calls，
  并推 `ai_event:usage`（含 `context` / `window` / `percent`）。
  设置新增 `ai_price_in` / `ai_price_out` / `ai_context_window`（留空用内置表）。
- **会话分支**：`agent.branch_session(id, upto)` + `ai_branch` 命令；
  复制到指定消息、丢弃悬空 tool 消息、不继承 usage；前端消息右键
  「从这里分支（新会话）」/「复制这条」。
- **新增用例**（`tests/test_minibt_desk_ai_agent.py` 扩到 17 个）：
  usage 解析与累计、成本 / token 估算、分支截断与悬空 tool 清理、
  `ai_branch` 命令、前端用量与分支菜单断言。

### desk：紧急修复（v1.3.7-6）

- **资源管理器卡在「正在读取目录…」**：`app.ts` 的 `switch` 里编辑器/资源管理器
  的 `case` 标签被 AI 分支吞掉（`explorer` / `editor_file` / `debug_state` …
  全落进 `ai_sessions` 分支被丢弃）。现已重新挂回，并加源码级回归测试
  `test_app_switch_routes_each_patch_to_its_own_branch`（13 个标签齐全 +
  AI 分支不含编辑器标签 + 每个 case 只出现一次）。

### desk：AI 设置（v1.3.7-7）

- **输入被冲掉**：`SettingsPage.setValues()` 在用户正编辑输入框时**不重画**
  （`pendingRepaint` + `repaint()`），输入框提交打 `data-dirty`；避免「写完不显示」。
- **独立分区**：设置左侧新增「AI 助手」（`_renderAi`），UI 上不再埋进「个性化」。
- **`ai_ping` 测试连接**：`agent.ping()` 发一次 `max_tokens: 1` 请求，
  返回 `{ok, model, ms, error}`；前端 `setPing()` 把结果写在设置页 + toast。
- 新增 4 个用例（分区 / 不重画 / 保存生效 + ping 成功 / ping 失败）。

### desk：AI 设置不丢（v1.3.7-8）

- 前端 AI 设置**输入即写 `localStorage('desk.ai.*')`**，渲染时
  `后端值 || 本地缓存`；`_textInput(..., storeKey)` 支持该兜底。
- `app.ts::send()` 对 `ai_*` 命令自动附 `config: _aiOverride()`
  （settingsValues + localStorage）。
- 后端 `_ai_config(payload)` 支持 `payload.config` 覆盖（空值不覆盖），
  `ai_send` / `ai_regenerate` / `ai_ping` 全部传 payload。
- 新增 4 个用例（含「完全不落盘、只靠 payload.config 跑通一次对话」）。

### desk：PI 助手（v1.3.7-9，零 npm）

- 新模块 `minibt/desk/pi.py`：会话（含**导入 `~/.pi/agent/sessions/**.jsonl`**）、
  `models.json`（供应商 + Key + 模型 + 当前选择）、技能（`SKILL.md` 扫描 /
  启用开关 / **HTTP 搜 skills.sh + `git clone` 安装** / 本地目录安装 / 删除）。
- 命令：`pi_sessions|pi_new_session|pi_history|pi_send|pi_stop|pi_rename|
  pi_delete|pi_import|pi_models|pi_models_save|pi_skills|pi_skills_search|
  pi_skills_install|pi_skills_toggle|pi_skills_remove`。
- `agent.py` 扩展：会话级 `effort` / `permission`（工具白名单）/ `compress`
  （模型摘要压缩）/ `skillsPrompt` + system 提示；`event_type` 支持 `pi_event`；
  `save_session` 加锁 + 重试；`AgentRun.run` 异常也推 error。
- 前端：`pi-panel.ts`（会话列表）/ `pi-chat.ts`（对话页）/ `pi-models.ts` /
  `pi-skills.ts` / `pi-util.ts`；`editor-panel` 增加 PI 按钮（在「打开」左边）、
  左栏切换、`pi:<id>` 会话标签；删除 `ai-page.ts` 与设置页 AI 分区。
- 新增测试 `tests/test_minibt_desk_pi.py`（13 个用例）：供应商目录 / models.json
  往返 / 无 Key 不回退 Ollama / 技能安装(本地) + 启用 + 删除 + 越界拒绝 /
  skills.sh 离线降级 / pi JSONL 导入（含 toolCall/toolResult）+ 去重 /
  `pi_send` 流式 + 选项落盘 + 只读模式只给 3 个工具 / 无模型时明确报错。

### desk：PI 细节（v1.3.7-10）

- **PI 按钮激活态改用中性高亮**（不再用主题色），并删除误伤「保存」按钮的
  通用 `.desk-editor-btn.on` 主题色覆盖。
- **模型对话框兜底**：前端内置 `PI_PROVIDERS`（12 个供应商）+ 缓存最近一次
  `pi_models` / `pi_skills` 补丁 + 1.5s 超时提示「后端没有响应」；
  新增后端 `pi_status`（版本 / 命令清单 / 会话与模型文件路径）。
- **新建会话**：1.5s 没回包给提示；`piOnPatch` 加 try/catch（异常弹 toast）。
- 新增用例：`pi_status`、供应商兜底 + `setOffline` + 缓存、按钮配色断言。

### desk：模型保存（v1.3.7-11）

- 前端 `pi-models.ts` 新增 `readFields()`：保存 Key / 断开连接 / 保存前先把
  输入框的值写回 `data`（不再用渲染快照覆盖，修复「只有 apiKey 存上」✗）；
  勾选「设为当前」时模型名从当前输入取。
- 后端 `pi.provider_catalog()`：有保存值就只用保存值，不再拼内置模型列表。
- 新增 2 个用例（保存往返 + 前端 readFields 断言）。

### desk：模型选择（v1.3.7-12）

- `_pi_models_data()` 的 `active` 改为**已解析**（provider / model / base / keySet）。
- `pi.model_config()`：所选模型不在供应商列表内 → 退回第一个。
- 模型对话框：新增「对话将使用：<model>」、「测试连接」（走 `ai_ping`）、
  `/anthropic` 端点提示；`EditorPanel.piPingResult()` 把结果送回对话框。
- 新增 3 个用例。

### desk：会话列表（v1.3.7-13）

- 会话项改成 pi-agent-web 样式：标题行 + 悬浮按钮（当前会话 2 个：
  重命名 / 删除；其它会话 3 个：合并摘要 / 重命名 / 删除），CSS 默认隐藏、
  `:hover` 才显示；图标用 `ICON_MERGE` / `ICON_PENCIL` / `ICON_TRASH`。
- 新命令 `pi_merge`：`pi.merge_into()` 生成会话摘要（标题 / 时间 / 条数 +
  最近 12 条），追加成一条 `user` 消息到当前会话，源会话不动。
- 右键菜单保留并新增「合并摘要到当前会话」。
- 新增 3 个用例。

### desk：会话目录切换 / 分屏（v1.3.7-14）

- 新增 `Desk._apply_explorer_root(path)`：统一设置根目录 + 记
  `settings.explorer_recent`（最多 10 条，去重）+ 推
  `explorer` / `pi_sessions`(dir/default/recent) / `explorer_root` 三个补丁；
  `explorer_pick` / `explorer_system_dir` / `explorer_set_root` 全部改走它。
- `pi-panel.ts`：目录按钮 + 下拉菜单（默认目录 / 最近打开 / 选择文件夹）；
  会话按 `cwd` 过滤当前目录；`setDefaultDir` / `setRecent` / `onDir` / `onPickDir`。
- `editor-panel.ts`：新增 `paneSession[0/1]`、`_paneHost()`、`_targetPane()`；
  会话可在右栏打开（先分屏再点会话）、关分屏搬回左栏、关标签清理归属。
- 新增 5 个用例：切目录三个补丁 + dir/最近去重上限 + 不存在目录不动 +
  前端目录菜单/过滤断言 + 会话分屏结构断言。

### desk：PI 乱码 / 完全访问（v1.3.7-15）

- `agent.decode_bytes()`（UTF-8 → GBK → GB18030 → latin-1）+ `read_text_smart()`；
  `run_command` 改二进制捕获 + `stdin=DEVNULL` + `PYTHONIOENCODING=utf-8`；
  `read_file` / `grep` / `read_refs` 全部智能解码；`grep` 跳过
  `__pycache__` 等目录与二进制文件（`SKIP_DIRS`）。
- `terminal.py` 改二进制读 + 智能解码（cmd 的 GBK 中文不再花屏）。
- 权限默认 **`full`（完全访问，不询问）**：`TOOL_GROUPS['full']` = 全部 5 个工具；
  `pi_new_session` / `pi_send` 都 `setdefault('permission', 'full')`；
  前端 chip 文案「完全访问（不询问）」。
- 新增 6 个用例。

### desk：PI 停止原因可视化（v1.3.7-16）

- `MAX_TURNS` 6 → **12**（`settings.ai_max_turns` 可设 1~24）；到上限、
  `finish_reason=length`、空回复三种情况都会追加一条**可见** assistant 提示，
  不再只推 `done` 导致界面空白 ✗。
- `tool_result` 带 `elapsed`，对话页工具卡标题显示 `· 1.2s`。
- system 提示里写明「可以连续调用多个工具（最多 12 轮）」。
- 新增 4 个用例。

### desk：模型对话框「高级」限制（v1.3.7-17）

- `models.json` 新增 `limits`（`turns` / `timeout` / `output` / `read` / `window`），
  `pi.limits_of()` 带钳制，`model_config()` 合并进 agent 配置。
- `agent.run_tool(..., limits)`：命令超时、输出截断、单文件读取上限按设置走；
  `AgentRun` 把 `config` 里的限制传给每次工具调用。
- 前端 `pi-models.ts` 底部「高级」条（4 个下拉）+ CSS；
  `pi_models` 补丁带 `limits`，保存后立即生效。
- 新增 4 个用例。

### desk：混合编码（v1.3.7-18）

- `agent.decode_bytes()` 改为**按行解码** + `_decode_one()` 多候选
  （UTF-8 / GBK / GB18030 / Big5）+ 「GBK→UTF-8」二次解码修复，
  用典型乱码字符打分挑最优 → 同一条命令里 UTF-8 与 GBK 混排也能各解各的。
- `run_command` / `read_file` / `grep` / `@文件` / 终端面板全部受益。
- 新增 3 个用例（混合字节 / 乱码修复 / 混合脚本输出）。

### desk：PI 未安装检测（v1.3.7-19）

- `pi.install_status()`：`which('pi')` + `pi --version`（10s、`stdin=DEVNULL`），
  30 秒缓存，返回 `{installed, command, version, hint}`。
- `pi_status` 带 `installed` / `piCommand` / `piVersion` / `hint`。
- 编辑器 PI 按钮未安装时 `disabled` + 安装提示 tooltip；
  首次显示即查 `pi_status`；点击被拦下并 toast。
- `_apply_explorer_root()` 未安装时不再同步 `pi_sessions`。
- 新增 6 个用例。

### desk：PI 对话页（v1.3.7-20）

- 思考：`_post_stream` 收 `reasoning_content`/`reasoning`/`thinking` → `thinking` 事件；
  会话里保存 `thinking`，`api_messages()` 发送前剥离（不算上下文）。
- 每轮用量 `usage_of()`（含 cached：OpenAI/DeepSeek/Anthropic 三种写法），
  `track_usage()` 返回单轮并推 `round`；tool 消息保存 `args`/`elapsed`。
- `_ai_session_payload` 保留 tool 行 + `thinking`/`usage`/`model`/`seconds`
  （修「重开会话只剩一排 deepseek-flash」）。
- 前端 `pi-chat.ts` 重写：思考/工具折叠卡、每轮用量 + 复制、代码块复制、
  右侧节点导航（点击跳转 + 滚动高亮）、右键粘贴、流式 token/t-s 徽章、
  回到底部按钮、markdown 列表修复。
- 新增 5 个用例。

### desk：PI 对话页三处细节（v1.3.7-21）

- 代码块底色：`pre code` 重置为透明（行内 `code` 的底色不再串到代码块）。
- 结论下方始终有「复制」按钮（`desk-pi-copy-answer`），不再依赖 usage 是否存在。
- 右键粘贴改走后端：`pi_paste` 命令（`QApplication.clipboard()` → tkinter 兜底），
  前端 `applyPaste()` 插到右键时的光标处。
- 新增 4 个用例。

### desk：终端 / REPL（v1.3.7-22）

- `repl.py`：`from minibt import *` 的名字逐个搬进 `exec` 的 namespace
  （另加 `np`/`pd`）；启动横幅 `@@banner@@`/`@@ready@@` 不混进命令输出。
- 终端 / REPL 面板可拖动高度（顶部 5px 拖拽条，默认 220px，上限 75vh）。
- 删除「AI 对话」按钮；关闭「×」移到最右。
- 终端提示符跟随 `cd`（显示当前目录最后一段，title 为完整路径）。
- 新增 4 个用例。

### desk：终端合并 + 发给 AI（v1.3.7-23）

- 工具栏「终端」「REPL」合成一个按钮：打开上次用的页签，右键可选页签。
- 「发给 AI」改为二级菜单：选中代码 / 整个文件 / 文件地址 → 选会话 → 插入输入框；
  编辑器右键、资源管理器右键（文件地址 / 全部代码）同样支持。
- 会话目标含「＋ 新建会话」；未打开的文件先 `editor_open` 读回来再发；
  PI 页签在前台时退回上一个打开的文件。
- `PiChat.appendToInput()` 追加并聚焦，状态栏提示「按 Enter 发送」。
- 新增 3 个用例。

### desk：PI 操控 desk（v1.3.7-24，MCP 方案 M1）

- 新增 `minibt/desk/tools.py`：`SPECS`（9 个 `desk_*` 工具）+ `call()` 白名单分发 +
  `audit()` 审计（参数脱敏）。
- `agent.TOOLS` 合并这些定义；`TOOL_GROUPS` 新增 `desk` 档（`default` 不含）；
  `run_tool(..., desk=…)` 路由，`AgentRun` 传 desk 句柄与会话 id。
- 前端权限 chip 多一档「操控 desk（会点按钮）」。
- 新增 `tests/test_minibt_desk_tools.py`（13 个用例）。
- 方案文档：`13.29_pi_mcp_desk_control.md`（已加 mkdocs 目录，标注 M1 完成）。

### desk：PI 操控 desk（v1.3.7-25，MCP 方案 M2）

- 新增 8 个 `desk_*` 工具：`desk_open_page` / `desk_backtest_run` /
  `desk_optimize_run` / `desk_strategy_status` / `desk_positions` / `desk_orders` /
  `desk_order` / `desk_strategy_live`（共 17 个）。
- `confirm` 闸门：`desk_order` 与 `desk_strategy_live(start)` 缺 `confirm` 不执行，
  返回 `need_confirm` + 中文说明（模型反问用户），并写审计。
- 下单只允许限价单（`price > 0`），`local=true` 走本地模拟；
  回测/优化通过 `queue_ui` + `_on_strategy_start` 触发。
- 新增 7 个用例（共 20 个）；方案文档 13.29 标注 M2 完成。

### desk：PI 操控 desk（v1.3.7-26，MCP 方案 M3）

- 设置键 `ai_desk_allow`（默认开）/ `ai_desk_order`（默认关），已加入
  `user_prefs.SETTING_KEYS`；`tools.flags()` 读取并做闸门
  （只读工具与「停止策略实盘」不受总开关限制）。
- 审计：`tools.recent_audit()` / `clear_audit()`；命令
  `ai_desk_settings` / `ai_desk_save` / `ai_audit` / `ai_audit_clear`；
  设置页「PI 操控 desk」区块（两个开关 + 查看/清空 + 日志区）。
- 新增 6 个用例（共 26 个）。

### desk：MCP 服务端（v1.3.7-27，MCP 方案 M4）

- 新增 `minibt/desk/mcp.py`：stdio JSON-RPC 2.0（initialize / ping /
  tools/list / tools/call），工具表复用 `tools.SPECS`，执行复用 `tools.call`。
- CLI：`--config`（写 `~/.minibt/ai/mcp.json`，合并已有 server）、
  `--embedded`（离屏 desk）、`--list`（打印工具表）。
- 新增 `tests/test_minibt_desk_mcp.py`（10 个用例）。
- 方案文档 13.29 标注 M4 完成，M5（反向 MCP / 运行中实例桥接）为下一步。

### desk：本机桥 + 反向 MCP（v1.3.7-28，MCP 方案 M5）

- `bridge.py`：127.0.0.1 + 一次性 token 的 HTTP 桥（`/health` `/tools` `/call`），
  信息写 `~/.minibt/ai/bridge.json`；Desk 启动自动开、退出关闭；
  `mcp.py` 默认优先转发到运行中的 desk。
- `mcp_client.py`：读 `mcp.json` 的外部 server（懒启动 + 60s 缓存），
  注册成 `mcp__<server>__<tool>`，`run_tool` 路由；`ai_mcp_tools` 可关。
- 设置页新增「MCP 本机桥」「接入外部 MCP 工具」两个开关。
- 新增 7 个用例（共 17 个）+ `tests/fake_mcp_server.py`。

### desk：反馈批量修复（v1.3.7-29）

- 复制走 `clipboard_set`（后端系统剪贴板）。
- `desk_add_indicator` / `desk_remove_indicator` / `desk_clear_indicators` 支持 `page`，
  默认用当前活动本地页；新增 `desk_local_pages`、`desk_clear_indicators`、
  `desk_clear_drawings`（工具共 20 个）。
- `Bt._load_strategies` 直接读源码 exec，修「改了策略还是跑旧代码」。
- `PiChat.scrollToBottom()` + 切页调用；PI / 终端 / REPL 输入框支持 ↑↓ 历史。
- 新增 `local_switch`（本地图表 CSV → CSV），前端本地图表改用它。
- `pi_send` 执行中排队 + `queued` 提示，`AgentRun` 结束自动放行。
- 新增 9 个用例。

### desk：命令矩阵 + 3 处反馈（v1.3.7-30）

- 新增 `scripts/desk_tool_matrix.py` + 文档 `13.30_desk_command_tool_matrix.md`
  （243 条命令 × 20 个工具的覆盖表）；`tests/test_minibt_desk_tool_matrix.py`
  强制文档与代码同步。
- 本地图表 / 实时图表工具栏新增「更多指标」按钮。
- PI 输入框多行也强制 ↑↓ 翻历史。
- 执行中插话改为**追加到本轮**（`AgentRun.append_user` / `_drain_pending`），
  不再 stop+重启；失败才退回排队。

### desk：A 批工具（v1.3.7-31）

- 新增 12 个工具：`desk_set_cycle` / `desk_open_chart` / `desk_close_chart` /
  `desk_replay` / `desk_indicator_picker` / `desk_templates` /
  `desk_apply_template` / `desk_save_template` / `desk_layouts` /
  `desk_layout_apply` / `desk_editor_add_indicator` / `desk_book_watch`（共 32 个）。
- 对照表重新生成：已覆盖 25 条命令；新增 5 个用例。

### desk：B 批工具（v1.3.7-32）

- 新增 13 个工具：`desk_editor_open` / `desk_editor_save` / `desk_editor_new` /
  `desk_editor_delete` / `desk_editor_check` / `desk_explorer_set_root` /
  `desk_explorer_system_dir` / `desk_explorer_op` / `desk_strategy_manage` /
  `desk_strategy_switch` / `desk_strategy_remove` / `desk_repl_eval` /
  `desk_terminal_run`（共 45 个）。
- 保存 / 删除 / 新建 / 资源管理器新建都**回读校验**（不再假成功）。
- 对照表重新生成（覆盖 35 条命令）；新增 6 个用例。

### desk：C 批工具（v1.3.7-33）

- 新增 13 个工具：布局保存/删除/收藏、`tv_list`/`detail`/`source`/`star`/`live`/
  `script`/`reload`、`desk_replay_trade`、`desk_screenshot`（共 57 个）。
- 截图：工具 → `ui_action{screenshot}` → 前端页截图 → 后端落盘 → 工具返回路径（带超时）。
- `_json()` 改为合法截断（不再把 JSON 截成半截）；`file:` 策略源码直接读文件。
- 对照表重新生成（覆盖 43 条命令）；新增 5 个用例。

### desk：D 批工具（v1.3.7-34）

- 新增 12 个工具：`desk_login_futures` / `desk_login_stock` / `desk_account_kind` /
  `desk_close_charts` / `desk_theme` / `desk_position_action` / `desk_order_action` /
  `desk_ticket_order` / `desk_alerts` / `desk_add_alert` / `desk_drop_alert` /
  `desk_layouts_export`（共 69 个）。
- 交易类（平仓 / 撤单 / 买卖盘下单）进 `DANGEROUS`，必须 `confirm`；
  登录缺凭证返回 `need_user_input`（模型反问用户）。
- 对照表重新生成（覆盖 54 条命令）；新增 5 个用例。

### desk：E 批工具（v1.3.7-35）

- 新增 `desk_close_tabs`（页面 / 编辑器页签 / PI 会话，全部或指定）与
  `desk_open_ui`（日志 / 设置 / 命令面板 / 首页 / 报价 / 工作台 / 研究 / 登录）；
  `desk_open_page` 的 kind 扩展 home/quote/settings/logs/palette（共 71 个工具）。
- 前端：`ui_action` 新增 `close_tabs` / `open_ui`；`EditorPanel.closeTabs()`。
- `desk_open_page` 非法 kind 改为 JSON 错误；新增 3 个用例。

### desk：F 批工具（v1.3.7-36）

- 新增 15 个工具：数据平台（list / query / preview / quality）、
  运维（tokens / token_issue / tasks / task_run / task_toggle）、
  研究（list / start / cancel）、工作台（snapshot / limits）（共 85 个）。
- 这些走模块 API（同步返回数据），对照表加 `MANUAL_COVERS` 正确标注覆盖。
- 新增 3 个用例；对照表：85 个工具 / 覆盖 72 条命令。

### desk：文档（v1.3.7-37）

- 新增使用手册 `manual/13.29_pi_mcp_usage.md`（MCP 介绍 / 三种用法 / 权限 / 速查 / 排错）。
- 方案稿移到 `minibt_desk/13.29_pi_mcp_desk_control.md`，mkdocs 两条目录分别指向。
- 测试：`test_docs_have_plan_and_usage` 校验文档位置与关键内容。

### desk：PI 独立界面（v1.3.7-38）

- 新增 `PiPage`（编辑器 `variant:'pi'`）+ `PiWelcome` 初始化页：
  首页「预警中心」下面 / 顶栏「＋ → PI 助手」两个入口（去掉「零 npm 依赖」字样）。
- 隐藏 8 个桌面专属按钮与右键「加到图表」（只隐藏，功能保留）；左栏固定 PI 会话；
  初始化页不是页签，发送即新建会话；新会话先显示初始化样式；关完页签回到初始化页。
- `app.ts` 补丁路由改用 `_editorPanels()`（覆盖 PI 独立界面）。
- 新增 `tests/test_minibt_desk_pi_page.py`（7 个用例）；手册 13.29 补一节。

### desk：PI 独立界面增强（v1.3.7-39）

- 初始化页「最近会话」（5 条，置顶带 📌，点一下打开）。
- 新设置键 `pi_root`（PI 页独立目录）/ `pi_pins`（置顶）；命令 `pi_pin`；
  目录类命令带 `pi:true` 时只改 PI 的根。
- 侧栏会话置顶（☆/★ + 右键），后端置顶优先排序。
- 初始化页发送带 `title`（首句 40 字）→ 新会话立刻有名字。
- 拖入文本可用；拖文件 / 粘图片给出明确提示（WebEngine 拿不到路径）。
- 新增 5 个用例（共 12 个）；对照表 244 条命令。

### desk：AI 悬浮对话窗（v1.3.7-40）

- 新增 `pi-float.ts`：紧凑对话（发到会话，非一次性问答）+ 输入框/发送/模型 chip，
  底部「执行中才出现」的不定进度条。
- 贴主窗口四边 <28px 自动收起成小圆标，点图标恢复；位置/收起边持久化。
- 激活条件：pi 已安装 + 模型已配置；入口＝＋菜单「AI 悬浮窗」+ `Ctrl/⌘+Alt+A`。
- 修：`app.ts` 漏路由 `pi_status`（PI 按钮未安装禁用此前未生效）。
- 新增 6 个用例。

### desk：悬浮窗增强（v1.3.7-41）

- `@文件` 联想（`ai_files`）+ 拖文本；标题栏「会话 ▾」切换最近 12 个会话；
  贴边展开后鼠标离开 900ms 自动收起，📍/📌 钉住可关闭（持久化）。
- 修：`app.ts` 漏路由 `ai_files`（PI 会话 / 编辑器的 @文件此前不生效）。
- 新增 3 个用例（共 9 个）。

### desk：浮窗独立窗口 + 会话搜索（v1.3.7-42）

- 新增 `minibt/desk/float_window.py` + `pi_detach_float`：第二个 Qt 置顶窗口，
  加载 `desk.html?pi=float`（前端只渲染悬浮窗），共用同一个 Desk / 桥，补丁广播。
- PiFloat 标题栏新增 ⧉「浮到窗口外」；会话下拉加搜索框（即时过滤）。
- 无 Qt 窗口（浏览器 / 测试）时只提示不崩；退出时关闭浮窗。
- 新增 4 个用例（共 13 个）；对照表 245 条命令。

### desk：PI 页会话 + 本地布局修复（v1.3.7-43）

- 修：PI 独立页的 `onCommand` 覆盖了 `payload.id`（会话 id）→ 会话删不掉 /
  打不开 / 页签变「PI」；现在原样透传 payload。
- `openPiSession()` 新建页签先用 `piRows` 已知标题。
- 新增 `local_layout` 命令 + `desk_set_layout{local,symbols,page}`：
  本地图表按数据集逐格装布局（先推 layout 再逐格 local_load）。
- 新增 4 个用例；对照表 246 条命令。

### desk：MCP 可用性优化（v1.3.7-44）

- 新增 `desk_find_indicator`、`desk_sequence`（一次调用多步，≤6，禁危险工具）；
  `desk_add_indicator` 自动解析别名 + `need_key_choice` 候选 + `next_hint`。
- `desk_replay` 支持本地图表（`ui_action: replay`）；本地加指标/回放自动取当前数据集。
- `desk_status` 增加 `hints` / `local_pages`；`indicator_picker` 描述澄清「不添加」。
- 新增 5 个用例；对照表 87 工具 / 246 命令；手册补 3.6。

### desk：系统提示 + 工具合并（v1.3.7-45）

- `AgentRun.with_system()` 新增「工具选择规则」（先 find / sequence 多步 / 本地带 local /
  picker 不添加 / 先 status），并给一个完整示例。
- 布局 6 个工具合并为 `desk_layouts{action}`（list/apply/save/delete/favorite/export），
  工具总数 87 → 82；对照表 MANUAL_COVERS 同步（覆盖 74 条命令）。
- 新增 3 个用例（共 61 个）。

### desk：工具合并 + sequence 引用（v1.3.7-46）

- tv(7) / datahub(4) / ops(5) 合并为 `desk_tv` / `desk_datahub` / `desk_ops`{action}；
  工具总数 87 → 69，对照表覆盖 78 条命令。
- `desk_sequence` 支持 `$0.resolved` 依赖引用（嵌套 / 列表下标），查→加一步完成。
- 新增 3 个用例（共 64 个）；手册 13.29 更新。

### desk：再合并 5 组 + sequence 提示（v1.3.7-47）

- `desk_local` / `desk_account` / `desk_research` / `desk_book` / `desk_drawings`
  改为 action 单入口，工具总数 69 → 62；对照表覆盖 82 条命令。
- `desk_sequence` 每步回执新增 `hint`（下一步推荐工具）。
- 新增 2 个用例（共 66 个）；手册 13.29 更新。

### docs：changelog v1.3.7 段整理（按主题分组）

- `minibt_docs/docs/changelog.md` 的 `[v1.3.7]` 段重排：导语改写成四段主线，
  新增「阶段地图 / 关键数字 / 升级注意 / 收尾状态」四张表；
  56 轮迭代降为 `####`，按 A~H 八组（崩溃与指标目录 / 编辑器 /
  AI 设置与 PI 对话 / MCP 工具桥 / 文档矩阵 / 独立界面与浮窗 /
  让模型更快选对工具 / 账户·图表·悬浮窗收尾）归位，正文内容未删改；
  「本版收尾状态」提升为同级小节，关键数字同步到最新（1743 passed /
  `desk.js?v=mw9h3gyb`）。
- mkdocs 每页目录（`toc_depth: 3`）仍只列版本 + 分组，不会冗长。

### desk：悬浮窗附件位置 + 窄窗口自适应（v1.3.7-57）

- 悬浮窗 📎 挪到底部模型按钮左边（22×22，同高）；输入行只留输入框 + 发送。
- 根因修：flex 链缺 `min-width: 0` → 页宽 1179px（窗口 1028px）把工具栏右侧 /
  对话导航 / 发送按钮 / 状态栏挤出屏幕。
  `.desk-editor*` / `.desk-pi-*` 全链路收缩；工具栏窄窗口换行；状态栏正文改 span
  省略号；LSP 徽标短标签（完整说明进 tooltip）；初始化页与宿主互斥。
- 实测 1200~760 宽 0 横向溢出，760 宽 17 个工具栏按钮全部可见。
- 新增 `tests/test_minibt_desk_pi_layout_fit.py`（6 项）；全量 1763 passed。

### desk：行情数据工具 + 图表缩放 + 预警条件（v1.3.7-58）

- 新增 `desk_market`（klines / indicator / summary / quote）：直接给模型
  OHLCV 数字、指标序列、报价 + 统计，不再靠截图做像素解析；本地 CSV 用
  `local:true`。
- 新增 `desk_bars{action:"all"|"last", count}`：等价图表右键「全部K线 /
  最新K线（300 根）」（视图缩放，走前端回执 `bars`）。
- `desk_drawings` 加 `action:"toolbox"`：等价右键「画线」（左侧工具箱开关）。
- 预警标签改成「预警 上穿 12680」（带穿过 / 上穿 / 下穿）。
- 系统提示新增第 9、10 条（数据优先、别改 `chart_data_length`）。
- 工具 62 → 64；新增 `tests/test_minibt_desk_market_tools.py`（15 项）。

### desk：分析工具 P0/P1/P2 + 终端条 + PI 首页（v1.3.7-59）

- `desk_market` 新增 levels（前高低 / 斐波那契 / POC-VAH-VAL）、stats（ATR/RSI/
  分位/趋势）、patterns（K 线形态）、depth（五档压力）、digest（紧凑文本）。
- 新增 `desk_scan`（多合约指标筛，≤30 个）与 `desk_strategy_data`
  （回测收益/回撤/逐笔/净值/买卖信号）；三者都是只读工具。
- 终端页签条：清屏…系统终端整组贴右、紧挨 ×（关闭按钮不再抢 auto 边距）。
- PI 首页：关掉全部页签后显示初始化页（含「有页签但未激活」自愈）；
  首页发送改成 `pi_send{id:""}`，后端先建会话（标题=首句）再跑模型，删掉
  兜底定时器（以前会重复建两个会话）。
- 工具 64 → 66；新增用例至 21 项；全量 1784 passed。

### desk：右键入口 + PI 首页 + F1（v1.3.7-60）

- 图表右键（实时 / 本地）补 4 个工具栏入口：更多指标、模板、策略管理、保存当前布局。
- PI 首页：模型 chip 显示真实选中模型（`pi_models.active`）；`pi` 版本改用
  `pi --version`（1.5.1），不再复用 minibt 版本号；最近会话只列 3 个、点击打开。
- AI 悬浮窗快捷键 `Ctrl+Alt+A` → **F1**（微信截图占用了前者）。
- 全量 1788 passed；构建 `desk.js?v=mwa1zcqu`。

### desk：`desk_market{action:"analysis"}` 一次拿全套（v1.3.7-61）

- 新增 analysis：一次取 K 线 → levels + stats + patterns + 紧凑 text（+ 图上指标），
  3 轮往返降到 1 轮，实测 0.087s / 回执约 2.6KB。
- 系统提示推荐先 analysis，再按需下钻；手册 13.29 同步。
- 新增 1 个用例；全量 1789 passed；构建 `desk.js?v=mwa2gogw`。

### desk：资讯 / 财经日历 P0（v1.3.7-62）

- 新增 `minibt/desk/info/`（providers / cache / service）：AkShare 适配
  （限速 + 重试 + 主备接口）、SQLite 缓存（TTL）、缓存优先 + 后台抓取。
- 首页「事件日历」改用真实财经日历（`news_economic_baidu`，按天传 date），
  抓完推 `info_calendar` 局部刷新，取不到回退静态。
- 新页面「资讯中心」：快讯（60s 自动刷新）/ 要闻 / 日历 + 搜索 + 数据源徽标 +
  右键「让 AI 分析这条」；设置页新增「资讯数据源」。
- MCP：`desk_news` / `desk_calendar`（只读）；`pip install "minibt[news]"`
  可选依赖；工具 66 → 68。
- 新增 `tests/test_minibt_desk_info.py`（13 项）；全量 1801 passed。

### desk：资讯 P1（宏观 / 合约资料 / 标的资讯页）（v1.3.7-63）

- 数据层：宏观 6 序列、合约规则、库存、基差（快照缓存 12h/12h/6h/1h，失败只降级一块）。
- 资讯中心加「宏观」「期货」两个 tab；新增**标的资讯页**（图表右键「资讯 / 财务…」，
  顶部 pill 在多布局多个合约间切换）。
- `info_macro` / `info_symbol` 改后台线程（实测同步会卡 3 秒）。
- MCP 新增 `desk_macro` / `desk_fundamentals`（只读），工具 68 → 70。
- 新增 `tests/test_minibt_desk_info_p1.py`（11 项）；全量 1813 passed。

### desk：资讯 P2（富途优先 + 财务/公告 + FTS5 + 事件标记）（v1.3.7-64）

- 新增 `info/futu_source.py`：个股**快照 / PE·PB / 资金流**优先走富途 OpenD
  （复用 desk 已连的 StockApi），没连富途自动降级 AkShare 并在回执里注明。
- 财务摘要（AkShare，缓存 24h）/ 公告（30min）/ 资金流（5min）按接口成本排 TTL；
  东财 `…` / `--` 占位值当空串。
- 资讯缓存加 **FTS5 trigram** 全文搜索（<3 字自动 LIKE）。
- 图表 **K 线事件标记**：财经日历中/高重要性事件按天打点（<0.2 秒，失败不影响行情）。
- 资讯中心「AI 摘要」：当前 15 条交给 PI 总结（先建会话再问）。
- 新增 `tests/test_minibt_desk_info_p2.py`（13 项）；全量 1826 passed。

### desk：用户四条反馈修复（v1.3.7-65）

- 标的资讯页：关掉标签后再打开打不开（closeTab 没清缓存引用）→ 修。
- 设置「资讯数据源」删掉 Tushare 提示。
- 悬浮球：设置里可选背景色（`pi_float_color`，持久化 + 恢复默认），
  小球文字改「π」并放大到 22px。
- K 线事件圆点：改用 LWC v5 的 `createSeriesMarkers`；本地图表 bars 回退；
  历史区间无交集时标在最后一根；日历推给所有图表页。
- 新增 `tests/test_minibt_desk_v137_fixes3.py`（4 项）；全量 1830 passed。

### desk：事件圆点贴顶 / 标的事件 / π 主题色 / 会话去重（v1.3.7-66）

- 图上事件圆点改为**顶部 DOM 徽标**（缩放也贴顶、无文字、tooltip 看内容），
  只画**与标的有关**的事件（股票公告 / 期货品种相关日历），宏观不上图。
- 新增「事件圆点：全部事件都画」开关（`chart_events_all`，默认只中/高重要性）。
- 悬浮球 π 的字色回到主题色（去掉自选底色的深色覆盖）。
- 新增 `agent.cleanup_sessions` + 命令 `pi_cleanup` + 设置按钮「清理重复会话」。
- 补回每格周期链路 / `_isTradeCell` / `local_switch` / 本地预警 `account: 'local'`。
- 全量 1832 passed；构建 `desk.js?v=mwa90lcx`。

### desk：标的资讯页改金融小插件 + 事件卡片 + 多账户策略 + 开图不阻塞（v1.3.7-67）

- 标的资讯页改用 `pylightcharts` 插件：Company Profile（QuoteHeader+TextBlock）/
  Fundamental Data（DataGrid，缺失填 `-`）/ Technical Analysis / Top Stories。
- 后端 `_symbol_widgets()` 一次给全 quote / profile_text / fundamentals /
  technical（`ta_summary`）/ stories。
- 事件圆点按天分组 + 悬停弹出「当日事件」卡片（.desk-cal-pop）。
- 多账户加策略：按图表页账户 key 取实例（`account_key_for` +
  `_fallback_trade_account`），不再报「需要指定账户实例 account」。
- 开图先出 K 线：辅助命令延后（`_deferCommands`）；股票跳过天勤合约校验。
- 新增 `tests/test_minibt_desk_v137_fixes4.py`（8 项）；全量 1840 passed。

### desk：资讯页跟随主题 + 控件 + 关页加固（v1.3.7-68）

- 标的资讯页：`applyTheme()` 别名 + 固定主题调色板（浅色下文字不再发灰）；
  Fundamental Data 数值列加宽 + 报告期下拉；Technical Analysis 周期下拉；
  Top Stories 搜索框（`info_news{query}`）。
- 事件圆点旧 `title` 关闭（只保留悬停卡片）。
- `info_symbol_events` 改后台线程（实测阻塞 4 秒）；切页 / 关页容错，
  图表页关不掉 / 空白页遮挡修复。
- 新增 5 个用例；全量 1845 passed。

### desk：资讯页浅色主题 / 小数 / 表格高度 / Top Stories（v1.3.7-69）

- Fundamental Data：浅色主题补全表头 / 悬停 / 斑马线颜色；按行数撑高度不出滚动条。
- Company Profile：开 / 高 / 低 / 昨收保留 2 位小数；成交量 / 持仓量用整数
  （`QuoteHeader` 新增 `intFields`）。
- Top Stories：资讯缓存为空时就地抓一次（后台等待），公告 + 资讯都显示。
- 新增 2 个用例；全量 1847 passed；构建 `desk.js?v=mwabml3q`。

### desk：资讯多源合并 + 去重 + 关键词 + 宏观加速（v1.3.7-70）

- `fetch_market_news()`：财新 + 同花顺合并去重（去 `【标签】`、补 url、按时间排序）。
- `fetch_symbol_news()`：个股 / 期货 = 专属源 + 全市场关键词匹配（名称、代码、
  品种、`沪X`）+ 新浪快讯；统一去重。
- 标的资讯 / 资讯中心「期货」tab 都接这套（新增「相关资讯」区块）。
- 宏观：先推缓存、仅过期或手动刷新才抓；前端按 key 合并补丁。
- 新增 3 个用例；全量 1849 passed；构建 `desk.js?v=mwacporj`。

### desk：资讯联动 / 自选筛选 / 摘要缓存 / F10（v1.3.7-71）

- 图表页 `focusTime()`：点资讯跳到对应 K 线 + 4 秒高亮徽标；`news_focus` 纯前端。
- `info_related`（自选 + 打开图表 + 持仓的合约与名称）+ 资讯中心「只看自选/持仓」。
- `ai_summary`：按天缓存到 `~/.minibt/ai/summary.json`，同一天命中缓存不重跑；
  Shift 点强制重生成。
- `F10` = 当前图表的标的资讯（右键菜单文案同步）。
- 标的资讯页小插件标题中文化：标的概况 / 基本面数据 / 技术分析 / 最新资讯。
- 新增 `tests/test_minibt_desk_v137_fixes5.py`（5 项）；全量 1855 passed。

### desk：资讯右键菜单 + 标的识别（v1.3.7-72）

- 资讯交互：左键不动作；右键菜单（打开原文 / 打开图表 / 复制 / 让 AI 分析）；
  双击打开原文；NewsFeed 面板支持 onItemContextMenu / onItemDoubleClick。
- 标的识别 `_symbolOf`：自带 symbol → 自选/持仓名称 → 文本里的期货/股票代码；
  认不到时菜单显示「找不到标的」并明确 toast，不再静默。
- `news_focus`：带 symbol 时先 `openChart` 真打开，再等 K 线到位后跳时间 + 高亮。
- 新增 `tests/test_minibt_desk_v137_fixes6.py`（4 项）；全量 1859 passed。

### minibt：信号（signals）+ 技术分析模板（v1.3.7-73）

- 新增 `minibt/signals.py`：`Threshold`（原 Osc）/ `Compare`（原 Trend）/
  `Custom`，1 多 · 0 中立 · -1 空；`minibt.utils` / `minibt` 顶层可导入。
- `@tobtind(signals={...})` 挂到结果上，`IndicatorsBase.signal_of()/signal_map()`；
  目录新增 `has_signal` / `signal_spec`（`CATALOG_SCHEMA 9`），内置信号用
  `BUILTIN_SIGNALS` 注册表覆盖 RSI/CCI/ADX/MACD/MA 等。
- `pylightcharts` 技术分析输出 `groups`（震荡 / 趋势 / 其他），面板渲染信号文案。
- `minibt/desk/ta.py`：`options / template / save_template / reset_template / snapshot`；
  标的资讯页技术分析「⚙ 设置」对话框（勾选指标 + 阈值/比较 + 保存模板/恢复默认）。
- 新增 MCP `desk_ta`（options / snapshot / set / reset），工具 70 → 71。
- 新增 `tests/test_minibt_signals_ta.py`（12 项）；全量 1901 passed。

### desk：信号接通圆点 / 预警 + 多模板 + TA 列对齐（v1.3.7-74 ~ -75）

- `ta_signals`：技术分析信号 → 图表最后一根 K 线旁的徽标（悬停看明细，10s 节流）。
- 信号预警：`kind:"signal"` + `key` + `op`，15s 缓存、触发日志明确；预警对话框
  新增「类型：价格 / 指标信号」；MCP `desk_add_alert` 支持信号。
- 多命名模板：`ta_templates` + `ta_template_name`，`desk_ta` 增 templates/use/save/delete，
  对话框底部模板下拉 + 另存为。
- 技术分析三列改 grid 固定列宽（中间数值列居中，不再对不齐）。
- 新增 4 个用例；全量 1905 passed；构建 `desk.js?v=mwanmdp7`。

### desk：AkShare 噪声静音 + 资讯自动认标的（v1.3.7-76）

- `providers._call()` 内静音 `PerformanceWarning` / `FutureWarning`，`TQDM_DISABLE=1`，
  日志不再被 pandas 碎片化警告与进度条刷屏。
- 资讯推送前 `_annotate_news_symbols()`：用**全市场名称索引**（3 字以上，最长优先）
  与合约 / 股票代码识别标的，条目自带 `symbol` —— 右键「打开图表」不再依赖
  「自选 / 已打开图表」，没开个股图表也能跳。
- `fetch_profile` 加巨潮 `stock_profile_cninfo` 备用（AkShare 1.18.64 的
  `stock_individual_info_em` 已抛 Length mismatch）。
- 新增 `tests/test_minibt_desk_v137_fixes7.py`（13 个用例）；全量 1917 passed。

### desk：工具栏「＋」更多指标和策略（v1.3.7-77）

- 实时图表 / 本地图表工具栏在「指标」右边新增 **`＋`** 快捷按钮，
  tooltip「更多指标和策略」，点一下直接开 `pylightcharts` 指标 / 策略选择器
  （`indicator_picker`，带当前 cell / 合约），少一层菜单。
- 新样式 `.desk-tool-add`（24px 窄按钮）；策略模式下随「指标」一起隐藏。
- 新增 2 个用例；全量 1920 passed；构建 `desk.js?v=mwaoq37w`。

### desk：「指标」菜单末两项只在实时图表（v1.3.7-78）

- 排查：实时图表 11 项（含「个人指标策略管理…」「策略管理…」），本地图表 9 项（本来就没有）。
- 给本地图表加过的两项**已回退**；用例锁定该现状（本地图表断言不含）。
- 构建 `desk.js?v=mwap0mua`。

### desk：定时任务（调度器 v2，v1.3.7-79）

- `ops.TaskScheduler` 升级：触发 `interval / daily(HH:MM, mon-fri) / manual`，
  动作 `builtin / tool（MCP 工具）/ ai（提示词）`，落盘
  `~/.minibt/desk/ops/scheduler.json`（任务 + 200 条历史）。
- 保护：skip_if_running、连续失败 3 次自动停用、每天次数上限、只在交易时段、
  跳过手工休市日（`holidays.json`）、异步执行不卡 tick；AI 任务默认只读权限，
  危险工具默认拒绝（勾选后才带 confirm，审计 `scheduler-confirm`）。
- `OpsService` 新增 `_run_tool / _run_ai / submit_due / run_task`；
  `_suite_tick` 改为异步提交，结果经 `on_result` 推 `ops_tasks` / `ops_task_output`。
- 运维页「定时任务」：工具下拉（71 项）/ 参数 JSON / 提示词 / 触发 / 保护开关 /
  列表（动作·触发·下次·状态）/ 立即跑·编辑·启停·删除 / 执行历史 / 手工休市日；
  设置页新增「启用定时任务」总开关（`scheduler_enabled`）。
- `desk_ops` 扩到 tasks / task_add / task_update / task_remove / task_history /
  task_run / task_toggle / holidays（仍 71 个工具）。
- 新文档 `minibt_docs/docs/minibt_desk/manual/13.32_scheduler.md`；
  新增 18 个用例；全量 1939 passed。

### desk：定时任务 P2（多步 / 条件 / 模板 / 导入导出，v1.3.7-80）

- `action.kind = "sequence"`：多步串联，支持 `$0.xxx` 引用、遇错即停、
  `continue_on_error`、非 JSON 结果按失败处理。
- `when` 前置条件：`{tool, path, op, cmp, value}`，支持
  `> >= < <= == != contains / truthy / falsy / count`；字符串不做大小比较，
  判断异常不拦任务。
- 模板库 6 个（开盘前简报 / 收盘复盘 / 资讯刷新 / 持仓风险巡检 / 每日清理 /
  行情快照落库）+ `add_from_template`；`export_tasks` / `import_tasks`。
- 运维页：动作下拉加「多步串联」（步骤 JSON）、前置条件框、模板下拉、
  导出/导入按钮；列表加「前置条件」列。
- `desk_ops` 增 task_templates / task_from_template / tasks_export / tasks_import。
- 用例 18 → 27；全量 1948 passed；构建 `desk.js?v=mwbdlhlb`。

### desk：定时任务 P3（失败推送 / 重试 / 停机补跑，v1.3.7-81）

- 任务级 `notify`：`error`（默认）/ `always` / `never`，走告警通道推企业微信 / 邮件，
  内容是「任务名 + 耗时 + 摘要 / 错误 / 跳过原因」。
- `guard.retries`（0~5）：失败重试，间隔 0.5s→1s→1.5s；只有最终失败才计 `errors`。
- `guard.catch_up`：停机期间错过的那一次开机补跑，仅限 6 小时内。
- 运维页表单 + 列表悬停提示；`desk_ops` 的 task_add / task_update 接受这三个字段。
- 用例 27 → 35；全量 1956 passed；构建 `desk.js?v=mwbdztkx`。

### desk：任务 DAG + 命令全量接工具（v1.3.7-82）

- 定时任务支持前置任务：`trigger.kind="after"`（上游成功后点名跑，`next_run=-1`
  表示等待）+ `guard.depends_on`（定时任务要求依赖最近成功，默认 24h）；
  环检测拒绝 A→B→A；`dependency_state()` 给界面 / PI。
- 新增 `desk_cmd{cmd, args}`（71→72 个工具）：白名单直通界面命令，走
  `desk.handle()` 同一条路径；`CMD_BLOCK`（36 条：动钱 / 执行代码 / 改权限 /
  删数据）拒绝并提示用专用工具；拼错给 `did_you_mean`。
- 命令矩阵：新增 `🔒 只走专用工具` 状态，统计「覆盖 / 🔒 / 内部 / 待补」，
  待补 173 → 0；文档 13.30 自动重生成，13.29 / 13.32 补说明。
- 新增 14 个用例；全量 1970 passed。

### desk：四个扩展页入口开放（v1.3.7-83）

- `＋ 新建 ▾` 恢复：交易工作台 / 策略研究 / 本地数据平台 / 平台·运维（4 项）。
- 命令面板恢复 7 条（4 页 + 工作台对账 / 导出审计 CSV），关键字补中文。
- `desk_open_ui` 白名单加 workbench / datahub / ops / info，前端 `open_ui` 分支补齐。
- 文档 13.17：入口全部开放 + 运维章节按**定时任务 v2**（触发/动作/when/DAG/
  重试/补跑/推送/模板/导入导出/休市日）重写；入口速查加 MCP 工具列。
- 新增 7 个用例；全量 1977 passed；构建 `desk.js?v=mwbfc0jy`。

### desk：告警通道加微信公众号推送（xtuis，v1.3.7-84）

- `ops.Notifier` 通道 2 → 4：`wecom` / **`xtuis`（公众号）** / `email` / `webhook`（通用）。
- xtuis：`GET https://wx.xtuis.cn/{token}.send?text=&desp=`（**`wx.` 前缀**），标题 200 / 正文 1000 截断；返回 HTML 视为失败（防止假成功）；
  可换自定 URL（`{token}` 占位）；缺 token 明确报错。
- 通用 webhook：GET/POST + 模板 `{title} {text} {level}`（Server酱 / PushPlus / 钉钉）。
- 运维页告警通道：新增公众号 token / 地址、自定义 webhook 地址 / 方法 / 模板；
  保存时四个通道各存一次。
- `desk_ops` 增 `notify_config` / `notify_test`；命令矩阵覆盖 222 / 🔒 35 / 待补 0。
- 新增 14 个用例；全量 1990 passed；构建 `desk.js?v=mwbin4jk`。

### desk：公众号推送域名修正（v1.3.7-85）

- 默认推送地址 `xtuis.cn` → **`wx.xtuis.cn`**（前者是官网首页，HTTP 200 但收不到）。
- xtuis 返回值是 HTML 时判为失败并提示正确域名，杜绝"看着成功其实没送到"。
- 运维页占位提示与文档同步；新增 1 个用例（共 14 个）。

### desk：定时任务界面 —— 参数骨架 / 说明 / 帮助面板（v1.3.7-86）

- 选 MCP 工具 → 参数框自动填骨架：`{"tool":名称,"args":{全部参数}}`，
  有默认填默认（`tools.UI_DEFAULTS` 22 组），没有用 `""`；后端接受整段动作 JSON。
- 参数框下方显示工具说明（作用 + 每参数 类型/必填/默认）+ 内置任务说明
  （`ops.BUILTIN_DOCS` 5 条：做什么 / 什么时候用 / 参数）。
- 新增「帮助 ?」面板：列出 72 个 MCP 工具（说明 + 参数 + 可复制骨架）与 5 个
  内置任务，带搜索；目录走新命令 `ops_catalog`（缓存，只推一次）。
- 新增 9 个用例；全量 2000 passed；构建 `desk.js?v=mwbjg8jm`。

### desk：定时任务三处修正（v1.3.7-87）

- 任务表状态列只放短标签（长原因进 title）+ `.desk-suite-table-wrap`
  （固定布局 / 省略号）→ 不再把页面撑出横向滚动。
- 定时 AI 任务改按 **PI 的 models.json** 解析模型与 Key（内置 AI 配置兜底，
  谁有 key 用谁），修掉「PI 能用、定时任务报没配 API Key」。
- 事件类型跟随配置（PI → `pi_event`），跑完刷新 PI 会话列表，`register(run)`
  支持 PI 停止；只读权限只作用于当轮，不写进会话。
- 新增 3 个用例（共 38 个）；全量 2003 passed；构建 `desk.js?v=mwbjuvgv`。

### desk：定时任务独立成页（v1.3.7-88）

- 新增 `SchedulePage`（tab `__schedule`）：原运维页「定时任务」卡片整体搬过来
  （表单 / 模板 / 导入导出 / 任务表 / 历史 / 休市日 / 帮助面板）。
- 入口：`＋ 新建 ▾ → 定时任务（工具 / AI / 内置）`、命令面板「定时任务」、
  `desk_open_ui{target:"schedule"}`。
- 补丁路由拆分：`ops_task*` / `ops_catalog` / `ops_holidays` → 定时任务页；
  `ops` / `ops_token` / `ops_notify` / `ops_versions` → 运维页。
- 新增 8 个用例；全量 2011 passed；构建 `desk.js?v=mwbka2yh`。

### desk：定时任务「工具」下拉为空（v1.3.7-89）

- 根因：拆页后只推 `tasks.snapshot()`（无工具清单），运维页以前靠 `ops` 补丁顺带获得。
- 新增 `OpsService.task_snapshot()` 统一带 `tools / builtins / enabled`，
  6 处推送全部替换；前端再加 `ops_catalog` 兜底。
- 新增 4 个用例（共 12 个）；全量 2015 passed；构建 `desk.js?v=mwbo48qc`。

### desk：命令行工具 `python -m minibt.desk.cli`（v1.3.7-90）

- 子命令：doctor / status / snapshot / tasks / run / history / rpc
  （`--payload` / `--file` / `--set k=v`，`--json` 出原始 JSON）。
- token 三种来源（env → --token → --token-file）；403 / 400 / 连不上都翻译成中文建议；
  `ops_task_*` 这类只推补丁的命令提示「已提交」。
- 新增 12 个用例；全量 2027 passed；文档 13.17 / 13.32 补用法。

### desk：告警通道搬到设置页（v1.3.7-91）

- 设置 → 系统设置 → **告警通道**（资讯数据源下方）：公众号 xtuis / 企业微信 /
  邮件 / 自定义 webhook + 发送测试 + 最近 8 条记录；填 token 保存即启用。
- 运维页的告警卡片移除（Token / 版本 / 状态保留），说明指向设置页。
- `ops` / `ops_notify` 补丁同时喂设置页；新增 5 个用例；全量 2032 passed；
  构建 `desk.js?v=mwbpkhz2`。

### desk：告警规则（v1.3.7-92）

- 新增 `ops.AlertRules`（`alerts.json`）：6 条规则（拒单 / 成交 / 预警 / 行情停更 /
  任务失败 / 后台异常），可配开关·等级·去重窗口；`notify_rule()` 统一发送 + 去重。
- 钩子：`trading.set_alert_hook`（拒单 / 成交）、`check_alerts`（预警）、
  `_watch_market_resume`（行情停更）、定时任务失败（task_error）。
- 设置页「告警通道」底部新增「告警规则」表（保存 / 恢复默认）；
  `desk_ops{action:"alert_rules"}` 支持 list / save / reset。
- 新增 11 个用例；全量 2043 passed；构建 `desk.js?v=mwbqgrkr`。

### desk：告警规则 P2（v1.3.7-93）

- 新增 3 条规则：`position_risk`（浮亏占市值 > 5%，可改）/`order_stale`
  （挂单超 10 分钟）/`login_lost`（交易连接从好变断）。
- 规则支持 `threshold` 阈值字段（带 label/unit），设置页多一个输入框；
  `trading.stale_seconds` 按规则注入（关掉=0）。
- 单测 11 → 17 个；全量 2049 passed；构建 `desk.js?v=mwbr09wx`。

### desk：告警 P3 + 四入口再收 + 说明上下布局（v1.3.7-94）

- 告警规则 9 → 14 条：`strategy_live` / `strategy_error` / `strategy_drawdown` /
  `news_macro` / `news_keyword`（后两条默认关）。
- 静默时段（默认关，23:00–08:00 只放严重）+ 每日汇总（默认关，16:00 一条）；
  `alerts.json` 存 `rules/quiet/digest`，PI 用 `alert_rules mode:"settings"`。
- 四个扩展入口（工作台 / 研究 / 数据平台 / 运维）再次注释关闭，**定时任务页保留**。
- 定时任务页工具说明改上下布局（整行独占 + 名字/说明/参数分行），帮助面板同步。
- 单测 17 → 29；全量 2063 passed；构建 `desk.js?v=mwbreszz`。

### desk：净值曲线 + 资讯关键词（v1.3.7-95）

- 新增 `ops.EquityStore`（`equity.db`）：每 60s 采一条账户净值，保留 400 天；
  `stats()` 给峰值 / 回撤 / 最大回撤 / 当日盈亏 + 曲线点；`ops_equity` 命令。
- `strategy_drawdown` 改读净值序列（重启不丢峰值）；设置页画 canvas 曲线。
- 资讯关键词自定义（`alerts.json.keywords`）：不依赖自选/持仓，命中标题或摘要
  就推；同一条不重复、同词 10 分钟最多 3 条；PI 用 `alert_rules mode:"settings"`。
- 新增 14 个用例；全量 2076 passed；构建 `desk.js?v=mwbsb1ko`。

### desk：告警分组 + 回测/优化完成提醒（v1.3.7-96）

- 规则表按 `source` 分组（交易 / 预警 / 行情 / 定时任务 / 持仓 / 策略 / 资讯 / 系统），
  组标题带条数。
- 新增 2 条规则（**默认关**）：`backtest_done` 回测完成、`optimize_done` 参数优化完成；
  `strategy_lab` 三处状态切换挂 `_notify_done()` → `desk.notify_lab_done()`，
  出错走 `system_error`。
- 单测 29 → 35；全量 2082 passed；构建 `desk.js?v=mwbtn9ak`。

### desk：告警中心页（时间轴 + 搜索，v1.3.7-97）

- 新增 `ops.AlertLog`（`alerts_log.db`，保留 180 天）：每条命中（含静默压制）
  落库（时间/规则/等级/标题/正文/通道/成败）；命令 `ops_alert_log` /
  `ops_alert_log_clear`；快照带统计。
- 新增页面 `AlertLogPage`（`__alertlog`）：入口 `＋ 新建 ▾ → 告警中心` + 命令面板；
  按天分组的时间轴、搜索（标题/正文/规则）、等级与规则筛选、统计、加载更多、清空。
- `desk_ops{action:"alert_log"}`（query / level / rule / limit / mode=clear）。
- 新增 10 个用例；全量 2092 passed；构建 `desk.js?v=mwbu5r54`。

### desk：告警中心一键复现 + 柱状图（v1.3.7-98）

- `alerts` 表加 `symbol`（老库自动 ALTER）；`notify_rule(..., symbol=…)` 记录合约，
  页面点击行 / 「打开图表」按钮 → `openChart(symbol)`。
- `AlertLog.daily(14)` + 页面近 14 天柱状图（等级堆叠 + 条数 + 日期，悬停明细）；
  命令与工具都带 `daily`。
- 单测 10 → 16；全量 2098 passed；构建 `desk.js?v=mwbuf6w2`。

### desk：技术分析标签固定右上角 + 开关（v1.3.7-99）

- 徽标从「整页 element + 按最后一根 K 线定位」改为挂在**图表格子**里，
  CSS `right:12px/top:10px` → 永远在图表右上角。
- 新增设置 `ta_badge`（默认开）：关掉后不画；开关放在标的资讯 → 技术分析 ⚙
  对话框（模板下拉下方），`set_setting` 落盘。
- 新增 5 个用例；全量 2103 passed；构建 `desk.js?v=mwbusdl7`。

### desk：TA 徽标悬停改卡片（v1.3.7-100）

- 禁用原生 `title`，改为悬停弹出 `.desk-cal-pop` 风格卡片：
  头部（项数 / 多空中立 / 评分）+ 每行「指标名 ｜ 看多·数值·备注」（红/绿/灰），
  贴图表格子右边界并夹在格子内。
- 本地图表页同步修好（此前仍是「按最后一根 K 线 + top:28px + title」的老实现）。
- 单测 5 → 9；全量 2107 passed；构建 `desk.js?v=mwbvf5sv`。

### desk：修「跑测试把告警真推到微信」（v1.3.7-101）

- `tests/conftest.py` 整个会话把 `MINIBT_DESK_OPS_DIR` 指到临时目录（不碰用户 token）。
- `Notifier._muted()`：pytest + 用户家目录的真实配置 → 静音；新增
  `home_notify_path()`（不受 `MINIBT_DESK_OPS_DIR` 影响）。
- `MINIBT_DESK_NO_NOTIFY=1` 可全局关推送（记录照样写，通道显示 local）。
- 新增 4 个用例；全量 2111 passed。

### desk：告警只认即时事件（v1.3.7-102）

- 资讯类：首扫只做基线（缓存里的旧新闻/旧日历不推）；日历缓存 `stale` 直接跳过。
- 回撤/持仓风险：必须有**本次运行**的采样，且只在「刚破阈值」推一次（回落才重置）。
- 策略启停：关窗口的 `stop_strategy_live()` 静默；内部重启不推；只有用户操作才推。
- 规则默认值不变（`strategy_live` 仍开）。
- 新增 9 个用例；全量 2120 passed。

### desk：PI 技能对话框搜索按钮竖排（v1.3.7-103）

- `.desk-pi-btn` 加 `white-space: nowrap / flex: 0 0 auto / min-width: 56px`，
  搜索行输入框 `flex: 1 1 auto; min-width: 0` → 按钮文字一行 ✓
- 小体验：空关键词给提示并聚焦；搜索中按钮变「搜索中…」+ 禁用（12 秒兜底复原）；
  未安装技能的空态文案更可操作。
- 新增 6 个用例；全量 2126 passed。

### desk：TA 首帧报错 + 技能搜索 404（v1.3.7-104）

- TA：K 线不足时 `note` 显示「数据不足」（异常原文进 `row.error`），
  `snapshot()` 用 `retry: true` 让前端 8 秒后自动再算一次；catalog 失败日志去重。
- 技能搜索：skills.sh 接口 `/api/skills` → **`/api/search`**，按新返回结构
  （`id/source/skillId/name/installs`）映射，安装包名取 `owner/repo`。
- 新增 7 个用例；全量 2133 passed。

### desk：PI 对话 / 悬浮窗 Markdown 表格（v1.3.7-105）

- `pi-chat.ts` 抽出并导出 `markdownToHtml` 等一套 Markdown 渲染（含 GFM 表格：
  对齐 / 补列 / 单元格行内格式 / XSS 转义）。
- 悬浮窗 assistant 气泡改用 Markdown（以前纯 textContent，表格只显示一堆 `|`）。
- 新增 `.desk-pi-table*` / `.desk-pi-float-bubble.md` 样式；8 个 vitest 用例，
  vitest 146 passed。

### desk：PI 圆点导航悬停两条提示（v1.3.7-106）

- 圆点与导轨容器不再设原生 `title`（改 `aria-label`），只留自定义浮出 label；
- 新增 3 个用例；全量 2136 passed。

### desk：圆点导航提示内容太少（v1.3.7-107）

- 回答节点提示改成两行「问：…（前 90 字）／答：…（前 140 字）」，用户节点带「问：」；
  `aria-label` 同步带问 + 答。
- CSS 提示卡片放宽到 320px、允许多行（最多约 3 行）。
- 用例 3 → 5；全量 2138 passed；构建 `desk.js?v=mwby8s84`。

### desk：圆点导航提示被挤成竖排（v1.3.7-108）

- 根因：导轨 `.desk-pi-nav` 只有 26px 宽，label 是它的普通 flex 子项 → 逐字换行。
- 修法：label 绝对定位（贴圆点左侧）+ `width: max-content` +
  `max-width: min(340px, 62vw)`；实测宽 358px / 4 行、不超出窗口。
- 用例 5 → 7；全量 2140 passed；构建 `desk.js?v=mwbyhx3u`。

### desk：格 1 残留指标删不掉（v1.3.7-109）

- 后端 `indicator_payload` 增 `pending_keys`；前端 pending 时保留范围改成
  `items ∪ pending_keys`，多余序列当拍删除（不再"只加不删"留残留）。
- `IndicatorLayer.removeSource()` 先物理删注册表序列（pane / overlay / 图例），
  即使不在 items 里也能删掉。
- 后端删除匹配改 `_same_indicator_key()`：忽略大小写 + 忽略 `:线名` 后缀。
- 新增 6 个用例；全量 2146 passed。

### docs：手册补齐「资讯中心 + 标的资讯」（v1.3.7-110）

- 新增 `minibt_docs/docs/minibt_desk/manual/13.31_news_center.md`（11 节）：
  两页分工、AkShare 可选 / 富途优先 / TTL 表、资讯中心五分区与条目三操作、
  标的资讯页 4 个插件（含 `ta_badge` 开关）、图上事件圆点、告警联动
  （`news_macro` / `news_keyword` + 只认即时事件）、设置页、PI 工具表、
  9 条前端命令对照、7 条 FAQ、按轮次的版本记录。
- 导航：`13.31 资讯中心与标的资讯`（手册）在前，原设计稿改标 **13.31a**，两篇互链。
- `mkdocs build --strict` 0 警告。

### desk：换合约后旧合约的线留在图上（v1.3.7-111）

- 用户截图 `持仓线没清理干净.png`：清仓后旧合约（约 800）的线还在，切到新
  合约（约 9000）时价格轴被拉到 0~12000，K 线压成一条线 ✗；预警线 / 挂单线
  同样要查。
- 修法（不再只靠"补丁能对上页面"）：
  - **价格闸门**：`_priceBand()` 取当前格最后 300 根 K 线的价格带，
    `_priceFits()` 上下留 50%；持仓 / 挂单 / 预警**画之前**过闸，
    `pruneForeignLines()` 撤销已存在的不合格线；`setBars()` 里复查一次；
  - **合约闸门**：`setPosition / setOrders` 带补丁的 `symbol`，
    别的合约的补丁一律忽略；
  - **清理加固**：新增 `clearAllLines()`，`resetForSymbol()` 与
    `setSymbol()`（合约变化）都调用；本地图表同款 + 换 CSV 时清线；
  - **指标图层**：补丁 `symbol` 变化先清空所有序列；主图**叠加线**若没有任何
    点落在当前价格带里直接丢弃（策略停止线就是这一类）。
- 新增 6 个用例；全量 2154 passed；构建 `desk.js?v=d1d1b706`。

### docs / 打包：sdist 过期自查（v1.3.7-112）

- 用户追问「改了 pylightcharts 是不是要重打？minibt 真的不用重打吗？」——
  实测两处 sdist 已过期（`pylightcharts` 的 `docs/changelog.md`、
  本包的 `CHANGELOG.md`）：根因是 **`python -m build` 之后又改了会被 sdist
  收录的资料**（CHANGELOG / RELEASE_NOTES / README / RELEASING / docs / tests）。
- 新增 `scripts/check_dist_fresh.py`（仓库根 `scripts/`）：把 sdist 里每个文件
  与工作区**逐字节**比对（`PKG-INFO` / `*.egg-info` / `build/` 自动跳过），
  过期返回 1；`RELEASING.md` 第 5 步已补。
- 新增 `tests/test_check_dist_fresh.py` 5 个用例。
- 附注：`data/utils.py` 是 `python -m build` 现场按**包内基础数据**重生成的
  （只会出现 `aliased / l2609_60 / pp2609_60 / test`）；若中途跑过
  `LocalDatas.rewrite()`（非 base_only），先重新 build 再上传 ✓。

### 测试

- 新增 `tests/test_minibt_desk_v137_indicators_alerts.py`（19 个用例）：
  目录完整性、三库条目数对平、NON_KLINE 不入目录、缓存指纹 / 重建、
  预警账户归属、`account_scope` 还原、本地预警取价、前端 6 处断言。
- `tests/test_minibt_desk_lsp.py` 断言同步成 `_button('预览', ...)`。

## [1.3.6] - 2026-11-06

> **一句话**：v1.3.5 之后的一批 **desk** 大修（11-04 ~ 11-06，7 轮用户反馈 +
> 2 轮自查），重点在**账户 / 交易 / 登录 / 行情**：三个统一账户（快期模拟 /
> 富途模拟 / TqAccount）且**按页面 / 按格独立**；「富途模拟」改成**富途官方模拟盘**；
> 交易面板改「快期式」四按钮、**全部限价（对手价）**、锁仓按平今 / 平昨拆单；
> 登录信息（含密码）持久化到独立文件；股票行情泵补齐；修掉「开图 / 换合约卡
> 158 s / 188 s」的卡顿根因。
>
> 详细发布说明见 [`RELEASE_NOTES.md`](RELEASE_NOTES.md)；逐条改动见
> `minibt_docs/docs/changelog.md` 的 `## [v1.3.6] - 2026-11-06` 段；
> `pyproject.toml` / `__init__.py`（`__version__` + `版本信息`）/ `README.md`
> 徽章已同步为 **1.3.6**；wheel + sdist 输出到 `minibt/dist/`
> （1.3.5 归档在 `minibt/dist/archive-1.3.5/`）。

### desk：账户 / 交易

- **期货登录信息持久化**（用户名 / 记住密码 / 使用实盘账户 / 期货公司 /
  资金账号，**交易密码永不保存**）：登录信息改存**独立文件**
  `~/.minibt/desk_login.json`，并从旧的 `desk_user_prefs.json` 自动迁移；
  前端加 `loginCache`（打开即回填）、字段一变 400ms 防抖落盘 + 关窗前再存一次
  （不点「登录」也不会丢）。
- **账户按页面 / 按格独立**：`Desk._home_key`（首页）+ `_account_keys`
  （`chart:SYM` / `chart:SYM#cell`）；数据读取按 key 显式取
  （`AccountView.payload/summary/tables/is_real(..., key)`），首页与每个
  实时图表页互不影响；多布局每格可各用一个账户。
- **首次打开实时图表按格 1 合约选账户**：股票 → 富途模拟，
  期货 → 快期模拟（**即使登录了实盘也默认快期模拟**）；之后用户手选的账户保留。
- 品种校验：股票页只能用富途模拟、期货页只能用快期模拟 / TqAccount，
  不匹配时**明确提示 + 下拉框弹回**。
- 本地图表：隐藏切账户下拉框，只接本地模拟账户；`local_account` 补丁与真实
  账户补丁**双向隔离**。

### stock_api：富途账户

- **「富途模拟」= 富途官方模拟盘**：`trd_env='SIMULATE'` 时 desk 强制开启交易
  上下文（不涉及真钱），登录框「启用交易」默认勾选；持仓 / 权益 / 委托
  **优先读富途**（`position_list_query` / `accinfo_query`），不再用 minibt 的
  本地记账账户。
- 标签 / 实盘判定按 `_trd_env`：`股票模拟（富途）` / `股票实盘（富途）` /
  `股票本地模拟`；只有 `REAL` 才需要二次确认。
- CN / HK / US 是**独立模拟子账户** → `_ensure_market()` 按需切换交易上下文；
  日本个股 / ETF / REITs **无模拟盘** → 下单明确报错（仅日本期货支持模拟）。

### desk：行情 / 体验

- **股票行情泵**：`pump()` 遍历所有行情源（期货 + 股票），富途侧 `deadline`
  按"秒"传；股票 quote 补齐买一 / 卖一 / 开高低收 / 昨收；一字线自动用最新价撑开。
- 买卖盘每次打开图表**默认关闭**；价格框 ▲▼：空值 = 卖一 / 买一，
  否则 ± 一个**最小变动价位**。
- 交易账户面板在 `_chartPageFor()` 返回 null 时不再抛异常（卡片 / 持仓正常渲染）。

## [1.3.5] - 2026-10-31

> 沿用 1.3.4 的打包流程；`pyproject.toml` / `__init__.py`（`版本信息` +
> `__version__` + `__version_info__`）/ `README.md`（徽章 + 更新亮点）已同步为
> **1.3.5**。本版内容按主题归并（明细见 `minibt_docs/docs/changelog.md` 的
> v1.3.5 段）。

### 亮点

- **新增「指标和策略」页（仿 TradingView）**：114 个 TradingView 指标做成卡片库
  （分组 / 搜索 / 收藏 / 热门 / 每页 24 张 / 自动缩略图），支持**添加用户自己的
  指标和策略文件夹**并递归加载；点卡片 = **新开一个页签的完整本地图表**
  （底部编辑器自动打开、指标/策略自动画到图上）；卡片右键可「打开 / 在图表上
  使用（选哪个图表） / 重载图表」；页签右键「查看原始码（只读）」；
- **代码展示统一** `# coding: utf-8` + `from minibt import *`，策略依赖的指标类 /
  函数通过 AST 依赖闭包一起带上（`cci.py` → `CCIStrategy` + `CCI`），老脚本
  打开时自动重建；
- **参数优化大修**：目标 3 → **9 个**、帕累托前沿 1~3 轴（含三维 canvas，
  可拖动旋转 + 悬停 tooltip）、「优化设置」（method / n_jobs / n_trials /
  sampler / pruner）、参数网格编辑器；`values_0` 恒 0 / 目标行内列被丢弃 /
  单目标 X 轴 / trial 差 1 等一批问题修好；优化超 1 分钟会提醒改用信号参数优化；
- **回测结果页的「回撤」副图可关**：新增 `config.drawdown_plot`（默认 `False`）；
- **多合约回测的盈亏副图不再空白**（同一根 K 线多条腿成交 → 重复时间戳 →
  lightweight-charts 报 `Value is null`）；
- **浅色主题**：等待页底色 / 分隔线 / 回放视窗三处不再发黑或跑偏；
- **图表观感**：画线导航条（间距 0、直角、隐藏滚动条但能滚）、副图删除不再
  连带、`vbar_up_color` / `vbar_down_color` 真正生效（alpha 0~255 → 0~1）、
  策略里的柱体 / 蜡烛 / 色带 / 参考线 / 水印 / VP / 表格在 desk 也按样式出图；
- **编辑器**：jedi 的 sys.path 显式带源码仓库根、可手动指定 minibt 路径、
  任何打开过的文件都能保存、个人指标「加不上图」不再报成功；
- **稳定性**：关 desk 不再刷 `runJavaScript: disabled in Discarded state`；
  图表右键菜单（全部K线 / 最新K线 / 画线 / 清除画线 / 截图）+ 原生右键拦截，
  截图改为后端落盘 `~/.minibt/exports/`；后台任务改为**按线程**捕获 stdout。

### 新增

**指标和策略页**

- 卡片列表（分组 / 关键词 / 收藏 / 热门排序 / 每页 24 张）+ 自动缩略图（首批
  纯 SVG；用户自己的指标 / 策略也会生成，且**保留颜色 / 线宽 / 虚线 / 柱状配色 /
  信号箭头 / 参考线**）；
- 用户分组：「＋ 添加指标和策略」（选文件夹，递归扫描 `.py`，分组名 = 文件夹名，
  存 `~/.minibt/desk/tv_groups.json`）与「－ 删除指标和策略」（只删记录）；
  `TradingView` 是系统默认分组（不可删），「全部分组」= 默认 + 用户分组合并分页；
- 卡片右键菜单：`打开指标 / 打开策略`、`在图表上使用 ›`（只列本地 / 实时图表，
  菜单出现在鼠标处）、`重载图表`（单张重算，深浅两套封面）；
  「刷新」右边新增「重载图表」（整页 24 张，后台线程逐张推送）；
- 收藏：图表工具栏 ★ / 顶栏页签 ★ / 收藏 tab（跨分组，且只显示仍在分组里的）；
  图表工具栏「截图」= 保存 PNG **并且**覆盖卡片封面（按当前主题，深浅各一套）；
- 页面右下角「回到顶部」圆钮（能滚动且滚过筛选行才出现）；
  自动缩略图保留指标样式（线宽 / 点虚线 / 柱状涨跌配色 / 信号箭头 / 参考线）；
  卡片封面按主题分开（`<key>_light.png` / `<key>_dark.png`，不跨主题回退）；
- 页签：名称带「指标 / 策略」（`策略 · cci · CCIStrategy`）、同一个指标只开一次、
  页签条支持**滚轮横向滚动**、关页签跳「后一个 / 前一个」；
- 进图表时同步 `local_list`（商品搜索框和本地图表一样有内置 / 用户数据）；
  连了行情时商品搜索框可在线搜合约并替换本页数据（`tv_live`）。

**参数优化 / 回测**

- 9 个优化目标 + 每目标权重；帕累托前沿 1~3 轴（三维 canvas）；优化设置
  （method / n_jobs / n_trials / sampler / pruner）与参数网格编辑器；
  `OPTTargetType` 全量指标参与计算；单目标时 X = 账户权益、tooltip 用真 trial 序号；
  慢优化 1 分钟提醒改用「信号参数优化」；`config.drawdown_plot`。

**图表面板 / 画线 / 主题**

- 多布局画线共用左侧导航条（图标原大小、`title` 悬停、间距 0、直角、
  隐藏滚动条但可滚、按「合约|周期」持久化、作用于最后点击的格）；
- 加载策略后再加指标（策略线与指标线互不覆盖）、删副图不连带、浅色主题三处；
- 回测 / 参数优化页图表工具栏的「画线 / 删除画线」改图标；图表右键菜单五项。

**编辑器 / 脚本**

- jedi 显式 sys.path（源码仓库优先）+ 悬停 / 补全注释；设置里可手动指定
  minibt 路径（默认关，改完即时生效）；任意打开过的文件都能保存；
- 多策略文件弹窗选类；文件里「导入」的指标类也能加到图表；
- 生成的个人脚本头部统一、缺依赖自动自愈、参数个数按 AST 统计。

**界面 / 稳定性**

- 页签可滚轮横滚、关页签跳邻居；原生右键在顶栏 / 工具栏 / 画线导航条 /
  二级报价 / 指标和策略页禁用（输入框与编辑器保留）；
- 关窗 / 页面 discard 后不再 `runJavaScript`；后台任务按线程捕获输出、
  `FilteredOutputRedirector` 只在仍是自己的流时复原。

### 修复

**指标和策略页**

- 「在图表上使用」菜单跑左下角、列出指标图表页 → 用鼠标坐标 + 排除指标页；
- 用户策略卡片缩略图只有 K 线、点开不画策略 → 跑一遍策略（预览模式，秒级）；
  根因是 `_local_indicator_payload()` 的 `page` 只按 CSV 反查 → 补丁没 `page`；
- 启动时 `[desk-personal] 跳过 xxx.py：NameError` → 生成头部补依赖 / 老脚本自愈；
- 「全部分组」看不到 TradingView、系统默认分组被删 → 用真 key + 拒绝删除；
- 本地图表页被「挤爆」（底部面板要最大化才见 / 编辑器滚不动）→ 去掉多余的
  `position: relative`，恢复 `.desk-stack > *` 绝对铺满；面板回到 3:1；
- **截图后卡片「指标 / 策略」标记消失**：标记改成**前端 HTML 层**
  （`.desk-tv-card-tag`），SVG / PNG 封面都有；类型信息也写进缩略图页脚。
- **指标表格的定位**：表格挂在**图表区**（`.desk-cell-main` / `.desk-chart-host`）
  并给 `.desk-cell-main` 补 `position: relative`，拖动也限制在图表区内 →
  右侧二级报价出现时不再遮挡、也不会跑出图表。
- **表格 / VP 跟随的三条规则**：鼠标移动时显示历史那根；**停住 2 秒**自动回
  实时；在最新那根 / 右侧空白时始终用最新数据（以前"保留旧跟随"会卡顿）。
  只有 VP 没有表格的策略也起计时（以前直接 return，VP 永远停在历史）。
- **实时图表挂策略后 VP / 表格仍不跟随鼠标**：`crosshairBoundCells` 以前记
  布尔"已订阅"，而挂策略会**重建格子**（新 chart 实例）→ 再也不给新图表订阅
  十字线 → 只有实时更新。改成存**订阅的 chart 实例**，chart 一换就重新订阅。
- **实时图表的 VP / 表格不跟随鼠标**：十字线只有"离开绘图区"才回落最新
  （两根之间不再当成离开）；`VpOverlay._search()` 在数据范围内取**最近的
  一根**（不再只认精确命中）；新 K 线到达时先显示最新、鼠标再动才跟随。
- **「＋ → 实时图表」切合约**：`_renameChart()` 补 `setCellSymbol(0, …)`
  （交易标的 / 画线键跟着换）+ `tab.baseLabel`；`_on_switch_symbol()` 改用
  `data_length()` 取数并记 K 线状态（`_note_kline_state`），修掉"初次切合约
  只有 2 根 K 线、切周期才正常"。
- **实时图表的 VP 档区**：`realtime._vp_spec()` 以前把 `price_bars=None`
  原样传下去 → 用整段数据的 low/high（矩阵按 500 根分档）→ 分布被压扁；
  现在默认 500（显式 0 = 整段，语义不变）。表格后端共用、前端已改每格订阅。
- **编辑器切换标签时在资源管理器定位文件**：`revealInExplorer()` 逐级展开
  上层目录（懒加载回来继续）、`scrollIntoView` 滚进可见区并短暂高亮；
  面板刚建/刚换根目录时先记住，根目录到了再定位。
- **本地图表 VP（成交量分布）位置 / 表格跟随鼠标**：VP 的档区窗口以前用
  `price_bars or 120`（指标默认 500）→ 分布被压扁、挤在价格区间下半部分；
  现在按指标的 500 根窗口、逐行还原（`vpLo/vpHi` 长度 = 矩阵行数）。
  十字线改为**每格各自订阅**（以前只订阅格 1 → 其它格的表格 / VP 收不到
  十字线，看着像静态图）。
- 页签无滚轮滚动 / 关页签回首页 / 指标页重复打开 / 卡片封面跨主题 → 已修；
  本地图表编号改为「当前最小空闲序号」（关完再建回到 1，指标图表页不占号）；
  添加分组后立刻切到新分组 ✓

**参数优化 / 回测**

- 优化图表三张图空白、按当前目标重新优化失效、`values_0` 恒 0、单目标 X 轴与
  trial 差 1、多合约盈亏副图空白、drawdown 开关、慢优化提示。

**图表 / 画线 / 主题**

- 画线工具条间距 / 直角 / 滚动条；浅色主题分隔线、等待页、回放视窗；
  `vbar_*_color` alpha 口径；格 1 柱体配色；策略 vbar / 蜡烛 / 色带 / 参考线 /
  水印 / VP / 表格样式；`stop_price` 数值离谱；`IndFrame.linestyle` 与单线
  `BtIndicator.linestyle` 静默失效；`Ture` 笔误。

**编辑器 / 脚本**

- 悬停无注释、只能保存个人目录、个人指标假成功、多策略默认取第一个、
  导入指标类不被识别、`custom Stop` 子类失效 / 脚本函数被误当指标。

**稳定性**

- `runJavaScript: disabled in Discarded state`、图表右键菜单不自动收起、
  输出流串台 / `I/O operation on closed file`。

### 测试

- 新增/更新一批 desk 测试（画线、格策略指标、hist 主题、vbar 颜色、编辑器保存、
  止损线、浅色主题、副图删除、优化选项 / 目标 / 帕累托、LSP 路径、编辑器 minibt
  路径、本地图表保留指标、策略选择、慢优化提示、导入指标、右键菜单截图、
  指标和策略页 / 用户分组）与 `jslib/test/strategy-lab-optimize.test.ts`、
  `jslib/test/pareto-3d.test.ts`、`jslib/test/sub-pane-visibility.test.ts`。

### 依赖

- `pylightcharts>=0.1.8`（本版已随 0.1.8 打包：desk 前端资源
  `desk.js` / `desk.css` 与 `pylightcharts/headless.py` 的 `<body>` 主题、
  `abstract.py` 的柱体基线 `base`、`colors.normalize_color()` 都在该版本里）。

## [1.3.4] - 2026-10-30

### 亮点

- **`Gui.Desk` 进 Jupyter / Notebook**：notebook 里不再弹 Qt（那会卡死 kernel），
  自动改成**浏览器壳 + iframe** 内嵌；`tutorials/plots/12~15` 四个最小示例
  （btplot / 回测 / 回放 / 实时）随包提供；
- **本地图表多开 + 副本独立**：顶栏「＋ → 本地图表」/ 首页-图表工作台
  「新建本地图表」/ 命令面板都能新建副本（本地图表1 / 2 / 3…），
  指标 / 策略按**页面**存，同一份 CSV 开两页也互不影响；
- **一个页面只放一个策略**（换策略 = 先清上一个，布局 / 指标保留）；
  需要多策略时用**多开页面**、「策略实盘」（可同时多个子进程）或
  **只读叠加**（只画线、不交易）；
- **多布局真正可用**：格 2..N 的 K 线 / 指标增量更新、持仓线 / 挂单线按格
  路由、换合约只换鼠标最后点击的那一格；加载策略时「合约数 ≤ 现有格数」
  就**保持当前布局**（多余格不关），格数不足才自动加格；
- **计算搬到后台线程**：重策略（如 `KalmanFilterStrategy` 的 Python 循环）
  不再卡界面 —— 先推 K 线、后台算线、算完自动上图；收盘后自动挂起；
- **图表右键增强**：新「我的模板 ▸ / 保存当前指标模板」；画线共用左侧
  竖排导航条，按「合约|周期」本地持久化。

### 新增

- `Desk._strategy_lives`：**策略实盘支持多策略**（一个文件一个子进程），
  重复启动同一文件被拒；按钮显示 `运行中 ×N`，`停止实盘` = 停止并删除全部；
  「策略管理」里每行可改两个开关（新 K 线 next / 运行 next）/ 看 PID / 删除；
- **只读叠加（display-only strategy）**：`run_overlay(replay=False)` 只跑
  `__init__` 画线，**不跑 next、不碰账户**，同一页可叠多个；
  身份 =（文件绝对路径, 类名），同一个再点 = 重新加载；
  「🗑」菜单与「策略管理」里可单条删除，两个运行开关置灰；
- **本地图表多开**：独立页签 `local:1/2/3…`、页面级指标与策略、
  「复制当前页面」、页签显示当前策略名（`本地图表1 · test`）；
- **多布局画线**：左侧竖排导航条（46px，带 `趋势线 · TrendLine（Alt+T）`
  tooltip），存 `~/.minibt/desk/drawings.json`，键 = `合约|周期`；
- **图表右键「我的模板 / 保存当前指标模板」**（本地图表 + 实时图表，
  作用在鼠标最后点击的那一格）；
- **指标 / 策略后台计算**：`_strategy_results` 队列 + `_heavy_jobs` 门控
  （后台任务期间主线程不碰 tqsdk）、格 2..N 的完整库指标延后补推；
- 编辑器工具栏「策略管理」按钮（紧跟「加到图表」）、图表工作台两栏
  （左列本地图表 / 右列新建）、回放实验室「弹菜单选本地图表页」；
- `pylightcharts>=0.1.7`（desk 前端资源重建，见 pylightcharts CHANGELOG）。

### 变更

- **加载数据只加载 K 线**（本地图表）：重新打开本地数据不再带出上次的指标，
  指标请重新「加到图表」或用指标模板；
- **布局规则（加载策略后）**：格数 < 策略合约数的布局**禁用**；相等可切
  （合约按格对上）；更大可切（多出来的格子没有策略线、保留原样）；
- 命令面板快捷键 `Ctrl/⌘+K` → **`Ctrl/⌘+P`**（`Ctrl+K` 让给编辑器的注释）；
- 本地 / 实时布局按 `scope` 分开保存；保存同名布局需「确认替换」；
- 指标增量更新与 K 线一致（同根 1 点 / 新 K 线至少 2 点 / 断线按时间补缺口）；
- 编辑器「帮助」页补充：一个页面只支持一个策略、重载会先清理、
  指标失败不加载、`next()` 运行时出错不影响图表。

### 修复

- **指标缺口被连成直线**（`Chandelier_Exit` / `SuperTrend_STRATEGY` 等一半
  `up` 一半 `dn` 的指标）：首尾空点裁掉、中间缺口补透明点，效果与
  TradingView `plot.style_linebr` 一致；
- **`ADX_and_DI` 每次计算都刷 `RuntimeWarning`**（`invalid value in
  less_equal` / `divide`）：numpy 的 errstate 是**线程局部**的，desk 后台线程
  拿不到主线程的 `np.seterr` → 改为 `astype('float64') + fillna` 比较、
  除法包 `np.errstate`；
- **多布局**：第 2..N 格没有持仓线、切合约整页跳走、工具栏切布局后端不知道、
  指标总加到格 1、右键关闭格 2 关成格 1、切换主题其余格仍是深色；
- **策略线串格 / 策略管理删不掉**：`_local_indicator_payload()` 末尾又
  `strategy['items'] + items` 把全部线加一遍 → 只用本格那一组；
  策略管理按行 `key`（页签 id / 绝对路径|类名）删除，关页清理幽灵记录；
- **策略 `next()` 运行时报错不再影响图表**：首次弹窗、之后只写日志，
  图表 / 指标不动；指标算不出来时回滚 + 弹窗（不加载上图表）；
- **本地图表「初始加载」策略线串格**：后端推的布局不再用前端过期的每格
  合约回写；格 3 加第一个指标不显示（占位 K 线）→ 数据到了自动补推；
- **收盘后还在空转**：行情指纹没变直接 return，末根超过
  `max(10 分钟, 5 个周期)` 判定已收盘并挂起，日志只记一次；
- 首页下方预览图严格按「K线」开关显示（空数据自动重试，不再永远迷你折线）；
- `AdaptiveTrendTrail` 预热期 `RuntimeWarning`、`Twin_Range_Filter` 短数据
  越界、富途/天勤行情与订阅、主题与主副图分隔线等零星问题。

### 测试

- 新增 / 扩充 desk 回归：`test_minibt_desk_async.py`、
  `test_minibt_desk_cell_indicators.py`、`test_minibt_desk_local_pages.py`、
  `test_minibt_desk_layout_strategy.py`、`test_minibt_desk_overlay_page.py`、
  `test_minibt_desk_one_strategy.py`、`test_minibt_desk_runtime_errors.py`、
  `test_minibt_desk_cell_switch.py`、`test_minibt_desk_drawings.py`、
  `test_minibt_desk_context_templates.py`、`test_minibt_desk_home_preview_kline.py`
  等，以及指标和策略页 / VP 表格跟随 / 切合约相关的一批新测试
  （本机 `pytest -k desk` **1307 项通过**）；
- 前端 `jslib` 侧 `vitest` **132 项通过**，`tsc --noEmit` 干净。

### 依赖

- `pylightcharts>=0.1.8`（0.1.7 → 0.1.8：desk 前端资源重建 —— 指标和策略页、
  VP / 指标表格跟随鼠标、多布局十字线按格订阅、柱体基线 `base`、
  截图后端落盘、颜色 alpha 规范化等）。

> 1.3.4 的逐项记录（含每个 P 编号修复）见
> `minibt_docs/docs/changelog.md` 的 `[v1.3.4]` 一节。

## [1.3.3] - 2026-10-27

### 亮点

- **纯指标策略不再多出「回测结果 / 指标记录」两页**：没有 `next()`、
  不产生交易的指标策略（例如 `vp.py` 的 `RollingVolumeProfile` 系列）
  只画指标，不会因为“权益是一条恒定平线”被误判成有回测数据。
- **本地图表 / 实时图表策略链路**：本地 CSV 策略、配对策略、实时多合约策略
  的指标、信号、持仓线、停止线、回测结果和参数优化入口统一。
- **图表与指标样式**：`PlotInfo` 的线型、线宽、图例、`bandstyle`、
  `signalstyle`、`tablestyle`、水印、逐点信号文字等能力在 desk 中落地。
- **行情与账户**：期货 / 股票数据源分流、天勤与富途账户切换、模拟账户、
  持仓线、预警线、二级报价和多布局状态同步继续完善。
- **文档**：VS Code 扩展更新到 **minibt-charts 0.3.11**：新增 desk 终端入口、
  天勤密码加密存储、连接体检与离线演示；安装命令和解释器自动探测保持可用。

### Changed

- `pylightcharts` 继续作为图表渲染依赖，最低要求保持 `>=0.1.5`
  （推荐安装最新 0.1.6，包含 panels / desk 资源更新）。
- 纯指标策略的输出按“是否真正发生交易”判断，不再按权益曲线是否水平判断。

### Fixed

- 修复本地图表 / 实时图表切换合约后旧指标、旧策略线、旧预警线残留。
- 修复本地策略回放时停止线越界、持仓线与成交次数统计不一致。
- 修复部分策略回测结果页 / 交易记录页为空但仍生成页签的问题。
- 修复富途股票行情订阅、账户切换与下单数量单位相关问题。
- 修复图表主题、副图分隔线、图例齿轮、指标 NaN 断点等显示问题。
- 修复 RL 特征预处理对 pandas 只读数组赋值失败（`assignment destination is read-only`）。
- 修复 RL 推理回测中收益曲线与时间索引长度不一致（`Length mismatch`）。
- 新增 RL 样本外改造基础设施：`fit_range` 训练区间归一化、独立 `eval_env`、
  `train/splits.py` 时间切分 / walk-forward。
- 新增 `train/metrics.py`：从权益曲线 / 收益率计算净收益、Sharpe、Sortino、
  最大回撤、Calmar 等验证指标。
- 新增验证集评分回调 `eval_score(env)`：可按净 Sharpe / 回撤选择最佳 checkpoint，
  默认仍使用累计 reward。
- 新增 `train/walk_forward.py`：`make_folds` / `run_walk_forward` 回调式 walk-forward 执行器。
- 新增 `train/ensemble.py`（多 seed 编排 / 动作聚合）与 `Strategy.rl_reset_index()`
  （fixed / random / incremental 起点）。
- 新增 `run_walk_forward_ensemble` / `runs_to_frame`：walk-forward × 多 seed 高层编排
  与结果表。
- 新增 `summarize_runs` / `save_runs_csv`：按 seed 汇总 walk-forward 指标并导出 CSV。
- 新增 `tutorials/elegantrl/08_walk_forward.py`：train / val / test 独立环境的一折示例；
  支持 `--all-folds` + `--seeds` + CSV 汇总。
- 新增 `tutorials/elegantrl/09_rl_ensemble.py`：多 seed actor 集成推理，
  同时评估单 actor / ensemble / 最佳 seed。
- 09 支持 `--csv` / `--report` / `--html`，导出单 actor 评估结果。
- 新增 `train/report.py`：Markdown walk-forward 报告；08 支持 `--report`。
- 报告新增 `best_seed` / `save_walk_forward_html`；08 支持 `--html`。
- `08_walk_forward.py` 支持全 fold / 多 seed / CSV / Markdown 报告。
- 08 会按 `--metric` 自动输出最佳 run / 最佳模型目录。
- 新增 `best_model_config` / `save_best_model`；08 支持 `--deploy` 复制最佳 actor。
- 新增 `load_best_actor`：从 `config.json` 恢复 actor / 架构并 eval。
- 新增 `tutorials/elegantrl/10_deploy_inference.py`：从部署目录复现 test 推理。
- 新增 `tutorials/elegantrl/11_rl_experiment.py`：RlExperiment / Bt 门面示例。
- 新增 `train/reward.py`：手续费 / 滑点 / 换手 / 回撤惩罚，03/05/06 已接入。
- 新增 `train/state.py`：仓位 / 持仓天数 / 浮盈 / 回撤 4 维状态，03/05/06 已接入。
- 新增 `train/small.py`：小样本小网络 / 离散动作 / 随机起点默认参数。
- 指标绘图设置审计：修正 `overlay` 拼写、TuLip/FinTa/TqTa/TA-Lib/BtInd
  等主图指标的 `overlap`，并隐藏 `thermo_long/short`、`signals` 等交易信号线。
- 修复 desk 布局管理：本地 / 实时布局按 `scope` 分开，布局行只显示布局 /
  合约 / 周期；应用多格布局时显式带上 `count`，避免只恢复成单图。
- 保存布局增加同名确认：同名布局需再次点击「确认替换」才覆盖，
  同一作用域内布局名称保持唯一。
- 修复本地布局恢复指标：布局里保存的 `pta_sma:sma` / `tv:X:trend`
  线条 key 先还原成目录基础 key 再计算，指标不再闪一下被清空。
- 修复实时图表多布局指标总加到格 1：工具栏 / 收藏 / 右键 / 键盘精灵
  统一按 `activeCell` 发送 `cell`，右键也先激活鼠标所在格。
- 修复 `AdaptiveTrendTrail` 等 TradingView 指标在 NaN 预热期的
  `RuntimeWarning`，并检查其它指标无同类警告；`Twin_Range_Filter`
  短数据不再越界。
- 指标全量推送只在历史未变时 `update(last)`，避免实时色带整段重绘闪烁。
- 指标增量更新与 K 线一致：同根只推 1 点；新 K 线至少推最后 2 点；
  断线重连按周期 / 时间差补缺口，缺口过大再全量重算。
- 新增 `minibt/elegantrl/REFACTOR_DETAILS.md`：样本外改造逐项原理与代码说明。
- 新增 `best_actor_path` / `restore_best_actor`：训练结束自动把验证最优 actor 覆盖为 `act.pth`。
- `Strategy._get_actor()` 优先加载 `act.pth`，避免 `find_pth_files()` 误选旧 checkpoint。
- 新增 `get_quant_feature_state` / `set_quant_feature_state`：08/09 的 val/test 复用 train 的 scaler / PCA / 异常值阈值 / 保留列。

### Packaging

- `pyproject.toml`、`minibt/__init__.py`、`README.md` 版本统一为 **1.3.3**。
- 新增包内发布资料：`CHANGELOG.md`、`RELEASE_NOTES.md`、`RELEASING.md`。
- `MANIFEST.in` 将上述资料纳入 sdist；wheel 仍只包含运行时包、数据与扩展模块。

> 1.3.3 的逐项修复（P44–P185、10-19 / 10-21 / 10-22 / 10-23 / 10-25 补充）
> 记录在 `minibt_docs/docs/changelog.md` 的 `[v1.3.3]` 一节。

## [1.3.2] - 2026-10-16

- `signal_backtest(gui=...)`、多策略权益 / 回撤对齐、`from_signals` 报表口径
  修复、`KLine.run` 的 `.ta` 竞态修复。

更早版本见 `minibt_docs/docs/changelog.md`。

<!-- build: mwbzjn05 -->
