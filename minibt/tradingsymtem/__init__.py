"""交易系统指标包（**只出信号、不出指标线**）。

用法：

```python
from minibt import *

self.ts = self.kline.tradingsystem.momentum.rsi_reversal()   # 分类访问
self.ts = self.kline.tradingsystem.momentum_rsi_reversal()   # 扁平访问
self.v = self.kline.tradingsystem.trend.adx(length=14)        # 只取值、不出信号
```

**分类下有哪些指标？看代码就能知道（IDE 可补全 ✓）**：
每个分类文件（如 `trend.py`）里的类，**生成区**内的 `def` 就是从规则表
展开来的真实方法 —— 在 `kline.tradingsystem.trend.` 后面一敲就列出来了；
加新系统：在 `tradingsystem.py` 的 `SYSTEMS` 里补一条配方，再跑
``py -3.12 scripts/gen_trading_systems.py --write``。

注册表 / 规则表：

```python
from minibt.tradingsymtem import systems, get
for category, table in systems().items():
    print(category, list(table))
```
"""
from .base import LIB_ORDER, LIB_TABLE, TradingSystemBase, TradingSystemCategory
from .tradingsystem import (
    CATEGORIES,
    SYSTEMS,
    TradingSystem,
    build,
    get,
    systems,
)

__all__ = [
    'CATEGORIES',
    'LIB_ORDER',
    'LIB_TABLE',
    'SYSTEMS',
    'TradingSystem',
    'TradingSystemBase',
    'TradingSystemCategory',
    'build',
    'get',
    'systems',
]
