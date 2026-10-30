"""指标主图 / 副图 / 信号线设置的静态审计。"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
IND = ROOT / 'minibt' / 'indicators'
SKIP = {'tradingview.py', '__init__.py', 'base.py', 'core.py',
        '_typing.py', '_acp.py'}


def _decorators():
    for path in sorted(IND.glob('*.py')):
        if path.name in SKIP:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and getattr(dec.func, 'id', None) == 'tobtind':
                    yield path.name, node.name, dec


def _literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def test_no_overlay_typo():
    for path, name, dec in _decorators():
        names = {kw.arg for kw in dec.keywords}
        assert 'overlay' not in names, (path, name)


def test_overlap_and_isplot_dict_keys_match_lines():
    for path, name, dec in _decorators():
        values = {kw.arg: _literal(kw.value) for kw in dec.keywords}
        lines = values.get('lines')
        if isinstance(lines, dict):
            lines = list(lines)
        for key in ('overlap', 'isplot'):
            value = values.get(key)
            if not isinstance(value, dict) or not isinstance(lines, list):
                continue
            assert set(value) <= set(lines), (path, name, key, value, lines)


def test_known_price_scale_indicators_are_overlap():
    def flag(module, name):
        path = IND / f'{module}.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and getattr(dec.func, 'id', None) == 'tobtind':
                        values = _literal
                        for kw in dec.keywords:
                            if kw.arg == 'overlap':
                                return values(kw.value)
        return None

    for module, name in [
        ('tulip', 'bbands'), ('tulip', 'sma'), ('tulip', 'psar'),
        ('finta', 'PIVOT'), ('finta', 'PIVOT_FIB'), ('finta', 'CHANDELIER'),
        ('talib', 'LINEARREG'), ('tqta', 'ENV'), ('tqta', 'CDP'),
        ('pine', 'percentile_nearest_rank'), ('btind', 'vwap_high'),
        ('btind', 'zigzag'), ('pandas_ta', 'ht_trendline'),
    ]:
        assert flag(module, name) is True, (module, name)


def test_known_oscillators_are_not_overlap():
    def flag(module, name):
        path = IND / f'{module}.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and getattr(dec.func, 'id', None) == 'tobtind':
                        for kw in dec.keywords:
                            if kw.arg == 'overlap':
                                return _literal(kw.value)
        return None

    for module, name in [
        ('finta', 'BBWIDTH'), ('finta', 'TRIX'), ('pine', 'atr'),
        ('pine', 'tr'), ('pine', 'highestbars'), ('pandas_ta', 'amat'),
    ]:
        assert flag(module, name) is False, (module, name)


def test_signal_lines_hidden():
    def isplot(module, name):
        path = IND / f'{module}.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and getattr(dec.func, 'id', None) == 'tobtind':
                        for kw in dec.keywords:
                            if kw.arg == 'isplot':
                                return _literal(kw.value)
        return None

    assert isplot('btind', 'gap_ratio')['signal'] is False
    assert isplot('pandas_ta', 'thermo')['thermo_long'] is False
    assert isplot('pandas_ta', 'chandelier_exit')['chandelier_direction'] is False
    assert isplot('pair', 'z_score')['signals'] is False
    assert isplot('factors', 'factor_optimizer')['signals'] is False
