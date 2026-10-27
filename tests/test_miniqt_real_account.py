# coding: utf-8
"""天勤**实盘账户**（TqAccount / TqMultiAccount）接入的回归测试。

用户需求：

* 期货登录窗口「记住密码」右侧加「使用实盘账户」勾选框 → 展开
  期货公司 / 资金账号 / 交易密码（同一登录界面）；
* 期货公司暂时固定三家（免费可用）：宏源期货 / 徽商期货 / 银河期货；
* 实盘密码**不保存**；
* 登录后用 ``TqMultiAccount([TqKq(), TqAccount(...)])`` 同时挂模拟 + 实盘，
  取账户/持仓/委托/成交与下单都要带 ``account=``；
* 看盘窗口底部的「模拟账户」改名为「交易账户」，加账户下拉切换。

    pytest tests/test_miniqt_real_account.py
"""
from __future__ import annotations

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
LOGIN = REPO / 'miniqt' / 'app' / 'login' / 'LoginWindow.py'
CONFIG = REPO / 'miniqt' / 'app' / 'common' / 'config.py'
MAIN = REPO / 'miniqt' / 'app' / 'view' / 'main_window.py'
PANEL = REPO / 'miniqt' / 'app' / 'windows' / 'sim_account_panel.py'
WINDOW = REPO / 'miniqt' / 'app' / 'windows' / 'pylightcharts_window.py'
REAL_ACCOUNTS = REPO / 'miniqt' / 'app' / 'common' / 'real_accounts.py'
SETTINGS = REPO / 'miniqt' / 'app' / 'view' / 'setting_interface.py'
DIALOG = REPO / 'miniqt' / 'app' / 'windows' / 'real_account_dialog.py'

pytestmark = pytest.mark.skipif(
    not LOGIN.exists(), reason='需要仓库里的 miniqt 源码')


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding='utf-8')


# --------------------------------------------------------------- 券商 broker_id
def test_broker_ids_are_the_official_tqsdk_ones():
    """broker_id 必须和 tqsdk 交易网关一致（不能自己起名）。

    已用 ``https://files.shinnytech.com/{broker_id}.json`` 核实：
    宏源 ``H宏源期货``、徽商 ``H徽商期货``、银河 ``Y银河期货``（**Y 前缀**）。
    """
    source = _read(REAL_ACCOUNTS)
    assert "'H宏源期货'" in source
    assert "'H徽商期货'" in source
    assert "'Y银河期货'" in source
    # 银河不是 H 前缀（踩过：H银河期货 404）
    assert "'H银河期货'" not in source


def test_login_window_has_the_real_account_form():
    source = _read(LOGIN)
    assert 'FUTURES_BROKERS' in source
    assert '使用实盘账户' in source
    assert 'realAccountCheckBox' in source
    assert 'brokerCombo' in source and 'findData' in source
    assert 'realAccountEdit' in source
    assert 'realPasswordEdit' in source
    # 勾选 → 展开
    assert 'realAccountWidget.setVisible' in source


def test_real_account_password_is_never_saved():
    """实盘密码**不落盘**（用户要求：不需要记住密码）✓"""
    login = _read(LOGIN)
    config = _read(CONFIG)
    assert 'futuresRealBrokerId' in config
    assert 'futuresRealAccountId' in config
    # 配置里没有「实盘密码」项
    assert 'futuresRealPassword' not in config
    # 登录只保存券商 / 资金账号
    assert 'cfg.futuresRealBrokerId.value' in login
    assert 'cfg.futuresRealAccountId.value' in login


# ------------------------------------------------------------- TqMultiAccount
def test_worker_builds_multi_account_when_real_is_given():
    source = _read(LOGIN)
    assert 'TqMultiAccount' in source
    assert 'TqAccount(' in source
    assert 'real_account' in source
    assert 'TqMultiAccount([sim, real])' in source


def test_main_window_collects_accounts_after_login():
    source = _read(MAIN)
    assert 'def start_futures_login' in source
    assert 'real_account' in source
    assert '_collect_tq_accounts' in source
    assert 'TqMultiAccount' in source
    assert 'tq_accounts' in source
    # 失败 / 退出要清空，避免残留
    assert source.count('self.tq_accounts = []') >= 2


# ------------------------------------------------------------- 账户路由（account=）
def test_chart_window_routes_account_for_every_account_call():
    source = _read(WINDOW)
    assert 'def _current_account' in source
    assert 'def _account_kwargs' in source
    assert 'def _on_account_changed' in source
    # 取账户 / 持仓 / 委托 / 成交都要带 account=
    assert 'value = getter(**account_kwargs)' in source
    assert '**self._account_kwargs())' in source
    # 下单 / 撤单 / TargetPosTask
    assert 'limit_price=float(price or 0) or None,\n' in source
    assert 'api.cancel_order(symbol, **self._account_kwargs())' in source
    assert 'api.cancel_order(order_id, **self._account_kwargs())' in source
    assert 'TargetPosTask(api, symbol, **self._account_kwargs())' in source


