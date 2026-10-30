# tutorials/indicators —— 指标示例索引

这组示例对应文档 **第 8 章「指标」**：
[`minibt_docs/docs/minibt_indicators/`](../../minibt_docs/docs/minibt_indicators/)。

全部示例只使用包内数据（`LocalDatas.test` / `LocalDatas.pp2609_60` /
`LocalDatas.l2609_60`），**不需要联网、不需要账号、不会下单**。

## 先决条件

```bash
pip install "minibt[dev]"     # 或者 pip install -e .
```

从仓库根目录运行：

```bash
python tutorials/indicators/01_overview.py
```

Windows 终端如果是 GBK，建议先设置 UTF-8，避免个别输出字符显示失败：

```powershell
$env:PYTHONIOENCODING = "utf-8"      # PowerShell
set PYTHONIOENCODING=utf-8           # cmd
export PYTHONIOENCODING=utf-8         # bash
```

## 示例一览

| # | 文件 | 演示 | 文档 |
| --- | --- | --- | --- |
| 8.1 | [`01_overview.py`](01_overview.py) | 12 个指标门面、类名 / 方法数、同一 EMA 跨库对比 | [8.1](../../minibt_docs/docs/minibt_indicators/8.1_overview.md) |
| 8.2 | [`02_builtin.py`](02_builtin.py) | `kline.ta` 核心命名空间、`kline.btind`、返回 DataFrame vs IndFrame | [8.2](../../minibt_docs/docs/minibt_indicators/8.2_builtin.md) |
| 8.3 | [`03_pandasta.py`](03_pandasta.py) | PandasTa 的 `length` / `offset` / `fillna` / `lines` / Category | [8.3](../../minibt_docs/docs/minibt_indicators/8.3_pandasta.md) |
| 8.4 | [`04_talib.py`](04_talib.py) | TaLib 大写方法名、`timeperiod`、`MaType`、与 PandasTa 对比 | [8.4](../../minibt_docs/docs/minibt_indicators/8.4_talib.md) |
| 8.5 | [`05_tqta_tqfunc.py`](05_tqta_tqfunc.py) | 天勤 TqTa 指标与 TqFunc 函数（Pine 风格参数） | [8.5](../../minibt_docs/docs/minibt_indicators/8.5_tqta_tqfunc.md) |
| 8.6 | [`06_tulip_finta.py`](06_tulip_finta.py) | TuLip / FinTa 的大小写与 `period=` 参数 | [8.6](../../minibt_docs/docs/minibt_indicators/8.6_tulip_finta.md) |
| 8.7 | [`07_pair_factors.py`](07_pair_factors.py) | 价差上的 Pair 指标、Kalman 的二维要求、Factors 高阶工具 | [8.7](../../minibt_docs/docs/minibt_indicators/8.7_pair_factors.md) |
| 8.8 | [`08_pine.py`](08_pine.py) | Pine `ta.*` 风格：sma / rma / rsi / atr / barssince | [8.8](../../minibt_docs/docs/minibt_indicators/8.8_pine.md) |
| 8.9 | [`09_custom_indicator.py`](09_custom_indicator.py) | 从零写 `BtIndicator`：lines / params / overlap / bandstyle / signalstyle | [8.9](../../minibt_docs/docs/minibt_indicators/8.9_custom_indicator.md) |
| 8.10 | [`10_fields.py`](10_fields.py) | 换字段：`rsi(..., close=open)`、ATR 三字段、在均线 / 成交量上算 | [8.10](../../minibt_docs/docs/minibt_indicators/8.10_fields.md) |
| 8.11 | [`11_unpack.py`](11_unpack.py) | `a, b, c = ind` 解包、`to_lines()`、`to_ndarray()`、按列名取 | [8.11](../../minibt_docs/docs/minibt_indicators/8.11_unpack.md) |
| 8.12 | [`12_step_backtest.py`](12_step_backtest.py) | 指标内实现 `step()`，用 `ind.backtest()` 一行回测 | [8.12](../../minibt_docs/docs/minibt_indicators/8.12_step_backtest.md) |
| 8.13 | [`13_performance.py`](13_performance.py) | 首算 / 重复调用 / 数据长度 / 复用对象 | [8.13](../../minibt_docs/docs/minibt_indicators/8.13_performance.md) |
| 8.14 | [`14_shared_pane.py`](14_shared_pane.py) | 两个指标用同一个 `plotinfo.source` 合并副图 | [8.14](../../minibt_docs/docs/minibt_indicators/8.14_shared_pane.md) |

## 批量检查

```bash
for f in tutorials/indicators/*.py; do
    echo "== $f"
    python "$f" || exit 1
done
```

说明：`14_shared_pane.py` 最后会打开图表窗口查看共享副图效果；其余例子以打印
结果为主。若只想做无窗口冒烟，可先运行 01–13。

## 常见问题

| 现象 | 原因 / 处理 |
| --- | --- |
| `UnicodeEncodeError: 'gbk' codec ...` | Windows 终端编码不是 UTF-8；设置 `PYTHONIOENCODING=utf-8` |
| `AttributeError: 'FinTa' object has no attribute 'ema'` | FinTa 方法名大写（`EMA`），示例 06 用错误写法演示 |
| `kalman_filter ... data must be 2-dimensional` | Pair 的 Kalman 需要两列；示例 07 用单列价差演示这个限制 |
| `macd().backtest()` 报没有 `step` | 普通指标没有交易逻辑；示例 12 演示正确写法 |
| 图表窗口卡住 / 不出图 | 入口脚本需要 `if __name__ == '__main__':`；或改用 `btplot(display='auto')` |
