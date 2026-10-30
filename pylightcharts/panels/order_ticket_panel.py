# coding: utf-8
"""下单窗口（照快期那张单子设计的，供模拟账号面板用）。

布局（紧凑、跟图表同一套深色主题）：:

    ┌───────────────────────────┐
    │  [ ag2612            🔍 ] │  ← 可编辑的**合约搜索框**（下拉选合约）
    │ ─────────────────────────  │
    │  卖5  14622   0           │  ← 五档阶梯：**点某一行 → 价格填进去**
    │  …                        │     卖盘用跌色、买盘用涨色
    │  卖1  14618   1           │
    │  买1  14610   2           │
    │  …                        │
    │  买5  14606   0           │
    │ ─────────────────────────  │
    │  手数   [ - ]  1  [ + ]    │  ← 默认 1 手，加减 1 ✓
    │  价格   [ - ] 14618 [ + ]  │  ← 上下键调价（步长 = 最小变动价位 ✓）
    │ ─────────────────────────  │
    │  [ 买入 ] [ 卖出 ] [ 平仓 ] │
    └───────────────────────────┘

只用 qfluentwidgets 控件拼出来（**壳**），合约搜索先用假数据。
以后做成 pylightcharts 的 JS 面板照这个布局来即可；
接口保持 ``set_book(...)`` / ``symbol()`` / ``actionRequested`` ✓。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QGridLayout, QHBoxLayout, QSizePolicy,
                            QVBoxLayout)

from qfluentwidgets import (Action, BodyLabel, CaptionLabel, CardWidget,
                            FluentIcon, PushButton, RoundMenu,
                            SearchLineEdit, StrongBodyLabel,
                            TransparentToolButton)

#: 五档盘口：卖 5 档 + 买 5 档 ✓
BOOK_ROWS = 5
#: 涨/跌色（和图表一致：多红 / 空绿 ✓）
UP_COLOR = '#ef5350'
DOWN_COLOR = '#26a69a'
#: 动作按钮（只要这三个 ✓）
ACTIONS = ('买入', '卖出', '平仓')
#: 合约搜索用的**假数据**（接入时换成看盘工具栏那个商品搜索 ✓）
FAKE_CONTRACTS = (
    ('SHFE.ag2612', '沪银2612'), ('SHFE.ag2701', '沪银2701'),
    ('SHFE.au2612', '沪金2612'), ('SHFE.cu2612', '沪铜2612'),
    ('SHFE.rb2610', '螺纹钢2610'), ('SHFE.ru2611', '橡胶2611'),
    ('DCE.i2609', '铁矿石2609'), ('DCE.m2609', '豆粕2609'),
    ('CZCE.TA610', 'PTA610'), ('CFFEX.IF2609', '沪深300 2609'),
)


class OrderTicketPanel(CardWidget):
    """下单窗口（合约搜索 + 五档 + 手数/价格 + 买入/卖出/平仓 ✓）。"""

    #: 点动作按钮：``(动作名, 手数, 价格, 合约)`` ✓
    actionRequested = pyqtSignal(str, int, float, str)
    #: 合约变了（下拉选 / 校验通过）→ 宿主立刻去接该合约的二级报价 ✓
    symbolChanged = pyqtSignal(str)
    #: 手输**回车** → 请求宿主先**校验合约合法性**再决定要不要生效 ✓
    symbolCommitRequested = pyqtSignal(str)

    def __init__(self, parent=None, symbol: str = 'SHFE.ag2612',
                 price_tick: float = 1.0, contracts=None):
        super().__init__(parent)
        self.setObjectName('OrderTicketPanel')
        self.setFixedWidth(240)
        # 不要纵向拉伸：否则多出来的高度会在按钮下面堆成一大块空白 ✗
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Maximum)
        self._symbol = symbol
        self._tick = float(price_tick) or 1.0
        self._contracts = list(contracts or FAKE_CONTRACTS)
        self._book: dict = {}
        self._volume = 1
        self._price = 0.0

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ---- 1) 合约搜索框（可编辑 + 下拉选择 ✓）----
        self.symbolEdit = SearchLineEdit(self)
        self.symbolEdit.setPlaceholderText('搜索合约（代码 / 名称）')
        self.symbolEdit.setText(symbol)
        self.symbolEdit.setClearButtonEnabled(True)
        self.symbolEdit.textChanged.connect(self._on_symbol_text)
        self.symbolEdit.returnPressed.connect(self._pick_first_match)
        # ⚠ 边打字边弹菜单会把界面卡住（菜单会抢焦点 / exec 阻塞）✗
        # → 打字时**什么都不弹**，只看下面的 ▼ 按钮主动拉候选 ✓
        self.symbolRow = QHBoxLayout()
        self.symbolRow.setSpacing(4)
        self.symbolRow.addWidget(self.symbolEdit, 1)
        self.matchButton = TransparentToolButton(FluentIcon.DOWN, self)
        self.matchButton.setToolTip('展开合约候选（也可以直接输代码回车）')
        self.matchButton.clicked.connect(self._on_match_button)
        self.symbolRow.addWidget(self.matchButton)
        root.addLayout(self.symbolRow)
        self._menu = RoundMenu(parent=self)
        self._showing_menu = False

        # ---- 2) 五档阶梯（点价格 → 填「价格」✓）----
        self._bookLabels: dict = {}
        book = QGridLayout()
        book.setContentsMargins(0, 2, 0, 2)
        book.setHorizontalSpacing(6)
        book.setVerticalSpacing(1)
        for index in range(BOOK_ROWS):           # 卖 5…卖 1
            self._add_book_row(book, index, f'卖{BOOK_ROWS - index}',
                               DOWN_COLOR, 'ask', BOOK_ROWS - index)
        for index in range(BOOK_ROWS):           # 买 1…买 5
            self._add_book_row(book, BOOK_ROWS + index, f'买{index + 1}',
                               UP_COLOR, 'bid', index + 1)
        root.addLayout(book)

        # ---- 3) 手数（默认 1，加减 1 ✓）----
        self.volumeLabel = StrongBodyLabel('1', self)
        root.addLayout(self._stepper_row('手数', self.volumeLabel,
                                         self._volume_down, self._volume_up))

        # ---- 4) 价格（上下键调价 ✓）----
        self.priceLabel = StrongBodyLabel('—', self)
        root.addLayout(self._stepper_row('价格', self.priceLabel,
                                         self._price_down, self._price_up))

        # ---- 5) 三个按钮 ✓ ----
        row = QHBoxLayout()
        row.setSpacing(4)
        self.actionButtons: list = []
        for label in ACTIONS:
            button = PushButton(label, self)
            color = UP_COLOR if label == '买入' else DOWN_COLOR
            button.setStyleSheet(f'color:{color};')
            button.clicked.connect(
                lambda _=False, name=label: self._fire(name))
            row.addWidget(button, 1)
            self.actionButtons.append(button)
        root.addLayout(row)

        self.statusLabel = CaptionLabel('（未下单）', self)
        self.statusLabel.setWordWrap(True)
        self.statusLabel.setAlignment(Qt.AlignmentFlag.AlignTop
                                      | Qt.AlignmentFlag.AlignLeft)
        # 按钮下面只留**两三条下单信息**的空间就够（不再是一大块空白 ✓）
        line = max(16, self.statusLabel.fontMetrics().lineSpacing())
        self.statusLabel.setFixedHeight(line * 3 + 6)
        root.addWidget(self.statusLabel)

    # ---- 合约搜索 ----------------------------------------------------------
    def _stepper_row(self, title, valueLabel, on_down, on_up):
        row = QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(CaptionLabel(title, self))
        down = TransparentToolButton(FluentIcon.REMOVE, self)
        down.setToolTip(f'{title} -1')
        down.clicked.connect(lambda _=False: on_down())
        row.addWidget(down)
        valueLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        valueLabel.setMinimumWidth(66)
        row.addWidget(valueLabel, 1)
        up = TransparentToolButton(FluentIcon.ADD, self)
        up.setToolTip(f'{title} +1')
        up.clicked.connect(lambda _=False: on_up())
        row.addWidget(up)
        return row

    def _matches(self, text: str) -> list:
        query = (text or '').strip().lower()
        items = []
        for code, name in self._contracts:
            if not query or query in code.lower() or query in name.lower():
                items.append((code, name))
        return items[:10]

    def _on_symbol_text(self, _text: str) -> None:
        """输入时什么都不做（不弹菜单 → 打字绝不卡 ✓）。"""
        return None

    def _on_match_button(self) -> None:
        self._show_matches()

    def _show_matches(self) -> None:
        """弹下拉候选（**非阻塞** ``popup``，假数据；接入时换成商品搜索 ✓）。"""
        items = self._matches(self.symbolEdit.text())
        if not items:
            return None
        self._menu.clear()
        for code, name in items:
            action = Action(f'{code}   {name}', self)
            action.triggered.connect(
                lambda _=False, c=code: self.set_symbol(c))
            self._menu.addAction(action)
        if self._showing_menu:            # 已经在弹就别再弹（防重入卡住 ✓）
            return None
        self._showing_menu = True
        try:
            self._menu.exec(self.symbolEdit.mapToGlobal(
                self.symbolEdit.rect().bottomLeft()))
        except Exception:                                        # noqa: BLE001
            pass
        finally:
            self._showing_menu = False
        return None

    def resolve_symbol(self, text: str = '') -> str:
        """手输的简写补全成完整合约：``ag2612`` / ``沪银2612`` → ``SHFE.ag2612`` ✓。

        ⚠ **不能把整串转大写** —— 合约代码是大小写敏感的：
        ``SHFE.ag2612`` 写成 ``SHFE.AG2612`` 天勤会报
        ``contains non-existent instrument`` ✗。只把**交易所**部分大写，
        合约部分用候选目录里的原始大小写 ✓。
        """
        text = (text or self.symbolEdit.text() or '').strip()
        if not text:
            return ''
        if '.' in text:
            exchange, _, code = text.partition('.')
            full = f'{exchange.upper()}.{code}'
            for known, _name in self._contracts:
                if known.lower() == full.lower():
                    return known          # 目录里的原始大小写 ✓
            return full
        items = self._matches(text)
        if items:
            # 完全等于代码 / 名称的优先，否则取第一个 ✓
            for code, name in items:
                if text.upper() == code.upper() or text == name:
                    return code
            return items[0][0]
        return text                       # 找不到就原样（别再大写 ✓）

    def _pick_first_match(self) -> None:
        """回车：交给宿主校验（能不能在天勤里查到）→ 通过才生效 ✓。

        不合法 / 取不到行情 → 宿主会把合约**还原成上一个** ✓。
        """
        self.symbolCommitRequested.emit(self.symbolEdit.text().strip())

    def set_symbol(self, symbol: str) -> None:
        symbol = str(symbol or '').strip()
        if getattr(self, '_setting_symbol', False):     # 防重入 ✓
            return None
        self._setting_symbol = True
        try:
            self._set_symbol(symbol)
        finally:
            self._setting_symbol = False
        return None

    def _set_symbol(self, symbol: str) -> None:
        self._symbol = symbol
        if self.symbolEdit.text() != symbol:      # 阻断信号，别再弹下拉 ✓
            self.symbolEdit.blockSignals(True)
            self.symbolEdit.setText(symbol)
            self.symbolEdit.blockSignals(False)
        self._price = 0.0                         # 换合约 → 价格重新跟盘口 ✓
        self.priceLabel.setText('—')
        self.statusLabel.setText(f'当前合约：{symbol}')
        self.symbolChanged.emit(symbol)

    def symbol(self) -> str:
        return (self.symbolEdit.text() or self._symbol).strip()

    # ---- 五档 --------------------------------------------------------------
    def _add_book_row(self, layout, row_index, tag, color, side, level):
        tagLabel = CaptionLabel(tag, self)
        tagLabel.setStyleSheet(f'color:{color};')
        priceLabel = BodyLabel('—', self)
        priceLabel.setAlignment(Qt.AlignmentFlag.AlignRight
                                | Qt.AlignmentFlag.AlignVCenter)
        priceLabel.setCursor(Qt.CursorShape.PointingHandCursor)
        priceLabel.setToolTip('点这一行 → 价格填进下单窗口 ✓')
        priceLabel.mousePressEvent = (
            lambda _event, s=side, lv=level: self._pick_price(s, lv))
        volumeLabel = CaptionLabel('—', self)
        volumeLabel.setAlignment(Qt.AlignmentFlag.AlignRight
                                 | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(tagLabel, row_index, 0)
        layout.addWidget(priceLabel, row_index, 1)
        layout.addWidget(volumeLabel, row_index, 2)
        self._bookLabels[f'{side}{level}'] = (priceLabel, volumeLabel)

    def set_book(self, asks=None, bids=None) -> None:
        """``asks`` / ``bids``：``[(price, volume), …]``（各自从近到远 ✓）。"""
        self._book = {'ask': list(asks or []), 'bid': list(bids or [])}
        for side in ('ask', 'bid'):
            values = self._book[side]
            for level in range(1, BOOK_ROWS + 1):
                labels = self._bookLabels.get(f'{side}{level}')
                if labels is None:
                    continue
                if level <= len(values):
                    price, volume = values[level - 1]
                    labels[0].setText('—' if price is None else f'{price:g}')
                    labels[1].setText('—' if volume is None else f'{volume:g}')
                else:
                    labels[0].setText('—')
                    labels[1].setText('—')
        if self._price <= 0:                # 还没价 → 用卖一价打底 ✓
            self.set_price(self._best_price())

    def _best_price(self) -> float:
        for side in ('ask', 'bid'):
            values = self._book.get(side) or []
            if values and values[0][0] is not None:
                return float(values[0][0])
        return 0.0

    def _pick_price(self, side: str, level: int):
        """点五档某一行 → 价格填进去（第 4 条要求 ✓）。"""
        values = self._book.get(side) or []
        if level <= len(values) and values[level - 1][0] is not None:
            self.set_price(float(values[level - 1][0]))
        return None

    # ---- 手数 / 价格 --------------------------------------------------------
    def _volume_down(self):
        self.set_volume(self._volume - 1)

    def _volume_up(self):
        self.set_volume(self._volume + 1)

    def set_volume(self, volume: int) -> int:
        self._volume = max(1, int(volume))          # 最少 1 手 ✓
        self.volumeLabel.setText(str(self._volume))
        return self._volume

    def volume(self) -> int:
        return self._volume

    def _price_down(self):
        self.set_price(self._price - self._tick)

    def _price_up(self):
        self.set_price(self._price + self._tick)

    def set_price(self, price: float) -> float:
        value = max(0.0, float(price))
        if self._tick > 0:                  # 对齐到最小变动价位，显示才干净 ✓
            value = round(value / self._tick) * self._tick
        self._price = value
        text = f'{self._price:.4f}'.rstrip('0').rstrip('.') or '0'
        self.priceLabel.setText(text)
        return self._price

    def price(self) -> float:
        return self._price

    def set_price_tick(self, tick: float) -> None:
        self._tick = float(tick) or 1.0

    # ---- 动作 --------------------------------------------------------------
    def _fire(self, name: str) -> None:
        """``买入 / 卖出 / 平仓``（壳：只更新状态栏 ✓）。"""
        self.statusLabel.setText(
            f'「{name}」{self._volume} 手 @ {self.priceLabel.text()}'
            f'  {self.symbol()}')
        self.actionRequested.emit(name, self._volume, self._price,
                                  self.symbol())

    def set_status(self, text: str) -> None:
        self.statusLabel.setText(text)
