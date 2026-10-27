"""参数优化目标：1~3 个 OPTTargetType（多目标权重 / 前后端接入）。"""
from __future__ import annotations

import pathlib

from minibt.desk.research import TARGET_METRICS, metric_direction
from minibt.desk.strategy_lab import StrategyLab

ROOT = pathlib.Path(__file__).resolve().parents[1]
JSLIB = ROOT / 'jslib' / 'src' / 'desk'


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding='utf-8')


class _Desk:
    def __init__(self):
        self.patches = []

    def push(self, patch):
        self.patches.append(patch)


def _lab_with_targets(metrics=None, weights=None):
    desk = _Desk()
    lab = StrategyLab(desk, 'opt-targets')
    payload = {'file': 'x.py', 'mode': 'optimize'}
    if metrics is not None:
        payload['metrics'] = metrics
    if weights is not None:
        payload['weights'] = weights
    # 不走线程：只验证参数解析 / 状态补丁 ✓
    lab.file = payload['file']
    lab.mode = 'optimize'
    if metrics:
        from minibt.desk.research import normalize_metrics
        lab.targets = normalize_metrics(metrics)
    if weights:
        lab.weights = list(weights)
    elif lab.targets:
        lab.weights = [float(metric_direction(name)) for name in lab.targets]
    return lab, desk


def test_state_patch_exposes_all_target_options():
    lab, desk = _lab_with_targets(['profit_ratio', 'sharpe',
                                   'max_drawdown'])
    lab._push_state()                                    # noqa: SLF001
    patch = desk.patches[-1]
    assert patch['type'] == 'strategy_state'
    assert patch['targets'] == ['profit_ratio', 'sharpe', 'max_drawdown']
    assert len(patch['target_options']) == len(TARGET_METRICS) == 73
    assert 'volatility' in patch['target_options']
    assert patch['weights'] == [1.0, 1.0, 1.0]


def test_weights_derived_from_direction():
    lab, _desk = _lab_with_targets(['sharpe', 'volatility', 'max_drawdown'])
    assert lab.weights == [1.0, -1.0, 1.0]


def test_run_optimize_forwards_multi_target_to_bt():
    captured = {}

    class Config(dict):
        pass

    class Strategy:
        op_config = {
            'target': 'profit_ratio',
            'weights': 1.0,
            'params': {'length': [5, 10]},
            'opconfig': {'n_trials': 1},
        }

    class Bt:
        strategies = [Strategy]

        def optstrategy(self, target, weights, **kwargs):
            captured['target'] = target
            captured['weights'] = weights
            captured['kwargs'] = kwargs

        def run(self, **kwargs):
            captured['run'] = kwargs

    lab, desk = _lab_with_targets(['profit_ratio', 'sharpe', 'max_drawdown'])
    lab._run_optimize(Bt())                               # noqa: SLF001
    assert captured['target'] == ['profit_ratio', 'sharpe', 'max_drawdown']
    assert captured['weights'] == (1.0, 1.0, 1.0)
    assert captured['run']['isplot'] is False
    assert lab._opt_key == 'opt_Strategy_profit_ratio'    # noqa: SLF001
    assert any(patch['type'] == 'strategy_progress'
               for patch in desk.patches)


def test_run_optimize_single_target_uses_float_weight():
    captured = {}

    class Strategy:
        op_config = {'target': 'profit_ratio', 'weights': 1.0,
                     'params': {}, 'opconfig': {'n_trials': 1}}

    class Bt:
        strategies = [Strategy]

        def optstrategy(self, target, weights, **kwargs):
            captured['target'] = target
            captured['weights'] = weights

        def run(self, **kwargs):
            pass

    lab, _desk = _lab_with_targets(['volatility'])
    lab._run_optimize(Bt())                               # noqa: SLF001
    assert captured['target'] == ['volatility']
    assert captured['weights'] == -1.0


def test_frontend_has_target_selector_and_restart():
    page = _read(JSLIB / 'strategy-lab-page.ts')
    for marker in ('data-opt-target', 'data-opt-restart',
                   'data-opt-target-reset', '_optSettingsHtml',
                   'target_options', '最多 3 个'):
        assert marker in page, marker
    css = _read(JSLIB / 'desk.css')
    assert '.desk-strategy-opt-targets' in css
