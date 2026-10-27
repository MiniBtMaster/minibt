"""本地图表：指标模板 + 布局保存/应用（不进真实 ~/.minibt）✓"""
from __future__ import annotations

from minibt.desk import local_data
from minibt.desk import user_prefs
from minibt.desk.app import Desk


def _desk(tmp_path, monkeypatch):
    monkeypatch.setattr(user_prefs, 'PREFS_FILE',
                        str(tmp_path / 'prefs.json'))
    monkeypatch.setattr(local_data, 'STATE_FILE',
                        str(tmp_path / 'state.json'))
    monkeypatch.setenv('MINIBT_DESK_SIM_DB', str(tmp_path / 'sim.sqlite3'))
    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk._on_local_load({'name': 'l2609_60', 'cell': 0})
    return desk


def test_local_indicator_template_save_and_apply(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk._on_local_add_indicator({
        'symbol': 'l2609_60', 'key': 'pta_sma', 'cell': 0,
        'params': {'length': 5},
    })
    desk._on_save_template({
        'local': True, 'symbol': 'l2609_60', 'cell': 0, 'name': 'T',
    })
    templates = user_prefs.templates()
    assert templates and templates[0]['name'] == 'T'

    desk._on_local_remove_indicator({
        'symbol': 'l2609_60', 'key': 'pta_sma', 'cell': 0,
    })
    assert desk.local_store().indicators('l2609_60', 0) == []
    desk._on_apply_template({
        'local': True, 'symbol': 'l2609_60', 'cell': 0,
        'key': templates[0]['key'],
    })
    assert desk.local_store().indicators('l2609_60', 0) == [
        {'key': 'pta_sma', 'params': {'length': 5}}]


def test_local_layout_save_and_apply(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk._on_local_add_indicator({
        'symbol': 'l2609_60', 'key': 'pta_sma', 'cell': 0,
        'params': {'length': 5},
    })
    cells = [{'symbol': 'l2609_60',
              'indicators': desk.local_store().indicators('l2609_60', 0)}]
    desk._on_layout_save({
        'local': True, 'name': 'L', 'cols': 1, 'rows': 1,
        'cycle': 60, 'cells': cells,
    })
    layouts = user_prefs.layouts()
    assert layouts and layouts[0]['name'] == 'L'

    desk._on_local_remove_indicator({
        'symbol': 'l2609_60', 'key': 'pta_sma', 'cell': 0,
    })
    desk._on_layout_apply({'local': True, 'key': layouts[0]['key']})
    assert desk.local_store().indicators('l2609_60', 0) == [
        {'key': 'pta_sma', 'params': {'length': 5}}]


def test_local_layout_keeps_strategy_path_and_restores_it(
        tmp_path, monkeypatch):
    """布局保存策略文件；应用布局时重新挂策略，而不是丢掉策略线 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    path = str(tmp_path / 'pair.py')
    (tmp_path / 'pair.py').write_text('x = 1\n', encoding='utf-8')
    desk._local_strategies = {
        'l2609_60': {'name': 'Pair', 'path': path, 'items': []},
    }
    desk._local_strategy_of = {'l2609_60': 'Pair'}
    desk.local_store().set_strategy('l2609_60',
                                    {'name': 'Pair', 'path': path})
    cells = [{
        'symbol': 'l2609_60',
        'indicators': [
            {'key': 'editor:Pair:line:0', 'params': {}},
            {'key': 'pta_sma', 'params': {'length': 5}},
        ],
    }]
    desk._on_layout_save({
        'local': True, 'name': 'WithStrategy', 'cols': 1, 'rows': 1,
        'cycle': 60, 'cells': cells,
    })
    record = next(item for item in user_prefs.layouts()
                  if item['name'] == 'WithStrategy')
    cell = record['cells'][0]
    assert cell['strategy']['path'] == path
    assert [item['key'] for item in cell['indicators']] == ['pta_sma']

    calls = []
    monkeypatch.setattr(desk, '_on_editor_add_indicator',
                        lambda payload: calls.append(payload))
    desk._on_layout_apply({'local': True, 'key': record['key']})
    assert desk.local_store().indicators('l2609_60', 0) == [
        {'key': 'pta_sma', 'params': {'length': 5}}]
    assert calls and calls[0]['path'] == path
    assert calls[0]['local'] is True


def test_guess_local_strategy_by_contracts(tmp_path, monkeypatch):
    from minibt.desk import personal

    folder = tmp_path / 'strategies'
    folder.mkdir()
    good = folder / 'pair.py'
    good.write_text(
        'from minibt import *\n'
        'def make(self):\n'
        '    self.a = self.get_kline(LocalDatas.a_60)\n'
        '    self.b = self.get_kline(LocalDatas.b_60)\n',
        encoding='utf-8')
    other = folder / 'other.py'
    other.write_text('x = 1\n', encoding='utf-8')
    monkeypatch.setattr(personal, 'directories',
                        lambda: [{'path': str(folder), 'kind': 'strategy'}])
    desk = Desk(offline=True)
    assert desk._guess_local_strategy(['a_60', 'b_60']) == str(good)
    assert desk._guess_local_strategy(['missing']) == ''


def test_local_layout_saves_indicator_style_and_visibility(
        tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    style = {
        'key': 'MA', 'params': {'length': 10}, 'color': '#123456',
        'lineWidth': 3, 'lineStyle': 2, 'visible': False,
        'overlay': False, 'priceLine': False, 'crossLabel': True,
    }
    cells = [{'symbol': 'l2609_60', 'indicators': [style]}]
    desk._on_layout_save({
        'local': True, 'name': 'Styled', 'cols': 1, 'rows': 1,
        'cycle': 60, 'cells': cells,
    })
    record = next(item for item in user_prefs.layouts()
                  if item['name'] == 'Styled')
    saved = record['cells'][0]['indicators'][0]
    assert saved['color'] == '#123456'
    assert saved['lineWidth'] == 3
    assert saved['lineStyle'] == 2
    assert saved['visible'] is False
    assert saved['overlay'] is False
    assert saved['priceLine'] is False

    desk._on_layout_apply({'local': True, 'key': record['key']})
    payload = desk._local_indicator_payload('l2609_60', 0)
    items = [item for item in payload['items'] if item.get('source') == 'MA']
    assert items
    assert items[0]['color'] == '#123456'
    assert items[0]['lineWidth'] == 3
    assert items[0]['lineStyle'] == 2
    assert items[0]['visible'] is False
    assert items[0]['overlay'] is False
    assert items[0]['priceLine'] is False
