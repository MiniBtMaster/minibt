"""OrderTicket — the TradingView buy / spread / sell ticket (chart top-left).

A thin shell: it renders three cells（卖出 / 点差 / 买入）and is driven by
``set_data(sell=..., buy=..., spread=...)``. Clicking the two sides calls the
``on_side_click`` handler with ``'sell'`` / ``'buy'``; the host decides what
those do (e.g. place a simulated order).
"""
from __future__ import annotations

import json
from typing import Callable, Optional

from .base import Panel


class OrderTicket(Panel):
    """A buy / spread / sell quote block.

    ::

        ticket = OrderTicket(chart.win, on_side_click=on_buy_sell)
        ticket.set_data(sell=bid, buy=ask)
    """

    def __init__(self, window, sell: Optional[float] = None,
                 buy: Optional[float] = None, spread: Optional[float] = None,
                 *, decimals: int = 2, font_size: Optional[int] = None,
                 theme: Optional[dict] = None,
                 container: Optional[str] = None,
                 on_side_click: Optional[Callable[[str], None]] = None):
        super().__init__(window)
        self._on_side = on_side_click
        options: dict = {'decimals': int(decimals)}
        if font_size is not None:
            options['fontSize'] = int(font_size)
        if sell is not None:
            options['sell'] = sell
        if buy is not None:
            options['buy'] = buy
        if spread is not None:
            options['spread'] = spread
        if theme:
            options['theme'] = theme
        self._create('OrderTicket', options, container)
        self._labels: dict = {}
        if on_side_click is not None:
            self.on_side_click(on_side_click)

    def set_data(self, sell=None, buy=None, spread=None) -> 'OrderTicket':
        """Push the current sell / buy prices (and optional spread)."""
        data: dict = {}
        if sell is not None:
            data['sell'] = sell
        if buy is not None:
            data['buy'] = buy
        if spread is not None:
            data['spread'] = spread
        if data:
            self._set('setData', data)
        return self

    def set_labels(self, sell: Optional[str] = None,
                   buy: Optional[str] = None) -> 'OrderTicket':
        """改两个按钮的文字（按持仓方向：空仓 卖出/买入、多仓 平仓/买入、
        空仓 平仓/卖出 ……）✓。

        JS bundle 里的文字是写死的，这里直接改 DOM（`.pylc-ot-label`）——
        不用重建 bundle ✓，并且只在**真的变了**时才下发 ✓。
        左侧 = ``sell``（卖一价）、右侧 = ``buy``（买一价）。
        """
        changed: dict = {}
        if sell is not None and self._labels.get('sell') != sell:
            changed['sell'] = str(sell)
        if buy is not None and self._labels.get('buy') != buy:
            changed['buy'] = str(buy)
        if not changed:
            return self
        self._labels.update(changed)
        # 按 **class** 选（`.pylc-ot-buy` / `.pylc-ot-sell`），不靠 DOM 顺序 ——
        # 左右顺序以后改了也不会错位 ✓
        actions = []
        for key in ('buy', 'sell'):
            if key not in changed:
                continue
            actions.append(
                f"el.querySelector('.pylc-ot-{key} .pylc-ot-label')"
                f".textContent={json.dumps(changed[key])};")
        self.run_script(
            "(function(){var el=" + self.id + ".element;if(!el)return;"
            + ''.join(actions) + "})();")
        return self

    def on_side_click(self, func: Callable[[str], None]) -> 'OrderTicket':
        """Register ``func(side)`` where ``side`` is ``'sell'`` or ``'buy'``."""
        self._on_side = func
        self._bind_callback(lambda side='', **_kw: func(side))
        return self

    def set_options(self, **options) -> 'OrderTicket':
        self._set('setOptions', options)
        return self

    def apply_theme(self, spec: dict) -> None:
        theme = {
            'text': spec.get('text'),
            'muted': spec.get('crosshair'),
            'border': spec.get('border_color'),
        }
        theme = {key: value for key, value in theme.items() if value}
        if theme:
            self._set('setOptions', {'theme': theme})
