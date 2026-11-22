# minibt 1.3.9 发布说明

**发布版本**：`1.3.9`
**发布日期**：2026-11-22
**Python**：>= 3.12（3.12 / 3.13 / 3.14 各一份 wheel）
**许可证**：MIT
**依赖**：`pylightcharts>=0.2.3`（desk 前端修复都在 0.2.3 里）

## 一句话

把原计划的 **1.3.9（文档轮）+ 1.3.10（三版本支持 / 指标库 / 交易系统）合并成一次发布**：
Python 3.13 / 3.14 支持、6 个 Rust 指标库 + 292 个 Alpha 因子、交易系统体系、
通达信本地数据接入，以及 desk 终端的一整轮修复。**Python 公共 API 零破坏**。

## 你能用到的新东西

### 1. Python 3.13 / 3.14（各一份 wheel）

- 三个 minor 各打一次 `python -m build --wheel` → `cp312` / `cp313` / `cp314`；
- **没编扩展也能跑**：`zigzag` 与 `signal_profit` 有纯 Python 兜底（逐值一致）；
- 统一入口 `minibt.cython_functions.load()`，缺扩展时给出可读提示；
- **3.13 阻断级 bug 已修**：指标加减比较改走 `operator` 函数表（PEP 667）。

### 2. 6 个 Rust 指标库（可选依赖，装了才出现在 desk）

| 门面 | 指标数 | Rust 包 |
| --- | --- | --- |
| `kline.ferro.*` | 225 | `ferro-ta` |
| `kline.tulip_rs.*` | 88 | `tulip-rs` |
| `kline.vta.*` | 209 | `vector-ta` |
| `kline.wickra.*` | 427 | `wickra` |
| `kline.kand.*` | 59 | `kand` |
| `kline.pta_rs.*` | 27 | `py-alpha-lib`（pandas_ta 的 Rust 版） |

另加 `kline.alpha.*`（py-alpha-lib）、**Alpha101 / Alpha191 共 292 因子**、
ZigZag 支撑阻力线等。API 参考：`minibt_docs/docs/minibt_api_reference/`。

### 3. 交易系统 `minibt.tradingsymtem`

`TradingSystemBase` 只出 `long_signal` / `short_signal`（不画指标线），
`TradingSystem` 门面按 10 分类暴露 **31 个系统**；底层按
`vector_ta → tulip_rs → pta_rs` 取数，desk 左栏有固定「交易系统」分组。

### 4. 通达信本地数据

`.day` / `.lc5` / `.lc1` 直接进 `get_kline()` 与 desk 本地图表
（设置 → 本地文件 → 通达信数据目录）。

### 5. desk 终端（配套 `pylightcharts 0.2.3`）

同合约多页彻底隔离、首页自选分组管理页、事件日历改用资讯中心数据、
「最近打开」按来源分流、编辑器临时文件 + 微信式另存、本地账户右键市价平仓、
回放退出平仓、参数优化进度、成交量分布价格轴修复…逐条见
[`CHANGELOG.md`](CHANGELOG.md) 与
[`minibt_docs/docs/changelog_simple.md`](../minibt_docs/docs/changelog_simple.md)。

## 安装 / 升级

```bash
python -m pip install -U minibt            # 按当前 Python 自动选 cpXXX wheel
python -m pip install -U "pylightcharts>=0.2.3"   # desk 前端
```

```bash
# 3.13 / 3.14 的 wheel 需要各自装
python -m pip install "minibt-1.3.9-cp313-cp313-win_amd64.whl"
```

## 产物与校验

| 文件 | 说明 |
| --- | --- |
| `minibt-1.3.9.tar.gz` | sdist（含 Cython 源码，可自行编 3.12 / 3.13 / 3.14）|
| `minibt-1.3.9-cp312-cp312-win_amd64.whl` | Windows / CPython 3.12 |
| `minibt-1.3.9-cp313-cp313-win_amd64.whl` | Windows / CPython 3.13（若本机有 3.13）|
| `minibt-1.3.9-cp314-cp314-win_amd64.whl` | Windows / CPython 3.14（若本机有 3.14）|
| `SHA256SUMS.txt` | 上面每个产物的 SHA256 |

```bash
python -m twine check dist/*
python scripts/check_dist_fresh.py minibt/dist/minibt-1.3.9.tar.gz --root minibt
```

## 已知边界

- `signal_backtest` / `bt_from_signals` **必须**有编译好的扩展；
  没有时会抛可读 `RuntimeError`（其余指标 / 回测 / desk 都能用）；
- 6 个 Rust 指标库与 `alpha` 都是**可选依赖**，没装时对应门面在 desk 里自动隐藏；
- `kand` 在 Python 3.14 上暂时**没有 wheel**（需本机 Rust 编），
  `pandas-ta` / `tulipy` 在 3.14 上同样需要现场编译（详见
  `scripts/check_dep_matrix.py` 的输出）。
