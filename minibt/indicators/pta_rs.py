"""**PtaRs** —— pandas_ta 的 Rust 版实现（27 个常用指标）✓

pandas_ta 的算法核心都是"滚动算子组合"，用 `py-alpha-lib`（Rust）的算子
1:1 拼出来即可；本模块是把公式落到 minibt 指标上的外壳：

| 事项 | 说明 |
|---|---|
| 前缀 | `pta_rs_`（CoreFunc：`pta_rs_sma` …） |
| 入口 | `kline.pta_rs.sma(length=20)`（数据源 = 调用它的 IndFrame ✓） |
| 口径 | 与 `pandas_ta` **逐值一致**（尾巴对齐；开头因窗口口径差异更早出值）|
| 生成 | `scripts/gen_pta_rs.py`（别手改本文件 ✓） |

包含：sma / ema / wma / rma / stdev / bbands / macd / rsi / atr / donchian / kc / kdj / stoch / obv / mfi / vwap / adx / ao / roc / ts_rank / quantile / skew / kurtosis / linreg / ts_argmax / ts_argmin / trix

依赖可选包 `py-alpha-lib`（Rust）：没装时调用抛可读错误，
`import minibt` 不受影响 ✓
"""

from __future__ import annotations

from .base import tobtind
from ..utils import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_ import *
    from .core import *


#: 全部指标名（`batch()` 用 ✓），顺序 = 定义顺序
_INDICATOR_NAMES = ('sma', 'ema', 'wma', 'rma', 'stdev', 'bbands', 'macd', 'rsi', 'atr', 'donchian', 'kc', 'kdj', 'stoch', 'obv', 'mfi', 'vwap', 'adx', 'ao', 'roc', 'ts_rank', 'quantile', 'skew', 'kurtosis', 'linreg', 'ts_argmax', 'ts_argmin', 'trix')


class PtaRs:
    """## PtaRs（pandas_ta 的 Rust 版）

    - 27 个常用指标，全部 `@tobtind(lib="pta_rs")`，参数名和 pandas_ta 一致；
    - 均值/通道类在主图（`overlap=True`），振荡类在副图；
    - 数值口径与 pandas_ta 对齐（总体标准差、Wilder 平滑、MACD 三线…）✓
    """
    _perfixes: str = "pta_rs_"
    _df: IndFrame | IndSeries

    def __init__(self, data):
        self._df = data
    @tobtind(lib="pta_rs", overlap=True, lines=['sma'])
    def sma(self, length: int = 10, **kwargs) -> IndSeries | IndFrame:
        """简单移动平均（SMA）
---------
    窗口内收盘价等权平均；和 `pandas_ta.sma` 等价。

计算方法:
---------
>>> SMA = alpha.MA(close, length)

参数:
---------
>>> length (int): 默认: 10

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=True, lines=['ema'])
    def ema(self, length: int = 10, **kwargs) -> IndSeries | IndFrame:
        """指数移动平均（EMA）
---------
    α = 2/(length+1) 的指数平滑，**前 n 根均值当种子**（TA-Lib / pandas_ta 口径）。

计算方法:
---------
>>> EMA = SMA 种子 + α·x + (1-α)·EMA₋₁

参数:
---------
>>> length (int): 默认: 10

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=True, lines=['wma'])
    def wma(self, length: int = 10, **kwargs) -> IndSeries | IndFrame:
        """加权移动平均（WMA）
---------
    窗口内按 1..n 线性加权；和 `pandas_ta.wma` 等价。

计算方法:
---------
>>> WMA = alpha.LWMA(close, length)

参数:
---------
>>> length (int): 默认: 10

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=True, lines=['rma'])
    def rma(self, length: int = 10, **kwargs) -> IndSeries | IndFrame:
        """Wilder 平滑（RMA）
---------
    α = 1/length 的指数平滑（Wilder），ATR/RSI/ADX 的平滑内核。

计算方法:
---------
>>> RMA = alpha.SMA(close, length, 1)

