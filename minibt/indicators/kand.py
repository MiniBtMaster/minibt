"""**kand** 指标库（第三方库，**可选依赖** ✓）

* 入口：`kline.kand.<指标名>(...)`（前缀 `kand_`）
* 数据源：调用它的 IndFrame 自己（`prices`→`close`、`high/low/open/volume`）
* 共 **59 个指标**；不支持的成员在 `NON_KLINE_INDICATORS` 里（desk 不显示）
* 生成：`scripts/gen_ext_libs.py`（**别手改本文件** ✓）
* docstring：`scripts/gen_ext_lib_docs.py` + `scripts/ext_lib_docs.json`

安装：`py -3.12 -m pip install kand`
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
_INDICATOR_NAMES = ('ad', 'adosc', 'adx', 'adxr', 'aroon', 'aroonosc', 'atr', 'bbands', 'bop', 'cci', 'cdl_doji', 'cdl_dragonfly_doji', 'cdl_gravestone_doji', 'cdl_hammer', 'cdl_inverted_hammer', 'cdl_long_shadow', 'cdl_marubozu', 'dema', 'dx', 'ecl', 'ema', 'macd', 'max', 'medprice', 'mfi', 'midpoint', 'midprice', 'min', 'minus_di', 'minus_dm', 'mom', 'natr', 'obv', 'plus_di', 'plus_dm', 'rma', 'roc', 'rocp', 'rocr', 'rocr100', 'rsi', 'sar', 'sma', 'stddev', 'stoch', 'sum', 'supertrend', 't3', 'tema', 'trange', 'trima', 'trix', 'typprice', 'var', 'vegas', 'vwap', 'wclprice', 'willr', 'wma')


class Kand:
    """## Kand —— kand 指标库（59 个指标）

    kand 是用 Rust 实现的 TA-Lib 风格指标库，接口与 TA-Lib 基本一一对应，数值口径成熟稳定。

    ### 📘 **原库文档**
    - https://pypi.org/project/kand/

    ### 入口与返回
    - 入口：`kline.kand.<指标名>(...)`（前缀 `kand_`）
    - 返回：`IndSeries`（单线）或 `IndFrame`（多线），索引与调用它的 K 线 / 指标对齐
    - 主图 / 副图：装饰器 `overlap=True` 的均线、通道类叠在主图，其余（振荡、量能、统计、形态）在副图

    ### 指标分类（共 59 个）
    **趋势（20）**：adx、adxr、aroon、aroonosc、dema、dx、ema、minus_di、minus_dm、plus_di、plus_dm、rma、sar、sma、supertrend、t3、tema、trima …（共 20 个）
    **动量（14）**：adosc、bop、cci、macd、mfi、mom、roc、rocp、rocr、rocr100、rsi、stoch、trix、willr
    **波动率（4）**：atr、bbands、natr、trange
    **成交量（3）**：ad、obv、vwap
    **形态（7）**：cdl_doji、cdl_dragonfly_doji、cdl_gravestone_doji、cdl_hammer、cdl_inverted_hammer、cdl_long_shadow、cdl_marubozu
    **统计（7）**：max、midpoint、midprice、min、stddev、sum、var
    **其他（4）**：ecl、medprice、typprice、wclprice

    ### 使用说明
    1. 直接调用（返回框架内置指标，可直接画图 / 参与计算）：
    >>> rsi = self.data.rsi(period=14)      # 副图
    >>> ma = self.data.ema(period=20)       # 主图叠加
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
    _perfixes: str = "kand_"
    _df: IndFrame | IndSeries

    def __init__(self, data):
        self._df = data
    @tobtind(lib="kand", overlap=False, lines=['ad'])
    def ad(self, **kwargs) -> IndSeries:
        """累积/派发线 · ad（成交量）
        ---------
            结合价格与成交量衡量资金流入流出的累积线，用于判断买方或卖方压力占优；由高、
            低、收与成交量计算。
            原库说明: Computes the Accumulation/Distribution (A/D) indicator over NumPy arrays.

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
            >>> out = self.data.ad()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.ad(high, low, close, volume)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['adosc'])
    def adosc(self, fast_period: int = 12, slow_period: int = 26, **kwargs) -> IndSeries:
        """累积/派发振荡器 · adosc（动量）
        ---------
            对累积/派发线做快慢两条EMA之差，属动量指标，用于识别趋势强弱与潜在反转；
            参数为快、慢周期。
            原库说明: Calculate Accumulation/Distribution Oscillator (A/D Oscillator or ADOSC)

        参数:
        ---------
            >>> fast_period (int): 快线周期. 默认: 12
            >>> slow_period (int): 慢线周期. 默认: 26

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — adosc

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.adosc(fast_period=12, slow_period=26)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.adosc(high, low, close, volume, fast_period=12, slow_period=26)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['adx'])
    def adx(self, period: int = 14, **kwargs) -> IndSeries:
        """平均趋向指数 · adx（趋势）
        ---------
            衡量趋势强度而不分涨跌，取值0至100，越高趋势越强；由period周期平滑+DM、-DM和真实波幅得出。
            原库说明: Calculate Average Directional Index (ADX) for a NumPy array

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — adx

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.adx(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.adx(high, low, close, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['adxr'])
    def adxr(self, period: int = 14, **kwargs) -> IndSeries:
        """平均趋向指数评级 · adxr（趋势）
        ---------
            将当前ADX与period周期前的ADX取平均，衡量趋势强度变化，可辅助判断趋势的持续与转折。
            原库说明: Calculate Average Directional Index Rating (ADXR) for a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — adxr

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.adxr(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.adxr(high, low, close, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['aroon_up', 'aroon_down'])
    def aroon(self, period: int = 25, **kwargs) -> IndFrame:
        """阿隆指标 · aroon（趋势）
        ---------
            由Aroon Up与Aroon Down两条线组成，用period内距最近最高价/最低价的时间衡量趋势启动与反转。
            原库说明: Calculate Aroon indicator for a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 25

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — aroon_up, aroon_down

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.aroon(period=25)    # 副图
            >>> out.columns               # 线名: aroon_up, aroon_down
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.aroon(high, low, period=25)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['aroonosc'])
    def aroonosc(self, period: int = 25, **kwargs) -> IndSeries:
        """阿隆振荡器 · aroonosc（趋势）
        ---------
            Aroon Up与Aroon Down之差，取值-100至+100，正值示上升趋势，负值示下降趋势，
            用于衡量趋势强度。
            原库说明: Calculate Aroon Oscillator for a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 25

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — aroonosc

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.aroonosc(period=25)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.aroonosc(high, low, period=25)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['atr'])
    def atr(self, period: int = 14, **kwargs) -> IndSeries:
        """平均真实波幅 · atr（波动率）
        ---------
            通过分解period内资产价格的全部波动区间来衡量市场波动性，数值越高波动越大，
            常用于设止损。
            原库说明: Computes the Average True Range (ATR) over NumPy arrays.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — atr

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.atr(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.atr(high, low, close, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['upper', 'middle', 'lower'])
    def bbands(self, period: int = 20, dev_up: float = 2.0, dev_down: float = 2.0, **kwargs) -> IndFrame:
        """布林带 · bbands（波动率）
        ---------
            以period周期简单均线为中轨，上下轨各加减dev_up/dev_down倍标准差，用于判断价格波动区间与超买超卖。
            原库说明: Calculate Bollinger Bands for a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20
            >>> dev_up (float): 宽度 / 倍数系数. 默认: 2.0
            >>> dev_down (float): 宽度 / 倍数系数. 默认: 2.0

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — upper, middle, lower

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.bbands(period=20, dev_up=2.0, dev_down=2.0)    # 主图叠加
            >>> out.columns               # 线名: upper, middle, lower
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.bbands(close, period=20, dev_up=2.0, dev_down=2.0)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['bop'])
    def bop(self, **kwargs) -> IndSeries:
        """力量平衡指标 · bop（动量）
        ---------
            用收盘价与开盘价之差除以最高最低价区间，衡量买卖双方相对强弱，为一种动量振荡指标。
            原库说明: Calculate Balance of Power (BOP) indicator for NumPy arrays.

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
            >>> out = self.data.bop()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.bop(open, high, low, close)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['cci'])
    def cci(self, period: int = 20, **kwargs) -> IndSeries:
        """顺势指标 · cci（动量）
        ---------
            基于period周期典型价格与其均值的偏离程度的动量振荡器，用于判断超买超卖及价格异常偏离。
            原库说明: Computes the Commodity Channel Index (CCI) over NumPy arrays.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cci

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.cci(period=20)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.cci(high, low, close, period=20)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['cdl_doji'])
    def cdl_doji(self, body_percent: float = 0.1, shadow_equal_percent: float = 0.1, **kwargs) -> IndSeries:
        """十字星 · cdl_doji（形态）
        ---------
            识别实体极小且上下影线相近的十字星K线，反映多空僵持；body_percent与shadow_equal_percent控制阈值。
            原库说明: Detects Doji candlestick patterns in price data.

        参数:
        ---------
            >>> body_percent (float): 最小实体占比（占整根振幅的比例）. 默认: 0.1
            >>> shadow_equal_percent (float): 两根影线等长的容差. 默认: 0.1

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdl_doji

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.cdl_doji(body_percent=0.1, shadow_equal_percent=0.1)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.cdl_doji(open, high, low, close, body_percent=0.1, shadow_equal_percent=0.1)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['cdl_dragonfly_doji'])
    def cdl_dragonfly_doji(self, body_percent: float = 0.1, **kwargs) -> IndSeries:
        """蜻蜓十字线 · cdl_dragonfly_doji（形态）
        ---------
            识别实体小、长下影线且几无上影的蜻蜓十字线，属看涨形态，返回100表示检出、
            0表示无；body_percent控阈值。
            原库说明: Detects Dragonfly Doji candlestick patterns in price data.

        参数:
        ---------
            >>> body_percent (float): 最小实体占比（占整根振幅的比例）. 默认: 0.1

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdl_dragonfly_doji

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.cdl_dragonfly_doji(body_percent=0.1)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.cdl_dragonfly_doji(open, high, low, close, body_percent=0.1)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['cdl_gravestone_doji'])
    def cdl_gravestone_doji(self, body_percent: float = 0.1, **kwargs) -> IndSeries:
        """墓碑十字线 · cdl_gravestone_doji（形态）
        ---------
            识别实体小、长上影线且几无下影的墓碑十字线，属看跌形态，返回-100表示检出、
            0表示无；body_percent控阈值。
            原库说明: Detects Gravestone Doji candlestick patterns in price data.

        参数:
        ---------
            >>> body_percent (float): 最小实体占比（占整根振幅的比例）. 默认: 0.1

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdl_gravestone_doji

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.cdl_gravestone_doji(body_percent=0.1)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.cdl_gravestone_doji(open, high, low, close, body_percent=0.1)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['cdl_hammer'])
    def cdl_hammer(self, period: int = 14, factor: float = 0.5, **kwargs) -> IndSeries:
        """锤头线 · cdl_hammer（形态）
        ---------
            识别下影线远长于实体的看涨锤头形态，返回100表示检出；period为实体EMA周期，
            factor为影线/实体下限比。
            原库说明: Detects Hammer candlestick patterns in price data.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> factor (float): 灵敏度系数（宽度 / 阈值 / 加速步长）. 默认: 0.5

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdl_hammer

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.cdl_hammer(period=14, factor=0.5)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.cdl_hammer(open, high, low, close, period=14, factor=0.5)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['cdl_inverted_hammer'])
    def cdl_inverted_hammer(self, period: int = 14, factor: float = 0.5, **kwargs) -> IndSeries:
        """倒锤头线 · cdl_inverted_hammer（形态）
        ---------
            识别上影线远长于实体的看涨倒锤头形态，返回100表示检出；period为实体EMA周期，
            factor为影线/实体下限比。
            原库说明: Detects Inverted Hammer candlestick patterns in price data.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> factor (float): 灵敏度系数（宽度 / 阈值 / 加速步长）. 默认: 0.5

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdl_inverted_hammer

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.cdl_inverted_hammer(period=14, factor=0.5)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.cdl_inverted_hammer(open, high, low, close, period=14, factor=0.5)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['cdl_long_shadow'])
    def cdl_long_shadow(self, period: int = 14, shadow_factor: float = 2.0, **kwargs) -> IndSeries:
        """长影线 · cdl_long_shadow（形态）
        ---------
            识别影线占整体区间比例较大的K线：长下影返回100看涨，长上影返回-100看跌；
            period为实体EMA周期。
            原库说明: Detects Long Shadow candlestick patterns in price data.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> shadow_factor (float): 影线长度倍数. 默认: 2.0

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdl_long_shadow

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.cdl_long_shadow(period=14, shadow_factor=2.0)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.cdl_long_shadow(open, high, low, close, period=14, shadow_factor=2.0)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['cdl_marubozu'])
    def cdl_marubozu(self, period: int = 14, shadow_percent: float = 0.1, **kwargs) -> IndSeries:
        """光头光脚线 · cdl_marubozu（形态）
        ---------
            识别几乎无影线的马鲁波祖K线，实体为阳返回1、为阴返回-1；shadow_percent限影线占实体比例，
            period用于实体EMA。
            原库说明: Detects Marubozu candlestick patterns in price data.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> shadow_percent (float): 影线最小占比. 默认: 0.1

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cdl_marubozu

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.cdl_marubozu(period=14, shadow_percent=0.1)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.cdl_marubozu(open, high, low, close, period=14, shadow_percent=0.1)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['dema'])
    def dema(self, period: int = 20, **kwargs) -> IndSeries:
        """双指数移动平均 · dema（趋势）
        ---------
            由两条EMA组合而成，在保留平滑的同时减少滞后，常作趋势跟踪线；period为EMA平滑周期。
            原库说明: Calculates Double Exponential Moving Average (DEMA) over NumPy arrays.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — dema

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.dema(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.dema(close, period=20)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['dx'])
    def dx(self, period: int = 14, **kwargs) -> IndSeries:
        """动向指数 · dx（趋势）
        ---------
            通过比较正向与负向方向运动衡量趋势强度，是ADX计算的中间量；period为平滑窗口。
            原库说明: Computes the Directional Movement Index (DX) over NumPy arrays.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — dx

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.dx(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.dx(high, low, close, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['ecl'])
    def ecl(self, **kwargs) -> IndSeries:
        """扩展卡玛利拉位 · ecl（其他）
        ---------
            依据上一周期的最高、最低与收盘价计算H5至L5共十档支撑与阻力位，常用于日内区间交易参考。
            原库说明: Computes the Expanded Camarilla Levels (ECL) over NumPy arrays.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — ecl

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.ecl()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.ecl(high, low, close)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['ema'])
    def ema(self, period: int = 20, k: float | None = None, **kwargs) -> IndSeries:
        """指数移动平均 · ema（趋势）
        ---------
            对近期价格赋予更高权重的移动平均，公式为价格乘k加前值乘(1-k)；period为窗口，
            k可自定义平滑系数。
            原库说明: Computes the Exponential Moving Average (EMA) over a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20
            >>> k (float): 平滑 / 放大系数（原库同名参数）. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — ema

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ema(period=20, k=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.ema(close, period=20, k=None)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['macd', 'signal', 'histogram'], linestyle={'histogram': LineStyle(line_dash=LineDash.vbar, vbar_base=0.0, vbar_up_color=Colors.bull_color, vbar_down_color=Colors.bear_color)})
    def macd(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9, **kwargs) -> IndFrame:
        """MACD · macd（动量）
        ---------
            由快慢EMA之差构成MACD线，其EMA为信号线，两者之差为柱状图，用于跟踪趋势动能与金叉死叉信号。
            原库说明: Computes the Moving Average Convergence Divergence (MACD) over a NumPy
                array.

        参数:
        ---------
            >>> fast_period (int): 快线周期. 默认: 12
            >>> slow_period (int): 慢线周期. 默认: 26
            >>> signal_period (int): 信号线平滑周期. 默认: 9

        返回:
        ---------
            >>> IndFrame: 副图 · 3 条线 — macd, signal, histogram

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.macd(fast_period=12, slow_period=26, signal_period=9)    # 副图
            >>> out.columns               # 线名: macd, signal, histogram
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.macd(close, fast_period=12, slow_period=26, signal_period=9)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['max'])
    def max(self, period: int = 14, **kwargs) -> IndSeries:
        """区间最大值 · max（统计）
        ---------
            求period周期窗口内价格的最大值，常用作上方压力或通道边界参考。
            原库说明: Calculate Maximum Value for a NumPy array

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — max

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.max(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.max(close, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['medprice'])
    def medprice(self, **kwargs) -> IndSeries:
        """中位价 · medprice（其他）
        ---------
            取每周期最高价与最低价的中间点作为价格代表值，常用于构造其他指标的输入价格。
            原库说明: Calculates the Median Price (MEDPRICE) for a NumPy array.

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
            >>> out = self.data.medprice()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.medprice(high, low)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['mfi'])
    def mfi(self, period: int = 14, **kwargs) -> IndSeries:
        """资金流量指标 · mfi（动量）
        ---------
            结合价格与成交量构造资金流，period内比较正负资金流得出0至100的振荡值，用于判断超买超卖。
            原库说明: Calculates the Money Flow Index (MFI) for a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — mfi

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.mfi(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.mfi(high, low, close, volume, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['midpoint'])
    def midpoint(self, period: int = 20, **kwargs) -> IndSeries:
        """中点值 · midpoint（统计）
        ---------
            计算period周期内最高值与最低值的算术平均，反映价格区间的中心位置，可作为支撑阻力参考。
            原库说明: Calculates Midpoint values for a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — midpoint

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.midpoint(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.midpoint(close, period=20)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['midprice'])
    def midprice(self, period: int = 20, **kwargs) -> IndSeries:
        """区间中价 · midprice（统计）
        ---------
            计算period周期内最高价与最低价的中点值，反映区间中心，常用作支撑阻力与趋势参考线。
            原库说明: Calculates Midpoint Price values for a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — midprice

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.midprice(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.midprice(high, low, period=20)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['min'])
    def min(self, period: int = 14, **kwargs) -> IndSeries:
        """区间最小值 · min（统计）
        ---------
            求period周期窗口内价格的最小值，常用作下方支撑或通道边界参考。
            原库说明: Calculate Minimum Value (MIN) for a NumPy array

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — min

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.min(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.min(close, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['minus_di'])
    def minus_di(self, period: int = 14, **kwargs) -> IndSeries:
        """负向指标 · minus_di（趋势）
        ---------
            衡量下降趋势的存在与强度，由平滑后的-DM与真实波幅相比得出，是计算ADX的分量之一。
            原库说明: Computes the Minus Directional Indicator (-DI) over NumPy arrays.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — minus_di

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.minus_di(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.minus_di(high, low, close, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['minus_dm'])
    def minus_dm(self, period: int = 14, **kwargs) -> IndSeries:
        """负向动向 · minus_dm（趋势）
        ---------
            衡量价格向下运动幅度，为Wilder动向系统中的组成部分；period为平滑窗口。
            原库说明: Computes the Minus Directional Movement (-DM) over NumPy arrays.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — minus_dm

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.minus_dm(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.minus_dm(high, low, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['mom'])
    def mom(self, period: int = 10, **kwargs) -> IndSeries:
        """动量 · mom（动量）
        ---------
            计算当前价格与period周期前价格之差，正值示上涨动能、负值示下跌动能，是最基础的动量指标。
            原库说明: Computes the Momentum (MOM) over a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — mom

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.mom(period=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.mom(close, period=10)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['natr'])
    def natr(self, period: int = 14, **kwargs) -> IndSeries:
        """归一化平均真实波幅 · natr（波动率）
        ---------
            将ATR表示为收盘价的百分比，消除价格水平影响，便于跨品种比较波动性；period为ATR窗口。
            原库说明: Computes the Normalized Average True Range (NATR) over NumPy arrays.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — natr

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.natr(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.natr(high, low, close, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['obv'])
    def obv(self, **kwargs) -> IndSeries:
        """能量潮 · obv（成交量）
        ---------
            按收盘涨跌方向累加或减去成交量，用成交量流向预测价格变化，量增价平往往预示后续突破。
            原库说明: Computes the On Balance Volume (OBV) over NumPy arrays.

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
            >>> out = self.data.obv()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.obv(close, volume)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['plus_di'])
    def plus_di(self, period: int = 14, **kwargs) -> IndSeries:
        """正向指标 · plus_di（趋势）
        ---------
            衡量上升趋势的存在与强度，由平滑后的+DM与真实波幅相比得出，是计算ADX的分量之一。
            原库说明: Computes the Plus Directional Indicator (+DI) over NumPy arrays.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — plus_di

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.plus_di(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.plus_di(high, low, close, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['plus_dm'])
    def plus_dm(self, period: int = 14, **kwargs) -> IndSeries:
        """正向动向 · plus_dm（趋势）
        ---------
            衡量价格向上运动幅度，为Wilder动向系统中的组成部分；period为平滑窗口。
            原库说明: Computes the Plus Directional Movement (+DM) over NumPy arrays.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — plus_dm

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.plus_dm(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.plus_dm(high, low, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['rma'])
    def rma(self, period: int = 20, **kwargs) -> IndSeries:
        """运行移动平均 · rma（趋势）
        ---------
            类似EMA但平滑系数为1/period的移动平均，对当前值与前期RMA加权，常用于Wilder类指标的平滑。
            原库说明: Computes the Running Moving Average (RMA) over a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — rma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.rma(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.rma(close, period=20)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['roc'])
    def roc(self, period: int = 10, **kwargs) -> IndSeries:
        """变动率 · roc（动量）
        ---------
            计算当前价格相对period周期前价格的百分比变化，正值示上涨、负值示下跌，用于衡量动量强弱。
            原库说明: Computes the Rate of Change (ROC) over a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — roc

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.roc(period=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.roc(close, period=10)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['rocp'])
    def rocp(self, period: int = 10, **kwargs) -> IndSeries:
        """变动率百分比 · rocp（动量）
        ---------
            以小数形式表示当前价格相对period周期前价格的百分比变化，用于衡量价格动量与变化速度。
            原库说明: Computes the Rate of Change Percentage (ROCP) over a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rocp

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.rocp(period=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.rocp(close, period=10)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['rocr'])
    def rocr(self, period: int = 10, **kwargs) -> IndSeries:
        """变动率比值 · rocr（动量）
        ---------
            计算当前价格与period周期前价格的比值，大于1示上涨、小于1示下跌，用于衡量价格动量。
            原库说明: Computes the Rate of Change Ratio (ROCR) over a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rocr

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.rocr(period=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.rocr(close, period=10)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['rocr100'])
    def rocr100(self, period: int = 10, **kwargs) -> IndSeries:
        """变动率比值×100 · rocr100（动量）
        ---------
            当前价格与period周期前价格比值乘以100，高于100表示价格上涨、低于100表示下跌，
            用于衡量动量。
            原库说明: Computes the Rate of Change Ratio * 100 (ROCR100) over a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rocr100

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.rocr100(period=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.rocr100(close, period=10)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['rsi'])
    def rsi(self, period: int = 14, **kwargs) -> IndSeries:
        """相对强弱指数 · rsi（动量）
        ---------
            以period内平均涨幅与平均跌幅之比衡量价格变化的速度与幅度，用于判断超买超卖状态。
            原库说明: Computes the Relative Strength Index (RSI) over NumPy arrays.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rsi

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.rsi(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.rsi(close, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['sar'])
    def sar(self, acceleration: float = 0.02, maximum: float = 0.2, **kwargs) -> IndSeries:
        """抛物线转向 · sar（趋势）
        ---------
            以加速因子与极值点计算的抛物线止损转向点，点位在价格下方示多头、上方示空头，
            用于跟踪趋势与反转。
            原库说明: Calculates the Parabolic SAR (Stop And Reverse) indicator over NumPy
                arrays.

        参数:
        ---------
            >>> acceleration (float): 抛物线加速因子（起步步长，SA 的 0.02）. 默认: 0.02
            >>> maximum (float): 抛物线加速因子上限（SA 的 0.2）. 默认: 0.2

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — sar

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.sar(acceleration=0.02, maximum=0.2)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.sar(high, low, acceleration=0.02, maximum=0.2)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['sma'])
    def sma(self, period: int = 20, **kwargs) -> IndSeries:
        """简单移动平均 · sma（趋势）
        ---------
            对period周期窗口内的数据取算术平均并逐点滚动，是最基础的平滑趋势线与均线交叉依据。
            原库说明: Computes the Simple Moving Average (SMA) over a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — sma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.sma(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.sma(close, period=20)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['stddev'])
    def stddev(self, period: int = 20, **kwargs) -> IndSeries:
        """标准差 · stddev（统计）
        ---------
            计算period周期内数值相对均值的离散程度（方差的平方根），反映波动大小，是布林带等指标的基础。
            原库说明: Calculate Standard Deviation for a NumPy array

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — stddev

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.stddev(period=20)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.stddev(close, period=20)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['k', 'd'])
    def stoch(self, k_period: int = 14, k_slow_period: int = 3, d_period: int = 3, **kwargs) -> IndFrame:
        """随机指标 · stoch（动量）
        ---------
            衡量收盘价在period内高低区间中的相对位置，含%K快线与%D慢线，用于判断超买超卖与转折。
            原库说明: Computes the Stochastic Oscillator indicator over NumPy arrays.

        参数:
        ---------
            >>> k_period (int): K 线平滑周期. 默认: 14
            >>> k_slow_period (int): 计算周期（K 线根数）. 默认: 3
            >>> d_period (int): D 线平滑周期. 默认: 3

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — k, d

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.stoch(k_period=14, k_slow_period=3, d_period=3)    # 副图
            >>> out.columns               # 线名: k, d
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.stoch(high, low, close, k_period=14, k_slow_period=3, d_period=3)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['sum'])
    def sum(self, period: int = 14, **kwargs) -> IndSeries:
        """滚动求和 · sum（统计）
        ---------
            计算period周期窗口内数值的滚动总和，常作为成交量或价差等数据的累计参考。
            原库说明: Calculate Sum for a NumPy array

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — sum

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.sum(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.sum(close, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['trend', 'supertrend'])
    def supertrend(self, period: int = 14, multiplier: float = 3.0, **kwargs) -> IndFrame:
        """超级趋势 · supertrend（趋势）
        ---------
            结合ATR与上下轨判断趋势方向（1为上升、-1为下降）并给出转向点；period为ATR周期，
            multiplier为ATR倍数。
            原库说明: Computes the Supertrend indicator over NumPy arrays.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> multiplier (float): ATR / 标准差倍数（决定通道与止损宽度）. 默认: 3.0

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 2 条线 — trend, supertrend

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.supertrend(period=14, multiplier=3.0)    # 主图叠加
            >>> out.columns               # 线名: trend, supertrend
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.supertrend(high, low, close, period=14, multiplier=3.0)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['t3'])
    def t3(self, period: int = 20, vfactor: float = 0.7, **kwargs) -> IndSeries:
        """T3均线 · t3（趋势）
        ---------
            Tillson提出的六重EMA加权组合均线，在保持平滑的同时显著降低滞后；period为平滑周期，
            vfactor控制权重。
            原库说明: Computes the T3 (Triple Exponential Moving Average) indicator over a NumPy
                array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20
            >>> vfactor (float): 量能加权系数. 默认: 0.7

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — t3

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.t3(period=20, vfactor=0.7)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.t3(close, period=20, vfactor=0.7)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['tema'])
    def tema(self, period: int = 20, **kwargs) -> IndSeries:
        """三重指数移动平均 · tema（趋势）
        ---------
            对价格做三重指数平滑以减少滞后并保持平滑性，更重视近期数据，常作趋势跟踪均线；
            period为平滑周期。
            原库说明: Calculate Triple Exponential Moving Average (TEMA) for a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — tema

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.tema(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.tema(close, period=20)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['trange'])
    def trange(self, **kwargs) -> IndSeries:
        """真实波幅 · trange（波动率）
        ---------
            综合当日最高最低区间与前一收盘价衡量市场波动，是ATR等波动率指标的计算基础。
            原库说明: Computes the True Range (TR) over NumPy arrays.

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
            >>> out = self.data.trange()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.trange(high, low, close)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['trima'])
    def trima(self, period: int = 20, **kwargs) -> IndSeries:
        """三角移动平均 · trima（趋势）
        ---------
            经两次平滑的均线，对序列中段赋予更高权重、两端更低，比简单均线更平滑；period为平滑周期。
            原库说明: Calculate Triangular Moving Average (TRIMA) for a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — trima

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.trima(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.trima(close, period=20)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['trix'])
    def trix(self, period: int = 10, **kwargs) -> IndSeries:
        """三重指数平滑振荡器 · trix（动量）
        ---------
            对三重指数平滑均线求变动率，用于识别超买超卖，并可通过与价格背离发现潜在趋势反转。
            原库说明: Calculates the Triple Exponential Moving Average Oscillator (TRIX) over a
                NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — trix

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.trix(period=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.trix(close, period=10)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['typprice'])
    def typprice(self, **kwargs) -> IndSeries:
        """典型价格 · typprice（其他）
        ---------
            取每周期最高价、最低价与收盘价的算术平均作为价格代表值，常作为其他指标的输入价格。
            原库说明: Computes the Typical Price over NumPy arrays.

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
            >>> out = self.data.typprice()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.typprice(high, low, close)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['var'])
    def var(self, period: int = 20, **kwargs) -> IndSeries:
        """方差 · var（统计）
        ---------
            计算period周期内数据点相对均值的平均平方偏差，衡量数值离散程度与波动大小。
            原库说明: Calculate Variance (VAR) for a NumPy array

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — var

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.var(period=20)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.var(close, period=20)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['vegas'])
    def vegas(self, **kwargs) -> IndSeries:
        """VEGAS通道 · vegas（趋势）
        ---------
            用多条EMA（144、169与576、676）构成趋势通道与边界，判断趋势方向及动态支撑阻力。
            原库说明: Computes the VEGAS (Volume and EMA Guided Adaptive Scaling) indicator over
                NumPy arrays.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — vegas

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.vegas()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.vegas(close)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['vwap'])
    def vwap(self, **kwargs) -> IndSeries:
        """成交量加权平均价 · vwap（成交量）
        ---------
            以典型价格乘成交量做累积加权平均，反映市场真实持仓成本，常作日内多空分界的支撑阻力。
            原库说明: Calculates Volume Weighted Average Price (VWAP) for a series of price
                data.

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — vwap

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.vwap()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.vwap(high, low, close, volume)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['wclprice'])
    def wclprice(self, **kwargs) -> IndSeries:
        """加权收盘价 · wclprice（其他）
        ---------
            对收盘价赋予更高权重的加权价（高+低+2×收）/4，突出收盘表现，可作为其他指标的输入价格。
            原库说明: Calculates the Weighted Close Price (WCLPRICE) for a series of price data.

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
            >>> out = self.data.wclprice()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.wclprice(high, low, close)
        """
        ...
    @tobtind(lib="kand", overlap=False, lines=['willr'])
    def willr(self, period: int = 14, **kwargs) -> IndSeries:
        """威廉指标 · willr（动量）
        ---------
            比较收盘价与period内最高最低价区间，取值0至-100，用于判断超买超卖与反转时机。
            原库说明: Calculates Williams %R (Williams Percent Range) for a series of prices.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — willr

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.willr(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.willr(high, low, close, period=14)
        """
        ...
    @tobtind(lib="kand", overlap=True, lines=['wma'])
    def wma(self, period: int = 20, **kwargs) -> IndSeries:
        """加权移动平均 · wma（趋势）
        ---------
            对period内各价格赋予线性递减权重，越近的价格权重越高，较简单均线更灵敏，
            用于趋势跟踪。
            原库说明: Computes the Weighted Moving Average (WMA) over a NumPy array.

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — wma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.wma(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> kand.wma(close, period=20)
        """
        ...
    #: 数据不全 / 不是指标 → desk 不显示（方法仍在）
    NON_KLINE_INDICATORS = ['cdl_doji', 'sar', 'vegas']
    #: 建议信号（目录 / 技术分析用；**想改就改这张表** ✓）
    SIGNALS = {
        'adx': {'adx': Compare(-2, 1, label='adx 高于前一根看多')},
        'adxr': {'adxr': Compare(-2, 1, label='adxr 高于前一根看多')},
        'aroon': {'aroon_up': Compare(-2, 1, label='aroon_up 高于前一根看多'), 'aroon_down': Compare(-2, 1, label='aroon_down 高于前一根看多')},
        'aroonosc': {'aroonosc': Compare(-2, 1, label='aroonosc 高于前一根看多')},
        'atr': {'atr': Compare(-2, 1, label='atr 高于前一根看多')},
        'bbands': {'upper': Compare(-2, 1, label='upper 高于前一根看多'), 'middle': Compare(-2, 1, label='middle 高于前一根看多'), 'lower': Compare(-2, 1, label='lower 高于前一根看多')},
        'cci': {'cci': Compare(-2, 1, label='cci 高于前一根看多')},
        'dx': {'dx': Compare(-2, 1, label='dx 高于前一根看多')},
        'ema': {'ema': Compare(-2, 1, label='ema 高于前一根看多')},
        'macd': {'macd': Compare(-2, 1, label='macd 高于前一根看多'), 'signal': Compare(-2, 1, label='signal 高于前一根看多'), 'histogram': Compare(-2, 1, label='histogram 高于前一根看多')},
        'mfi': {'mfi': Compare(-2, 1, label='mfi 高于前一根看多')},
        'mom': {'mom': Compare(-2, 1, label='mom 高于前一根看多')},
        'obv': {'obv': Compare(-2, 1, label='obv 高于前一根看多')},
        'rma': {'rma': Compare(-2, 1, label='rma 高于前一根看多')},
        'roc': {'roc': Compare(-2, 1, label='roc 高于前一根看多')},
        'rsi': {'rsi': Compare(-2, 1, label='rsi 高于前一根看多')},
        'sma': {'sma': Compare(-2, 1, label='sma 高于前一根看多')},
        'stoch': {'k': Compare(-2, 1, label='k 高于前一根看多'), 'd': Compare(-2, 1, label='d 高于前一根看多')},
        'supertrend': {'trend': Compare(-2, 1, label='trend 高于前一根看多'), 'supertrend': Compare(-2, 1, label='supertrend 高于前一根看多')},
        'trix': {'trix': Compare(-2, 1, label='trix 高于前一根看多')},
        'vwap': {'vwap': Compare(-2, 1, label='vwap 高于前一根看多')},
        'willr': {'willr': Compare(-2, 1, label='willr 高于前一根看多')},
        'wma': {'wma': Compare(-2, 1, label='wma 高于前一根看多')},
    }