def test_account_selector_in_trade_panel():
    panel = _read(PANEL)
    assert 'accountChanged' in panel
    assert '交易账户' in panel
    assert 'accountCombo' in panel
    # 只有一个账户时隐藏选择器
    assert 'setVisible(len(labels) > 1)' in panel
    # 「模拟账户」页改名为「交易账户」
    assert "('sim', '模拟账户')" not in panel
    assert "('sim', '交易账户')" in panel


def test_real_account_is_warned_and_orders_are_tagged():
    """选中实盘账户时必须**红色警告**，下单/撤单提示带【实盘】✓"""
    panel = _read(PANEL)
    assert 'realWarnLabel' in panel
    assert '当前为实盘账户' in panel
    assert 'real_flags' in panel
    window = _read(WINDOW)
    assert 'REAL_ACCOUNT_TYPES' in window
    assert '_selected_account_is_real' in window
    assert 'def _order_tag' in window
    assert '【实盘】' in window


def test_position_lines_follow_the_selected_account():
    """持仓线必须按**当前账户**取，并在切账户时立刻换成另一套线 ✓"""
    window = _read(WINDOW)
    refresh = window.split('def _refresh_position_lines', 1)[1]
    refresh = refresh.split('\n    def ', 1)[0]
    assert 'account_kwargs' in refresh
    assert 'getter(**account_kwargs)' in refresh
    switch = window.split('def _on_account_changed', 1)[1]
    switch = switch.split('\n    def ', 1)[0]
    assert '_update_position_lines()' in switch
    # 标签带账户标识（模拟无前缀 / 实盘带【实盘】）
    assert '_position_title_with_tag' in window
    assert '【实盘】' in window


def test_strategy_runner_receives_the_selected_account():
    """把选中账户接进策略链路（但**仍是回测模式、不下单**）✓"""
    runner = (REPO / 'miniqt' / 'app' / 'common' /
              'strategy_runner.py').read_text(encoding='utf-8')
    assert 'account=None' in runner
    assert 'strategy._live_account' in runner
    # 明确保留：策略运行仍为回测模式（不下真单）
    assert '不下单' in runner or '_is_live_trading' in runner
    window = _read(WINDOW)
    assert window.count('account=self._current_account()') >= 4


# --------------------------------------------------- minibt：实盘账户透传
def test_tqobjs_passes_account_to_live_calls(monkeypatch):
    """``TqObjs`` 必须把账户传给 ``get_position`` / ``TargetPosTask`` ✓"""
    import sys
    import types

    import minibt.utils as utils

    calls = {}

    class FakeApi:
        @property
        def _loop(self):
            class _Loop:
                def is_closed(self):
                    return False
            return _Loop()

        def get_quote(self, symbol):
            return 'QUOTE'

        def get_position(self, symbol, **kwargs):
            calls['position'] = (symbol, kwargs)
            return 'POSITION'

    class FakeTargetPosTask:
        def __init__(self, api, symbol, **kwargs):
            calls['target'] = (symbol, kwargs)

    monkeypatch.setitem(sys.modules, 'tqsdk',
                        types.SimpleNamespace(TargetPosTask=FakeTargetPosTask))
    monkeypatch.setattr(utils.Base, '_api', FakeApi(), raising=False)

    account = object()
    obj = utils.TqObjs('SHFE.rb2610', account=account)
    assert obj.Quote == 'QUOTE'
    assert calls['position'][1].get('account') is account
    assert calls['target'][1].get('account') is account

    # 不传账户 → 保持旧行为（不传 account=）
    utils.TqObjs('SHFE.rb2610')
    assert calls['position'][1] == {}
    assert calls['target'][1] == {}


def test_kline_and_get_kline_thread_the_live_account():
    core = (REPO / 'minibt' / 'indicators' / 'core.py').read_text(
        encoding='utf-8')
    assert "live_account = kwargs.pop('account', None)" in core
    assert 'TqObjs(symbol, account=live_account)' in core
    base = (REPO / 'minibt' / 'strategy' / 'base.py').read_text(
        encoding='utf-8')
    assert "kwargs['account'] = self._live_account" in base


# ------------------------------------------------- 策略实盘 / 预警下单
def test_strategy_runner_has_a_live_mode():
    runner = (REPO / 'miniqt' / 'app' / 'common' /
              'strategy_runner.py').read_text(encoding='utf-8')
    assert 'def enable_live' in runner
    assert 'def disable_live' in runner
    assert 'def _advance_live' in runner
    assert '_execute_live_trading' in runner
    assert '_live_account=self.account' in runner
    assert 'Base._is_live_trading = True' in runner