参数:
---------
>>> length (int): 默认: 10

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['stdev'])
    def stdev(self, length: int = 20, **kwargs) -> IndSeries | IndFrame:
        """滚动标准差（总体口径）
---------
    pandas_ta 的 `stdev` 默认 `ddof=1`（样本）→ 和 `alpha.STDDEV` 口径一致。

计算方法:
---------
>>> STDEV = alpha.STDDEV(close, n)（ddof=1 ✓）

参数:
---------
>>> length (int): 默认: 20

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=True, lines=['bbl', 'bbm', 'bbu'])
    def bbands(self, length: int = 20, std: float = 2.0, **kwargs) -> IndSeries | IndFrame:
        """布林带（BBANDS）
---------
    中轨 = SMA，上下轨 = 中轨 ± k × 标准差（ddof=1，同 pandas_ta）。

计算方法:
---------
>>> BBM = MA(close, n)；BBU/BBL = BBM ± k·STDDEV

参数:
---------
>>> length (int): 默认: 20
>>> std (float): 默认: 2.0

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['macd', 'macdh', 'macds'])
    def macd(self, fast: int = 12, slow: int = 26, signal: int = 9, **kwargs) -> IndSeries | IndFrame:
        """MACD（12/26/9）
---------
    快慢 EMA 差 + 其 EMA 信号线 + 柱状差。

计算方法:
---------
>>> MACD = EMA(close,f) - EMA(close,s)；MACDs = EMA(MACD, sig)；MACDh = MACD - MACDs

参数:
---------
>>> fast (int): 默认: 12
>>> slow (int): 默认: 26
>>> signal (int): 默认: 9

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['rsi'])
    def rsi(self, length: int = 14, **kwargs) -> IndSeries | IndFrame:
        """相对强弱（RSI）
---------
    涨幅 / 跌幅的 Wilder 平滑之比（`alpha.SMA(x,n,1)` 就是 RMA）。

计算方法:
---------
>>> RSI = 100·RMA(gain,n)/(RMA(gain,n)+|RMA(loss,n)|)

参数:
---------
>>> length (int): 默认: 14

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['atr'])
    def atr(self, length: int = 14, **kwargs) -> IndSeries | IndFrame:
        """平均真实波幅（ATR）
---------
    TR = max(H-L, |H-C₋₁|, |C₋₁-L|)，前 n 根均值当种子后 Wilder 平滑（和 pandas_ta 的 `presma=True` 一致）。

计算方法:
---------
>>> ATR = RMA(TR, n)

参数:
---------
>>> length (int): 默认: 14

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=True, lines=['dcl', 'dcm', 'dcu'])
    def donchian(self, lower_length: int = 20, upper_length: int = 20, **kwargs) -> IndSeries | IndFrame:
        """唐奇安通道（DONCHIAN）
---------
    上下轨 = 区间最高 / 最低，中轨取两者均值。

计算方法:
---------
>>> DCU = HHV(high,u)；DCL = LLV(low,l)；DCM = (DCU+DCL)/2

参数:
---------
>>> lower_length (int): 默认: 20
>>> upper_length (int): 默认: 20

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=True, lines=['kcl', 'kcb', 'kcu'])
    def kc(self, length: int = 20, scalar: float = 2.0, **kwargs) -> IndSeries | IndFrame:
        """肯特纳通道（KC）
---------
    中轨 = EMA(close)，带宽 = EMA(TR)，上下轨 = 中轨 ± k×带宽。

计算方法:
---------
>>> KCB = EMA(close,n)；KCB ± k·EMA(TR,n)

参数:
---------
>>> length (int): 默认: 20
>>> scalar (float): 默认: 2.0

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['k', 'd', 'j'])
    def kdj(self, length: int = 9, signal: int = 3, **kwargs) -> IndSeries | IndFrame:
        """KDJ
---------
    RSV = (C-LLV)/(HHV-LLV)×100，K/D 用 RMA 平滑，J = 3K-2D。

计算方法:
---------
>>> K = RMA(RSV, sig)；D = RMA(K, sig)；J = 3K - 2D

