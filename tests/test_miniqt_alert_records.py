# coding:utf-8
"""预警记录（顶栏「预警记录」）：持久化 + 状态 + 暂停/运行/删除 + 触发完成后删除 ✓。"""
from __future__ import annotations

import os
import types
from datetime import datetime, timedelta

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PyQt6')

from miniqt.app.common.chart_data import ChartDataManager


# ---- 持久化（chart_data.json）---------------------------------------------
def test_alert_records_persist_and_delete(tmp_path):
    path = tmp_path / 'chart_data.json'
    manager = ChartDataManager(str(path))
    assert manager.get_alert_records() == []
    manager.add_alert_record({'id': 'a1', 'message': '穿过 100',
                              'status': 'active', 'notify': '满足条件时触发一次'})
    manager.add_alert_record({'id': 'a2', 'message': '上穿 200',
                              'status': 'paused'})
    reloaded = ChartDataManager(str(path))
    assert [item['id'] for item in reloaded.get_alert_records()] == ['a1', 'a2']
    assert reloaded.get_alert_records()[0]['message'] == '穿过 100'
    # 同 id 覆盖
    manager.add_alert_record({'id': 'a1', 'message': '改过', 'status': 'paused'})
    assert len(manager.get_alert_records()) == 2
    # 删除
    manager.delete_alert_record('a1')
    assert [item['id'] for item in ChartDataManager(
        str(path)).get_alert_records()] == ['a2']
    # 结构校验：没有 id 的被丢掉
    manager.set_alert_records([{'id': 'x'}, {'message': 'no-id'}, 'bad'])
    assert [item['id'] for item in manager.get_alert_records()] == ['x']


# ---- 窗口方法（假窗口）-----------------------------------------------------
@pytest.fixture()
def alert_env(tmp_path, monkeypatch):
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    import miniqt.app.common.chart_data as chart_data
    manager = ChartDataManager(str(tmp_path / 'chart_data.json'))
    monkeypatch.setattr(chart_data, 'chart_data_manager', manager)

    class _Bar:
        @staticmethod
        def success(*args, **kwargs):
            pass

        @staticmethod
        def warning(*args, **kwargs):
            pass

        @staticmethod
        def info(*args, **kwargs):
            pass

    monkeypatch.setattr(window_module, 'InfoBar', _Bar)
    return window_module, manager


def _alert_window(window_module, symbol='SHFE.ag2612'):
    W = window_module.PylightchartsChartWindow
    window = types.SimpleNamespace(
        cycle=60, _alert_records_last_close={},
        # 预警「操作」映射 + 触发后下单（SimpleNamespace 不会继承类属性 ✗）
        ALERT_ACTIONS=W.ALERT_ACTIONS,
        _alert_confirm_order=lambda *args, **kwargs: None,
        topbar_current_symbol=lambda: symbol)
    for name in ('alert_records', '_save_alert_records', 'add_alert_record',
                 'set_alert_record_status', 'delete_alert_record',
                 'purge_expired_alert_records', '_alert_record_hit',
                 '_notify_alert_record', '_check_alert_records',
                 'check_price_alert',
                 # 预警线（新增 ✓）
                 '_refresh_alert_lines', '_remove_alert_line',
                 '_remove_all_alert_lines', 'set_alert_record_line',
                 'topbar_alert_line_toggle', '_purge_and_refresh_alert_lines'):
        setattr(window, name, types.MethodType(getattr(W, name), window))
    # staticmethod → 直接挂
    window._new_alert_record_id = W._new_alert_record_id
    window._alert_record_expired = W._alert_record_expired
    window._same_contract = W._same_contract
    window._alert_record_tag = W._alert_record_tag
    window._alert_line_price = W._alert_line_price
    window._alert_line_color = W._alert_line_color
    return window


