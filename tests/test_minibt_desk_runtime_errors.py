"""策略 `next()` 运行时报错 / 指标算不出来时的错误处理 ✓

用户 2026-10-30 要求：

1. **策略在运行时**（每拍 `advance()`）`next()` 报错：图表 / 指标**不受影响**
   （不关页、不清线），第一次弹窗提醒、之后只在终端 / 运行日志里提醒，
   让用户「删除策略 → 改代码 → 重新加到图表」；
2. **指标算不出来**（参数非法 / 脚本报错 / 数据不够）：弹窗提醒，
   并且**指标不加载上图表**（把刚加的那一条撤回去）。
"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, user_prefs
    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.log_to_stdout = False
    desk.log_to_ui = False
    return desk


def _patches(desk):
    import json
    out = []
    for script in desk.sent:
        text = str(script)
        if text.startswith('window.__desk.applyPatch('):
            out.append(json.loads(text[len('window.__desk.applyPatch('):-2]))
    return out


# ------------------------------------------------------------ 策略 next 报错
class _BadRunner:
    """`advance()` 永远失败（模拟用户 `next()` 里抛异常 ✓）"""

    strategy = object()
    error = 'ValueError: boom'
    traceback = 'Traceback (most recent call last):\n'
    '  File "x.py", line 9, in next\nValueError: boom'

    def advance(self, frames=None):
        return False

    def update_symbols(self):
        return []


def test_strategy_next_error_keeps_chart(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    tab = 'SHFE.demo01'
    desk.tabs[tab] = {
        'cycle': 60,
        'strategy': {'name': 'bad_st', 'path': '/tmp/bad.py'},
        'strategy_items': [{'key': 'editor:bad:line:0', 'label': 'ma'}],
        'strategy_runner': _BadRunner(),
        'layout': {'cols': 2, 'rows': 1, 'symbols': [tab, 'SHFE.demo02'],
                   'cells': [{'symbol': tab, 'indicators': [],
                              'strategy_items': [{'key': 'a'}]},
                             {'symbol': 'SHFE.demo02', 'indicators': [],
                              'strategy_items': [{'key': 'b'}]}]},
    }
    info = desk.tabs[tab]

    desk._update_strategy_items(tab, info, frame=None, main_symbol=tab)

    kinds = [item['type'] for item in _patches(desk)]
    # 第一次：弹窗提醒（不再悄悄吞掉 ✓）
    assert 'alert' in kinds, kinds
    alert = [item for item in _patches(desk) if item['type'] == 'alert'][-1]
    assert 'ValueError: boom' in alert['message']
    assert '删除策略' in alert['detail'] or '加到图表' in alert['detail']
    # 图表 / 策略线 / 布局都**不受影响**（没关页、没清线 ✓）
    assert tab in desk.tabs
    assert info['strategy_items'] == [{'key': 'editor:bad:line:0',
                                       'label': 'ma'}]
    assert info['layout']['cells'][0]['strategy_items'] == [{'key': 'a'}]
    assert info['layout']['cells'][1]['strategy_items'] == [{'key': 'b'}]
    assert info['_strat_error'] == 'ValueError: boom'

    # 第二次：不再弹窗（只打印 / 写日志 ✓）
    desk.sent.clear()
    info['_strat_at'] = 0.0
    desk._update_strategy_items(tab, info, frame=None, main_symbol=tab)
    assert 'alert' not in [item['type'] for item in _patches(desk)]
    assert info['strategy_items'] == [{'key': 'editor:bad:line:0',
                                       'label': 'ma'}]


def test_strategy_error_flags_cleared_on_remove(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    tab = 'SHFE.demo01'
    desk.tabs[tab] = {'strategy': {'name': 'bad_st'},
                      'strategy_items': [{'key': 'a'}],
                      '_strat_error_shown': True,
                      '_strat_error': 'boom'}
    desk._remove_strategy_of(tab)
    info = desk.tabs[tab]
    for key in ('strategy', 'strategy_items', '_strat_error',
                '_strat_error_shown', '_strat_error_at'):
        assert not info.get(key), key


# ------------------------------------------------------- 指标算不出来 → 不加
def test_indicator_failure_is_not_added(tmp_path, monkeypatch):
    """`add_indicator` 时算不出来 → 撤掉 + 弹窗（图上不能留半条 ✗）"""
    from minibt.desk import indicators as ind

    def fake_compute(symbol, frame, selected, limit=600, errors=None):
        if errors is not None:
            errors['BAD'] = 'ValueError: boom'
        return {'type': 'indicator', 'symbol': symbol, 'items': []}

    monkeypatch.setattr(ind, 'CATALOG', [{'key': 'BAD', 'label': 'BAD',
                                          'overlay': True, 'params': []}])
    monkeypatch.setattr(ind, 'compute', fake_compute)

    desk = _desk(tmp_path, monkeypatch)
    tab = 'SHFE.demo01'
    desk.tabs[tab] = {'cycle': 60, 'indicators': [{'key': 'MA'}]}

    desk._on_add_indicator({'symbol': tab, 'key': 'BAD', 'cell': 0})

    info = desk.tabs[tab]
    assert [item['key'] for item in info['indicators']] == ['MA']   # 没加上 ✓
    patches = _patches(desk)
    kinds = [item['type'] for item in patches]
    assert 'toast' in kinds
    toast = [item for item in patches if item['type'] == 'toast'][-1]
    assert toast['level'] == 'error' and '加不上图' in toast['text']


def test_local_indicator_failure_is_not_added(tmp_path, monkeypatch):
    from minibt.desk import indicators as ind

    def fake_compute(symbol, frame, selected, limit=600, errors=None):
        if errors is not None:
            errors['BAD'] = 'ValueError: boom'
        return {'type': 'indicator', 'symbol': symbol, 'items': []}

    monkeypatch.setattr(ind, 'CATALOG', [{'key': 'BAD', 'label': 'BAD',
                                          'overlay': True, 'params': []}])
    monkeypatch.setattr(ind, 'compute', fake_compute)

    desk = _desk(tmp_path, monkeypatch)
    desk._on_local_add_indicator({'symbol': 'test', 'key': 'BAD', 'cell': 0})

    store = desk.local_store()
    keys = [item.get('key') for item in store.indicators('test', 0)]
    assert 'BAD' not in keys                        # 没写进去 ✓
    toast = [item for item in _patches(desk) if item['type'] == 'toast']
    assert toast and toast[-1]['level'] == 'error'


def test_indicators_compute_reports_errors(monkeypatch):
    """`indicators.compute(..., errors=)` 要把失败的 key 填进去 ✓"""
    from minibt.desk import indicators as ind

    def boom(key, frame, close, stamps, params):
        raise ValueError(f'{key} boom')

    monkeypatch.setattr(ind, '_build', boom)
    frame = pytest.importorskip('pandas').DataFrame({
        'datetime': [1, 2], 'open': [1.0, 2.0], 'high': [1.0, 2.0],
        'low': [1.0, 2.0], 'close': [1.0, 2.0], 'volume': [1.0, 1.0],
    })
    errors = {}
    payload = ind.compute('X', frame, [{'key': 'MA', 'params': {}}],
                          errors=errors)
    assert payload['items'] == []
    assert 'MA' in errors and 'boom' in errors['MA']
