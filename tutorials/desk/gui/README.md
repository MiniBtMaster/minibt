# tutorials/desk/gui —— 用 `Gui.Desk` 把 minibt 接到 desk 界面

这些示例统一用 **`gui=Gui.Desk`**（等价 `gui='desk'`）：界面完全交给
minibt desk，minibt 只负责把「指标 / 策略」交过去。

| 文件 | 演示 | 在 desk 里看到 |
| --- | --- | --- |
| [`01_btplot_style.py`](01_btplot_style.py) | `btplot(gui=Gui.Desk)`（一行出图）+ 线颜色 / 线宽 | 本地图表 + 1 个指标 |
| [`02_btindicator_style.py`](02_btindicator_style.py) | `BtIndicator` 完整样式：颜色 / 虚线 / 线宽 / 主副图 / 买卖箭头 / `isplot` / `legend` | 本地图表 + 均线 + 箭头 |
| [`03_strategy_local_chart.py`](03_strategy_local_chart.py) | 策略「加到图表」（指标带样式） | 本地图表 + 策略线 + K 线 |
| [`04_backtest_local_chart.py`](04_backtest_local_chart.py) | 本地图表**策略回测** | 图表页 + 「回测」标签页 |
| [`05_optimize_local_chart.py`](05_optimize_local_chart.py) | 本地图表**参数优化**（Optuna） | 图表页 + 「优化」标签页 |
| [`06_live_single_shfe.py`](06_live_single_shfe.py) | 实时**单合约**（上期所主力 `SHFE.ag2612`） | 实时图表 + 真下单（快期模拟） |
| [`07_live_pair_shfe.py`](07_live_pair_shfe.py) | 实时**配对交易**（`SHFE.ag2612` / `SHFE.au2612`） | 实时图表左右两格 + 两条腿持仓 |
| [`08_live_multi_shfe.py`](08_live_multi_shfe.py) | 实时**多策略**（ag / au / cu 各 1 个策略） | **3 个**实时图表页 |

## 运行

```bash
# 1) 指标 / 策略 / 回测 / 优化（本地数据，离线可跑）
python tutorials/desk/gui/01_btplot_style.py
python tutorials/desk/gui/02_btindicator_style.py
python tutorials/desk/gui/03_strategy_local_chart.py
python tutorials/desk/gui/04_backtest_local_chart.py
python tutorials/desk/gui/05_optimize_local_chart.py

# 2) 实时（需要天勤账号；默认快期模拟盘 TqKq）
python tutorials/desk/gui/06_live_single_shfe.py --user 账号 --password 密码
python tutorials/desk/gui/07_live_pair_shfe.py  --user 账号 --password 密码
python tutorials/desk/gui/08_live_multi_shfe.py --user 账号 --password 密码

# 也可以用环境变量
set TQ_USER=账号
set TQ_PASS=密码
```

运行后会**弹出 desk 窗口**（Qt）。指标 / 策略示例不需要行情源；
实时示例会在 desk 里登录天勤并「加到图表」（真下单 → 请先用快期模拟）。

## 和 desk 里点按钮的对应关系

| minibt 一行 | desk 里等价的操作 |
| --- | --- |
| `ind.btplot(gui=Gui.Desk)` | 本地图表 → 打开 CSV → **加到图表** |
| `Bt(...).run(gui=Gui.Desk, desk_mode='chart')` | 本地图表 → **加到图表**（只挂策略） |
| `... desk_mode='backtest'` | **策略回测** 按钮 |
| `... desk_mode='optimize'` | **参数优化** 按钮 |
| `Bt(live=True).run(gui=Gui.Desk)` | 天勤登录 → 实时图表 → **加到图表**（每个策略一个页） |

## 样式能带到 desk 的部分

`BtIndicator` / 策略里的 PlotInfo：

* `LineStyle(line_color=…, line_width=…)` → 线颜色 / 线宽 ✅
* `line_dash=LineDash.dashed / dotdash / dotted` → 虚线 / 点划线 ✅
* `overlap=True/False` → 主图叠加 / 独立副图 ✅
* `signalstyle=SignalStyle(...)`（+ `set_label`）→ 买卖箭头 + 文字 ✅
* `isplot=dict(long_signal=False)` → 信号列只画箭头 ✅
* `legend=False` / `legend=dict(x=…False)` → 不进图例行 ✅
* `price_line / price_label` → 右侧价格线 / 价格标签 ✅

色带 `bandstyle`、统计表 `tablestyle`、水印 `watermark` 走 desk 的
**指标目录**路径：见 [`../indicators/style_zoo/`](../indicators/style_zoo/README.md)
与文档 13.21。

## 数据

指标 / 策略示例用 minibt 内置 `LocalDatas`：

* `l2609_60`（DCE.l2609，1 分钟）
* `pp2609_60`（DCE.pp2609，1 分钟）

`Gui.Desk` 会把它们写成 `~/.minibt/datas/<合约>_<周期>.csv`，
再让 desk 的本地图表加载（所以也能在 desk 里手动选到这些 CSV）。

实时示例用上期所主力合约：`SHFE.ag2612`（白银）、`SHFE.au2612`（黄金）、
`SHFE.cu2612`（铜）。换合约直接改脚本顶部的常量/参数即可
（`--symbol` / `--leg-a` / `--leg-b` 也行）。
