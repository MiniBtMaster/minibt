# coding: utf-8
"""股票数据源 mootdx → 富途 futu-api 的源码约束与单测。

* 不需要真 FutuOpenD 网关；
* 不需要安装 futu（缺依赖时 ``stock_api`` 会降级，用假客户端驱动）；
* 覆盖：代码格式转换、K 线标准化、``get_kline_serial`` / ``wait_update`` /
  ``unsubscribe`` / 订阅去重 / 北交所降级。

    pytest tests/test_miniqt_futu_api.py
"""
from __future__ import annotations

import pathlib
import sys
import types

import pandas as pd
import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import miniqt.app.common.stock_api as stock_api  # noqa: E402

STOCK_API = REPO / 'miniqt' / 'app' / 'common' / 'stock_api.py'
LOGIN = REPO / 'miniqt' / 'app' / 'login' / 'LoginWindow.py'


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding='utf-8')


# --------------------------------------------------------------- 源码约束
def test_stock_api_no_longer_uses_mootdx():
    source = _read(STOCK_API)
    # 只约束“功能上不再用 mootdx”，历史迁移注释可以提
    assert 'from mootdx' not in source
    assert 'import mootdx' not in source
    assert 'Quotes.factory' not in source
    assert 'from futu import' in source
    assert '_to_futu_code' in source
    assert 'validate_connection' in source
    assert 'PERIOD_TO_FREQUENCY' in source          # 兼容旧调用
    assert 'OpenQuoteContext' in source


def test_login_window_uses_futu_gateway():
    source = _read(LOGIN)
    assert 'from mootdx' not in source
    assert 'import mootdx' not in source
    assert 'Quotes.factory' not in source
    assert 'HQ_HOSTS' not in source
    assert 'ServerTestThread' not in source
    assert 'class GatewayTestThread' in source
    assert 'DEFAULT_GATEWAY_HOST' in source
    assert 'DEFAULT_GATEWAY_PORT' in source
    assert 'validate_connection' in source
    assert 'FutuOpenD' in source


def test_config_defaults_to_futu_gateway():
    source = _read(REPO / 'miniqt' / 'app' / 'common' / 'config.py')
    assert '"127.0.0.1"' in source
    assert '11111' in source
    # 旧 mootdx 端口应做迁移
    assert '7709' in source


# --------------------------------------------------------- _to_futu_code
@pytest.mark.parametrize('symbol,expected', [
    ('600000', 'SH.600000'),
    ('SH.600000', 'SH.600000'),
    ('sh.600000', 'SH.600000'),
    ('600000.SH', 'SH.600000'),
    ('000001', 'SZ.000001'),
    ('sz.000001', 'SZ.000001'),
    ('000001.SZ', 'SZ.000001'),
    ('300750', 'SZ.300750'),
    ('688001', 'SH.688001'),
    ('510300', 'SH.510300'),
    # 天勤风格前缀（旧代码里会出现 SSE/SZSE）
    ('SSE.600478', 'SH.600478'),
    ('sse.600000', 'SH.600000'),
    ('SHSE.600000', 'SH.600000'),
    ('SZSE.000001', 'SZ.000001'),
    ('', ''),
])
def test_to_futu_code(symbol, expected):
    api = stock_api.StockApi()
    assert api._to_futu_code(symbol) == expected


def test_to_futu_code_rejects_beijing():
    api = stock_api.StockApi()
    # 北交所（8/4 开头）futu 不支持 → 返回空串
    assert api._to_futu_code('830799') == ''
    assert api._to_futu_code('430047') == ''
    assert api._to_futu_code('BJ.830799') == ''
    assert api._to_futu_code('BSE.830799') == ''