def test_add_alert_record_defaults_to_active(alert_env):
    window_module, manager = alert_env
    window = _alert_window(window_module)
    record = window.add_alert_record(
        {'message': 'SHFE.ag2612 穿过 14645', 'alert_type': 'cross',
         'cross_price': 14645.0, 'notify': '满足条件时触发一次'})
    assert record['status'] == 'active'              # 初始：生效 ✓
    saved = window.alert_records()
    assert len(saved) == 1
    assert saved[0]['id'] == record['id']
    assert saved[0]['symbol'] == 'SHFE.ag2612'
    assert saved[0]['cycle'] == 60
    assert saved[0]['status'] == 'active'


def test_pause_run_and_delete(alert_env):
    window_module, manager = alert_env
    window = _alert_window(window_module)
    record = window.add_alert_record({'message': '上穿 100',
                                      'alert_type': 'up', 'up_price': 100.0})
    window.set_alert_record_status(record['id'], 'paused')
    assert window.alert_records()[0]['status'] == 'paused'     # 暂停 → 无效 ✓
    window.set_alert_record_status(record['id'], 'active')
    assert window.alert_records()[0]['status'] == 'active'     # 运行 → 生效 ✓
    window.delete_alert_record(record['id'])                   # 生效也能删 ✓
    assert window.alert_records() == []


def test_trigger_once_deletes_the_record(alert_env):
    window_module, manager = alert_env
    window = _alert_window(window_module)
    window.add_alert_record({'message': '上穿 100', 'alert_type': 'up',
                             'up_price': 100.0,
                             'notify': '满足条件时触发一次'})
    assert window._check_alert_records(101.0) is True
    assert window.alert_records() == []              # 完成 → 删除记录 ✓


def test_paused_record_is_skipped(alert_env):
    window_module, manager = alert_env
    window = _alert_window(window_module)
    record = window.add_alert_record({'message': '上穿 100', 'alert_type': 'up',
                                      'up_price': 100.0})
    window.set_alert_record_status(record['id'], 'paused')
    assert window._check_alert_records(101.0) is False
    assert len(window.alert_records()) == 1          # 无效 → 不触发、保留 ✓


def test_expired_record_is_deleted(alert_env):
    window_module, manager = alert_env
    window = _alert_window(window_module)
    past = (datetime.now() - timedelta(hours=1)).isoformat(timespec='minutes')
    window.add_alert_record({'message': '上穿 100', 'alert_type': 'up',
                             'up_price': 100.0, 'expire_at': past})
    window.purge_expired_alert_records()
    assert window.alert_records() == []              # 过期 → 删除 ✓


def test_per_minute_notification_keeps_the_record(alert_env):
    window_module, manager = alert_env
    window = _alert_window(window_module)
    window.add_alert_record({'message': '上穿 100', 'alert_type': 'up',
                             'up_price': 100.0,
                             'notify': '满足条件时每分钟发一次'})
    assert window._check_alert_records(101.0) is True
    assert len(window.alert_records()) == 1          # 每分钟 → 保留 ✓
    assert window._check_alert_records(101.0) is False   # 60s 内不重复触发 ✓


def test_cross_record_uses_last_close(alert_env):
    window_module, manager = alert_env
    window = _alert_window(window_module)
    window.add_alert_record({'message': '穿过 100', 'alert_type': 'cross',
                             'cross_price': 100.0,
                             'notify': '满足条件时触发一次'})
    assert window._check_alert_records(99.0) is False    # 第一笔只记基准
    assert window._check_alert_records(101.0) is True    # 上穿 → 触发
    assert window.alert_records() == []


def test_records_fire_per_contract(alert_env):
    """多图时每一格用自己的合约 + 最新价检查 → 所有合约都能触发 ✓。"""
    window_module, manager = alert_env
    window = _alert_window(window_module, symbol='SHFE.ag2612')
    window.add_alert_record({'symbol': 'SHFE.ag2612', 'message': 'ag',
                             'alert_type': 'up', 'up_price': 100.0})
    window.add_alert_record({'symbol': 'SHFE.au2612', 'message': 'au',
                             'alert_type': 'up', 'up_price': 200.0})
    # 用 au2612 自己的价检查 → 只触发 au 那条 ✓
    assert window._check_alert_records(201.0, 'SHFE.au2612') is True
    assert [r['message'] for r in window.alert_records()] == ['ag']
    # ag 那条还在，用 ag 自己的价仍能触发 ✓
    assert window._check_alert_records(101.0, 'SHFE.ag2612') is True
    assert window.alert_records() == []
    # 不传 symbol 时回退到当前点击那格（这里 stub 成 ag2612 ✓）
    window.add_alert_record({'symbol': 'SHFE.ag2612', 'message': 'ag2',
                             'alert_type': 'up', 'up_price': 50.0})
    assert window._check_alert_records(51.0) is True
    assert window.alert_records() == []


