# 本地图表教程示例

这些文件配合 `minibt_docs/docs/minibt_desk/manual/13.17`–`13.21` 使用。
数据都是 minibt 内置的 `LocalDatas` 示例 CSV：

* `l2609_60`（DCE.l2609，1 分钟）
* `pp2609_60`（DCE.pp2609，1 分钟）

## 文件说明

| 文件 | 类型 | desk 里怎么用 |
| --- | --- | --- |
| `01_indicator_style.py` | `BtIndicator` | 本地图表 → 编辑器打开 → **加到图表**（纯指标，不交易） |
| `02_strategy_single.py` | `Strategy` | 加到图表 → 回放；或 **策略回测** |
| `03_strategy_pair.py` | `Strategy`（两合约） | 加到图表（自动左右两图）→ 回放；或 **策略回测** |
| `04_indicator_signal.py` | `BtIndicator` + 信号 | **策略回测** / **参数优化**（`signal_backtest`） |
| `05_indicator_pair.py` | `BtIndicator` + `pair_klines` | **策略回测** / **参数优化**（`pair_backtest`，保留两腿） |
| `06_optimize_strategy.py` | `Strategy` + `op_config` | **参数优化**（单合约 Strategy） |
| `07_optimize_pair_strategy.py` | `Strategy` + `op_config` | **参数优化**（配对 Strategy） |

## 运行

从仓库根目录运行，例如：

```bash
python tutorials/desk/local_chart/01_indicator_style.py
python tutorials/desk/local_chart/02_strategy_single.py
python tutorials/desk/local_chart/03_strategy_pair.py
```

`04` / `05` / `06` / `07` 的 `__main__` 会直接跑优化（`06` / `07` 是 30 trials，较慢）；如果只想
在 desk 里看，打开文件后点「策略回测」或「参数优化」即可。

> 参数优化文件（`06` / `07`）专门用于优化；做普通图表回放请用
> `02` / `03`，避免优化配置影响普通运行。
