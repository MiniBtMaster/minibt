"""**tulip-rs** 指标库（第三方库，**可选依赖** ✓）

* 入口：`kline.tulip_rs.<指标名>(...)`（前缀 `tulip_`）
* 数据源：调用它的 IndFrame 自己（`prices`→`close`、`high/low/open/volume`）
* 共 **88 个指标**；不支持的成员在 `NON_KLINE_INDICATORS` 里（desk 不显示）
* 生成：`scripts/gen_ext_libs.py`（**别手改本文件** ✓）
* docstring：`scripts/gen_ext_lib_docs.py` + `scripts/ext_lib_docs.json`

安装：`py -3.12 -m pip install tulip`
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
_INDICATOR_NAMES = ('AD', 'ADAPTIVEMSW', 'ADOSC', 'ADX', 'ADXR', 'AO', 'APO', 'AROON', 'AROONOSC', 'ATR', 'AVGPRICE', 'BBANDS', 'BOP', 'CCI', 'CHAIKINMF', 'CHANDELIEREXIT', 'CMO', 'CVI', 'DEMA', 'DI', 'DM', 'DONCHIANCHANNEL', 'DPO', 'DX', 'EF', 'ELDERRAY', 'EMA', 'EMV', 'FISHER', 'FOSC', 'HIGHPASS', 'HILBERTTRANSFORM', 'HMA', 'HOMODYNEDISCRIMINATOR', 'ICHIMOKU', 'INSTANTANEOUSTRENDLINE', 'KAMA', 'KELTNERCHANNEL', 'KVO', 'LINREG', 'MACD', 'MARKETFI', 'MASS', 'MAX', 'MD', 'MEDPRICE', 'MFI', 'MIN', 'MOM', 'MSW', 'NATR', 'NVI', 'OBV', 'PIVOTPOINT', 'PPO', 'PSAR', 'PVI', 'QSTICK', 'ROC', 'ROCR', 'ROOFINGFILTER', 'RSI', 'SMA', 'SMAENVELOPE', 'STDDEV', 'STOCH', 'STOCHRSI', 'SUPERSMOOTHER', 'SUPERTREND', 'TEMA', 'TR', 'TRIMA', 'TRIX', 'TRVI', 'TSF', 'TYPPRICE', 'VHF', 'VOLATILITY', 'VORTEX', 'VOSC', 'VWAP', 'VWMA', 'WAD', 'WCPRICE', 'WILDERS', 'WILLR', 'WMA', 'ZLEMA')


class TulipRS:
    """## TulipRS —— tulip-rs 指标库（88 个指标）

    tulip-rs 是 Tulip Indicators 的 Rust 绑定，经典、轻量、数值稳定，每个指标都很小很快。

    ### 📘 **原库文档**
    - https://pypi.org/project/tulip-rs/

    ### 入口与返回
    - 入口：`kline.tulip_rs.<指标名>(...)`（前缀 `tulip_`）
    - 注意：`kline.tulip` 是**另一家** tulipy（`TuLip`，小写方法名）——
      两者同名但命名风格不同，别混用 ✗
    - 返回：`IndSeries`（单线）或 `IndFrame`（多线），索引与调用它的 K 线 / 指标对齐
    - 主图 / 副图：装饰器 `overlap=True` 的均线、通道类叠在主图，其余（振荡、量能、统计、形态）在副图

    ### 指标分类（共 88 个）
    **趋势（30）**：ADX、ADXR、AROON、AROONOSC、DEMA、DI、DM、DONCHIANCHANNEL、DX、EF、EMA、HMA、ICHIMOKU、INSTANTANEOUSTRENDLINE、KAMA、MACD、PIVOTPOINT、PSAR …（共 30 个）
    **动量（21）**：AO、APO、BOP、CCI、CMO、DPO、ELDERRAY、FISHER、FOSC、MOM、MSW、PPO、QSTICK、ROC、ROCR、RSI、STOCH、STOCHRSI …（共 21 个）
    **波动率（10）**：ATR、BBANDS、CHANDELIEREXIT、CVI、KELTNERCHANNEL、MASS、NATR、SMAENVELOPE、TR、VOLATILITY
    **成交量（13）**：AD、ADOSC、CHAIKINMF、EMV、KVO、MARKETFI、MFI、NVI、OBV、PVI、VOSC、VWAP、VWMA
    **统计（13）**：ADAPTIVEMSW、AVGPRICE、HIGHPASS、HILBERTTRANSFORM、HOMODYNEDISCRIMINATOR、LINREG、MD、MEDPRICE、MIN、STDDEV、TSF、TYPPRICE、WCPRICE
    **其他（1）**：MAX

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
    _perfixes: str = "tulip_"
    _df: IndFrame | IndSeries

    def __init__(self, data):
        self._df = data
    @tobtind(lib="tulip", overlap=False, lines=['ad'])
    def AD(self, **kwargs) -> IndSeries:
        """累积派发线 · AD（成交量）
        ---------
            以收盘位置加权成交量的累积线，上升示资金流入、下降示流出，可判定量价背离。

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
            >>> tulip_rs.indicators.ad.indicator([high, low, close, volume], [])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['sine', 'lead_sine'])
    def ADAPTIVEMSW(self, **kwargs) -> IndFrame:
        """自适应正弦波 · ADAPTIVEMSW（统计）
        ---------
            用MESA算法拟合自适应周期正弦波，sine与lead_sine交叉可预判转折，取值约±1。

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — sine, lead_sine

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ADAPTIVEMSW()    # 副图
            >>> out.columns               # 线名: sine, lead_sine
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.adaptivemsw.indicator([close], [])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['adosc'])
    def ADOSC(self, short_period: int = 12, long_period: int = 26, **kwargs) -> IndSeries:
        """蔡金累积派发振荡器 · ADOSC（成交量）
        ---------
            累积派发线快慢均线之差，正值示资金流入、负值示流出，穿越零轴提示量能转向。

        参数:
        ---------
            >>> short_period (int): 短周期. 默认: 12
            >>> long_period (int): 长周期. 默认: 26

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — adosc

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.ADOSC(short_period=12, long_period=26)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.adosc.indicator([high, low, close, volume], [12, 26])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['adx'])
    def ADX(self, period: int = 14, **kwargs) -> IndSeries:
        """平均趋向指数 · ADX（趋势）
        ---------
            取值0~100，只衡量趋势强度不看方向，高于25趋势明显、低于20多为盘整。

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
            >>> out = self.data.ADX(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.adx.indicator([high, low, close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['adxr'])
    def ADXR(self, period: int = 14, **kwargs) -> IndSeries:
        """平均趋向指数评值 · ADXR（趋势）
        ---------
            ADX与其n周期前值的平均，0~100，平滑趋势强度，>25确认趋势、低值示无趋势。

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
            >>> out = self.data.ADXR(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.adxr.indicator([high, low, close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['ao'])
    def AO(self, **kwargs) -> IndSeries:
        """动量震荡指标 · AO（动量）
        ---------
            5与34周期中价均线之差，零轴上方为多头动能、下方为空头，柱体变色示动能变化。

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — ao

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.AO()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.ao.indicator([high, low], [])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['apo'])
    def APO(self, short_period: int = 12, long_period: int = 26, **kwargs) -> IndSeries:
        """绝对价格振荡器 · APO（动量）
        ---------
            短期与长期均线之差的绝对数值，正负与穿越零轴反映多空动能及趋势转换。

        参数:
        ---------
            >>> short_period (int): 短周期. 默认: 12
            >>> long_period (int): 长周期. 默认: 26

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — apo

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.APO(short_period=12, long_period=26)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.apo.indicator([close], [12, 26])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['aroon_down', 'aroon_up'])
    def AROON(self, period: int = 25, **kwargs) -> IndFrame:
        """阿隆指标 · AROON（趋势）
        ---------
            上线与下线取值0~100，衡量距区间最高/最低价的时间，两线同高示强趋势、交织示震荡。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 25

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — aroon_down, aroon_up

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.AROON(period=25)    # 副图
            >>> out.columns               # 线名: aroon_down, aroon_up
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.aroon.indicator([high, low], [25])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['aroonosc'])
    def AROONOSC(self, period: int = 25, **kwargs) -> IndSeries:
        """阿隆振荡器 · AROONOSC（趋势）
        ---------
            阿隆上线减下线，范围-100~100，正值偏多、负值偏空，穿越零轴提示趋势转换。

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
            >>> out = self.data.AROONOSC(period=25)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.aroonosc.indicator([high, low], [25])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['atr'])
    def ATR(self, period: int = 14, **kwargs) -> IndSeries:
        """平均真实波幅 · ATR（波动率）
        ---------
            真实波幅的移动平均，数值越高波动越剧烈，常用于设定止损距离与仓位规模。

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
            >>> out = self.data.ATR(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.atr.indicator([high, low, close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['avgprice'])
    def AVGPRICE(self, **kwargs) -> IndSeries:
        """平均价格 · AVGPRICE（统计）
        ---------
            开盘、最高、最低、收盘四价的算术平均，平滑单根K线噪声，常作其他指标的输入价。

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
            >>> tulip_rs.indicators.avgprice.indicator([open, high, low, close], [])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['bbands_lower', 'bbands_middle', 'bbands_upper'])
    def BBANDS(self, period: int = 20, std_dev: int = 20, **kwargs) -> IndFrame:
        """布林带 · BBANDS（波动率）
        ---------
            中轨为均线，上下轨为中轨加减n倍标准差，触轨示超买超卖，带宽反映波动大小。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20
            >>> std_dev (int): 宽度 / 倍数系数. 默认: 20

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — bbands_lower, bbands_middle, bbands_upper

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.BBANDS(period=20, std_dev=20)    # 主图叠加
            >>> out.columns               # 线名: bbands_lower, bbands_middle, bbands_upper
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.bbands.indicator([close], [20, 20])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['bop'])
    def BOP(self, **kwargs) -> IndSeries:
        """实力平衡指标 · BOP（动量）
        ---------
            收盘减开盘除以最高减最低，范围-1~1，正值为买方主导、负值卖方主导。

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
            >>> tulip_rs.indicators.bop.indicator([open, high, low, close], [])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['cci'])
    def CCI(self, period: int = 20, **kwargs) -> IndSeries:
        """顺势指标 · CCI（动量）
        ---------
            衡量价格偏离统计均值的程度，±100为超买超卖界，可识别极端行情与趋势启动。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — cci

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.CCI(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.cci.indicator([high, low, close], [20])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['cmf'])
    def CHAIKINMF(self, period: int = 14, **kwargs) -> IndSeries:
        """蔡金资金流量 · CHAIKINMF（成交量）
        ---------
            周期内加权资金流之和与成交量之比，范围-1~1，正值吸筹、负值派发。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cmf

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.CHAIKINMF(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.chaikinmf.indicator([high, low, close, volume], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['long', 'short'])
    def CHANDELIEREXIT(self, period: int = 14, step: int = 14, **kwargs) -> IndFrame:
        """吊灯止损 · CHANDELIEREXIT（波动率）
        ---------
            以周期最高/最低价为基准加减ATR得到多头与空头离场线，用于趋势跟踪止损。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> step (int): 步长. 默认: 14

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 2 条线 — long, short

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.CHANDELIEREXIT(period=14, step=14)    # 主图叠加
            >>> out.columns               # 线名: long, short
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.chandelierexit.indicator([high, low, close], [14, 14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['cmo'])
    def CMO(self, period: int = 14, **kwargs) -> IndSeries:
        """钱德动量摆动指标 · CMO（动量）
        ---------
            取值-100~100，正负表示涨跌动量占比，绝对超50为超买或超卖区。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cmo

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.CMO(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.cmo.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['cvi'])
    def CVI(self, period: int = 14, **kwargs) -> IndSeries:
        """蔡金波动率 · CVI（波动率）
        ---------
            高低价差EMA的变化率，数值走高大示波动加剧，可用于判断突破与情绪变化。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cvi

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.CVI(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.cvi.indicator([high, low], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['dema'])
    def DEMA(self, period: int = 20, **kwargs) -> IndSeries:
        """双指数移动平均线 · DEMA（趋势）
        ---------
            两倍EMA减去EMA的EMA，滞后小于普通EMA，用于趋势跟踪与动态支撑压力。

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
            >>> out = self.data.DEMA(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.dema.indicator([close], [20])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['plus_di', 'minus_di'])
    def DI(self, period: int = 14, **kwargs) -> IndFrame:
        """动向指标 · DI（趋势）
        ---------
            plus_di与minus_di衡量涨跌方向动量占比，+DI上穿-DI为多头信号，反之偏空。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — plus_di, minus_di

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.DI(period=14)    # 副图
            >>> out.columns               # 线名: plus_di, minus_di
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.di.indicator([high, low, close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['plus_dm', 'minus_dm'])
    def DM(self, period: int = 14, **kwargs) -> IndFrame:
        """动向运动量 · DM（趋势）
        ---------
            统计上行的正向与下行的负向真实波幅，是DI、DX、ADX系列指标的基础分量。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — plus_dm, minus_dm

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.DM(period=14)    # 副图
            >>> out.columns               # 线名: plus_dm, minus_dm
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.dm.indicator([high, low], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['lower', 'middle', 'upper'])
    def DONCHIANCHANNEL(self, period: int = 14, **kwargs) -> IndFrame:
        """唐奇安通道 · DONCHIANCHANNEL（趋势）
        ---------
            由周期内最高、最低及中值构成，突破上轨示强势、跌破下轨示弱势，常用于突破策略。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — lower, middle, upper

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.DONCHIANCHANNEL(period=14)    # 主图叠加
            >>> out.columns               # 线名: lower, middle, upper
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.donchianchannel.indicator([high, low], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['dpo'])
    def DPO(self, period: int = 14, **kwargs) -> IndSeries:
        """去趋势价格振荡器 · DPO（动量）
        ---------
            剔除趋势后的周期波动，围绕零轴摆动，用于识别短周期高低点与超买超卖。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — dpo

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.DPO(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.dpo.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['dx'])
    def DX(self, period: int = 14, **kwargs) -> IndSeries:
        """动向指数 · DX（趋势）
        ---------
            +DI与-DI之差占两者之和的百分比，范围0~100，值高示方向性强，为ADX原始量。

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
            >>> out = self.data.DX(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.dx.indicator([high, low, close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['ef'])
    def EF(self, period: int = 14, **kwargs) -> IndSeries:
        """效率系数 · EF（趋势）
        ---------
            周期内净价格变动与路径总长之比，0~1，越接近1趋势越顺畅、越小越震荡。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ef

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.EF(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.ef.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['bull', 'bear'])
    def ELDERRAY(self, period: int = 14, **kwargs) -> IndFrame:
        """埃尔德射线 · ELDERRAY（动量）
        ---------
            由EMA与高低价之差算出牛市与熊市力度，bull大示多头强、bear大示空头强。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 2 条线 — bull, bear

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.ELDERRAY(period=14)    # 主图叠加
            >>> out.columns               # 线名: bull, bear
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.elderray.indicator([high, low, close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['ema'])
    def EMA(self, period: int = 20, **kwargs) -> IndSeries:
        """指数移动平均线 · EMA（趋势）
        ---------
            按指数衰减加权平滑价格，反应快于简单均线，用于趋势判断与动态支撑阻力。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — ema

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.EMA(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.ema.indicator([close], [20])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['emv'])
    def EMV(self, **kwargs) -> IndSeries:
        """简易波动指标 · EMV（成交量）
        ---------
            用中价变动与成交量的关系衡量量价效率，正值示低量上行、负值示下行。

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — emv

        数据:
        ---------
            >>> high, low, volume

        使用案例:
        ---------
            >>> out = self.data.EMV()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.emv.indicator([high, low, volume], [])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['fisher', 'fisher_signal'])
    def FISHER(self, period: int = 14, **kwargs) -> IndFrame:
        """费雪变换 · FISHER（动量）
        ---------
            将价格区间位置变换为近似正态分布值，与信号线交叉及极值区提示反转。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — fisher, fisher_signal

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.FISHER(period=14)    # 副图
            >>> out.columns               # 线名: fisher, fisher_signal
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.fisher.indicator([high, low], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['fosc'])
    def FOSC(self, period: int = 14, **kwargs) -> IndSeries:
        """预测振荡器 · FOSC（动量）
        ---------
            收盘价相对线性回归预测值的百分比偏离，可判断超买超卖与趋势强弱。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — fosc

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.FOSC(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.fosc.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['highpass'])
    def HIGHPASS(self, period: int = 14, **kwargs) -> IndSeries:
        """高通滤波 · HIGHPASS（统计）
        ---------
            二阶高通滤波去除低频趋势，输出围绕零轴的短期波动成分，用于提取周期信号。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — highpass

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.HIGHPASS(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.highpass.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['in_phase', 'quadrature'])
    def HILBERTTRANSFORM(self, ss_period: int = 14, hp_period: int = 14, **kwargs) -> IndFrame:
        """希尔伯特变换 · HILBERTTRANSFORM（统计）
        ---------
            由同相与正交分量给出瞬时相位与主导周期，用于识别市场周期与转折点。

        参数:
        ---------
            >>> ss_period (int): 计算周期（K 线根数）. 默认: 14
            >>> hp_period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — in_phase, quadrature

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.HILBERTTRANSFORM(ss_period=14, hp_period=14)    # 副图
            >>> out.columns               # 线名: in_phase, quadrature
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.hilberttransform.indicator([close], [14, 14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['hma'])
    def HMA(self, period: int = 14, **kwargs) -> IndSeries:
        """赫尔移动平均线 · HMA（趋势）
        ---------
            由加权均线组合成的平滑均线，滞后极小且曲线平滑，适合趋势跟踪与均线交叉。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — hma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.HMA(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.hma.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['dc_period'])
    def HOMODYNEDISCRIMINATOR(self, **kwargs) -> IndSeries:
        """同态判别器 · HOMODYNEDISCRIMINATOR（统计）
        ---------
            由价格序列估计主导周期长度，输出以K线根数计的dc_period，供自适应参数使用。

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — dc_period

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.HOMODYNEDISCRIMINATOR()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.homodynediscriminator.indicator([close], [])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['conversion', 'base', 'leading_span_a', 'leading_span_b'])
    def ICHIMOKU(self, short_period: int = 12, long_period: int = 26, **kwargs) -> IndFrame:
        """一目均衡表 · ICHIMOKU（趋势）
        ---------
            转换线、基准线与先行带A/B构成云带，云带上下沿确定支撑压力与多空格局。

        参数:
        ---------
            >>> short_period (int): 短周期. 默认: 12
            >>> long_period (int): 长周期. 默认: 26

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 4 条线 — conversion, base, leading_span_a, leading_span_b

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.ICHIMOKU(short_period=12, long_period=26)    # 主图叠加
            >>> out.columns               # 线名: conversion, base, leading_span_a, leading_span_b
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.ichimoku.indicator([high, low, close], [12, 26])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['trendline'])
    def INSTANTANEOUSTRENDLINE(self, **kwargs) -> IndSeries:
        """瞬时趋势线 · INSTANTANEOUSTRENDLINE（趋势）
        ---------
            以周期中值与ATR构造贴近价格的趋势线，用于判断趋势方向与设置动态止损。

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — trendline

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.INSTANTANEOUSTRENDLINE()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.instantaneoustrendline.indicator([close], [])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['kama'])
    def KAMA(self, period: int = 14, **kwargs) -> IndSeries:
        """考夫曼自适应均线 · KAMA（趋势）
        ---------
            按效率系数自适应调整平滑速度，趋势时贴近价格、震荡时更平滑，减少虚假信号。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — kama

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.KAMA(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.kama.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['lower', 'middle', 'upper'])
    def KELTNERCHANNEL(self, period: int = 14, step: int = 14, **kwargs) -> IndFrame:
        """肯特纳通道 · KELTNERCHANNEL（波动率）
        ---------
            中轨为EMA，上下轨为中轨加减n倍ATR，通道随波动伸缩，触轨示超买超卖。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> step (int): 步长. 默认: 14

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — lower, middle, upper

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.KELTNERCHANNEL(period=14, step=14)    # 主图叠加
            >>> out.columns               # 线名: lower, middle, upper
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.keltnerchannel.indicator([high, low, close], [14, 14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['kvo'])
    def KVO(self, short_period: int = 12, long_period: int = 26, **kwargs) -> IndSeries:
        """克林格量价振荡器 · KVO（成交量）
        ---------
            基于成交量方向力度的快慢EMA差值，正负及零轴穿越判断资金进出与量价背离。

        参数:
        ---------
            >>> short_period (int): 短周期. 默认: 12
            >>> long_period (int): 长周期. 默认: 26

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — kvo

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.KVO(short_period=12, long_period=26)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.kvo.indicator([high, low, close, volume], [12, 26])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['linreg'])
    def LINREG(self, period: int = 14, **kwargs) -> IndSeries:
        """线性回归线 · LINREG（统计）
        ---------
            周期内价格最小二乘回归的末值，代表趋势拟合价，可判断趋势方向与斜率。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — linreg

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.LINREG(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.linreg.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['macd_line', 'signal_line', 'histogram'], linestyle={'histogram': LineStyle(line_dash=LineDash.vbar, vbar_base=0.0, vbar_up_color=Colors.bull_color, vbar_down_color=Colors.bear_color)})
    def MACD(self, short_period: int = 12, long_period: int = 26, signal_period: int = 9, **kwargs) -> IndFrame:
        """指数平滑异同移动平均线 · MACD（趋势）
        ---------
            快慢EMA之差及其信号线与柱状图，金叉死叉和零轴位置判断趋势与动能强弱。

        参数:
        ---------
            >>> short_period (int): 短周期. 默认: 12
            >>> long_period (int): 长周期. 默认: 26
            >>> signal_period (int): 信号线平滑周期. 默认: 9

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — macd_line, signal_line, histogram

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MACD(short_period=12, long_period=26, signal_period=9)    # 主图叠加
            >>> out.columns               # 线名: macd_line, signal_line, histogram
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.macd.indicator([close], [12, 26, 9])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['marketfi'])
    def MARKETFI(self, **kwargs) -> IndSeries:
        """市场促进指数 · MARKETFI（成交量）
        ---------
            最高减最低除以成交量，衡量单位成交量带来的价格移动，值高表示交易效率高。

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — marketfi

        数据:
        ---------
            >>> high, low, volume

        使用案例:
        ---------
            >>> out = self.data.MARKETFI()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.marketfi.indicator([high, low, volume], [])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['mass'])
    def MASS(self, period: int = 14, **kwargs) -> IndSeries:
        """质量指数 · MASS（波动率）
        ---------
            高低价差EMA比值之和，数值膨胀(常以27为界)提示趋势衰竭与反转风险。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — mass

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.MASS(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.mass.indicator([high, low], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['max'])
    def MAX(self, period: int = 14, **kwargs) -> IndSeries:
        """周期最高值 · MAX（其他）
        ---------
            取最近n根K线的最高价，是唐奇安上轨等通道与突破类指标的基础组件。

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
            >>> out = self.data.MAX(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.max.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['md'])
    def MD(self, period: int = 14, **kwargs) -> IndSeries:
        """平均偏差 · MD（统计）
        ---------
            周期内价格与均值之绝对偏差的平均，衡量离散程度，为统计类指标基础组件。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — md

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MD(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.md.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['medprice'])
    def MEDPRICE(self, **kwargs) -> IndSeries:
        """中价 · MEDPRICE（统计）
        ---------
            取最高价与最低价的平均值，单位同价格。常作为滤波与通道的输入价格序列。

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
            >>> tulip_rs.indicators.medprice.indicator([high, low], [])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['mfi'])
    def MFI(self, period: int = 14, **kwargs) -> IndSeries:
        """资金流量指标 · MFI（成交量）
        ---------
            以典型价与成交量计算资金流入流出，取值0~100。高于80超买、低于20超卖，可提示背离。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — mfi

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.MFI(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.mfi.indicator([high, low, close, volume], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['min'])
    def MIN(self, period: int = 14, **kwargs) -> IndSeries:
        """最小值 · MIN（统计）
        ---------
            取最近N期的最小值，单位同价格。用于构造下轨、支撑位或区间突破参考。

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
            >>> out = self.data.MIN(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.min.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['mom'])
    def MOM(self, period: int = 10, **kwargs) -> IndSeries:
        """动量 · MOM（动量）
        ---------
            当前价与N期前价格之差，围绕0波动。大于0表示上涨动能，可辅助判断趋势强弱。

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
            >>> out = self.data.MOM(period=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.mom.indicator([close], [10])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['msw_sine', 'msw_lead'])
    def MSW(self, period: int = 14, **kwargs) -> IndFrame:
        """梅辛格正弦波 · MSW（动量）
        ---------
            输出正弦与领先两条曲线，围绕0轴摆动。可辅助识别周期转折与短线买卖时机。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — msw_sine, msw_lead

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.MSW(period=14)    # 副图
            >>> out.columns               # 线名: msw_sine, msw_lead
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.msw.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['natr'])
    def NATR(self, period: int = 14, **kwargs) -> IndSeries:
        """归一化真实波幅 · NATR（波动率）
        ---------
            真实波幅占收盘价百分比，单位%。数值越大波动越剧烈，常用于设置止损与仓位。

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
            >>> out = self.data.NATR(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.natr.indicator([high, low, close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['nvi'])
    def NVI(self, **kwargs) -> IndSeries:
        """负成交量指标 · NVI（成交量）
        ---------
            成交量减少日的累积涨跌指数，起始1000。上升表示缩量上涨，多用于确认吸筹。

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
            >>> tulip_rs.indicators.nvi.indicator([close, volume], [])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['obv'])
    def OBV(self, **kwargs) -> IndSeries:
        """能量潮 · OBV（成交量）
        ---------
            按涨跌方向累加成交量得到累计量能曲线。与价格同向确认趋势，背离常示警。

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
            >>> tulip_rs.indicators.obv.indicator([close, volume], [])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['s3'])
    def PIVOTPOINT(self, period: int = 14, **kwargs) -> IndSeries:
        """枢轴点 · PIVOTPOINT（趋势）
        ---------
            依前一周期高、低、收盘推算的支撑阻力价位，单位同价格。用于日内多空分界参考。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — s3

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.PIVOTPOINT(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.pivotpoint.indicator([high, low, close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['ppo'])
    def PPO(self, short_period: int = 12, long_period: int = 26, **kwargs) -> IndSeries:
        """百分比价格振荡器 · PPO（动量）
        ---------
            快慢均线差占慢线百分比，单位%。正负与穿越零轴反映趋势方向，正值偏多。

        参数:
        ---------
            >>> short_period (int): 短周期. 默认: 12
            >>> long_period (int): 长周期. 默认: 26

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — ppo

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.PPO(short_period=12, long_period=26)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.ppo.indicator([close], [12, 26])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['psar'])
    def PSAR(self, acceleration_factor: float = 0.02, max_acceleration_factor: int = 14, **kwargs) -> IndSeries:
        """抛物线转向 · PSAR（趋势）
        ---------
            点状止损转向线，单位同价格。价在点上方看多、下方看空，翻转即趋势转换信号。

        参数:
        ---------
            >>> acceleration_factor (float): 宽度 / 倍数系数. 默认: 0.02
            >>> max_acceleration_factor (int): 宽度 / 倍数系数. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — psar

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.PSAR(acceleration_factor=0.02, max_acceleration_factor=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.psar.indicator([high, low], [0.02, 14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['pvi'])
    def PVI(self, **kwargs) -> IndSeries:
        """正成交量指标 · PVI（成交量）
        ---------
            成交量放大日的累积涨跌指数，起始1000。上升说明放量上涨，常用于判断主力参与。

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
            >>> tulip_rs.indicators.pvi.indicator([close, volume], [])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['qstick'])
    def QSTICK(self, period: int = 14, **kwargs) -> IndSeries:
        """快棒指标 · QSTICK（动量）
        ---------
            开盘与收盘价差的N期均值，围绕0摆动。正值偏多、负值偏空，可辨短线多空力量。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — qstick

        数据:
        ---------
            >>> open, close

        使用案例:
        ---------
            >>> out = self.data.QSTICK(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.qstick.indicator([open, close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['roc'])
    def ROC(self, period: int = 10, **kwargs) -> IndSeries:
        """变动率 · ROC（动量）
        ---------
            价格相对N期前的变化百分比，围绕0波动。大于0示上升动能，可判趋势与超买超卖。

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
            >>> out = self.data.ROC(period=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.roc.indicator([close], [10])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['rocr'])
    def ROCR(self, period: int = 10, **kwargs) -> IndSeries:
        """变动率比率 · ROCR（动量）
        ---------
            当前价与N期前价格之比，1为基准。大于1表示上涨，便于比较不同价位的动能。

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
            >>> out = self.data.ROCR(period=10)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.rocr.indicator([close], [10])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['roofing'])
    def ROOFINGFILTER(self, ss_period: int = 14, hp_period: int = 14, **kwargs) -> IndSeries:
        """屋顶滤波 · ROOFINGFILTER（趋势）
        ---------
            叠加超平滑与高通滤波的趋势线，单位同价格。可滤除噪声并突出转折点。

        参数:
        ---------
            >>> ss_period (int): 计算周期（K 线根数）. 默认: 14
            >>> hp_period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — roofing

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ROOFINGFILTER(ss_period=14, hp_period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.roofingfilter.indicator([close], [14, 14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['rsi'])
    def RSI(self, period: int = 14, **kwargs) -> IndSeries:
        """相对强弱指标 · RSI（动量）
        ---------
            比较涨跌幅得出强度，取值0~100。高于70超买、低于30超卖，可观察背离。

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
            >>> out = self.data.RSI(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.rsi.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['sma'])
    def SMA(self, period: int = 20, **kwargs) -> IndSeries:
        """简单移动平均 · SMA（趋势）
        ---------
            N期收盘价算术均值，单位同价格。用于平滑价格、判断趋势方向与支撑阻力。

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
            >>> out = self.data.SMA(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.sma.indicator([close], [20])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['lower', 'middle', 'upper'])
    def SMAENVELOPE(self, period: int = 14, percentage: int = 14, **kwargs) -> IndFrame:
        """均线包络 · SMAENVELOPE（波动率）
        ---------
            以均线为中心按百分比上下偏移形成通道。价格触及上轨偏强、下轨偏弱，可判回归。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> percentage (int): 比例阈值（小数，0.1 = 10%）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — lower, middle, upper

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.SMAENVELOPE(period=14, percentage=14)    # 主图叠加
            >>> out.columns               # 线名: lower, middle, upper
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.smaenvelope.indicator([close], [14, 14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['stddev'])
    def STDDEV(self, period: int = 20, **kwargs) -> IndSeries:
        """标准差 · STDDEV（统计）
        ---------
            N期价格的标准差，单位同价格。数值越大波动越强，是布林带等指标的波动度量。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — stddev

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.STDDEV(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.stddev.indicator([close], [20])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['stoch_k', 'stoch_d'])
    def STOCH(self, k_period: int = 14, k_slow: int = 3, d_period: int = 3, **kwargs) -> IndFrame:
        """随机指标 · STOCH（动量）
        ---------
            %K与%D取值0~100。高于80超买、低于20超卖，金叉死叉提示短线买卖。

        参数:
        ---------
            >>> k_period (int): K 线平滑周期. 默认: 14
            >>> k_slow (int): K 线二次平滑周期. 默认: 3
            >>> d_period (int): D 线平滑周期. 默认: 3

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — stoch_k, stoch_d

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.STOCH(k_period=14, k_slow=3, d_period=3)    # 副图
            >>> out.columns               # 线名: stoch_k, stoch_d
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.stoch.indicator([high, low, close], [14, 3, 3])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['stochrsi'])
    def STOCHRSI(self, period: int = 14, **kwargs) -> IndSeries:
        """随机相对强弱 · STOCHRSI（动量）
        ---------
            对RSI再做随机化处理，取值0~100。高于80超买、低于20超卖，比RSI更灵敏。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — stochrsi

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.STOCHRSI(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.stochrsi.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['supersmoother'])
    def SUPERSMOOTHER(self, period: int = 14, **kwargs) -> IndSeries:
        """超级平滑线 · SUPERSMOOTHER（趋势）
        ---------
            低滞后平滑的趋势线，单位同价格。斜率向上偏多、向下偏空，噪声小适合定趋势。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — supersmoother

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.SUPERSMOOTHER(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.supersmoother.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['supertrend'])
    def SUPERTREND(self, period: int = 14, step: int = 14, **kwargs) -> IndSeries:
        """超级趋势 · SUPERTREND（趋势）
        ---------
            基于ATR的通道止损线，单位同价格。价在其上方为多头、下方为空头，翻转即信号。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> step (int): 步长. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — supertrend

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.SUPERTREND(period=14, step=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.supertrend.indicator([high, low, close], [14, 14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['tema'])
    def TEMA(self, period: int = 20, **kwargs) -> IndSeries:
        """三重指数均线 · TEMA（趋势）
        ---------
            对均线做三次指数平滑以减小滞后，单位同价格。用于更及时地跟随趋势方向。

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
            >>> out = self.data.TEMA(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.tema.indicator([close], [20])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['tr'])
    def TR(self, **kwargs) -> IndSeries:
        """真实波幅 · TR（波动率）
        ---------
            取当日振幅与跳空缺口的最大值，单位同价格。衡量单期波动，是ATR的计算基础。

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — tr

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.TR()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.tr.indicator([high, low, close], [])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['trima'])
    def TRIMA(self, period: int = 20, **kwargs) -> IndSeries:
        """三角移动平均 · TRIMA（趋势）
        ---------
            加权移动平均的再平滑，单位同价格。曲线平滑且滞后适中，适合识别中长期趋势。

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
            >>> out = self.data.TRIMA(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.trima.indicator([close], [20])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['trix'])
    def TRIX(self, period: int = 10, **kwargs) -> IndSeries:
        """三重指数平滑均线变动率 · TRIX（动量）
        ---------
            三重指数均线的变化率，单位%。正负反映趋势方向，零轴穿越可作中长线信号。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 10

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — trix

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.TRIX(period=10)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.trix.indicator([close], [10])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['trvi'])
    def TRVI(self, period: int = 14, **kwargs) -> IndSeries:
        """趋势相对强弱 · TRVI（趋势）
        ---------
            以价格为权重的趋势强度指标，围绕0摆动。正值偏多、负值偏空，可辨趋势强弱。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — trvi

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.TRVI(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.trvi.indicator([high, low, close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['tsf'])
    def TSF(self, period: int = 14, **kwargs) -> IndSeries:
        """时间序列预测 · TSF（统计）
        ---------
            对价格做线性回归外推得到的预测值，单位同价格。与价格比较可判趋势偏向。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — tsf

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.TSF(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.tsf.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['typprice'])
    def TYPPRICE(self, **kwargs) -> IndSeries:
        """典型价 · TYPPRICE（统计）
        ---------
            最高、最低、收盘三价的均值，单位同价格。常作为资金流与通道类指标的输入。

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
            >>> tulip_rs.indicators.typprice.indicator([high, low, close], [])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['vhf'])
    def VHF(self, period: int = 14, **kwargs) -> IndSeries:
        """垂直水平滤波 · VHF（趋势）
        ---------
            净涨跌与路径总长之比，取值0~1。数值高示趋势明确、低示震荡，可切换策略。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — vhf

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.VHF(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.vhf.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['volatility'])
    def VOLATILITY(self, period: int = 14, **kwargs) -> IndSeries:
        """年化波动率 · VOLATILITY（波动率）
        ---------
            收益率标准差年化后的百分比。数值越大风险越高，常用于期权定价与风险控制。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — volatility

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.VOLATILITY(period=14)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.volatility.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['vi_up', 'vi_down'])
    def VORTEX(self, period: int = 14, **kwargs) -> IndFrame:
        """涡旋指标 · VORTEX（趋势）
        ---------
            输出VI+与VI-两条线，均大于0。两线交叉可判趋势反转，VI+在上为上升趋势。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — vi_up, vi_down

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.VORTEX(period=14)    # 副图
            >>> out.columns               # 线名: vi_up, vi_down
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.vortex.indicator([high, low, close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['vosc'])
    def VOSC(self, short_period: int = 12, long_period: int = 26, **kwargs) -> IndSeries:
        """成交量振荡器 · VOSC（成交量）
        ---------
            短期与长期成交量均线之差占长期均线百分比。正值示量能放大，可辅助确认趋势。

        参数:
        ---------
            >>> short_period (int): 短周期. 默认: 12
            >>> long_period (int): 长周期. 默认: 26

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — vosc

        数据:
        ---------
            >>> volume

        使用案例:
        ---------
            >>> out = self.data.VOSC(short_period=12, long_period=26)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.vosc.indicator([volume], [12, 26])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['vwap'])
    def VWAP(self, **kwargs) -> IndSeries:
        """成交量加权均价 · VWAP（成交量）
        ---------
            按成交量加权的累计均价，单位同价格。价在其上方偏强、下方偏弱，常用作成本基准。

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
            >>> out = self.data.VWAP()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.vwap.indicator([high, low, close, volume], [])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['vwma'])
    def VWMA(self, period: int = 14, **kwargs) -> IndSeries:
        """成交量加权均线 · VWMA（成交量）
        ---------
            以成交量为权重的N期移动平均，单位同价格。放量价格影响更大，可反映真实成本。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — vwma

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.VWMA(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.vwma.indicator([close, volume], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=False, lines=['wad'])
    def WAD(self, **kwargs) -> IndSeries:
        """威廉累积量 · WAD（动量）
        ---------
            按收盘相对前收位置累加涨跌幅度，围绕0波动。与价格背离可提示趋势变化。

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — wad

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.WAD()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.wad.indicator([high, low, close], [])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['wcprice'])
    def WCPRICE(self, **kwargs) -> IndSeries:
        """加权收盘价 · WCPRICE（统计）
        ---------
            高低均价与收盘价的两倍加权平均，单位同价格。比典型价更贴近收盘，用于平滑。

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — wcprice

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.WCPRICE()    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.wcprice.indicator([high, low, close], [])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['wilders'])
    def WILDERS(self, period: int = 14, **kwargs) -> IndSeries:
        """威尔德平滑 · WILDERS（趋势）
        ---------
            Wilder式指数平滑均线，单位同价格。滞后小且平滑，是ATR、RSI等的平滑基础。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — wilders

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.WILDERS(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.wilders.indicator([close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['willr'])
    def WILLR(self, period: int = 14, **kwargs) -> IndSeries:
        """威廉指数 · WILLR（动量）
        ---------
            收盘在N期高低区间中的位置，取值-100~0。高于-20超买、低于-80超卖。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — willr

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.WILLR(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.willr.indicator([high, low, close], [14])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['wma'])
    def WMA(self, period: int = 20, **kwargs) -> IndSeries:
        """加权移动平均 · WMA（趋势）
        ---------
            按时间线性加权的N期均价，单位同价格。比SMA更重视近期价格，趋势跟随更快。

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
            >>> out = self.data.WMA(period=20)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.wma.indicator([close], [20])
        """
        ...
    @tobtind(lib="tulip", overlap=True, lines=['zlema'])
    def ZLEMA(self, period: int = 14, **kwargs) -> IndSeries:
        """零滞后指数均线 · ZLEMA（趋势）
        ---------
            先消除滞后再指数平滑的均线，单位同价格。比EMA更贴近价格，适合及时跟踪趋势。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — zlema

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ZLEMA(period=14)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> tulip_rs.indicators.zlema.indicator([close], [14])
        """
        ...
    #: 数据不全 / 不是指标 → desk 不显示（方法仍在）
    NON_KLINE_INDICATORS = []
    #: 建议信号（目录 / 技术分析用；**想改就改这张表** ✓）
    SIGNALS = {
        'ADX': {'adx': Compare(-2, 1, label='adx 高于前一根看多')},
        'ADXR': {'adxr': Compare(-2, 1, label='adxr 高于前一根看多')},
        'AO': {'ao': Compare(-2, 1, label='ao 高于前一根看多')},
        'APO': {'apo': Compare(-2, 1, label='apo 高于前一根看多')},
        'ATR': {'atr': Compare(-2, 1, label='atr 高于前一根看多')},
        'CCI': {'cci': Compare(-2, 1, label='cci 高于前一根看多')},
        'CMO': {'cmo': Compare(-2, 1, label='cmo 高于前一根看多')},
        'DEMA': {'dema': Compare(-2, 1, label='dema 高于前一根看多')},
        'EMA': {'ema': Compare(-2, 1, label='ema 高于前一根看多')},
        'HMA': {'hma': Compare(-2, 1, label='hma 高于前一根看多')},
        'KAMA': {'kama': Compare(-2, 1, label='kama 高于前一根看多')},
        'MACD': {'macd_line': Compare(-2, 1, label='macd_line 高于前一根看多'), 'signal_line': Compare(-2, 1, label='signal_line 高于前一根看多'), 'histogram': Compare(-2, 1, label='histogram 高于前一根看多')},
        'MFI': {'mfi': Compare(-2, 1, label='mfi 高于前一根看多')},
        'OBV': {'obv': Compare(-2, 1, label='obv 高于前一根看多')},
        'PPO': {'ppo': Compare(-2, 1, label='ppo 高于前一根看多')},
        'ROC': {'roc': Compare(-2, 1, label='roc 高于前一根看多')},
        'RSI': {'rsi': Compare(-2, 1, label='rsi 高于前一根看多')},
        'SMA': {'sma': Compare(-2, 1, label='sma 高于前一根看多')},
        'TEMA': {'tema': Compare(-2, 1, label='tema 高于前一根看多')},
        'TRIMA': {'trima': Compare(-2, 1, label='trima 高于前一根看多')},
        'TRIX': {'trix': Compare(-2, 1, label='trix 高于前一根看多')},
        'VWAP': {'vwap': Compare(-2, 1, label='vwap 高于前一根看多')},
        'VWMA': {'vwma': Compare(-2, 1, label='vwma 高于前一根看多')},
        'WMA': {'wma': Compare(-2, 1, label='wma 高于前一根看多')},
    }
