"""**GTJA Alpha191** 因子（从 `py-alpha-lib` 官方示例内置 ✓）

`GTJA Alpha191` 共 **191 个因子**，前缀 `alpha191_`，
入口 `self.kline.alpha191.alpha001()` …

### 单标的 vs 横截面

* **120 个纯时序因子**：只用本标的价量 → 任何 IndFrame 都能算，
  desk 选择器里能看到（副图）；
* 其余 **71 个**是横截面 / 缺外部数据因子：
  要自己准备正确的 IndFrame（`securityid` / `tradetime` /
  `indclass` / 基准指数 …），否则 alpha 会抛原生错误；
  这些已进 `NON_KLINE_INDICATORS`，**不在 desk 选择器里显示** ✓

### 用法

```python
factor = self.data.alpha191.alpha001()   # 副图一条线
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


class Alpha191:
    """## GTJA Alpha191 因子

    - 全部 191 个因子（前缀 `alpha191_`），全部**副图**；
    - 纯时序 120 个可直接用（desk 可见）：
      `self.data.alpha191.alpha001()`；
    - 横截面 / 缺数据因子要自备正确的 IndFrame 列，错误由 alpha 原生抛出；
    - 依赖可选包 py-alpha-lib（BSD-2-Clause 示例原样 vendor）。
    """
    _perfixes: str = "alpha191_"
    _df: IndFrame | IndSeries

    def __init__(self, data):
        self._df = data
    @tobtind(lib="alpha191", overlap=False, lines=["alpha001"])
    def alpha001(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #1
---------
    (-1 * CORR(RANK(DELTA(LOG(VOLUME), 1)), RANK(((CLOSE - OPEN) / OPEN)), 6))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha002"])
    def alpha002(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #2
---------
    (-1 * DELTA((((CLOSE - LOW) - (HIGH - CLOSE)) / (HIGH - LOW)), 1))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha003"])
    def alpha003(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #3
---------
    SUM((CLOSE==DELAY(CLOSE,1)?0:CLOSE-(CLOSE>DELAY(CLOSE,1)?MIN(LOW,DELAY(CLOSE,1)):MAX(HIGH,DELAY(CLOSE,1)))),6)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha004"])
    def alpha004(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #4
---------
    ((((SUM(CLOSE, 8) / 8) + STD(CLOSE, 8)) < (SUM(CLOSE, 2) / 2)) ? (-1 * 1) : (((SUM(CLOSE, 2) / 2) < ((SUM(CLOSE, 8) / 8) - STD(CLOSE, 8))) ? 1 : (((1 < (VOLUME / MEAN(VOLUME,20))) || ((VOLUME / MEAN(VOLUME,20)) == 1)) ? 1 : (-1 * 1))))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha005"])
    def alpha005(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #5
---------
    (-1 * TSMAX(CORR(TSRANK(VOLUME, 5), TSRANK(HIGH, 5), 5), 3))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha006"])
    def alpha006(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #6
---------
    (RANK(SIGN(DELTA((((OPEN * 0.85) + (HIGH * 0.15))), 4)))* -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha007"])
    def alpha007(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #7
---------
    ((RANK(MAX((VWAP - CLOSE), 3)) + RANK(MIN((VWAP - CLOSE), 3))) * RANK(DELTA(VOLUME, 3)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha008"])
    def alpha008(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #8
---------
    RANK(DELTA(((((HIGH + LOW) / 2) * 0.2) + (VWAP * 0.8)), 4) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha009"])
    def alpha009(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #9
---------
    SMA(((HIGH+LOW)/2-(DELAY(HIGH,1)+DELAY(LOW,1))/2)*(HIGH-LOW)/VOLUME,7,2)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha010"])
    def alpha010(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #10
---------
    RANK(TSMAX(((RET < 0) ? STD(RET, 20) : CLOSE)^2, 5))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha011"])
    def alpha011(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #11
---------
    SUM(((CLOSE-LOW)-(HIGH-CLOSE))/(HIGH-LOW)*VOLUME,6)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha012"])
    def alpha012(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #12
---------
    (RANK((OPEN - (SUM(VWAP, 10) / 10)))) * (-1 * (RANK(ABS((CLOSE - VWAP)))))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha013"])
    def alpha013(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #13
---------
    (((HIGH * LOW)^0.5) - VWAP)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha014"])
    def alpha014(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #14
---------
    CLOSE-DELAY(CLOSE,5)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha015"])
    def alpha015(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #15
---------
    OPEN/DELAY(CLOSE,1)-1

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha016"])
    def alpha016(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #16
---------
    (-1 * TSMAX(RANK(CORR(RANK(VOLUME), RANK(VWAP), 5)), 5))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha017"])
    def alpha017(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #17
---------
    RANK((VWAP - MAX(VWAP, 15)))^DELTA(CLOSE, 5)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha018"])
    def alpha018(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #18
---------
    CLOSE/DELAY(CLOSE,5)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha019"])
    def alpha019(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #19
---------
    (CLOSE<DELAY(CLOSE,5)?(CLOSE-DELAY(CLOSE,5))/DELAY(CLOSE,5):(CLOSE==DELAY(CLOSE,5)?0:(CLOSE-DELAY(CLOSE,5))/CLOSE))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha020"])
    def alpha020(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #20
---------
    (CLOSE-DELAY(CLOSE,6))/DELAY(CLOSE,6)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha021"])
    def alpha021(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #21
---------
    REGBETA(MEAN(CLOSE,6),SEQUENCE,6)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha022"])
    def alpha022(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #22
---------
    SMA(((CLOSE-MEAN(CLOSE,6))/MEAN(CLOSE,6)-DELAY((CLOSE-MEAN(CLOSE,6))/MEAN(CLOSE,6),3)),12,1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha023"])
    def alpha023(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #23
---------
    SMA((CLOSE>DELAY(CLOSE,1)?STD(CLOSE,20):0),20,1)/(SMA((CLOSE>DELAY(CLOSE,1)?STD(CLOSE,20):0),20,1 )+SMA((CLOSE<=DELAY(CLOSE,1)?STD(CLOSE,20):0),20,1))*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha024"])
    def alpha024(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #24
---------
    SMA(CLOSE-DELAY(CLOSE,5),5,1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha025"])
    def alpha025(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #25
---------
    ((-1 * RANK((DELTA(CLOSE, 7) * (1 - RANK(DECAYLINEAR((VOLUME / MEAN(VOLUME,20)), 9)))))) * (1 + RANK(SUM(RET, 250))))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha026"])
    def alpha026(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #26
---------
    ((((SUM(CLOSE, 7) / 7) - CLOSE)) + ((CORR(VWAP, DELAY(CLOSE, 5), 230))))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha027"])
    def alpha027(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #27
---------
    WMA((CLOSE-DELAY(CLOSE,3))/DELAY(CLOSE,3)*100+(CLOSE-DELAY(CLOSE,6))/DELAY(CLOSE,6)*100,12)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha028"])
    def alpha028(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #28
---------
    3*SMA((CLOSE-TSMIN(LOW,9))/(TSMAX(HIGH,9)-TSMIN(LOW,9))*100,3,1)-2*SMA(SMA((CLOSE-TSMIN(LOW,9))/(MAX(HIGH,9)-TSMAX(LOW,9))*100,3,1),3,1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha029"])
    def alpha029(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #29
---------
    (CLOSE-DELAY(CLOSE,6))/DELAY(CLOSE,6)*VOLUME

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha030"])
    def alpha030(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #30
---------
    WMA((REGRESI(CLOSE/DELAY(CLOSE)-1,MKT,SMB,HML,60))^2,20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha031"])
    def alpha031(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #31
---------
    (CLOSE-MEAN(CLOSE,12))/MEAN(CLOSE,12)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha032"])
    def alpha032(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #32
---------
    (-1 * SUM(RANK(CORR(RANK(HIGH), RANK(VOLUME), 3)), 3))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha033"])
    def alpha033(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #33
---------
    ((((-1 * TSMIN(LOW, 5)) + DELAY(TSMIN(LOW, 5), 5)) * RANK(((SUM(RET, 240) - SUM(RET, 20)) / 220))) * TSRANK(VOLUME, 5))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha034"])
    def alpha034(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #34
---------
    MEAN(CLOSE,12)/CLOSE

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha035"])
    def alpha035(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #35
---------
    (MIN(RANK(DECAYLINEAR(DELTA(OPEN, 1), 15)), RANK(DECAYLINEAR(CORR((VOLUME), ((OPEN * 0.65) + (OPEN *0.35)), 17),7))) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha036"])
    def alpha036(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #36
---------
    RANK(SUM(CORR(RANK(VOLUME), RANK(VWAP), 6), 2))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha037"])
    def alpha037(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #37
---------
    (-1 * RANK(((SUM(OPEN, 5) * SUM(RET, 5)) - DELAY((SUM(OPEN, 5) * SUM(RET, 5)), 10))))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha038"])
    def alpha038(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #38
---------
    (((SUM(HIGH, 20) / 20) < HIGH) ? (-1 * DELTA(HIGH, 2)) : 0)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha039"])
    def alpha039(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #39
---------
    ((RANK(DECAYLINEAR(DELTA((CLOSE), 2),8)) - RANK(DECAYLINEAR(CORR(((VWAP * 0.3) + (OPEN * 0.7)), SUM(MEAN(VOLUME,180), 37), 14), 12))) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha040"])
    def alpha040(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #40
---------
    SUM((CLOSE>DELAY(CLOSE,1)?VOLUME:0),26)/SUM((CLOSE<=DELAY(CLOSE,1)?VOLUME:0),26)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha041"])
    def alpha041(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #41
---------
    (RANK(MAX(DELTA((VWAP), 3), 5))* -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha042"])
    def alpha042(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #42
---------
    ((-1 * RANK(STD(HIGH, 10))) * CORR(HIGH, VOLUME, 10))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha043"])
    def alpha043(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #43
---------
    SUM((CLOSE>DELAY(CLOSE,1)?VOLUME:(CLOSE<DELAY(CLOSE,1)?-VOLUME:0)),6)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha044"])
    def alpha044(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #44
---------
    (TSRANK(DECAYLINEAR(CORR(((LOW )), MEAN(VOLUME,10), 7), 6),4) + TSRANK(DECAYLINEAR(DELTA((VWAP), 3), 10), 15))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha045"])
    def alpha045(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #45
---------
    (RANK(DELTA((((CLOSE * 0.6) + (OPEN *0.4))), 1)) * RANK(CORR(VWAP, MEAN(VOLUME,150), 15)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha046"])
    def alpha046(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #46
---------
    (MEAN(CLOSE,3)+MEAN(CLOSE,6)+MEAN(CLOSE,12)+MEAN(CLOSE,24))/(4*CLOSE)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha047"])
    def alpha047(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #47
---------
    SMA((TSMAX(HIGH,6)-CLOSE)/(TSMAX(HIGH,6)-TSMIN(LOW,6))*100,9,1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha048"])
    def alpha048(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #48
---------
    (-1*((RANK(((SIGN((CLOSE - DELAY(CLOSE, 1))) + SIGN((DELAY(CLOSE, 1) - DELAY(CLOSE, 2)))) + SIGN((DELAY(CLOSE, 2) - DELAY(CLOSE, 3)))))) * SUM(VOLUME, 5)) / SUM(VOLUME, 20))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha049"])
    def alpha049(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #49
---------
    SUM(((HIGH+LOW)>=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)/(SUM(((HIGH+LOW)>=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)+SUM(((HIGH+LOW)<=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha050"])
    def alpha050(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #50
---------
    SUM(((HIGH+LOW)<=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)/(SUM(((HIGH+LOW)<=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)+SUM(((HIGH+LOW)>=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12))-SUM(((HIGH+LOW)>=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)/(SUM(((HIGH+LOW)>=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)+SUM(((HIGH+LOW)<=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha051"])
    def alpha051(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #51
---------
    SUM(((HIGH+LOW)<=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)/(SUM(((HIGH+LOW)<=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)+SUM(((HIGH+LOW)>=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha052"])
    def alpha052(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #52
---------
    SUM(MAX(0,HIGH-DELAY((HIGH+LOW+CLOSE)/3,1)),26)/SUM(MAX(0,DELAY((HIGH+LOW+CLOSE)/3,1)-LOW),26)* 100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha053"])
    def alpha053(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #53
---------
    COUNT(CLOSE>DELAY(CLOSE,1),12)/12*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha054"])
    def alpha054(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #54
---------
    (-1 * RANK((STD(ABS(CLOSE - OPEN), 10) + (CLOSE - OPEN)) + CORR(CLOSE, OPEN, 10)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha055"])
    def alpha055(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #55
---------
    SUM(16*(CLOSE-DELAY(CLOSE,1)+(CLOSE-OPEN)/2+DELAY(CLOSE,1)-DELAY(OPEN,1))/((ABS(HIGH-DELAY(CLOSE,1))>ABS(LOW-DELAY(CLOSE,1)) && ABS(HIGH-DELAY(CLOSE,1))>ABS(HIGH-DELAY(LOW,1))?ABS(HIGH-DELAY(CLOSE,1))+ABS(LOW-DELAY(CLOSE,1))/2+ABS(DELAY(CLOSE,1)-DELAY(OPEN,1))/4:(ABS(LOW-DELAY(CLOSE,1))>ABS(HIGH-DELAY(LOW,1)) && ABS(LOW-DELAY(CLOSE,1))>ABS(HIGH-DELAY(CLOSE,1))?ABS(LOW-DELAY(CLOSE,1))+ABS(HIGH-DELAY(CLOSE,1))/2+ABS(DELAY(CLOSE,1)-DELAY(OPEN,1))/4:ABS(HIGH-DELAY(LOW,1))+ABS(DELAY(CLOSE,1)-DELAY(OPEN,1))/4)))*MAX(ABS(HIGH-DELAY(CLOSE,1)),ABS(LOW-DELAY(CLOSE,1))),20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha056"])
    def alpha056(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #56
---------
    (RANK((OPEN - TSMIN(OPEN, 12))) < RANK((RANK(CORR(SUM(((HIGH + LOW) / 2), 19), SUM(MEAN(VOLUME,40), 19), 13))^5)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha057"])
    def alpha057(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #57
---------
    SMA((CLOSE-TSMIN(LOW,9))/(TSMAX(HIGH,9)-TSMIN(LOW,9))*100,3,1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha058"])
    def alpha058(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #58
---------
    COUNT(CLOSE>DELAY(CLOSE,1),20)/20*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha059"])
    def alpha059(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #59
---------
    SUM((CLOSE==DELAY(CLOSE,1)?0:CLOSE-(CLOSE>DELAY(CLOSE,1)?MIN(LOW,DELAY(CLOSE,1)):MAX(HIGH,DELAY(CLOSE,1)))),20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha060"])
    def alpha060(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #60
---------
    SUM(((CLOSE-LOW)-(HIGH-CLOSE))/(HIGH-LOW)*VOLUME,20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha061"])
    def alpha061(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #61
---------
    (MAX(RANK(DECAYLINEAR(DELTA(VWAP, 1), 12)), RANK(DECAYLINEAR(RANK(CORR((LOW),MEAN(VOLUME,80), 8)), 17))) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha062"])
    def alpha062(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #62
---------
    (-1 * CORR(HIGH, RANK(VOLUME), 5))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha063"])
    def alpha063(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #63
---------
    SMA(MAX(CLOSE-DELAY(CLOSE,1),0),6,1)/SMA(ABS(CLOSE-DELAY(CLOSE,1)),6,1)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha064"])
    def alpha064(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #64
---------
    (MAX(RANK(DECAYLINEAR(CORR(RANK(VWAP), RANK(VOLUME), 4), 4)), RANK(DECAYLINEAR(MAX(CORR(RANK(CLOSE), RANK(MEAN(VOLUME,60)), 4), 13), 14))) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha065"])
    def alpha065(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #65
---------
    MEAN(CLOSE,6)/CLOSE

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha066"])
    def alpha066(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #66
---------
    (CLOSE-MEAN(CLOSE,6))/MEAN(CLOSE,6)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha067"])
    def alpha067(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #67
---------
    SMA(MAX(CLOSE-DELAY(CLOSE,1),0),24,1)/SMA(ABS(CLOSE-DELAY(CLOSE,1)),24,1)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha068"])
    def alpha068(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #68
---------
    SMA(((HIGH+LOW)/2-(DELAY(HIGH,1)+DELAY(LOW,1))/2)*(HIGH-LOW)/VOLUME,15,2)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha069"])
    def alpha069(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #69
---------
    (SUM(DTM,20)>SUM(DBM,20) ? (SUM(DTM,20)-SUM(DBM,20))/SUM(DTM,20) : (SUM(DTM,20)==SUM(DBM,20) ? 0:(SUM(DTM,20)-SUM(DBM,20))/SUM(DBM,20)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha070"])
    def alpha070(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #70
---------
    STD(AMOUNT,6)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha071"])
    def alpha071(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #71
---------
    (CLOSE-MEAN(CLOSE,24))/MEAN(CLOSE,24)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha072"])
    def alpha072(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #72
---------
    SMA((TSMAX(HIGH,6)-CLOSE)/(TSMAX(HIGH,6)-TSMIN(LOW,6))*100,15,1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha073"])
    def alpha073(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #73
---------
    ((TSRANK(DECAYLINEAR(DECAYLINEAR(CORR((CLOSE), VOLUME, 10), 16), 4), 5) - RANK(DECAYLINEAR(CORR(VWAP, MEAN(VOLUME,30), 4),3))) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha074"])
    def alpha074(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #74
---------
    (RANK(CORR(SUM(((LOW * 0.35) + (VWAP * 0.65)), 20), SUM(MEAN(VOLUME,40), 20), 7)) + RANK(CORR(RANK(VWAP), RANK(VOLUME), 6)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha075"])
    def alpha075(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #75
---------
    COUNT(CLOSE>OPEN && BANCHMARKINDEXCLOSE<BANCHMARKINDEXOPEN,50)/COUNT(BANCHMARKINDEXCLOSE<BANCHMARKINDEXOPEN,50)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha076"])
    def alpha076(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #76
---------
    STD(ABS((CLOSE/DELAY(CLOSE,1)-1))/VOLUME,20)/MEAN(ABS((CLOSE/DELAY(CLOSE,1)-1))/VOLUME,20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha077"])
    def alpha077(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #77
---------
    MIN(RANK(DECAYLINEAR(((((HIGH + LOW) / 2) + HIGH) - (VWAP + HIGH)), 20)), RANK(DECAYLINEAR(CORR(((HIGH + LOW) / 2), MEAN(VOLUME,40), 3), 6)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha078"])
    def alpha078(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #78
---------
    ((HIGH+LOW+CLOSE)/3-MA((HIGH+LOW+CLOSE)/3,12))/(0.015*MEAN(ABS(CLOSE-MEAN((HIGH+LOW+CLOSE)/3,12)),12))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha079"])
    def alpha079(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #79
---------
    SMA(MAX(CLOSE-DELAY(CLOSE,1),0),12,1)/SMA(ABS(CLOSE-DELAY(CLOSE,1)),12,1)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha080"])
    def alpha080(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #80
---------
    (VOLUME-DELAY(VOLUME,5))/DELAY(VOLUME,5)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha081"])
    def alpha081(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #81
---------
    SMA(VOLUME,21,2)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha082"])
    def alpha082(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #82
---------
    SMA((TSMAX(HIGH,6)-CLOSE)/(TSMAX(HIGH,6)-TSMIN(LOW,6))*100,20,1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha083"])
    def alpha083(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #83
---------
    (-1 * RANK(COV(RANK(HIGH), RANK(VOLUME), 5)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha084"])
    def alpha084(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #84
---------
    SUM((CLOSE>DELAY(CLOSE,1)?VOLUME:(CLOSE<DELAY(CLOSE,1)?-VOLUME:0)),20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha085"])
    def alpha085(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #85
---------
    (TSRANK((VOLUME / MEAN(VOLUME,20)), 20) * TSRANK((-1 * DELTA(CLOSE, 7)), 8))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha086"])
    def alpha086(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #86
---------
    ((0.25 < (((DELAY(CLOSE, 20) - DELAY(CLOSE, 10)) / 10) - ((DELAY(CLOSE, 10) - CLOSE) / 10))) ? (-1 * 1) : (((((DELAY(CLOSE, 20) - DELAY(CLOSE, 10)) / 10) - ((DELAY(CLOSE, 10) - CLOSE) / 10)) < 0) ? 1 : ((-1 * 1) * (CLOSE - DELAY(CLOSE, 1)))))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha087"])
    def alpha087(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #87
---------
    ((RANK(DECAYLINEAR(DELTA(VWAP, 4), 7)) + TSRANK(DECAYLINEAR(((((LOW * 0.9) + (LOW * 0.1)) - VWAP) / (OPEN - ((HIGH + LOW) / 2))), 11), 7)) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha088"])
    def alpha088(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #88
---------
    (CLOSE-DELAY(CLOSE,20))/DELAY(CLOSE,20)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha089"])
    def alpha089(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #89
---------
    2*(SMA(CLOSE,13,2)-SMA(CLOSE,27,2)-SMA(SMA(CLOSE,13,2)-SMA(CLOSE,27,2),10,2))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha090"])
    def alpha090(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #90
---------
    (RANK(CORR(RANK(VWAP), RANK(VOLUME), 5)) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha091"])
    def alpha091(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #91
---------
    ((RANK((CLOSE - MAX(CLOSE, 5)))*RANK(CORR((MEAN(VOLUME,40)), LOW, 5))) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha092"])
    def alpha092(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #92
---------
    (MAX(RANK(DECAYLINEAR(DELTA(((CLOSE * 0.35) + (VWAP *0.65)), 2), 3)), TSRANK(DECAYLINEAR(ABS(CORR((MEAN(VOLUME,180)), CLOSE, 13)), 5), 15)) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha093"])
    def alpha093(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #93
---------
    SUM((OPEN>=DELAY(OPEN,1)?0:MAX((OPEN-LOW),(OPEN-DELAY(OPEN,1)))),20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha094"])
    def alpha094(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #94
---------
    SUM((CLOSE>DELAY(CLOSE,1)?VOLUME:(CLOSE<DELAY(CLOSE,1)?-VOLUME:0)),30)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha095"])
    def alpha095(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #95
---------
    STD(AMOUNT,20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha096"])
    def alpha096(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #96
---------
    SMA(SMA((CLOSE-TSMIN(LOW,9))/(TSMAX(HIGH,9)-TSMIN(LOW,9))*100,3,1),3,1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha097"])
    def alpha097(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #97
---------
    STD(VOLUME,10)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha098"])
    def alpha098(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #98
---------
    ((((DELTA((SUM(CLOSE, 100) / 100), 100) / DELAY(CLOSE, 100)) < 0.05) || ((DELTA((SUM(CLOSE, 100) / 100), 100) / DELAY(CLOSE, 100)) == 0.05)) ? (-1 * (CLOSE - TSMIN(CLOSE, 100))) : (-1 * DELTA(CLOSE, 3)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha099"])
    def alpha099(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #99
---------
    (-1 * RANK(COV(RANK(CLOSE), RANK(VOLUME), 5)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha100"])
    def alpha100(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #100
---------
    STD(VOLUME,20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha101"])
    def alpha101(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #101
---------
    ((RANK(CORR(CLOSE, SUM(MEAN(VOLUME,30), 37), 15)) < RANK(CORR(RANK(((HIGH * 0.1) + (VWAP * 0.9))), RANK(VOLUME), 11))) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha102"])
    def alpha102(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #102
---------
    SMA(MAX(VOLUME-DELAY(VOLUME,1),0),6,1)/SMA(ABS(VOLUME-DELAY(VOLUME,1)),6,1)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha103"])
    def alpha103(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #103
---------
    ((20-LOWDAY(LOW,20))/20)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha104"])
    def alpha104(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #104
---------
    (-1 * (DELTA(CORR(HIGH, VOLUME, 5), 5) * RANK(STD(CLOSE, 20))))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha105"])
    def alpha105(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #105
---------
    (-1 * CORR(RANK(OPEN), RANK(VOLUME), 10))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha106"])
    def alpha106(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #106
---------
    CLOSE-DELAY(CLOSE,20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha107"])
    def alpha107(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #107
---------
    (((-1 * RANK((OPEN - DELAY(HIGH, 1)))) * RANK((OPEN - DELAY(CLOSE, 1)))) * RANK((OPEN - DELAY(LOW, 1))))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha108"])
    def alpha108(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #108
---------
    ((RANK((HIGH - MIN(HIGH, 2)))^RANK(CORR((VWAP), (MEAN(VOLUME,120)), 6))) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha109"])
    def alpha109(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #109
---------
    SMA(HIGH-LOW,10,2)/SMA(SMA(HIGH-LOW,10,2),10,2)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha110"])
    def alpha110(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #110
---------
    SUM(MAX(0,HIGH-DELAY(CLOSE,1)),20)/SUM(MAX(0,DELAY(CLOSE,1)-LOW),20)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha111"])
    def alpha111(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #111
---------
    SMA(VOLUME*((CLOSE-LOW)-(HIGH-CLOSE))/(HIGH-LOW),11,2)-SMA(VOLUME*((CLOSE-LOW)-(HIGH-CLOSE))/(HIGH-LOW),4,2)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha112"])
    def alpha112(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #112
---------
    (SUM((CLOSE-DELAY(CLOSE,1)>0?CLOSE-DELAY(CLOSE,1):0),12)-SUM((CLOSE-DELAY(CLOSE,1)<0?ABS(CLOSE-DELAY(CLOSE,1)):0),12))/(SUM((CLOSE-DELAY(CLOSE,1)>0?CLOSE-DELAY(CLOSE,1):0),12)+SUM((CLOSE-DELAY(CLOSE,1)<0?ABS(CLOSE-DELAY(CLOSE,1)):0),12))*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha113"])
    def alpha113(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #113
---------
    (-1 * ((RANK((SUM(DELAY(CLOSE, 5), 20) / 20)) * CORR(CLOSE, VOLUME, 2)) * RANK(CORR(SUM(CLOSE, 5), SUM(CLOSE, 20), 2))))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha114"])
    def alpha114(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #114
---------
    ((RANK(DELAY(((HIGH - LOW) / (SUM(CLOSE, 5) / 5)), 2)) * RANK(RANK(VOLUME))) / (((HIGH - LOW) / (SUM(CLOSE, 5) / 5)) / (VWAP - CLOSE)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha115"])
    def alpha115(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #115
---------
    (RANK(CORR(((HIGH * 0.9) + (CLOSE * 0.1)), MEAN(VOLUME,30), 10))^RANK(CORR(TSRANK(((HIGH + LOW) / 2), 4), TSRANK(VOLUME, 10), 7)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha116"])
    def alpha116(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #116
---------
    REGBETA(CLOSE,SEQUENCE,20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha117"])
    def alpha117(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #117
---------
    ((TSRANK(VOLUME, 32) * (1 - TSRANK(((CLOSE + HIGH) - LOW), 16))) * (1 - TSRANK(RET, 32)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha118"])
    def alpha118(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #118
---------
    SUM(HIGH-OPEN,20)/SUM(OPEN-LOW,20)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha119"])
    def alpha119(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #119
---------
    (RANK(DECAYLINEAR(CORR(VWAP, SUM(MEAN(VOLUME,5), 26), 5), 7)) - RANK(DECAYLINEAR(TSRANK(MIN(CORR(RANK(OPEN), RANK(MEAN(VOLUME,15)), 21), 9), 7), 8)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha120"])
    def alpha120(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #120
---------
    (RANK((VWAP - CLOSE)) / RANK((VWAP + CLOSE)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha121"])
    def alpha121(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #121
---------
    ((RANK((VWAP - MIN(VWAP, 12)))^TSRANK(CORR(TSRANK(VWAP, 20), TSRANK(MEAN(VOLUME,60), 2), 18), 3)) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha122"])
    def alpha122(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #122
---------
    (SMA(SMA(SMA(LOG(CLOSE),13,2),13,2),13,2)-DELAY(SMA(SMA(SMA(LOG(CLOSE),13,2),13,2),13,2),1))/DELAY(SMA(SMA(SMA(LOG(CLOSE),13,2),13,2),13,2),1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha123"])
    def alpha123(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #123
---------
    ((RANK(CORR(SUM(((HIGH + LOW) / 2), 20), SUM(MEAN(VOLUME,60), 20), 9)) < RANK(CORR(LOW, VOLUME, 6))) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha124"])
    def alpha124(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #124
---------
    (CLOSE - VWAP) / DECAYLINEAR(RANK(TSMAX(CLOSE, 30)),2)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha125"])
    def alpha125(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #125
---------
    (RANK(DECAYLINEAR(CORR((VWAP), MEAN(VOLUME,80),17), 20)) / RANK(DECAYLINEAR(DELTA(((CLOSE * 0.5) + (VWAP * 0.5)), 3), 16)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha126"])
    def alpha126(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #126
---------
    (CLOSE+HIGH+LOW)/3

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha127"])
    def alpha127(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #127
---------
    (MEAN((100*(CLOSE-TSMAX(CLOSE,12))/(TSMAX(CLOSE,12)))^2, 12))^(1/2)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha128"])
    def alpha128(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #128
---------
    100-(100/(1+SUM(((HIGH+LOW+CLOSE)/3>DELAY((HIGH+LOW+CLOSE)/3,1)?(HIGH+LOW+CLOSE)/3*VOLUME:0),14)/SUM(((HIGH+LOW+CLOSE)/3<DELAY((HIGH+LOW+CLOSE)/3,1)?(HIGH+LOW+CLOSE)/3*VOLUME:0), 14)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha129"])
    def alpha129(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #129
---------
    SUM((CLOSE-DELAY(CLOSE,1)<0?ABS(CLOSE-DELAY(CLOSE,1)):0),12)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha130"])
    def alpha130(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #130
---------
    (RANK(DECAYLINEAR(CORR(((HIGH + LOW) / 2), MEAN(VOLUME,40), 9), 10)) / RANK(DECAYLINEAR(CORR(RANK(VWAP), RANK(VOLUME), 7),3)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha131"])
    def alpha131(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #131
---------
    (RANK(DELTA(VWAP, 1))^TSRANK(CORR(CLOSE,MEAN(VOLUME,50), 18), 18))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha132"])
    def alpha132(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #132
---------
    MEAN(AMOUNT,20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha133"])
    def alpha133(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #133
---------
    ((20-HIGHDAY(HIGH,20))/20)*100-((20-LOWDAY(LOW,20))/20)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha134"])
    def alpha134(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #134
---------
    (CLOSE-DELAY(CLOSE,12))/DELAY(CLOSE,12)*VOLUME

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha135"])
    def alpha135(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #135
---------
    SMA(DELAY(CLOSE/DELAY(CLOSE,20),1),20,1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha136"])
    def alpha136(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #136
---------
    ((-1 * RANK(DELTA(RET, 3))) * CORR(OPEN, VOLUME, 10))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha137"])
    def alpha137(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #137
---------
    16*(CLOSE-DELAY(CLOSE,1)+(CLOSE-OPEN)/2+DELAY(CLOSE,1)-DELAY(OPEN,1))/((ABS(HIGH-DELAY(CLOSE, 1))>ABS(LOW-DELAY(CLOSE,1)) && ABS(HIGH-DELAY(CLOSE,1))>ABS(HIGH-DELAY(LOW,1))?ABS(HIGH-DELAY(CLOSE,1))+ABS(LOW-DELAY(CLOSE,1))/2+ABS(DELAY(CLOSE,1)-DELAY(OPEN,1))/4:(ABS(LOW-DELAY(CLOSE,1))>ABS(HIGH-DELAY(LOW,1)) && ABS(LOW-DELAY(CLOSE,1))>ABS(HIGH-DELAY(CLOSE,1))?ABS(LOW-DELAY(CLOSE,1))+ABS(HIGH-DELAY(CLOSE,1))/2+ABS(DELAY(CLOSE,1)-DELAY(OPEN,1))/4:ABS(HIGH-DELAY(LOW,1))+ABS(DELAY(CLOSE,1)-DELAY(OPEN,1))/4)))*MAX(ABS(HIGH-DELAY(CLOSE,1)),ABS(LOW-DELAY(CLOSE,1)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha138"])
    def alpha138(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #138
---------
    ((RANK(DECAYLINEAR(DELTA((((LOW * 0.7) + (VWAP *0.3))), 3), 20)) - TSRANK(DECAYLINEAR(TSRANK(CORR(TSRANK(LOW, 8), TSRANK(MEAN(VOLUME,60), 17), 5), 19), 16), 7)) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha139"])
    def alpha139(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #139
---------
    (-1 * CORR(OPEN, VOLUME, 10))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha140"])
    def alpha140(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #140
---------
    MIN(RANK(DECAYLINEAR(((RANK(OPEN) + RANK(LOW)) - (RANK(HIGH) + RANK(CLOSE))), 8)), TSRANK(DECAYLINEAR(CORR(TSRANK(CLOSE, 8), TSRANK(MEAN(VOLUME,60), 20), 8), 7), 3))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha141"])
    def alpha141(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #141
---------
    (RANK(CORR(RANK(HIGH), RANK(MEAN(VOLUME,15)), 9))* -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha142"])
    def alpha142(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #142
---------
    (((-1 * RANK(TSRANK(CLOSE, 10))) * RANK(DELTA(DELTA(CLOSE, 1), 1))) * RANK(TSRANK((VOLUME /MEAN(VOLUME,20)), 5)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha143"])
    def alpha143(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #143
---------
    CLOSE>DELAY(CLOSE,1)?(CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1)*SELF:SELF

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha144"])
    def alpha144(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #144
---------
    SUMIF(ABS(CLOSE/DELAY(CLOSE,1)-1)/AMOUNT,20,CLOSE<DELAY(CLOSE,1))/COUNT(CLOSE<DELAY(CLOSE, 1),20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha145"])
    def alpha145(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #145
---------
    (MEAN(VOLUME,9)-MEAN(VOLUME,26))/MEAN(VOLUME,12)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha146"])
    def alpha146(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #146
---------
    MEAN((CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1)-SMA((CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1),61,2),20)*(( CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1)-SMA((CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1),61,2))/SMA(((CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1)-((CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1)-SMA((CLOSE-DELAY(CLOSE, 1))/DELAY(CLOSE,1),61,2)))^2,60)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha147"])
    def alpha147(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #147
---------
    REGBETA(MEAN(CLOSE,12),SEQUENCE,12)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha148"])
    def alpha148(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #148
---------
    ((RANK(CORR((OPEN), SUM(MEAN(VOLUME,60), 9), 6)) < RANK((OPEN - TSMIN(OPEN, 14)))) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha149"])
    def alpha149(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #149
---------
    REGBETA(FILTER(CLOSE/DELAY(CLOSE,1)-1,BANCHMARKINDEXCLOSE<DELAY(BANCHMARKINDEXCLOSE,1) ),FILTER(BANCHMARKINDEXCLOSE/DELAY(BANCHMARKINDEXCLOSE,1)-1,BANCHMARKINDEXCLOSE<DELAY(BANCHMARKINDEXCLOSE,1)),252)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha150"])
    def alpha150(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #150
---------
    (CLOSE+HIGH+LOW)/3*VOLUME

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha151"])
    def alpha151(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #151
---------
    SMA(CLOSE-DELAY(CLOSE,20),20,1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha152"])
    def alpha152(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #152
---------
    SMA(MEAN(DELAY(SMA(DELAY(CLOSE/DELAY(CLOSE,9),1),9,1),1),12)-MEAN(DELAY(SMA(DELAY(CLOSE/DELAY (CLOSE,9),1),9,1),1),26),9,1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha153"])
    def alpha153(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #153
---------
    (MEAN(CLOSE,3)+MEAN(CLOSE,6)+MEAN(CLOSE,12)+MEAN(CLOSE,24))/4

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha154"])
    def alpha154(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #154
---------
    (((VWAP - MIN(VWAP, 16))) < (CORR(VWAP, MEAN(VOLUME,180), 18)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha155"])
    def alpha155(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #155
---------
    SMA(VOLUME,13,2)-SMA(VOLUME,27,2)-SMA(SMA(VOLUME,13,2)-SMA(VOLUME,27,2),10,2)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha156"])
    def alpha156(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #156
---------
    (MAX(RANK(DECAYLINEAR(DELTA(VWAP, 5), 3)), RANK(DECAYLINEAR(((DELTA(((OPEN * 0.15) + (LOW *0.85)), 2) / ((OPEN * 0.15) + (LOW * 0.85))) * -1), 3))) * -1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha157"])
    def alpha157(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #157
---------
    (MIN(PROD(RANK(RANK(LOG(SUM(TSMIN(RANK(RANK((-1 * RANK(DELTA((CLOSE - 1), 5))))), 2), 1)))), 1), 5) + TSRANK(DELAY((-1 * RET), 6), 5))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha158"])
    def alpha158(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #158
---------
    ((HIGH-SMA(CLOSE,15,2))-(LOW-SMA(CLOSE,15,2)))/CLOSE

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha159"])
    def alpha159(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #159
---------
    ((CLOSE-SUM(MIN(LOW,DELAY(CLOSE,1)),6))/SUM(MAX(HIGH,DELAY(CLOSE,1))-MIN(LOW,DELAY(CLOSE,1)),6) *12*24+(CLOSE-SUM(MIN(LOW,DELAY(CLOSE,1)),12))/SUM(MAX(HIGH,DELAY(CLOSE,1))-MIN(LOW,DELAY(CLOSE,1)),12)*6*24+(CLOSE-SUM(MIN(LOW,DELAY(CLOSE,1)),24))/SUM(MAX(HIGH,DELAY(CLOSE,1))-MIN(LOW,DELAY(CLOSE,1)),24)*6*24)*100/(6*12+6*24+12*24)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha160"])
    def alpha160(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #160
---------
    SMA((CLOSE<=DELAY(CLOSE,1)?STD(CLOSE,20):0),20,1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha161"])
    def alpha161(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #161
---------
    MEAN(MAX(MAX((HIGH-LOW),ABS(DELAY(CLOSE,1)-HIGH)),ABS(DELAY(CLOSE,1)-LOW)),12)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha162"])
    def alpha162(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #162
---------
    (SMA(MAX(CLOSE-DELAY(CLOSE,1),0),12,1)/SMA(ABS(CLOSE-DELAY(CLOSE,1)),12,1)*100-MIN(SMA(MAX(CLOSE-DELAY(CLOSE,1),0),12,1)/SMA(ABS(CLOSE-DELAY(CLOSE,1)),12,1)*100,12))/(MAX(SMA(MAX(CLOSE-DELAY(CLOSE,1),0),12,1)/SMA(ABS(CLOSE-DELAY(CLOSE,1)),12,1)*100,12)-MIN(SMA(MAX(CLOSE-DELAY(CLOSE,1),0),12, 1)/SMA(ABS(CLOSE-DELAY(CLOSE,1)),12,1)*100,12))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha163"])
    def alpha163(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #163
---------
    RANK(((((-1 * RET) * MEAN(VOLUME,20)) * VWAP) * (HIGH - CLOSE)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha164"])
    def alpha164(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #164
---------
    SMA((((CLOSE>DELAY(CLOSE,1))?1/(CLOSE-DELAY(CLOSE,1)):1)-MIN(((CLOSE>DELAY(CLOSE,1))?1/(CLOSE-DELAY(CLOSE,1)):1),12))/(HIGH-LOW)*100,13,2)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha165"])
    def alpha165(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #165
---------
    TSMAX(SUM(CLOSE-MEAN(CLOSE,48),48),48)-TSMIN(SUM(CLOSE-MEAN(CLOSE,48),48),48)/STD(CLOSE,48)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha166"])
    def alpha166(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #166
---------
    -20* ( 20-1 ) ^1.5*SUM(CLOSE/DELAY(CLOSE,1)-1-MEAN(CLOSE/DELAY(CLOSE,1)-1,20),20)/((20-1)*(20-2)*(SUM(CLOSE/DELAY(CLOSE,1),20)^2))^1.5

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha167"])
    def alpha167(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #167
---------
    SUM((CLOSE-DELAY(CLOSE,1)>0?CLOSE-DELAY(CLOSE,1):0),12)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha168"])
    def alpha168(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #168
---------
    (-1*VOLUME/MEAN(VOLUME,20))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha169"])
    def alpha169(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #169
---------
    SMA(MEAN(DELAY(SMA(CLOSE-DELAY(CLOSE,1),9,1),1),12)-MEAN(DELAY(SMA(CLOSE-DELAY(CLOSE,1),9,1),1), 26),10,1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha170"])
    def alpha170(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #170
---------
    ((((RANK((1 / CLOSE)) * VOLUME) / MEAN(VOLUME,20)) * ((HIGH * RANK((HIGH - CLOSE))) / (SUM(HIGH, 5) / 5))) - RANK((VWAP - DELAY(VWAP, 5))))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha171"])
    def alpha171(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #171
---------
    ((-1 * ((LOW - CLOSE) * (OPEN^5))) / ((CLOSE - HIGH) * (CLOSE^5)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha172"])
    def alpha172(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #172
---------
    MEAN(ABS(SUM((LD>0 && LD>HD)?LD:0,14)*100/SUM(TR,14)-SUM((HD>0 && HD>LD)?HD:0,14)*100/SUM(TR,14))/(SUM((LD>0 && LD>HD)?LD:0,14)*100/SUM(TR,14)+SUM((HD>0 && HD>LD)?HD:0,14)*100/SUM(TR,14))*100,6)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha173"])
    def alpha173(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #173
---------
    3*SMA(CLOSE,13,2)-2*SMA(SMA(CLOSE,13,2),13,2)+SMA(SMA(SMA(LOG(CLOSE),13,2),13,2),13,2)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha174"])
    def alpha174(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #174
---------
    SMA((CLOSE>DELAY(CLOSE,1)?STD(CLOSE,20):0),20,1)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha175"])
    def alpha175(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #175
---------
    MEAN(MAX(MAX((HIGH-LOW),ABS(DELAY(CLOSE,1)-HIGH)),ABS(DELAY(CLOSE,1)-LOW)),6)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha176"])
    def alpha176(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #176
---------
    CORR(RANK(((CLOSE - TSMIN(LOW, 12)) / (TSMAX(HIGH, 12) - TSMIN(LOW,12)))), RANK(VOLUME), 6)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha177"])
    def alpha177(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #177
---------
    ((20-HIGHDAY(HIGH,20))/20)*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha178"])
    def alpha178(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #178
---------
    (CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1)*VOLUME

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha179"])
    def alpha179(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #179
---------
    (RANK(CORR(VWAP, VOLUME, 4)) *RANK(CORR(RANK(LOW), RANK(MEAN(VOLUME,50)), 12)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha180"])
    def alpha180(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #180
---------
    ((MEAN(VOLUME,20) < VOLUME) ? ((-1 * TSRANK(ABS(DELTA(CLOSE, 7)), 60)) * SIGN(DELTA(CLOSE, 7))) : (-1 * VOLUME))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha181"])
    def alpha181(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #181
---------
    SUM(((CLOSE/DELAY(CLOSE,1)-1)-MEAN((CLOSE/DELAY(CLOSE,1)-1),20))-(BANCHMARKINDEXCLOSE-MEAN(BANCHMARKINDEXCLOSE,20))^2,20)/SUM((BANCHMARKINDEXCLOSE-MEAN(BANCHMARKINDEXCLOSE,20))^3,20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha182"])
    def alpha182(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #182
---------
    COUNT((CLOSE>OPEN && BANCHMARKINDEXCLOSE>BANCHMARKINDEXOPEN) ||(CLOSE<OPEN && BANCHMARKINDEXCLOSE<BANCHMARKINDEXOPEN),20)/20

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha183"])
    def alpha183(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #183
---------
    TSMAX(SUM(CLOSE-MEAN(CLOSE,24),24),24)-TSMIN(SUM(CLOSE-MEAN(CLOSE,24),24),24)/STD(CLOSE,24)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha184"])
    def alpha184(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #184
---------
    (RANK(CORR(DELAY((OPEN - CLOSE), 1), CLOSE, 200)) + RANK((OPEN - CLOSE)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha185"])
    def alpha185(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #185
---------
    RANK((-1 * ((1 - (OPEN / CLOSE))^2)))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha186"])
    def alpha186(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #186
---------
    (MEAN(ABS(SUM((LD>0 && LD>HD)?LD:0,14)*100/SUM(TR,14)-SUM((HD>0 && HD>LD)?HD:0,14)*100/SUM(TR,14))/(SUM((LD>0 && LD>HD)?LD:0,14)*100/SUM(TR,14)+SUM((HD>0 && HD>LD)?HD:0,14)*100/SUM(TR,14))*100,6)+DELAY(MEAN(ABS(SUM((LD>0 && LD>HD)?LD:0,14)*100/SUM(TR,14)-SUM((HD>0 && HD>LD)?HD:0,14)*100/SUM(TR,14))/(SUM((LD>0 && LD>HD)?LD:0,14)*100/SUM(TR,14)+SUM((HD>0 && HD>LD)?HD:0,14)*100/SUM(TR,14))*100,6),6))/2

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha187"])
    def alpha187(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #187
---------
    SUM((OPEN<=DELAY(OPEN,1)?0:MAX((HIGH-OPEN),(OPEN-DELAY(OPEN,1)))),20)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha188"])
    def alpha188(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #188
---------
    ((HIGH - LOW - SMA(HIGH-LOW,11,2))/SMA(HIGH-LOW,11,2))*100

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha189"])
    def alpha189(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #189
---------
    MEAN(ABS(CLOSE-MEAN(CLOSE,6)),6)

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha190"])
    def alpha190(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #190
---------
    LOG((COUNT(CLOSE/DELAY(CLOSE,1)-1>((CLOSE/DELAY(CLOSE,19))^(1/20)-1),20)-1)*(SUMIF(((CLOSE/DELAY(CLOSE,1)-1-(CLOSE/DELAY(CLOSE,19))^(1/20)-1))^2,20,CLOSE/DELAY(CLOSE,1)-1<(CLOSE/DELAY(CLOSE,19))^(1/20)-1))/((COUNT((CLOSE/DELAY(CLOSE,1)-1<(CLOSE/DELAY(CLOSE,19))^(1/20)-1),20))*(SUMIF((CLOSE/DELAY(CLOSE,1)-1-((CLOSE/DELAY(CLOSE,19))^(1/20)-1))^2,20,CLOSE/DELAY(CLOSE,1)-1>(CLOSE/DELAY(CLOSE,19))^(1/20)-1))))

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

    @tobtind(lib="alpha191", overlap=False, lines=["alpha191"])
    def alpha191(self, **kwargs) -> IndSeries:
        """GTJA Alpha191 #191
