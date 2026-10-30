"""模拟账号面板（底层壳）—— 表格 + 操作按钮 + 右侧下单窗口。

这是给「模拟账号」界面优化的**底层壳**：先把布局和交互演出来，看看效果，
确认之后再决定要不要搬成 pylightcharts 的 JS 面板（那样渲染更顺、更新更稳 ✓）。

布局（从左到右）：:

    ┌──────────────────────────────┬──────┬──────────────┐
    │  持仓 / 委托 / 成交记录 / 未成委托  │ 平   │  价格  [ ]  │
    │  （表格，原地更新、行数封顶 ✓）      │ 反   │  手数  [ ]  │
    │                              │ 全   │  买入  卖出  │
    │                              │ 组   │              │
    └──────────────────────────────┴──────┴──────────────┘

* 中间那列是**操作按钮**：持仓单是「平 / 反 / 全 / 组」，
  委托 / 未成委托是「撤 / 全」（切换上面的 Tab 会自动换 ✓）；
* 最右边是一个**简单下单窗口**（价格 / 手数 / 买入 / 卖出）✓；
* 数据是**假的**（自带一个定时器模拟行情跳动），只演示界面与更新方式 ✓。

    python examples/13_panels/11_sim_account_shell.py
"""
from __future__ import annotations

import random
import sys

sys.path.insert(0, str(__import__('pathlib').Path(__file__)
                       .resolve().parents[2]))

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QTableWidgetItem,
                             QVBoxLayout, QWidget)

from qfluentwidgets import (BodyLabel, PushButton, SegmentedWidget,
                            TableWidget, setTheme, Theme)

#: 表格最多渲染多少行（和 miniqt 里一致：控开销 ✓）
MAX_ROWS = 200

#: 每个 Tab 的列 + 中间那列的按钮（用户要求 ✓）
TABS = (
    ('positions', '持仓',
     ['合约', '买卖', '总仓', '可用', '开仓价', '持仓均价', '浮动盈亏',
      '持仓市值', '占用保证金'],
     ('平', '反', '全')),
    ('orders', '委托',
     ['委托合约', '买卖', '开平', '手', '未成交', '报单价', '挂单状态',
      '成交价', '报单时间'],
     ('撤', '全')),
    ('trades', '成交记录',
     ['成交合约', '买卖', '开平', '成交价', '手', '手续费', '成交时间'],
     ()),
    ('open_orders', '未成委托',
     ['委托合约', '买卖', '开平', '手', '未成交', '报单价', '挂单状态',
      '成交价', '报单时间'],
     ('撤', '全')),
)


def _make_rows(kind: str) -> list:
    """假数据（带一点随机，好看出「原地更新」的效果 ✓）。"""
    price = 14700 + random.random() * 40
    if kind in ('orders', 'open_orders'):
        return [{'symbol': 'SHFE.ag2612', 'direction': '买', 'offset': '开',
                 'volume': 1, 'left': 1, 'price': round(price, 0),
                 'status': '有效', 'trade_price': '—', 'time': '09:31:02'}]
    if kind == 'trades':
        return [{'symbol': 'SHFE.ag2612', 'direction': '买', 'offset': '开',
                 'price': round(price, 0), 'volume': 1, 'commission': 11.2,
                 'time': '09:30:55'}]
    return [{'symbol': 'SHFE.ag2612', 'direction': '买', 'total': 3,
             'usable': 3, 'open_price': 14728.0, 'avg_price': 14732.0,
             'float_profit': round((price - 14732.0) * 15, 2),
             'market_value': 221010.0, 'margin': 49262.4}]


BOOK_ROWS = 5


