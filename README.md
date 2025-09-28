# minibt：让量化交易更简单、更高效的一站式策略开发库

<center>
<img src="https://pica.zhimg.com/v2-d5438d7502600aafdeb46d83c76dc865_l.jpg" 
  alt="minibt" 
  width="200" 
  class="center-img">
</center>

无论是量化新手还是资深开发者，minibt 都能帮你轻松搞定从策略搭建到实盘交易的全流程 —— 以极简的代码实现复杂逻辑，用强大的工具链提升策略效果。

## 核心优势一目了然：



*   **极简编码体验**：告别繁琐的底层实现，用简洁语法快速定义交易逻辑，让你的精力聚焦于策略思想而非代码细节。

*   **丰富指标即插即用**：内置 pandas\_ta、talib 等主流指标库，均线、MACD、RSI 等常用指标一键调用，无需重复造轮子。

*   **直观可视化分析**：集成 Bokeh 可视化工具，策略回测结果、资金曲线、信号分布等数据一键生成交互式图表，趋势洞察更清晰。

*   **无缝对接实盘**：支持 TQSDK 实盘接口，策略在回测通过后可快速切换至实盘交易，从研究到落地零门槛。

*   **智能优化升级**：内置参数优化工具与强化学习模块，自动迭代策略参数、动态适应市场变化，助力提升策略稳定性与收益潜力。

&emsp;&emsp;minibt，让量化交易的门槛更低、效率更高，无论是快速验证想法还是部署实盘策略，都是你的得力助手。

