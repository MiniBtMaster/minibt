"""Alpha 指标（py-alpha-lib，Rust 实现，**可选依赖**）

安装::

    py -3.12 -m pip install py-alpha-lib

**⚠ 只有装了这个包才能用**：`import alpha` 失败时，整个 `Alpha` 分类会从
选择器里消失，`import minibt` 和其它指标完全不受影响 ✓

### 数据源约定（和 pandas_ta / btind 一致）

* **主数据列固定走 `FILED.C`**：KLine 上就是 `close`，IndSeries 上就是它自己；
  方法签名里**没有** `input='close'` 这种参数 ✓
* 需要**第二条序列**的算子（`CROSS(a,b)` / `ALPHA(input,benchmark)` …）
  才把其余参数列出来（默认 `None`，传 `pd.Series` / `np.ndarray`），
  **顺序与原指标签名一致** ✓
* **可画线**的单序列指标（40 个）里：均线 / 通道 / 位移 / 回归截距
  是**主图叠加**（`overlap=True`，17 个）；标准差 / 方差 / Z 分数 /
  排名 / 相关性 / 熵 / 振幅等统计量是**副图**（`overlap=False`）；
* 其余 38 个是**算子** → 进 `NON_KLINE_INDICATORS`：选择器里不出现，
  但它们同样 `@tobtind(lib="alpha")` + 返回 `IndSeries`，
  策略里可以 `self.data.alpha.cross(b=...)` 直接用 ✓。
"""

from __future__ import annotations

from .base import tobtind
from ..utils import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_ import *
    from .core import *


class Alpha:
    """## Alpha 指标指引（py-alpha-lib）

    - Rust 实现的高性能滚动窗口计算库（Alpha101 / 因子算子）；
    - 需要额外安装：``pip install py-alpha-lib``（Python >= 3.12）；
    - 单序列指标 `self.data.alpha.ma(periods=20)` 直接画线（数据 = close）；
    - 算子类（CROSS / CORR2 / WHERE …）当工具函数用：
      `self.data.alpha.cross(b=other_series)`。
    """
    _perfixes: str = "alpha_"
    _df: IndFrame | IndSeries

    def __init__(self, data):
        self._df = data
    @tobtind(lib="alpha", overlap=False, lines=["bins"])
    def bins(self, bins: int = 10, **kwargs) -> IndSeries:
        """等宽分箱编号 (BINS)
---------
    把数值离散成 0..bins-1 的桶号（同值同桶），常用来做分组 / 直方图；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> bin = floor((x - min) / (max - min) * bins)

参数:
---------
>>> bins (int): 参数. 默认: 10

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.bins(bins=10)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.BINS(bins)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["corr"])
    def corr(self, periods: int = 20, **kwargs) -> IndSeries:
        """时序相关性 (CORR)