# ------------------------------------------------------- K 线标准化
def test_standardize_kline_from_futu():
    api = stock_api.StockApi()
    raw = pd.DataFrame({
        'code': ['SH.600000'] * 2,
        'time_key': ['2026-10-13 09:30:00', '2026-10-13 09:31:00'],
        'open': [1.0, 2.0],
        'high': [2.0, 3.0],
        'low': [0.5, 1.5],
        'close': [1.5, 2.5],
        'volume': [10, 20],
        'turnover': [1.0, 2.0],
    })
    df = api._standardize_kline(raw)
    assert list(df.columns) == ['datetime', 'open', 'high', 'low', 'close',
                                'volume']
    assert len(df) == 2
    assert df['datetime'].dtype == 'int64'
    # 纳秒时间戳（19 位）
    assert int(df['datetime'].iloc[0]) > 10 ** 18
    assert df['datetime'].is_monotonic_increasing


def test_standardize_kline_fills_missing_columns():
    api = stock_api.StockApi()
    raw = pd.DataFrame({'time_key': ['2026-10-13 09:30:00'], 'close': [1.0]})
    df = api._standardize_kline(raw)
    assert list(df.columns) == ['datetime', 'open', 'high', 'low', 'close',
                                'volume']
    assert float(df['open'].iloc[0]) == 0.0


# ---------------------------------------------------- 假客户端驱动接口
class _FakeClient:
    """模拟 futu OpenQuoteContext（同步查询）"""

    def __init__(self):
        self.subscribed = []       # [(codes, subtypes)]
        self.unsubscribed = []
        self.close_called = False
        self.cur_kline_calls = 0
        self._seq = 0

    def subscribe(self, codes, subtypes):
        self.subscribed.append((list(codes), list(subtypes)))
        return 0, None

    def unsubscribe(self, codes, subtypes):
        self.unsubscribed.append((list(codes), list(subtypes)))
        return 0, None

    def get_cur_kline(self, code, num, ktype, autype=None):
        self._seq += 1
        self.cur_kline_calls += 1
        base = self._seq
        df = pd.DataFrame({
            'code': [code] * 2,
            'time_key': ['2026-10-13 09:30:00', '2026-10-13 09:31:00'],
            'open': [1.0, 2.0],
            'high': [2.0, 3.0],
            'low': [0.5, 1.5],
            'close': [1.5, float(base)],
            'volume': [10, 20],
        })
        return 0, df

    def get_market_snapshot(self, codes):
        codes = list(codes)
        return 0, pd.DataFrame({
            'code': codes,
            'last_price': [1.0] * len(codes),
            'prev_close_price': [1.0] * len(codes),
        })

    def close(self):
        self.close_called = True


@pytest.fixture
def fake_api(monkeypatch):
    monkeypatch.setattr(stock_api, 'AuType',
                        types.SimpleNamespace(QFQ='qfq'))
    monkeypatch.setattr(stock_api.StockApi, 'PERIOD_TO_KLTYPE',
                        {60: 'K_1M', 300: 'K_5M', 86400: 'K_DAY'})
    monkeypatch.setattr(stock_api.StockApi, 'KLTYPE_TO_SUBTYPE',
                        {'K_1M': 'K_1M', 'K_5M': 'K_5M', 'K_DAY': 'K_DAY'})
    api = stock_api.StockApi(host='127.0.0.1', port=11111)
    api._client = _FakeClient()
    api._initialized = True
    return api


def test_get_kline_serial_subscribes_and_caches(fake_api):
    df = fake_api.get_kline_serial('600000', 60, 800)
    assert list(df.columns) == ['datetime', 'open', 'high', 'low', 'close',
                                'volume']
    assert len(df) == 2
    # 首次订阅了一次
    assert fake_api._client.subscribed == [(['SH.600000'], ['K_1M'])]
    assert fake_api.is_subscribed('600000')

    # 第二次取走缓存 → 不再重复订阅
    fake_api.get_kline_serial('600000', 60, 800)
    assert len(fake_api._client.subscribed) == 1