## 相关资源
知乎minibt量化教程专栏：[https://zhuanlan.zhihu.com/column/c_1942555756558783128](https://zhuanlan.zhihu.com/column/c_1942555756558783128)

minibt量化教程：[http://www.minibt.cn](https://www.minibt.cn) 或 [https://www.minibt.cn](https://www.minibt.cn)

github仓库：[https://github.com/MiniBtMaster/minibt](https://github.com/MiniBtMaster/minibt)

pypi仓库：[https://pypi.org/project/minibt/](https://pypi.org/project/minibt/)

# minibt 安装

## 一、环境要求

minibt 依赖以下基础环境，建议使用 Python 3.8 及以上版本（推荐 3.8 - 3.11 系列 ），可通过 `python --version` 检查当前环境版本 ：



*   **基础依赖**：`numpy`、`pandas` 用于数据处理；`PyQt5`（若使用可视化 UI 功能）、`qfluentwidgets`（UI 组件库 ）、`TA-Lib`/`pandas-ta`（指标计算相关 ）、`optuna`（参数优化 ）、`tqsdk`（若对接实盘 ）等。

## 二、安装方式

### （一）通过 pip 安装（推荐）



1.  **基础安装**

    打开终端（Windows 下为命令提示符或 PowerShell，Linux/Mac 下为终端 ），执行以下命令安装 minibt 核心包：



```python
pip install minibt
```

该命令会自动拉取 minibt 及其基础依赖（如 `numpy`、`pandas` 等 ），但部分特殊依赖（如 `TA-Lib` 需额外系统级依赖 ）需手动处理。

### （二）从源码安装（适合开发 / 定制）



1.  **克隆源码**

    从github项目仓库（`https://github.com/MiniBtMaster/minibt` ）或pypi仓库（`https://pypi.org/project/minibt`）下载安装minibt的whl文件



```python
python -m pip install 文件名.whl
```



## 三、验证安装

安装完成后，打开 Python 交互环境（终端执行 `python` 或 `ipython` ），输入：



```python
import minibt
print(minibt.__version__)
```

若输出 `1.0.4`（或对应版本号 ），且无导入错误，说明安装成功。

# minibt示例代码

## 一、**双均线交叉**量化策略
```python
from minibt import *  # 导入minibt核心功能（策略、指标、回测引擎等）

class MA(Strategy):  # 定义策略类，必须继承Strategy基类
    params = dict(
       length1=10,  # 短期均线周期（可通过参数优化调整）
       length2=20   # 长期均线周期（可通过参数优化调整）
   )
   def __init__(self):
       # 1. 加载数据：使用minibt内置测试数据（无需手动准备）
       self.data = self.get_data(LocalDatas.test) 
      
       # 2. 计算均线指标：基于收盘价计算SMA
       self.ma1 = self.data.close.sma(self.params.length1)  # 短期均线
       self.ma2 = self.data.close.sma(self.params.length2)  # 长期均线
      

       # 3. 生成交易信号：金叉（多头）、死叉（空头）
       self.long_signal = self.ma1.cross_up(self.ma2)  # 短期均线上穿长期均线
       self.short_signal = self.ma2.cross_down(self.ma1)  # 长期均线下穿短期均线
       
   def next(self):
       # next 方法：逐根K线处理核心逻辑，策略的“大脑”
       # 情况1：无持仓时，根据信号开仓
       if not self.data.position:  # position=0 表示空仓
           if self.long_signal.new:  # 金叉信号最新值
               self.data.buy()       # 开多仓
           elif self.short_signal.new:  # 死叉信号最新值
               self.data.sell()      # 开空仓
      
       # 情况2：持有多头时，死叉信号平仓
       elif self.data.position > 0 and self.short_signal.new: 
           self.data.sell()  # 平多仓
      
       # 情况3：持有空头时，金叉信号平仓
       elif self.data.position < 0 and self.long_signal.new: 
           self.data.buy()   # 平空仓

if __name__ == "__main__":
   # 初始化回测引擎：auto=True 自动处理数据加载、回测、可视化
   bt = Bt(auto=True) 
   bt.run()  # 启动回测，完成后自动弹出可视化界面
```

<center>
<img src="https://picx.zhimg.com/v2-539ddf5cbe7f0cb1d4b99b15d75628e5_1440w.jpg" 
  alt="minibt" 
  class="center-img">
</center>

## 二、极简指标展示
```python
from minibt import *
if __name__ == "__main__":
    BtData(LocalDatas.test.dataframe).run(
        ["ma1", Multiply(PandasTa.sma, dict(length=20))],
        ["ma2", Multiply(PandasTa.sma, dict(length=30))],
        ["ma3", Multiply(PandasTa.sma, dict(length=60))],
        ["ma4", Multiply(PandasTa.sma, dict(length=120))],
        ["ebsw", Multiply(PandasTa.ebsw)])
```

<center>
<img src="https://picx.zhimg.com/v2-271b0e9d30aedf5dfdd444088563bf51_1440w.jpg" 
  alt="minibt" 
  class="center-img">
</center>

## 三、参数优化配置
```python
if __name__ == "__main__":
    bt = Bt(auto=True)
    # 设置优化目标和参数范围
    bt.optstrategy(
        ["profit", "win_rate"],  # 优化目标：收益和胜率
        (1, 1),                  # 权重配置
        length1=(5, 15, 1),      # length1参数范围：5到15，步长为1
        length2=(20, 30, 1),     # length2参数范围：20到30，步长为1
        opconfig=OptunaConfig(n_trials=100)  # Optuna配置：100次试验
    )
    bt.run()
```

<center>
<img src="https://pic2.zhimg.com/v2-c92fecec6a4b7a750a5d6a49e9c3217f_1440w.jpg" 
  alt="minibt" 
  class="center-img">
</center>


## 四、多周期策略示例
```python
from minibt import *


class MultiTimeframeStrategy(Strategy):
    def __init__(self):
        # 主数据（1分钟）
        self.data_1m = self.get_data(LocalDatas.v2509_60)
        # 转换到5分钟数据
        self.data_5m = self.data_1m.resample(300)
        # 在不同周期上计算指标
        self.ma_1m = self.data_1m.close.sma(20)
        # 数据上采样
        self.ma_5m = self.data_5m.close.sma(20)()
        self.ma_5m.overlap = True
        # 交易信号
        self.long_signal = self.ma_1m.cross_up(self.ma_5m)
        self.short_signal = self.ma_1m.cross_down(self.ma_5m)

    def next(self):
        if not self.data_1m.position:
            # 多周期信号组合
            if self.long_signal.new:
                self.buy()
            elif self.short_signal.new:
                self.sell()
        elif self.data_1m.position > 0 and self.short_signal.new:
            self.sell()
        elif self.data_1m.position < 0 and self.long_signal.new:
            self.buy()


if __name__ == "__main__":
    Bt().run()
```

## 五、标准化接口，快速生成指标
minibt量化框架中所有指标和数据对象统一封装了指标与K线数据的共性能力，为子类（如 `Line`、`series`、`dataframe`、`BtData`）提供标准化接口

### 1. 多类型数据统一接口
- **Line**: 单值数据序列
- **series**: 一维数据序列（类似pandas.Series）
- **dataframe**: 多维数据表格（类似pandas.DataFrame）
- **BtData**: K线数据对象

### 2. 运算符重载体系
- 支持算术运算（`+`, `-`, `*`, `/` 等）
- 支持比较运算（`>`, `<`, `==` 等）
- 支持逻辑运算（`&`, `|` 等）
- 支持一元运算（`abs()`, `-x` 等）

### 3. 无缝Pandas兼容
- 自动将Pandas方法返回结果转换为框架内置类型
- 支持原生Pandas API调用
- 保持指标对象特性不被破坏

### 4. 多周期数据处理
- 支持上采样（upsample）
- 自动处理跨周期数据对齐
- 保持多周期数据的一致性

## 核心功能详解

### 1. 数据访问与操作

#### 基础属性访问
```python
# 获取数据值数组
values = indicator.values
# 获取数据形状（行数, 列数）
shape = indicator.shape
# 获取行数（时间步数量）
length = indicator.V  # 或 indicator.length
# 获取列数（特征维度）
columns = indicator.H
```

#### 索引访问
```python
# 支持多种索引方式
indicator[0]          # 第一行
indicator['close']    # close列（如果是dataframe）
indicator[10:20]      # 切片
indicator[[1, 3, 5]]  # 索引列表
```

#### 专用索引器
```python
# 基于位置的索引
indicator.iloc[0]        # 第一行
indicator.iloc[0:5]      # 前5行
indicator.iloc[0, 1]     # 第一行第二列

# 基于标签的索引
indicator.loc['close']   # close列
indicator.loc[0:5]       # 前5行

# 快速标量访问
indicator.at[0, 'close'] # 第一行的close值
indicator.iat[0, 1]      # 第一行第二列的值
```

### 2. 运算符重载

#### 算术运算
```python
# 基本算术运算
result = ma5 + ma10
result = close - open
result = volume * 2
result = close / open
# 原地运算
ma5 += 10
volume *= 1.5
```

#### 比较运算
```python
# 比较运算
signal = close > ma20
signal = volume >= volume.mean()
signal = rsi == 50
```

#### 逻辑运算
```python
# 逻辑运算
combined_signal = (close > ma20) & (volume > volume.mean())
either_signal = (rsi > 70) | (rsi < 30)
```

### 3. 数据处理与转换

#### 历史数据访问
```python
# 访问历史数据
current_value = indicator.new        # 当前值
current_value = indicator[0]         # 当前值
previous_value = indicator.prev      # 前一个值
previous_value = indicator[1]        # 前一个值
value_10_periods_ago = indicator.history(10)  # 10周期前的值
last_10_values = indicator.history(0, 10)     # 最近10个值
```

#### 数据填充
```python
# 生成填充数据
ones = indicator.ones        # 全1序列
zeros = indicator.zeros      # 全0序列
filled = indicator.full(100) # 填充指定值的序列
```

### 4. 多条件数据处理

#### ifs 方法
```python
# 多条件数据处理
signal = indicator.ifs(
    condition1, value1,    # 条件1满足时设为value1
    condition2, value2,    # 条件2满足时设为value2
    other=default_value    # 默认值
)

# 示例：生成交易信号
long_signal = price.ifs(
    price > ma20, 1,       # 价格上穿MA20时设为1
    price < ma10, 0,       # 价格下穿MA10时设为0
    other=0                # 默认值0（无信号）
)
```

### 5. 滚动窗口计算

#### 基本滚动计算
```python
# 滚动窗口计算
rolling_mean = indicator.rolling(window=20).mean()
rolling_std = indicator.rolling(window=20).std()
rolling_max = indicator.rolling(window=20).max()
```

#### 自定义滚动函数
```python
# 自定义滚动函数
def custom_roll_func(window_data):
    return window_data.max() - window_data.min()

rolling_range = indicator.rolling_apply(custom_roll_func, window=20)
```

### 6. 多周期处理

#### 上采样
```python
# 指标上采样
minute_data = indicator.upsample()  # 默认参数
minute_data = indicator()
```

#### 多指标并行计算
```python
# 多指标并行计算
result1, result2, result3 = indicator.multi_apply(
    [func1, params1],  # 第一个指标
    [func2, params2],  # 第二个指标
    [func3, params3]   # 第三个指标
)
```

### 7. 第三方指标库集成

```python
# 使用PandasTA指标
pandas_ta_result = indicator.pta.sma(length=20)

# 使用TA-Lib指标
talib_result = indicator.talib.RSI(timeperiod=14)

# 使用Tulip指标
tulip_result = indicator.tulip.wma(period=10)

# 使用内置指标
btind_result = indicator.btind.pmax(period=14, multiplier=3)

# 使用FinTa指标
finta_result = indicator.finta.SMA(period=20)

# 使用AutoTrader指标
autotrader_result = indicator.autotrader.supertrend()

# 使用天勤指标
tqfunc_result = indicator.tqfunc.barlast()

# 使用信号特征
signal_features = indicator.sf.Binarizer()

# 使用配对交易指标
pair_result = indicator.pairtrading.bollinger_bands()

# 使用因子分析
factors: pd.DataFrame
factor_result = indicator.factors.single_asset_multi_factor_strategy(*factors)
```

### 8. 绘图配置

#### 基本绘图设置
```python
# 设置指标名称
indicator.sname = "my_indicator"           #策略里面命名的变量名称
indicator.ind_name = "Custom Indicator"    #指标名称

# 设置绘图开关
indicator.isplot = True  # 全部显示
indicator.isplot = [True, False]  # 多线条分别设置
indicator.isplot = {"line1": True, "line2": False}  # 按线条名设置

# 设置主图叠加
indicator.overlap = True  # 全部叠加
indicator.overlap = [True, False]  # 多线条分别设置
indicator.overlap = {"line1": True, "line2": False}  # 按线条名设置

# 设置绘图高度
indicator.height = 200  # 像素
```

#### 水平线设置
```python
# 添加水平线
indicator.span_style = 50.0  # 单个水平线
indicator.span_style = [30.0, 70.0]  # 多个水平线
indicator.span_style = SpanStyle(  # 完整配置
    location=50.0,
    color="red",
    dash="dashed",
    width=2.0
)

# 分别设置水平线属性
indicator.span_location = [30.0, 70.0]  # 位置
indicator.span_color = ["red", "green"]  # 颜色
indicator.span_dash = ["solid", "dashed"]  # 线型
indicator.span_width = [1.0, 2.0]  # 宽度
```

### 9. 数据类型标识

```python
# 检查数据类型
is_indicator = indicator.isindicator  # 是否为指标
is_custom = indicator.iscustom        # 是否为自定义数据
is_mdim = indicator.isMDim            # 是否为多维数据
is_main = indicator.ismain            # 是否在主周期显示
is_resample = indicator.isresample    # 是否为转换数据
is_replay = indicator.isreplay        # 是否为回放数据
is_candles = indicator.iscandles      # 是否为蜡烛图
is_signal = indicator.issignal        # 是否包含交易信号
```

### 10. 策略关联

```python
# 获取关联的策略和数据
strategy = indicator.strategy_instance  # 关联的策略实例
bt_data = indicator.btdata             # 关联的K线数据

# 获取策略ID和索引
strategy_id = indicator.strategy_id    # 策略ID
plot_id = indicator.plot_id            # 绘图ID
data_id = indicator.data_id            # 数据ID
resample_id = indicator.resample_id    # 转换ID
replay_id = indicator.replay_id        # 回放ID

# 获取回测状态
current_index = indicator.btindex      # 当前回测索引
is_live = indicator.islivetrading      # 是否为实盘交易
```

## 使用示例

### 基本指标运算
```python
# 创建指标
ma5 = close.sma(5)
ma10 = close.sma(10)

# 指标运算
diff = ma10 - ma5
ratio = ma5 / ma10
signal = ma5 > ma10

# 组合条件
complex_signal = (ma5 > ma10) & (volume > volume.mean())
```

### 多周期策略
```python
# 多周期数据
data_5m = data.resample(60*5)  # 转换为5分钟周期
data_15m = data.resample(60*15)  # 转换为15分钟周期

# 多周期指标
ma_5m = data_5m.close.sma(20)
ma_15m = data_15m.close.sma(10)

# 多周期信号
long_term_bullish = ma_15m > ma_15m.shift(1)
short_term_bullish = ma_5m > ma_5m.shift(1)

entry_signal = long_term_bullish() & short_term_bullish
```

### 自定义指标
```python
# 使用btind_like创建自定义指标
custom_ind = indicator.btind_like(ma5)  # 创建与MA5结构相同的指标

# 手动计算指标值
for i in range(len(custom_ind)):
    custom_ind[i] = some_calculation(ma5[i], volume[i])
    
# 或者使用向量化操作
custom_ind[:] = ma5.values * 0.5 + volume.values * 0.01
```

### 交易信号生成
```python
# 使用ifs生成交易信号
entry_signal = price.ifs(
    (rsi < 30) & (price > bollinger_lower), 1,  # 超卖且价格在布林下轨上方
    (rsi > 70) | (price < bollinger_lower), 0,  # 超买或价格跌破布林下轨
    other=0  # 默认无信号
)

exit_signal = price.ifs(
    price < stop_loss, 1,  # 跌破止损线
    price > take_profit, 1,  # 涨破止盈线
    rsi > 80, 1,  # RSI超买
    other=0  # 默认无信号
)
```
## 指标构造器 BtIndicator

### 复杂指标示例（G-Channels）
```python
from minibt import *


class G_Channels(BtIndicator):
    """G-Channels指标 - 高效计算上下极值通道"""
    params = dict(length=144., cycle=1)
    overlap = True  # 主图叠加显示

    def next(self):
        length = self.params.length
        cycle = min(max(int(self.params.cycle), 1), 3)
        size = self.close.size
        a = np.full(size, np.nan)  # 上通道
        b = np.full(size, np.nan)  # 下通道
        close = self.close.values
        pre_a = 0.
        pre_b = 0.
        # 计算通道
        for i in range(size):
            if i and i % cycle == 0:
                a[i] = max(close[i], pre_a) - (pre_a - pre_b) / length
                b[i] = min(close[i], pre_b) + (pre_a - pre_b) / length
                pre_a = a[i]
                pre_b = b[i]
        # 周期大于1时进行插值
        if cycle > 1:
            a = pd.Series(a).interpolate(method="linear")
            b = pd.Series(b).interpolate(method="linear")
        # 计算中轨
        avg = (a + b) / 2.
        return a, b, avg  # 返回上轨、下轨、中轨


class MyStrategy(Strategy):
    def __init__(self):
        self.data = self.get_data(LocalDatas.v2509_60)
        self.data.height = 600
        self.G_Channels = G_Channels(self.data)
        self.G_Channels.a.line_style = LineStyle(
            LineDash.solid, 2, Colors.blue),     # 上轨样式
        self.G_Channels.b.line_style = LineStyle(
            LineDash.solid, 2, Colors.red),      # 下轨样式
        self.G_Channels.avg.line_style = LineStyle(
            LineDash.dotted, 3, Colors.gray)     # 中轨样式


if __name__ == "__main__":
    Bt().run()
```

<center>
<img src="https://pic3.zhimg.com/v2-169d274aa723107fadea8bb06e7eaf0e_1440w.jpg" 
  alt="minibt" 
  class="center-img">
</center>
