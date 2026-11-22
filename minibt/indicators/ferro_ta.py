"""**ferro** 指标库（第三方库，**可选依赖** ✓）

* 入口：`kline.ferro.<指标名>(...)`（前缀 `ferro_`）
* 数据源：调用它的 IndFrame 自己（`prices`→`close`、`high/low/open/volume`）
* 共 **225 个指标**；不支持的成员在 `NON_KLINE_INDICATORS` 里（desk 不显示）
* 生成：`scripts/gen_ext_libs.py`（**别手改本文件** ✓）
* docstring：`scripts/gen_ext_lib_docs.py` + `scripts/ext_lib_docs.json`

安装：`py -3.12 -m pip install ferro`
"""

from __future__ import annotations

from .base import tobtind
from ..signals import Compare, Threshold
from ..utils import Colors, LineDash, LineStyle
from ..utils import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_ import *
    from .core import *

#: 全部指标名（`batch()` / 文档用 ✓）
_INDICATOR_NAMES = ('AC', 'ACOS', 'AD', 'ADD', 'ADOSC', 'ADX', 'ADXR', 'ALLIGATOR', 'ALMA', 'AO', 'APO', 'AROON', 'AROONOSC', 'ASIN', 'ATAN', 'ATR', 'AVGPRICE', 'BBANDS', 'BBPERCENT', 'BBWIDTH', 'BETA', 'BOP', 'CCI', 'CDL2CROWS', 'CDL3BLACKCROWS', 'CDL3INSIDE', 'CDL3LINESTRIKE', 'CDL3OUTSIDE', 'CDL3STARSINSOUTH', 'CDL3WHITESOLDIERS', 'CDLABANDONEDBABY', 'CDLADVANCEBLOCK', 'CDLBELTHOLD', 'CDLBREAKAWAY', 'CDLCLOSINGMARUBOZU', 'CDLCONCEALBABYSWALL', 'CDLCOUNTERATTACK', 'CDLDARKCLOUDCOVER', 'CDLDOJI', 'CDLDOJISTAR', 'CDLDRAGONFLYDOJI', 'CDLENGULFING', 'CDLEVENINGDOJISTAR', 'CDLEVENINGSTAR', 'CDLGAPSIDESIDEWHITE', 'CDLGRAVESTONEDOJI', 'CDLHAMMER', 'CDLHANGINGMAN', 'CDLHARAMI', 'CDLHARAMICROSS', 'CDLHIGHWAVE', 'CDLHIKKAKE', 'CDLHIKKAKEMOD', 'CDLHOMINGPIGEON', 'CDLIDENTICAL3CROWS', 'CDLINNECK', 'CDLINVERTEDHAMMER', 'CDLKICKING', 'CDLKICKINGBYLENGTH', 'CDLLADDERBOTTOM', 'CDLLONGLEGGEDDOJI', 'CDLLONGLINE', 'CDLMARUBOZU', 'CDLMATCHINGLOW', 'CDLMATHOLD', 'CDLMORNINGDOJISTAR', 'CDLMORNINGSTAR', 'CDLONNECK', 'CDLPIERCING', 'CDLRICKSHAWMAN', 'CDLRISEFALL3METHODS', 'CDLSEPARATINGLINES', 'CDLSHOOTINGSTAR', 'CDLSHORTLINE', 'CDLSPINNINGTOP', 'CDLSTALLEDPATTERN', 'CDLSTICKSANDWICH', 'CDLTAKURI', 'CDLTASUKIGAP', 'CDLTHRUSTING', 'CDLTRISTAR', 'CDLUNIQUE3RIVER', 'CDLUPSIDEGAP2CROWS', 'CDLXSIDEGAP3METHODS', 'CEIL', 'CHAIKIN_VOL', 'CHANDELIER_EXIT', 'CHANDE_KROLL_STOP', 'CHANGE', 'CHO', 'CHOPPINESS_INDEX', 'CMF', 'CMO', 'COPPOCK', 'CORREL', 'COS', 'COSH', 'CROSS', 'CROSSOVER', 'CROSSUNDER', 'CRSI', 'DEMA', 'DIV', 'DMI', 'DONCHIAN', 'DPO', 'DX', 'ELDER_RAY', 'EMA', 'EMV', 'EXP', 'EXREM', 'FALLING', 'FISHER', 'FLIP', 'FLOOR', 'FORCE_INDEX', 'FRAMA', 'GATOR', 'HIGHEST', 'HISTORICAL_VOLATILITY', 'HT_DCPERIOD', 'HT_DCPHASE', 'HT_PHASOR', 'HT_SINE', 'HT_TRENDLINE', 'HT_TRENDMODE', 'HULL_MA', 'ICHIMOKU', 'KAMA', 'KELTNER_CHANNELS', 'KST', 'KVO', 'LINEARREG', 'LINEARREG_ANGLE', 'LINEARREG_INTERCEPT', 'LINEARREG_SLOPE', 'LN', 'LOG10', 'LOWEST', 'MA', 'MACD', 'MACDEXT', 'MACDFIX', 'MAMA', 'MASS', 'MAVP', 'MAX', 'MAXINDEX', 'MA_ENVELOPES', 'MCGINLEY', 'MEDIAN', 'MEDIAN_BANDS', 'MEDPRICE', 'MFI', 'MIDPOINT', 'MIDPRICE', 'MIN', 'MININDEX', 'MINUS_DI', 'MINUS_DM', 'MODE', 'MOM', 'MULT', 'NATR', 'NVI', 'NVI_WITH_EMA', 'OBV', 'OBV_SMOOTHED', 'PIVOT_POINTS', 'PLUS_DI', 'PLUS_DM', 'PO', 'PPO', 'PVI', 'PVI_WITH_SIGNAL', 'PVT', 'RISING', 'ROC', 'ROCP', 'ROCR', 'ROCR100', 'RSI', 'RVI', 'RVOL', 'RWI', 'SAR', 'SAREXT', 'SIN', 'SINH', 'SMA', 'SQRT', 'STARC', 'STC', 'STDDEV', 'STOCH', 'STOCHF', 'STOCHRSI', 'SUB', 'SUM', 'SUPERTREND', 'T3', 'TAN', 'TANH', 'TEMA', 'TRANGE', 'TRIMA', 'TRIX', 'TSF', 'TSI', 'TYPPRICE', 'ULCER_INDEX', 'ULTOSC', 'VAR', 'VIDYA', 'VOLOSC', 'VORTEX', 'VROC', 'VWAP', 'VWMA', 'WCLPRICE', 'WILLIAMS_FRACTALS', 'WILLR', 'WMA', 'ZLEMA')


