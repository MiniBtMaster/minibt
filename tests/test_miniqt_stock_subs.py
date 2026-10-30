"""股票订阅管理：配额腾位 / 引用保护 / 自愈重订 / 缓存长度。

回归「第一次开图正常，之后切周期 / 开别的股票就加载不了」：
* 腾位必须**优先淘汰没人持有的**（看盘窗口持有的最后才动），且要按「最久没用」
  而不是 ``set`` 的任意元素；
* 报价页 / 其它清理路径误调 ``unsubscribe`` 时**不能订掉看盘窗口持有的**；
* ``get_cur_kline`` 一直拿不到数据（网关那边已无订阅）要**自愈重订**；
* ``_store_kline`` 记**实际行数**，别用一个没补齐的短结果声称 10000 根。
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pandas as pd
import pytest

pytest.importorskip('PyQt6')

from miniqt.app.common import stock_api as mod          # noqa: E402
from miniqt.app.common.stock_api import StockApi, KLType  # noqa: E402


def _kline(n=5):
    now = pd.Timestamp('2026-01-05 09:30')
    rows = [
        {'time_key': (now + pd.Timedelta(minutes=i)).strftime(
            '%Y-%m-%d %H:%M:%S'),
         'open': 1.0, 'high': 1.0, 'low': 1.0, 'close': 1.0, 'volume': 1.0}
        for i in range(n)
    ]
    return pd.DataFrame(rows)


class FakeClient:
    def __init__(self):
        self.subs = set()
        self.calls = []
        self.fail_sub = False
        self.empty_cur = False

    def subscribe(self, codes, subtypes):
        self.calls.append(('subscribe', tuple(codes)))
        if self.fail_sub:
            return (1, '订阅额度不足')
        self.subs.update(codes)
        return (0, '')

    def unsubscribe(self, codes, subtypes):
        self.calls.append(('unsubscribe', tuple(codes)))
        for code in codes:
            self.subs.discard(code)
        return (0, '')

    def get_cur_kline(self, code, num, ktype, autype):
        self.calls.append(('cur', code, num))
        if self.empty_cur:
            return (1, '未订阅')
        return (0, _kline(min(int(num), 5)))

    def request_history_kline(self, code, start=None, end=None, ktype=None,
                              autype=None, max_count=None):
        self.calls.append(('history', code, start))
        return (0, _kline(20), None)

    def query_subscription(self):
        return (0, {'total_used': len(self.subs),
                    'remain': 100 - len(self.subs)})


def _api():
    api = StockApi(host='127.0.0.1', port=11111)
    api._client = FakeClient()
    api._initialized = True
    return api


# --------------------------------------------------------------------------- #
# 缓存长度
# --------------------------------------------------------------------------- #
def test_history_request_does_not_poison_panel_cache():
    """10000 根的历史帧不能把面板缓存记成长 10000（否则以后再也不用重取 ✗）"""
    api = _api()
    api.get_kline_serial('600519', 86400, 1000, allow_history=False)
    assert api._symbol_configs[('SH.600519', 86400)]['length'] == 1000
    api.get_kline_serial('600519', 86400, 10000, allow_history=True)
    # 面板缓存的长度仍按**数据长度**算，没被历史长帧改掉 ✓
    assert api._symbol_configs[('SH.600519', 86400)]['length'] == 1000


def test_history_window_start_is_bounded():
    """日线 10000 根的 start 不能退到 54 年前（request_history_kline 会报错 ✗）"""
    api = _api()
    api.get_kline_serial('600519', 86400, 10000, allow_history=True)
    starts = [c[2] for c in api._client.calls if c[0] == 'history']
    assert starts, api._client.calls
    years = 2026 - int(starts[0][:4])
    assert years <= 30, starts


# --------------------------------------------------------------------------- #
# 配额腾位：优先淘汰「没人持有的 + 最久没用过的」
# --------------------------------------------------------------------------- #
def test_eviction_prefers_unreferenced_lru(monkeypatch):
    monkeypatch.setattr(mod, 'MAX_KLINE_SUBSCRIPTIONS', 3)
    api = _api()
    # 600519 被看盘窗口持有
    api.acquire('600519', 86400)
    # 按插入顺序：持有点在中间，最久的是 600001 ✓
    api._subscriptions[('SH.600001', 86400)] = True
    api._subscriptions[('SH.600519', 86400)] = True
    api._subscriptions[('SH.600002', 86400)] = True

    api._ensure_subscribed('SH.600003', 86400, KLType.K_DAY)

    assert ('SH.600519', 86400) in api._subscriptions, '持有项不能被腾掉'
    assert ('SH.600001', 86400) not in api._subscriptions, '应先淘汰最旧自由项'
    assert ('SH.600003', 86400) in api._subscriptions
    assert ('unsubscribe', ('SH.600001',)) in api._client.calls


def test_pinned_never_evicted_even_when_pool_full(monkeypatch):
    """池里的订阅占满额度 → 也不淘汰它们（宁可放弃新订阅 ✗）"""
    monkeypatch.setattr(mod, 'MAX_KLINE_SUBSCRIPTIONS', 2)
    api = _api()
    api.acquire('600519', 86400)          # acquire = 进池
    api.acquire('000001', 86400)
    api._subscriptions[('SH.600519', 86400)] = True
    api._subscriptions[('SZ.000001', 86400)] = True

    api._ensure_subscribed('SH.600002', 86400, KLType.K_DAY)

    assert ('SH.600519', 86400) in api._subscriptions, '池里的不能被腾掉'
    assert ('SZ.000001', 86400) in api._subscriptions, '池里的不能被腾掉'
    assert not [c for c in api._client.calls if c[0] == 'unsubscribe']


def test_subscription_touch_moves_to_back():
    """命中已有订阅 → 挪到队尾（LRU）✓"""
    api = _api()
    api._subscriptions[('SH.600001', 86400)] = True
    api._subscriptions[('SH.600002', 86400)] = True
    api._ensure_subscribed('SH.600001', 86400, KLType.K_DAY)
    assert list(api._subscriptions) == [('SH.600002', 86400),
                                        ('SH.600001', 86400)]


# --------------------------------------------------------------------------- #
# 引用保护：别的路径不能订掉看盘窗口的订阅
# --------------------------------------------------------------------------- #
def test_unsubscribe_skips_referenced():
    api = _api()
    api.acquire('600519', 86400)
    api._subscriptions[('SH.600519', 86400)] = True
    api._subscribed_symbols[('SH.600519', 86400)] = \
        api._standardize_kline(_kline())

    api.unsubscribe('600519', 86400)          # 报价页清理误调

    assert ('SH.600519', 86400) in api._subscriptions
    assert ('SH.600519', 86400) in api._subscribed_symbols
    assert not [c for c in api._client.calls if c[0] == 'unsubscribe']


def test_release_then_unsubscribe_really_drops():
    """没进池的持有者（只靠 _refs）释放后才会真退订 ✓"""
    api = _api()
    api._refs[('SH.600519', 86400)] = 1       # 只登记引用，不进池
    api._subscriptions[('SH.600519', 86400)] = True
    api._subscribed_symbols[('SH.600519', 86400)] = \
        api._standardize_kline(_kline())

    api.release('600519', 86400)              # 引用归零 → 真退订 ✓

    assert ('SH.600519', 86400) not in api._subscriptions
    assert ('unsubscribe', ('SH.600519',)) in api._client.calls


def test_acquire_then_release_leaves_pool_when_no_window_holds():
    """看盘窗口 acquire → 进池；**最后一个窗口 release** → 出池 + 真退订 ✓"""
    api = _api()
    api.acquire('600519', 86400)
    assert ('SH.600519', 86400) in api._pinned
    api._subscriptions[('SH.600519', 86400)] = True
    api._subscribed_symbols[('SH.600519', 86400)] = \
        api._standardize_kline(_kline())

    api.release('600519', 86400)              # 关窗 / 切走 → 引用归零

    assert ('SH.600519', 86400) not in api._pinned, '没人看了 → 出池'
    assert ('SH.600519', 86400) not in api._subscriptions, '没人看了 → 退订'
    assert ('unsubscribe', ('SH.600519',)) in api._client.calls


def test_pool_keeps_while_any_window_or_layout_holds():
    """多窗口 / 多布局：同一只股票多个持有者，只到**最后一个**走了才出池 ✓"""
    api = _api()
    api.acquire('600519', 86400)              # 窗口 A（或同一窗口的一格）
    api.acquire('600519', 86400)              # 窗口 B（或另一格）
    api._subscriptions[('SH.600519', 86400)] = True
    api._subscribed_symbols[('SH.600519', 86400)] = \
        api._standardize_kline(_kline())

    api.release('600519', 86400)              # A 关窗 / 切走
    assert ('SH.600519', 86400) in api._pinned, 'B 还在看 → 留池'
    assert ('SH.600519', 86400) in api._subscriptions
    assert not [c for c in api._client.calls if c[0] == 'unsubscribe']

    api.release('600519', 86400)              # B 也走了 → 出池
    assert ('SH.600519', 86400) not in api._pinned
    assert ('SH.600519', 86400) not in api._subscriptions
    assert ('unsubscribe', ('SH.600519',)) in api._client.calls


def test_unsubscribe_force_bypasses_guard():
    api = _api()
    api.acquire('600519', 86400)
    api._subscriptions[('SH.600519', 86400)] = True
    api.unsubscribe('600519', 86400, force=True)
    assert ('SH.600519', 86400) not in api._subscriptions


# --------------------------------------------------------------------------- #
# 自愈重订
# --------------------------------------------------------------------------- #
def test_resubscribe_on_total_failure():
    """一次都没拿到 → 强制重订再试（原来直接返回空 → 图只剩测试数据 ✗）"""
    api = _api()
    api._client.empty_cur = True
    api.get_kline_serial('600519', 86400, 5, allow_history=False)
    kinds = [c[0] for c in api._client.calls]
    assert kinds.count('subscribe') >= 2, api._client.calls
    assert kinds.count('unsubscribe') >= 1, api._client.calls


def test_history_window_is_bounded():
    """日线 10000 根不能换算成 54 年窗口（会报错 / 很慢 ✗）"""
    assert mod.MAX_HISTORY_BARS <= 10000
    assert mod.MAX_HISTORY_DAYS <= 20000


def test_market_watch_logs_pool_on_open_switch_close():
    """看盘窗口：打开 / 切换周期 / 关闭都打印订阅池（用户要求 ✓）"""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / 'miniqt' / 'app' /
           'windows' / 'pylightcharts_market_watch.py').read_text(
               encoding='utf-8')
    assert "self._log_stock_pool('打开看盘窗口')" in src
    assert "self._log_stock_pool('打开看盘窗口完成')" in src
    assert "self._log_stock_pool('切换周期')" in src
    assert "self._log_stock_pool('关闭看盘窗口')" in src


def test_pool_log_prints_both_sets(capsys):
    api = _api()
    api.acquire('600519', 86400)
    api._subscriptions[('SH.600519', 86400)] = True
    api.log_pinned('测试')
    out = capsys.readouterr().out
    assert '看盘窗口持有 1/100' in out
    assert '已订阅   1/100' in out


def test_main_reports_loaded_code_paths():
    """启动时打印实际加载的包路径 —— 防止“改了仓库却在跑 site-packages 旧包”✗"""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / 'miniqt' /
           '__main__.py').read_text(encoding='utf-8')
    assert 'def _report_code_paths' in src
    assert '_report_code_paths()' in src
    assert '不是仓库里的那份' in src


def test_fetch_frame_logs_branch_once():
    """``_fetch_frame`` 每个 (合约,周期,根数,stock) 打一次分支日志 ✓"""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / 'miniqt' / 'app' /
           'windows' / 'pylightcharts_market_watch.py').read_text(
               encoding='utf-8')
    assert '_fetch_logged' in src
    assert 'stock_api=' in src
    assert 'tq_api=' in src


def test_chart_window_has_probe():
    """图表探针：回报主图 K 线根数（Qt 取不到返回值 → 走 callbackFunction）✓"""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / 'miniqt' / 'app' /
           'windows' / 'pylightcharts_window.py').read_text(encoding='utf-8')
    assert 'def probe(self' in src
    assert '.data().length' in src
    assert '空图！' in src

    market = (pathlib.Path(__file__).resolve().parents[1] / 'miniqt' / 'app' /
              'windows' / 'pylightcharts_market_watch.py').read_text(
                  encoding='utf-8')
    assert '.probe(' in market
    assert '建图后' in market
    assert '切周期后' in market


def test_market_watch_releases_old_symbol_on_switch():
    """换合约：本窗口不再看旧合约 → 释放它的订阅（别的窗口 / 格子还在就不退 ✓）"""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / 'miniqt' / 'app' /
           'windows' / 'pylightcharts_market_watch.py').read_text(
               encoding='utf-8')
    assert 'def _release_symbol_subscriptions' in src
    assert 'self._release_symbol_subscriptions(old_symbol)' in src
    assert 'old_symbol not in self.contracts' in src
