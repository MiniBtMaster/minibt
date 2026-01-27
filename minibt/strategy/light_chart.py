# coding:utf-8
# https://github.com/louisnw01/lightweight-charts-python
# https://tradingview.github.io/lightweight-charts/
# https://lightweight-charts-python.readthedocs.io/en/latest/index.html

from __future__ import annotations
from collections import deque
from lightweight_charts import Chart, util
from lightweight_charts.abstract import Line, Candlestick, AbstractChart
from lightweight_charts.drawings import HorizontalLine
import sys
from lightweight_charts.widgets import QtChart
from lightweight_charts.toolbox import ToolBox, json
from PyQt5.QtCore import Qt, QSize, QTimer, pyqtSignal, QUrl, QObject, QThread, QMetaObject
from PyQt5.QtGui import QColor, QFont, QPainter, QIcon, QPen
from PyQt5.QtWidgets import (QApplication,  QSplitter, QWidget, QVBoxLayout, QSizePolicy,
                             QHBoxLayout, QAbstractItemView, QTableWidgetItem, QHeaderView,)
from qfluentwidgets import (setTheme, Theme, FluentWindow, TransparentToolButton, RoundMenu, Action,
                            FluentIcon, FluentStyleSheet, FluentTitleBar, TableWidget, CaptionLabel,
                            Dialog, SearchLineEdit, ListWidget, PushButton,
                            BodyLabel, DoubleSpinBox, TitleLabel, SwitchButton, PrimaryPushButton,
                            ComboBox,  CardWidget, ScrollArea,
                            InfoBar, InfoBarPosition, HyperlinkLabel)

from typing import TYPE_CHECKING, Union, Iterable
if TYPE_CHECKING:
    from strategy import Strategy
from ..utils import Colors as btcolors, OrderedDict, _time
from ..other import FILED, os, pd, partial
from itertools import cycle
Colors: list[str] = ['fuchsia', 'lime', 'olive', 'blue', 'purple', 'silver', 'teal', 'aqua',
                     'green', 'maroon', 'navy', 'red']
mem_before = 0.


def get_colors() -> cycle:
    """指标初始颜色"""
    return cycle(Colors)


class FixedSizeQueue:
    def __init__(self, max_size, value=False, values: Iterable = None):
        self.queue = deque(maxlen=max_size)
        if not (values and isinstance(values, Iterable)):
            values = [False,]*10
        self.add_items(list(values))
        if isinstance(value, bool):
            self.add(value)

    def add(self, item) -> FixedSizeQueue:
        """添加单个元素"""
        self.queue.append(item)
        return self

    def add_items(self, items) -> FixedSizeQueue:
        """批量添加元素"""
        self.queue.extend(items)
        return self

    def get_all(self):
        """获取队列中所有元素（列表形式）"""
        return list(self.queue)

    def clear(self) -> FixedSizeQueue:
        """清空队列"""
        self.queue.clear()
        return self

    @property
    def any(self) -> bool:
        return any(self.queue)


class PriceAlertSettingDialog(Dialog):
    """
    简洁版价格预警设置对话框（基于自定义 Dialog 基类）
    核心功能：启用开关、预警类型、上下破价格设置
    """
    alertSettingsChanged = pyqtSignal(dict)

    def __init__(self, title="", content="", parent: LightChartWindow = None, current_settings: dict = None):
        """
        初始化对话框（调用基类构造方法，后续替换默认布局内容）
        :param parent: 父窗口
        :param current_settings: 现有预警设置（可选）
        """
        super().__init__(title=title, content=content, parent=parent)
        self.linght_chart_window = parent
        self.current_settings = current_settings
        self.setFixedSize(420, 360)
        self.setResizeEnabled(False)
        self._clean_base_widgets()
        self._init_alert_ui()
        self._init_signals()
        self._load_current_settings()

    def _clean_base_widgets(self):
        """
        清理基类默认控件（不修改基类源码，仅在子类中移除无用控件）
        避免默认标题/内容标签与预警设置控件冲突
        """
        # 移除基类默认的 titleLabel 和 contentLabel
        if hasattr(self, 'titleLabel') and self.titleLabel:
            self.textLayout.removeWidget(self.titleLabel)
            self.titleLabel.hide()
            self.titleLabel.deleteLater()

        if hasattr(self, 'contentLabel') and self.contentLabel:
            self.textLayout.removeWidget(self.contentLabel)
            self.contentLabel.hide()
            self.contentLabel.deleteLater()

        # 移除基类默认的 yesButton 和 cancelButton（替换为自定义按钮）
        if hasattr(self, 'yesButton') and self.yesButton:
            self.buttonLayout.removeWidget(self.yesButton)
            self.yesButton.hide()
            self.yesButton.deleteLater()

        if hasattr(self, 'cancelButton') and self.cancelButton:
            self.buttonLayout.removeWidget(self.cancelButton)
            self.cancelButton.hide()
            self.cancelButton.deleteLater()

    def _init_alert_ui(self):
        """
        初始化预警设置UI（复用基类的 textLayout 和 vBoxLayout，无重复布局）
        """
        # 1. 核心设置卡片（承载所有预警功能，添加到基类的 textLayout 中）
        core_card = CardWidget(self)
        card_layout = QVBoxLayout(core_card)
        card_layout.setSpacing(18)
        card_layout.setContentsMargins(20, 20, 20, 20)

        # 1.1 预警启用开关
        self.enable_switch = SwitchButton("启用价格预警", core_card)
        card_layout.addWidget(self.enable_switch)

        # 1.2 预警类型选择
        type_layout = QHBoxLayout()
        type_label = BodyLabel("预警类型：", core_card)
        self.alert_combo = ComboBox(core_card)
        self.alert_combo.addItems(["双向预警", "上破预警", "下破预警"])
        type_layout.addWidget(type_label)
        type_layout.addStretch()
        type_layout.addWidget(self.alert_combo)
        card_layout.addLayout(type_layout)

        # 1.3 上破价格设置
        up_layout = QHBoxLayout()
        up_label = BodyLabel("上破价格：", core_card)
        self.up_spin = DoubleSpinBox(core_card)
        self.up_spin.setRange(0, 1000000)
        self.up_spin.setDecimals(4)
        self.up_spin.setFixedWidth(180)
        up_layout.addWidget(up_label)
        up_layout.addStretch()
        up_layout.addWidget(self.up_spin)
        card_layout.addLayout(up_layout)

        # 1.4 下破价格设置
        down_layout = QHBoxLayout()
        down_label = BodyLabel("下破价格：", core_card)
        self.down_spin = DoubleSpinBox(core_card)
        self.down_spin.setRange(0, 1000000)
        self.down_spin.setDecimals(4)
        self.down_spin.setFixedWidth(180)
        down_layout.addWidget(down_label)
        down_layout.addStretch()
        down_layout.addWidget(self.down_spin)
        card_layout.addLayout(down_layout)

        # 2. 复用基类的 textLayout，添加核心卡片（无新布局，避免冲突）
        self.textLayout.addWidget(core_card, 0, Qt.AlignTop)
        self.textLayout.setSpacing(20)
        self.textLayout.setContentsMargins(24, 24, 24, 24)

        # 3. 复用基类的 buttonGroup 和 buttonLayout，添加自定义按钮
        self.cancel_btn = PushButton("Cancel", self.buttonGroup)
        self.confirm_btn = PrimaryPushButton("OK", self.buttonGroup)
        self.confirm_btn.setIcon(FluentIcon.ACCEPT.icon())

        # 重新布局自定义按钮
        self.buttonLayout.setSpacing(12)
        self.buttonLayout.setContentsMargins(24, 24, 24, 24)
        self.buttonLayout.addStretch()
        self.buttonLayout.addWidget(self.cancel_btn)
        self.buttonLayout.addWidget(self.confirm_btn)

        # 4. 初始状态更新（禁用输入框）
        self._update_widget_status(self.enable_switch.isChecked())

    def _init_signals(self):
        """绑定信号槽（仅关联预警功能所需信号，不改动基类逻辑）"""
        # 启用开关状态变更
        self.enable_switch.checkedChanged.connect(self._update_widget_status)
        # 预警类型变更
        self.alert_combo.currentIndexChanged.connect(
            self._on_alert_type_changed)
        # 自定义按钮点击事件
        self.cancel_btn.clicked.connect(self.reject)
        self.confirm_btn.clicked.connect(self._on_confirm_clicked)

    def _load_current_settings(self):
        """加载现有设置（填充到控件中）"""
        # 启用状态
        self.enable_switch.setChecked(
            self.current_settings.get('enabled', False))
        # 预警类型
        type_map = {'both': 0, 'up': 1, 'down': 2}
        current_type = self.current_settings.get('alert_type', 'both')
        self.alert_combo.setCurrentIndex(type_map.get(current_type, 0))
        # 价格设置
        self.up_spin.setValue(self.current_settings.get('up_price', 0.0))
        self.down_spin.setValue(self.current_settings.get('down_price', 0.0))

    def _update_widget_status(self, is_enabled: bool):
        """更新控件启用状态（跟随总开关）"""
        self.alert_combo.setEnabled(is_enabled)
        self.up_spin.setEnabled(is_enabled)
        self.down_spin.setEnabled(is_enabled)

        # 同步更新预警类型对应的输入框状态
        if is_enabled:
            self._on_alert_type_changed(self.alert_combo.currentIndex())

    def _on_alert_type_changed(self, index: int):
        """预警类型变更处理（控制输入框可用性）"""
        if not self.enable_switch.isChecked():
            return

        # 0: 双向预警, 1: 上破预警, 2: 下破预警
        if index == 1:  # 上破预警
            self.up_spin.setEnabled(True)
            self.down_spin.setEnabled(False)
            self.down_spin.setValue(0.0)
        elif index == 2:  # 下破预警
            self.up_spin.setEnabled(False)
            self.up_spin.setValue(0.0)
            self.down_spin.setEnabled(True)
        else:  # 双向预警
            self.up_spin.setEnabled(True)
            self.down_spin.setEnabled(True)

    def _validate_input(self) -> bool:
        """验证输入合法性（简洁校验，只保留核心规则）"""
        if not self.enable_switch.isChecked():
            return True

        up_price = self.up_spin.value()
        down_price = self.down_spin.value()
        alert_index = self.alert_combo.currentIndex()

        # 上破预警校验
        if alert_index == 1 and up_price <= 0:
            self._show_info_bar("警告", "上破价格必须大于0！", "warning")
            return False

        # 下破预警校验
        if alert_index == 2 and down_price <= 0:
            self._show_info_bar("警告", "下破价格必须大于0！", "warning")
            return False

        # 双向预警校验
        if alert_index == 0 and up_price > 0 and down_price > 0 and up_price <= down_price:
            self._show_info_bar("警告", "上破价格必须大于下破价格！", "warning")
            return False

        return True

    def _get_current_settings(self) -> dict:
        """获取当前控件中的设置（组装为字典）"""
        type_map = {0: 'both', 1: 'up', 2: 'down'}
        return {
            'enabled': self.enable_switch.isChecked(),
            'alert_type': type_map.get(self.alert_combo.currentIndex(), 'both'),
            'up_price': self.up_spin.value(),
            'down_price': self.down_spin.value()
        }

    def _on_confirm_clicked(self):
        """确认按钮点击处理（校验→发射信号→关闭对话框）"""
        if not self._validate_input():
            return

        # 获取当前设置并发射信号
        current_settings = self._get_current_settings()
        self.alertSettingsChanged.emit(current_settings)

        # 显示成功提示
        self._show_info_bar("成功", "价格预警设置已保存！", "success")

        # 关闭对话框
        self.accept()

    def _show_info_bar(self, title: str, content: str, info_type: str):
        """
        正确使用自定义 InfoBar 类显示提示框
        :param title: 提示标题
        :param content: 提示内容
        :param info_type: 提示类型（success/warning/info/error）
        """
        # 配置默认参数（与自定义 InfoBar 类匹配）
        duration = 2000
        position = InfoBarPosition.TOP_RIGHT
        orient = Qt.Horizontal
        is_closable = True

        # 根据提示类型调用对应的 InfoBar 类方法
        if info_type == "success":
            InfoBar.success(
                title=title,
                content=content,
                orient=orient,
                isClosable=is_closable,
                duration=duration,
                position=position,
                parent=self
            )
        elif info_type == "warning":
            InfoBar.warning(
                title=title,
                content=content,
                orient=orient,
                isClosable=is_closable,
                duration=duration,
                position=position,
                parent=self
            )
        elif info_type == "error":
            InfoBar.error(
                title=title,
                content=content,
                orient=orient,
                isClosable=is_closable,
                duration=duration,
                position=position,
                parent=self
            )
        else:  # 默认 info 类型
            InfoBar.info(
                title=title,
                content=content,
                orient=orient,
                isClosable=is_closable,
                duration=duration,
                position=position,
                parent=self
            )