def test_cache_is_length_aware(fake_api):
    """先小的后大的：缓存要按长度重取（spark 不能拖累主图 ✗）"""
    fake_api.get_kline_serial('600000', 60, 120)
    n1 = fake_api._client.cur_kline_calls
    assert n1 >= 1
    # 同样长度 → 命中缓存，不再取
    fake_api.get_kline_serial('600000', 60, 120)
    assert fake_api._client.cur_kline_calls == n1
    # 更长 → 必须重取
    fake_api.get_kline_serial('600000', 60, 1000)
    assert fake_api._client.cur_kline_calls > n1
    assert fake_api._symbol_configs[('SH.600000', 60)]['length'] == 1000
    # 再要短的 → 现有 1000 根缓存够用，不再取
    n2 = fake_api._client.cur_kline_calls
    fake_api.get_kline_serial('600000', 60, 120)
    assert fake_api._client.cur_kline_calls == n2


def test_get_kline_serial_default_length_is_1000(fake_api):
    fake_api.get_kline_serial('600000', 60)
    assert fake_api._symbol_configs[('SH.600000', 60)]['length'] == 1000


def test_get_kline_serial_empty_when_disconnected():
    api = stock_api.StockApi()
    df = api.get_kline_serial('600000', 60, 800)
    assert df.empty
    assert list(df.columns) == ['datetime', 'open', 'high', 'low', 'close',
                                'volume']


def test_wait_update_refreshes_cache(fake_api, monkeypatch):
    fake_api.get_kline_serial('600000', 60, 800)
    before = float(fake_api.get_quote('600000')['close'].iloc[-1])
    # 绕过交易时段判断，强制走刷新分支
    monkeypatch.setattr(fake_api, 'is_trading_time', lambda: True)
    updated = fake_api.wait_update()
    assert updated is True
    after = float(fake_api.get_quote('600000')['close'].iloc[-1])
    assert after != before


def test_wait_update_outside_trading_hours_returns_false(fake_api,
                                                         monkeypatch):
    fake_api.get_kline_serial('600000', 60, 800)
    monkeypatch.setattr(fake_api, 'is_trading_time', lambda: False)
    assert fake_api.wait_update() is False


def test_unsubscribe_removes_cache_and_gateway(fake_api):
    fake_api.get_kline_serial('600000', 60, 800)
    fake_api.unsubscribe('600000', 60)
    assert not fake_api.is_subscribed('600000')
    assert fake_api.get_quote('600000') is None
    assert fake_api._client.unsubscribed == [(['SH.600000'], ['K_1M'])]


def test_close_releases_gateway(fake_api):
    fake_api.get_kline_serial('600000', 60, 800)
    client = fake_api._client
    fake_api.close()
    assert client.close_called is True
    assert fake_api._client is None
    assert fake_api._initialized is False


def test_snapshot_uses_market_snapshot(fake_api):
    df = fake_api.snapshot('SH.600000')
    assert df is not None and 'last_price' in df.columns


def test_snapshot_to_quote_fields():
    row = {
        'code': 'SZ.000001', 'update_time': '2026-10-13 15:00:00',
        'last_price': 11.57, 'prev_close_price': 11.73,
        'bid_price': 11.57, 'ask_price': 11.58,
        'bid_vol': 100, 'ask_vol': 200, 'volume': 1000,
        'open_price': 11.73, 'high_price': 11.77, 'low_price': 11.55,
        'price_spread': 0.01,
    }
    q = stock_api.StockApi._snapshot_to_quote(row)
    assert q.last_price == 11.57
    assert q.pre_settlement == 11.73 and q.pre_close == 11.73
    assert q.bid_price1 == 11.57 and q.ask_price1 == 11.58
    assert q.bid_volume1 == 100 and q.ask_volume1 == 200
    assert q.open == 11.73 and q.highest == 11.77 and q.lowest == 11.55
    assert q.datetime == '2026-10-13 15:00:00'
    assert q.trading_time.day[0] == ['09:30:00', '11:30:00']


