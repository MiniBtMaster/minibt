# MiniBT — 一站式量化交易策略开发库

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/minibt.svg)](https://pypi.org/project/minibt/)
[![Version](https://img.shields.io/badge/version-1.3.4-green.svg)](https://github.com/MiniBtMaster/minibt)

MiniBT 是一个覆盖量化交易**全流程**的 Python 开发库：从指标计算、策略编写、回测分析，到参数优化、K线回放、实盘交易，再到机器学习与强化学习，全部通过一套极简 API 打通。基于 Python 3.12+，MIT 许可证。

## 🆕 v1.3.4 更新亮点

- **🖥️ minibt desk 多布局 / 多页面**：本地图表可以**多开**（本地图表1 / 2 / 3…，
  各自独立的指标与策略），一个页面只放一个策略；需要对比时用「复制当前页面」
  或**只读叠加**（只画线、不交易）；
- **🧠 计算搬到后台线程**：加载 `KalmanFilterStrategy` 这类重策略不再卡界面
  （先出 K 线 → 后台算指标线 → 算完自动上图）；收盘后自动挂起，不再空转；
- **📊 指标渲染对齐 TradingView**：`Chandelier_Exit` / `SuperTrend` 这类
  「一半 up 一半 dn」的指标按 `linebr` **断开缺口**；增量只推最后一点
  （实时色带不再闪）；
- **🖱️ 图表右键增强**：「我的模板 ▸ / 保存当前指标模板」、画线共用左侧导航条、
  画线按「合约|周期」本地持久化；
- **📓 Jupyter 支持**：`Gui.Desk` 在 notebook 里自动用 iframe 内嵌（不再弹 Qt
  卡死 kernel），`tutorials/plots/12~15` 四个示例开箱可用；
- **📦 依赖升级**：`pylightcharts>=0.1.7`。

v1.3.3 的主要更新（纯指标策略不再多出空回测页、desk 本地/实时图表策略链路、
`PlotInfo` 样式落地）见更新日志。

## ✨ 核心优势

- **🚀 极简开发**：约 20 行代码即可完成一个完整策略，无需关心底层细节，精力聚焦策略思想。
- **📊 指标即插即用**：内置 10+ 指标库（Pandas-TA、TA-Lib、TradingView、Tulip、FinTA、BtInd、TqTa、TqFunc、Factors、Pair 等），数千个指标一行调用。
- **⚡ 高性能回测**：信号级 Cython 快速回测 + 完整策略回测双引擎，回测/实盘同一套策略代码，零改写切换。
- **🎯 内置优化器**：网格搜索 / Optuna 贝叶斯优化，单目标 / 多目标 / 加权，收益、胜率、夏普、回撤等指标一键寻优。
- **🖥️ 可视化 & 回放**：**三个引擎 × 三种场景 = 九种模式** —— 引擎为 **Bokeh**（浏览器，纯 bokeh server）、**纯 pylightcharts**（原生窗口）、**pylightcharts_web**（浏览器 + SSE）；场景为**回测 / 回放 / 实时**，支持逐 K 线回放，直观观察信号与交易过程。
- **🤖 智能交易**：集成 ElegantRL 强化学习，让策略具备自适应能力。
- **🏷️ 逐点信号文本**：信号点可就地标注**不同文本**（支持多行），样式（字号 / 颜色 /
  行距 / 偏移 / 字体 / 底色 / 边框）**一套参数**在 bokeh 与 pylightcharts 两个图表上同时生效。
- **🔗 实盘对接**：基于 TQSDK（天勤）无缝连接期货实盘，支持图表 / 后台串行 / 多进程并行三种部署模式。

## 📦 安装

默认安装即为**全功能**（指标 / 回测 / 图表 / 参数优化 / 统计报告 / 实盘 / 强化学习）：

```bash
pip install minibt
```

> 全部重依赖（PyQt6、torch、tqsdk、quantstats 等）都采用**按需惰性 import**：
> 依赖会一并安装，但 `import minibt` 不会加载它们，启动时间仍保持在 **~1.2s**。

开发 / 打包额外工具：

```bash
pip install "minibt[dev]"
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
    Bt().run()          # 5. 一键回测并出图（默认 pylightcharts 原生窗口）
    # 想用 bokeh：Bt().run(gui=Gui.Bokeh)；网页版：gui=Gui.PylightchartsWeb

# ⚠️ Windows / macOS 上，入口脚本请带 main 保护（否则原生窗口起不来：
#    子进程会重新执行本脚本）。v1.3.0 起会自动回退到浏览器版并提示。
# if __name__ == '__main__':
#     Bt().run()
```

## 🖥️ minibt desk：一体化行情终端（1.3.4）

`minibt.desk` 是随 1.3.4 一起完善的桌面行情终端：**报价页 + 多标签看盘页 +
账户 / 交易 / 预警 / 回放 / 本地图表**都在同一个本地进程里，UI 由
`pylightcharts` 的 JS/TS 页面驱动，Python 只负责数据、策略和交易。

### 启动

```python
from minibt import Desk, tq_auth

desk = Desk(title='minibt桌面端', theme='dark')
desk.add_futures(tq_auth=tq_auth('天勤账号', '天勤密码'))  # 期货 / 快期模拟
desk.add_stocks()          # 股票：需要本机 FutuOpenD，默认 127.0.0.1:11111
desk.run()                 # 默认 Qt 桌面窗口
```

或者直接用命令行：

```bash
minibt desk --user 账号 --password 密码          # 期货 + 股票
minibt desk --user 账号 --password 密码 --no-stocks
minibt desk --offline                            # 不连网关，打开本地图表
minibt desk --browser                            # 浏览器壳（无 Qt 依赖）
minibt desk --check --json                       # 只体检连接 / 合约数量
```

富途网关**不需要账号**：只要本机打开并登录 FutuOpenD，就可以只看股票。
天勤 / 富途都没连上时，desk 会进入**离线本地图表**，不阻塞启动。

### 界面能力

| 模块 | 能力 |
| --- | --- |
| **报价页** | 期货 / 主连 / 指数 / 期权 / 股票 chips、交易所筛选、搜索、虚拟滚动报价表、sparkline、底部 Ticker；左键合约概览气泡、双击开图、右键周期菜单 |
| **看盘页** | 每个合约一个 tab，周期 / 6 种图表类型 / 指标工具栏、OHLC 行、LWC 主图 + 成交量、二级报价 5 档、持仓线、预警线、回放条 |
| **指标** | 完整指标目录（PandasTA / TuLip / 天勤TA / Pine / BtInd / TqFunc …）、搜索 / 收藏 / 模板、就地改参数、线型 / 线宽 / 颜色 / 价格线、主副图与共享副图 |
| **账户 / 交易** | 11 张账户指标卡、持仓 / 委托 / 成交 / 未成委托、多账户切换、期货与股票下单、平 / 反 / 全 / 撤、实盘二次确认、模拟账户 |
| **布局 / 回放** | 单图 / 左右两图 / 四图，每格独立合约与指标；布局保存 / 导入 / 导出；逐 K 线回放与多格联动 |
| **本地图表** | 直接加载本地 CSV，挂指标、策略、回测、参数优化；没有行情账号也能完整使用 |
| **对外集成** | `QtTransport` / `SseTransport` / `RestTransport` / `MockTransport`；`window.Desk.mountDesk(...)` 可嵌进任意网页；`minibt-charts` 在 VS Code 里打开 |

### 1.3.4 重点改进

- **多布局**：格 2..N 的 K 线 / 指标增量更新（数据变了才推）、持仓线 / 挂单线
  按格路由、换合约只换鼠标最后点击的那一格；加载策略时按合约数**保留多余格**，
  格数不足才自动加格（更小的布局在菜单里禁用）。
- **策略**：一个页面只放一个策略（重新加载先清上一个，布局 / 指标保留）；
  策略实盘可同时跑多个（一个文件一个子进程）；「策略管理」可改两个运行开关、
  查看 PID、删除；只读叠加在管理页里开关置灰（它不跑 next）。
- **指标**：缺口断线、增量只推最后一点、加不上的指标自动回滚并弹窗提示；
  指标 / 策略的计算放后台线程，界面不卡。
- **本地图表**：多开 + 每页独立（指标 / 策略按页存）、加载数据只加载 K 线、
  「复制当前页面」做 A/B 对比、只读叠加。
- **行情**：收盘后（末根超过 `max(10 分钟, 5 个周期)` 没更新）自动挂起策略计算，
  有新 K 线自动恢复；首页下方预览图严格按「K线」开关显示并自动重试空数据。
- **依赖**：`pylightcharts>=0.1.7`（desk 前端资源重建）。

## 📖 重要功能

### 1. 指标即插即用

K线 / IndSeries / IndFrame 直接调用全部内置指标库，无需自写基础指标：

```python
rsi  = self.kline.close.rsi(14)                         # Pandas-TA 指标
macd = self.kline.close.MACD()                          # TA-Lib 指标
pmax = self.kline.close.btind.pmax3()                   # BtInd 指标
sma  = self.kline.close.tqfunc.sma(75, 0.02)            # TqFunc 指标
ut   = self.kline.tradingview.UT_Bot_Alerts()           # TradingView 指标（含信号）

rsi  = self.kline.rsi(14,close = self.kline.open)       # 使用开盘价计算rsi指标（close 为默认）
atr  = self.kline.atr(14,high=_high,low=_low,close=_close)  # 使用其它最高最低价、收盘价计算atr指标
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
        # 方式一：将指标值赋值给 `lines`
        self.lines.cci = cci
        self.lines.long_signal = long_signal
        self.lines.short_signal = short_signal
        # 方式二：直接返回指标值
        # return cci, long_signal, short_signal

class CCIStrategy(Strategy):
    def __init__(self):
        self.kline = self.get_kline(LocalDatas.pp2609_60)
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

策略级优化有两种方式：

**方式一：策略类属性 `op_config`（推荐，最简洁）**

在策略类上定义 `op_config`，`Bt.run()` 会自动检测并执行优化，无需手动调用 `optstrategy()`：

```python
class MyStrategy(Strategy):
    params = dict(len1=10, len2=20, a=1.0)
    op_config = OpConfig(
        target=['profit', 'sharpe', 'max_drawdown'],
        weights=(1., 1., 1.),
        opconfig=OptunaConfig(n_trials=10),
        op_method='optuna',
        params={'len1': (5, 21, 1), 'len2': (10, 31, 1), 'a': (0.5, 3., 0.1)},
    )
    ...

if __name__ == "__main__":
    Bt().run()   # 自动识别 op_config，执行参数优化
```

**方式二：手动调用 `optstrategy()`**

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

    def __init__(self, atr_length: int = 14, atr_mult: float = 1.0):
        self.atr_length = atr_length
        self.atr_mult = atr_mult
        self.atr = self.kline.atr(self.atr_length)  

    def long(self):
        stop = self.low[-1] - self.atr_mult * self.atr[-1]
        # 写入多头止损价
        self.stop_price.new = stop
        # 写入多头止盈价
        self.target_price.new = self.kline.open_price + (self.kline.open_price - stop) * 2 
    def short(self):
        ...

BtStop.ATRDynamicStop = ATRDynamicStop      # 注册后即可在策略中使用
```

### 6. 多周期 K 线

`resample()` 一键切换周期，指标自动对齐（只适用于回测）：

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
mystrategy= MyStrategy.copy(params=dict(symbol="l2609_60"))
bt.addstrategy(mystrategy)  # 副本+参数
bt.run(gui=Gui.Pylightcharts)
```

### 8. K 线回放 `replay`

逐 K 线推进回测，直观复现实时交易过程：

```python
class ReplayStrategy(Strategy):
    def __init__(self):
        self.kline = self.get_kline(LocalDatas.test)
        self.test = self.kline.tradingview.UT_Bot_Alerts()

    def next(self):
        if not self.kline.position:
            if self.test.long_signal.new:
                self.kline.buy(stop=BtStop.SegmentationTracking)
            elif self.test.short_signal.new:
                self.kline.sell(stop=BtStop.SegmentationTracking)

if __name__ == "__main__":
    Bt(replay=True).run(period_milliseconds=1000, gui=Gui.Pylightcharts)
```

### 9. 实盘交易（TQSDK）

回测通过的策略，切换 `Bt(live=True)` 即可实盘，支持三种部署模式：

```python
bt = Bt(live=True)
bt.addstrategy(CCIStrategy, CMOStrategy)
bt.addTqapi(tq_auth=tq_auth(user_name="账号", password="密码"))

bt.run()                                   # 模式一：pylightcharts 实时图表（原生窗口）
# bt.run(isplot=False)                     # 模式二：后台串行（低资源）
# bt.run(isplot=False, run_parallel=True)  # 模式三：多进程并行（互相隔离）
```

### 10. 机器学习 & 强化学习

集成 ElegantRL 强化学习，策略一行配置即可训练：

```python
class RLStrategy(Strategy):
    rl = True  # 开启强化学习
    def __init__(self):
        # 初始化指标特征
        ...
        # 配置强化学习模型
        self.set_model_params(
            agent=Agents.AgentDiscretePPO, if_discrete=True,
            train=True, break_step=1e6, state_dim=..., action_dim=...,
            auto_process_features=True,        # 自动处理指标特征
        )

    def reset(self):
        # 重置强化学习模型
        ...
    
    def step(self):
        # 训练和测试强化学习模型
        ...
    # 训练 / 回测 / 实盘统一由 Bt 调度
```

## 🧩 VS Code 扩展：图表 + minibt desk（minibt-charts 0.3.11）

图表也能像代码文件一样开在 **VS Code 编辑器页签**里（回测 / 回放 / 实时都行）。
扩展**跟随策略里写的 gui**：`Gui.Bokeh` 用 bokeh（回放/实时是 bokeh server，
回测是自包含 HTML 快照），`Gui.Pylightcharts` / `Gui.PylightchartsWeb` 用
pylightcharts 网页版（本地 SSE + iframe 活图）—— 原生窗口嵌不进 VS Code，
会被换成**同一个渲染器**的网页版，图形完全一致；`btplot(...)` 一样跟随。

```bash
# 安装（在 minibt 仓库的 vscode-minibt/ 目录里打包，或下载现成的 .vsix）
npx --yes @vscode/vsce package
code --install-extension minibt-charts-0.3.11.vsix
```

也可以直接从市场装：VS Code 扩展面板搜 **`MiniBT Charts`**，或
[VS Marketplace](https://marketplace.visualstudio.com/items?itemName=MiniBtMaster.minibt-charts) /
[Open VSX](https://open-vsx.org/extension/MiniBtMaster/minibt-charts)（VSCodium / Gitpod 等）。

装好后**不必先配解释器**（`0.3.6` 起会自动挑一个装了 `minibt` / `pylightcharts`
的 Python：先看 `python.defaultInterpreterPath`，再试 `py -0p` 列出的各版本，
最后 `python` / `python3`，选第一个依赖齐的；只在都不行时才提示安装缺失模块）。
想固定某个解释器/工作目录时，再写工作区 `.vscode/settings.json`：

```jsonc
{ "minibt.pythonPath": ".venv/Scripts/python.exe", "minibt.cwd": "${workspaceFolder}" }
```

| 命令（`Ctrl+Shift+P` 搜 `MiniBT`） | 快捷键 | 作用 |
| --- | --- | --- |
| `在编辑器页运行策略图表` | `Ctrl+Alt+M` | 图表开在编辑器页签，实时/回放会持续刷新 |
| `显示策略日志（带进度）` | `Ctrl+Alt+L` | 日志页签，带进度条（认 `进度 x/y`、`xx%`） |
| `停止策略进程` / `刷新图表` | — | 结束子进程 / 重新加载图表 |
| `在浏览器中打开图表` | — | 用系统浏览器打开同一张图 |
| `MiniBT: 打开 MiniBT 看盘终端` | `Ctrl+Alt+D` | 在编辑器页打开 minibt desk（0.3.11 新增） |
| `MiniBT: 设置天勤密码（加密存储）` | — | 密码写入 VS Code `SecretStorage`，不写 settings.json |
| `MiniBT: 停止看盘终端` / `显示看盘日志` | — | 停止 desk 子进程 / 查看启动日志 |

编辑器标题栏里还会出现一个 **MiniBT 快速按钮**（K 线图标）—— 和 Pi Agent
Studio 一样，就排在 VS Code 原生「运行 ▾」按钮右边的**同一行**里，任何文件
都能看到，点它直接运行当前策略。

### minibt-charts 0.3.11：把 desk 开进 VS Code

0.3.11 新增 **「打开 MiniBT 看盘终端」**：扩展会启动
`python -m minibt desk --browser --json`，等待本地服务 `/healthz` 就绪后把
desk 页面嵌进编辑器页签。它和「在编辑器页运行策略图表」使用同一套
子进程 + 本地服务 + iframe 机制，不需要把 PyQt 窗口塞进 VS Code。

- **入口**：编辑器标题栏 🕯 图标 / 命令面板 / 状态栏「MiniBT 看盘」/ `Ctrl+Alt+D`；
- **启动体检**：有天勤账号 + 密码 → 期货 + 股票；没有天勤但 FutuOpenD 通 →
  只连股票；都没有 → 弹窗选择【输入天勤账号】【只连 Futu 股票】【进入离线演示】；
- **密码安全**：优先使用 VS Code `SecretStorage`，其次 `MINIBT_TQ_PASSWORD`，
  最后才是 `settings.json`；传给子进程走环境变量，不出现在命令行 / `ps` 里；
- **配置项**：`minibt.desk.account` / `password` / `futuHost` / `futuPort` /
  `stocks` / `offline` / `theme` / `autoStart` / `port`，全部有默认值；
- **状态栏**：点「MiniBT 看盘」可启动 / 停止常驻 desk；
- **修复**：浏览器壳 SSE 订阅、`/desk.js` 静态资源 404、VS Code 内不再弹系统浏览器、
  本地开发优先使用工作区里的 minibt 源码。

> ⚠️ **纯 pylightcharts 原生窗口无法嵌入 VS Code** —— 它是 PyQt6 + WebView2 的
> 独立操作系统窗口。扩展用的是**同一个渲染器**的网页版，图形完全一致；
> 需要原生窗口时照旧直接运行策略即可。

详见 [图表引擎与九种运行模式](https://www.minibt.cn/minibt_basic/1.29minibt_chart_modes/)
的「九、在 VS Code 里看图表」一节。

## 🔬 更多示例

完整示例见 [`tutorials/`](https://github.com/MiniBtMaster/minibt/tree/main/tutorials) 目录：

| 功能                                            | 示例文件                                 |
| ----------------------------------------------- | ---------------------------------------- |
| 信号回测与止损止盈（20 种组合）                 | `basic/signal_stop.py`                   |
| 信号级参数优化（网格/Optuna）                   | `basic/signal_optimize.py`               |
| 策略级参数优化                                  | `basic/optstrategy.py`                   |
| 自定义止损（ATR 动态止损）                      | `basic/stop.py`、`basic/stop_params.py`  |
| K 线回放                                        | `basic/strategy_replay.py`               |
| 实盘三种模式                                    | `basic/live_trading_modes.py`、`basic/live_chart.py` |
| 多策略加载                                      | `basic/load_strategies_from_dir.py`      |
| 指标交易逻辑                                    | `basic/indicator_step.py`                |
| 多指标策略                                      | `basic/multi_indicator_strategies.py`    |
| 经典策略库（CCI/RSI/Hull/VPT/随机森林等 17 个） | `strategies/`                            |
| 指标体系（12 个门面 / 自定义 / 字段 / 解包 / 回测 / 性能 / 共享副图） | `tutorials/indicators/`（见 `tutorials/indicators/README.md`） |

## 📚 相关资源

- **在线教程**：[https://www.minibt.cn](https://www.minibt.cn)
- **更新日志**：[包内 CHANGELOG](CHANGELOG.md) · [官网](https://www.minibt.cn/changelog/)
- **发布说明**：[1.3.4 RELEASE_NOTES](RELEASE_NOTES.md)
- **GitHub**：[https://github.com/MiniBtMaster/minibt](https://github.com/MiniBtMaster/minibt)
- **PyPI**：[https://pypi.org/project/minibt/](https://pypi.org/project/minibt/)
- **作者**: owen | **邮箱**: 407841129@qq.com

## 📄 许可证

本项目采用 [MIT](https://github.com/MiniBtMaster/minibt/blob/main/LICENSE) 许可证。