class CustomTitleBar(FluentTitleBar):
    """自定义标题栏"""

    def __init__(self, parent):
        super().__init__(parent)
        FluentStyleSheet.FLUENT_WINDOW.apply(self, Theme.DARK)
        self.iconLabel.setFixedSize(36, 36)

        self.avatar = TransparentToolButton(
            FluentIcon.CONSTRACT, self)
        self.avatar.setIconSize(QSize(18, 18))
        self.avatar.setFixedHeight(24)
        self.hBoxLayout.insertWidget(2, self.avatar, 0, Qt.AlignRight)
        self.avatar.clicked.connect(parent.setTheme)

    def setIcon(self, icon):
        self.iconLabel.setPixmap(QIcon(icon).pixmap(36, 36))


class MainWindow(FluentWindow):
    """主窗口"""

    def __init__(self, strategyes: list[Strategy], period_milliseconds: int = 1000):
        super().__init__()
        self.title_height = 36
        self.theme = Theme.LIGHT
        self.light_chart_window = LightChartWindow(
            self, strategyes, period_milliseconds)
        self.base_dir = strategyes[0]._base_dir
        self.initNavigation()
        self.initWindow()

    def initNavigation(self):
        self.setTitleBar(CustomTitleBar(self))
        self.addSubInterface(self.light_chart_window, FluentIcon.HOME, 'Home')
        self.setMicaEffectEnabled(False)
        self.navigationInterface.setAcrylicEnabled(False)
        self.navigationInterface.hide()

    def initWindow(self):
        self.resize(900, 700)
        self.widgetLayout.setContentsMargins(0, self.title_height, 0, 0)
        self.setTheme()
        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)

    def setTheme(self):
        self.theme = Theme.LIGHT if self.isdark else Theme.DARK
        setTheme(self.theme)
        self.light_chart_window.chart_window.setTheme()
        self._seticon()

    @property
    def isdark(self) -> bool:
        return self.theme == Theme.DARK

    def _seticon(self):
        if self.isdark:
            path = os.path.join(self.base_dir, "data", "minibt_dark.png")
        else:
            path = os.path.join(self.base_dir, "data", "minibt_light.png")

        if os.path.exists(path):
            icon = QIcon(path)
            self.titleBar.setIcon(icon)

    def closeEvent(self, e):
        self.light_chart_window.chart_window.cleanup()
        self.light_chart_window.close_api()
        return super().closeEvent(e)


class InfoWindow(QWidget):
    """账户信息窗口"""

    def __init__(self, parent: MainWindow = None):
        super().__init__(parent=parent)
        self.hBoxLayout = QHBoxLayout(self)
        self.setFixedHeight(40)
        self.text_label = CaptionLabel("test")
        label_font = QFont()
        label_font.setFamily('Microsoft YaHei')
        label_font.setPointSize(12)
        self.text_label.setFont(label_font)
        self.hBoxLayout.addWidget(self.text_label)
        self.hBoxLayout.addStretch(1)
        self.hBoxLayout.setContentsMargins(10, 0, 10, 0)
        self.hBoxLayout.setSpacing(10)

    def set_account_info(self, text: str = ""):
        self.text_label.setText(text)


class ContractTable(TableWidget):
    """合约表格"""

    def __init__(self, parent: LightChartWindow = None):
        super().__init__(parent)
        self.light_chart_window = parent
        self.contracts = parent.contract_dict
        self.setObjectName("StrategyTable")
        font = self.horizontalHeader().font()  # 表格格式
        font.setBold(True)
        self.horizontalHeader().setFont(font)  # 表头加粗
        self.adjustSize()
        self.verticalHeader().setVisible(True)
        self.setSelectionBehavior(
            QAbstractItemView.SelectRows)  # 设置不可选择单个单元格，只可选择一行。
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)  # 禁止编辑
        self.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)  # 铺满整个QTableWidget控件
        self.setSortingEnabled(True)  # 设置表头不可排序
        self.setBorderVisible(True)
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(['合约',])
        num = len(self.contracts)
        self.setRowCount(num)
        for i, contract in enumerate(self.contracts.keys()):
            item = QTableWidgetItem(contract)
            self.setItem(i, 0, item)
            if not i:
                self.light_chart_window.current_contract = contract
                self.setCurrentItem(item)
        self.current_row = 0

        self.cellDoubleClicked.connect(self.on_click_item)

    def on_click_item(self, row, column):
        """双击事件"""
        if row == self.current_row:
            return
        self.current_row = row
        contract = self.item(row, column).text()
        self.light_chart_window.current_contract = contract
        strategy = self.light_chart_window.strategyes[self.contracts[contract]]
        self.light_chart_window.replace_chart(strategy)