class SimAccountShell(QWidget):
    """模拟账号面板壳（表格 + 操作按钮 + 下单窗口 ✓）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('SimAccountShell')
        # 壳自己撑起背景（不靠父窗口）：深色主题下才不会是白芒芒 ✓
        self.setStyleSheet(
            'QWidget#SimAccountShell{background:rgba(32,32,32,1);}'
            'QWidget#SimAccountShell QLabel{color:rgba(240,240,240,1);}')
        self._cells: dict = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 6)
        root.setSpacing(6)

        # ---- 1) 表格 + Tab ----
        left = QVBoxLayout()
        left.setSpacing(4)
        self.segmented = SegmentedWidget(self)
        self.tables: dict = {}
        for key, title, columns, _buttons in TABS:
            self.segmented.addItem(key, title)
            table = TableWidget(self)
            table.setColumnCount(len(columns))
            table.setHorizontalHeaderLabels(columns)
            table.verticalHeader().hide()
            table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
            table.setBorderVisible(True)
            table.setBorderRadius(6)
            table.horizontalHeader().setSectionResizeMode(
                table.horizontalHeader().ResizeMode.Stretch)
            table.hide()
            self.tables[key] = table
            left.addWidget(table)
        self.segmented.currentItemChanged.connect(self._switch)
        left.insertWidget(0, self.segmented)
        root.addLayout(left, 1)

        # ---- 2) 中间：操作按钮（跟着 Tab 换 ✓）----
        self.actionColumn = QVBoxLayout()
        self.actionColumn.setSpacing(4)
        self.actionButtons: list = []
        holder = QVBoxLayout()
        holder.addLayout(self.actionColumn)
        holder.addStretch(1)
        root.addLayout(holder)

        # ---- 3) 最右：下单窗口（照快期那张单子设计 ✓）----
        from pylightcharts.panels.order_ticket_panel import OrderTicketPanel
        self.orderTicket = OrderTicketPanel(self, symbol='SHFE.ag2612')
        self.orderTicket.actionRequested.connect(self._on_ticket)
        self.orderStatus = self.orderTicket.statusLabel
        root.addWidget(self.orderTicket)

        self._switch(TABS[0][0])
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(500)                 # 500ms 一跳，看原地更新顺不顺 ✓

    # ---- 交互 -------------------------------------------------------------
    def _switch(self, key: str) -> None:
        for name, table in self.tables.items():
            table.setVisible(name == key)
        for button in self.actionButtons:
            self.actionColumn.removeWidget(button)
            button.deleteLater()
        self.actionButtons = []
        buttons = next((item[3] for item in TABS if item[0] == key), ())
        for label in buttons:
            button = PushButton(label, self)
            button.clicked.connect(
                lambda _=False, name=label, k=key: self._action(k, name))
            self.actionColumn.addWidget(button)
            self.actionButtons.append(button)
        self._refresh()

    def _action(self, key: str, label: str) -> None:
        self.orderStatus.setText(f'[{key}] 点了「{label}」（壳：还没接天勤 ✓）')

    def _on_ticket(self, name: str, volume: int, price: float) -> None:
        """下单窗口的按钮（壳：还没接天勤 ✓）。"""
        self.orderStatus.setText(f'{name} {volume} 手 @ {price:g}（壳：还没接天勤 ✓）')

    # ---- 数据（原地更新 ✓）------------------------------------------------
    def _refresh(self) -> None:
        for key, _title, columns, _buttons in TABS:
            self._fill(key, _make_rows(key), columns)
        # 五档盘口（假数据，随机跳一下好看效果 ✓）
        base = 14700 + random.random() * 30
        asks = [(base + (BOOK_ROWS - i) * 10, random.choice([0, 1, 2, 4]))
                for i in range(BOOK_ROWS)]
        bids = [(base - (i + 1) * 10, random.choice([0, 1, 2, 3]))
                for i in range(BOOK_ROWS)]
        self.orderTicket.set_book(asks, bids)

    def _fill(self, key: str, rows: list, columns: list) -> None:
        table = self.tables[key]
        rows = rows[:MAX_ROWS]
        if table.rowCount() != len(rows):
            table.setRowCount(len(rows))      # 只有行数变了才动结构 ✓
        for row_index, row in enumerate(rows):
            values = list(row.values())
            for column in range(len(columns)):
                text = str(values[column]) if column < len(values) else ''
                item = table.item(row_index, column)
                if item is None:              # 复用单元格，不重建 ✓
                    item = QTableWidgetItem('')
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                          | Qt.AlignmentFlag.AlignVCenter)
                    table.setItem(row_index, column, item)
                if item.text() != text:
                    item.setText(text)


def main():
    # ⚠ ``setTheme`` 必须在 **QApplication 之后、建控件之前**调 ——
    # 放在 app 前面会出现「深色前景 + 浅色背景」＝白字白底一片白 ✗
    app = QApplication(sys.argv)
    setTheme(Theme.DARK)
    window = QWidget()
    window.setObjectName('SimAccountShellWindow')
    # 纯 QWidget 不像 FluentWindow 会自己刷背景 → 手动跟主题 ✓
    window.setStyleSheet(
        'QWidget#SimAccountShellWindow'
        '{background:rgba(32,32,32,1);}')
    window.setWindowTitle('pylightcharts - 模拟账号面板壳')
    window.resize(1100, 460)
    layout = QVBoxLayout(window)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.addWidget(BodyLabel('模拟账号（底层壳）：表格 + 操作按钮 + 下单窗口 ✓'))
    layout.addWidget(SimAccountShell(window), 1)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
