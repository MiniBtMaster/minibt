"""策略实盘的**运行开关**（新K线next / 运行next）——父进程与子进程之间的控制文件。

* 父进程（desk）：策略管理弹窗里的两个开关 → 写这里；
* 子进程（`minibt.desk.live_runner`）：每个 tick 读一次（按 mtime 缓存，几乎零开销）
  → 决定这次要不要跑策略的 `step()`。

文件：``~/.minibt/desk/live_control.json``

```json
{
  "C:/Users/me/.minibt/personal/strategies/test1.py": {
    "next_on_new_bar": true,
    "run_next": true
  }
}
```

两个开关的语义与「图表上的策略」一致（见 `desk/strategy_runner.py`）：

* ``next_on_new_bar=True``：只在**出现新 K 线**时跑 ``step()``；
* ``run_next=False``：**只算指标**、不跑 ``step()``（纯指标策略）。
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, Optional

#: 默认值（与 `user_prefs` 里 `strategy_next_on_new_bar` / `strategy_run_next` 一致 ✓）
DEFAULTS: Dict[str, bool] = {'next_on_new_bar': True, 'run_next': True}

_LOCK = threading.Lock()
#: (mtime_ns, size, data) —— 按文件变化缓存，子进程每秒读一次也不心疼 ✓
_CACHE: Dict[str, Any] = {'stamp': None, 'data': {}}


def control_file() -> str:
    return os.path.join(os.path.expanduser('~'), '.minibt', 'desk',
                        'live_control.json')


def normalize(path: str) -> str:
    """统一 key：绝对路径 + 正斜杠（Windows 上父子进程写法一致 ✓）"""
    text = str(path or '')
    if not text:
        return ''
    return os.path.abspath(os.path.expanduser(text)).replace('\\', '/')


def _load() -> Dict[str, dict]:
    target = control_file()
    try:
        stat = os.stat(target)
        stamp = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        stamp = None
    if _CACHE['stamp'] == stamp:
        return _CACHE['data']
    data: Dict[str, dict] = {}
    if stamp is not None:
        try:
            with open(target, encoding='utf-8') as handle:
                raw = json.load(handle) or {}
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if isinstance(value, dict):
                        data[normalize(key)] = value
        except (OSError, ValueError):
            data = {}
    _CACHE['stamp'] = stamp
    _CACHE['data'] = data
    return data


def _save(data: Dict[str, dict]) -> None:
    target = control_file()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = f'{target}.tmp'
    with open(tmp, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, target)
    try:
        stat = os.stat(target)
        _CACHE['stamp'] = (stat.st_mtime_ns, stat.st_size)
        _CACHE['data'] = data
    except OSError:
        pass


def read(path: str) -> Dict[str, bool]:
    """某个策略的开关（没写过 → 返回默认值 ✓）"""
    key = normalize(path)
    if not key:
        return dict(DEFAULTS)
    values = dict(DEFAULTS)
    with _LOCK:
        block = _load().get(key)
    if isinstance(block, dict):
        for name in DEFAULTS:
            if name in block:
                values[name] = bool(block[name])
    return values


def write(path: str, values: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
    """整块覆盖（启动策略时用；默认值 = `DEFAULTS` ✓）"""
    key = normalize(path)
    if not key:
        return dict(DEFAULTS)
    block = dict(DEFAULTS)
    for name in DEFAULTS:
        if isinstance(values, dict) and name in values:
            block[name] = bool(values[name])
    with _LOCK:
        data = dict(_load())
        data[key] = block
        _save(data)
    return block


def set_value(path: str, key: str, value: Any) -> Dict[str, bool]:
    """改一个开关（策略管理弹窗 ✓）"""
    if key not in DEFAULTS:
        return read(path)
    values = read(path)
    values[key] = bool(value)
    return write(path, values)


def clear(path: str) -> None:
    """删掉某个策略的条目（停止 / 删除后 ✓）"""
    key = normalize(path)
    if not key:
        return
    with _LOCK:
        data = dict(_load())
        if key in data:
            data.pop(key, None)
            _save(data)


def clear_all() -> None:
    with _LOCK:
        _save({})