def test_check_price_alert_passes_the_symbol_through(alert_env):
    """``check_price_alert`` 要把 symbol 透传给记录检查（每一格各查各的 ✓）。"""
    window_module, manager = alert_env
    window = _alert_window(window_module, symbol='SHFE.ag2612')
    seen = []
    window._check_alert_records = lambda close, symbol=None: (
        seen.append(symbol) or False)
    window._anchor_symbol = lambda: 'SHFE.ag2612'
    window._check_single_price_alert = lambda close: False
    window.check_price_alert(101.0, symbol='SHFE.au2612')
    assert seen == ['SHFE.au2612']


# ---- 界面 ------------------------------------------------------------------
def test_alert_records_dialog_and_button(alert_env):
    window_module, manager = alert_env
    records_mod = pytest.importorskip(
        'miniqt.app.windows.tradingview_alert_records')
    dialog_mod = pytest.importorskip(
        'miniqt.app.windows.tradingview_alert_dialog')
    from PyQt6.QtWidgets import QApplication, QWidget

    window = _alert_window(window_module)
    window.add_alert_record({'message': 'SHFE.ag2612 穿过 14645',
                             'alert_type': 'cross', 'cross_price': 14645.0,
                             'notify': '满足条件时触发一次'})
    parent = QWidget()
    dialog = records_mod.AlertRecordsDialog(window, parent=parent)
    QApplication.processEvents()
    assert dialog.countLabel.text() == '1 个'
    # 底部没有「关闭」按钮（右上角已有 ✕ 关闭 ✓）
    assert dialog.cancelButton.isHidden() and dialog.yesButton.isHidden()

    def _rows():
        return [dialog._listLayout.itemAt(i).widget()
                for i in range(dialog._listLayout.count() - 1)]

    rows = _rows()
    assert len(rows) == 1
    assert rows[0].titleLabel.text() == 'SHFE.ag2612 穿过 14645'
    assert '生效' in rows[0].subtitleLabel.text()
    # 三个操作按钮都在：预警线 / 暂停 / 删除（默认隐藏，悬浮才显 ✓）
    assert rows[0].actions.isHidden()
    assert rows[0].lineButton is not None
    assert rows[0].pauseButton is not None
    assert rows[0].deleteButton is not None
    # 每条记录带边框；悬浮底色与布局界面一致 ✓
    assert 'border:1px solid' in rows[0].styleSheet()
    assert 'border:1px solid' in records_mod._row_qss('alertRecordRow')
    assert 'rgba(128,128,128,0.12)' in records_mod._row_qss(
        'alertRecordRow', True)
    # 暂停后刷新 → 状态「无效」✓
    window.set_alert_record_status(window.alert_records()[0]['id'], 'paused')
    dialog._refresh()
    assert '无效' in _rows()[0].subtitleLabel.text()
    dialog.close()

    # 创建预警对话框上有「预警记录」按钮 + 预警线/操作两行 ✓
    create = dialog_mod.TradingViewAlertDialog(symbol='rb2610', price=1.0,
                                               window=window, parent=parent)
    assert create.recordsButton.text() == '预警记录'
    assert create.lineSwitch.isChecked()
    assert create.qtySpin.value() == 1
    assert create.actionBox.currentText() == '无操作'
    create.close()


# ---- 预警线（新增 ✓）------------------------------------------------------
class _FakeLine:
    def __init__(self, price, **kwargs):
        self.price = price
        self.deleted = False
        self.kwargs = kwargs

    def update(self, price):
        self.price = price

    def delete(self):
        self.deleted = True


