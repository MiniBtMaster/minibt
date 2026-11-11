"""desk 本地画线持久化：键 = ``合约|周期`` ✓

用户 2026-10-29 需求：

* 多布局里所有图**共用一个画线工具**（前端 `drawings-sync.ts` 负责显隐）；
* 画线要**本地持久化**，同一个品种**不同周期各画各的**——
  不能把一个品种所有周期的画线混到同一个周期里显示（之前验证过会乱 ✗）。

所以存储键就是 :func:`drawing_key` 的 ``"<合约>|<周期秒>"``；本地图表用
"CSV 数据名"当合约，一样按 ``duration`` 分开 ✓。

落盘：``~/.minibt/desk/drawings.json``

```json
{
  "SHFE.ag2612|60": [ {"type": "TrendLine", "points": [...], "options": {...}} ],
  "l2609_60|60":    [ ... ]
}
```
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

_LOCK = threading.RLock()
#: 内存缓存（避免每次读盘；写盘后同步 ✓）
_CACHE: Dict[str, List[Any]] = {}
_LOADED = False


def drawings_file() -> str:
    return os.path.join(os.path.expanduser('~'), '.minibt', 'desk',
                        'drawings.json')


def drawing_key(symbol: str, cycle: Any = None) -> str:
    """存储键：``合约|周期``（周期缺失时只用合约 ✓）"""
    text = str(symbol or '')
    if cycle is None or str(cycle) == '':
        return text
    try:
        value = int(cycle)
    except (TypeError, ValueError):
        value = 0
    return f'{text}|{value}'


def _load() -> Dict[str, List[Any]]:
    global _LOADED
    if _LOADED:
        return _CACHE
    _LOADED = True
    try:
        with open(drawings_file(), encoding='utf-8') as handle:
            raw = json.load(handle) or {}
    except (OSError, ValueError):
        raw = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, list) and value:
                _CACHE[str(key)] = value
    return _CACHE


def _write() -> None:
    target = drawings_file()
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp = f'{target}.tmp'
        with open(tmp, 'w', encoding='utf-8') as handle:
            json.dump(_CACHE, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, target)
    except OSError:
        pass


def get(key: str) -> List[Any]:
    """某个键的画线（没有 → 空列表 ✓）"""
    with _LOCK:
        return list(_load().get(str(key or ''), []))


def save(key: str, items: Optional[List[Any]]) -> List[Any]:
    """整份覆盖某个键（空列表 = 删除该键 ✓）"""
    key = str(key or '')
    if not key:
        return []
    with _LOCK:
        data = _load()
        values = [item for item in (items or []) if isinstance(item, dict)]
        if values:
            data[key] = values
        else:
            data.pop(key, None)
        _write()
        return list(values)


def clear(key: str = '') -> None:
    """删一个键；``key=''`` 清空全部 ✓"""
    with _LOCK:
        data = _load()
        if key:
            data.pop(str(key), None)
        else:
            data.clear()
        _write()


def all_drawings() -> Dict[str, List[Any]]:
    with _LOCK:
        return {key: list(value) for key, value in _load().items()}