def test_strategy_live_switch_needs_confirmation():
    window = _read(WINDOW)
    assert 'def _on_strategy_live_changed' in window
    assert 'def _confirm_strategy_live' in window
    assert 'def _enable_live_runner' in window
    assert 'def _strategy_runners' in window
    # 默认按钮必须是「取消」（防误点 ✓）
    assert 'setDefaultButton(QMessageBox.StandardButton.No)' in window
    panel = _read(PANEL)
    assert 'strategyLiveCheckBox' in panel
    assert 'strategyLiveChanged' in panel
    assert 'set_strategy_live_available' in panel


def test_alert_action_asks_before_ordering():
    window = _read(WINDOW)
    assert 'ALERT_ACTIONS' in window
    assert 'def _alert_confirm_order' in window
    # 确认后才下单，且走手动交易同一套（自动带 account=）
    assert '_sim_place_order(kind, qty, 0, symbol)' in window
    # 实盘账户 5 秒不操作自动取消
    assert 'QTimer.singleShot(5000, box.reject)' in window


# ---------------------------------------------------- 细节：布局 / 日志 / 降级
def test_real_account_checkbox_sits_next_to_remember_password():
    login = _read(LOGIN)
    assert 'rememberRow' in login
    assert 'rememberRow.addWidget(self.rememberCheckBox)' in login
    assert 'rememberRow.addWidget(self.realAccountCheckBox)' in login
    # 顺序：先「记住密码」，后「使用实盘账户」
    assert (login.index('rememberRow.addWidget(self.rememberCheckBox)')
            < login.index('rememberRow.addWidget(self.realAccountCheckBox)'))


def test_log_page_is_renamed_and_records_orders():
    panel = _read(PANEL)
    assert "('log', '运行日志')" in panel
    assert "add_page('log', '运行日志'" in panel
    window = _read(WINDOW)
    # 策略实盘的下单/成交也会被抓进「运行日志」
    assert 'def _log_new_trades' in window
    assert '[成交]' in window and '[委托]' in window
    assert 'def _account_tag' in window
    assert "_log_primed" in window


def test_multi_account_falls_back_to_pure_real_account():
    """多账户连不上时降级为纯实盘（部分快期账户不支持 TqKq+TqAccount）✓"""
    login = _read(LOGIN)
    assert 'TqMultiAccount([sim, real])' in login
    assert 'api = TqApi(real,' in login
    assert 'self.degraded = True' in login
    main = _read(MAIN)
    assert 'degraded' in main
    assert '已降级为纯实盘连接' in main


def test_strategy_runners_dedup_by_runner():
    """多 K 线策略会登记到多个 chart_id → 同一 runner 只算一个 ✓"""
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow)

    window = PylightchartsChartWindow.__new__(PylightchartsChartWindow)
    r1, r2 = object(), object()
    window._panel_strategies = {
        'a': {'runner': r1}, 'b': {'runner': r1},
        'c': {'runner': r2}, 'd': {},
    }
    assert len(window._strategy_runners()) == 2


# ------------------------------------------------ 运行日志：过滤 / 容量
def test_log_page_has_filter_and_cap():
    panel = _read(PANEL)
    assert 'filterEdit' in panel
    assert 'MAX_RECORDS = 2000' in panel
    assert 'def _render' in panel
    assert 'self._records' in panel


# ------------------------------------------------ 登录：等真实错误 / 时段提示
def test_login_waits_for_the_real_error():
    main = _read(MAIN)
    assert '_on_futures_login_soft_timeout' in main
    assert 'hard.start(300000)' in main          # 5 分钟硬超时
    assert '_non_trading_hint' in main           # 周末/非日盘提示
    login = _read(LOGIN)
    assert '_log_login_event' in login
    assert '[已超时中止]' in login               # 超时后也记录真实错误


def test_real_account_self_check_after_login():
    """勾了实盘但只挂上快期模拟 → 明确提醒 ✓"""
    main = _read(MAIN)
    assert '实盘账户未连接' in main
    assert "getattr(acc, '_broker_id'" in main