def test_price_limits_by_board_and_st():
    """涨/跌停：主板±10%、创业板/科创板±20%、ST±5%（futu 不提供 → 自算 ✓）"""
    L = stock_api.StockApi._price_limits
    assert L(10.0, 'SH.600000', '浦发银行') == (11.0, 9.0)
    assert L(10.0, 'SZ.300750', '宁德时代') == (12.0, 8.0)
    assert L(10.0, 'SH.688001', '华兴源创') == (12.0, 8.0)
    assert L(10.0, 'SH.600000', 'ST某某') == (10.5, 9.5)
    assert L(None, 'SH.600000', 'x') == (None, None)
    assert L(0, 'SH.600000', 'x') == (None, None)


def test_spark_fetch_skips_stocks_and_releases_subs():
    """报价页：股票走势不再订阅 K 线（额度），且离开当前页要退订 ✓"""
    source = (REPO / 'miniqt' / 'app' / 'view' /
              'market_quote_preview.py').read_text(encoding='utf-8')
    spark = source.split('def _maybe_fetch_spark', 1)[1].split('\n    def ', 1)[0]
    assert '_is_futu_symbol(s)' in spark          # futu 供数（股票/期权）跳过 K 线订阅
    assert 'def _release_offpage_subs' in source
    assert 'unsubscribe(symbol, 60)' in source
    assert 'def _on_overview_closed' in source     # 气泡关闭也退订


def test_market_watch_releases_subscriptions_on_close():
    """看盘窗口关闭 → 退掉本窗口股票 K 线订阅（否则订阅额度只增不减 ✗）"""
    source = (REPO / 'miniqt' / 'app' / 'windows' /
              'pylightcharts_market_watch.py').read_text(encoding='utf-8')
    assert 'def _release_stock_subscriptions' in source
    assert 'unsubscribe(symbol, cycle)' in source
    close = source.split('def closeEvent', 1)[1]
    assert '_release_stock_subscriptions' in close


def test_stock_name_map_from_futu(fake_api, monkeypatch):
    """股票名称表：futu get_stock_basicinfo → {code: name}，退市不入表 ✓"""
    monkeypatch.setattr(stock_api, '_FUTU_AVAILABLE', True)
    monkeypatch.setattr(stock_api, 'Market',
                        types.SimpleNamespace(SH='SH', SZ='SZ'))

    def fake_basicinfo(market):
        if market == 'SH':
            return 0, pd.DataFrame([
                {'code': 'SH.600000', 'name': '浦发银行', 'delisting': False},
                {'code': 'SH.600001', 'name': '退市股', 'delisting': True},
            ])
        return 0, pd.DataFrame([
            {'code': 'SZ.000001', 'name': '平安银行', 'delisting': False},
        ])

    fake_api._client.get_stock_basicinfo = fake_basicinfo
    fake_api._name_map = None
    names = fake_api.stock_name_map()
    assert names.get('SH.600000') == '浦发银行'
    assert names.get('SZ.000001') == '平安银行'
    assert 'SH.600001' not in names                # 退市 → 过滤


def test_get_quote_list_from_snapshot(fake_api):
    quotes = fake_api.get_quote_list(['600000', '000001'])
    assert len(quotes) == 2
    assert all(q is not None and q.last_price == 1.0 for q in quotes)


def test_subscription_reference_counting(fake_api):
    """多窗口共享：引用计数归零（没有窗口再看）才退订并出池 ✓"""
    fake_api.get_kline_serial('600000', 60, 120)
    fake_api.acquire('600000', 60)
    fake_api.acquire('600000', 60)
    assert fake_api.is_in_use('600000')
    assert fake_api.is_in_use('600000', 60)
    assert fake_api.pinned_keys()                 # 有窗口在看 → 在池
    fake_api.release('600000', 60)
    assert fake_api.is_in_use('600000')          # 还有一个持有者
    assert fake_api.pinned_keys()                 # 仍在池
    fake_api.release('600000', 60)
    assert not fake_api.is_in_use('600000')      # 归零
    # ★ 没有任何看盘窗口再看它 → **出池 + 真退订**
    assert not fake_api.pinned_keys()
    assert not fake_api.is_subscribed('600000')