---------
    ((CORR(MEAN(VOLUME,20), LOW, 5) + ((HIGH + LOW) / 2)) - CLOSE)

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
    NON_KLINE_INDICATORS = ["alpha001", "alpha006", "alpha007", "alpha008", "alpha010",
                            "alpha012", "alpha016", "alpha017", "alpha021", "alpha025",
                            "alpha030", "alpha032", "alpha033", "alpha035", "alpha036",
                            "alpha037", "alpha039", "alpha041", "alpha042", "alpha045",
                            "alpha048", "alpha054", "alpha056", "alpha061", "alpha062",
                            "alpha064", "alpha073", "alpha074", "alpha075", "alpha077",
                            "alpha083", "alpha087", "alpha090", "alpha091", "alpha092",
                            "alpha099", "alpha101", "alpha104", "alpha105", "alpha107",
                            "alpha108", "alpha113", "alpha114", "alpha115", "alpha116",
                            "alpha119", "alpha120", "alpha121", "alpha123", "alpha124",
                            "alpha125", "alpha130", "alpha131", "alpha136", "alpha138",
                            "alpha140", "alpha141", "alpha142", "alpha147", "alpha148",
                            "alpha149", "alpha156", "alpha157", "alpha163", "alpha170",
                            "alpha176", "alpha179", "alpha181", "alpha182", "alpha184",
                            "alpha185"]
    #: 纯时序因子编号（desk 里能显示的 120 个）
    PURE_INDICATORS = [2, 3, 4, 5, 9, 11, 13, 14, 15, 18, 19, 20, 22, 23, 24, 26, 27, 28, 29, 31, 34, 38, 40, 43, 44, 46, 47, 49, 50, 51, 52, 53, 55, 57, 58, 59, 60, 63, 65, 66, 67, 68, 69, 70, 71, 72, 76, 78, 79, 80, 81, 82, 84, 85, 86, 88, 89, 93, 94, 95, 96, 97, 98, 100, 102, 103, 106, 109, 110, 111, 112, 117, 118, 122, 126, 127, 128, 129, 132, 133, 134, 135, 137, 139, 143, 144, 145, 146, 150, 151, 152, 153, 154, 155, 158, 159, 160, 161, 162, 164, 165, 166, 167, 168, 169, 171, 172, 173, 174, 175, 177, 178, 180, 183, 186, 187, 188, 189, 190, 191]