class FerroTa:
    """## FerroTa —— ferro-ta 指标库（225 个指标）

    ferro-ta 是用 Rust 实现的 TA-Lib 兼容指标库，函数名与参数名沿用 TA-Lib，计算结果与 TA-Lib 基本一致。

    ### 📘 **原库文档**
    - https://pypi.org/project/ferro-ta/

    ### 入口与返回
    - 入口：`kline.ferro_ta.<指标名>(...)`（前缀 `ferro_ta_`）
    - 返回：`IndSeries`（单线）或 `IndFrame`（多线），索引与调用它的 K 线 / 指标对齐
    - 主图 / 副图：装饰器 `overlap=True` 的均线、通道类叠在主图，其余（振荡、量能、统计、形态）在副图

    ### 指标分类（共 225 个）
    **趋势（45）**：ADX、ADXR、ALLIGATOR、ALMA、AROON、AROONOSC、DEMA、DMI、DONCHIAN、DX、EMA、FRAMA、GATOR、HT_TRENDLINE、HT_TRENDMODE、HULL_MA、ICHIMOKU、KAMA …（共 45 个）
    **动量（31）**：AC、AO、APO、BOP、CCI、CMO、COPPOCK、CRSI、DPO、ELDER_RAY、FISHER、KST、MACD、MACDEXT、MACDFIX、MOM、PO、PPO …（共 31 个）
    **波动率（16）**：ATR、BBANDS、BBPERCENT、BBWIDTH、CHAIKIN_VOL、CHANDELIER_EXIT、CHANDE_KROLL_STOP、CHOPPINESS_INDEX、HISTORICAL_VOLATILITY、KELTNER_CHANNELS、MASS、MEDIAN_BANDS、NATR、STARC、TRANGE、ULCER_INDEX
    **成交量（19）**：AD、ADOSC、CHO、CMF、EMV、FORCE_INDEX、KVO、MFI、NVI、NVI_WITH_EMA、OBV、OBV_SMOOTHED、PVI、PVI_WITH_SIGNAL、PVT、RVOL、VOLOSC、VROC …（共 19 个）
    **形态（62）**：CDL2CROWS、CDL3BLACKCROWS、CDL3INSIDE、CDL3LINESTRIKE、CDL3OUTSIDE、CDL3STARSINSOUTH、CDL3WHITESOLDIERS、CDLABANDONEDBABY、CDLADVANCEBLOCK、CDLBELTHOLD、CDLBREAKAWAY、CDLCLOSINGMARUBOZU、CDLCONCEALBABYSWALL、CDLCOUNTERATTACK、CDLDARKCLOUDCOVER、CDLDOJI、CDLDOJISTAR、CDLDRAGONFLYDOJI …（共 62 个）
    **统计（26）**：ACOS、ADD、ASIN、ATAN、AVGPRICE、BETA、CHANGE、CORREL、HIGHEST、HT_DCPERIOD、HT_DCPHASE、HT_PHASOR、HT_SINE、LOWEST、MAX、MAXINDEX、MEDIAN、MIDPOINT …（共 26 个）
    **其他（26）**：CEIL、COS、COSH、CROSS、CROSSOVER、CROSSUNDER、DIV、EXP、EXREM、FALLING、FLIP、FLOOR、LN、LOG10、MEDPRICE、MULT、PIVOT_POINTS、RISING …（共 26 个）

    ### 使用说明
    1. 直接调用（返回框架内置指标，可直接画图 / 参与计算）：
    >>> rsi = self.data.rsi(period=14)      # 副图
    >>> ma = self.data.EMA(timeperiod=20)   # 主图叠加
    2. 取结果：
    >>> rsi.new           # 最新一根的值
    >>> rsi.prev          # 上一根的值
    >>> rsi[-20:]         # 最近 20 根（支持切片）
    3. 策略里可直接当条件用：
    >>> if rsi.new < 30:  # 超卖区，可再叠加其它指标过滤

    ### 注意事项
    - 周期类参数按「K 线根数」计，传 0 / 负数会被原库拒绝；参数留空则回落到默认值
    - 需要两条序列的指标（相关、协整、比较类）要显式传 `real1=` / `b=` 等第二序列
    - 本文件的 docstring 由 `scripts/gen_ext_lib_docs.py` 生成，**别手改**（改 `scripts/ext_lib_docs.json` 再跑脚本 ✓）
    - 可选依赖：没装本库时整个类自动消失，框架其余功能不受影响
    """
    _perfixes: str = "ferro_"
    _df: IndFrame | IndSeries

    def __init__(self, data):
        self._df = data
    @tobtind(lib="ferro", overlap=False, lines=['ac'])
    def AC(self, fastperiod: int = 5, slowperiod: int = 34, smoothperiod: int = 5, **kwargs) -> IndSeries:
        """加速震荡指标 · AC（动量）
        ---------
            加速震荡指标，等于动量指标AO减去AO的5期简单均线，用于提前捕捉动量转折。
            原库说明: Accelerator Oscillator: AO − SMA(AO, 5).

        参数:
        ---------
            >>> fastperiod (int): 快线周期. 默认: 5
            >>> slowperiod (int): 慢线周期. 默认: 34
            >>> smoothperiod (int): 计算周期（K 线根数）. 默认: 5

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ac

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.AC(fastperiod=5, slowperiod=34, smoothperiod=5)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.AC(high, low, fastperiod=5, slowperiod=34, smoothperiod=5)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['acos'])
    def ACOS(self, **kwargs) -> IndSeries:
        """反余弦 · ACOS（统计）
        ---------
            对输入逐元素取反余弦，输入需在[-1,1]之间，超出范围输出NaN，为数学变换工具。
            原库说明: Arc cosine (element-wise). Returns NaN outside [-1, 1].

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — acos

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ACOS()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ACOS(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['ad'])
    def AD(self, **kwargs) -> IndSeries:
        """佳庆累积派发线 · AD（成交量）
        ---------
            柴金累积/派发线，按收盘在当日区间的相对位置加权成交量并累加，衡量资金累积或派发。
            原库说明: Chaikin A/D Line.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ad

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.AD()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.AD(high, low, close, volume)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['add'])
    def ADD(self, real1=None, **kwargs) -> IndSeries:
        """逐元素相加 · ADD（统计）
        ---------
            对两个等长数组逐元素相加，属于通用数值运算工具而非技术指标。
            原库说明: Element-wise addition: real0 + real1.

        参数:
        ---------
            >>> real1 (值): 第二条价格序列（pd.Series / np.ndarray，长度与 K 线一致，必填）. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — add

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ADD(real1=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ADD(close, real1=None)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['adosc'])
    def ADOSC(self, fastperiod: int = 3, slowperiod: int = 10, **kwargs) -> IndSeries:
        """佳庆震荡指标 · ADOSC（成交量）
        ---------
            柴金A/D振荡器，为A/D线的快速与慢速EMA之差，正值示买盘积聚，负值示派发。
            原库说明: Chaikin A/D Oscillator.

        参数:
        ---------
            >>> fastperiod (int): 快线周期. 默认: 3
            >>> slowperiod (int): 慢线周期. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — adosc

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.ADOSC(fastperiod=3, slowperiod=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ADOSC(high, low, close, volume, fastperiod=3, slowperiod=10)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['adx'])
    def ADX(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """平均趋向指数 · ADX（趋势）
        ---------
            平均趋向运动指数，取值0至100，衡量趋势强度而非方向，数值越高趋势越明显。
            原库说明: Average Directional Movement Index.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — adx

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.ADX(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ADX(high, low, close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['adxr'])
    def ADXR(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """平均趋向指数评级 · ADXR（趋势）
        ---------
            ADX的评级值，取当前ADX与若干周期前ADX的均值，用于平滑并确认趋势强度。
            原库说明: Average Directional Movement Index Rating.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — adxr

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.ADXR(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ADXR(high, low, close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['alligator_1', 'alligator_2', 'alligator_3'])
    def ALLIGATOR(self, jaw_period: int = 13, jaw_shift: int = 8, teeth_period: int = 8, teeth_shift: int = 5, lips_period: int = 5, lips_shift: int = 3, **kwargs) -> IndFrame:
        """鳄鱼线 · ALLIGATOR（趋势）
        ---------
            比尔·威廉姆斯的鳄鱼线，对中价用不同周期的SMMA并向前位移，形成三条趋势线。
            原库说明: Bill Williams Alligator (jaw, teeth, lips).

        参数:
        ---------
            >>> jaw_period (int): 计算周期（K 线根数）. 默认: 13
            >>> jaw_shift (int): 平移根数. 默认: 8
            >>> teeth_period (int): 计算周期（K 线根数）. 默认: 8
            >>> teeth_shift (int): 平移根数. 默认: 5
            >>> lips_period (int): 计算周期（K 线根数）. 默认: 5
            >>> lips_shift (int): 平移根数. 默认: 3

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — alligator_1, alligator_2, alligator_3

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.ALLIGATOR(jaw_period=13, jaw_shift=8, teeth_period=8, teeth_shift=5, lips_period=5, lips_shift=3)    # 主图叠加
            >>> out.columns               # 线名: alligator_1, alligator_2, alligator_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ALLIGATOR(high, low, jaw_period=13, jaw_shift=8, teeth_period=8, teeth_shift=5, lips_period=5, lips_shift=3)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['alma'])
    def ALMA(self, timeperiod: int = 14, offset: int = 0, sigma: float = 6.0, **kwargs) -> IndSeries:
        """阿诺勒古移动平均 · ALMA（趋势）
        ---------
            高斯加权移动平均，峰值位置与宽度可调，平滑同时减少滞后，常用于趋势与信号线。
            原库说明: Arnaud Legoux Moving Average.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> offset (int): 中心偏移（0~1，越大越靠右）. 默认: 0
            >>> sigma (float): 高斯平滑宽度（越大越平滑）. 默认: 6.0

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — alma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ALMA(timeperiod=14, offset=0, sigma=6.0)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ALMA(close, timeperiod=14, offset=0, sigma=6.0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['ao'])
    def AO(self, fastperiod: int = 5, slowperiod: int = 34, **kwargs) -> IndSeries:
        """动量震荡指标 · AO（动量）
        ---------
            动量震荡指标，用中价5期与34期简单均线之差衡量动量，零轴穿越提示方向转换。
            原库说明: Awesome Oscillator: SMA(median, 5) − SMA(median, 34).

        参数:
        ---------
            >>> fastperiod (int): 快线周期. 默认: 5
            >>> slowperiod (int): 慢线周期. 默认: 34

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ao

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.AO(fastperiod=5, slowperiod=34)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.AO(high, low, fastperiod=5, slowperiod=34)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['apo'])
    def APO(self, fastperiod: int = 12, slowperiod: int = 26, matype: int = 0, **kwargs) -> IndSeries:
        """绝对价格振荡器 · APO（动量）
        ---------
            绝对价格振荡器，为快慢两条移动平均之差，反映价格动量的方向与强弱。
            原库说明: Absolute Price Oscillator.

        参数:
        ---------
            >>> fastperiod (int): 快线周期. 默认: 12
            >>> slowperiod (int): 慢线周期. 默认: 26
            >>> matype (int): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 0

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — apo

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.APO(fastperiod=12, slowperiod=26, matype=0)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.APO(close, fastperiod=12, slowperiod=26, matype=0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['aroon_down', 'aroon_up'])
    def AROON(self, timeperiod: int = 25, **kwargs) -> IndFrame:
        """阿隆指标 · AROON（趋势）
        ---------
            阿隆指标，输出下跌线与上涨线，依据距最高价与最低价的周期数衡量趋势方向与强度。
            原库说明: Aroon.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 25

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — aroon_down, aroon_up

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.AROON(timeperiod=25)    # 副图
            >>> out.columns               # 线名: aroon_down, aroon_up
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.AROON(high, low, timeperiod=25)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['aroonosc'])
    def AROONOSC(self, timeperiod: int = 25, **kwargs) -> IndSeries:
        """阿隆振荡器 · AROONOSC（趋势）
        ---------
            阿隆振荡器，为阿隆上涨线与下跌线之差，正值偏多、负值偏空，用于判断趋势。
            原库说明: Aroon Oscillator.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 25

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — aroonosc

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.AROONOSC(timeperiod=25)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.AROONOSC(high, low, timeperiod=25)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['asin'])
    def ASIN(self, **kwargs) -> IndSeries:
        """反正弦 · ASIN（统计）
        ---------
            对输入逐元素取反正弦，输入需在[-1,1]之间，超出范围输出NaN，为数学变换工具。
            原库说明: Arc sine (element-wise). Returns NaN outside [-1, 1].

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — asin

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ASIN()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ASIN(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['atan'])
    def ATAN(self, **kwargs) -> IndSeries:
        """反正切 · ATAN（统计）
        ---------
            对输入逐元素取反正切，属通用数学变换，可用于压缩数值取值范围。
            原库说明: Arc tangent (element-wise).

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — atan

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ATAN()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ATAN(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['atr'])
    def ATR(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """平均真实波幅 · ATR（波动率）
        ---------
            平均真实波幅，对真实波幅做平滑，衡量价格波动幅度，常用于止损和仓位管理。
            原库说明: Average True Range.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — atr

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.ATR(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ATR(high, low, close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['avgprice'])
    def AVGPRICE(self, **kwargs) -> IndSeries:
        """平均价 · AVGPRICE（统计）
        ---------
            平均价格，取开盘、最高、最低、收盘四价之和的四分之一，作为单根K线的代表价。
            原库说明: Average Price: (Open + High + Low + Close) / 4.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — avgprice

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.AVGPRICE()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.AVGPRICE(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['upper', 'middle', 'lower'])
    def BBANDS(self, timeperiod: int = 20, nbdevup: float = 2.0, nbdevdn: float = 2.0, matype: int = 0, **kwargs) -> IndFrame:
        """布林带 · BBANDS（波动率）
        ---------
            布林带，中轨为移动平均，上下轨按同窗口标准差偏移，用于衡量波动与超买超卖。
            原库说明: Bollinger Bands.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 20
            >>> nbdevup (float): 上轨标准差倍数. 默认: 2.0
            >>> nbdevdn (float): 下轨标准差倍数. 默认: 2.0
            >>> matype (int): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 0

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — upper, middle, lower

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.BBANDS(timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0)    # 主图叠加
            >>> out.columns               # 线名: upper, middle, lower
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.BBANDS(close, timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['bbpercent'])
    def BBPERCENT(self, timeperiod: int = 14, nbdevup: float = 2.0, nbdevdn: float = 2.0, **kwargs) -> IndSeries:
        """布林百分比B · BBPERCENT（波动率）
        ---------
            布林%B，用收盘价相对上下轨位置计算，0为下轨、1为上轨，衡量价格在带中的位置。
            原库说明: Bollinger %B — ``(close - lower) / (upper - lower)``.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> nbdevup (float): 上轨标准差倍数. 默认: 2.0
            >>> nbdevdn (float): 下轨标准差倍数. 默认: 2.0

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — bbpercent

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.BBPERCENT(timeperiod=14, nbdevup=2.0, nbdevdn=2.0)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.BBPERCENT(close, timeperiod=14, nbdevup=2.0, nbdevdn=2.0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['bbwidth'])
    def BBWIDTH(self, timeperiod: int = 14, nbdevup: float = 2.0, nbdevdn: float = 2.0, **kwargs) -> IndSeries:
        """布林带宽 · BBWIDTH（波动率）
        ---------
            布林带宽，为上下轨之差除以中轨，数值收窄常示盘整，扩张示波动放大。
            原库说明: Bollinger Bandwidth — ``(upper - lower) / middle``.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> nbdevup (float): 上轨标准差倍数. 默认: 2.0
            >>> nbdevdn (float): 下轨标准差倍数. 默认: 2.0

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — bbwidth

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.BBWIDTH(timeperiod=14, nbdevup=2.0, nbdevdn=2.0)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.BBWIDTH(close, timeperiod=14, nbdevup=2.0, nbdevdn=2.0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['beta'])
    def BETA(self, real1=None, timeperiod: int = 14, **kwargs) -> IndSeries:
        """贝塔 · BETA（统计）
        ---------
            滚动回归斜率，衡量资产0相对资产1的敏感度，用于评估相对走势与系统性风险。
            原库说明: Beta — regression slope of real0 relative to real1.

        参数:
        ---------
            >>> real1 (值): 第二条价格序列（pd.Series / np.ndarray，长度与 K 线一致，必填）. 默认: None
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — beta

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.BETA(real1=None, timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.BETA(close, real1=None, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['bop'])
    def BOP(self, **kwargs) -> IndSeries:
        """均势指标 · BOP（动量）
        ---------
            均势指标，用收盘与开盘之差除以最高最低之差，取值-1至1，反映买卖双方力量。
            原库说明: Balance Of Power.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — bop

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.BOP()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.BOP(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cci'])
    def CCI(self, timeperiod: int = 20, **kwargs) -> IndSeries:
        """顺势指标 · CCI（动量）
        ---------
            顺势指标，衡量典型价格偏离其移动平均的程度，用于识别超买超卖与周期反转。
            原库说明: Commodity Channel Index.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cci

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.CCI(timeperiod=20)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CCI(high, low, close, timeperiod=20)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdl2crows'])
    def CDL2CROWS(self, **kwargs) -> IndSeries:
        """两只乌鸦 · CDL2CROWS（形态）
        ---------
            两只乌鸦形态，三根K线组成的看跌反转形态，识别时输出-100，否则为0。
            原库说明: Two Crows — bearish 3-candle reversal pattern.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdl2crows

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDL2CROWS()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDL2CROWS(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdl3blackcrows'])
    def CDL3BLACKCROWS(self, **kwargs) -> IndSeries:
        """三只黑乌鸦 · CDL3BLACKCROWS（形态）
        ---------
            三只黑乌鸦，三根连续长阴线且逐级开在前实体内的看跌反转形态，检测输出-100。
            原库说明: Three Black Crows — bearish 3-candle reversal.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdl3blackcrows

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDL3BLACKCROWS()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDL3BLACKCROWS(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdl3inside'])
    def CDL3INSIDE(self, **kwargs) -> IndSeries:
        """三内升/降 · CDL3INSIDE（形态）
        ---------
            三内升/降，孕线加确认K线的三K形态，看涨输出100，看跌输出-100。
            原库说明: Three Inside Up/Down — harami followed by confirmation candle.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdl3inside

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDL3INSIDE()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDL3INSIDE(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdl3linestrike'])
    def CDL3LINESTRIKE(self, **kwargs) -> IndSeries:
        """三线打击 · CDL3LINESTRIKE（形态）
        ---------
            三线打击，四根K线组成的反转形态，看涨输出100，看跌输出-100，否则为0。
            原库说明: Three-Line Strike — 4-candle reversal pattern.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdl3linestrike

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDL3LINESTRIKE()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDL3LINESTRIKE(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdl3outside'])
    def CDL3OUTSIDE(self, **kwargs) -> IndSeries:
        """三外升/降 · CDL3OUTSIDE（形态）
        ---------
            三外升/降，吞没形态加确认K线，看涨输出100，看跌输出-100，否则为0。
            原库说明: Three Outside Up/Down — engulfing followed by confirmation candle.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdl3outside

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDL3OUTSIDE()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDL3OUTSIDE(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdl3starsinsouth'])
    def CDL3STARSINSOUTH(self, **kwargs) -> IndSeries:
        """南方三星 · CDL3STARSINSOUTH（形态）
        ---------
            南方三星，三根K线组成的看涨反转形态，识别时输出100，否则为0。
            原库说明: Three Stars In The South — 3-candle bullish reversal.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdl3starsinsouth

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDL3STARSINSOUTH()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDL3STARSINSOUTH(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdl3whitesoldiers'])
    def CDL3WHITESOLDIERS(self, **kwargs) -> IndSeries:
        """三白兵 · CDL3WHITESOLDIERS（形态）
        ---------
            三白兵，三根连续长阳线且逐级开在前实体内的看涨反转形态，检测输出100。
            原库说明: Three White Soldiers — bullish 3-candle reversal.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdl3whitesoldiers

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDL3WHITESOLDIERS()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDL3WHITESOLDIERS(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlabandonedbaby'])
    def CDLABANDONEDBABY(self, **kwargs) -> IndSeries:
        """弃婴形态 · CDLABANDONEDBABY（形态）
        ---------
            弃婴形态，中间为跳空十字星的三K反转形态，看涨输出100，看跌输出-100。
            原库说明: Abandoned Baby — 3-candle reversal with gapping doji in the middle.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlabandonedbaby

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLABANDONEDBABY()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLABANDONEDBABY(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdladvanceblock'])
    def CDLADVANCEBLOCK(self, **kwargs) -> IndSeries:
        """大敌当前 · CDLADVANCEBLOCK（形态）
        ---------
            大敌当前，三根阳线但动能递减，提示上涨乏力，识别时输出-100。
            原库说明: Advance Block — 3 bullish candles with weakening momentum, bearish
                warning.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdladvanceblock

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLADVANCEBLOCK()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLADVANCEBLOCK(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlbelthold'])
    def CDLBELTHOLD(self, **kwargs) -> IndSeries:
        """捉腰带线 · CDLBELTHOLD（形态）
        ---------
            捉腰带线，单根开盘于极值并带长实体的K线，看涨输出100，看跌输出-100。
            原库说明: Belt-hold — single candle opening at extreme with long body.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlbelthold

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLBELTHOLD()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLBELTHOLD(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlbreakaway'])
    def CDLBREAKAWAY(self, **kwargs) -> IndSeries:
        """脱离形态 · CDLBREAKAWAY（形态）
        ---------
            脱离形态，五根K线组成的反转形态，看涨输出100，看跌输出-100，否则为0。
            原库说明: Breakaway — 5-candle reversal pattern.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlbreakaway

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLBREAKAWAY()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLBREAKAWAY(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlclosingmarubozu'])
    def CDLCLOSINGMARUBOZU(self, **kwargs) -> IndSeries:
        """收盘光头光脚线 · CDLCLOSINGMARUBOZU（形态）
        ---------
            收盘光头光脚线，收盘侧无影线的大实体K线，看涨输出100，看跌输出-100。
            原库说明: Closing Marubozu — candle with no shadow on the closing side.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlclosingmarubozu

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLCLOSINGMARUBOZU()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLCLOSINGMARUBOZU(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlconcealbabyswall'])
    def CDLCONCEALBABYSWALL(self, **kwargs) -> IndSeries:
        """藏婴吞没 · CDLCONCEALBABYSWALL（形态）
        ---------
            藏婴吞没，四根K线组成的看涨反转形态，识别时输出100，否则为0。
            原库说明: Concealing Baby Swallow — 4-candle bullish reversal.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlconcealbabyswall

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLCONCEALBABYSWALL()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLCONCEALBABYSWALL(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlcounterattack'])
    def CDLCOUNTERATTACK(self, **kwargs) -> IndSeries:
        """反击线 · CDLCOUNTERATTACK（形态）
        ---------
            反击线，两根相反方向但收盘价相同的K线形态，看涨输出100，看跌输出-100。
            原库说明: Counterattack Lines — 2-candle pattern with opposite candles closing at
                same price.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlcounterattack

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLCOUNTERATTACK()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLCOUNTERATTACK(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdldarkcloudcover'])
    def CDLDARKCLOUDCOVER(self, **kwargs) -> IndSeries:
        """乌云盖顶 · CDLDARKCLOUDCOVER（形态）
        ---------
            乌云盖顶，两根K线组成的看跌反转形态，识别时输出-100，否则为0。
            原库说明: Dark Cloud Cover — 2-candle bearish reversal.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdldarkcloudcover

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLDARKCLOUDCOVER()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLDARKCLOUDCOVER(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdldoji'])
    def CDLDOJI(self, **kwargs) -> IndSeries:
        """十字星 · CDLDOJI（形态）
        ---------
            十字星，开盘价与收盘价接近，反映市场犹豫不决，识别时输出100，否则为0。
            原库说明: Doji — open ≈ close, reflecting market indecision.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdldoji

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLDOJI()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLDOJI(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdldojistar'])
    def CDLDOJISTAR(self, **kwargs) -> IndSeries:
        """十字星线 · CDLDOJISTAR（形态）
        ---------
            十字星线，跳空脱离前一根长实体的十字星，看涨输出100，看跌输出-100。
            原库说明: Doji Star — doji that gaps away from the prior large candle.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdldojistar

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLDOJISTAR()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLDOJISTAR(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdldragonflydoji'])
    def CDLDRAGONFLYDOJI(self, **kwargs) -> IndSeries:
        """蜻蜓十字 · CDLDRAGONFLYDOJI（形态）
        ---------
            蜻蜓十字，带长下影线的十字星形态，识别时输出100，否则为0。
            原库说明: Dragonfly Doji — doji with long lower shadow.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdldragonflydoji

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLDRAGONFLYDOJI()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLDRAGONFLYDOJI(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlengulfing'])
    def CDLENGULFING(self, **kwargs) -> IndSeries:
        """吞没形态 · CDLENGULFING（形态）
        ---------
            吞没形态，后一根实体完全包住前一根实体，看涨输出100，看跌输出-100。
            原库说明: Engulfing Pattern.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlengulfing

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLENGULFING()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLENGULFING(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdleveningdojistar'])
    def CDLEVENINGDOJISTAR(self, **kwargs) -> IndSeries:
        """黄昏十字星 · CDLEVENINGDOJISTAR（形态）
        ---------
            黄昏十字星，含十字星的三K看跌反转形态，识别时输出-100，否则为0。
            原库说明: Evening Doji Star — 3-candle bearish reversal with doji star.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdleveningdojistar

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLEVENINGDOJISTAR()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLEVENINGDOJISTAR(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdleveningstar'])
    def CDLEVENINGSTAR(self, **kwargs) -> IndSeries:
        """黄昏之星 · CDLEVENINGSTAR（形态）
        ---------
            黄昏之星，三根K线组成的看跌反转形态，识别时输出-100，否则为0。
            原库说明: Evening Star — 3-candle bearish reversal pattern.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdleveningstar

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLEVENINGSTAR()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLEVENINGSTAR(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlgapsidesidewhite'])
    def CDLGAPSIDESIDEWHITE(self, **kwargs) -> IndSeries:
        """跳空并列白线 · CDLGAPSIDESIDEWHITE（形态）
        ---------
            跳空并列白线，三根K线组成的持续形态，向上跳空输出100，向下跳空输出-100。
            原库说明: Up/Down-Gap Side-by-Side White Lines — 3-candle continuation.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlgapsidesidewhite

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLGAPSIDESIDEWHITE()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLGAPSIDESIDEWHITE(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlgravestonedoji'])
    def CDLGRAVESTONEDOJI(self, **kwargs) -> IndSeries:
        """墓碑十字 · CDLGRAVESTONEDOJI（形态）
        ---------
            墓碑十字，带长上影线的十字星形态，识别时输出-100，否则为0。
            原库说明: Gravestone Doji — doji with long upper shadow.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlgravestonedoji

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLGRAVESTONEDOJI()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLGRAVESTONEDOJI(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlhammer'])
    def CDLHAMMER(self, **kwargs) -> IndSeries:
        """锤子线 · CDLHAMMER（形态）
        ---------
            锤子线，实体小且位于上方、下影线长，属看涨反转K线，识别时输出100。
            原库说明: Hammer — small body at top, long lower shadow.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlhammer

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLHAMMER()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLHAMMER(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlhangingman'])
    def CDLHANGINGMAN(self, **kwargs) -> IndSeries:
        """上吊线 · CDLHANGINGMAN（形态）
        ---------
            上吊线，形状与锤子线相同但出现在高位，为看跌警示，识别时输出-100。
            原库说明: Hanging Man — same shape as hammer but bearish warning.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlhangingman

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLHANGINGMAN()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLHANGINGMAN(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlharami'])
    def CDLHARAMI(self, **kwargs) -> IndSeries:
        """孕线 · CDLHARAMI（形态）
        ---------
            孕线形态，小实体完全落在前一根大实体之内，看涨输出100，看跌输出-100。
            原库说明: Harami Pattern — small candle inside the prior large candle's body.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlharami

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLHARAMI()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLHARAMI(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlharamicross'])
    def CDLHARAMICROSS(self, **kwargs) -> IndSeries:
        """十字孕线 · CDLHARAMICROSS（形态）
        ---------
            十字孕线，前大实体内部出现十字星，看涨输出100，看跌输出-100，否则为0。
            原库说明: Harami Cross — doji inside the prior large candle's body.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlharamicross

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLHARAMICROSS()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLHARAMICROSS(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlhighwave'])
    def CDLHIGHWAVE(self, **kwargs) -> IndSeries:
        """高浪线 · CDLHIGHWAVE（形态）
        ---------
            高浪线，实体很小而上下影线极长，显示多空分歧，看涨输出100、看跌输出-100。
            原库说明: High-Wave Candle — small body with very long upper and lower shadows.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlhighwave

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLHIGHWAVE()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLHIGHWAVE(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlhikkake'])
    def CDLHIKKAKE(self, **kwargs) -> IndSeries:
        """陷阱形态 · CDLHIKKAKE（形态）
        ---------
            陷阱形态，内包线后出现假突破再反转，看涨输出100，看跌输出-100。
            原库说明: Hikkake Pattern — inside bar followed by false breakout then reversal.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlhikkake

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLHIKKAKE()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLHIKKAKE(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlhikkakemod'])
    def CDLHIKKAKEMOD(self, **kwargs) -> IndSeries:
        """修正陷阱形态 · CDLHIKKAKEMOD（形态）
        ---------
            修正陷阱形态，即带延迟确认的陷阱形态，看涨输出100，看跌输出-100。
            原库说明: Modified Hikkake Pattern — hikkake with delayed confirmation.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlhikkakemod

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLHIKKAKEMOD()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLHIKKAKEMOD(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlhomingpigeon'])
    def CDLHOMINGPIGEON(self, **kwargs) -> IndSeries:
        """家鸽形态 · CDLHOMINGPIGEON（形态）
        ---------
            家鸽形态，两根阴线且第二根实体被第一根包住，看涨提示，识别时输出100。
            原库说明: Homing Pigeon — 2 bearish candles, second inside the first body.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlhomingpigeon

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLHOMINGPIGEON()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLHOMINGPIGEON(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlidentical3crows'])
    def CDLIDENTICAL3CROWS(self, **kwargs) -> IndSeries:
        """相同三乌鸦 · CDLIDENTICAL3CROWS（形态）
        ---------
            相同三乌鸦，三根阴线均开在前一根收盘价附近，看跌形态，识别时输出-100。
            原库说明: Identical Three Crows — 3 bearish candles each opening at prior close.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlidentical3crows

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLIDENTICAL3CROWS()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLIDENTICAL3CROWS(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlinneck'])
    def CDLINNECK(self, **kwargs) -> IndSeries:
        """颈内形态 · CDLINNECK（形态）
        ---------
            颈内形态，阴线后阳线仅收在前收盘附近，属看跌持续形态，识别时输出-100。
            原库说明: In-Neck Pattern — bearish then bullish closing near prior close, bearish
                continuation.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlinneck

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLINNECK()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLINNECK(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlinvertedhammer'])
    def CDLINVERTEDHAMMER(self, **kwargs) -> IndSeries:
        """倒锤子线 · CDLINVERTEDHAMMER（形态）
        ---------
            倒锤子线，实体小且位于下方、上影线长，属看涨反转K线，识别时输出100。
            原库说明: Inverted Hammer — small body at bottom, long upper shadow.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlinvertedhammer

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLINVERTEDHAMMER()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLINVERTEDHAMMER(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlkicking'])
    def CDLKICKING(self, **kwargs) -> IndSeries:
        """反冲形态 · CDLKICKING（形态）
        ---------
            反冲形态，两根方向相反且带跳空的光头光脚线，看涨输出100，看跌输出-100。
            原库说明: Kicking — two opposite marubozu candles with a gap.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlkicking

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLKICKING()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLKICKING(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlkickingbylength'])
    def CDLKICKINGBYLENGTH(self, **kwargs) -> IndSeries:
        """按长度判定的反冲 · CDLKICKINGBYLENGTH（形态）
        ---------
            按长度判定的反冲形态，由较长光头光脚线的方向决定，看涨100、看跌-100。
            原库说明: Kicking by the Longer Marubozu — direction determined by longer marubozu.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlkickingbylength

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLKICKINGBYLENGTH()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLKICKINGBYLENGTH(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlladderbottom'])
    def CDLLADDERBOTTOM(self, **kwargs) -> IndSeries:
        """梯底形态 · CDLLADDERBOTTOM（形态）
        ---------
            梯底形态，五根K线组成的看涨反转形态，识别时输出100，否则为0。
            原库说明: Ladder Bottom — 5-candle bullish reversal.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlladderbottom

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLLADDERBOTTOM()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLLADDERBOTTOM(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdllongleggeddoji'])
    def CDLLONGLEGGEDDOJI(self, **kwargs) -> IndSeries:
        """长脚十字 · CDLLONGLEGGEDDOJI（形态）
        ---------
            长脚十字，上下影线都很长的十字星形态，识别时输出100，否则为0。
            原库说明: Long Legged Doji — doji with long upper and lower shadows.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdllongleggeddoji

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLLONGLEGGEDDOJI()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLLONGLEGGEDDOJI(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdllongline'])
    def CDLLONGLINE(self, **kwargs) -> IndSeries:
        """长实体线 · CDLLONGLINE（形态）
        ---------
            长实体线，实体长度占全幅七成以上的K线，看涨输出100，看跌输出-100。
            原库说明: Long Line Candle — long body candle (body >= 70% of range).

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdllongline

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLLONGLINE()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLLONGLINE(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlmarubozu'])
    def CDLMARUBOZU(self, **kwargs) -> IndSeries:
        """光头光脚线 · CDLMARUBOZU（形态）
        ---------
            光头光脚线，几乎无上下影线的全实体K线，看涨输出100，看跌输出-100。
            原库说明: Marubozu — full body candle with no or minimal shadows.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlmarubozu

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLMARUBOZU()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLMARUBOZU(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlmatchinglow'])
    def CDLMATCHINGLOW(self, **kwargs) -> IndSeries:
        """相同低价 · CDLMATCHINGLOW（形态）
        ---------
            相同低价，两根阴线收盘价相等，属看涨反转形态，识别时输出100。
            原库说明: Matching Low — 2 bearish candles with equal closes, bullish reversal.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlmatchinglow

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLMATCHINGLOW()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLMATCHINGLOW(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlmathold'])
    def CDLMATHOLD(self, **kwargs) -> IndSeries:
        """铺垫形态 · CDLMATHOLD（形态）
        ---------
            铺垫形态，五根K线组成的看涨持续形态，识别时输出100，否则为0。
            原库说明: Mat Hold — 5-candle bullish continuation pattern.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlmathold

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLMATHOLD()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLMATHOLD(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlmorningdojistar'])
    def CDLMORNINGDOJISTAR(self, **kwargs) -> IndSeries:
        """早晨十字星 · CDLMORNINGDOJISTAR（形态）
        ---------
            早晨十字星，含十字星的三K看涨反转形态，识别时输出100，否则为0。
            原库说明: Morning Doji Star — 3-candle bullish reversal with doji star.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlmorningdojistar

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLMORNINGDOJISTAR()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLMORNINGDOJISTAR(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlmorningstar'])
    def CDLMORNINGSTAR(self, **kwargs) -> IndSeries:
        """早晨之星 · CDLMORNINGSTAR（形态）
        ---------
            早晨之星，三根K线组成的看涨反转形态，识别时输出100，否则为0。
            原库说明: Morning Star — 3-candle bullish reversal pattern.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlmorningstar

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLMORNINGSTAR()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLMORNINGSTAR(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlonneck'])
    def CDLONNECK(self, **kwargs) -> IndSeries:
        """颈上形态 · CDLONNECK（形态）
        ---------
            颈上形态，阴线后阳线仅回升至前一根最低价，属看跌持续，识别时输出-100。
            原库说明: On-Neck Pattern — bearish then bullish reaching only prior low, bearish
                continuation.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlonneck

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLONNECK()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLONNECK(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlpiercing'])
    def CDLPIERCING(self, **kwargs) -> IndSeries:
        """刺透形态 · CDLPIERCING（形态）
        ---------
            刺透形态，阴线后阳线刺入其前实体中点以上，属看涨反转，识别时输出100。
            原库说明: Piercing Pattern — bearish then bullish piercing past midpoint, bullish
                reversal.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlpiercing

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLPIERCING()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLPIERCING(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlrickshawman'])
    def CDLRICKSHAWMAN(self, **kwargs) -> IndSeries:
        """黄包车夫 · CDLRICKSHAWMAN（形态）
        ---------
            黄包车夫形态，上下影线长且实体位于中部的十字星，识别时输出100。
            原库说明: Rickshaw Man — doji with long shadows and body near center.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlrickshawman

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLRICKSHAWMAN()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLRICKSHAWMAN(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlrisefall3methods'])
    def CDLRISEFALL3METHODS(self, **kwargs) -> IndSeries:
        """上升/下降三法 · CDLRISEFALL3METHODS（形态）
        ---------
            上升/下降三法，五根K线组成的持续形态，看涨输出100，看跌输出-100。
            原库说明: Rising/Falling Three Methods — 5-candle continuation pattern.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlrisefall3methods

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLRISEFALL3METHODS()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLRISEFALL3METHODS(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlseparatinglines'])
    def CDLSEPARATINGLINES(self, **kwargs) -> IndSeries:
        """分离线 · CDLSEPARATINGLINES（形态）
        ---------
            分离线，两根开盘价相同但方向相反的K线，属持续形态，看涨输出100、看跌-100。
            原库说明: Separating Lines — 2-candle continuation with same open, opposite
                direction.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlseparatinglines

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLSEPARATINGLINES()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLSEPARATINGLINES(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlshootingstar'])
    def CDLSHOOTINGSTAR(self, **kwargs) -> IndSeries:
        """流星线 · CDLSHOOTINGSTAR（形态）
        ---------
            流星线，实体小且位于下方、上影线长，属看跌反转K线，识别时输出-100。
            原库说明: Shooting Star — small body at bottom, long upper shadow.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlshootingstar

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLSHOOTINGSTAR()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLSHOOTINGSTAR(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlshortline'])
    def CDLSHORTLINE(self, **kwargs) -> IndSeries:
        """短实体线 · CDLSHORTLINE（形态）
        ---------
            短实体线，实体长度不超过全幅三成的K线，看涨输出100，看跌输出-100。
            原库说明: Short Line Candle — small body (body <= 30% of range).

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlshortline

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLSHORTLINE()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLSHORTLINE(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlspinningtop'])
    def CDLSPINNINGTOP(self, **kwargs) -> IndSeries:
        """陀螺线 · CDLSPINNINGTOP（形态）
        ---------
            陀螺线，实体小且影线长于实体，反映多空犹豫，看涨输出100、看跌输出-100。
            原库说明: Spinning Top — small body with shadows longer than the body.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlspinningtop

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLSPINNINGTOP()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLSPINNINGTOP(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlstalledpattern'])
    def CDLSTALLEDPATTERN(self, **kwargs) -> IndSeries:
        """停顿形态 · CDLSTALLEDPATTERN（形态）
        ---------
            停顿形态，三根阳线中第三根动能停顿，属看跌警示，识别时输出-100。
            原库说明: Stalled Pattern — 3 bullish candles with stalling on the third, bearish
                warning.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlstalledpattern

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLSTALLEDPATTERN()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLSTALLEDPATTERN(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlsticksandwich'])
    def CDLSTICKSANDWICH(self, **kwargs) -> IndSeries:
        """条形三明治 · CDLSTICKSANDWICH（形态）
        ---------
            两根阴线夹一根阳线且首尾收盘价相同的形态，属看跌信号，常用于确认下跌延续。
            原库说明: Stick Sandwich — 2 bearish candles surrounding a bullish, same close.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlsticksandwich

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLSTICKSANDWICH()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLSTICKSANDWICH(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdltakuri'])
    def CDLTAKURI(self, **kwargs) -> IndSeries:
        """探底蜻蜓十字 · CDLTAKURI（形态）
        ---------
            下影线极长（至少为实体3倍）的蜻蜓十字形态，显示下方承接，常见于底部反转信号。
            原库说明: Takuri — Dragonfly Doji with very long lower shadow (>= 3x body).

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdltakuri

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLTAKURI()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLTAKURI(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdltasukigap'])
    def CDLTASUKIGAP(self, **kwargs) -> IndSeries:
        """跳空并列阴阳线 · CDLTASUKIGAP（形态）
        ---------
            三根K线构成的跳空延续形态，第三根部分回补缺口，用于判断原趋势是否延续。
            原库说明: Tasuki Gap — 3-candle gap continuation with partial fill.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdltasukigap

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLTASUKIGAP()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLTASUKIGAP(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlthrusting'])
    def CDLTHRUSTING(self, **kwargs) -> IndSeries:
        """插入线 · CDLTHRUSTING（形态）
        ---------
            先阴后阳、阳线收盘未越过前阴线中点的形态，暗示反弹乏力，属看跌延续信号。
            原库说明: Thrusting Pattern — bearish then bullish reaching below midpoint, bearish
                continuation.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlthrusting

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLTHRUSTING()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLTHRUSTING(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdltristar'])
    def CDLTRISTAR(self, **kwargs) -> IndSeries:
        """三星 · CDLTRISTAR（形态）
        ---------
            三根十字星组成的形态，预示趋势动能衰竭，据其排列方向判断看涨或看跌反转。
            原库说明: Tristar Pattern — 3 dojis with reversal implication.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdltristar

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLTRISTAR()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLTRISTAR(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlunique3river'])
    def CDLUNIQUE3RIVER(self, **kwargs) -> IndSeries:
        """奇特三河床 · CDLUNIQUE3RIVER（形态）
        ---------
            三根K线构成的看涨反转形态，先长阴后连续小实体并收回，暗示底部转折。
            原库说明: Unique 3 River — 3-candle bullish reversal.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlunique3river

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLUNIQUE3RIVER()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLUNIQUE3RIVER(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlupsidegap2crows'])
    def CDLUPSIDEGAP2CROWS(self, **kwargs) -> IndSeries:
        """向上跳空两只乌鸦 · CDLUPSIDEGAP2CROWS（形态）
        ---------
            三根K线的看跌反转形态：跳空高开后连收两根阴线，暗示上涨动能转弱。
            原库说明: Upside Gap Two Crows — 3-candle bearish reversal.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlupsidegap2crows

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLUPSIDEGAP2CROWS()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLUPSIDEGAP2CROWS(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cdlxsidegap3methods'])
    def CDLXSIDEGAP3METHODS(self, **kwargs) -> IndSeries:
        """跳空三法 · CDLXSIDEGAP3METHODS（形态）
        ---------
            三根K线的跳空回补延续形态，按方向给出看涨或看跌信号，表示原趋势将继续。
            原库说明: Upside/Downside Gap Three Methods — 3-candle gap fill continuation.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdlxsidegap3methods

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.CDLXSIDEGAP3METHODS()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CDLXSIDEGAP3METHODS(open, high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['ceil'])
    def CEIL(self, **kwargs) -> IndSeries:
        """向上取整 · CEIL（其他）
        ---------
            对输入序列逐元素向上取整，属于通用数学运算，可用于价格或指标的取整处理。
            原库说明: Ceiling (element-wise).

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — ceil

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.CEIL()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CEIL(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['chaikin_vol'])
    def CHAIKIN_VOL(self, timeperiod: int = 14, rocperiod: int = 10, **kwargs) -> IndSeries:
        """蔡金波动率 · CHAIKIN_VOL（波动率）
        ---------
            对最高最低价差的EMA计算变动率，反映波动率的扩张与收缩，数值以百分比表示。
            原库说明: Chaikin Volatility — ROC of an EMA of the high–low range.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> rocperiod (int): 对应子指标的周期（原库同名参数）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — chaikin_vol

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.CHAIKIN_VOL(timeperiod=14, rocperiod=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CHAIKIN_VOL(high, low, timeperiod=14, rocperiod=10)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['chandelier_exit_1', 'chandelier_exit_2'])
    def CHANDELIER_EXIT(self, timeperiod: int = 14, multiplier: float = 3.0, **kwargs) -> IndFrame:
        """吊灯止损 · CHANDELIER_EXIT（波动率）
        ---------
            以最高价或最低价加减ATR倍数得到多头与空头追踪止损位，用于持仓离场管理。
            原库说明: Chandelier Exit — ATR-based trailing stop levels.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> multiplier (float): ATR / 标准差倍数（决定通道与止损宽度）. 默认: 3.0

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 2 条线 — chandelier_exit_1, chandelier_exit_2

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.CHANDELIER_EXIT(timeperiod=14, multiplier=3.0)    # 主图叠加
            >>> out.columns               # 线名: chandelier_exit_1, chandelier_exit_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CHANDELIER_EXIT(high, low, close, timeperiod=14, multiplier=3.0)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['chande_kroll_stop_1', 'chande_kroll_stop_2'])
    def CHANDE_KROLL_STOP(self, timeperiod: int = 14, multiplier: float = 3.0, stop_period: int = 9, **kwargs) -> IndFrame:
        """钱德克罗尔止损 · CHANDE_KROLL_STOP（波动率）
        ---------
            结合最高最低价与ATR生成初始止损，再取确认窗口内的极值，得到多空追踪止损线。
            原库说明: Chande Kroll Stop.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> multiplier (float): ATR / 标准差倍数（决定通道与止损宽度）. 默认: 3.0
            >>> stop_period (int): 计算周期（K 线根数）. 默认: 9

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 2 条线 — chande_kroll_stop_1, chande_kroll_stop_2

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.CHANDE_KROLL_STOP(timeperiod=14, multiplier=3.0, stop_period=9)    # 主图叠加
            >>> out.columns               # 线名: chande_kroll_stop_1, chande_kroll_stop_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CHANDE_KROLL_STOP(high, low, close, timeperiod=14, multiplier=3.0, stop_period=9)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['change'])
    def CHANGE(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """变动值 · CHANGE（统计）
        ---------
            当前值与若干周期前值之差，衡量价格的绝对涨跌幅度，前期数据为NaN。
            原库说明: Lookback difference: ``real[i] - real[i - timeperiod]``.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — change

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.CHANGE(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CHANGE(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cho'])
    def CHO(self, fastperiod: int = 3, slowperiod: int = 10, **kwargs) -> IndSeries:
        """蔡金振荡器 · CHO（成交量）
        ---------
            以快慢两条ADL的EMA之差衡量资金流向动量，正值表示买压增强、负值表示卖压增强。
            原库说明: Chaikin Oscillator — same math as ``ADOSC``.

        参数:
        ---------
            >>> fastperiod (int): 快线周期. 默认: 3
            >>> slowperiod (int): 慢线周期. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cho

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.CHO(fastperiod=3, slowperiod=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CHO(high, low, close, volume, fastperiod=3, slowperiod=10)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['choppiness_index'])
    def CHOPPINESS_INDEX(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """震荡指数 · CHOPPINESS_INDEX（波动率）
        ---------
            比较区间内真实波幅之和与最高最低价差，取值0至100，越高代表震荡盘整、越低代表强趋势。
            原库说明: Choppiness Index — measures market choppiness (range-bound vs trending).

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — choppiness_index

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.CHOPPINESS_INDEX(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CHOPPINESS_INDEX(high, low, close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cmf'])
    def CMF(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """蔡金资金流 · CMF（成交量）
        ---------
            以收盘位置乖离乘成交量的滚动和除以成交量滚动和，正值表示资金流入、负值表示流出。
            原库说明: Chaikin Money Flow.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cmf

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.CMF(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CMF(high, low, close, volume, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cmo'])
    def CMO(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """钱德动量振荡器 · CMO（动量）
        ---------
            用上涨动量与下跌动量之差除以两者之和，取值-100至100，用于判断超买超卖与动量强弱。
            原库说明: Chande Momentum Oscillator.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cmo

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.CMO(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CMO(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['coppock'])
    def COPPOCK(self, wma_period: int = 10, roc1_period: int = 14, roc2_period: int = 11, **kwargs) -> IndSeries:
        """科波克曲线 · COPPOCK（动量）
        ---------
            对长短两个ROC之和再做加权移动平均，用于识别长期动量转折与买入时机。
            原库说明: Coppock Curve: WMA of ROC(14) + ROC(11).

        参数:
        ---------
            >>> wma_period (int): WMA 周期. 默认: 10
            >>> roc1_period (int): 对应子指标的周期（原库同名参数）. 默认: 14
            >>> roc2_period (int): 对应子指标的周期（原库同名参数）. 默认: 11

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — coppock

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.COPPOCK(wma_period=10, roc1_period=14, roc2_period=11)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.COPPOCK(close, wma_period=10, roc1_period=14, roc2_period=11)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['correl'])
    def CORREL(self, real1=None, timeperiod: int = 14, **kwargs) -> IndSeries:
        """皮尔逊相关系数 · CORREL（统计）
        ---------
            滚动计算两组序列的皮尔逊相关系数，取值-1至1，用于衡量两者同向或反向的联动程度。
            原库说明: Pearson's Correlation Coefficient (r).

        参数:
        ---------
            >>> real1 (值): 第二条价格序列（pd.Series / np.ndarray，长度与 K 线一致，必填）. 默认: None
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — correl

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.CORREL(real1=None, timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CORREL(close, real1=None, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cos'])
    def COS(self, **kwargs) -> IndSeries:
        """余弦 · COS（其他）
        ---------
            对输入序列逐元素计算余弦值，属于通用数学运算，多用于自定义指标构造。
            原库说明: Cosine (element-wise).

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cos

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.COS()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.COS(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cosh'])
    def COSH(self, **kwargs) -> IndSeries:
        """双曲余弦 · COSH（其他）
        ---------
            对输入序列逐元素计算双曲余弦值，属于通用数学运算，多用于自定义指标构造。
            原库说明: Hyperbolic cosine (element-wise).

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cosh

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.COSH()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.COSH(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['cross'])
    def CROSS(self, real1=None, **kwargs) -> IndSeries:
        """交叉 · CROSS（其他）
        ---------
            当两条序列在任一根K线上发生交叉（无论方向）时返回1，否则返回0，用于捕捉交叉事件。
            原库说明: 1.0 on any bar where *real0* crosses *real1* in either direction.

        参数:
        ---------
            >>> real1 (值): 第二条价格序列（pd.Series / np.ndarray，长度与 K 线一致，必填）. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cross

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.CROSS(real1=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CROSS(close, real1=None)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['crossover'])
    def CROSSOVER(self, real1=None, **kwargs) -> IndSeries:
        """上穿 · CROSSOVER（其他）
        ---------
            当第一条序列由不高于第二条变为高于第二条时返回1，用于生成金叉一类的买入信号。
            原库说明: 1.0 on the bar where *real0* crosses strictly above *real1*.

        参数:
        ---------
            >>> real1 (值): 第二条价格序列（pd.Series / np.ndarray，长度与 K 线一致，必填）. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — crossover

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.CROSSOVER(real1=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CROSSOVER(close, real1=None)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['crossunder'])
    def CROSSUNDER(self, real1=None, **kwargs) -> IndSeries:
        """下穿 · CROSSUNDER（其他）
        ---------
            当第一条序列由不低于第二条变为低于第二条时返回1，用于生成死叉一类的卖出信号。
            原库说明: 1.0 on the bar where *real0* crosses strictly below *real1*.

        参数:
        ---------
            >>> real1 (值): 第二条价格序列（pd.Series / np.ndarray，长度与 K 线一致，必填）. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — crossunder

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.CROSSUNDER(real1=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CROSSUNDER(close, real1=None)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['crsi'])
    def CRSI(self, timeperiod: int = 14, streakperiod: int = 2, rankperiod: int = 100, **kwargs) -> IndSeries:
        """康纳斯RSI · CRSI（动量）
        ---------
            由价格RSI、连续涨跌RSI与单周期ROC百分位排名取平均，构成0至100的复合超买超卖指标。
            原库说明: Connors RSI — average of price RSI, streak RSI, and ROC percent rank.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> streakperiod (int): 计算周期（K 线根数）. 默认: 2
            >>> rankperiod (int): 计算周期（K 线根数）. 默认: 100

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — crsi

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.CRSI(timeperiod=14, streakperiod=2, rankperiod=100)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.CRSI(close, timeperiod=14, streakperiod=2, rankperiod=100)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['dema'])
    def DEMA(self, timeperiod: int = 20, **kwargs) -> IndSeries:
        """双指数移动平均 · DEMA（趋势）
        ---------
            用两倍EMA减EMA的EMA以降低滞后，趋势跟随更灵敏，前期若干个值为NaN。
            原库说明: Double Exponential Moving Average.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — dema

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.DEMA(timeperiod=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.DEMA(close, timeperiod=20)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['div'])
    def DIV(self, real1=None, **kwargs) -> IndSeries:
        """逐元素相除 · DIV（其他）
        ---------
            将两条序列逐元素相除，属于通用数学运算，可用于构造比值类自定义指标。
            原库说明: Element-wise division: real0 / real1.

        参数:
        ---------
            >>> real1 (值): 第二条价格序列（pd.Series / np.ndarray，长度与 K 线一致，必填）. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — div

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.DIV(real1=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.DIV(close, real1=None)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['adx', 'plus_di', 'minus_di'])
    def DMI(self, timeperiod: int = 14, **kwargs) -> IndFrame:
        """动向指标组 · DMI（趋势）
        ---------
            一次计算给出正负方向线与ADX三条序列，用于判断趋势方向及其强度，与分别调用等价。
            原库说明: Directional Movement Index — ``(PLUS_DI, MINUS_DI, ADX)`` in one pass.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 副图 · 3 条线 — adx, plus_di, minus_di

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.DMI(timeperiod=14)    # 副图
            >>> out.columns               # 线名: adx, plus_di, minus_di
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.DMI(high, low, close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['donchian_1', 'donchian_2', 'donchian_3'])
    def DONCHIAN(self, timeperiod: int = 14, **kwargs) -> IndFrame:
        """唐奇安通道 · DONCHIAN（趋势）
        ---------
            由滚动最高价、最低价及其中线构成的通道，常用于突破交易与衡量价格区间。
            原库说明: Donchian Channels — rolling highest high / lowest low.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — donchian_1, donchian_2, donchian_3

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.DONCHIAN(timeperiod=14)    # 主图叠加
            >>> out.columns               # 线名: donchian_1, donchian_2, donchian_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.DONCHIAN(high, low, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['dpo'])
    def DPO(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """去趋势价格振荡器 · DPO（动量）
        ---------
            剔除价格中的趋势成分后观察其围绕零轴的周期波动，用于识别买卖周期与超买超卖。
            原库说明: Detrended Price Oscillator.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — dpo

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.DPO(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.DPO(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['dx'])
    def DX(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """动向指数 · DX（趋势）
        ---------
            由正负方向运动平滑后计算的方向强度指标，取值0至100，数值越高趋势越明确。
            原库说明: Directional Movement Index.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — dx

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.DX(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.DX(high, low, close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['elder_ray_1', 'elder_ray_2'])
    def ELDER_RAY(self, timeperiod: int = 14, **kwargs) -> IndFrame:
        """埃尔德射线 · ELDER_RAY（动量）
        ---------
            最高价与最低价相对收盘EMA的偏离，分别构成多头力量与空头力量，用于衡量多空力度。
            原库说明: Elder Ray Index — bull power and bear power versus EMA(close).

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — elder_ray_1, elder_ray_2

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.ELDER_RAY(timeperiod=14)    # 副图
            >>> out.columns               # 线名: elder_ray_1, elder_ray_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ELDER_RAY(high, low, close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['ema'])
    def EMA(self, timeperiod: int = 20, **kwargs) -> IndSeries:
        """指数移动平均 · EMA（趋势）
        ---------
            对价格按指数权重平滑的移动平均，对近期价格更敏感，常用于判断趋势方向与支撑阻力。
            原库说明: Exponential Moving Average.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — ema

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.EMA(timeperiod=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.EMA(close, timeperiod=20)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['emv'])
    def EMV(self, timeperiod: int = 14, divisor: float = 10000.0, **kwargs) -> IndSeries:
        """简易波动指标 · EMV（成交量）
        ---------
            阿姆斯简易波动指标，结合价格位移与成交量衡量推动价格变动的难易程度。
            原库说明: Ease of Movement (Arms).

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> divisor (float): 除数 / 调整系数. 默认: 10000.0

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — emv

        数据:
        ---------
            >>> high, low, volume

        使用案例:
        ---------
            >>> out = self.data.EMV(timeperiod=14, divisor=10000.0)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.EMV(high, low, volume, timeperiod=14, divisor=10000.0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['exp'])
    def EXP(self, **kwargs) -> IndSeries:
        """指数函数 · EXP（其他）
        ---------
            对输入序列逐元素计算自然指数，属于通用数学运算，多用于自定义指标构造。
            原库说明: Exponential (element-wise).

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — exp

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.EXP()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.EXP(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['exrem'])
    def EXREM(self, secondary=None, **kwargs) -> IndSeries:
        """信号去冗余 · EXREM（其他）
        ---------
            仅保留首个主信号，在有次信号出现前抑制后续主信号，常用于避免重复开仓提示。
            原库说明: Keep the first *primary* signal and suppress further primaries until a
                *secondary* signal occurs.

        参数:
        ---------
            >>> secondary (值): 第二条价格序列（pd.Series / np.ndarray，长度与 K 线一致，必填）. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — exrem

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.EXREM(secondary=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.EXREM(close, secondary=None)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['falling'])
    def FALLING(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """下降判定 · FALLING（其他）
        ---------
            当前值严格低于若干周期前值时返回1，否则返回0，用于筛选处于下降状态的序列。
            原库说明: 1.0 when *real* is strictly less than it was *timeperiod* bars ago.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — falling

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.FALLING(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.FALLING(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['fisher_1', 'fisher_2'])
    def FISHER(self, timeperiod: int = 14, **kwargs) -> IndFrame:
        """费雪变换 · FISHER（动量）
        ---------
            对中价做埃尔德斯费雪变换并给出信号线，用于识别超买超卖与周期拐点。
            原库说明: Ehlers Fisher Transform of median price.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — fisher_1, fisher_2

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.FISHER(timeperiod=14)    # 副图
            >>> out.columns               # 线名: fisher_1, fisher_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.FISHER(high, low, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['flip'])
    def FLIP(self, secondary=None, **kwargs) -> IndSeries:
        """信号保持 · FLIP（其他）
        ---------
            主信号出现后保持为1，直到次信号将其清除，用于构造持续持仓状态标记。
            原库说明: Hold 1.0 from a *primary* signal until a *secondary* signal clears it.

        参数:
        ---------
            >>> secondary (值): 第二条价格序列（pd.Series / np.ndarray，长度与 K 线一致，必填）. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — flip

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.FLIP(secondary=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.FLIP(close, secondary=None)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['floor'])
    def FLOOR(self, **kwargs) -> IndSeries:
        """向下取整 · FLOOR（其他）
        ---------
            对输入序列逐元素向下取整，属于通用数学运算，可用于价格或指标的取整处理。
            原库说明: Floor (element-wise).

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — floor

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.FLOOR()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.FLOOR(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['force_index'])
    def FORCE_INDEX(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """强力指数 · FORCE_INDEX（成交量）
        ---------
            以价格变化乘以成交量衡量多空推动力，周期为1时即为原始强力指数序列。
            原库说明: Elder's Force Index.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — force_index

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.FORCE_INDEX(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.FORCE_INDEX(close, volume, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['frama'])
    def FRAMA(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """分形自适应均线 · FRAMA（趋势）
        ---------
            按收盘价的分形维数自适应调整平滑系数的EMA，趋势快、震荡慢，用于降低噪声与滞后。
            原库说明: Fractal Adaptive Moving Average.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — frama

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.FRAMA(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.FRAMA(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['gator_1', 'gator_2'])
    def GATOR(self, jaw_period: int = 13, jaw_shift: int = 8, teeth_period: int = 8, teeth_shift: int = 5, lips_period: int = 5, lips_shift: int = 3, **kwargs) -> IndFrame:
        """鳄鱼振荡器 · GATOR（趋势）
        ---------
            由鳄鱼线各SMMA之间的距离构成上下两条柱线，用于判断趋势启动、休眠或衰弱状态。
            原库说明: Gator Oscillator from Alligator SMMA lines.

        参数:
        ---------
            >>> jaw_period (int): 计算周期（K 线根数）. 默认: 13
            >>> jaw_shift (int): 平移根数. 默认: 8
            >>> teeth_period (int): 计算周期（K 线根数）. 默认: 8
            >>> teeth_shift (int): 平移根数. 默认: 5
            >>> lips_period (int): 计算周期（K 线根数）. 默认: 5
            >>> lips_shift (int): 平移根数. 默认: 3

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — gator_1, gator_2

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.GATOR(jaw_period=13, jaw_shift=8, teeth_period=8, teeth_shift=5, lips_period=5, lips_shift=3)    # 副图
            >>> out.columns               # 线名: gator_1, gator_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.GATOR(high, low, jaw_period=13, jaw_shift=8, teeth_period=8, teeth_shift=5, lips_period=5, lips_shift=3)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['highest'])
    def HIGHEST(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """滚动最高值 · HIGHEST（统计）
        ---------
            取过去若干根K线内的最高值，与MAX算法相同，常用于构建通道上轨或突破参考。
            原库说明: Rolling highest value over *timeperiod* bars.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — highest

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.HIGHEST(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.HIGHEST(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['historical_volatility'])
    def HISTORICAL_VOLATILITY(self, timeperiod: int = 14, annual: float = 252.0, **kwargs) -> IndSeries:
        """历史波动率 · HISTORICAL_VOLATILITY（波动率）
        ---------
            以收盘价对数收益率的标准差年化并转为百分比，用于衡量标的已实现波动水平。
            原库说明: Close-to-close historical volatility, annualized and in percent.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> annual (float): 原库参数（默认值见签名）. 默认: 252.0

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — historical_volatility

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.HISTORICAL_VOLATILITY(timeperiod=14, annual=252.0)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.HISTORICAL_VOLATILITY(close, timeperiod=14, annual=252.0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['ht_dcperiod'])
    def HT_DCPERIOD(self, **kwargs) -> IndSeries:
        """希尔伯特主周期 · HT_DCPERIOD（统计）
        ---------
            用希尔伯特变换估计当前主周期长度（单位K线），平滑后限制在6至50之间。
            原库说明: Hilbert Transform - Dominant Cycle Period.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ht_dcperiod

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.HT_DCPERIOD()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.HT_DCPERIOD(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['ht_dcphase'])
    def HT_DCPHASE(self, **kwargs) -> IndSeries:
        """希尔伯特主周期相位 · HT_DCPHASE（统计）
        ---------
            给出主周期的瞬时相位（以度为单位），用于判断周期所处位置与转折时机。
            原库说明: Hilbert Transform - Dominant Cycle Phase.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ht_dcphase

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.HT_DCPHASE()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.HT_DCPHASE(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['ht_phasor_1', 'ht_phasor_2'])
    def HT_PHASOR(self, **kwargs) -> IndFrame:
        """希尔伯特相位分量 · HT_PHASOR（统计）
        ---------
            输出希尔伯特变换的同相分量与正交分量，即解析信号的实部与虚部，用于周期分析。
            原库说明: Hilbert Transform - Phasor Components.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — ht_phasor_1, ht_phasor_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.HT_PHASOR()    # 副图
            >>> out.columns               # 线名: ht_phasor_1, ht_phasor_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.HT_PHASOR(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['ht_sine_1', 'ht_sine_2'])
    def HT_SINE(self, **kwargs) -> IndFrame:
        """希尔伯特正弦波 · HT_SINE（统计）
        ---------
            输出主周期相位的正弦线与其45度领先线，两条线的交叉常用于识别周期拐点。
            原库说明: Hilbert Transform - SineWave.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — ht_sine_1, ht_sine_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.HT_SINE()    # 副图
            >>> out.columns               # 线名: ht_sine_1, ht_sine_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.HT_SINE(close)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['ht_trendline'])
    def HT_TRENDLINE(self, **kwargs) -> IndSeries:
        """希尔伯特趋势线 · HT_TRENDLINE（趋势）
        ---------
            用希尔伯特变换估计价格的潜在趋势线，可平滑噪声并反映即时趋势方向。
            原库说明: Hilbert Transform - Instantaneous Trendline.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — ht_trendline

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.HT_TRENDLINE()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.HT_TRENDLINE(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['ht_trendmode'])
    def HT_TRENDMODE(self, **kwargs) -> IndSeries:
        """趋势/周期模式 · HT_TRENDMODE（趋势）
        ---------
            主周期短于20根K线时返回1表示趋势模式，否则返回0表示周期震荡模式。
            原库说明: Hilbert Transform - Trend vs Cycle Mode.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ht_trendmode

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.HT_TRENDMODE()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.HT_TRENDMODE(close)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['hull_ma'])
    def HULL_MA(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """赫尔均线 · HULL_MA（趋势）
        ---------
            通过加权均线的组合构成低滞后、反应快速的移动平均，常用于趋势跟随与均线交叉。
            原库说明: Hull Moving Average (HMA).

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — hull_ma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.HULL_MA(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.HULL_MA(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['ichimoku_1', 'ichimoku_2', 'ichimoku_3', 'ichimoku_4', 'ichimoku_5'])
    def ICHIMOKU(self, tenkan_period: int = 9, kijun_period: int = 26, senkou_b_period: int = 52, displacement: int = 26, **kwargs) -> IndFrame:
        """一目均衡表 · ICHIMOKU（趋势）
        ---------
            一次性输出转换线、基准线、先行带A/B与迟行线，用于判断趋势、支撑阻力与云层强弱。
            原库说明: Ichimoku Cloud (Ichimoku Kinko Hyo).

        参数:
        ---------
            >>> tenkan_period (int): 计算周期（K 线根数）. 默认: 9
            >>> kijun_period (int): 计算周期（K 线根数）. 默认: 26
            >>> senkou_b_period (int): 计算周期（K 线根数）. 默认: 52
            >>> displacement (int): 平移根数（结果整体后移，避免偷看未来）. 默认: 26

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 5 条线 — ichimoku_1, ichimoku_2, ichimoku_3, ichimoku_4, ichimoku_5

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.ICHIMOKU(tenkan_period=9, kijun_period=26, senkou_b_period=52, displacement=26)    # 主图叠加
            >>> out.columns               # 线名: ichimoku_1, ichimoku_2, ichimoku_3, ichimoku_4, ichimoku_5
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ICHIMOKU(high, low, close, tenkan_period=9, kijun_period=26, senkou_b_period=52, displacement=26)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['kama'])
    def KAMA(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """考夫曼自适应均线 · KAMA（趋势）
        ---------
            依据效率比率调整平滑速度的自适应均线，趋势时灵敏、震荡时平滑，用于趋势跟踪。
            原库说明: Kaufman Adaptive Moving Average.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — kama

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.KAMA(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.KAMA(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['keltner_channels_1', 'keltner_channels_2', 'keltner_channels_3'])
    def KELTNER_CHANNELS(self, timeperiod: int = 14, atr_period: int = 10, multiplier: float = 3.0, **kwargs) -> IndFrame:
        """肯特纳通道 · KELTNER_CHANNELS（波动率）
        ---------
            以收盘价EMA为中轨、加减ATR倍数构成上下轨，用于判断突破与波动区间。
            原库说明: Keltner Channels — EMA ± (multiplier × ATR).

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> atr_period (int): ATR 计算周期. 默认: 10
            >>> multiplier (float): ATR / 标准差倍数（决定通道与止损宽度）. 默认: 3.0

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — keltner_channels_1, keltner_channels_2, keltner_channels_3

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.KELTNER_CHANNELS(timeperiod=14, atr_period=10, multiplier=3.0)    # 主图叠加
            >>> out.columns               # 线名: keltner_channels_1, keltner_channels_2, keltner_channels_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.KELTNER_CHANNELS(high, low, close, timeperiod=14, atr_period=10, multiplier=3.0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['kst_1', 'kst_2'])
    def KST(self, roc1: int = 10, roc2: int = 15, roc3: int = 20, roc4: int = 30, sma1: int = 10, sma2: int = 10, sma3: int = 10, sma4: int = 15, signalperiod: int = 9, **kwargs) -> IndFrame:
        """确然指标 · KST（动量）
        ---------
            由四个不同周期ROC加权平滑后求和并附信号线，用于识别长期动量转折与买卖点。
            原库说明: Know Sure Thing and signal line.

        参数:
        ---------
            >>> roc1 (int): 对应子指标的周期（原库同名参数）. 默认: 10
            >>> roc2 (int): 对应子指标的周期（原库同名参数）. 默认: 15
            >>> roc3 (int): 对应子指标的周期（原库同名参数）. 默认: 20
            >>> roc4 (int): 对应子指标的周期（原库同名参数）. 默认: 30
            >>> sma1 (int): 对应子指标的周期（原库同名参数）. 默认: 10
            >>> sma2 (int): 对应子指标的周期（原库同名参数）. 默认: 10
            >>> sma3 (int): 对应子指标的周期（原库同名参数）. 默认: 10
            >>> sma4 (int): 对应子指标的周期（原库同名参数）. 默认: 15
            >>> signalperiod (int): 信号线平滑周期. 默认: 9

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — kst_1, kst_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.KST(roc1=10, roc2=15, roc3=20, roc4=30, sma1=10, sma2=10, sma3=10, sma4=15, signalperiod=9)    # 副图
            >>> out.columns               # 线名: kst_1, kst_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.KST(close, roc1=10, roc2=15, roc3=20, roc4=30, sma1=10, sma2=10, sma3=10, sma4=15, signalperiod=9)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['kvo_1', 'kvo_2'])
    def KVO(self, fastperiod: int = 34, slowperiod: int = 55, signalperiod: int = 13, **kwargs) -> IndFrame:
        """克林格量价振荡器 · KVO（成交量）
        ---------
            结合成交量与价格趋势方向的长短期EMA之差及信号线，用于确认量价配合与资金流向。
            原库说明: Klinger Volume Oscillator and signal line.

        参数:
        ---------
            >>> fastperiod (int): 快线周期. 默认: 34
            >>> slowperiod (int): 慢线周期. 默认: 55
            >>> signalperiod (int): 信号线平滑周期. 默认: 13

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — kvo_1, kvo_2

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.KVO(fastperiod=34, slowperiod=55, signalperiod=13)    # 副图
            >>> out.columns               # 线名: kvo_1, kvo_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.KVO(high, low, close, volume, fastperiod=34, slowperiod=55, signalperiod=13)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['linearreg'])
    def LINEARREG(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """线性回归 · LINEARREG（趋势）
        ---------
            对滚动窗口做最小二乘拟合，输出回归线在当根K线的端点值，用于判断趋势走向。
            原库说明: Linear Regression.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — linearreg

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.LINEARREG(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.LINEARREG(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['linearreg_angle'])
    def LINEARREG_ANGLE(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """线性回归角度 · LINEARREG_ANGLE（趋势）
        ---------
            输出滚动窗口回归直线的倾斜角度（度），角度越陡表示趋势越强。
            原库说明: Linear Regression Angle (in degrees).

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — linearreg_angle

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.LINEARREG_ANGLE(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.LINEARREG_ANGLE(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['linearreg_intercept'])
    def LINEARREG_INTERCEPT(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """线性回归截距 · LINEARREG_INTERCEPT（趋势）
        ---------
            输出滚动窗口回归直线的截距，用于定位回归线的基准水平并与端点价配合分析。
            原库说明: Linear Regression Intercept.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — linearreg_intercept

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.LINEARREG_INTERCEPT(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.LINEARREG_INTERCEPT(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['linearreg_slope'])
    def LINEARREG_SLOPE(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """线性回归斜率 · LINEARREG_SLOPE（趋势）
        ---------
            输出滚动窗口回归直线的斜率，正值表示上行趋势，负值表示下行趋势。
            原库说明: Linear Regression Slope.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — linearreg_slope

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.LINEARREG_SLOPE(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.LINEARREG_SLOPE(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['ln'])
    def LN(self, **kwargs) -> IndSeries:
        """自然对数 · LN（其他）
        ---------
            对输入序列逐元素取自然对数，非正数输入返回NaN，常用于收益率等变换计算。
            原库说明: Natural logarithm (element-wise). Returns NaN for non-positive inputs.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ln

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.LN()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.LN(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['log10'])
    def LOG10(self, **kwargs) -> IndSeries:
        """常用对数 · LOG10（其他）
        ---------
            对输入序列逐元素取以10为底的对数，非正数输入返回NaN，属通用数学运算。
            原库说明: Base-10 logarithm (element-wise). Returns NaN for non-positive inputs.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — log10

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.LOG10()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.LOG10(close)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['lowest'])
    def LOWEST(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """滚动最低值 · LOWEST（统计）
        ---------
            取过去若干根K线内的最低值，与MIN算法相同，常用于构建通道下轨或止损参考。
            原库说明: Rolling lowest value over *timeperiod* bars.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — lowest

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.LOWEST(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.LOWEST(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['ma'])
    def MA(self, timeperiod: int = 14, matype: int = 0, **kwargs) -> IndSeries:
        """通用移动平均 · MA（趋势）
        ---------
            按指定的均线类型（SMA、EMA、WMA、DEMA、TEMA、TRIMA、KAMA、T3）计算移动平均。
            原库说明: Generic Moving Average.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> matype (int): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 0

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — ma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MA(timeperiod=14, matype=0)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MA(close, timeperiod=14, matype=0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['macd', 'signal', 'histogram'], linestyle={'histogram': LineStyle(line_dash=LineDash.vbar, vbar_base=0.0, vbar_up_color=Colors.bull_color, vbar_down_color=Colors.bear_color)})
    def MACD(self, fastperiod: int = 12, slowperiod: int = 26, signalperiod: int = 9, **kwargs) -> IndFrame:
        """指数平滑异同均线 · MACD（动量）
        ---------
            快慢EMA之差及其信号线与柱状图，用于判断趋势方向、动量变化与交叉买卖点。
            原库说明: Moving Average Convergence/Divergence.

        参数:
        ---------
            >>> fastperiod (int): 快线周期. 默认: 12
            >>> slowperiod (int): 慢线周期. 默认: 26
            >>> signalperiod (int): 信号线平滑周期. 默认: 9

        返回:
        ---------
            >>> IndFrame: 副图 · 3 条线 — macd, signal, histogram

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MACD(fastperiod=12, slowperiod=26, signalperiod=9)    # 副图
            >>> out.columns               # 线名: macd, signal, histogram
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['macd', 'signal', 'histogram'], linestyle={'histogram': LineStyle(line_dash=LineDash.vbar, vbar_base=0.0, vbar_up_color=Colors.bull_color, vbar_down_color=Colors.bear_color)})
    def MACDEXT(self, fastperiod: int = 12, fastmatype: int = 1, slowperiod: int = 26, slowmatype: int = 1, signalperiod: int = 9, signalmatype: int = 1, **kwargs) -> IndFrame:
        """可定制MACD · MACDEXT（动量）
        ---------
            与MACD相同，但快线、慢线与信号线可分别指定均线类型，便于灵活调整计算方式。
            原库说明: MACD with Controllable MA Types.

        参数:
        ---------
            >>> fastperiod (int): 快线周期. 默认: 12
            >>> fastmatype (int): 快线周期. 默认: 1
            >>> slowperiod (int): 慢线周期. 默认: 26
            >>> slowmatype (int): 慢线周期. 默认: 1
            >>> signalperiod (int): 信号线平滑周期. 默认: 9
            >>> signalmatype (int): 信号线平滑周期. 默认: 1

        返回:
        ---------
            >>> IndFrame: 副图 · 3 条线 — macd, signal, histogram

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MACDEXT(fastperiod=12, fastmatype=1, slowperiod=26, slowmatype=1, signalperiod=9, signalmatype=1)    # 副图
            >>> out.columns               # 线名: macd, signal, histogram
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MACDEXT(close, fastperiod=12, fastmatype=1, slowperiod=26, slowmatype=1, signalperiod=9, signalmatype=1)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['macd', 'signal', 'histogram'], linestyle={'histogram': LineStyle(line_dash=LineDash.vbar, vbar_base=0.0, vbar_up_color=Colors.bull_color, vbar_down_color=Colors.bear_color)})
    def MACDFIX(self, signalperiod: int = 9, **kwargs) -> IndFrame:
        """固定参数MACD · MACDFIX（动量）
        ---------
            固定采用12与26周期的MACD，仅可调信号周期，输出MACD、信号线与柱状图三条序列。
            原库说明: Moving Average Convergence/Divergence Fix 12/26.

        参数:
        ---------
            >>> signalperiod (int): 信号线平滑周期. 默认: 9

        返回:
        ---------
            >>> IndFrame: 副图 · 3 条线 — macd, signal, histogram

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MACDFIX(signalperiod=9)    # 副图
            >>> out.columns               # 线名: macd, signal, histogram
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MACDFIX(close, signalperiod=9)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['mama_1', 'mama_2'])
    def MAMA(self, fastlimit: float = 0.5, slowlimit: float = 0.05, **kwargs) -> IndFrame:
        """MESA自适应均线 · MAMA（趋势）
        ---------
            依据希尔伯特变换相位变化率自适应调整平滑系数的均线，输出MAMA与跟随线FAMA。
            原库说明: MESA Adaptive Moving Average.

        参数:
        ---------
            >>> fastlimit (float): 快线周期. 默认: 0.5
            >>> slowlimit (float): 慢线周期. 默认: 0.05

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 2 条线 — mama_1, mama_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MAMA(fastlimit=0.5, slowlimit=0.05)    # 主图叠加
            >>> out.columns               # 线名: mama_1, mama_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MAMA(close, fastlimit=0.5, slowlimit=0.05)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['mass'])
    def MASS(self, timeperiod: int = 14, sumperiod: int = 25, **kwargs) -> IndSeries:
        """质量指数 · MASS（波动率）
        ---------
            对高低价差的单双EMA比值做滚动求和，用于识别趋势反转，数值高涨后再回落常预示转折。
            原库说明: Mass Index — rolling sum of the single/double EMA ratio of the range.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> sumperiod (int): 计算周期（K 线根数）. 默认: 25

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — mass

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.MASS(timeperiod=14, sumperiod=25)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MASS(high, low, timeperiod=14, sumperiod=25)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['mavp'])
    def MAVP(self, minperiod: int = 2, maxperiod: int = 30, matype: int = 0, **kwargs) -> IndSeries:
        """可变周期均线 · MAVP（趋势）
        ---------
            按每根K线给定的周期计算移动平均，周期会被限制在最小与最大值之间，可自适应调整。
            原库说明: Moving Average with Variable Period.

        参数:
        ---------
            >>> minperiod (int): 计算周期（K 线根数）. 默认: 2
            >>> maxperiod (int): 计算周期（K 线根数）. 默认: 30
            >>> matype (int): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 0

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — mavp

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MAVP(minperiod=2, maxperiod=30, matype=0)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MAVP(close, minperiod=2, maxperiod=30, matype=0)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['max'])
    def MAX(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """滚动最大值 · MAX（统计）
        ---------
            取过去若干根K线内的最大值，用于刻画区间高点、构建通道上轨或突破判断。
            原库说明: Rolling maximum over *timeperiod* bars.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — max

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MAX(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MAX(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['maxindex'])
    def MAXINDEX(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """最大值位置 · MAXINDEX（统计）
        ---------
            返回滚动窗口内最大值所在的绝对下标，用于定位区间高点出现的位置。
            原库说明: Index of the rolling maximum over *timeperiod* bars.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — maxindex

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MAXINDEX(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MAXINDEX(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['ma_envelopes_1', 'ma_envelopes_2', 'ma_envelopes_3'])
    def MA_ENVELOPES(self, timeperiod: int = 14, percent: float = 0.1, matype: int = 0, **kwargs) -> IndFrame:
        """均线包络线 · MA_ENVELOPES（趋势）
        ---------
            以移动平均为中轨、按其百分比上下偏移形成包络，用于判断超买超卖与回归机会。
            原库说明: Moving-average envelopes.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> percent (float): 比例阈值（小数，0.1 = 10%）. 默认: 0.1
            >>> matype (int): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 0

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — ma_envelopes_1, ma_envelopes_2, ma_envelopes_3

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MA_ENVELOPES(timeperiod=14, percent=0.1, matype=0)    # 主图叠加
            >>> out.columns               # 线名: ma_envelopes_1, ma_envelopes_2, ma_envelopes_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MA_ENVELOPES(close, timeperiod=14, percent=0.1, matype=0)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['mcginley'])
    def MCGINLEY(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """麦金利动态均线 · MCGINLEY（趋势）
        ---------
            随价格相对均线偏离程度自动调整速度的动态均线，能贴合趋势并减少震荡噪声。
            原库说明: McGinley Dynamic.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — mcginley

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MCGINLEY(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MCGINLEY(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['median'])
    def MEDIAN(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """滚动中位数 · MEDIAN（统计）
        ---------
            取滚动窗口内数值的中位数，偶数窗口取中间两值平均，对异常值不敏感。
            原库说明: Rolling median.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — median

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MEDIAN(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MEDIAN(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['median_bands_1', 'median_bands_2', 'median_bands_3', 'median_bands_4'])
    def MEDIAN_BANDS(self, timeperiod: int = 14, atr_period: int = 14, multiplier: float = 3.0, **kwargs) -> IndFrame:
        """中位价通道 · MEDIAN_BANDS（波动率）
        ---------
            以最高最低价中值为中线，叠加ATR上下轨及中线EMA。用波动幅度包络价格，可判断趋势与突破区间。
            原库说明: Median of ``(high + low) / 2`` with ATR envelopes and an EMA of the
                median.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> atr_period (int): ATR 计算周期. 默认: 14
            >>> multiplier (float): ATR / 标准差倍数（决定通道与止损宽度）. 默认: 3.0

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 4 条线 — median_bands_1, median_bands_2, median_bands_3, median_bands_4

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.MEDIAN_BANDS(timeperiod=14, atr_period=14, multiplier=3.0)    # 主图叠加
            >>> out.columns               # 线名: median_bands_1, median_bands_2, median_bands_3, median_bands_4
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MEDIAN_BANDS(high, low, close, timeperiod=14, atr_period=14, multiplier=3.0)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['medprice'])
    def MEDPRICE(self, **kwargs) -> IndSeries:
        """中位价 · MEDPRICE（其他）
        ---------
            每根K线最高价与最低价的均值，衡量当根K线的价格中枢，常作为平滑后的价格序列使用。
            原库说明: Median Price: (High + Low) / 2.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — medprice

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.MEDPRICE()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MEDPRICE(high, low)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['mfi'])
    def MFI(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """资金流量指数 · MFI（成交量）
        ---------
            结合典型价格与成交量的动量指标，取值0到100。以70和30判断超买超卖，反映资金进出力度。
            原库说明: Money Flow Index.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — mfi

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.MFI(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MFI(high, low, close, volume, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['midpoint'])
    def MIDPOINT(self, timeperiod: int = 20, **kwargs) -> IndSeries:
        """中点价 · MIDPOINT（统计）
        ---------
            窗口内收盘价最高值与最低值的均值，衡量价格的中间水平，用于平滑价格并判断区间位置。
            原库说明: MidPoint over period — (max + min) / 2 of close.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — midpoint

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MIDPOINT(timeperiod=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MIDPOINT(close, timeperiod=20)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['midprice'])
    def MIDPRICE(self, timeperiod: int = 20, **kwargs) -> IndSeries:
        """中价 · MIDPRICE（统计）
        ---------
            窗口内最高价与最低价的均值，衡量价格区间中枢，常作通道中线与支撑阻力参考。
            原库说明: MidPrice over period — (highest high + lowest low) / 2.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — midprice

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.MIDPRICE(timeperiod=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MIDPRICE(high, low, timeperiod=20)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['min'])
    def MIN(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """滚动最小值 · MIN（统计）
        ---------
            过去timeperiod根内的最低值，用于定位近期低点，辅助判断支撑与区间下界。
            原库说明: Rolling minimum over *timeperiod* bars.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — min

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MIN(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MIN(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['minindex'])
    def MININDEX(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """最小值位置 · MININDEX（统计）
        ---------
            返回滚动窗口内最小值所在的绝对索引，用于定位近期低点出现的时点。
            原库说明: Index of the rolling minimum over *timeperiod* bars.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — minindex

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MININDEX(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MININDEX(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['minus_di'])
    def MINUS_DI(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """负向指标 · MINUS_DI（趋势）
        ---------
            平滑负向动向占真实波幅的比例，衡量空方力量强弱，常与正向指标配合判断趋势方向。
            原库说明: Minus Directional Indicator.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — minus_di

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.MINUS_DI(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MINUS_DI(high, low, close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['minus_dm'])
    def MINUS_DM(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """负向动向 · MINUS_DM（趋势）
        ---------
            当日低点下移幅度的平滑值，衡量向下的方向性运动强度，是负向指标的计算基础。
            原库说明: Minus Directional Movement.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — minus_dm

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.MINUS_DM(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MINUS_DM(high, low, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['mode'])
    def MODE(self, timeperiod: int = 14, bins: int = 10, **kwargs) -> IndSeries:
        """滚动众数 · MODE（统计）
        ---------
            将每个窗口内的值等宽分箱后取样本最多箱的中心，衡量价格最常出现的水平。
            原库说明: Rolling mode via equal-width discretization of each window.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> bins (int): 分箱数量（分布 / 直方图用）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — mode

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MODE(timeperiod=14, bins=10)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MODE(close, timeperiod=14, bins=10)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['mom'])
    def MOM(self, timeperiod: int = 10, **kwargs) -> IndSeries:
        """动量 · MOM（动量）
        ---------
            当前价格与n周期前价格之差，衡量价格上涨或下跌的速度，是趋势强弱的基础度量。
            原库说明: Momentum.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — mom

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MOM(timeperiod=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MOM(close, timeperiod=10)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['mult'])
    def MULT(self, real1=None, **kwargs) -> IndSeries:
        """乘法 · MULT（其他）
        ---------
            两个等长序列逐元素相乘，用于自定义指标或价格变换的组合计算。
            原库说明: Element-wise multiplication: real0 * real1.

        参数:
        ---------
            >>> real1 (值): 第二条价格序列（pd.Series / np.ndarray，长度与 K 线一致，必填）. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — mult

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MULT(real1=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.MULT(close, real1=None)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['natr'])
    def NATR(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """归一化真实波幅 · NATR（波动率）
        ---------
            真实波幅除以收盘价换算为百分比，衡量相对波动率，便于不同品种间比较。
            原库说明: Normalized Average True Range.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — natr

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.NATR(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.NATR(high, low, close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['nvi'])
    def NVI(self, **kwargs) -> IndSeries:
        """负成交量指数 · NVI（成交量）
        ---------
            仅在成交量减少时累计价格涨跌幅的指数，起始值1000，用于追踪所谓聪明资金动向。
            原库说明: Negative Volume Index, seeded at 1000.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — nvi

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.NVI()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.NVI(close, volume)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['nvi_with_ema_1', 'nvi_with_ema_2'])
    def NVI_WITH_EMA(self, timeperiod: int = 14, **kwargs) -> IndFrame:
        """负成交量指数均线 · NVI_WITH_EMA（成交量）
        ---------
            负成交量指数与其EMA信号线，通过两者相对位置观察NVI的强弱变化。
            原库说明: Negative Volume Index plus its EMA signal.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — nvi_with_ema_1, nvi_with_ema_2

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.NVI_WITH_EMA(timeperiod=14)    # 副图
            >>> out.columns               # 线名: nvi_with_ema_1, nvi_with_ema_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.NVI_WITH_EMA(close, volume, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['obv'])
    def OBV(self, **kwargs) -> IndSeries:
        """能量潮 · OBV（成交量）
        ---------
            按价格涨跌方向累加成交量的累积指标，衡量买卖压力，可用于观察量价背离。
            原库说明: On Balance Volume.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — obv

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.OBV()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.OBV(close, volume)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['obv_smoothed'])
    def OBV_SMOOTHED(self, timeperiod: int = 14, matype: int = 0, **kwargs) -> IndSeries:
        """平滑能量潮 · OBV_SMOOTHED（成交量）
        ---------
            对能量潮做SMA或EMA平滑，减少噪声，更清晰地观察量能累积趋势。
            原库说明: On-Balance Volume smoothed with a moving average.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> matype (int): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 0

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — obv_smoothed

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.OBV_SMOOTHED(timeperiod=14, matype=0)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.OBV_SMOOTHED(close, volume, timeperiod=14, matype=0)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['pivot_points_1', 'pivot_points_2', 'pivot_points_3', 'pivot_points_4', 'pivot_points_5'])
    def PIVOT_POINTS(self, method: str = 'classic', **kwargs) -> IndFrame:
        """枢轴点 · PIVOT_POINTS（其他）
        ---------
            用上一根K线的最高、最低、收盘计算枢轴与两级支撑阻力，可选经典、斐波那契或卡玛利拉法。
            原库说明: Pivot Points — support / resistance levels.

        参数:
        ---------
            >>> method (str): 原库参数（默认值见签名）. 默认: 'classic'

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 5 条线 — pivot_points_1, pivot_points_2, pivot_points_3, pivot_points_4, pivot_points_5

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.PIVOT_POINTS(method='classic')    # 主图叠加
            >>> out.columns               # 线名: pivot_points_1, pivot_points_2, pivot_points_3, pivot_points_4, pivot_points_5
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.PIVOT_POINTS(high, low, close, method='classic')
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['plus_di'])
    def PLUS_DI(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """正向指标 · PLUS_DI（趋势）
        ---------
            平滑正向动向占真实波幅的比例，衡量多方力量强弱，与负向指标配合判断趋势。
            原库说明: Plus Directional Indicator.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — plus_di

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.PLUS_DI(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.PLUS_DI(high, low, close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['plus_dm'])
    def PLUS_DM(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """正向动向 · PLUS_DM（趋势）
        ---------
            当日高点上移幅度的平滑值，衡量向上的方向性运动强度，是正向指标的计算基础。
            原库说明: Plus Directional Movement.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — plus_dm

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.PLUS_DM(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.PLUS_DM(high, low, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['po'])
    def PO(self, fastperiod: int = 10, slowperiod: int = 21, **kwargs) -> IndSeries:
        """价格振荡器 · PO（动量）
        ---------
            快慢两期收盘价简单均线之差，衡量短期价格相对长期的偏离，用于判断趋势与动量。
            原库说明: Price Oscillator: SMA(close, fast) − SMA(close, slow).

        参数:
        ---------
            >>> fastperiod (int): 快线周期. 默认: 10
            >>> slowperiod (int): 慢线周期. 默认: 21

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — po

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.PO(fastperiod=10, slowperiod=21)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.PO(close, fastperiod=10, slowperiod=21)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['ppo_1', 'ppo_2', 'ppo_3'])
    def PPO(self, fastperiod: int = 12, slowperiod: int = 26, signalperiod: int = 9, matype: int = 0, **kwargs) -> IndFrame:
        """百分比价格振荡器 · PPO（动量）
        ---------
            快慢均线差值的百分比形式，并给出信号线与柱状值，衡量动量强弱且便于跨品种比较。
            原库说明: Percentage Price Oscillator.

        参数:
        ---------
            >>> fastperiod (int): 快线周期. 默认: 12
            >>> slowperiod (int): 慢线周期. 默认: 26
            >>> signalperiod (int): 信号线平滑周期. 默认: 9
            >>> matype (int): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 0

        返回:
        ---------
            >>> IndFrame: 副图 · 3 条线 — ppo_1, ppo_2, ppo_3

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.PPO(fastperiod=12, slowperiod=26, signalperiod=9, matype=0)    # 副图
            >>> out.columns               # 线名: ppo_1, ppo_2, ppo_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.PPO(close, fastperiod=12, slowperiod=26, signalperiod=9, matype=0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['pvi'])
    def PVI(self, **kwargs) -> IndSeries:
        """正成交量指数 · PVI（成交量）
        ---------
            仅在成交量增加时累计价格涨跌幅的指数，起始值1000，常用来追踪散户资金动向。
            原库说明: Positive Volume Index, seeded at 1000.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — pvi

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.PVI()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.PVI(close, volume)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['pvi_with_signal_1', 'pvi_with_signal_2'])
    def PVI_WITH_SIGNAL(self, timeperiod: int = 14, matype: int = 0, **kwargs) -> IndFrame:
        """正成交量指数信号 · PVI_WITH_SIGNAL（成交量）
        ---------
            正成交量指数与其移动平均信号线，通过两者交叉比较PVI的相对强弱。
            原库说明: Positive Volume Index plus a moving-average signal.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> matype (int): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 0

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — pvi_with_signal_1, pvi_with_signal_2

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.PVI_WITH_SIGNAL(timeperiod=14, matype=0)    # 副图
            >>> out.columns               # 线名: pvi_with_signal_1, pvi_with_signal_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.PVI_WITH_SIGNAL(close, volume, timeperiod=14, matype=0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['pvt'])
    def PVT(self, **kwargs) -> IndSeries:
        """价量趋势 · PVT（成交量）
        ---------
            按价格涨跌幅加权累加成交量，衡量量价配合下形成的累积趋势方向。
            原库说明: Price-Volume Trend.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — pvt

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.PVT()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.PVT(close, volume)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['rising'])
    def RISING(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """上升标记 · RISING（其他）
        ---------
            当前值严格高于timeperiod根前的值时输出1，否则输出0，用于筛选持续上行的序列。
            原库说明: 1.0 when *real* is strictly greater than it was *timeperiod* bars ago.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rising

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.RISING(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.RISING(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['roc'])
    def ROC(self, timeperiod: int = 10, **kwargs) -> IndSeries:
        """变动率 · ROC（动量）
        ---------
            当前价格相对n周期前价格的百分比变动，衡量动量速度与方向，可用于判断超买超卖。
            原库说明: Rate of Change: ((price/prevPrice)-1)*100.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — roc

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ROC(timeperiod=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ROC(close, timeperiod=10)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['rocp'])
    def ROCP(self, timeperiod: int = 10, **kwargs) -> IndSeries:
        """变动率比例 · ROCP（动量）
        ---------
            价格相对n周期前的变化除以原价格，以小数形式衡量涨跌幅度与动量。
            原库说明: Rate of Change Percentage: (price-prevPrice)/prevPrice.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rocp

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ROCP(timeperiod=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ROCP(close, timeperiod=10)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['rocr'])
    def ROCR(self, timeperiod: int = 10, **kwargs) -> IndSeries:
        """变动率比值 · ROCR（动量）
        ---------
            当前价格与n周期前价格之比，以比值形式衡量价格涨跌幅度。
            原库说明: Rate of Change Ratio: price/prevPrice.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rocr

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ROCR(timeperiod=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ROCR(close, timeperiod=10)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['rocr100'])
    def ROCR100(self, timeperiod: int = 10, **kwargs) -> IndSeries:
        """变动率比值100 · ROCR100（动量）
        ---------
            当前价格与n周期前价格之比乘以100，以100为基准衡量价格涨跌比例。
            原库说明: Rate of Change Ratio 100 scale: (price/prevPrice)*100.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rocr100

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ROCR100(timeperiod=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ROCR100(close, timeperiod=10)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['rsi'])
    def RSI(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """相对强弱指数 · RSI（动量）
        ---------
            以平均涨幅与平均跌幅之比换算为0到100，衡量多空力度，常用70与30判断超买超卖。
            原库说明: Relative Strength Index.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rsi

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.RSI(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.RSI(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['rvi_1', 'rvi_2'])
    def RVI(self, timeperiod: int = 14, **kwargs) -> IndFrame:
        """相对活力指数 · RVI（动量）
        ---------
            用收盘价在当日区间中的相对位置衡量趋势活力，并附4周期对称加权均线作信号。
            原库说明: Relative Vigor Index (Ehlers) and 4-bar SWMA signal.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — rvi_1, rvi_2

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.RVI(timeperiod=14)    # 副图
            >>> out.columns               # 线名: rvi_1, rvi_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.RVI(open, high, low, close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['rvol'])
    def RVOL(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """相对成交量 · RVOL（成交量）
        ---------
            成交量除以成交量的移动均值，衡量当前量能相对常态水平的高低。
            原库说明: Relative volume: ``volume / SMA(volume)``.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rvol

        数据:
        ---------
            >>> volume

        使用案例:
        ---------
            >>> out = self.data.RVOL(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.RVOL(volume, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['rwi_1', 'rwi_2'])
    def RWI(self, timeperiod: int = 14, **kwargs) -> IndFrame:
        """随机漫步指数 · RWI（趋势）
        ---------
            价格行程与随机漫步波动之比，分别衡量高点与低点方向；大于1表示趋势强于随机漫步。
            原库说明: Random Walk Index — how far price has travelled versus a random walk.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — rwi_1, rwi_2

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.RWI(timeperiod=14)    # 副图
            >>> out.columns               # 线名: rwi_1, rwi_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.RWI(high, low, close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['sar'])
    def SAR(self, acceleration: float = 0.02, maximum: float = 0.2, **kwargs) -> IndSeries:
        """抛物线转向 · SAR（趋势）
        ---------
            按加速因子逐步跟进的价格转向点，价格位于其上方或下方用于判断趋势方向与出场时机。
            原库说明: Parabolic SAR.

        参数:
        ---------
            >>> acceleration (float): 抛物线加速因子（起步步长，SA 的 0.02）. 默认: 0.02
            >>> maximum (float): 抛物线加速因子上限（SA 的 0.2）. 默认: 0.2

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — sar

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.SAR(acceleration=0.02, maximum=0.2)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.SAR(high, low, acceleration=0.02, maximum=0.2)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['sarext'])
    def SAREXT(self, startvalue: float = 0.0, offsetonreverse: float = 0.0, accelerationinitlong: float = 0.02, accelerationlong: float = 0.02, accelerationmaxlong: float = 0.2, accelerationinitshort: float = 0.02, accelerationshort: float = 0.02, accelerationmaxshort: float = 0.2, **kwargs) -> IndSeries:
        """抛物线转向扩展 · SAREXT（趋势）
        ---------
            抛物线转向的扩展版，多空可分别设定加速因子，并支持固定起始值与反转偏移。
            原库说明: Parabolic SAR Extended.

        参数:
        ---------
            >>> startvalue (float): 原库参数（默认值见签名）. 默认: 0.0
            >>> offsetonreverse (float): 原库参数（默认值见签名）. 默认: 0.0
            >>> accelerationinitlong (float): 比例阈值（小数，0.1 = 10%）. 默认: 0.02
            >>> accelerationlong (float): 比例阈值（小数，0.1 = 10%）. 默认: 0.02
            >>> accelerationmaxlong (float): 比例阈值（小数，0.1 = 10%）. 默认: 0.2
            >>> accelerationinitshort (float): 比例阈值（小数，0.1 = 10%）. 默认: 0.02
            >>> accelerationshort (float): 比例阈值（小数，0.1 = 10%）. 默认: 0.02
            >>> accelerationmaxshort (float): 比例阈值（小数，0.1 = 10%）. 默认: 0.2

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — sarext

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.SAREXT(startvalue=0.0, offsetonreverse=0.0, accelerationinitlong=0.02, accelerationlong=0.02, accelerationmaxlong=0.2, accelerationinitshort=0.02, accelerationshort=0.02, accelerationmaxshort=0.2)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.SAREXT(high, low, startvalue=0.0, offsetonreverse=0.0, accelerationinitlong=0.02, accelerationlong=0.02, accelerationmaxlong=0.2, accelerationinitshort=0.02, accelerationshort=0.02, accelerationmaxshort=0.2)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['sin'])
    def SIN(self, **kwargs) -> IndSeries:
        """正弦 · SIN（其他）
        ---------
            对输入序列逐元素取正弦值，用于数学变换类计算。
            原库说明: Sine (element-wise).

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — sin

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.SIN()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.SIN(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['sinh'])
    def SINH(self, **kwargs) -> IndSeries:
        """双曲正弦 · SINH（其他）
        ---------
            对输入序列逐元素取双曲正弦值，用于数学变换类计算。
            原库说明: Hyperbolic sine (element-wise).

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — sinh

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.SINH()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.SINH(close)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['sma'])
    def SMA(self, timeperiod: int = 20, **kwargs) -> IndSeries:
        """简单移动平均 · SMA（趋势）
        ---------
            窗口内价格的算术平均值，平滑价格波动以显示趋势方向，是最常用的趋势基准线。
            原库说明: Simple Moving Average.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — sma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.SMA(timeperiod=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.SMA(close, timeperiod=20)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['sqrt'])
    def SQRT(self, **kwargs) -> IndSeries:
        """平方根 · SQRT（其他）
        ---------
            对输入序列逐元素开平方，负值输入返回NaN。
            原库说明: Square root (element-wise). Returns NaN for negative inputs.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — sqrt

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.SQRT()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.SQRT(close)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['starc_1', 'starc_2', 'starc_3'])
    def STARC(self, timeperiod: int = 14, atr_period: int = 15, multiplier: float = 3.0, **kwargs) -> IndFrame:
        """斯托勒平均区间通道 · STARC（波动率）
        ---------
            收盘价均线加减ATR倍数构成的上下轨通道，衡量价格相对波动范围的偏离程度。
            原库说明: Stoller Average Range Channels — SMA(close) ± ``multiplier * ATR``.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> atr_period (int): ATR 计算周期. 默认: 15
            >>> multiplier (float): ATR / 标准差倍数（决定通道与止损宽度）. 默认: 3.0

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — starc_1, starc_2, starc_3

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.STARC(timeperiod=14, atr_period=15, multiplier=3.0)    # 主图叠加
            >>> out.columns               # 线名: starc_1, starc_2, starc_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.STARC(high, low, close, timeperiod=14, atr_period=15, multiplier=3.0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['stc'])
    def STC(self, fastperiod: int = 23, slowperiod: int = 50, cycleperiod: int = 10, d1: int = 3, d2: int = 3, **kwargs) -> IndSeries:
        """沙夫趋势周期 · STC（趋势）
        ---------
            结合快慢均线与周期随机化处理，在0到100之间衡量趋势周期的转折与方向。
            原库说明: Schaff Trend Cycle.

        参数:
        ---------
            >>> fastperiod (int): 快线周期. 默认: 23
            >>> slowperiod (int): 慢线周期. 默认: 50
            >>> cycleperiod (int): 计算周期（K 线根数）. 默认: 10
            >>> d1 (int): 原库参数（默认值见签名）. 默认: 3
            >>> d2 (int): 原库参数（默认值见签名）. 默认: 3

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — stc

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.STC(fastperiod=23, slowperiod=50, cycleperiod=10, d1=3, d2=3)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.STC(close, fastperiod=23, slowperiod=50, cycleperiod=10, d1=3, d2=3)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['stddev'])
    def STDDEV(self, timeperiod: int = 20, nbdev: float = 1.0, **kwargs) -> IndSeries:
        """标准差 · STDDEV（统计）
        ---------
            窗口内价格标准差乘以倍数，衡量价格的离散程度即波动大小。
            原库说明: Standard Deviation.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 20
            >>> nbdev (float): 标准差倍数（通道上下轨宽度）. 默认: 1.0

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — stddev

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.STDDEV(timeperiod=20, nbdev=1.0)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.STDDEV(close, timeperiod=20, nbdev=1.0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['k', 'd'])
    def STOCH(self, fastk_period: int = 5, slowk_period: int = 3, slowk_matype: int = 0, slowd_period: int = 3, slowd_matype: int = 0, **kwargs) -> IndFrame:
        """随机指标 · STOCH（动量）
        ---------
            收盘价在区间高低点中的相对位置，输出平滑后的K线与D线，衡量动量与超买超卖。
            原库说明: Stochastic.

        参数:
        ---------
            >>> fastk_period (int): K 线平滑周期. 默认: 5
            >>> slowk_period (int): 计算周期（K 线根数）. 默认: 3
            >>> slowk_matype (int): 慢线周期. 默认: 0
            >>> slowd_period (int): 计算周期（K 线根数）. 默认: 3
            >>> slowd_matype (int): 慢线周期. 默认: 0

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — k, d

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.STOCH(fastk_period=5, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)    # 副图
            >>> out.columns               # 线名: k, d
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.STOCH(high, low, close, fastk_period=5, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['k', 'd'])
    def STOCHF(self, fastk_period: int = 5, fastd_period: int = 3, fastd_matype: int = 0, **kwargs) -> IndFrame:
        """快速随机指标 · STOCHF（动量）
        ---------
            未平滑的快速K线与平滑后的D线，反应更灵敏地衡量收盘价在区间中的位置动量。
            原库说明: Stochastic Fast.

        参数:
        ---------
            >>> fastk_period (int): K 线平滑周期. 默认: 5
            >>> fastd_period (int): D 线平滑周期. 默认: 3
            >>> fastd_matype (int): D 线均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 0

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — k, d

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.STOCHF(fastk_period=5, fastd_period=3, fastd_matype=0)    # 副图
            >>> out.columns               # 线名: k, d
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.STOCHF(high, low, close, fastk_period=5, fastd_period=3, fastd_matype=0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['k', 'd'])
    def STOCHRSI(self, timeperiod: int = 14, fastk_period: int = 5, fastd_period: int = 3, fastd_matype: int = 0, **kwargs) -> IndFrame:
        """随机相对强弱 · STOCHRSI（动量）
        ---------
            对RSI再做随机化处理，衡量RSI在自身历史区间中的位置，用于判断超买超卖。
            原库说明: Stochastic Relative Strength Index.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> fastk_period (int): K 线平滑周期. 默认: 5
            >>> fastd_period (int): D 线平滑周期. 默认: 3
            >>> fastd_matype (int): D 线均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 0

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — k, d

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.STOCHRSI(timeperiod=14, fastk_period=5, fastd_period=3, fastd_matype=0)    # 副图
            >>> out.columns               # 线名: k, d
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.STOCHRSI(close, timeperiod=14, fastk_period=5, fastd_period=3, fastd_matype=0)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['sub'])
    def SUB(self, real1=None, **kwargs) -> IndSeries:
        """减法 · SUB（其他）
        ---------
            两个等长序列逐元素相减，用于自定义指标或价差类计算。
            原库说明: Element-wise subtraction: real0 - real1.

        参数:
        ---------
            >>> real1 (值): 第二条价格序列（pd.Series / np.ndarray，长度与 K 线一致，必填）. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — sub

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.SUB(real1=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.SUB(close, real1=None)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['sum'])
    def SUM(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """滚动求和 · SUM（统计）
        ---------
            过去timeperiod根内数值的滚动之和，常作为其他指标的构造基础。
            原库说明: Rolling sum over *timeperiod* bars.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — sum

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.SUM(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.SUM(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['supertrend_1'])
    def SUPERTREND(self, timeperiod: int = 14, multiplier: float = 3.0, **kwargs) -> IndSeries:
        """超级趋势 · SUPERTREND（趋势）
        ---------
            基于ATR的趋势跟随线，同时给出方向：价格在其上方为上升趋势，下方为下降趋势。
            原库说明: Supertrend indicator.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> multiplier (float): ATR / 标准差倍数（决定通道与止损宽度）. 默认: 3.0

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — supertrend_1

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.SUPERTREND(timeperiod=14, multiplier=3.0)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.SUPERTREND(high, low, close, timeperiod=14, multiplier=3.0)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['t3'])
    def T3(self, timeperiod: int = 20, vfactor: float = 0.7, **kwargs) -> IndSeries:
        """T3均线 · T3（趋势）
        ---------
            多次指数平滑并按体积因子加权的均线，比普通EMA更平滑且滞后更小。
            原库说明: Triple Exponential Moving Average (Tillson T3).

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 20
            >>> vfactor (float): 量能加权系数. 默认: 0.7

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — t3

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.T3(timeperiod=20, vfactor=0.7)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.T3(close, timeperiod=20, vfactor=0.7)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['tan'])
    def TAN(self, **kwargs) -> IndSeries:
        """正切 · TAN（其他）
        ---------
            对输入序列逐元素取正切值，用于数学变换类计算。
            原库说明: Tangent (element-wise).

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — tan

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.TAN()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.TAN(close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['tanh'])
    def TANH(self, **kwargs) -> IndSeries:
        """双曲正切 · TANH（其他）
        ---------
            对输入序列逐元素取双曲正切值，用于数学变换类计算。
            原库说明: Hyperbolic tangent (element-wise).

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — tanh

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.TANH()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.TANH(close)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['tema'])
    def TEMA(self, timeperiod: int = 20, **kwargs) -> IndSeries:
        """三重指数均线 · TEMA（趋势）
        ---------
            由三重EMA组合而成的均线，在保持平滑的同时显著减少滞后，适合趋势跟随。
            原库说明: Triple Exponential Moving Average.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — tema

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.TEMA(timeperiod=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.TEMA(close, timeperiod=20)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['trange'])
    def TRANGE(self, **kwargs) -> IndSeries:
        """真实波幅 · TRANGE（波动率）
        ---------
            取当日最高最低价差与昨收相比的最大波动幅度，是ATR等波动指标的计算基础。
            原库说明: True Range.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — trange

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.TRANGE()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.TRANGE(high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['trima'])
    def TRIMA(self, timeperiod: int = 20, **kwargs) -> IndSeries:
        """三角移动平均 · TRIMA（趋势）
        ---------
            对价格做两次加权平滑得到的均线，平滑度高，对短期噪声不敏感。
            原库说明: Triangular Moving Average.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — trima

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.TRIMA(timeperiod=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.TRIMA(close, timeperiod=20)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['trix'])
    def TRIX(self, timeperiod: int = 10, **kwargs) -> IndSeries:
        """三重指数平滑变动率 · TRIX（动量）
        ---------
            三重指数平滑均线的单周期变动率，过滤短期波动后衡量趋势动量与转折。
            原库说明: 1-day Rate-Of-Change of a Triple Smooth EMA.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — trix

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.TRIX(timeperiod=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.TRIX(close, timeperiod=10)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['tsf'])
    def TSF(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """时间序列预测 · TSF（统计）
        ---------
            用线性回归拟合窗口价格并向前外推一期，输出预测价格，可作趋势参考与信号。
            原库说明: Time Series Forecast — linear regression extrapolated one period ahead.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — tsf

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.TSF(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.TSF(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['tsi_1', 'tsi_2'])
    def TSI(self, longperiod: int = 25, shortperiod: int = 13, signalperiod: int = 13, **kwargs) -> IndFrame:
        """真实强度指数 · TSI（动量）
        ---------
            对价格变动与绝对变动分别双重平滑后取比值，衡量趋势强度并附信号线。
            原库说明: True Strength Index and signal line.

        参数:
        ---------
            >>> longperiod (int): 计算周期（K 线根数）. 默认: 25
            >>> shortperiod (int): 计算周期（K 线根数）. 默认: 13
            >>> signalperiod (int): 信号线平滑周期. 默认: 13

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — tsi_1, tsi_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.TSI(longperiod=25, shortperiod=13, signalperiod=13)    # 副图
            >>> out.columns               # 线名: tsi_1, tsi_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.TSI(close, longperiod=25, shortperiod=13, signalperiod=13)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['typprice'])
    def TYPPRICE(self, **kwargs) -> IndSeries:
        """典型价格 · TYPPRICE（其他）
        ---------
            最高、最低与收盘价三者的平均值，作为单根K线的价格代表，常用于VWAP等计算。
            原库说明: Typical Price: (High + Low + Close) / 3.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — typprice

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.TYPPRICE()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.TYPPRICE(high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['ulcer_index'])
    def ULCER_INDEX(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """溃疡指数 · ULCER_INDEX（波动率）
        ---------
            相对滚动峰值的回撤百分比的均方根，衡量下行风险与持仓的痛苦程度。
            原库说明: Ulcer Index — RMS of percent drawdowns versus the rolling peak.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ulcer_index

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ULCER_INDEX(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ULCER_INDEX(close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['ultosc'])
    def ULTOSC(self, timeperiod1: int = 7, timeperiod2: int = 14, timeperiod3: int = 28, **kwargs) -> IndSeries:
        """终极振荡器 · ULTOSC（动量）
        ---------
            按三个不同周期加权组合的动量振荡器，取值0到100，用于判断超买超卖与背离。
            原库说明: Ultimate Oscillator.

        参数:
        ---------
            >>> timeperiod1 (int): 计算周期（K 线根数）. 默认: 7
            >>> timeperiod2 (int): 计算周期（K 线根数）. 默认: 14
            >>> timeperiod3 (int): 计算周期（K 线根数）. 默认: 28

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ultosc

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.ULTOSC(timeperiod1=7, timeperiod2=14, timeperiod3=28)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ULTOSC(high, low, close, timeperiod1=7, timeperiod2=14, timeperiod3=28)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['var'])
    def VAR(self, timeperiod: int = 20, nbdev: float = 1.0, **kwargs) -> IndSeries:
        """方差 · VAR（统计）
        ---------
            窗口内价格的方差乘以倍数，衡量价格的离散程度与波动大小。
            原库说明: Variance.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 20
            >>> nbdev (float): 标准差倍数（通道上下轨宽度）. 默认: 1.0

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — var

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.VAR(timeperiod=20, nbdev=1.0)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.VAR(close, timeperiod=20, nbdev=1.0)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['vidya'])
    def VIDYA(self, timeperiod: int = 14, cmo_period: int = 9, **kwargs) -> IndSeries:
        """可变指数动态均线 · VIDYA（趋势）
        ---------
            用CMO绝对值缩放松系数的自适应EMA，趋势强时反应加快，震荡时更平滑。
            原库说明: Variable Index Dynamic Average.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14
            >>> cmo_period (int): 计算周期（K 线根数）. 默认: 9

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — vidya

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.VIDYA(timeperiod=14, cmo_period=9)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.VIDYA(close, timeperiod=14, cmo_period=9)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['volosc'])
    def VOLOSC(self, fastperiod: int = 5, slowperiod: int = 10, **kwargs) -> IndSeries:
        """成交量振荡器 · VOLOSC（成交量）
        ---------
            快慢两期成交量均线的百分比差值，衡量成交量相对变化的强弱。
            原库说明: Percentage volume oscillator: ``100 * (fast SMA - slow SMA) / slow SMA``.

        参数:
        ---------
            >>> fastperiod (int): 快线周期. 默认: 5
            >>> slowperiod (int): 慢线周期. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — volosc

        数据:
        ---------
            >>> volume

        使用案例:
        ---------
            >>> out = self.data.VOLOSC(fastperiod=5, slowperiod=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.VOLOSC(volume, fastperiod=5, slowperiod=10)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['vortex_1', 'vortex_2'])
    def VORTEX(self, timeperiod: int = 14, **kwargs) -> IndFrame:
        """涡旋指标 · VORTEX（趋势）
        ---------
            由正向与负向两条VI线组成，通过交叉判断趋势的起始与方向。
            原库说明: Vortex Indicator: ``(+VI, −VI)``.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — vortex_1, vortex_2

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.VORTEX(timeperiod=14)    # 副图
            >>> out.columns               # 线名: vortex_1, vortex_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.VORTEX(high, low, close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['vroc'])
    def VROC(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """成交量变动率 · VROC（成交量）
        ---------
            成交量相对n周期前的变化率，衡量量能的扩张或萎缩程度。
            原库说明: Volume rate of change.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — vroc

        数据:
        ---------
            >>> volume

        使用案例:
        ---------
            >>> out = self.data.VROC(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.VROC(volume, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['vwap'])
    def VWAP(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """成交量加权均价 · VWAP（成交量）
        ---------
            以典型价格按成交量加权的平均价，衡量市场平均持仓成本，可为累计或滚动窗口计算。
            原库说明: Volume Weighted Average Price.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — vwap

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.VWAP(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.VWAP(high, low, close, volume, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['vwma'])
    def VWMA(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """成交量加权均线 · VWMA（趋势）
        ---------
            收盘价按成交量加权的移动平均，衡量有成交量支撑的价格趋势。
            原库说明: Volume Weighted Moving Average.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — vwma

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.VWMA(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.VWMA(close, volume, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['wclprice'])
    def WCLPRICE(self, **kwargs) -> IndSeries:
        """加权收盘价 · WCLPRICE（其他）
        ---------
            最高、最低与两倍收盘价之和的四分之一，更重视收盘价的单根K线代表价格。
            原库说明: Weighted Close Price: (High + Low + Close * 2) / 4.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — wclprice

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.WCLPRICE()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.WCLPRICE(high, low, close)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['williams_fractals_1', 'williams_fractals_2'])
    def WILLIAMS_FRACTALS(self, timeperiod: int = 14, **kwargs) -> IndFrame:
        """威廉分形 · WILLIAMS_FRACTALS（形态）
        ---------
            识别两侧高点均低的高点与两侧低点均高的低点，确认后标记为上下分形，用于寻找转折位。
            原库说明: Williams Fractals — confirmed swing highs and swing lows.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 2 条线 — williams_fractals_1, williams_fractals_2

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.WILLIAMS_FRACTALS(timeperiod=14)    # 主图叠加
            >>> out.columns               # 线名: williams_fractals_1, williams_fractals_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.WILLIAMS_FRACTALS(high, low, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=False, lines=['willr'])
    def WILLR(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """威廉指标 · WILLR（动量）
        ---------
            收盘价相对区间最高价的负向位置，取值-100到0，衡量超买超卖状态。
            原库说明: Williams' %R.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — willr

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.WILLR(timeperiod=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.WILLR(high, low, close, timeperiod=14)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['wma'])
    def WMA(self, timeperiod: int = 20, **kwargs) -> IndSeries:
        """加权移动平均 · WMA（趋势）
        ---------
            按线性递减权重加权的移动平均，比简单均线更重视近期价格，反应更灵敏。
            原库说明: Weighted Moving Average.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — wma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.WMA(timeperiod=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.WMA(close, timeperiod=20)
        """
        ...
    @tobtind(lib="ferro", overlap=True, lines=['zlema'])
    def ZLEMA(self, timeperiod: int = 14, **kwargs) -> IndSeries:
        """零滞后指数均线 · ZLEMA（趋势）
        ---------
            先对价格做滞后误差修正再取EMA，减少滞后的趋势跟随均线。
            原库说明: Zero-Lag Exponential Moving Average.

        参数:
        ---------
            >>> timeperiod (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — zlema

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ZLEMA(timeperiod=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> ferro_ta.ZLEMA(close, timeperiod=14)
        """
        ...
    #: 数据不全 / 不是指标 → desk 不显示（方法仍在）
    NON_KLINE_INDICATORS = ['ADD', 'BETA', 'CDL2CROWS', 'CDL3BLACKCROWS', 'CDL3STARSINSOUTH', 'CDL3WHITESOLDIERS', 'CDLABANDONEDBABY', 'CDLCONCEALBABYSWALL', 'CDLDARKCLOUDCOVER', 'CDLGAPSIDESIDEWHITE', 'CDLKICKING', 'CDLKICKINGBYLENGTH', 'CDLMATHOLD', 'CDLRISEFALL3METHODS', 'CDLTRISTAR', 'CDLUPSIDEGAP2CROWS', 'CORREL', 'CROSS', 'CROSSOVER', 'CROSSUNDER', 'DIV', 'EXREM', 'FALLING', 'FLIP', 'HT_TRENDMODE', 'MULT', 'RISING', 'SUB', 'TANH']
    #: 建议信号（目录 / 技术分析用；**想改就改这张表** ✓）
    SIGNALS = {
        'ADX': {'adx': Threshold(50, 1, label='adx 在 50 上方看多')},
        'ADXR': {'adxr': Threshold(50, 1, label='adxr 在 50 上方看多')},
        'ALMA': {'alma': Compare(-2, 1, label='alma 高于前一根看多')},
        'AO': {'ao': Compare(-2, 1, label='ao 高于前一根看多')},
        'APO': {'apo': Compare(-2, 1, label='apo 高于前一根看多')},
        'ATR': {'atr': Compare(-2, 1, label='atr 高于前一根看多')},
        'CCI': {'cci': Compare(-2, 1, label='cci 高于前一根看多')},
        'CMF': {'cmf': Compare(-2, 1, label='cmf 高于前一根看多')},
        'CMO': {'cmo': Compare(-2, 1, label='cmo 高于前一根看多')},
        'DEMA': {'dema': Compare(-2, 1, label='dema 高于前一根看多')},
        'DMI': {'adx': Threshold(50, 1, label='adx 在 50 上方看多'), 'plus_di': Threshold(50, 1, label='plus_di 在 50 上方看多'), 'minus_di': Threshold(50, 1, label='minus_di 在 50 上方看多')},
        'EMA': {'ema': Compare(-2, 1, label='ema 高于前一根看多')},
        'KAMA': {'kama': Compare(-2, 1, label='kama 高于前一根看多')},
        'MACD': {'macd': Compare(-2, 1, label='macd 高于前一根看多'), 'signal': Compare(-2, 1, label='signal 高于前一根看多'), 'histogram': Compare(-2, 1, label='histogram 高于前一根看多')},
        'MFI': {'mfi': Threshold(50, 1, label='mfi 在 50 上方看多')},
        'OBV': {'obv': Compare(-2, 1, label='obv 高于前一根看多')},
        'PPO': {'ppo_1': Compare(-2, 1, label='ppo_1 高于前一根看多'), 'ppo_2': Compare(-2, 1, label='ppo_2 高于前一根看多'), 'ppo_3': Compare(-2, 1, label='ppo_3 高于前一根看多')},
        'ROC': {'roc': Compare(-2, 1, label='roc 高于前一根看多')},
        'RSI': {'rsi': Threshold(50, 1, label='rsi 在 50 上方看多')},
        'SMA': {'sma': Compare(-2, 1, label='sma 高于前一根看多')},
        'TEMA': {'tema': Compare(-2, 1, label='tema 高于前一根看多')},
        'TRIMA': {'trima': Compare(-2, 1, label='trima 高于前一根看多')},
        'TRIX': {'trix': Compare(-2, 1, label='trix 高于前一根看多')},
        'TSI': {'tsi_1': Compare(-2, 1, label='tsi_1 高于前一根看多'), 'tsi_2': Compare(-2, 1, label='tsi_2 高于前一根看多')},
        'VWAP': {'vwap': Compare(-2, 1, label='vwap 高于前一根看多')},
        'VWMA': {'vwma': Compare(-2, 1, label='vwma 高于前一根看多')},
        'WMA': {'wma': Compare(-2, 1, label='wma 高于前一根看多')},
    }