def _line_window(window_module, symbol='SHFE.ag2612'):
    """带假图表 + 假 ``horizontal_line`` 的预警窗口（验证预警线 ✓）。"""
    W = window_module.PylightchartsChartWindow
    window = _alert_window(window_module, symbol=symbol)
    window.chart = object()
    window.cycle = 60
    window._alert_lines = {}
    window._closing = False
    created = []

    def horizontal_line(*args, **kwargs):
        price = kwargs.get('price', args[0] if args else None)
        line = _FakeLine(price)
        line.kwargs = dict(kwargs)
        created.append(line)
        return line

    window.horizontal_line = horizontal_line
    for name in ('_refresh_alert_lines', '_remove_alert_line',
                 '_remove_all_alert_lines', 'set_alert_record_line',
                 'topbar_alert_line_toggle', '_current_alert_tag'):
        setattr(window, name, types.MethodType(getattr(W, name), window))
    return window, created


def test_alert_record_stores_line_qty_action(alert_env):
    """预警记录要带 预警线开关 / 数量 / 操作（默认 开/1/无操作 ✓）。"""
    window_module, manager = alert_env
    window = _alert_window(window_module)
    record = window.add_alert_record(
        {'message': 'x', 'alert_type': 'cross', 'cross_price': 100.0})
    assert record['show_line'] is True
    assert record['qty'] == 1
    assert record['action'] == '无操作'
    record2 = window.add_alert_record(
        {'message': 'y', 'show_line': False, 'qty': 3, 'action': '买'})
    assert record2['show_line'] is False
    assert record2['qty'] == 3
    assert record2['action'] == '买'


def test_alert_lines_drawn_toggled_and_contract_scoped(alert_env):
    """预警线：同合约才画；开关 / 删除后同步增删 ✓（原理同持仓线）。"""
    window_module, manager = alert_env
    window, created = _line_window(window_module)
    record = window.add_alert_record(
        {'message': 'SHFE.ag2612 穿过 14645', 'alert_type': 'cross',
         'cross_price': 14645.0})
    assert len(window._alert_lines) == 1          # 创建即画 ✓
    assert created[-1].price == 14645.0
    # 标签在**图内左边**（同持仓线），不放右边 Y 轴 ✓
    assert created[-1].kwargs.get('axis_label_visible') is False
    assert created[-1].kwargs.get('label_visible') is True
    # 关掉预警线 → 删线 ✓
    window.set_alert_record_line(record['id'], False)
    assert window._alert_lines == {}
    assert created[-1].deleted is True
    # 再打开 → 重新建 ✓
    window.topbar_alert_line_toggle(record['id'])
    assert len(window._alert_lines) == 1
    # 删除记录 → 线也删 ✓
    window.delete_alert_record(record['id'])
    assert window._alert_lines == {}
    # 别的合约（SHFE.au2612）不该画到当前合约上 ✓
    window.add_alert_record({'message': 'au 上穿 780', 'symbol': 'SHFE.au2612',
                             'alert_type': 'up', 'up_price': 780.0})
    assert window._alert_lines == {}


def test_alert_line_price_and_color(alert_env):
    """预警线价格 / 颜色按预警类型取 ✓。"""
    window_module, manager = alert_env
    W = window_module.PylightchartsChartWindow
    assert W._alert_line_price({'alert_type': 'up', 'up_price': 10.0}) == 10.0
    assert W._alert_line_price(
        {'alert_type': 'down', 'down_price': 5.0}) == 5.0
    assert W._alert_line_price(
        {'alert_type': 'cross', 'cross_price': 7.0}) == 7.0
    assert W._alert_line_price({'alert_type': 'up'}) == 0.0
    assert W._alert_line_color({'alert_type': 'up'}) == '#ef5350'
    assert W._alert_line_color({'alert_type': 'down'}) == '#26a69a'
    assert W._alert_line_color({'alert_type': 'cross'}) == '#FF9800'
