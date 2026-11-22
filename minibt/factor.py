"""Alpha101 / Alpha191 **横截面因子研究接口**（`minibt.factor` ✓）

为什么单独有这个模块：原版 WQ Alpha101 / GTJA Alpha191 是**多标的横截面**
因子（`RANK` 跨股票排名、`INDNEUTRALIZE` 按行业中性化）—— minibt 的 K 线
是**单个标的**，这些算子没有意义。研究 / 选股场景给一张多标的面板就行：

```python
import minibt
import pandas as pd

# 面板需要：securityid / tradetime / open / high / low / close / vol
# 可选：vwap（缺 → 典型价）、amount、indclass、cap
frame = pd.read_csv('panel.csv')
values = minibt.factor.panel(frame, 'wq101', 101)     # 一行一个标的×时点

minibt.factor.available('gtja191')   # 编号 + 是否横截面 + 公式
minibt.factor.numbers('gtja191')     # 纯时序编号（单标的也能用 ✓）
```

单标的因子**不需要**这个模块：`self.data.af.alpha191_002()` 直接画图 ✓
"""
from __future__ import annotations

from typing import Any

import pandas as pd

__all__ = ['panel', 'available', 'numbers', 'formula']

NOT_INSTALLED = ('Alpha101 / Alpha191 因子需要安装 py-alpha-lib：'
                 'py -3.12 -m pip install py-alpha-lib')


def _sub():
    """惰性导入（没装 py-alpha-lib / 不用因子时零开销 ✓）"""
    try:
        from .indicators import _alpha_factors as factors
    except Exception as error:                                   # noqa: BLE001
        raise RuntimeError(NOT_INSTALLED) from error
    return factors


def panel(data, family: str = 'gtja191', no: int = 2) -> pd.Series:
    """多标的 DataFrame → 因子值（长度 / 索引和输入一致 ✓）

    Args:
        data: 面板 DataFrame，列：``securityid`` / ``tradetime`` /
            ``open`` / ``high`` / ``low`` / ``close`` / ``vol``
            （可选 ``vwap`` / ``amount`` / ``indclass`` / ``cap``）
        family: ``'wq101'``（WQ Alpha101）或 ``'gtja191'``（GTJA Alpha191）
        no: 因子编号（1~101 / 1~191）

    Returns:
        pd.Series: 因子值（横截面因子也能算：内部按 `securityid` 分组 ✓）

    Examples:
        >>> values = minibt.factor.panel(frame, 'wq101', 101)
        >>> frame['alpha101_101'] = values
    """
    return _sub().panel_values(data, family, no)


def available(family: str | None = None) -> dict[str, Any]:
    """可用因子清单：``{family: {label, count, factors: {no: {kind, formula}}}}``

    ``kind``：``ts`` 纯时序（单标的可算）/ ``cross`` 横截面 / ``external``
    缺外部数据（基准指数 / 市值风格因子）✓
    """
    return _sub().available(family)


def numbers(family: str = 'gtja191', kind: str = 'ts') -> list[int]:
    """某一类因子的编号（``ts`` / ``cross`` / ``external`` ✓）"""
    factors = _sub()
    table = {
        'ts': factors.TS_NUMBERS,
        'cross': factors.CROSS_NUMBERS,
        'external': factors.EXTERNAL_NUMBERS,
    }.get(str(kind or 'ts').lower())
    if table is None:
        raise ValueError(f"kind 只能是 ts / cross / external：{kind!r}")
    if family not in table:
        raise ValueError(f'未知因子家族 {family!r}：可选 '
                         f'{", ".join(sorted(table))}')
    return list(table[family])


def formula(family: str, no: int) -> str:
    """某个因子的原始公式（源码注释里的表达式 ✓）"""
    return _sub().factor_info(family, no)['formula']
