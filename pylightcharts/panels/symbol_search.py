"""``SymbolSearch``：商品搜索（复刻 miniqt 顶栏的合约搜索）。

```python
from pylightcharts.panels import SymbolSearch

search = SymbolSearch(chart.win, items=rows)      # rows: [{symbol,name,exchange,type}]
search.on_pick(lambda item: print('切换合约', item['symbol']))
search.open()                                     # 也可 open('rb')
```

两种模式：

* **本地**：传了 ``items`` → 输入时前端自己过滤（几百个合约够用）；
* **远程**：不传 ``items`` → 输入防抖 150ms 后发 ``query;;;<text>``，
  后端用 :meth:`SymbolSearch.set_results` 回填（几千个合约更省 ✓）。

事件：``query;;;<text>`` / ``pick;;;<symbol>``。
"""
from __future__ import annotations

from typing import Callable, Iterable, Optional

from .base import Panel, _derived_theme_colors

_SEP = ';;;'


class SymbolSearch(Panel):
    """合约搜索框（模态；键盘 ↑↓ / Enter / Esc ✓）。"""

    def __init__(
        self,
        window,
        *,
        items: Optional[Iterable[dict]] = None,
        placeholder: str = '搜索商品 / 代码 / 名称',
        remote: Optional[bool] = None,
        limit: int = 200,
        width: int = 520,
        theme: str = 'dark',
    ):
        super().__init__(window)
        options = {
            'placeholder': str(placeholder or ''),
            'limit': int(limit),
            'width': int(width),
        }
        if items is not None:
            options['items'] = [_item(row) for row in items]
        if remote is not None:
            options['remote'] = bool(remote)
        self._create('SymbolSearch', options)
        self._bind_callback(self._dispatch)
        self.set_theme(theme)

        self._on_query: Optional[Callable] = None
        self._on_pick: Optional[Callable] = None

    # ------------------------------------------------------------- 交互
    def open(self, symbol: str = '') -> 'SymbolSearch':
        self._set('open', str(symbol or ''))
        return self

    def close(self) -> 'SymbolSearch':
        self._set('close')
        return self

    def set_items(self, items: Iterable[dict]) -> 'SymbolSearch':
        """本地模式：换一批可选合约 ✓"""
        self._set('setItems', [_item(row) for row in items])
        return self

    def set_results(self, items: Iterable[dict]) -> 'SymbolSearch':
        """远程模式：回填搜索结果 ✓"""
        self._set('setResults', [_item(row) for row in items])
        return self

    def set_theme(self, theme: str) -> 'SymbolSearch':
        self._set('setTheme', 'light' if str(theme) == 'light' else 'dark')
        return self

    def apply_theme(self, spec: dict) -> None:
        spec = spec or {}
        colors = _derived_theme_colors(spec)
        self.set_theme('light' if colors['light'] else 'dark')

    # ------------------------------------------------------------- 事件
    def on_query(self, func: Callable[[str], None]) -> 'SymbolSearch':
        """``func(text)`` —— 远程搜索（自己不传 items 时用 ✓）"""
        self._on_query = func
        return self

    def on_pick(self, func: Callable[[dict], None]) -> 'SymbolSearch':
        """``func({'symbol','name','exchange','type'})``"""
        self._on_pick = func
        return self

    def _dispatch(self, *args) -> None:
        message = str(args[0]) if args else ''
        parts = message.split(_SEP)
        if len(parts) < 2:
            return
        kind = parts[0]
        if kind == 'query' and self._on_query is not None:
            self._on_query(parts[1])
        elif kind == 'pick' and self._on_pick is not None:
            symbol = parts[1]
            self._on_pick({'symbol': symbol, 'name': '', 'exchange': '',
                           'type': ''})


def _item(row) -> dict:
    """行 → `{symbol, name, exchange, type}`（多余字段丢掉 ✓）"""
    if isinstance(row, dict):
        return {
            'symbol': str(row.get('symbol') or row.get('instrument_id') or ''),
            'name': str(row.get('name') or row.get('instrument_name') or ''),
            'exchange': str(row.get('exchange') or row.get('exchange_id') or ''),
            'type': str(row.get('type') or row.get('ins_class') or ''),
        }
    return {'symbol': str(row), 'name': '', 'exchange': '', 'type': ''}