def test_market_watch_acquires_and_releases():
    """看盘窗口：开图登记 acquire、关窗 release（多窗口共享 ✓）"""
    source = (REPO / 'miniqt' / 'app' / 'windows' /
              'pylightcharts_market_watch.py').read_text(encoding='utf-8')
    assert 'def _acquire_stock' in source
    assert 'api.acquire(symbol,' in source
    assert 'api.release(symbol, cycle)' in source
    assert 'is_in_use(symbol, cycle)' in source


def test_preview_skips_in_use_before_unsubscribe():
    """预览退订前先 is_in_use —— 看盘里打开的股票不退 ✓"""
    source = (REPO / 'miniqt' / 'app' / 'view' /
              'market_quote_preview.py').read_text(encoding='utf-8')
    block = source.split('def _release_offpage_subs', 1)[1].split(
        '\n    def ', 1)[0]
    assert 'api.is_in_use(symbol)' in block


def test_ticker_tape_only_visible_symbols():
    """Ticker Tape：**股票**只播可视（订阅受限）；**期货**无限制 → 整页 ✓"""
    source = (REPO / 'miniqt' / 'app' / 'view' /
              'market_quote_preview.py').read_text(encoding='utf-8')
    block = source.split('def _on_visible_keys', 1)[1].split('\n    def ', 1)[0]
    assert 'self._refresh_tape_symbols()' in block
    helper = source.split('def _refresh_tape_symbols', 1)[1].split(
        '\n    def ', 1)[0]
    assert 'self._visible_symbols' in helper      # 股票 → 可视
    assert 'self._page_symbols' in helper         # 期货 → 整页
    assert 'def _page_is_stock' in source


def test_market_watch_releases_old_cycle_on_switch():
    """看盘切周期 → 退旧周期（订阅按 (股票, 周期) 维度 ✓）"""
    source = (REPO / 'miniqt' / 'app' / 'windows' /
              'pylightcharts_market_watch.py').read_text(encoding='utf-8')
    assert 'def _set_cycle' in source
    assert 'def _release_cycle_subscriptions' in source
    assert 'api.release(symbol, cyc)' in source
    assert 'int(cyc) != cycle' in source


def test_quote_preview_routes_stocks_to_futu():
    """行情报价页：股票走 futu、期货走天勤，并把行情源记到日志 ✓"""
    source = (REPO / 'miniqt' / 'app' / 'view' /
              'market_quote_preview.py').read_text(encoding='utf-8')
    assert 'def _quote_api_for' in source
    assert 'stock_api' in source
    assert '行情源：' in source
    assert 'get_quote_list' in source


def test_overview_left_click_gates_by_type():
    """Symbol Overview 左击门槛：股票→futu、非股票→天勤（不再硬性要求 tq_api）✗"""
    source = (REPO / 'miniqt' / 'app' / 'view' /
              'market_quote_preview.py').read_text(encoding='utf-8')
    block = source.split('def _on_row_left_click', 1)[1].split('\n    def ', 1)[0]
    assert '_quote_api_for(symbol)' in block


def test_unsupported_symbol_returns_empty(fake_api):
    df = fake_api.get_kline_serial('830799', 60, 800)
    assert df.empty
    assert fake_api._client.subscribed == []


# ---------------------------------------------------- 历史 K 线（>1000 根）
class _FakeHistoryClient(_FakeClient):
    def __init__(self):
        super().__init__()
        self.last_history_kwargs = {}

    def request_history_kline(self, code, start=None, end=None, ktype=None,
                              autype=None, max_count=None):
        self.last_history_kwargs = {'start': start, 'end': end,
                                    'max_count': max_count}
        n = 1500
        times = pd.date_range('2026-01-01', periods=n, freq='min')
        df = pd.DataFrame({
            'code': [code] * n,
            'time_key': times.strftime('%Y-%m-%d %H:%M:%S'),
            'open': list(range(n)),
            'high': list(range(n)),
            'low': list(range(n)),
            'close': list(range(n)),
            'volume': [1] * n,
        })
        return 0, df, None