# ------------------------------------------------ 实盘账户档案（多套）
def test_real_account_profiles_roundtrip(monkeypatch):
    """保存 / 去重 / 提到最前 / 删除（**不含密码** ✓）"""
    import types

    import miniqt.app.common.real_accounts as real_accounts

    class FakeCfg:
        def __init__(self):
            self.futuresRealAccounts = types.SimpleNamespace(value='[]')

        def save(self):
            pass

    monkeypatch.setattr(real_accounts, 'cfg', FakeCfg())

    assert real_accounts.load_real_accounts() == []
    real_accounts.remember_real_account('H宏源期货', '123456')
    real_accounts.remember_real_account('Y银河期货', '888888')
    real_accounts.remember_real_account('H宏源期货', '123456')   # 重复 → 提到最前
    items = real_accounts.load_real_accounts()
    assert [i['account_id'] for i in items] == ['123456', '888888']
    assert set(items[0]) == {'broker_id', 'account_id'}     # 没有密码字段 ✓

    real_accounts.forget_real_account('Y银河期货', '888888')
    assert [i['account_id'] for i in real_accounts.load_real_accounts()] == ['123456']
    assert real_accounts.broker_display_name('H宏源期货') == '宏源期货'
    assert real_accounts.broker_display_name('Y银河期货') == '银河期货'


def test_login_has_saved_account_selector():
    login = _read(LOGIN)
    assert 'savedAccountCombo' in login
    assert '_reload_saved_accounts' in login
    assert '_on_saved_account_changed' in login
    assert '_manage_real_accounts' in login
    assert 'remember_real_account' in login
    # 档案定义搬到了 real_accounts.py，LoginWindow 仍然导出 ✓
    assert 'FUTURES_BROKERS' in login
    assert 'FUTURES_BROKERS' in _read(REAL_ACCOUNTS)


def test_real_account_management_dialog_and_settings_card():
    dialog = _read(DIALOG)
    assert 'class RealAccountsDialog' in dialog
    assert 'forget_real_account' in dialog
    assert '不保存密码' in dialog or '不会保存' in dialog
    settings = _read(SETTINGS)
    assert 'realAccountsCard' in settings
    assert '_manage_real_accounts' in settings


def test_log_page_has_copy_and_export():
    panel = _read(PANEL)
    assert 'copy_to_clipboard' in panel
    assert 'export_to_file' in panel
    assert 'FluentIcon.COPY' in panel
    assert 'FluentIcon.SAVE' in panel
    assert 'QFileDialog.getSaveFileName' in panel


# ------------------------------------------------ 记住上次交易账户
def test_account_key_and_restore():
    import types

    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow)

    sim = types.SimpleNamespace(_broker_id='快期模拟', _account_id='')
    real = types.SimpleNamespace(_broker_id='H宏源期货', _account_id='123456')
    assert PylightchartsChartWindow._account_key(sim) == '快期模拟'
    assert (PylightchartsChartWindow._account_key(real)
            == 'H宏源期货|123456')

    window = PylightchartsChartWindow.__new__(PylightchartsChartWindow)
    window._saved_account_key = lambda: 'H宏源期货|123456'
    assert window._restored_account_index([sim, real]) == 1
    window._saved_account_key = lambda: 'Y银河期货|999'
    assert window._restored_account_index([sim, real]) == 0
    window._saved_account_key = lambda: ''
    assert window._restored_account_index([sim, real]) == 0


def test_account_selection_is_persisted():
    assert 'futuresLastAccountKey' in _read(CONFIG)
    window = _read(WINDOW)
    assert 'def _account_key' in window
    assert 'def _remember_account_key' in window
    assert 'def _restored_account_index' in window
    assert 'futuresLastAccountKey' in window


# ------------------------------------------------ 日志落盘 / CSV 导出
def test_log_is_persisted_to_daily_file(monkeypatch, tmp_path):
    import miniqt.app.windows.sim_account_panel as sp

    monkeypatch.setattr(sp, 'LOG_DIR', str(tmp_path))
    sp.append_log_file('[成交] 测试一行')
    from datetime import datetime
    path = tmp_path / f'miniqt-{datetime.now():%Y-%m-%d}.log'
    assert path.exists()
    assert '[成交] 测试一行' in path.read_text(encoding='utf-8')


def test_account_panel_exports_csv():
    panel = _read(PANEL)
    assert 'def export_current_table' in panel
    assert 'csv.writer' in panel
    assert 'currentTableKey' in panel
    assert 'utf-8-sig' in panel          # Excel 打开中文不乱码 ✓


# ---------------------------------------- 实盘说明：帮助按钮 + 免责声明
def test_real_account_help_is_a_button_with_disclaimer():
    login = _read(LOGIN)
    # 原来的内联说明改成帮助按钮 ✓
    assert 'realTipLabel' not in login
    assert 'realHelpButton' in login
    assert 'show_real_account_help' in login
    assert 'class _RealAccountHelpDialog' in login
    # 帮助正文：两账号区别 + 免责声明
    assert '快期账户' in login and '实盘账户' in login
    assert '免责声明' in login
    assert '不构成任何投资建议' in login
    assert '盈亏与风险由你自行承担' in login
    assert '不承担任何责任' in login