参数:
---------
>>> length (int): 默认: 9
>>> signal (int): 默认: 3

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['stochk', 'stochd', 'stochh'])
    def stoch(self, k: int = 14, d: int = 3, smooth_k: int = 3, **kwargs) -> IndSeries | IndFrame:
        """随机指标（STOCH）
---------
    K = SMA(%K, smooth_k)，D = SMA(K, d)，H = K - D。

计算方法:
---------
>>> %K = 100(C-LLV)/(HHV-LLV)；K = SMA(%K,sm)；D = SMA(K,d)

参数:
---------
>>> k (int): 默认: 14
>>> d (int): 默认: 3
>>> smooth_k (int): 默认: 3

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['obv'])
    def obv(self, **kwargs) -> IndSeries | IndFrame:
        """能量潮（OBV）
---------
    收盘涨则加成交量、跌则减，逐根累加（第一根按缺失处理）。

计算方法:
---------
>>> OBV = cumsum(sign(Δclose) * volume)

参数:
---------
>>> 无

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['mfi'])
    def mfi(self, length: int = 14, **kwargs) -> IndSeries | IndFrame:
        """资金流量（MFI）
---------
    典型价 × 量按涨跌定号，窗口内正 / 负流量比 → 0~100。

计算方法:
---------
>>> MFI = 100·Σpos/(Σpos+Σneg)

参数:
---------
>>> length (int): 默认: 14

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=True, lines=['vwap'])
    def vwap(self, **kwargs) -> IndSeries | IndFrame:
        """成交量加权均价（VWAP）
---------
    典型价 × 量的累计 / 成交量累计；按**交易日**分组重置（时间索引从 IndFrame 的 datetime 列取）。

计算方法:
---------
>>> VWAP = Σ(tp·vol) / Σ(vol)（按日重置）

参数:
---------
>>> 无

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['adx', 'dmp', 'dmn'])
    def adx(self, length: int = 14, signal_length: int = 14, **kwargs) -> IndSeries | IndFrame:
        """趋向指标（ADX / DI）
---------
    方向运动 DM± / ATR → DI± → DX → RMA 平滑成 ADX。

计算方法:
---------
>>> DI± = 100·RMA(DM±,n)/ATR；DX = 100·|DI+-DI-|/(DI++DI-)；ADX = RMA(DX,sig)

参数:
---------
>>> length (int): 默认: 14
>>> signal_length (int): 默认: 14

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['ao'])
    def ao(self, fast: int = 5, slow: int = 34, **kwargs) -> IndSeries | IndFrame:
        """动量震荡（AO）
---------
    (H+L)/2 的快慢 SMA 差。

计算方法:
---------
>>> AO = SMA((H+L)/2, fast) - SMA((H+L)/2, slow)

参数:
---------
>>> fast (int): 默认: 5
>>> slow (int): 默认: 34

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['roc'])
    def roc(self, length: int = 10, **kwargs) -> IndSeries | IndFrame:
        """变动率（ROC）
---------
    n 根涨跌幅（百分比）。

计算方法:
---------
>>> ROC = (close/REF(close,n) - 1) * 100

参数:
---------
>>> length (int): 默认: 10

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['ts_rank'])
    def ts_rank(self, length: int = 20, **kwargs) -> IndSeries | IndFrame:
        """窗口排名百分比（TS_RANK）
---------
    当前值在最近 n 根里的排名（并列取平均名次）÷ 窗口个数 → 0~1。pandas 的 `rolling.apply(rank)` 要几十倍时间。

计算方法:
---------
>>> rank_pct = (min_rank + max_rank) / 2 / count

参数:
---------
>>> length (int): 默认: 20

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['quantile'])
    def quantile(self, length: int = 20, q: float = 0.5, **kwargs) -> IndSeries | IndFrame:
        """窗口分位数（QUANTILE）
---------
    最近 n 根的 q 分位值（线性插值），中位数 q=0.5。

计算方法:
---------
>>> quantile = alpha.QUANTILE(close, n, q)

参数:
---------
>>> length (int): 默认: 20
>>> q (float): 默认: 0.5

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['skew'])
    def skew(self, length: int = 20, **kwargs) -> IndSeries | IndFrame:
        """窗口偏度（SKEW）
---------
    分布左右偏斜程度（与 pandas `rolling.skew()` 一致）；三阶矩 + 样本标准差组合算。

计算方法:
---------
>>> skew = n/((n-1)(n-2)) · (M3·n / std³)