class SeparatorWidget(QWidget):
    """分隔线组件"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # 设置分隔线高度
        self.setFixedHeight(1)
        # 根据主题设置分隔线颜色
        self._color = QColor(0, 0, 0, 20)

    def paintEvent(self, e):
        """绘制分隔线"""
        painter = QPainter(self)
        painter.setPen(QPen(self._color, 1))
        # 绘制一条水平直线
        painter.drawLine(0, 0, self.width(), 0)


class LightChartWindow(QWidget):
    """整体图表窗口"""
    current_contract: str

    def __init__(self, parent: MainWindow = None, strategyes: list[Strategy] = None, period_milliseconds: int = 1000):
        super().__init__(parent=parent)
        self.period_milliseconds = period_milliseconds
        self.main_window = parent
        self.strategyes = strategyes
        self.price_scale_widthes: dict[str, int] = {}
        self.drawings = {}
        self.visible_range = {}
        self.setObjectName("LightChartWindow")
        self.vBoxLayout = QVBoxLayout(self)
        self.__initWidget()

    def __initWidget(self):
        """初始化组件和布局"""
        # 布局基础设置
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(0)

        # 1. 添加顶部信息栏
        self.info_window = InfoWindow(self)
        self.vBoxLayout.addWidget(self.info_window)

        # 2. 添加分隔线
        self.separator = SeparatorWidget(self)
        self.vBoxLayout.addWidget(self.separator)

        # 3. 添加水平分割窗口（策略窗口 + 表格）
        self.splitter = QSplitter(Qt.Horizontal, self)
        # ========== 设置QSplitter样式表，和SeparatorWidget视觉一致 ==========
        self.splitter.setStyleSheet("""
            QSplitter {
                background-color: transparent;  /* 透明背景，不影响整体布局 */
            }
            QSplitter::handle:horizontal {
                /* 水平分割线样式（和SeparatorWidget一致） */
                background-color: rgba(0, 0, 0, 20);  /* 颜色和SeparatorWidget完全一致 */
                width: 1px;  /* 宽度和SeparatorWidget高度一致 */
            }
            /* 鼠标悬停时的样式（可选，增加拖动辨识度） */
            QSplitter::handle:horizontal:hover {
                background-color: rgba(0, 0, 0, 50);  /* 悬停时略深，提示可拖动 */
                width: 2px;  /* 悬停时宽度稍大，更容易点击 */
            }
        """)

        self.contract_dict = {}
        self.price_alert = {}
        for strategy in self.strategyes:
            for k, v in strategy._btklinedataset.items():
                self.contract_dict[f"{v.symbol}_{v.cycle}"] = strategy._sid
                self.price_alert[v.symbol] = {}

        # 3.2 合约表格
        self.strategy_table = ContractTable(self)
        self.strategy_table.setMaximumWidth(300)  # 最大宽度300px
        self.strategy_table.setMinimumWidth(150)  # 最小宽度150px
        # 3.1 策略窗口
        self.chart_window = Chart(
            self, toolbox=True, strategy=self.strategyes[0])

        # 添加到分割窗口
        self.splitter.addWidget(self.strategy_table)
        self.splitter.addWidget(self.chart_window.get_webview())

        # 设置初始尺寸比例
        self.splitter.setSizes([220, 1800])

        # 添加到主布局，并设置拉伸因子让分割窗口填充剩余空间
        self.vBoxLayout.addWidget(self.splitter, stretch=1)

    def _safe_remove_splitter_widget(self, widget):
        """
        安全地从QSplitter中移除子组件（封装通用逻辑）
        :param widget: 要移除的子组件（QWidget子类）
        """
        if not widget or not self.splitter:
            return

        widget_index = self.splitter.indexOf(widget)
        if widget_index >= 0:
            target_widget = self.splitter.widget(widget_index)
            if target_widget == widget:
                widget.setParent(None)

    def _do_chart_replacement(self, strategy: Strategy):
        self.chart_window = Chart(
            self, toolbox=True, strategy=strategy, period_milliseconds=self.period_milliseconds)
        self.splitter.insertWidget(1, self.chart_window.get_webview())
        QTimer.singleShot(100, lambda: self._restore_splitter_sizes())

    def _restore_splitter_sizes(self):
        """延迟恢复splitter尺寸，避免布局冲突"""
        self.splitter.setSizes(self.current_sizes)
        self.splitter.update()
        QApplication.processEvents()

    def replace_chart(self, strategy: Strategy):
        QTimer.singleShot(100, lambda: self._start_chart_replacement(strategy))

    def _start_chart_replacement(self, strategy: Strategy):
        """开始图表替换流程"""
        self.current_sizes = self.splitter.sizes()
        old_chart = self.chart_window
        if old_chart:
            webview = old_chart.get_webview()
            self._safe_remove_splitter_widget(webview)
            old_chart.cleanup()
            webview.deleteLater()
        self.chart_window = None
        QTimer.singleShot(100, lambda: self._do_chart_replacement(strategy))

    def close_api(self):
        """关闭天勤API"""
        self.strategyes[0].api.close()


class CustomToolBox(ToolBox):
    def __init__(self, chart: Chart):
        self.run_script = chart.run_script
        self.id = chart.id
        self.drawings = {}
        self.chart = chart
        self.window = chart.light_chart_window
        self._save_under = self.window
        chart.win.handlers[f'save_drawings{self.id}'] = self._save_drawings
        self.run_script(f'{self.id}.createToolBox()')

    def load_drawings(self, tag: str):
        """
        优先从 LightChartWindow 加载画线，兜底从自身字典加载
        :param tag: 画线标签（如合约代码）
        """
        target_drawings = self.window.drawings.get(tag)
        if not target_drawings:
            target_drawings = self.drawings.get(tag)
        if not target_drawings:
            return
        self.run_script(
            f'if ({self.id}.toolBox) {self.id}.toolBox.loadDrawings({json.dumps(target_drawings)})'
        )

    def _save_drawings(self, drawings: str):
        """前端回调：保存画线到 自身字典 + 窗口字典"""
        if not self._save_under:
            return
        parsed_drawings = json.loads(drawings)
        tag = self._save_under.current_contract
        self.drawings[tag] = parsed_drawings
        self.window.drawings[tag] = parsed_drawings


class QuoteQTimer(QObject):
    """支持开盘/收盘状态自动切换的定时器管理类"""
    names: list[str] = ["monitor", "kline", "indicator", "account"]

    def __init__(self, chart: Chart):
        super().__init__()
        self.chart = chart
        self.qtimers: dict[str, QTimer] = OrderedDict()
        self.msecs: dict[str, int] = {}
        self.current_status = chart._is_update
        self.initqtimers()

    def initqtimers(self):
        """初始化定时器配置和实例"""
        self.msecs = dict(zip(self.names, [
            1000, 100, self.chart.period_milliseconds, self.chart.period_milliseconds
        ]))
        self.create_timers()

        # 初始化状态检测定时器（持续检测行情状态）
        self.status_check_timer = QTimer(self.chart.light_chart_window)
        self.status_check_timer.timeout.connect(self.start)
        self._switch_qtimer(self.current_status)
        self.status_check_timer.start(1000)

    def _create_timer(self, name: str):
        """创建单个定时器并绑定回调"""
        timer = QTimer(self.chart.light_chart_window)
        timer.timeout.connect(getattr(self.chart, f"{name}_loop"))
        self.qtimers[name] = timer

    def create_timers(self):
        """批量创建所有定时器"""
        for name in self.names:
            self._create_timer(name)

    def start(self):
        """启动"""
        if QThread.currentThread() != QApplication.instance().thread():
            QMetaObject.invokeMethod(self, "start", Qt.QueuedConnection)
            return
        status = self.chart.update_queue.any
        if status != self.current_status:
            self._switch_qtimer(status)

    def _switch_qtimer(self, status):
        if status:
            self.chart.update_queue.clear()
            self.start_quote()
        else:
            self.start_monitor()
        self.current_status = status

    def start_quote(self):
        """开盘模式：启动行情定时器，停止监视器"""
        # 停止monitor定时器
        self._stop_all_timers()
        # 启动kline/indicator/account定时器
        for name in ["kline", "indicator", "account"]:
            self._start_timer(self.qtimers[name], self.msecs[name])

    def start_monitor(self):
        """收盘模式：停止行情定时器，启动监视器"""
        # 停止kline/indicator/account定时器
        self._stop_all_timers()
        # 启动monitor定时器
        self._start_timer(self.qtimers["monitor"], self.msecs["monitor"])

    def _stop_all_timers(self):
        """批量停止定时器（增加排除项）"""
        if self.qtimers:
            for timer in self.qtimers.values():
                self._stop_timer(timer)

    def _start_timer(self, timer: QTimer, msec: int):
        """安全启动定时器（避免重复启动）"""
        if not timer.isActive():
            timer.start(msec)

    def _stop_timer(self, timer: QTimer):
        """安全停止定时器"""
        if timer.isActive():
            timer.stop()

    def stop(self):
        """资源清理"""
        # 3. 停止定时器运行
        if self.status_check_timer and self.status_check_timer.isActive():
            self.status_check_timer.stop()

        for timer in self.qtimers.values():
            if timer and timer.isActive():
                timer.stop()
        # 1. 先断开所有信号
        if self.status_check_timer:
            try:
                self.status_check_timer.timeout.disconnect(self.start)
            except:
                pass

        # 2. 停止所有定时器
        for name, timer in self.qtimers.items():
            if timer:
                try:
                    timer.timeout.disconnect(
                        getattr(self.chart, f"{name}_loop"))
                except:
                    pass

        QTimer.singleShot(100, lambda: self._final_cleanup())

    def _final_cleanup(self):
        """最终清理"""
        if self.status_check_timer:
            self.status_check_timer.deleteLater()
            self.status_check_timer = None

        for timer in self.qtimers.values():
            if timer:
                timer.deleteLater()
        self.qtimers.clear()
        self.msecs.clear()
        self.deleteLater()
        self.chart = None


class Chart(QtChart):
    """lightweight_charts QtChart"""
    toolbox: CustomToolBox
    position_horizontal_line: HorizontalLine
    chart_indicators: dict[str, dict[str, Line]]
    subcharts: dict[str, AbstractChart]

    def __init__(self, widget: LightChartWindow = None, inner_width: float = 1.0, inner_height: float = 1.0,
                 scale_candles_only: bool = False, toolbox: bool = False, strategy: Strategy = None, period_milliseconds: int = 1000):
        super().__init__(widget, inner_width, inner_height, scale_candles_only, toolbox)
        self.light_chart_window = widget
        self.period_milliseconds = max(period_milliseconds, 100)
        self.monitor_period = max(
            1, int(min(strategy._btklinedataset.cycles)/2-1))
        self.strategy = strategy
        self.chart_indicators = {}
        self.subcharts = {}
        self.signal_indicators = {}
        self.toolbox = None
        if toolbox:
            self.toolbox = CustomToolBox(self)
        self._new_bar_event = False
        self._saved_visible_range = None
        self._webview_loadfinished = False
        webview = self.get_webview()
        webview.page().loadFinished.connect(self._on_webview_loaded)
        webview.setContextMenuPolicy(Qt.CustomContextMenu)
        webview.customContextMenuRequested.connect(
            self._on_webview_custom_context_menu)
        self._init_chart_data()
        # self.events.click += self.on_chart_click
        # self.events.range_change += self.on_range_change

    # def on_chart_click(self, chart, time, price):
    #    ...

    # def on_range_change(self, chart, bars_before, bars_after):
    #     self._save_current_visible_range()

    def _on_webview_loaded(self, success: bool):
        """WebView加载完成回调（增加图表初始化延迟，避开时序差）"""
        if success:
            QTimer.singleShot(500, self.get_price_scale_width_async)
            self.qtimer = QuoteQTimer(self)

    def get_price_scale_width_async(self):
        """异步获取价格轴宽度"""
        def handle_result(result):
            if result is not None and result > 0:
                width = int(result)
                self.light_chart_window.price_scale_widthes[self.symbol] = width
            if self.symbol in self.light_chart_window.price_scale_widthes:
                width = self.light_chart_window.price_scale_widthes[
                    self.symbol]
            for _, chart in self.subcharts.items():
                self.set_price_scale_fixed_width(chart, width)
            self.set_only_last_chart_xaxis_visible()
            self.add_chart_separator_lines()
            self._restore_visible_range()
            self.events.search += self.on_search
            self._on_alert_settings_changed(self.price_alert, False)

        # 使用page().runJavaScript异步获取
        # script = f'{self.id}.chart.priceScale("right").width()'
        # 优化JS脚本：增加容错判断，避免图表实例未就绪时报错
        script = f'''
            (function() {{
                if (typeof {self.id} !== 'undefined' && {self.id}.chart && {self.id}.chart.priceScale) {{
                    return {self.id}.chart.priceScale("right").width();
                }}
                return null;
            }})();
        '''
        self.get_webview().page().runJavaScript(script, handle_result)
        self._webview_loadfinished = True

    def init_update(self) -> bool:
        count = 0
        is_update = False
        start_time = _time.time()
        while count < 100 and (_time.time() - start_time) < 1.0:
            is_update = self.strategy.wait_update(1)
            count += 1
            if is_update:
                break
        return is_update

    def _init_chart_data(self):
        """初始化图表"""
        self.update_queue = FixedSizeQueue(10, self.init_update())
        self._is_update = self.update_queue.any
        for i, (k, v) in enumerate(self.strategy._btklinedataset.items()):
            if self.light_chart_window.current_contract == f"{v.symbol}_{v.cycle}":
                dataset = v._dataset
                self.cycle = v.cycle
                self.current_index = i
                self.water_mark = v.watermark
                if v._light_chart_candles_down_color:
                    bear_color = v.bear_color
                else:
                    bear_color = 'rgba(200, 97, 100, 100)'
                if v._light_chart_candles_up_color:
                    bull_color = v.bull_color
                else:
                    bull_color = 'rgba(39, 157, 130, 100)'
                self.volume_multiple = v.volume_multiple
                self.price_tick = v.price_tick
                self.position = v.position
                self.account = v.account
                self.symbol = self.light_chart_window.current_contract

        self.kline = dataset.tq_object
        self.tick = dataset.tq_tick
        df = self.kline.copy()
        df['time'] = self.kline.datetime
        df = df[FILED.TALL]
        self.set(df, True)
        if self.water_mark is not None:
            self.water_mark = self.water_mark.vars
            self.set_watermark(**self.water_mark)
        self.candle_style(up_color=bull_color, down_color=bear_color)

        self.strategy()
        self.account_float_profit = self.account.float_profit
        self.light_chart_window.info_window.set_account_info(
            self.strategy._get_account_info())
        pos = self.position.pos
        price = 0.
        text = ""
        color = btcolors.red
        if pos:
            price = self.position.open_price_long if pos > 0 else self.position.open_price_short
            profit = self.position.float_profit
            text = f"{profit}"
            color = btcolors.red if pos > 0 else btcolors.green

        self.position_horizontal_line = self.horizontal_line(
            price, color=color, width=4, style='dashed', text=text)
        colors = get_colors()
        for k, v in self.strategy._btindicatordataset.items():
            if v.plot_id == self.current_index:
                plot_id, isplot, name, lines, _lines, ind_names, overlaps, \
                    categorys, indicators, doubles, _ind_plotinfo, span, _signal = v._get_plot_datas(
                        k)
                lineinfo = _ind_plotinfo.get('linestyle', {})
                signal_info: dict = _ind_plotinfo.get('signalstyle', {})
                indicator = v.pandas_object
                if doubles:
                    ind_dict = dict()
                    for j in range(2):
                        if any(isplot[j]):
                            cache_dict = {}
                            if overlaps[j]:
                                chart = self
                            else:
                                chart = self.create_subchart(
                                    'bottom', sync=True)
                                self.setSubChartTheme(chart, name[j])
                                self.subcharts.update({name[j]: chart})
                            for i, plot in enumerate(isplot[j]):
                                if plot:
                                    col = _lines[j][i]
                                    info = lineinfo[col]
                                    color = info.get(
                                        "line_color", None)
                                    if not color:
                                        color = next(colors)
                                    style = info.get('line_dash', 'solid')
                                    if style != "vbar" and style not in util.LINE_STYLE.__args__:
                                        style = 'solid'
                                    width = info.get("line_width", 2)
                                    price_line = info.get("price_line", False)
                                    price_label = info.get(
                                        "price_label", False)

                                    if style == "vbar":
                                        line = chart.create_histogram(
                                            name=col, color=color, price_line=price_line, price_label=price_label)
                                        line.set(
                                            pd.concat([df["time"], indicator[col]], axis=1))

                                    else:
                                        line = partial(chart.create_line,
                                                       name=col, color=color, style=style, width=width, price_line=price_line, price_label=price_label)
                                        line.vdata = pd.concat(
                                            [df["time"], indicator[col]], axis=1)
                                    cache_dict[col] = line
                            else:
                                # vbar指标在前其它指标线在后，否则vbar柱体会挡住其它指标线
                                if cache_dict:
                                    new_dict = {}
                                    for _k, _v in cache_dict.items():
                                        if hasattr(_v, "vdata"):
                                            data = _v.vdata
                                            _v = _v()
                                            _v.set(data)
                                        new_dict.update({_k: _v})
                                    ind_dict.update(new_dict)
                    if ind_dict:
                        self.chart_indicators.update({name[0]: ind_dict})
                else:
                    if any(isplot):
                        ind_dict = dict()
                        is_candles = v.iscandles
                        if not v.isMDim:
                            indicator = pd.DataFrame({_lines[0]: indicator})

                        if is_candles:
                            if set(indicator.columns) != set(FILED.OHLC):
                                print(f"蜡烛图指标列名必须为{FILED.OHLC}")
                                continue
                            chart = self.create_subchart(
                                'bottom', sync=True)
                            self.setSubChartTheme(chart, name)
                            self.subcharts.update({name: chart})
                            candles_df = indicator.copy()
                            candles_df["time"] = df["time"]
                            candles_df = candles_df[FILED.TOHLC]
                            chart.set(candles_df)
                        else:
                            if overlaps:
                                chart = self
                            else:
                                chart = self.create_subchart(
                                    'bottom', sync=True)
                                self.setSubChartTheme(chart, name)
                                self.subcharts.update({name: chart})

                            for i, plot in enumerate(isplot):
                                if plot:
                                    col = _lines[i]
                                    info = lineinfo[col]
                                    color = info.get(
                                        "line_color", None)
                                    if not color:
                                        color = next(colors)
                                    style = info.get('line_dash', 'solid')
                                    if style != "vbar" and style not in util.LINE_STYLE.__args__:
                                        style = 'solid'
                                    width = info.get("line_width", 2)
                                    price_line = info.get("price_line", False)
                                    price_label = info.get(
                                        "price_label", False)
                                    if style == "vbar":
                                        line = chart.create_histogram(
                                            name=col, color=color, price_line=price_line, price_label=price_label)
                                        line.set(
                                            pd.concat([df["time"], indicator[col]], axis=1))
                                    else:
                                        line = partial(chart.create_line,
                                                       name=col, color=color, style=style, width=width, price_line=price_line, price_label=price_label)
                                        line.vdata = pd.concat(
                                            [df["time"], indicator[col]], axis=1)
                                    ind_dict[col] = line
                            else:
                                if ind_dict:
                                    new_dict = {}
                                    for _k, _v in ind_dict.items():
                                        if hasattr(_v, "vdata"):
                                            data = _v.vdata
                                            _v = _v()
                                            _v.set(data)
                                        new_dict.update({_k: _v})
                                    ind_dict = new_dict
                        if ind_dict:
                            self.chart_indicators.update({name: ind_dict})
                # 交易信号：
                if signal_info:
                    signal_dict = {}
                    last_signal_dict = {}
                    all_markers = []

                    for signalname, signal_config in signal_info.items():
                        signalkey, signalcolor, signalmarker, signaloverlap, signalshow, signalsize, signallabel = list(
                            signal_config.values())
                        signal_series = indicator[signalname]
                        is_buy_signal = any([name in signalname for name in [
                                            "long", "exitshort"]]) or "low" in signalkey.lower()
                        signal_points = signal_series[signal_series > 0]
                        if is_buy_signal:
                            position = 'below'
                            shape = signalmarker if signalmarker in util.MARKER_SHAPE.__args__ else 'arrow_up'
                            color = signalcolor if signalcolor else btcolors.red
                        else:
                            position = 'above'
                            shape = signalmarker if signalmarker in util.MARKER_SHAPE.__args__ else 'arrow_down'
                            color = signalcolor if signalcolor else btcolors.green
                        text = signallabel.get("text", "") if isinstance(
                            signallabel, dict) else ""
                        signalconfig = dict(
                            position=position, shape=shape, color=color, text=text)

                        for idx in signal_points.index:
                            time_value = df.iloc[idx]['time']
                            all_markers.append(
                                {"time": time_value, **signalconfig})
                        else:
                            if not signal_series.empty and signal_series.iloc[-1] > 0:
                                last_signal_dict[signalname] = self._single_datetime_format(
                                    df.iloc[-1]['time'])
                        signal_dict.update({signalname: signalconfig})
                    if all_markers:
                        all_markers.sort(key=lambda x: x["time"])
                        self.marker_list(all_markers)
                        if last_signal_dict:
                            count = 0
                            for markername in reversed(self.markers):
                                marker = self.markers[markername]
                                for lsd, lsv in last_signal_dict.items():
                                    if marker["time"] == lsv:
                                        signal_dict[lsd]["signal"] = markername
                                        count += 1
                                if count == len(last_signal_dict):
                                    break

                    self.signal_indicators.update({v.sname: signal_dict})
        self.setChartTheme()
        self._resizes()
        if self.toolbox and hasattr(self, 'symbol'):
            self.toolbox.load_drawings(tag=self.symbol)

    def monitor_loop(self):
        try:
            self.update_queue.add(
                self.strategy.wait_update(1))
        except Exception as e:
            print(f"监视器更新异常：{e}")

    def kline_loop(self):
        """行情更新函数"""
        try:
            self.update_queue.add(self.strategy.wait_update(1))
            self._is_update = self.update_queue.any
            if self._is_update:
                self.kline_update()
        except Exception as e:
            if "which occurs before the last bar time" in str(e):
                print(f"K线更新异常：时间戳乱序，已跳过 -> {e}")
                # 可选择清空队列或重置图表时间戳
                self.update_queue.clear()
                self.update_queue.add(self._is_update)
            else:
                print(f"K线更新异常：{e}")

    def account_loop(self):
        """账户更新函数"""
        try:
            if self._is_update:
                self.account_update()
        except Exception as e:
            print(f"账户更新异常：{e}")

    def indicator_loop(self):
        """循环执行指标计算（不依赖K线更新，独立循环）"""
        try:
            if self._is_update:
                current_kline_time = self.kline.iloc[-1].copy()["datetime"]
                self.strategy()
                self.indicator_update(current_kline_time)
        except Exception as e:
            print(f"指标更新异常：{e}")

    def is_changing(self, obj: Union[Candlestick, Line], ns) -> int:
        """判断是否更新,获取最新时间与图表最后更新时间的差转化为需要更新数据的K线数量"""
        return int((ns*1e-9-obj._last_bar["time"])/self.cycle)

    def is_key_changing(self, chart_obj: Union[Candlestick, Line], obj: pd.DataFrame, key: str = "close") -> bool:
        return chart_obj._last_bar[key] != obj[key]

    def kline_update(self) -> None:
        """K线更新函数"""
        latest_tick_time = self.kline.iloc[-1].copy()["datetime"]
        if latest_tick_time < self._last_bar["time"]:
            return
        chang = self.is_changing(
            self, latest_tick_time)
        if chang:
            count = -chang-1
            for i in range(count, 0):
                if i == count:
                    series = self.kline.iloc[i].copy()[FILED.DCV]
                    series.index = FILED.TPV
                    self.update_from_tick(series)
                else:
                    sereis = self.kline.iloc[i].copy()[FILED.ALL]
                    sereis.index = FILED.TALL
                    self.update(sereis)
        else:
            series = self.kline.iloc[-1].copy()[FILED.DCV]
            series.index = FILED.TPV
            self.update_from_tick(series)

    def account_update(self):
        pos = self.position.pos
        price = 0.
        text = ""
        color = btcolors.red
        if pos:
            price = self.position.open_price_long if pos > 0 else self.position.open_price_short
            profit = self.position.float_profit
            text = f"{profit}"
            color = btcolors.red if pos > 0 else btcolors.green
            if self.position_horizontal_line.price != price:
                self.position_horizontal_line.update(price)
            self.position_horizontal_line.options(
                color=color, style='dashed', text=text)

        if price == 0. and self.position_horizontal_line.price != price:
            self.position_horizontal_line.update(price)
            self.position_horizontal_line.options(
                color=color, style='dashed', text=text)
        if self.account.float_profit or self.account_float_profit:
            self.light_chart_window.info_window.set_account_info(
                self.strategy._get_account_info())
            self.account_float_profit = self.account.float_profit

    def indicator_update(self, kline_time):
        """指标更新"""
        ischang = False
        datetime = self.kline.datetime.copy()
        for k, v in self.strategy._btindicatordataset.items():
            sname = v.sname
            if v.plot_id == self.current_index and (sname in self.chart_indicators or sname in self.subcharts):
                if v.iscandles:
                    chart = self.subcharts[sname]
                    if not ischang:
                        chang = self.is_changing(chart, kline_time)
                        ischang = True
                    if chang != 0:
                        count = -chang-1
                        for i in range(count, 0):
                            if i == count:
                                series = pd.Series(
                                    [datetime.iloc[i], v.iloc[i][3]], index=FILED.TP)
                                chart.update_from_tick(series)
                            else:
                                series = pd.Series(
                                    [datetime.iloc[i], *v.iloc[i].values], index=FILED.TOHLC)
                                chart.update(series)
                    else:
                        series = pd.Series(
                            [kline_time, v.iloc[-1][3]], index=FILED.TP)
                        chart.update_from_tick(series)

                else:
                    lines = self.chart_indicators[sname]
                    if v.isMDim:
                        ind = v
                    else:
                        ind = pd.DataFrame({v.lines[0]: v.values})
                    for name in v.lines:
                        if name in lines:
                            line = lines[name]
                            if not ischang:
                                chang = self.is_changing(line, kline_time)
                                ischang = True
                            values = ind[name].values
                            count = -chang-1
                            for j in range(count, 0):
                                series = pd.Series(
                                    [datetime.iloc[j], values[j]], index=["time", name])
                                line.update(series)
                if sname in self.signal_indicators:
                    signal: dict[str, dict] = self.signal_indicators[sname]
                    for sk, sv in signal.items():
                        if chang:
                            svalue = v[sk].values[-2]
                            last_signal = sv.pop("signal", None)
                            if svalue > 0:
                                if last_signal is None:
                                    last_signal = self.marker(
                                        datetime.iloc[-2], **sv)
                            else:
                                if last_signal is not None:
                                    self.remove_marker(last_signal)
                        else:
                            svalue = v[sk].values[-1]
                            last_signal = sv.pop("signal", None)
                            if svalue > 0:
                                if last_signal is None:
                                    last_signal = self.marker(kline_time, **sv)
                                self.signal_indicators[sname][sk]["signal"] = last_signal
                            else:
                                if last_signal is not None:
                                    self.remove_marker(last_signal)

    def set_watermark(self, text: str, font_size: int = 44, dark: bool = None):
        """设置水印"""
        if dark is None:
            dark = self.light_chart_window.main_window.isdark
        color: str = 'rgba(180, 180, 200, 0.3)' if dark else 'rgba(75, 75, 55, 0.3)'
        self.watermark(text, font_size, color)

    def sub_legend_params(self, name, dark):
        """指标参数显示"""
        return dict(text=name, color='rgb(249, 249, 249)' if dark else 'rgb(6, 6, 6)', lines=True, font_size=14, color_based_on_candle=True)

    def _resizes(self):
        """指标窗口高度设置,主图占3,副图占1"""
        num_sub_chart = len(self.subcharts)
        if num_sub_chart == 0:
            self.resize(1, 1)
            return
        num = round(1./(3+num_sub_chart), 4)
        self.resize(1., 1.-num_sub_chart*num)
        for _, subchart in self.subcharts.items():
            subchart.resize(1., num)

    def setTheme(self):
        """设置所有chart的样式"""
        charts = [self, *self.subcharts.values()]
        for chart in charts:
            self.setChartTheme(chart)
        if self.water_mark:
            self.set_watermark(**self.water_mark)
        if self._webview_loadfinished:
            self.add_chart_separator_lines()

    def setChartTheme(self, chart: AbstractChart = None):
        """设置对应chart的样式"""
        if chart is None:
            chart = self
        dark = self.light_chart_window.main_window.isdark
        if dark:
            chart.layout(background_color='rgb(6, 6, 6)', text_color='rgb(249, 249, 249)', font_size=14,
                         font_family='Microsoft YaHei')  # 'Helvetica')
            chart.grid(color="rgb(26, 26, 26)")
            chart.legend(visible=True, font_size=14,
                         color='rgb(249, 249, 249)')
        else:
            chart.layout(background_color='rgb(249, 249, 249)', text_color='rgb(6, 6, 6)', font_size=14,
                         font_family='Microsoft YaHei')  # 'Helvetica')
            chart.grid(color="rgb(229, 229, 229)")
            chart.legend(visible=True, font_size=14,
                         color='rgb(6, 6, 6)')

    def setSubChartTheme(self, chart: AbstractChart = None, text: str = ""):
        """设置对应子图的样式"""
        dark = self.light_chart_window.main_window.isdark
        if dark:
            chart.layout(background_color='rgb(6, 6, 6)', text_color='rgb(249, 249, 249)', font_size=14,
                         font_family='Microsoft YaHei')  # 'Helvetica')
            chart.grid(color="rgb(26, 26, 26)")
            chart.legend(True, **self.sub_legend_params(text, dark))
        else:
            chart.layout(background_color='rgb(249, 249, 249)', text_color='rgb(6, 6, 6)', font_size=14,
                         font_family='Microsoft YaHei')  # 'Helvetica')
            chart.grid(color="rgb(229, 229, 229)")
            chart.legend(True, **self.sub_legend_params(text, dark))

    def _set_price_scale_fixed_width(self, chart: AbstractChart, target_width: int = None):
        """
        固定副图价格轴宽度，自动同步主图价格轴宽度（优先获取主图实际宽度，兜底使用默认值）
        :param main_chart: 主图实例（AbstractChart类型），用于获取主图价格轴宽度
        :param fixed_width: 可选参数，手动指定宽度；若为None，自动同步主图宽度
        :return: 无
        """
        chart.run_script(f'''
            // 方案1：省略变量声明，直接链式调用（推荐，最简洁，无变量冲突）
            {chart.id}.chart.priceScale("right").applyOptions({{
                minimumWidth: {target_width},  // 最小宽度=主图宽度，防止宽度缩小
                width: {target_width} ,         // 固定宽度=主图宽度，强制统一
                autoScale: false
            }});
        ''')

    def set_price_scale_fixed_width(self, chart: AbstractChart, target_width: int = None):
        """固定副图价格轴宽度（优化容错与性能，避免无效执行）"""
        # 1. 兜底值设置，避免target_width为None/负数
        target_width = target_width if (
            target_width is not None and target_width > 0) else 80

        # 2. 容错：确保chart有效且有id属性
        if not chart or not hasattr(chart, 'id'):
            return

        # 3. 优化JS脚本：增加容错，避免执行失败
        script = f'''
            try {{
                var targetChart = {chart.id};
                if (targetChart && targetChart.chart && targetChart.chart.priceScale) {{
                    var priceScale = targetChart.chart.priceScale("right");
                    priceScale.applyOptions({{
                        minimumWidth: {target_width},
                        width: {target_width},
                        autoScale: false
                    }});
                }}
            }} catch (e) {{
                console.error("设置副图价格轴宽度失败：", e);
            }}
        '''
        chart.run_script(script)

    def set_only_last_chart_xaxis_visible(self):
        """
        遍历所有主图+副图，仅最后一个图表显示X轴时间，其余隐藏X轴
        """
        # 1. 收集所有图表：主图 + 所有副图
        all_charts = [self]  # 主图
        all_charts.extend(self.subcharts.values())  # 所有副图

        if not all_charts:
            return

        # 2. 遍历所有图表，仅最后一个显示X轴
        for idx, chart in enumerate(all_charts):
            # 仅最后一个图表显示X轴，其余隐藏
            is_visible = (idx == len(all_charts) - 1)
            self._set_chart_xaxis_visible(chart, is_visible)

    def _set_chart_xaxis_visible(self, chart: AbstractChart, visible: bool):
        """
        控制单个图表的X轴显示/隐藏（修正lightweight-charts API调用方式）
        :param chart: 目标图表
        :param visible: True=显示X轴，False=隐藏X轴
        """
        chart.run_script(f'''
            try {{
                var targetChart = {chart.id};
                if (targetChart && targetChart.chart && targetChart.chart.timeScale) {{
                    // 修正：X轴配置是timeScale的visible属性，不是layout的timeScaleVisible
                    targetChart.chart.timeScale().applyOptions({{
                        visible: {str(visible).lower()}  // 转成JS布尔值（true/false）
                    }});
                }}
            }} catch (e) {{
                console.error("设置图表X轴显示状态失败：", e);
            }}
        ''')

    def add_chart_separator_lines(self):
        """
        通过lightweight-charts的容器结构添加分隔线
        """
        if not self.subcharts:
            return
        dark_theme = self.light_chart_window.main_window.isdark
        border_color = "rgba(180, 180, 180, 0.6)" if dark_theme else "rgba(80, 80, 80, 0.4)"

        # 构建一次性执行的JavaScript脚本
        script = f'''
        (function() {{
            try {{
                console.log("开始添加图表分隔线");
                
                // 查找所有lightweight-charts容器
                var chartContainers = document.querySelectorAll('.tv-lightweight-charts');
                console.log("找到图表容器数量:", chartContainers.length);
                
                if (chartContainers.length === 0) {{
                    console.warn("未找到任何lightweight-charts容器");
                    return;
                }}
                
                // 为每个图表容器添加分隔线（除了第一个）
                for (var i = 1; i < chartContainers.length; i++) {{
                    var container = chartContainers[i];
                    var separatorId = 'chart_separator_' + i;
                    
                    // 移除已存在的分隔线
                    var existingSeparator = document.getElementById(separatorId);
                    if (existingSeparator) {{
                        existingSeparator.remove();
                    }}
                    
                    // 创建新的分隔线
                    var separator = document.createElement('div');
                    separator.id = separatorId;
                    separator.style.cssText = `
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        height: 1px;
                        background-color: {border_color};
                        z-index: 1000;
                        pointer-events: none;
                    `;
                    
                    // 确保容器有相对定位
                    container.style.position = 'relative';
                    container.appendChild(separator);
                    
                    console.log("为图表容器", i, "添加分隔线成功");
                }}
                
                console.log("全部分隔线添加完成");
                
            }} catch (error) {{
                console.error("添加分隔线时出错:", error);
            }}
        }})();
        '''
        self.run_script(script)

    def _on_webview_custom_context_menu(self, pos):
        """
        自定义 WebView 右键菜单槽函数（添加图标 + 关于弹窗，适配自定义 Dialog）
        """
        webview = self.get_webview()
        custom_menu = RoundMenu("", webview)

        # 构建菜单动作 + 匹配 Fluent 图标
        action_refresh = Action("适应窗口", parent=custom_menu)
        action_refresh.setIcon(FluentIcon.FIT_PAGE.icon())  # 适配窗口图标

        action_restore_range = Action("恢复窗口", parent=custom_menu)
        action_restore_range.setIcon(
            FluentIcon.BACK_TO_WINDOW.icon())  # 恢复窗口图标

        # 新增：显示最新300根K线（优化名称，用户可清晰知晓功能）
        action_show_latest_kline = Action("最新K线", parent=custom_menu)
        action_show_latest_kline.setIcon(
            FluentIcon.SYNC.icon())  # 同步/刷新最新数据图标，贴合功能
        action_show_latest_kline.setToolTip(
            "快速切换到最新300根K线视图")  # 可选：添加 tooltip 提示

        action_clear = Action("清空画线", parent=custom_menu)
        action_clear.setIcon(FluentIcon.BROOM.icon())  # 清空/清理图标

        action_alert = Action("价格预警设置", parent=custom_menu)
        action_alert.setIcon(FluentIcon.MESSAGE.icon())  # 预警消息图标

        action_alert_stats = Action("清除预警", parent=custom_menu)
        action_alert_stats.setIcon(FluentIcon.DELETE.icon())  # 清除/删除图标

        action_about = Action("关于", parent=custom_menu)
        action_about.setIcon(FluentIcon.INFO.icon())  # 关于信息图标

        # 绑定槽函数
        action_refresh.triggered.connect(self._fit_chart)
        action_restore_range.triggered.connect(self._restore_visible_range)
        action_show_latest_kline.triggered.connect(
            self._switch_to_latest_300_kline)
        custom_menu.addAction(action_show_latest_kline)
        action_clear.triggered.connect(self._clear_all_drawings)
        action_alert.triggered.connect(self._show_price_alert_dialog)
        action_alert_stats.triggered.connect(self._reset_price_alert)
        action_about.triggered.connect(self._show_about_dialog)  # 绑定关于弹窗

        # 根据状态启用/禁用菜单
        action_restore_range.setEnabled(self._saved_visible_range is not None)
        action_clear.setEnabled(
            self.symbol in self.light_chart_window.drawings)
        action_alert_stats.setEnabled(
            self.price_alert.get('enabled', False) and
            (self.price_alert.get('up_price', 0) > 0 or
             self.price_alert.get('down_price', 0) > 0)
        )

        # 组装菜单
        custom_menu.addAction(action_refresh)
        custom_menu.addAction(action_restore_range)
        custom_menu.addSeparator()
        custom_menu.addAction(action_clear)
        custom_menu.addSeparator()
        custom_menu.addAction(action_alert)
        custom_menu.addAction(action_alert_stats)
        custom_menu.addSeparator()
        custom_menu.addAction(action_about)

        # 显示菜单
        custom_menu.exec_(webview.mapToGlobal(pos))

    def _get_latest_minibt_version(self) -> str:
        """从PyPI获取minibt最新版本号，失败则返回本地默认版本"""
        default_version = "v1.1.9"
        try:
            import requests
            import json
            # PyPI的JSON接口，直接返回包的最新信息
            url = "https://pypi.org/pypi/minibt/json"
            # 设置超时，避免卡界面
            response = requests.get(url, timeout=5)
            response.raise_for_status()  # 捕获HTTP错误（如404、500）

            # 解析JSON获取最新版本号
            data = json.loads(response.text)
            latest_version = data["info"]["version"]
            return f"v{latest_version}"  # 格式化为 vx.x.x

        except requests.exceptions.RequestException as e:
            # 网络错误（超时、断网、接口不可用）
            print(f"获取最新版本失败（网络问题）：{e}")
            return default_version
        except (KeyError, json.JSONDecodeError) as e:
            # 接口格式变化/解析错误
            print(f"解析版本信息失败：{e}")
            return default_version

    def _show_about_dialog(self):
        """显示“关于”弹窗（适配自定义 Dialog，显示关闭按钮，可正常退出）"""
        # 步骤 1：初始化自定义 Dialog（传入标题和空内容，避免默认文本干扰）
        about_dialog = Dialog("关于 MiniBt", "", parent=self.light_chart_window)
        about_dialog.setFixedSize(450, 420)  # 调整高度，适配内容+按钮组，避免挤压

        # 步骤 2：清理自定义 Dialog 的默认控件（不修改原码，仅隐藏冗余元素）
        self._clean_about_dialog_default_widgets(about_dialog)
        # 步骤 3：优化原有按钮组（保留并修改文本，符合“关闭”需求）
        self._optimize_dialog_default_buttons(about_dialog)

        # 步骤 4：创建内容容器，直接挂载到自定义 Dialog 的 vBoxLayout
        content_container = QWidget(about_dialog)
        main_layout = QVBoxLayout(content_container)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(24, 24, 24, 20)

        # 步骤 5：添加 Fluent 风格内容（与需求一致，分卡片展示信息）
        # 1. 标题卡片（版本、许可证）
        title_card = CardWidget(content_container)
        title_layout = QVBoxLayout(title_card)
        title_layout.setContentsMargins(20, 16, 20, 16)

        app_title = TitleLabel("MiniBt", title_card)
        latest_version = self._get_latest_minibt_version()
        version_label = BodyLabel(f"版本: {latest_version}", title_card)

        title_layout.addWidget(app_title)
        title_layout.addWidget(version_label)
        main_layout.addWidget(title_card)

        # 2. 链接信息卡片（仓库、教程、邮箱，支持点击打开浏览器）
        link_card = CardWidget(content_container)
        link_layout = QVBoxLayout(link_card)
        link_layout.setContentsMargins(20, 16, 20, 16)
        link_layout.setSpacing(12)

        # GitHub 仓库
        github_link = HyperlinkLabel(QUrl("https://github.com/MiniBtMaster/minibt"),
                                     "GitHub 仓库", link_card)
        link_layout.addWidget(github_link)

        # PyPI 仓库
        pypi_link = HyperlinkLabel(QUrl("https://pypi.org/project/minibt/"),
                                   "PyPI 仓库", link_card)
        link_layout.addWidget(pypi_link)

        # 项目教程
        tutorial_link = HyperlinkLabel(QUrl("https://www.minibt.cn"),
                                       "项目教程", link_card)
        link_layout.addWidget(tutorial_link)

        # 联系邮箱
        email_label = BodyLabel("联系邮箱: 407841129@qq.com", link_card)
        link_layout.addWidget(email_label)

        main_layout.addWidget(link_card)

        # 步骤 6：核心适配：将内容容器添加到自定义 Dialog 的 vBoxLayout
        # 插入到默认 textLayout 之后、buttonGroup 之前，【不再隐藏按钮组】
        about_dialog.vBoxLayout.insertWidget(
            1, content_container, 1, Qt.AlignTop)
        # 注释/删除这行代码：不再隐藏按钮组，保留优化后的关闭按钮
        # about_dialog.buttonGroup.hide()  # 这是导致按钮消失的核心原因

        # 步骤 7：显示对话框
        about_dialog.exec_()

    def _switch_to_latest_300_kline(self,):
        """
        新增：切换到最新300根K线视图（核心功能实现）
        """
        from_ts = pd.to_datetime(
            self.kline.iloc[-300].copy().datetime).timestamp()
        to_ts = pd.to_datetime(self.kline.iloc[-1].copy().datetime).timestamp()
        self.run_script(f'''
        {self.id}.chart.timeScale().setVisibleRange({{
            from: {from_ts},
            to: {to_ts}
        }})
        ''')

    def _clean_about_dialog_default_widgets(self, dialog):
        """
        清理自定义 Dialog 的默认冗余控件（不修改原码，仅临时隐藏）
        避免默认标题/内容标签与自定义内容重叠
        """
        # 隐藏默认标题标签（windowTitleLabel 和 titleLabel）
        if hasattr(dialog, 'windowTitleLabel') and dialog.windowTitleLabel:
            dialog.windowTitleLabel.hide()
        if hasattr(dialog, 'titleLabel') and dialog.titleLabel:
            dialog.titleLabel.hide()

        # 隐藏默认内容标签（contentLabel）
        if hasattr(dialog, 'contentLabel') and dialog.contentLabel:
            dialog.contentLabel.hide()

        # 清理默认 textLayout 的间距，避免影响自定义内容布局
        if hasattr(dialog, 'textLayout'):
            dialog.textLayout.setSpacing(0)
            dialog.textLayout.setContentsMargins(0, 0, 0, 0)

    def _optimize_dialog_default_buttons(self, dialog):
        """
        优化自定义 Dialog 的默认按钮组（保留功能，修改文本为“关闭”，符合需求）
        """
        # 1. 保留按钮组（不再隐藏），调整按钮文本
        if hasattr(dialog, 'yesButton') and dialog.yesButton:
            dialog.yesButton.setText("关闭")  # 将原“OK”改为“关闭”
            dialog.yesButton.setIcon(FluentIcon.CLOSE.icon())  # 添加关闭图标，更直观
            dialog.yesButton.adjustSize()  # 自适应文本尺寸

        if hasattr(dialog, 'cancelButton') and dialog.cancelButton:
            # 隐藏 Cancel 按钮（仅保留一个“关闭”按钮，更简洁）
            # 若需保留“取消”，可修改文本为“取消”并保留显示
            dialog.cancelButton.hide()

        # 2. 确保按钮组高度适配，不挤压内容
        if hasattr(dialog, 'buttonGroup') and dialog.buttonGroup:
            dialog.buttonGroup.setFixedHeight(81)  # 保持原有高度，适配布局

    def _fit_chart(self):
        """适应窗口：将所有K线纳入可视范围，并记录之前的范围"""
        self._save_current_visible_range()
        self.fit()

    def _save_current_visible_range(self):
        """
        修复：通过异步回调获取当前可视范围
        """
        def handle_range_result(result):
            """处理JS返回的结果"""
            try:
                if result is not None and isinstance(result, str):
                    from_ts, to_ts = result.split(',')
                    self._saved_visible_range = (float(from_ts), float(to_ts))
                    self.light_chart_window.visible_range[self.symbol] = self._saved_visible_range
                else:
                    self._saved_visible_range = None
            except Exception as e:
                self._saved_visible_range = None

        # 使用page().runJavaScript获取结果
        get_range_script = f'''
            (function() {{
                try {{
                    const chart = {self.id};
                    if (!chart || !chart.chart) {{
                        console.error("图表实例未找到");
                        return null;
                    }}
                    
                    const timeScale = chart.chart.timeScale();
                    if (!timeScale) {{
                        console.error("timeScale未找到");
                        return null;
                    }}
                    
                    const visibleRange = timeScale.getVisibleRange();
                    if (!visibleRange) {{
                        console.error("无法获取可视范围");
                        return null;
                    }}
                    
                    console.log("可视范围:", visibleRange);
                    return visibleRange.from + "," + visibleRange.to;
                    
                }} catch (error) {{
                    console.error("获取可视范围时出错:", error);
                    return null;
                }}
            }})();
        '''
        webview = self.get_webview()
        if webview and webview.page():
            webview.page().runJavaScript(get_range_script, handle_range_result)
        else:
            self._saved_visible_range = None

    def _restore_visible_range(self):
        """
        核心方法：恢复到 fit() 前保存的可视范围（右键菜单「恢复窗口」绑定此方法）
        """
        if not self._saved_visible_range:
            self._saved_visible_range = self.light_chart_window.visible_range.get(
                self.symbol, None)
        if not self._saved_visible_range:
            return
        from_ts, to_ts = self._saved_visible_range
        self.run_script(f'''
        {self.id}.chart.timeScale().setVisibleRange({{
            from: {from_ts},
            to: {to_ts}
        }})
        ''')

    def _clear_all_drawings(self):
        """清空所有画线（基于CustomToolBox的drawings数据）"""
        if not self.toolbox:
            return
        self.run_script(
            f'if ({self.id}.toolBox) {self.id}.toolBox.clearDrawings()')
        current_tag = self.light_chart_window.current_contract
        if current_tag in self.toolbox.drawings:
            del self.toolbox.drawings[current_tag]
        if current_tag in self.light_chart_window.drawings:
            del self.light_chart_window.drawings[current_tag]

    # 事件
    def _show_price_alert_dialog(self):
        """显示价格预警设置对话框 - 使用新版对话框"""
        # 创建对话框
        dialog = PriceAlertSettingDialog(
            "价格预警设置",
            "",
            self.light_chart_window,
            self.price_alert

        )
        # 连接信号
        dialog.alertSettingsChanged.connect(self._on_alert_settings_changed)
        # 显示对话框
        if dialog.exec_():
            ...

    @property
    def price_alert(self) -> dict:
        if self.symbol not in self.light_chart_window.price_alert:
            return {}
        return self.light_chart_window.price_alert[self.symbol]

    @price_alert.setter
    def price_alert(self, value):
        if isinstance(value, dict):
            self.light_chart_window.price_alert[self.symbol] = value

    def _on_alert_settings_changed(self, settings: dict, showinfo: bool = True):
        """处理预警设置变化"""
        if not settings.get('enabled', False):
            self.price_alert = {}
            return
        if settings:
            up_price = settings.get('up_price', 0)
            down_price = settings.get('down_price', 0)
            if not any([up_price, down_price]):
                self.price_alert = {}
                return
        self.price_alert.update(settings)
        self.set_on_new_bar_event()
        if showinfo:
            alert_type_text = {
                'both': '双向预警',
                'up': '上破预警',
                'down': '下破预警'
            }.get(settings.get('alert_type', 'both'), '双向预警')

            info_text = f"价格预警已启用 [{alert_type_text}]"

            up_price = settings.get('up_price', 0)
            down_price = settings.get('down_price', 0)

            if up_price > 0:
                info_text += f" 上破: {up_price:.4f}"
            if down_price > 0:
                info_text += f" 下破: {down_price:.4f}"

            # 在合适的位置显示状态信息
            InfoBar.info("价格预警设置成功", info_text, duration=2000,
                         position=InfoBarPosition.TOP_RIGHT, parent=self.light_chart_window)

    def set_on_new_bar_event(self):
        if not self._new_bar_event:
            self.events.new_bar += self.on_new_bar
            self._new_bar_event = True

    def on_new_bar(self, chart):
        """
        新K线生成回调：实用看盘功能
        1. 监控收盘价是否触发价格预警
        2. 打印最新收盘价（保留4位小数，便于精准监控）
        3. 触发预警时弹出提示并标记K线
        4. 自动重置预警（价格回归区间后）
        """
        if not self.price_alert:
            return
        latest_close = self.kline['close'].iloc[-1]

        # 1. 检查价格预警配置
        alert_config = self.price_alert
        up_price = alert_config['up_price']
        down_price = alert_config['down_price']
        enabled = alert_config['enabled']

        # 2. 上破价格预警（未触发过且配置有效才提示）
        if up_price > 0 and latest_close >= up_price and enabled:
            self._trigger_price_alert(
                "上破预警",
                f"收盘价 {latest_close:.4f} 上破预警价格 {up_price:.4f}！"
            )
        # 3. 下破价格预警（未触发过且配置有效才提示）
        elif down_price > 0 and latest_close <= down_price and enabled:
            self._trigger_price_alert(
                "下破预警",
                f"收盘价 {latest_close:.4f} 下破预警价格 {down_price:.4f}！"
            )

    def _trigger_price_alert(self, title, content, duration=2000, position=InfoBarPosition.TOP_RIGHT):
        InfoBar.info(title, content, duration=duration,
                     position=position, parent=self.light_chart_window)

    def _reset_price_alert(self):
        self.price_alert = {}

    def on_search(self, chart, searched_string):
        """
        合约搜索回调：基于自定义 Dialog 适配，避免 contentWidget 报错
        """
        if not searched_string or not hasattr(self.light_chart_window, 'contract_dict'):
            return

        # 1. 筛选符合条件的合约（不区分大小写，模糊匹配）
        matched_contracts = []
        contract_dict = self.light_chart_window.contract_dict
        search_lower = searched_string.lower()

        for contract in contract_dict.keys():
            if search_lower in contract.lower():
                matched_contracts.append(contract)

        # 2. 无匹配结果，显示优雅提示
        if not matched_contracts:
            InfoBar.warning(
                title="无匹配结果",
                content=f"未找到包含「{searched_string}」的合约",
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self.light_chart_window
            )
            return

        # 3. 单个匹配结果，直接切换合约并提示
        if len(matched_contracts) == 1:
            target_contract = matched_contracts[0]
            self._switch_contract_directly(target_contract)
            InfoBar.success(
                title="切换成功",
                content=f"已快速切换至合约「{target_contract}」",
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self.light_chart_window
            )
            return

        # 4. 多个匹配结果，弹出适配自定义 Dialog 的 Fluent 风格对话框
        self._create_fluent_search_dialog(matched_contracts, searched_string)

    def _create_fluent_search_dialog(self, matched_contracts: list[str], searched_string: str):
        """
        创建适配自定义 Dialog 的 Fluent 风格对话框（核心修正：无 contentWidget）
        复用自定义 Dialog 的 vBoxLayout，清理默认文本控件，添加 QFluentWidgets 控件
        """
        # 步骤 1：初始化自定义 Dialog（传入空内容，避免默认文本干扰）
        dialog_title = f"找到 {len(matched_contracts)} 个匹配合约"
        self.search_dialog = Dialog(
            dialog_title, "", parent=self.light_chart_window)
        # 调整对话框大小（适配内容，比原默认 240x192 更大）
        self.search_dialog.setFixedSize(450, 400)

        # 步骤 2：清理自定义 Dialog 的默认控件（不修改原码，仅在子类中移除）
        self._clean_custom_dialog_default_widgets()

        # 步骤 3：创建顶层内容容器（直接添加到自定义 Dialog 的 vBoxLayout 中）
        content_container = QWidget(self.search_dialog)
        main_layout = QVBoxLayout(content_container)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(24, 24, 24, 20)

        # 步骤 4：添加 Fluent 风格控件（与之前设计一致，保留所有优化）
        # 1. 提示卡片（显示搜索关键词）
        tip_card = CardWidget(content_container)
        tip_layout = QHBoxLayout(tip_card)
        tip_layout.setContentsMargins(16, 12, 16, 12)
        tip_label = BodyLabel(f"关键词：「{searched_string}」，可二次筛选缩小范围", tip_card)
        tip_layout.addWidget(tip_label, 0, Qt.AlignLeft)
        main_layout.addWidget(tip_card)

        # 2. 二次筛选搜索框（QFluentWidgets SearchLineEdit）
        self.filter_search = SearchLineEdit(content_container)
        self.filter_search.setPlaceholderText("再次筛选合约（模糊匹配）...")
        self.filter_search.setClearButtonEnabled(True)
        self.filter_search.textChanged.connect(
            lambda text: self._filter_contract_list_fluent(
                text, matched_contracts)
        )
        main_layout.addWidget(self.filter_search)

        # 3. 滚动列表容器
        scroll_area = ScrollArea(content_container)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")

        # 4. 合约列表（QFluentWidgets ListWidget）
        self.contract_list_fluent = ListWidget(scroll_area)
        self.contract_list_fluent.addItems(matched_contracts)
        self.contract_list_fluent.setSelectionMode(ListWidget.SingleSelection)
        self.contract_list_fluent.setCurrentRow(0)
        self.contract_list_fluent.itemDoubleClicked.connect(
            lambda item: self._confirm_contract_selection_fluent(item.text())
        )
        scroll_area.setWidget(self.contract_list_fluent)

        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(scroll_area, 1)

        # 5. 底部按钮栏（主次按钮区分）
        btn_layout = QHBoxLayout()
        cancel_btn = PushButton("取消", content_container,
                                FluentIcon.CLOSE.icon())
        cancel_btn.clicked.connect(self.search_dialog.reject)
        confirm_btn = PrimaryPushButton(
            "确认选择", content_container, FluentIcon.ACCEPT.icon())
        confirm_btn.clicked.connect(self._confirm_contract_selection_fluent)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(confirm_btn)
        btn_layout.setSpacing(12)
        main_layout.addLayout(btn_layout)

        # 步骤 5：核心修正：将内容容器添加到自定义 Dialog 的 vBoxLayout 中
        # 替换原有的 textLayout 位置，避免布局冲突
        self.search_dialog.vBoxLayout.insertWidget(
            1, content_container, 1, Qt.AlignTop)
        # 隐藏原有的 buttonGroup（默认 OK/Cancel 按钮），替换为自定义按钮栏
        self.search_dialog.buttonGroup.hide()

        # 步骤 6：显示对话框
        self.search_dialog.exec_()

    def _clean_custom_dialog_default_widgets(self):
        """
        清理自定义 Dialog 的默认控件（不修改原码，仅临时隐藏/移除）
        避免默认标题/内容标签与 QFluentWidgets 控件冲突
        """
        dialog = self.search_dialog
        # 1. 隐藏默认标题标签（windowTitleLabel 和 titleLabel）
        if hasattr(dialog, 'windowTitleLabel') and dialog.windowTitleLabel:
            dialog.windowTitleLabel.hide()
        if hasattr(dialog, 'titleLabel') and dialog.titleLabel:
            dialog.titleLabel.hide()

        # 2. 隐藏默认内容标签（contentLabel）
        if hasattr(dialog, 'contentLabel') and dialog.contentLabel:
            dialog.contentLabel.hide()

        # 3. 清理默认 textLayout（移除多余间距，避免影响自定义内容）
        if hasattr(dialog, 'textLayout'):
            dialog.textLayout.setSpacing(0)
            dialog.textLayout.setContentsMargins(0, 0, 0, 0)

    def _filter_contract_list_fluent(self, filter_text: str, original_contracts: list[str]):
        """实时二次筛选合约列表"""
        self.contract_list_fluent.clear()
        if not filter_text:
            self.contract_list_fluent.addItems(original_contracts)
            self.contract_list_fluent.setCurrentRow(0)
            return

        filter_lower = filter_text.lower()
        filtered_contracts = [
            c for c in original_contracts if filter_lower in c.lower()
        ]
        self.contract_list_fluent.addItems(filtered_contracts)
        if filtered_contracts:
            self.contract_list_fluent.setCurrentRow(0)

    def _confirm_contract_selection_fluent(self, contract_text: str = None):
        """确认合约选择"""
        target_contract = None
        if contract_text:
            target_contract = contract_text
        else:
            current_item = self.contract_list_fluent.currentItem()
            if not current_item:
                InfoBar.warning(
                    title="选择错误",
                    content="请先选择一个合约再确认！",
                    duration=1500,
                    position=InfoBarPosition.TOP_RIGHT,
                    parent=self.search_dialog
                )
                return
            target_contract = current_item.text()

        self._switch_contract_directly(target_contract)
        self.search_dialog.accept()
        InfoBar.success(
            title="切换成功",
            content=f"已切换至合约「{target_contract}」，图表数据正在更新...",
            duration=2000,
            position=InfoBarPosition.TOP_RIGHT,
            parent=self.light_chart_window
        )

    def _switch_contract_directly(self, contract: str):
        """直接切换目标合约"""
        light_window = self.light_chart_window
        if contract not in light_window.contract_dict:
            InfoBar.error(
                title="切换失败",
                content=f"合约「{contract}」未配置对应的策略！",
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self.light_chart_window
            )
            return
        light_window.current_contract = contract
        strategy = light_window.strategyes[light_window.contract_dict[contract]]
        light_window.replace_chart(strategy)

    def cleanup(self):
        """切换合约时的彻底清理逻辑（核心）"""
        if hasattr(self, 'qtimer') and self.qtimer:
            try:
                self.qtimer.stop()
            except Exception as e:
                print(f"停止定时器时出错: {e}")
            finally:
                self.qtimer = None
        event_names = [
            f'search{self.id}',
            f'save_drawings{self.id}',
            f'click{self.id}',
            f'range_change{self.id}',
            f'new_bar{self.id}'
        ]

        for event_name in event_names:
            try:
                if hasattr(self.win, 'handlers') and event_name in self.win.handlers:
                    del self.win.handlers[event_name]
            except Exception as e:
                print(f"清理事件监听器异常:{e}")
        if hasattr(self, 'events'):
            try:
                for event_name in ['click', 'range_change', 'search', 'new_bar']:
                    if hasattr(self.events, event_name):
                        getattr(self.events, event_name)._callable = []
                        setattr(self.events, event_name, None)
                self.events = None
            except Exception as e:
                print(f"清理 Emitter 事件异常:{e}")

        webview = self.get_webview()
        if webview:
            cleanup_js = f'''
            try {{
                // 1. 销毁图表实例
                if (typeof {self.id} !== 'undefined' && {self.id}.chart) {{
                    // 解绑所有事件
                    {self.id}.chart.unsubscribeClick();
                    {self.id}.chart.unsubscribeCrosshairMove();
                    {self.id}.chart.timeScale().unsubscribeVisibleLogicalRangeChange();
                    
                    // 移除所有系列和子图表
                    while ({self.id}.chart.seriesCount() > 0) {{
                        {self.id}.chart.removeSeries({self.id}.chart.seriesByIndex(0));
                    }}
                    
                    // 销毁图表
                    {self.id}.chart.destroy();
                    {self.id}.chart = null;
                }}
                
                // 2. 销毁工具箱
                if ({self.id}.toolBox) {{
                    {self.id}.toolBox = null;
                }}
                
                // 3. 清空整个图表对象
                {self.id} = null;
                
                // 4. 强制垃圾回收
                if (window.gc) {{ window.gc(); }}
            }} catch (e) {{
                console.error("JS层清理失败:", e);
            }}
            '''
            webview.page().runJavaScript(cleanup_js)
            try:
                # 断开所有信号连接
                webview.page().loadFinished.disconnect(self._on_webview_loaded)
                webview.customContextMenuRequested.disconnect(
                    self._on_webview_custom_context_menu)

                # 停止页面加载
                webview.stop()
                webview.setUrl(QUrl("about:blank"))  # 清空页面

                # 清理页面
                page = webview.page()
                if page:
                    # page.history().clear()
                    page.deleteLater()

                # 设置空页面
                webview.setPage(None)

            except Exception as e:
                print(f"清理 WebView 时出错: {e}")
        for name, subchart in list(self.subcharts.items()):
            try:
                subchart_id = subchart.id
                if hasattr(self.win, 'handlers'):
                    keys_to_delete = []
                    for key in list(self.win.handlers.keys()):
                        if subchart_id in key:
                            keys_to_delete.append(key)
                    for key in keys_to_delete:
                        del self.win.handlers[key]
            except Exception as e:
                print(f"清理子图表 {name} 时出错: {e}")

        self.subcharts.clear()
        self.chart_indicators.clear()
        self.signal_indicators.clear()
        self.kline = None
        self.tick = None
        self.strategy = None
        self.toolbox = None
        self.light_chart_window = None


def main(strategyes, period_milliseconds: int = 1000):
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    w = MainWindow(strategyes, period_milliseconds)
    w.show()
    app.exec_()
