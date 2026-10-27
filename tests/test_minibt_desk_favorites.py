"""收藏策略 → 带 label / path，能被图表菜单加到图上 ✓"""
from __future__ import annotations

import json

from minibt.desk.app import Desk
from minibt.desk import user_prefs


def _patch(script: str):
    return json.loads(script[len('window.__desk.applyPatch('):-2])


def test_favorites_include_strategy_paths(monkeypatch):
    monkeypatch.setattr(user_prefs, 'favorites',
                        lambda kind='indicator': (
                            ['pi:my/S'] if kind == 'strategy' else []))
    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.picker_items = lambda: [{
        'key': 'pi:my/S', 'label': 'S', 'desc': '/tmp/S.py',
        'provider': '个人', 'section': 'my_strategies',
    }]
    desk._on_favorites({})
    patch = _patch(desk.sent[-1])
    assert patch['type'] == 'favorites'
    strategy = patch['strategies'][0]
    assert strategy['key'] == 'pi:my/S'
    assert strategy['label'] == 'S'
    assert strategy['path'] == '/tmp/S.py'


def test_frontend_favorite_strategy_uses_editor_add(monkeypatch):
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / 'jslib' / 'src' / 'desk'
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        text = (root / name).read_text(encoding='utf-8')
        assert "editor_add_indicator" in text
        assert "String(row.path || '')" in text