---------
    窗口内价格与**时间序号**的相关系数，衡量趋势线性程度（±1 很直，0 很乱）；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> corr(x, index) in window

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.corr(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.CORR(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["count"])
    def count(self, periods: int = 20, **kwargs) -> IndSeries:
        """窗口内条件计数 (COUNT)
---------
    窗口内**条件成立**的根数，统计连续上涨 / 放量天数等；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> count(cond, n)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.count(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.COUNT(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["count_v"])
    def count_v(self, periods: int = 20, **kwargs) -> IndSeries:
        """窗口内条件计数（可变窗口） (COUNT_V)
---------
    和 `COUNT` 相同，窗口可逐根变化。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> count(cond, n_i)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.count_v(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.COUNT_V(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["dma"])
    def dma(self, weight: float = 0.5, **kwargs) -> IndSeries:
        """指数平滑（固定权重） (DMA)
---------
    直接用权重做指数平滑，等价于自定义 α 的 EMA。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> dma_i = w·x_i + (1-w)·dma_{i-1}

参数:
---------
>>> weight (float): 参数. 默认: 0.5

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.dma()
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.DMA(weight)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["dma_v"])
    def dma_v(self, weight: float = 0.5, **kwargs) -> IndSeries:
        """指数平滑（可变权重） (DMA_V)
---------
    权重可逐根变化，常用于自适应均线。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> dma_i = w_i·x_i + (1-w_i)·dma_{i-1}

参数:
---------
>>> weight (float): 参数. 默认: 0.5

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.dma_v()
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.DMA_V(weight)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["ema"])
    def ema(self, period: int = 20, **kwargs) -> IndSeries:
        """指数移动平均 (EMA)
---------
    按指数衰减加权，越新的价格权重越大，比 MA 更灵敏。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> ema_i = α·x_i + (1-α)·ema_{i-1}，α = 2/(period+1)

参数:
---------
>>> period (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.ema(period=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.EMA(period)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["ema_v"])
    def ema_v(self, periods: int = 20, **kwargs) -> IndSeries:
        """指数移动平均（可变窗口） (EMA_V)
---------
    和 `EMA` 相同，平滑系数可**逐根变化**。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> α_i = 2/(period_i+1)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.ema_v(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.EMA_V(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["entropy"])
    def entropy(self, periods: int = 20, bins: int = 10, **kwargs) -> IndSeries:
        """滚动香农熵 (ENTROPY)
---------
    窗口内分箱后的信息熵，衡量"混乱度"（熵低 = 单边，熵高 = 震荡）；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> -sum(p·ln p)，p 为等宽分箱频率

参数:
---------
>>> periods (int): 参数. 默认: 20
>>> bins (int): 参数. 默认: 10

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.entropy(periods=20, bins=10)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.ENTROPY(periods, bins)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["hhv"])
    def hhv(self, periods: int = 20, **kwargs) -> IndSeries:
        """区间最高值 (HHV)
---------
    前 n 根（含当前）的最高价——画通道上沿、突破位。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> HHV(x, n) = max(x[i-n+1 .. i])

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.hhv(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.HHV(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["hhvbars"])
    def hhvbars(self, periods: int = 20, **kwargs) -> IndSeries:
        """距区间最高点的根数 (HHVBARS)
---------
    最高点出现在几根之前（0 = 就是当前这根），用于判断高点新旧。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> i - argmax(x[i-n+1 .. i])

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.hhvbars(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.HHVBARS(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["hhvbars_v"])
    def hhvbars_v(self, periods: int = 20, **kwargs) -> IndSeries:
        """距区间最高点的根数（可变窗口） (HHVBARS_V)
---------
    和 `HHVBARS` 相同，回看根数可逐根变化。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> 同上，n 用 n_i

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.hhvbars_v(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.HHVBARS_V(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["hhv_v"])
    def hhv_v(self, periods: int = 20, **kwargs) -> IndSeries:
        """区间最高值（可变窗口） (HHV_V)
---------
    和 `HHV` 相同，回看根数可逐根变化。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> 同上，n 用 n_i

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.hhv_v(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.HHV_V(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["intercept"])
    def intercept(self, periods: int = 20, **kwargs) -> IndSeries:
        """线性回归截距 (INTERCEPT)
---------
    窗口内价格回归直线的截距（≈ 窗口起点价格水平），可当趋势基准线；主图。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> intercept of linreg(x, n)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.intercept(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.INTERCEPT(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["kurtosis"])
    def kurtosis(self, periods: int = 20, **kwargs) -> IndSeries:
        """滚动超额峰度 (KURTOSIS)
---------
    尾部厚度（>0 尖峰厚尾、<0 平顶），极端行情预警用；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> 调整 Fisher 公式（与 pandas 一致，超额峰度）

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.kurtosis(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.KURTOSIS(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["llv"])
    def llv(self, periods: int = 20, **kwargs) -> IndSeries:
        """区间最低值 (LLV)
---------
    前 n 根（含当前）的最低价——画通道下沿、支撑位。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> LLV(x, n) = min(x[i-n+1 .. i])

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.llv(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.LLV(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["llvbars"])
    def llvbars(self, periods: int = 20, **kwargs) -> IndSeries:
        """距区间最低点的根数 (LLVBARS)
---------
    最低点出现在几根之前（0 = 当前这根）。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> i - argmin(x[i-n+1 .. i])

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.llvbars(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.LLVBARS(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["llvbars_v"])
    def llvbars_v(self, periods: int = 20, **kwargs) -> IndSeries:
        """距区间最低点的根数（可变窗口） (LLVBARS_V)
---------
    和 `LLVBARS` 相同，回看根数可逐根变化。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> 同上，n 用 n_i

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.llvbars_v(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.LLVBARS_V(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["llv_v"])
    def llv_v(self, periods: int = 20, **kwargs) -> IndSeries:
        """区间最低值（可变窗口） (LLV_V)
---------
    和 `LLV` 相同，回看根数可逐根变化。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> 同上，n 用 n_i

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.llv_v(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.LLV_V(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["lwma"])
    def lwma(self, periods: int = 20, **kwargs) -> IndSeries:
        """线性加权移动平均 (LWMA)
---------
    窗口内按 1..n 线性加权，越新权重越大（比 MA 跟手、比 EMA 稳）。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> LWMA = sum(x_i · w_i) / sum(w_i)，w_i = 1..n

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.lwma(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.LWMA(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["lwma_v"])
    def lwma_v(self, periods: int = 20, **kwargs) -> IndSeries:
        """线性加权移动平均（可变窗口） (LWMA_V)
---------
    和 `LWMA` 相同，窗口可逐根变化。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> 同上，n 用 n_i

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.lwma_v(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.LWMA_V(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["ma"])
    def ma(self, periods: int = 20, **kwargs) -> IndSeries:
        """简单移动平均 (MA)
---------
    最基础的均线：窗口内收盘价的算术平均，用来平滑噪声、看趋势方向。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> MA(x, n) = sum(x, n) / n

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.ma(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.MA(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["max_drawdown"])
    def max_drawdown(self, periods: int = 20, **kwargs) -> IndSeries:
        """滚动最大回撤 (MAX_DRAWDOWN)
---------
    窗口内的最大峰谷跌幅（负数，-0.2 = 回撤 20%），评估持有风险；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> min((x - 峰值) / 峰值)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.max_drawdown(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.MAX_DRAWDOWN(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["ma_v"])
    def ma_v(self, periods: int = 20, **kwargs) -> IndSeries:
        """简单移动平均（可变窗口） (MA_V)
---------
    和 `MA` 相同，只是窗口长度可以**逐根变化**（例如用 ATR 或成交量自适应）。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> MA_V(x, n_i) = sum(x, n_i) / n_i

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.ma_v(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.MA_V(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["min_max_diff"])
    def min_max_diff(self, periods: int = 20, **kwargs) -> IndSeries:
        """区间振幅 (MIN_MAX_DIFF)
---------
    窗口内最高与最低之差（ATR 的极值版），衡量波动幅度；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> max(x, d) - min(x, d)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.min_max_diff(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.MIN_MAX_DIFF(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["moment"])
    def moment(self, periods: int = 20, k: int = 1, **kwargs) -> IndSeries:
        """滚动 k 阶中心矩 (MOMENT)
---------
    分布形状的原始矩（k=2 方差、k=3 偏度、k=4 峰度）；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> moment = mean((x - mean)^k)

参数:
---------
>>> periods (int): 参数. 默认: 20
>>> k (int): 参数. 默认: 1

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.moment(periods=20, k=1)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.MOMENT(periods, k)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["product"])
    def product(self, periods: int = 20, **kwargs) -> IndSeries:
        """滚动乘积 (PRODUCT)
---------
    窗口内连乘（periods=0 时从头累计），复利 / 比值累乘场景用；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> prod(x[i-n+1 .. i])

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.product(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.PRODUCT(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["quantile"])
    def quantile(self, periods: int = 20, q: float = 0.5, **kwargs) -> IndSeries:
        """滚动分位数 (QUANTILE)
---------
    窗口内的 q 分位值（线性插值），可做动态支撑 / 压力；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> quantile(x[i-n+1 .. i], q)

参数:
---------
>>> periods (int): 参数. 默认: 20
>>> q (float): 参数. 默认: 0.5

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.quantile(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.QUANTILE(periods, q)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["rank"])
    def rank(self, periods: int = 20, **kwargs) -> IndSeries:
        """滚动分位排名 (RANK)
---------
    当前值在窗口内的排名（min 法处理并列），取值 0..n，做横截面 / 时序强弱比较好用；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> rank(x_i) in x[i-n+1 .. i]

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.rank(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.RANK(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["ref"])
    def ref(self, periods: int = 20, **kwargs) -> IndSeries:
        """向前引用（位移） (REF)
---------
    取 n 根之前的值（0 = 当前），常用于算涨跌、比较前高前低。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> REF(x, n)_i = x[i-n]

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.ref(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.REF(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["ref_v"])
    def ref_v(self, periods: int = 20, **kwargs) -> IndSeries:
        """向前引用（可变位移） (REF_V)
---------
    和 `REF` 相同，回退根数可逐根变化。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> REF_V(x, n)_i = x[i-n_i]

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.ref_v(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.REF_V(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["sharpe"])
    def sharpe(self, periods: int = 20, **kwargs) -> IndSeries:
        """滚动夏普比率 (SHARPE)
---------
    窗口内收益均值 / 收益标准差，衡量风险调整后的收益质量；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> sharpe = mean(ret) / stddev(ret)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.sharpe(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.SHARPE(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["skewness"])
    def skewness(self, periods: int = 20, **kwargs) -> IndSeries:
        """滚动偏度 (SKEWNESS)
---------
    分布左右偏斜程度（>0 右偏 / 尖峰在左），配合波动率看风险形态；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> Fisher-Pearson 调整式（与 pandas 一致）

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.skewness(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.SKEWNESS(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["slope"])
    def slope(self, periods: int = 20, **kwargs) -> IndSeries:
        """线性回归斜率 (SLOPE)
---------
    窗口内价格回归直线的斜率（每根变化量），判断趋势强弱 / 转向；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> slope of linreg(x, n)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.slope(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.SLOPE(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["sma"])
    def sma(self, n: int = 5, m: int = 2, **kwargs) -> IndSeries:
        """SMA（通达信式指数平均） (SMA)
---------
    权重 = m/n 的指数平均，即通称的 `SMA(X, N, M)`；比 EMA 更平滑。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> y_i = (m·x_i + (n-m)·y_{i-1}) / n

参数:
---------
>>> n (int): 参数. 默认: 5
>>> m (int): 参数. 默认: 2

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.sma(n=20, m=2)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.SMA(n, m)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=True, lines=["sma_v"])
    def sma_v(self, ns: int = 1, m: int = 2, **kwargs) -> IndSeries:
        """SMA（可变周期） (SMA_V)
---------
    和 `SMA` 相同，周期可逐根变化。
    图上归类：**主图叠加**（与价格同量纲）。

计算方法:
---------
>>> y_i = (m·x_i + (ns_i-m)·y_{i-1}) / ns_i

参数:
---------
>>> ns (int): 参数. 默认: 1
>>> m (int): 参数. 默认: 2

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.sma_v(ns=20, m=2)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.SMA_V(ns, m)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["stddev"])
    def stddev(self, periods: int = 20, **kwargs) -> IndSeries:
        """滚动标准差 (STDDEV)
---------
    衡量波动大小（σ），是布林带 / 波动率过滤的基础；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> std = sqrt(sum((x-mean)^2) / (n-1))

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.stddev(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.STDDEV(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["sum"])
    def sum(self, periods: int = 20, **kwargs) -> IndSeries:
        """滚动求和 (SUM)
---------
    窗口内求和（periods=0 时是从头累计），成交量 / 资金流指标常用；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> sum(x[i-n+1 .. i])

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.sum(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.SUM(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["var"])
    def var(self, periods: int = 20, **kwargs) -> IndSeries:
        """滚动方差 (VAR)
---------
    标准差的平方（σ²），波动率的原始度量；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> var = sum((x-mean)^2) / (n-1)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.var(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.VAR(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha", overlap=False, lines=["zscore"])
    def zscore(self, periods: int = 20, **kwargs) -> IndSeries:
        """滚动 Z 分数 (ZSCORE)
---------
    当前值偏离均值多少个 σ（|z|>2 常视为极端），用于标准化信号；放副图。
    图上归类：**副图指标**（统计量，不与价格同轴）。

计算方法:
---------
>>> z = (x - mean) / std（样本 std，ddof=1）

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.zscore(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.ZSCORE(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def abs(self, **kwargs) -> IndSeries:
        """绝对值 (ABS)
---------
    逐元素取绝对值（ABS(x) = |x|），构造幅度类条件时用。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> ABS(x) = |x|

参数:
---------
>>> 无参数

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.abs()
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.ABS()`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def all(self, periods: int = 20, **kwargs) -> IndSeries:
        """窗口内恒成立 (ALL)
---------
    窗口内条件**始终为真**返回 1，否则 0（periods=0 = 从开始至今）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> ALL(cond, periods)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.all(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.ALL(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def alpha(self, benchmark=None, periods: int = 20, **kwargs) -> IndSeries:
        """滚动 Jensen Alpha (ALPHA)
---------
    扣除 Beta 后的**超额收益**（跑赢基准多少），因子研究常用。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> α = mean(x) - β·mean(benchmark)

参数:
---------
>>> periods (int): 参数. 默认: 20
>>> benchmark: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.alpha(benchmark=self.data.close, periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.ALPHA(benchmark, periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def any(self, periods: int = 20, **kwargs) -> IndSeries:
        """窗口内至少一次成立 (ANY)
---------
    窗口内条件**出现过**返回 1，否则 0。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> ANY(cond, periods)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.any(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.ANY(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def backfill(self, **kwargs) -> IndSeries:
        """向前填充 NaN (BACKFILL)
---------
    用最近一个有效值填补 NaN（开头的 NaN 保留），清洗数据用。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> x[i] = x[i-1] if isnan(x[i])

参数:
---------
>>> 无参数

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.backfill()
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.BACKFILL()`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def backset(self, periods: int = 20, **kwargs) -> IndSeries:
        """回溯置真 (BACKSET)
---------
    条件成立时，把**当前及之前 periods-1 根**都置为真（画"多久之前发生过"）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> BACKSET(cond, periods)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.backset(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.BACKSET(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def barslast(self, **kwargs) -> IndSeries:
        """距上次成立的根数 (BARSLAST)
---------
    距**最近一次**条件为真的根数（0 = 当前这根），判断信号新鲜度。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> bars since last(cond)

参数:
---------
>>> 无参数

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.barslast()
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.BARSLAST()`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def barssince(self, **kwargs) -> IndSeries:
        """距首次成立的根数 (BARSSINCE)
---------
    距**第一次**条件为真的根数，用于统计"已经涨了几天"。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> bars since first(cond)

参数:
---------
>>> 无参数

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.barssince()
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.BARSSINCE()`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def beta(self, benchmark=None, periods: int = 20, **kwargs) -> IndSeries:
        """滚动 Beta (BETA)
---------
    标的相对基准的**系统性风险**（1 = 同步，>1 更波动）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> β = Cov(x, benchmark) / Var(benchmark)

参数:
---------
>>> periods (int): 参数. 默认: 20
>>> benchmark: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.beta(benchmark=self.data.close, periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.BETA(benchmark, periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def bw_split(self, dividend=None, transfer_shares=None, right_shares=None, right_price=None, **kwargs) -> IndSeries:
        """后向拆股 / 分红复权 (BW_SPLIT)
---------
    从最新往最早按等差数列调整价格（除权除息后保持历史连续）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> price_adj = price / factor

参数:
---------
>>> dividend: 第二条序列（pd.Series / np.ndarray，必填）
>>> transfer_shares: 第二条序列（pd.Series / np.ndarray，必填）
>>> right_shares: 第二条序列（pd.Series / np.ndarray，必填）
>>> right_price: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.bw_split(dividend=self.data.close, transfer_shares=self.data.close, right_shares=self.data.close, right_price=self.data.close)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.BW_SPLIT(dividend, transfer_shares, right_shares, right_price)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def bw_split_factor(self, dividend=None, transfer_shares=None, right_shares=None, right_price=None, **kwargs) -> IndSeries:
        """后向复权因子 (BW_SPLIT_FACTOR)
---------
    只算后向复权因子（等比数列），价格自己乘即可。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> factor 逐步相乘

参数:
---------
>>> dividend: 第二条序列（pd.Series / np.ndarray，必填）
>>> transfer_shares: 第二条序列（pd.Series / np.ndarray，必填）
>>> right_shares: 第二条序列（pd.Series / np.ndarray，必填）
>>> right_price: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.bw_split_factor(dividend=self.data.close, transfer_shares=self.data.close, right_shares=self.data.close, right_price=self.data.close)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.BW_SPLIT_FACTOR(dividend, transfer_shares, right_shares, right_price)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def cc_rank(self, **kwargs) -> IndSeries:
        """横截面排名百分比 (CC_RANK)
---------
    同一时刻跨标的排名百分比（0~1，同值取平均）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> rank(x) / groups

参数:
---------
>>> 无参数

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.cc_rank()
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.CC_RANK()`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def cc_zscore(self, **kwargs) -> IndSeries:
        """横截面 Z 分数 (CC_ZSCORE)
---------
    同一时刻跨标的标准化（NaN 不参与均值/方差）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> z = (x - mean) / std（跨标的）

参数:
---------
>>> 无参数

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.cc_zscore()
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.CC_ZSCORE()`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def corr2(self, y=None, periods: int = 20, **kwargs) -> IndSeries:
        """两序列滚动相关 (CORR2)
---------
    两条序列在窗口内的相关系数（±1），配对 / 对冲时判断联动强弱。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> corr = Cov(x,y) / (σx·σy)

参数:
---------
>>> periods (int): 参数. 默认: 20
>>> y: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.corr2(y=self.data.close, periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.CORR2(y, periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def count_nans(self, periods: int = 20, **kwargs) -> IndSeries:
        """窗口内 NaN 计数 (COUNT_NANS)
---------
    前 periods 根里 NaN 的个数，数据质量体检用。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> count(isnan, n)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.count_nans(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.COUNT_NANS(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def cov(self, y=None, periods: int = 20, **kwargs) -> IndSeries:
        """滚动协方差 (COV)
---------
    两条序列的协方差（方向一致的联动程度）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> cov = (Σxy - ΣxΣy/n) / (n-1)

参数:
---------
>>> periods (int): 参数. 默认: 20
>>> y: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.cov(y=self.data.close, periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.COV(y, periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def cross(self, b=None, **kwargs) -> IndSeries:
        """上穿（金叉） (CROSS)
---------
    `a` 上穿 `b`（上一根 a<b、当前 a>=b）为真；`a` 固定取 close，`b` 由参数传入。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> CROSS(a,b) = a[i-1] < b[i-1] and a[i] >= b[i]

参数:
---------
>>> b: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.cross(b=self.data.close)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.CROSS(b)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def filter(self, periods: int = 20, **kwargs) -> IndSeries:
        """信号去抖 (FILTER)
---------
    条件成立一次后，**之后 periods 根内不再算成立**（过滤连续信号）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> FILTER(cond, periods)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.filter(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.FILTER(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def fret(self, close=None, is_calc=None, delay: int = 1, periods: int = 20, **kwargs) -> IndSeries:
        """未来收益（回测标签） (FRET)
---------
    从延迟 delay 根后的开盘价，到之后再 periods-1 根的收盘价的收益率——**用于生成训练标签**（未来函数）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> (Close[t+delay+periods-1] - Open[t+delay]) / Open[t+delay]

参数:
---------
>>> delay (int): 参数. 默认: 1
>>> periods (int): 参数. 默认: 20
>>> close: 第二条序列（pd.Series / np.ndarray，必填）
>>> is_calc: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.fret(close=self.data.close, is_calc=self.data.close, periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.FRET(close, is_calc, delay, periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def fw_split(self, dividend=None, transfer_shares=None, right_shares=None, right_price=None, **kwargs) -> IndSeries:
        """前向拆股 / 分红复权 (FW_SPLIT)
---------
    从最早往最新按等差数列调整价格（前复权口径）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> price_adj = price * factor

参数:
---------
>>> dividend: 第二条序列（pd.Series / np.ndarray，必填）
>>> transfer_shares: 第二条序列（pd.Series / np.ndarray，必填）
>>> right_shares: 第二条序列（pd.Series / np.ndarray，必填）
>>> right_price: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.fw_split(dividend=self.data.close, transfer_shares=self.data.close, right_shares=self.data.close, right_price=self.data.close)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.FW_SPLIT(dividend, transfer_shares, right_shares, right_price)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def fw_split_factor(self, dividend=None, transfer_shares=None, right_shares=None, right_price=None, **kwargs) -> IndSeries:
        """前向复权因子 (FW_SPLIT_FACTOR)
---------
    只算前向复权因子（等比数列）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> factor 逐步相乘

参数:
---------
>>> dividend: 第二条序列（pd.Series / np.ndarray，必填）
>>> transfer_shares: 第二条序列（pd.Series / np.ndarray，必填）
>>> right_shares: 第二条序列（pd.Series / np.ndarray，必填）
>>> right_price: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.fw_split_factor(dividend=self.data.close, transfer_shares=self.data.close, right_shares=self.data.close, right_price=self.data.close)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.FW_SPLIT_FACTOR(dividend, transfer_shares, right_shares, right_price)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def group_rank(self, input=None, **kwargs) -> IndSeries:
        """分组内排名 (GROUP_RANK)
---------
    同一时刻按 `category` 分组后组内排名（0~1），横截面选股用。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> rank(x) within category

参数:
---------
>>> input: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.group_rank(input=self.data.close)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.GROUP_RANK(input)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def group_zscore(self, input=None, **kwargs) -> IndSeries:
        """分组内 Z 分数 (GROUP_ZSCORE)
---------
    同一时刻按 `category` 分组后组内标准化，横截面比较用。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> z = (x - group_mean) / group_std

参数:
---------
>>> input: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.group_zscore(input=self.data.close)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.GROUP_ZSCORE(input)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def last(self, **kwargs) -> IndSeries:
        """连续成立根数 (LAST)
---------
    截至当前条件**连续成立**了多少根（断掉归零）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> LAST(cond)

参数:
---------
>>> 无参数

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.last()
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.LAST()`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def longcross(self, b=None, n: int = 5, **kwargs) -> IndSeries:
        """长期上穿 (LONGCROSS)
---------
    连续 n 根 `a<b` 之后**首次**上穿 `b`（要求"站上去之前压了 n 根"）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> all(a<b, n) then a>=b

参数:
---------
>>> n (int): 参数. 默认: 5
>>> b: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.longcross(b=self.data.close, n=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.LONGCROSS(b, n)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def max(self, b=None, **kwargs) -> IndSeries:
        """逐元素取大 (MAX)
---------
    两个序列逐根取较大值（可当"价格站上某线"的台阶线）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> MAX(a, b)

参数:
---------
>>> b: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.max(b=self.data.close)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.MAX(b)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def min(self, b=None, **kwargs) -> IndSeries:
        """逐元素取小 (MIN)
---------
    两个序列逐根取较小值。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> MIN(a, b)

参数:
---------
>>> b: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.min(b=self.data.close)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.MIN(b)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def neutralize(self, input=None, **kwargs) -> IndSeries:
        """中性化 (NEUTRALIZE)
---------
    剔除 `category`（行业等）对数值的影响，得到行业内可比的残差。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> x - group_mean(x)（按 category 分组）

参数:
---------
>>> input: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.neutralize(input=self.data.close)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.NEUTRALIZE(input)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def rcross(self, b=None, **kwargs) -> IndSeries:
        """下穿（死叉） (RCROSS)
---------
    `a` 下穿 `b`（上一根 a>b、当前 a<=b）为真；`a` 固定取 close。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> RCROSS(a,b) = a[i-1] > b[i-1] and a[i] <= b[i]

参数:
---------
>>> b: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.rcross(b=self.data.close)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.RCROSS(b)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def regbeta(self, x=None, periods: int = 20, **kwargs) -> IndSeries:
        """回归系数（Y 对 X） (REGBETA)
---------
    Y 对 X 回归的斜率 Beta（X 变 1 单位，Y 平均变多少）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> β = Cov(x, y) / Var(x)

参数:
---------
>>> periods (int): 参数. 默认: 20
>>> x: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.regbeta(x=self.data.close, periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.REGBETA(x, periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def regresi(self, x=None, periods: int = 20, **kwargs) -> IndSeries:
        """回归残差 (REGRESI)
---------
    Y 对 X 回归后**最后一点的残差**，衡量偏离程度（均值回归信号）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> ε = y - (a + b·x)

参数:
---------
>>> periods (int): 参数. 默认: 20
>>> x: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.regresi(x=self.data.close, periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.REGRESI(x, periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def rlongcross(self, b=None, n: int = 5, **kwargs) -> IndSeries:
        """长期下穿 (RLONGCROSS)
---------
    连续 n 根 `a>b` 之后**首次**下穿 `b`。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> all(a>b, n) then a<=b

参数:
---------
>>> n (int): 参数. 默认: 5
>>> b: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.rlongcross(b=self.data.close, n=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.RLONGCROSS(b, n)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def scan_add(self, condition=None, **kwargs) -> IndSeries:
        """条件累加（自引用） (SCAN_ADD)
---------
    `r[i] = r[i-1] + (cond ? x : 0)`；用于 GTJA 这类需要**自引用**的 alpha 表达式。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> r[i] = r[i-1] + (cond[i] ? x[i] : 0)

参数:
---------
>>> condition: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.scan_add(condition=self.data.close)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.SCAN_ADD(condition)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def scan_mul(self, condition=None, **kwargs) -> IndSeries:
        """条件累乘（自引用） (SCAN_MUL)
---------
    `r[i] = r[i-1] * (cond ? x : 1)`；自引用乘法版的 alpha 表达式。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> r[i] = r[i-1] * (cond[i] ? x[i] : 1)

参数:
---------
>>> condition: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.scan_mul(condition=self.data.close)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.SCAN_MUL(condition)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def sumbars(self, amount: float = 1.0, **kwargs) -> IndSeries:
        """累计达到目标值的根数 (SUMBARS)
---------
    从当前往回累加，到累计值 ≥ `amount` 需要几根（AmiBroker 同款）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> bars until sum >= amount

参数:
---------
>>> amount (float): 参数. 默认: 1.0

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.sumbars()
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.SUMBARS(amount)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def sumif(self, condition=None, periods: int = 20, **kwargs) -> IndSeries:
        """条件滚动求和 (SUMIF)
---------
    窗口内**只对条件成立**的根求和（例如只统计上涨日的成交量）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> sum(x where cond, n)

参数:
---------
>>> periods (int): 参数. 默认: 20
>>> condition: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.sumif(condition=self.data.close, periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.SUMIF(condition, periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def weighted_delay(self, periods: int = 20, **kwargs) -> IndSeries:
        """加权延迟（滞后 LWMA） (WEIGHTED_DELAY)
---------
    对**滞后序列**做线性加权，等价于"把过去 k 根按 1..k 加权"的平滑滞后值。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> sum((k-i)·x[i]) / (k(k+1)/2)

参数:
---------
>>> periods (int): 参数. 默认: 20

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.weighted_delay(periods=20)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.WEIGHTED_DELAY(periods)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    @tobtind(lib="alpha")
    def where(self, a=None, b=None, **kwargs) -> IndSeries:
        """条件选择 (WHERE)
---------
    按条件在 a / b 之间逐根取值（三元表达式向量化）。
    图上归类：**工具函数**（算子上不了图，但返回 IndSeries）。

计算方法:
---------
>>> WHERE(cond, a, b) = a if cond else b

参数:
---------
>>> a: 第二条序列（pd.Series / np.ndarray，必填）
>>> b: 第二条序列（pd.Series / np.ndarray，必填）

所需数据字段:
---------
>>> close（`FILED.C`：K 线收盘价 / IndSeries 自身）

使用案例:
---------
>>> ind = self.data.alpha.where(a=self.data.close, b=self.data.close)
>>> if ind.rising:
>>>     return "指标向上"

说明:
---------
    - 原生接口：`alpha.WHERE(a, b)`；
    - alpha 用**扩张窗口**（`min_periods=1`），前几根就有值；
    - 依赖可选包 py-alpha-lib（Rust 实现）✓"""
        ...

    #: 不是「单序列进 → 同长序列出」的：多序列 / 条件 / 拆股 / 分组 …
    #: （选择器里不出现；策略里仍可调用 ✓）
    NON_KLINE_INDICATORS = ["abs", "all", "alpha", "any", "backfill", "backset", "barslast", "barssince", "beta", "bw_split", "bw_split_factor", "cc_rank", "cc_zscore", "corr2", "count_nans", "cov", "cross", "filter", "fret", "fw_split", "fw_split_factor", "group_rank", "group_zscore", "last", "longcross", "max", "min", "neutralize", "rcross", "regbeta", "regresi", "rlongcross", "scan_add", "scan_mul", "sumbars", "sumif", "weighted_delay", "where"]
