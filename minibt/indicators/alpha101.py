"""**WQ Alpha101** 因子（从 `py-alpha-lib` 官方示例内置 ✓）

`WQ Alpha101` 共 **101 个因子**，前缀 `alpha101_`，
入口 `self.kline.alpha101.alpha001()` …

### 单标的 vs 横截面

* **18 个纯时序因子**：只用本标的价量 → 任何 IndFrame 都能算，
  desk 选择器里能看到（副图）；
* 其余 **83 个**是横截面 / 缺外部数据因子：
  要自己准备正确的 IndFrame（`securityid` / `tradetime` /
  `indclass` / 基准指数 …），否则 alpha 会抛原生错误；
  这些已进 `NON_KLINE_INDICATORS`，**不在 desk 选择器里显示** ✓

### 用法

```python
factor = self.data.alpha101.alpha001()   # 副图一条线
```

依赖可选包 `py-alpha-lib`（Rust）：没装时调用抛可读错误，
`import minibt` 不受影响 ✓
"""

from __future__ import annotations

from .base import tobtind
from ..utils import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_ import *
    from .core import *


class Alpha101:
    """## WQ Alpha101 因子

    - 全部 101 个因子（前缀 `alpha101_`），全部**副图**；
    - 纯时序 18 个可直接用（desk 可见）：
      `self.data.alpha101.alpha001()`；
    - 横截面 / 缺数据因子要自备正确的 IndFrame 列，错误由 alpha 原生抛出；
    - 依赖可选包 py-alpha-lib（BSD-2-Clause 示例原样 vendor）。
    """
    _perfixes: str = "alpha101_"
    _df: IndFrame | IndSeries

    def __init__(self, data):
        self._df = data
    @tobtind(lib="alpha101", overlap=False, lines=["alpha001"])
    def alpha001(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #1
---------
    (rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) -0.5)

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha002"])
    def alpha002(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #2
---------
    (-1 * correlation(rank(delta(log(volume), 2)), rank(((close - open) / open)), 6))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha003"])
    def alpha003(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #3
---------
    (-1 * correlation(rank(open), rank(volume), 10))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha004"])
    def alpha004(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #4
---------
    (-1 * Ts_Rank(rank(low), 9))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha005"])
    def alpha005(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #5
---------
    (rank((open - (sum(vwap, 10) / 10))) * (-1 * abs(rank((close - vwap)))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha006"])
    def alpha006(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #6
---------
    (-1 * correlation(open, volume, 10))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha007"])
    def alpha007(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #7
---------
    ((adv20 < volume) ? ((-1 * ts_rank(abs(delta(close, 7)), 60)) * sign(delta(close, 7))) : (-1* 1))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha008"])
    def alpha008(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #8
---------
    (-1 * rank(((sum(open, 5) * sum(returns, 5)) - delay((sum(open, 5) * sum(returns, 5)),10))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha009"])
    def alpha009(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #9
---------
    ((0 < ts_min(delta(close, 1), 5)) ? delta(close, 1) : ((ts_max(delta(close, 1), 5) < 0) ?delta(close, 1) : (-1 * delta(close, 1))))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha010"])
    def alpha010(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #10
---------
    rank(((0 < ts_min(delta(close, 1), 4)) ? delta(close, 1) : ((ts_max(delta(close, 1), 4) < 0)? delta(close, 1) : (-1 * delta(close, 1)))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha011"])
    def alpha011(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #11
---------
    ((rank(ts_max((vwap - close), 3)) + rank(ts_min((vwap - close), 3))) *rank(delta(volume, 3)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha012"])
    def alpha012(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #12
---------
    (sign(delta(volume, 1)) * (-1 * delta(close, 1)))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha013"])
    def alpha013(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #13
---------
    (-1 * rank(covariance(rank(close), rank(volume), 5)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha014"])
    def alpha014(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #14
---------
    ((-1 * rank(delta(returns, 3))) * correlation(open, volume, 10))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha015"])
    def alpha015(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #15
---------
    (-1 * sum(rank(correlation(rank(high), rank(volume), 3)), 3))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha016"])
    def alpha016(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #16
---------
    (-1 * rank(covariance(rank(high), rank(volume), 5)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha017"])
    def alpha017(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #17
---------
    (((-1 * rank(ts_rank(close, 10))) * rank(delta(delta(close, 1), 1))) *rank(ts_rank((volume / adv20), 5)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha018"])
    def alpha018(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #18
---------
    (-1 * rank(((stddev(abs((close - open)), 5) + (close - open)) + correlation(close, open,10))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha019"])
    def alpha019(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #19
---------
    ((-1 * sign(((close - delay(close, 7)) + delta(close, 7)))) * (1 + rank((1 + sum(returns,250)))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha020"])
    def alpha020(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #20
---------
    (((-1 * rank((open - delay(high, 1)))) * rank((open - delay(close, 1)))) * rank((open -delay(low, 1))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha021"])
    def alpha021(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #21
---------
    ((((sum(close, 8) / 8) + stddev(close, 8)) < (sum(close, 2) / 2)) ? (-1 * 1) : (((sum(close,2) / 2) < ((sum(close, 8) / 8) - stddev(close, 8))) ? 1 : (((1 < (volume / adv20)) || ((volume /adv20) == 1)) ? 1 : (-1 * 1))))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha022"])
    def alpha022(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #22
---------
    (-1 * (delta(correlation(high, volume, 5), 5) * rank(stddev(close, 20))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha023"])
    def alpha023(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #23
---------
    (((sum(high, 20) / 20) < high) ? (-1 * delta(high, 2)) : 0)

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha024"])
    def alpha024(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #24
---------
    ((((delta((sum(close, 100) / 100), 100) / delay(close, 100)) < 0.05) ||((delta((sum(close, 100) / 100), 100) / delay(close, 100)) == 0.05)) ? (-1 * (close - ts_min(close,100))) : (-1 * delta(close, 3)))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha025"])
    def alpha025(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #25
---------
    rank(((((-1 * returns) * adv20) * vwap) * (high - close)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha026"])
    def alpha026(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #26
---------
    (-1 * ts_max(correlation(ts_rank(volume, 5), ts_rank(high, 5), 5), 3))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha027"])
    def alpha027(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #27
---------
    ((0.5 < rank((sum(correlation(rank(volume), rank(vwap), 6), 2) / 2.0))) ? (-1 * 1) : 1)

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha028"])
    def alpha028(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #28
---------
    scale(((correlation(adv20, low, 5) + ((high + low) / 2)) - close))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha029"])
    def alpha029(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #29
---------
    (min(product(rank(rank(scale(log(sum(ts_min(rank(rank((-1 * rank(delta((close - 1),5))))), 2), 1))))), 1), 5) + ts_rank(delay((-1 * returns), 6), 5))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha030"])
    def alpha030(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #30
---------
    (((1.0 - rank(((sign((close - delay(close, 1))) + sign((delay(close, 1) - delay(close, 2)))) +sign((delay(close, 2) - delay(close, 3)))))) * sum(volume, 5)) / sum(volume, 20))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha031"])
    def alpha031(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #31
---------
    ((rank(rank(rank(decay_linear((-1 * rank(rank(delta(close, 10)))), 10)))) + rank((-1 *delta(close, 3)))) + sign(scale(correlation(adv20, low, 12))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha032"])
    def alpha032(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #32
---------
    (scale(((sum(close, 7) / 7) - close)) + (20 * scale(correlation(vwap, delay(close, 5),230))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha033"])
    def alpha033(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #33
---------
    rank((-1 * ((1 - (open / close))^1)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha034"])
    def alpha034(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #34
---------
    rank(((1 - rank((stddev(returns, 2) / stddev(returns, 5)))) + (1 - rank(delta(close, 1)))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha035"])
    def alpha035(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #35
---------
    ((Ts_Rank(volume, 32) * (1 - Ts_Rank(((close + high) - low), 16))) * (1 -Ts_Rank(returns, 32)))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha036"])
    def alpha036(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #36
---------
    (((((2.21 * rank(correlation((close - open), delay(volume, 1), 15))) + (0.7 * rank((open- close)))) + (0.73 * rank(Ts_Rank(delay((-1 * returns), 6), 5)))) + rank(abs(correlation(vwap,adv20, 6)))) + (0.6 * rank((((sum(close, 200) / 200) - open) * (close - open)))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha037"])
    def alpha037(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #37
---------
    (rank(correlation(delay((open - close), 1), close, 200)) + rank((open - close)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha038"])
    def alpha038(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #38
---------
    ((-1 * rank(Ts_Rank(close, 10))) * rank((close / open)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha039"])
    def alpha039(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #39
---------
    ((-1 * rank((delta(close, 7) * (1 - rank(decay_linear((volume / adv20), 9)))))) * (1 +rank(sum(returns, 250))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha040"])
    def alpha040(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #40
---------
    ((-1 * rank(stddev(high, 10))) * correlation(high, volume, 10))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha041"])
    def alpha041(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #41
---------
    (((high * low)^0.5) - vwap)

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha042"])
    def alpha042(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #42
---------
    (rank((vwap - close)) / rank((vwap + close)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha043"])
    def alpha043(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #43
---------
    (ts_rank((volume / adv20), 20) * ts_rank((-1 * delta(close, 7)), 8))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha044"])
    def alpha044(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #44
---------
    (-1 * correlation(high, rank(volume), 5))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha045"])
    def alpha045(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #45
---------
    (-1 * ((rank((sum(delay(close, 5), 20) / 20)) * correlation(close, volume, 2)) *rank(correlation(sum(close, 5), sum(close, 20), 2))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha046"])
    def alpha046(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #46
---------
    ((0.25 < (((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10))) ?(-1 * 1) : (((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < 0) ? 1 :((-1 * 1) * (close - delay(close, 1)))))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha047"])
    def alpha047(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #47
---------
    ((((rank((1 / close)) * volume) / adv20) * ((high * rank((high - close))) / (sum(high, 5) /5))) - rank((vwap - delay(vwap, 5))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha048"])
    def alpha048(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #48
---------
    (indneutralize(((correlation(delta(close, 1), delta(delay(close, 1), 1), 250) *delta(close, 1)) / close), IndClass.subindustry) / sum(((delta(close, 1) / delay(close, 1))^2), 250))

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha049"])
    def alpha049(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #49
---------
    (((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < (-1 *0.1)) ? 1 : ((-1 * 1) * (close - delay(close, 1))))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha050"])
    def alpha050(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #50
---------
    (-1 * ts_max(rank(correlation(rank(volume), rank(vwap), 5)), 5))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha051"])
    def alpha051(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #51
---------
    (((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < (-1 *0.05)) ? 1 : ((-1 * 1) * (close - delay(close, 1))))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha052"])
    def alpha052(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #52
---------
    ((((-1 * ts_min(low, 5)) + delay(ts_min(low, 5), 5)) * rank(((sum(returns, 240) -sum(returns, 20)) / 220))) * ts_rank(volume, 5))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha053"])
    def alpha053(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #53
---------
    (-1 * delta((((close - low) - (high - close)) / (close - low)), 9))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha054"])
    def alpha054(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #54
---------
    ((-1 * ((low - close) * (open^5))) / ((low - high) * (close^5)))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha055"])
    def alpha055(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #55
---------
    (-1 * correlation(rank(((close - ts_min(low, 12)) / (ts_max(high, 12) - ts_min(low,12)))), rank(volume), 6))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha056"])
    def alpha056(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #56
---------
    (0 - (1 * (rank((sum(returns, 10) / sum(sum(returns, 2), 3))) * rank((returns * cap)))))

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha057"])
    def alpha057(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #57
---------
    (0 - (1 * ((close - vwap) / decay_linear(rank(ts_argmax(close, 30)), 2))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha058"])
    def alpha058(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #58
---------
    (-1 * Ts_Rank(decay_linear(correlation(IndNeutralize(vwap, IndClass.sector), volume,3.92795), 7.89291), 5.50322))

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha059"])
    def alpha059(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #59
---------
    (-1 * Ts_Rank(decay_linear(correlation(IndNeutralize(((vwap * 0.728317) + (vwap *(1 - 0.728317))), IndClass.industry), volume, 4.25197), 16.2289), 8.19648))

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha060"])
    def alpha060(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #60
---------
    (0 - (1 * ((2 * scale(rank(((((close - low) - (high - close)) / (high - low)) * volume)))) -scale(rank(ts_argmax(close, 10))))))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha061"])
    def alpha061(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #61
---------
    (rank((vwap - ts_min(vwap, 16.1219))) < rank(correlation(vwap, adv180, 17.9282)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha062"])
    def alpha062(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #62
---------
    ((rank(correlation(vwap, sum(adv20, 22.4101), 9.91009)) < rank(((rank(open) +rank(open)) < (rank(((high + low) / 2)) + rank(high))))) * -1)

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha063"])
    def alpha063(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #63
---------
    ((rank(decay_linear(delta(IndNeutralize(close, IndClass.industry), 2.25164), 8.22237))- rank(decay_linear(correlation(((vwap * 0.318108) + (open * (1 - 0.318108))), sum(adv180,37.2467), 13.557), 12.2883))) * -1)

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha064"])
    def alpha064(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #64
---------
    ((rank(correlation(sum(((open * 0.178404) + (low * (1 - 0.178404))), 12.7054),sum(adv120, 12.7054), 16.6208)) < rank(delta(((((high + low) / 2) * 0.178404) + (vwap * (1 -0.178404))), 3.69741))) * -1)

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha065"])
    def alpha065(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #65
---------
    ((rank(correlation(((open * 0.00817205) + (vwap * (1 - 0.00817205))), sum(adv60,8.6911), 6.40374)) < rank((open - ts_min(open, 13.635)))) * -1)

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha066"])
    def alpha066(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #66
---------
    ((rank(decay_linear(delta(vwap, 3.51013), 7.23052)) + Ts_Rank(decay_linear(((((low* 0.96633) + (low * (1 - 0.96633))) - vwap) / (open - ((high + low) / 2))), 11.4157), 6.72611)) * -1)

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha067"])
    def alpha067(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #67
---------
    ((rank((high - ts_min(high, 2.14593)))^rank(correlation(IndNeutralize(vwap,IndClass.sector), IndNeutralize(adv20, IndClass.subindustry), 6.02936))) * -1)

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha068"])
    def alpha068(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #68
---------
    ((Ts_Rank(correlation(rank(high), rank(adv15), 8.91644), 13.9333) <rank(delta(((close * 0.518371) + (low * (1 - 0.518371))), 1.06157))) * -1)

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha069"])
    def alpha069(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #69
---------
    ((rank(ts_max(delta(IndNeutralize(vwap, IndClass.industry), 2.72412),4.79344))^Ts_Rank(correlation(((close * 0.490655) + (vwap * (1 - 0.490655))), adv20, 4.92416),9.0615)) * -1)

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha070"])
    def alpha070(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #70
---------
    ((rank(delta(vwap, 1.29456))^Ts_Rank(correlation(IndNeutralize(close,IndClass.industry), adv50, 17.8256), 17.9171)) * -1)

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha071"])
    def alpha071(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #71
---------
    max(Ts_Rank(decay_linear(correlation(Ts_Rank(close, 3.43976), Ts_Rank(adv180,12.0647), 18.0175), 4.20501), 15.6948), Ts_Rank(decay_linear((rank(((low + open) - (vwap +vwap)))^2), 16.4662), 4.4388))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha072"])
    def alpha072(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #72
---------
    (rank(decay_linear(correlation(((high + low) / 2), adv40, 8.93345), 10.1519)) /rank(decay_linear(correlation(Ts_Rank(vwap, 3.72469), Ts_Rank(volume, 18.5188), 6.86671),2.95011)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha073"])
    def alpha073(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #73
---------
    (max(rank(decay_linear(delta(vwap, 4.72775), 2.91864)),Ts_Rank(decay_linear(((delta(((open * 0.147155) + (low * (1 - 0.147155))), 2.03608) / ((open *0.147155) + (low * (1 - 0.147155)))) * -1), 3.33829), 16.7411)) * -1)

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha074"])
    def alpha074(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #74
---------
    ((rank(correlation(close, sum(adv30, 37.4843), 15.1365)) <rank(correlation(rank(((high * 0.0261661) + (vwap * (1 - 0.0261661)))), rank(volume), 11.4791)))* -1)

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha075"])
    def alpha075(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #75
---------
    (rank(correlation(vwap, volume, 4.24304)) < rank(correlation(rank(low), rank(adv50),12.4413)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha076"])
    def alpha076(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #76
---------
    (max(rank(decay_linear(delta(vwap, 1.24383), 11.8259)),Ts_Rank(decay_linear(Ts_Rank(correlation(IndNeutralize(low, IndClass.sector), adv81,8.14941), 19.569), 17.1543), 19.383)) * -1)

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha077"])
    def alpha077(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #77
---------
    min(rank(decay_linear(((((high + low) / 2) + high) - (vwap + high)), 20.0451)),rank(decay_linear(correlation(((high + low) / 2), adv40, 3.1614), 5.64125)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha078"])
    def alpha078(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #78
---------
    (rank(correlation(sum(((low * 0.352233) + (vwap * (1 - 0.352233))), 19.7428),sum(adv40, 19.7428), 6.83313))^rank(correlation(rank(vwap), rank(volume), 5.77492)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha079"])
    def alpha079(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #79
---------
    (rank(delta(IndNeutralize(((close * 0.60733) + (open * (1 - 0.60733))),IndClass.sector), 1.23438)) < rank(correlation(Ts_Rank(vwap, 3.60973), Ts_Rank(adv150,9.18637), 14.6644)))

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha080"])
    def alpha080(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #80
---------
    ((rank(Sign(delta(IndNeutralize(((open * 0.868128) + (high * (1 - 0.868128))),IndClass.industry), 4.04545)))^Ts_Rank(correlation(high, adv10, 5.11456), 5.53756)) * -1)

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha081"])
    def alpha081(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #81
---------
    ((rank(Log(product(rank((rank(correlation(vwap, sum(adv10, 49.6054),8.47743))^4)), 14.9655))) < rank(correlation(rank(vwap), rank(volume), 5.07914))) * -1)

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha082"])
    def alpha082(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #82
---------
    (min(rank(decay_linear(delta(open, 1.46063), 14.8717)),Ts_Rank(decay_linear(correlation(IndNeutralize(volume, IndClass.sector), ((open * 0.634196) +(open * (1 - 0.634196))), 17.4842), 6.92131), 13.4283)) * -1)

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha083"])
    def alpha083(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #83
---------
    ((rank(delay(((high - low) / (sum(close, 5) / 5)), 2)) * rank(rank(volume))) / (((high -low) / (sum(close, 5) / 5)) / (vwap - close)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha084"])
    def alpha084(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #84
---------
    SignedPower(Ts_Rank((vwap - ts_max(vwap, 15.3217)), 20.7127), delta(close,4.96796))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha085"])
    def alpha085(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #85
---------
    (rank(correlation(((high * 0.876703) + (close * (1 - 0.876703))), adv30,9.61331))^rank(correlation(Ts_Rank(((high + low) / 2), 3.70596), Ts_Rank(volume, 10.1595),7.11408)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha086"])
    def alpha086(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #86
---------
    ((Ts_Rank(correlation(close, sum(adv20, 14.7444), 6.00049), 20.4195) < rank(((open+ close) - (vwap + open)))) * -1)

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha087"])
    def alpha087(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #87
---------
    (max(rank(decay_linear(delta(((close * 0.369701) + (vwap * (1 - 0.369701))),1.91233), 2.65461)), Ts_Rank(decay_linear(abs(correlation(IndNeutralize(adv81,IndClass.industry), close, 13.4132)), 4.89768), 14.4535)) * -1)

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha088"])
    def alpha088(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #88
---------
    min(rank(decay_linear(((rank(open) + rank(low)) - (rank(high) + rank(close))),8.06882)), Ts_Rank(decay_linear(correlation(Ts_Rank(close, 8.44728), Ts_Rank(adv60,20.6966), 8.01266), 6.65053), 2.61957))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha089"])
    def alpha089(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #89
---------
    (Ts_Rank(decay_linear(correlation(((low * 0.967285) + (low * (1 - 0.967285))), adv10,6.94279), 5.51607), 3.79744) - Ts_Rank(decay_linear(delta(IndNeutralize(vwap,IndClass.industry), 3.48158), 10.1466), 15.3012))

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha090"])
    def alpha090(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #90
---------
    ((rank((close - ts_max(close, 4.66719)))^Ts_Rank(correlation(IndNeutralize(adv40,IndClass.subindustry), low, 5.38375), 3.21856)) * -1)

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha091"])
    def alpha091(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #91
---------
    ((Ts_Rank(decay_linear(decay_linear(correlation(IndNeutralize(close,IndClass.industry), volume, 9.74928), 16.398), 3.83219), 4.8667) -rank(decay_linear(correlation(vwap, adv30, 4.01303), 2.6809))) * -1)

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha092"])
    def alpha092(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #92
---------
    min(Ts_Rank(decay_linear(((((high + low) / 2) + close) < (low + open)), 14.7221),18.8683), Ts_Rank(decay_linear(correlation(rank(low), rank(adv30), 7.58555), 6.94024),6.80584))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha093"])
    def alpha093(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #93
---------
    (Ts_Rank(decay_linear(correlation(IndNeutralize(vwap, IndClass.industry), adv81,17.4193), 19.848), 7.54455) / rank(decay_linear(delta(((close * 0.524434) + (vwap * (1 -0.524434))), 2.77377), 16.2664)))

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha094"])
    def alpha094(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #94
---------
    ((rank((vwap - ts_min(vwap, 11.5783)))^Ts_Rank(correlation(Ts_Rank(vwap,19.6462), Ts_Rank(adv60, 4.02992), 18.0926), 2.70756)) * -1)

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha095"])
    def alpha095(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #95
---------
    (rank((open - ts_min(open, 12.4105))) < Ts_Rank((rank(correlation(sum(((high + low)/ 2), 19.1351), sum(adv40, 19.1351), 12.8742))^5), 11.7584))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha096"])
    def alpha096(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #96
---------
    (max(Ts_Rank(decay_linear(correlation(rank(vwap), rank(volume), 3.83878),4.16783), 8.38151), Ts_Rank(decay_linear(Ts_ArgMax(correlation(Ts_Rank(close, 7.45404),Ts_Rank(adv60, 4.13242), 3.65459), 12.6556), 14.0365), 13.4143)) * -1)

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha097"])
    def alpha097(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #97
---------
    ((rank(decay_linear(delta(IndNeutralize(((low * 0.721001) + (vwap * (1 - 0.721001))),IndClass.industry), 3.3705), 20.4523)) - Ts_Rank(decay_linear(Ts_Rank(correlation(Ts_Rank(low,7.87871), Ts_Rank(adv60, 17.255), 4.97547), 18.5925), 15.7152), 6.71659)) * -1)

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha098"])
    def alpha098(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #98
---------
    (rank(decay_linear(correlation(vwap, sum(adv5, 26.4719), 4.58418), 7.18088)) -rank(decay_linear(Ts_Rank(Ts_ArgMin(correlation(rank(open), rank(adv15), 20.8187), 8.62571),6.95668), 8.07206)))

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha099"])
    def alpha099(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #99
---------
    ((rank(correlation(sum(((high + low) / 2), 19.8975), sum(adv60, 19.8975), 8.8136)) <rank(correlation(low, volume, 6.28259))) * -1)

数据来源:
---------
>>> IndFrame 自身（**横截面**：`RANK` / `INDNEUTRALIZE` 需要多标的（IndFrame 里要有 `securityid` / `tradetime` / `indclass`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha100"])
    def alpha100(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #100
---------
    (0 - (1 * (((1.5 * scale(indneutralize(indneutralize(rank(((((close - low) - (high -close)) / (high - low)) * volume)), IndClass.subindustry), IndClass.subindustry))) -scale(indneutralize((correlation(close, rank(adv20), 5) - rank(ts_argmin(close, 30))),IndClass.subindustry))) * (volume / adv20))))

数据来源:
---------
>>> IndFrame 自身（**缺外部数据**：要用基准指数 / 市值风格列（`MKT` / `SMB` / `HML` / `BANCHMARKINDEX*`））

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    @tobtind(lib="alpha101", overlap=False, lines=["alpha101"])
    def alpha101(self, **kwargs) -> IndSeries:
        """WQ Alpha101 #101
---------
    ((close - open) / ((high - low) + .001))

数据来源:
---------
>>> IndFrame 自身（**纯时序**：只用本标的价量 → 单根 K 线（IndFrame）就能算 ✓）

说明:
---------
    - 副图指标（`overlap=False`）：因子值无量纲，正负代表多空倾向；
    - 原始出处：`py-alpha-lib` 官方示例（BSD-2-Clause）✓
    - 计算走 `alpha` 的 `ExecContext`（可选依赖：`pip install py-alpha-lib`）；
    - 数据不符合因子要求时由 alpha 直接抛原生错误（不做封装）。"""
        ...

    #: **非纯时序**因子（横截面 / 缺外部数据）→ desk 选择器不显示，
    #: 但方法照样存在，传对数据就能算 ✓
    NON_KLINE_INDICATORS = ["alpha001", "alpha002", "alpha003", "alpha004", "alpha005",
                            "alpha008", "alpha010", "alpha011", "alpha013", "alpha014",
                            "alpha015", "alpha016", "alpha017", "alpha018", "alpha019",
                            "alpha020", "alpha022", "alpha025", "alpha027", "alpha028",
                            "alpha029", "alpha030", "alpha031", "alpha032", "alpha033",
                            "alpha034", "alpha036", "alpha037", "alpha038", "alpha039",
                            "alpha040", "alpha042", "alpha044", "alpha045", "alpha047",
                            "alpha048", "alpha050", "alpha052", "alpha055", "alpha056",
                            "alpha057", "alpha058", "alpha059", "alpha060", "alpha061",
                            "alpha062", "alpha063", "alpha064", "alpha065", "alpha066",
                            "alpha067", "alpha068", "alpha069", "alpha070", "alpha071",
                            "alpha072", "alpha073", "alpha074", "alpha075", "alpha076",
                            "alpha077", "alpha078", "alpha079", "alpha080", "alpha081",
                            "alpha082", "alpha083", "alpha085", "alpha086", "alpha087",
                            "alpha088", "alpha089", "alpha090", "alpha091", "alpha092",
                            "alpha093", "alpha094", "alpha095", "alpha096", "alpha097",
                            "alpha098", "alpha099", "alpha100"]
    #: 纯时序因子编号（desk 里能显示的 18 个）
    PURE_INDICATORS = [6, 7, 9, 12, 21, 23, 24, 26, 35, 41, 43, 46, 49, 51, 53, 54, 84, 101]