def test_get_kline_serial_over_1000_uses_history(fake_api):
    fake_api._client = _FakeHistoryClient()
    df = fake_api.get_kline_serial('600000', 60, 1500)
    # 实际要到 1500 根，只留最近 1500（此处正好 1500）
    assert len(df) == 1500
    assert df['datetime'].is_monotonic_increasing


def test_history_request_passes_end(fake_api):
    """★ 必须显式传 end：否则 futu 把 end=start+365 天，只回约一年 ✗"""
    client = _FakeHistoryClient()
    fake_api._client = client
    fake_api.get_kline_serial('600000', 86400, 1500)
    assert client.last_history_kwargs.get('end')          # 有值
    assert client.last_history_kwargs.get('start')
    assert client.last_history_kwargs.get('max_count') is None


# ---------------------------------------------------------- 登录框冒烟
import os                                                       # noqa: E402
import subprocess                                               # noqa: E402


def _run(script: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONIOENCODING'] = 'utf-8'
    result = subprocess.run(
        [sys.executable, '-c', script], cwd=str(REPO), env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=180)
    if result.returncode != 0:
        raise AssertionError(f'子进程失败（{result.returncode}）:\n'
                             f'{result.stdout}\n{result.stderr}')
    return result


def test_stock_login_window_smoke():
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "from PyQt6.QtWidgets import QApplication, QWidget\n"
        "app = QApplication([])\n"
        "host = QWidget(); host.resize(800, 600); host.show()\n"
        "from miniqt.app.login.LoginWindow import LoginWindow\n"
        "w = LoginWindow(parent=host, is_stock=True)\n"
        "print('HOST', w.hostEdit.text())\n"
        "print('PORT', w.portEdit.text())\n"
        "print('BTN', w.testServerBtn.text())\n"
        "print('HELP', w.helpButton.text())\n"
        "print('SUB', w.subtitleLabel.text())\n"
        "print('STATUS', w.gatewayStatusLabel.text())\n"
    )
    out = _run(script).stdout
    assert 'HOST 127.0.0.1' in out
    assert 'PORT 11111' in out
    assert 'BTN 测试连接' in out
    assert 'HELP 帮助' in out
    assert 'FutuOpenD' in out
    assert '未连接' in out


def test_login_window_gateway_status_hint():
    """登录页有「网关连通/权限状态」提示条（可更新）"""
    source = _read(LOGIN)
    assert 'gatewayStatusLabel' in source
    assert 'def _set_gateway_status' in source
    assert 'def _on_gateway_field_changed' in source
    assert '网关可用' in source
    assert '连接失败' in source


def test_login_window_has_futu_help():
    """股票登录窗口有「帮助」按钮 → FutuOpenD 连接教程 ✓"""
    source = _read(LOGIN)
    assert 'class _FutuHelpDialog' in source
    assert 'FUTU_SETUP_URL' in source
    assert 'openapi.futunn.com' in source
    assert 'def show_futu_help' in source
    assert 'self.helpButton' in source
    assert '保持客户端处于登录状态' in source


def test_protobuf_too_new_detection(monkeypatch):
    """新版 protobuf 会被识别（futu 的旧 _pb2 需要兼容处理）"""
    import importlib.metadata as md

    def fake_version(name):
        return fake_version.value

    monkeypatch.setattr(md, 'version', fake_version)
    for raw, expected in (('3.19.6', False), ('3.20.3', False),
                          ('3.21.0', True), ('4.25.0', True),
                          ('6.33.6', True)):
        fake_version.value = raw
        assert stock_api._protobuf_too_new() is expected, raw


