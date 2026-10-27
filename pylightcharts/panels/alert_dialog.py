"""``AlertDialog``：价格预警对话框（复刻 miniqt / TradingView 的「创建预警」）。

```python
from pylightcharts.panels import AlertDialog

dialog = AlertDialog(chart.win, symbol='SHFE.rb2610', price=3600.0)
dialog.on_create(lambda payload: print('创建', payload))
dialog.on_delete(lambda alert_id: print('删除', alert_id))
dialog.set_items(existing_alerts)
dialog.open()
```

字段（和 miniqt 的 `TradingViewAlertDialog` 一致）：

| 字段 | 说明 |
| --- | --- |
| 价格 | 触发价 |
| 方向 | `穿过 / 上穿 / 下穿` |
| 到期时间 | 1 小时 / 1 天 / 1 周 / 无到期 |
| 消息 | 触发时显示的提醒（留空 → 自动生成） |
| 触发动作 | `无操作 / 买 / 卖 / 平`（动作 ≠ 无操作时，前端会问一句要不要下单） |
| 手数 | 下单数量 |
| 已有预警 | 列表（可逐条删除；已触发的标「已触发」） |

事件载荷（``;;;`` 分隔）：``create;;;<json>`` / ``delete;;;<id>``。
"""
from __future__ import annotations

import json
from typing import Callable, Iterable, Optional

from .base import Panel, _derived_theme_colors

_SEP = ';;;'


class AlertDialog(Panel):
    """创建 / 管理价格预警的对话框面板。"""

    def __init__(
        self,
        window,
        *,
        symbol: str = '',
        price: Optional[float] = None,
        crosses: Optional[Iterable[str]] = None,
        expires: Optional[Iterable[tuple]] = None,
        actions: Optional[Iterable[str]] = None,
        items: Optional[Iterable[dict]] = None,
        theme: str = 'dark',
    ):
        super().__init__(window)
        options = {
            'symbol': str(symbol or ''),
            'price': float(price) if price is not None else None,
            'items': [dict(item) for item in (items or [])],
        }
        if crosses:
            options['crosses'] = [str(item) for item in crosses]
        if expires:
            options['expires'] = [[str(label), int(seconds)]
                                  for label, seconds in expires]
        if actions:
            options['actions'] = [str(item) for item in actions]
        self._create('AlertDialog', options)
        self._bind_callback(self._dispatch)
        self.set_theme(theme)

        self._on_create: Optional[Callable] = None
        self._on_delete: Optional[Callable] = None
        self._items: list = [dict(item) for item in (items or [])]

    # ------------------------------------------------------------- 交互
    def open(self, symbol: str = '', price: Optional[float] = None) -> 'AlertDialog':
        """打开（可顺手改商品/价格 ✓）"""
        if symbol:
            self._set('setSymbol', str(symbol))
        if price is not None:
            self._set('setPrice', float(price))
        self._set('open')
        return self

    def close(self) -> 'AlertDialog':
        self._set('close')
        return self

    def set_items(self, items: Iterable[dict]) -> 'AlertDialog':
        """刷新「已有预警」列表（`[{id, price, action, qty, message, fired}]`）"""
        self._items = [dict(item) for item in (items or [])]
        self._set('setItems', self._items)
        return self

    def set_theme(self, theme: str) -> 'AlertDialog':
        self._set('setTheme', 'light' if str(theme) == 'light' else 'dark')
        return self

    def apply_theme(self, spec: dict) -> None:
        """跟着 `Window.theme()` 走（浅底 → light 调色板 ✓）"""
        spec = spec or {}
        colors = _derived_theme_colors(spec)
        self.set_theme('light' if colors['light'] else 'dark')

    # ------------------------------------------------------------- 事件
    def on_create(self, func: Callable[[dict], None]) -> 'AlertDialog':
        """``func({'price','cross','expire','message','action','qty'})``"""
        self._on_create = func
        return self

    def on_delete(self, func: Callable[[object], None]) -> 'AlertDialog':
        """``func(alert_id)``"""
        self._on_delete = func
        return self

    def _dispatch(self, *args) -> None:
        message = str(args[0]) if args else ''
        parts = message.split(_SEP)
        if len(parts) < 2:
            return
        kind = parts[0]
        if kind == 'create' and self._on_create is not None:
            try:
                payload = json.loads(parts[1])
            except (TypeError, ValueError):
                return
            if isinstance(payload, dict):
                self._on_create(payload)
        elif kind == 'delete' and self._on_delete is not None:
            raw = parts[1]
            try:
                alert_id: object = int(raw)
            except (TypeError, ValueError):
                alert_id = raw
            self._on_delete(alert_id)