参数:
---------
>>> length (int): 默认: 20

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['kurtosis'])
    def kurtosis(self, length: int = 20, **kwargs) -> IndSeries | IndFrame:
        """窗口超额峰度（KURTOSIS）
---------
    尾部厚度（>0 尖峰厚尾）；超额峰度口径与 pandas `rolling.kurt()` 一致。

计算方法:
---------
>>> kurt = n(n+1)/((n-1)(n-2)(n-3))·(M4·n/std⁴) - 3(n-1)²/((n-2)(n-3))

参数:
---------
>>> length (int): 默认: 20

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['linreg'])
    def linreg(self, length: int = 14, **kwargs) -> IndSeries | IndFrame:
        """线性回归终点（LINREG）
---------
    最近 n 根线性回归直线在**当前这根**的取值（= 截距 + 斜率·(n-1)，同 TA-Lib LINEARREG）。

计算方法:
---------
>>> LINREG = INTERCEPT(close,n) + SLOPE(close,n)·(n-1)

参数:
---------
>>> length (int): 默认: 14

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['ts_argmax'])
    def ts_argmax(self, length: int = 20, **kwargs) -> IndSeries | IndFrame:
        """最高点在窗口里的位置（TS_ARGMAX）
---------
    最近 n 根里最高点距今几根（0 = 当前这根），**并列时取最近的一次**。

计算方法:
---------
>>> ts_argmax = (count-1) - HHVBARS(close, n)

参数:
---------
>>> length (int): 默认: 20

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['ts_argmin'])
    def ts_argmin(self, length: int = 20, **kwargs) -> IndSeries | IndFrame:
        """最低点在窗口里的位置（TS_ARGMIN）
---------
    最近 n 根里最低点距今几根（0 = 当前这根），并列时取最近的一次。

计算方法:
---------
>>> ts_argmin = (count-1) - LLVBARS(close, n)

参数:
---------
>>> length (int): 默认: 20

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    @tobtind(lib="pta_rs", overlap=False, lines=['trix', 'trixs'])
    def trix(self, length: int = 10, signal: int = 9, **kwargs) -> IndSeries | IndFrame:
        """三重指数平滑均线变动率（TRIX）
---------
    三重 EMA 的单根变动率 + 其 SMA 信号线。

计算方法:
---------
>>> TRIX = 100·(EMA₃/REF(EMA₃,1)-1)；TRIXs = SMA(TRIX,sig)

参数:
---------
>>> length (int): 默认: 10
>>> signal (int): 默认: 9

说明:
---------
    - 口径与 `pandas_ta` 一致（尾部逐值相同）；
    - 窗口是**扩张式**：比 pandas 的 `rolling(n)` 更早出值；
    - 计算走 Rust（py-alpha-lib，可选依赖）✓"""
        ...

    #: 全部都不是"数学工具"，都能上图 ✓
    NON_KLINE_INDICATORS = []



def batch(frame, specs: dict | None = None) -> dict:
    """**一次算多个 PtaRs 指标**（绕过 `@tobtind` 的包装开销 ✓）

    `@tobtind` 每个指标有 ~40–60 ms 的固定开销（取数 / 校验 / 构造
    `IndSeries` / `_plotinfo`）—— 研究场景一次算几十个指标时先把它绕掉：

    >>> from minibt.indicators.pta_rs import batch
    >>> out = batch(kline.pandas_object,
    ...             {'sma': {'length': 20}, 'macd': {}, 'atr': {'length': 14}})
    >>> out['macd']                  # → DataFrame（macd / macdh / macds）

    Args:
        frame: K 线 DataFrame（open/high/low/close/volume，可带 datetime）
        specs: ``{指标名: 参数字典}``；``None`` → 按默认参数全算一遍

    Returns:
        dict: ``{指标名: pd.Series | pd.DataFrame}``（没有 plotinfo ——
        画图仍然走 `kline.pta_rs.*` ✓）
    """
    from ..core import CoreFunc          # 惰性导入，避免循环依赖

    if specs is None:
        specs = {name: {} for name in _INDICATOR_NAMES}
    out: dict = {}
    for name, params in specs.items():
        func = getattr(CoreFunc, f"pta_rs_{name}", None)
        if func is None:
            raise KeyError(f"没有这个 PtaRs 指标：{name!r}")
        out[name] = func(frame, **dict(params or {}))
    return out