def test_futu_missing_deps_reports_packages(monkeypatch):
    """缺依赖时能报出包名（给登录页展示）"""
    import importlib

    real_import = importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name == 'Crypto':
            raise ImportError('no Crypto')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, 'import_module', fake_import)
    missing = stock_api._futu_missing_deps()
    assert 'pycryptodome' in missing


def test_stock_default_cycle_is_daily():
    """股票开图默认周期 = 日线（分钟数据源不稳，用户要求 ✓）"""
    source = _read(REPO / 'miniqt' / 'app' / 'view' / 'main_window.py')
    assert 'cycle: int = None' in source
    assert '86400 if is_stock else 60' in source


def test_futu_client_calls_serialized():
    """futu 客户端调用要串行化（SDK 不是线程安全的，主线程+工作线程并发会死锁）✓"""
    source = _read(STOCK_API)
    assert 'class _ThreadSafeClient' in source
    assert '_client_lock' in source
    assert 'self._client = _ThreadSafeClient(' in source
    # 订阅配额腾位的**网络退订**已移到 _lock 之外（持锁做网络会冻结界面）
    assert 'stale' in source


def test_stock_wait_update_runs_off_main_thread():
    """``StockApiQTimer`` 的 ``wait_update`` 要在后台线程跑（主线程会冻结界面）✓"""
    source = _read(REPO / 'miniqt' / 'app' / 'common' / 'stock_api_qtimer.py')
    assert 'import threading' in source
    assert 'def _run_wait_update' in source
    assert 'threading.Thread' in source
    # 主线程里不再直接调 wait_update（只有后台线程的目标函数里调）
    assert source.count('self.stock_api.wait_update()') == 1


def test_wait_update_only_active_subscriptions():
    """``wait_update`` 只刷新当前订阅，不再遍历整个缓存（避免爆发式请求）✓"""
    source = _read(STOCK_API)
    block = source.split('def wait_update', 1)[1].split('\n    def ', 1)[0]
    assert 'for key in self._subscriptions' in block


def test_get_kline_serial_allow_history_opt_in():
    """``allow_history=False`` → 主线程不退化到历史 K 线（切周期不冻界面）✓"""
    source = _read(STOCK_API)
    assert 'allow_history: bool = True' in source
    assert 'if len(best) < wanted and allow_history:' in source
    assert 'if not allow_history:' in source
    # 看盘窗口：默认**不补历史**（开图 / 切周期快）；只有「无限历史」往左翻
    # 才显式 ``allow_history=True``（不再按线程判断 ✓）
    market = _read(REPO / 'miniqt' / 'app' / 'windows' /
                   'pylightcharts_market_watch.py')
    assert 'allow_history=allow_history' in market
    assert 'allow_history=True' in market
    assert 'threading.current_thread()' not in market
    assert 'allow_history=False)' in market


def test_get_kline_serial_stores_cache():
    """取到的 K 线必须写缓存（``_store_kline``）—— 否则图永远等不到数据 ✗"""
    source = _read(STOCK_API)
    assert 'def _store_kline' in source
    gk = source.split('def get_kline_serial', 1)[1].split('\n    def ', 1)[0]
    assert '_store_kline(' in gk


def test_bootstrap_worker_finished_runs_on_main_thread():
    """``QThread.finished`` 不能直接连 lambda 调 ``_resume_tq_qtimer`` —— 那在

    工作线程里跑，``QTimer.start()`` 跨线程不生效 → tq 泵永远恢复不了 ✗。
    改成 emit 信号 queued 回主线程 ✓
    """
    market = _read(REPO / 'miniqt' / 'app' / 'windows' /
                   'pylightcharts_market_watch.py')
    assert '_bootstrapWorkerDone = pyqtSignal(object)' in market
    assert 'self._bootstrapWorkerDone.connect(self._on_bootstrap_finished)' in market
    assert 'self._bootstrapWorkerDone.emit(w)' in market
    assert 'lambda w=worker: self._on_bootstrap_finished(w)' not in market
