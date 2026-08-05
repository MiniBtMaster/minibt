# MiniBT — 一站式量化交易策略开发库

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/minibt.svg)](https://pypi.org/project/minibt/)
[![Version](https://img.shields.io/badge/version-1.2.7-green.svg)](https://github.com/MiniBtMaster/minibt)

MiniBT 是一个覆盖量化交易**全流程**的 Python 开发库：从指标计算、策略编写、回测分析，到参数优化、K线回放、实盘交易，再到机器学习与强化学习，全部通过一套极简 API 打通。基于 Python 3.12+，MIT 许可证。

## ✨ 核心优势

- **🚀 极简开发**：约 20 行代码即可完成一个完整策略，无需关心底层细节，精力聚焦策略思想。
- **📊 指标即插即用**：内置 10+ 指标库（Pandas-TA、TA-Lib、TradingView、Tulip、FinTA、BtInd、TqTa、TqFunc、Factors、Pair 等），数千个指标一行调用。
- **⚡ 高性能回测**：信号级 Cython 快速回测 + 完整策略回测双引擎，回测/实盘同一套策略代码，零改写切换。
- **🎯 内置优化器**：网格搜索 / Optuna 贝叶斯优化，单目标 / 多目标 / 加权，收益、胜率、夏普、回撤等指标一键寻优。
- **🖥️ 可视化 & 回放**：Bokeh / LightChart 双图表，支持逐 K 线回放，直观观察信号与交易过程。
- **🤖 智能交易**：集成 ElegantRL 强化学习，让策略具备自适应能力。
- **🔗 实盘对接**：基于 TQSDK（天勤）无缝连接期货实盘，支持图表 / 后台串行 / 多进程并行三种部署模式。

## 📦 安装

```bash
pip install minibt
```

## 🚀 快速开始

一个完整的双均线交叉策略只需约 20 行：

```python
from minibt import *

class MA(Strategy):
    params = dict(length1=10, length2=20)

    def __init__(self):
        self.kline = self.get_kline(LocalDatas.test)          # 1. 加载数据（内置测试数据）
        self.ma1 = self.kline.close.sma(self.params.length1)  # 2. 计算指标
        self.ma2 = self.kline.close.sma(self.params.length2)
        self.long_signal = self.ma1.cross_up(self.ma2)       # 3. 定义信号：金叉/死叉
        self.short_signal = self.ma1.cross_down(self.ma2)

    def next(self):                                          # 4. 逐 K 线交易逻辑
        if not self.kline.position:
            if self.long_signal.new:
                self.kline.buy()
            elif self.short_signal.new:
                self.kline.sell()
        elif self.kline.position > 0 and self.short_signal.new:
            self.kline.sell()
        elif self.kline.position < 0 and self.long_signal.new:
            self.kline.buy()

if __name__ == "__main__":
    Bt().run()                                               # 5. 一键回测并出图
```

## 📖 重要功能

### 1. 指标即插即用

K线 / IndSeries / IndFrame 直接调用全部内置指标库，无需自写基础指标：

```python
rsi  = self.kline.close.rsi(14)                         # Pandas-TA 指标
macd = self.kline.close.MACD()                          # TA-Lib 指标
pmax = self.kline.close.btind.pmax3()                   # BtInd 指标
sma  = self.kline.close.tqfunc.sma(75, 0.02)            # TqFunc 指标
ut   = self.kline.tradingview.UT_Bot_Alerts()           # TradingView 指标（含信号）
```

### 2. 自定义指标 `BtIndicator`

继承 `BtIndicator`，在 `next()` 中计算并返回输出线，自动生成交易信号：

```python
class CCI(BtIndicator):
    params = dict(CCI_PERIOD=10, CCI_UPPER=100, CCI_LOWER=-100)
    isplot = dict(long_signal=False, short_signal=False)   # 控制显示

    def next(self):
        cci = self.close.cci(self.params.CCI_PERIOD)
        long_signal  = cci.cross_up(self.params.CCI_UPPER)
        short_signal = cci.cross_down(self.params.CCI_LOWER)
        return cci, long_signal, short_signal

class CCIStrategy(Strategy):
    def __init__(self):
        self.kline = self.get_kline(LocalDatas.pp2601_60)
        self.cci = CCI(self.kline)

    def next(self):
        if not self.kline.position:
            if self.cci.long_signal.new:
                self.kline.buy(stop=BtStop.SegmentationTracking)
            elif self.cci.short_signal.new:
                self.kline.sell(stop=BtStop.SegmentationTracking)

if __name__ == "__main__":
    Bt().run()
```

### 3. 信号快速回测 `signal_backtest`

指标内置信号回测引擎，无需编写策略即可评估，支持完整止损/止盈体系：

```python
ind = CCI(kline)   # 任意含 long_signal/short_signal 的指标

result = ind.signal_backtest(
    commission=1.0, com_type=1,
    sl_stop=0.01,   tp_stop=0.03,   stop_mode=2,    # 止损止盈（tick/金额/百分比三模式）
    sl_trail=1,                                      # 移动止损
    max_hold_bars=5,                                 # 持仓超时强平
    # sl_callback=my_sl, sl_callback_args=(...),    # 动态止损/止盈回调
    isplot=True, isreport=True,
)
result.pprint()    # 统计报告 + 资金曲线
```

### 4. 参数优化

策略级优化（网格 / Optuna 多目标加权）：

```python
if __name__ == "__main__":
    bt = Bt()
    bt.optstrategy(['profit', 'sharpe', 'max_drawdown'], (1., 1., 1.),
                   opconfig=OptunaConfig(n_trials=10), op_method='optuna',
                   len1=(5, 21, 1), len2=(10, 31, 1), a=(0.5, 3., 0.1))
    bt.run()
```

信号级优化（`OptimizeConfig`：单/多目标、网格/Optuna、加权）：

```python
config = OptimizeConfig(
    params={'length1': (5, 30, 2), 'length2': (30, 60, 2)},
    target=['max_drawdown', 'sharpe', 'win_rate'],
    weights=(-1.0, 3.0, 1.5),          # 回撤最小化、夏普与胜率最大化
    method='optuna', config={'n_trials': 100, 'sampler': 'TPESampler'},
)
result = ind.signal_backtest(optimize=config)
result.plot_optuna()
```

### 5. 自定义止损 `Stop`

继承 `Stop`，实现 `long()/short()` 即可打造 ATR 动态止损等任意止损逻辑：

```python
class ATRDynamicStop(Stop):
    def long(self):
        stop = self.low[-1] - self.atr_mult * self.kline.atr(14)[-1]
        # 写入多头止损价
        self.stop_price.new = stop
        # 写入多头止盈价
        self.target_price.new = self.kline.open_price + (self.kline.open_price - stop) * 2 
    def short(self):
        ...

BtStop.ATRDynamicStop = ATRDynamicStop      # 注册后即可在策略中使用
```

### 6. 多周期 K 线

`resample()` 一键切换周期，指标自动对齐：

```python
self.kline_1m = self.get_kline(LocalDatas.v2509_60)
self.kline_5m = self.kline_1m.resample(300)   # 1分钟 → 5分钟
self.ma_1m = self.kline_1m.close.sma(20)
self.ma_5m = self.kline_5m.close.sma(20)()   # 上采样回主周期
```

### 7. 多策略加载 `addstrategy`

支持策略类 / 模块名 / .py 路径 / 目录 / 包路径混合加载，并可传参：

```python
bt = Bt()
bt.addstrategy('cci', 'cmo')                          # 模块名自动发现
bt.addstrategy('./strategy/cci.py')                   # 文件路径
bt.addstrategy('strategy')                            # 目录批量加载
bt.addstrategy(MyStrategy.copy(params=dict(symbol="v2601_60")))  # 副本+参数
bt.run(gui=Gui.LightChart)
```

### 8. K 线回放 `replay`

逐 K 线推进回测，直观复现实时交易过程：

```python
class ReplayStrategy(Strategy):
    def __init__(self):
        self.kline = self.get_kline(LocalDatas.v2601_300)
        self.test = self.kline.tradingview.UT_Bot_Alerts()

    def next(self):
        if not self.kline.position:
            if self.test.long_signal.new:
                self.kline.buy(stop=BtStop.SegmentationTracking)
            elif self.test.short_signal.new:
                self.kline.sell(stop=BtStop.SegmentationTracking)

if __name__ == "__main__":
    Bt(replay=True).run(period_milliseconds=1000, gui=Gui.LightChart)
```

### 9. 实盘交易（TQSDK）

回测通过的策略，切换 `Bt(live=True)` 即可实盘，支持三种部署模式：

```python
bt = Bt(live=True)
bt.addstrategy(CCIStrategy, CMOStrategy)
bt.addTqapi(tq_auth=tq_auth(user_name="账号", password="密码"))

bt.run()                                   # 模式一：LightChart 实时图表
# bt.run(isplot=False)                     # 模式二：后台串行（低资源）
# bt.run(isplot=False, run_parallel=True)  # 模式三：多进程并行（互相隔离）
```

### 10. 机器学习 & 强化学习

集成 ElegantRL 强化学习，策略一行配置即可训练：

```python
class RLStrategy(Strategy):
    rl = True
    def start(self):
        self.set_model_params(
            agent=Agents.AgentDiscretePPO, if_discrete=True,
            train=True, break_step=1e6, state_dim=..., action_dim=...,
            auto_process_features=True,        # 自动处理指标特征
        )
    # 训练 / 回测 / 实盘统一由 Bt 调度
```

## 🔬 更多示例

完整示例见 [`tutorials/`](tutorials/) 目录：

| 功能                                            | 示例文件                                 |
| ----------------------------------------------- | ---------------------------------------- |
| 信号回测与止损止盈（20 种组合）                 | `signal_stop.py`                         |
| 信号级参数优化（网格/Optuna）                   | `signal_optimize.py`                     |
| 策略级参数优化                                  | `optstrategy.py`                         |
| 自定义止损（ATR 动态止损）                      | `stop.py`、`stop_params.py`              |
| K 线回放                                        | `strategy_replay.py`                     |
| 实盘三种模式                                    | `live_trading_modes.py`、`live_chart.py` |
| 多策略加载                                      | `load_strategies_from_dir.py`            |
| 指标交易逻辑                                    | `indicator_step.py`                      |
| 多指标策略                                      | `multi_indicator_strategies.py`          |
| 经典策略库（CCI/RSI/Hull/VPT/随机森林等 17 个） | `strategy/`                              |

## 📚 相关资源

- **在线教程**：[https://www.minibt.cn](https://www.minibt.cn)
- **GitHub**：[https://github.com/MiniBtMaster/minibt](https://github.com/MiniBtMaster/minibt)
- **PyPI**：[https://pypi.org/project/minibt/](https://pypi.org/project/minibt/)
- **作者**: owen | **邮箱**: 407841129@qq.com

## 📄 许可证

本项目采用 [MIT](LICENSE) 许可证。
