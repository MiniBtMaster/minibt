"""策略研究平台：walk-forward / 参数网格 / 热力图 / Pareto / 实验库 / 报告。"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from minibt.desk.research import (TARGET_METRICS, ExperimentStore,
                                  ResearchLab, export_report, heatmap,
                                  local_data_names, metric_direction,
                                  normalize_metrics, param_grid, pareto,
                                  resolve_data_files, split_windows,
                                  stability_score, summarize,
                                  walk_forward_windows)


def _frame(rows=120):
    close = 100 + np.arange(rows, dtype=float) * 0.1
    return pd.DataFrame({
        'datetime': pd.date_range('2024-01-01', periods=rows, freq='1min'),
        'open': close - 0.1, 'high': close + 0.2,
        'low': close - 0.2, 'close': close,
        'volume': 10.0, 'symbol': 'SHFE.demo',
    })


def test_walk_forward_windows_and_splits():
    windows = walk_forward_windows(100, 40, 10)
    assert windows[0] == {'index': 0, 'train_start': 0, 'train_end': 40,
                          'test_start': 40, 'test_end': 50}
    assert windows[-1]['test_end'] == 100
    splits = split_windows(_frame(), 40, 10)
    assert splits
    assert len(splits[0]['train']) == 40
    assert len(splits[0]['test']) == 10
    assert 'train_from' in splits[0]['window']


def test_param_grid_and_heatmap():
    grid = param_grid({'length': [10, 20], 'std': [1, 2, 3]})
    assert len(grid) == 6
    rows = [
        {'params': {'length': 10, 'std': 1}, 'metrics': {'profit_ratio': 0.1}},
        {'params': {'length': 10, 'std': 2}, 'metrics': {'profit_ratio': -0.1}},
        {'params': {'length': 20, 'std': 1}, 'metrics': {'profit_ratio': 0.3}},
    ]
    data = heatmap(rows, 'length', 'std')
    assert data['x_values'] == ['10', '20']
    assert data['y_values'] == ['1', '2']
    assert data['grid'][0] == [0.1, 0.3]
    assert data['grid'][1] == [-0.1, None]


def test_pareto_and_summary():
    rows = [
        {'params': {'a': 1}, 'metrics': {'profit_ratio': 0.1,
                                         'max_drawdown': 0.05}},
        {'params': {'a': 2}, 'metrics': {'profit_ratio': 0.2,
                                         'max_drawdown': 0.1}},
        {'params': {'a': 3}, 'metrics': {'profit_ratio': 0.12,
                                         'max_drawdown': 0.02}},
        {'params': {'a': 4}, 'metrics': {'profit_ratio': None}},
    ]
    front = pareto(rows)
    assert {item['params']['a'] for item in front} == {2, 3}
    summary = summarize(rows)
    assert summary['count'] == 3
    assert summary['positive_rate'] == 1.0
    assert 0 <= stability_score(summary) <= 100
    assert stability_score({'mean': None}) is None


def test_experiment_store_roundtrip(tmp_path):
    store = ExperimentStore(str(tmp_path / 'research.db'))
    experiment = store.add_experiment(
        name='demo', mode='grid', file='x.py', symbols=['a'],
        params={'a': [1, 2]}, metrics={'profit_ratio': 0.1},
        summary={'mean': 0.1}, windows=[{'metrics': {'profit_ratio': 0.1}}],
        score=55.0)
    assert experiment > 0
    rows = store.experiments()
    assert rows[0]['name'] == 'demo'
    assert rows[0]['score'] == 55.0
    trial = store.add_trial(experiment, window=0,
                            params={'a': 1},
                            metrics={'profit_ratio': 0.1})
    assert trial > 0
    assert len(store.trials(experiment)) == 1
    path = export_report(store.experiment(experiment),
                         str(tmp_path / 'report.md'),
                         trials=store.trials(experiment))
    assert os.path.isfile(path)
    assert os.path.isfile(os.path.splitext(path)[0] + '.csv')
    assert 'Walk-forward' in open(path, encoding='utf-8').read()
    assert store.delete(experiment) is True
    assert store.trials(experiment) == []


class FakeDesk:
    def __init__(self):
        self.patches = []

    def push(self, patch):
        self.patches.append(patch)

    def push_log(self, text, level='info'):
        self.patches.append({'type': 'log', 'text': text})


def test_research_lab_walk_forward_with_injected_runner(tmp_path, monkeypatch):
    data = tmp_path / 'demo.csv'
    _frame(150).to_csv(data, index=False)
    strategy = tmp_path / 's.py'
    strategy.write_text('class X: pass\n', encoding='utf-8')
    calls = []

    def runner(file, frames, params):
        calls.append((file, list(frames), dict(params)))
        return {'strategies': [{'name': 'X', 'metrics': {
            'profit_ratio': 0.1 * len(calls),
            'max_drawdown': 0.02,
        }}]}

    desk = FakeDesk()
    store = ExperimentStore(str(tmp_path / 'r.db'))
    lab = ResearchLab(desk, store=store, runner=runner)
    lab.start({'mode': 'walk_forward', 'file': str(strategy),
               'data': str(data), 'train': 50, 'test': 20, 'step': 20,
               'metric': 'profit_ratio', 'name': 'wf'})
    lab._thread.join(20)                                  # noqa: SLF001
    assert lab.status == 'ready', lab.error
    assert len(calls) >= 2
    result = lab.result
    assert result['kind'] == 'walk_forward'
    assert result['summary']['count'] == len(calls)
    assert result['experiments']
    assert any(patch.get('type') == 'research_result' for patch in desk.patches)
    # 报告可从实验库导出
    report = lab.report(result['experiment'])
    assert os.path.isfile(report)


def test_research_lab_grid(tmp_path):
    data = tmp_path / 'demo.csv'
    _frame(60).to_csv(data, index=False)
    strategy = tmp_path / 's.py'
    strategy.write_text('class X: pass\n', encoding='utf-8')
    values = iter([0.1, 0.2, 0.3, 0.4])

    def runner(file, frames, params):
        return {'strategies': [{'name': 'X', 'metrics': {
            'profit_ratio': next(values), 'max_drawdown': 0.05}}]}

    lab = ResearchLab(FakeDesk(), store=ExperimentStore(':memory:'),
                      runner=runner)
    lab.start({'mode': 'grid', 'file': str(strategy), 'data': str(data),
               'params': {'a': [1, 2], 'b': [3, 4]}})
    lab._thread.join(20)                                  # noqa: SLF001
    assert lab.status == 'ready', lab.error
    assert len(lab.result['grid_rows']) == 4
    assert lab.result['heatmap']['grid']


def test_research_lab_requires_data_and_file(tmp_path):
    lab = ResearchLab(FakeDesk(), store=ExperimentStore(':memory:'),
                      runner=lambda *args, **kwargs: {})
    lab.start({'mode': 'walk_forward', 'file': '/nope.py', 'data': ''})
    lab._thread.join(10)                                  # noqa: SLF001
    assert lab.status == 'error'
    assert '数据文件' in lab.error or '策略文件' in lab.error


def test_target_metrics_match_minibt_literal():
    import ast
    import pathlib
    source = pathlib.Path(__file__).resolve().parents[1] / 'minibt' / 'typing_.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    values = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == 'OPTTargetType'
                for target in node.targets):
            values = [item.value for item in node.value.slice.elts]
    assert values is not None
    assert list(TARGET_METRICS) == values
    assert len(TARGET_METRICS) == 73


def test_metric_normalize_and_direction():
    assert normalize_metrics('sharpe') == ['sharpe']
    assert normalize_metrics(['sharpe', 'sharpe', 'max_drawdown']) == [
        'sharpe', 'max_drawdown']
    assert normalize_metrics(['a', 'b', 'c', 'd']) == ['profit_ratio']
    assert normalize_metrics(['sharpe', 'sortino', 'calmar', 'omega']) == [
        'sharpe', 'sortino', 'calmar']
    assert metric_direction('profit_ratio') == 1
    assert metric_direction('volatility') == -1
    assert metric_direction('max_drawdown') == 1


def test_local_datas_names_resolve_to_builtin_csv():
    names = local_data_names()
    assert 'test' in names
    files = resolve_data_files(['test'])
    assert files and files[0].endswith('test.csv')
    assert os.path.isfile(files[0])


def test_target_value_reads_extra_stats_metric():
    from minibt.desk.research import _target_value

    class Stats:
        def omega(self):
            return 1.75

        def rolling_sharpe(self):
            return pd.Series([0.1, 0.2, 0.9])

        def broken(self):
            raise RuntimeError('nope')

    class Instance:
        _stats = Stats()

    assert _target_value(Instance(), 'omega') == 1.75
    assert _target_value(Instance(), 'rolling_sharpe') == 0.9
    assert _target_value(Instance(), 'broken', {'broken': 3.0}) == 3.0
    assert _target_value(Instance(), 'missing') is None


def test_walk_forward_supports_builtin_data_and_multi_metrics(tmp_path):
    _frame(150).to_csv(tmp_path / 'd.csv', index=False)
    strategy = tmp_path / 's.py'
    strategy.write_text("""class X: pass
""", encoding='utf-8')
    calls = []

    def runner(file, frames, params, metrics):
        calls.append(list(metrics))
        return {'strategies': [{'name': 'X', 'metrics': {
            'profit_ratio': 0.1 * len(calls), 'sharpe': 0.5,
            'max_drawdown': -0.02,
        }}]}

    lab = ResearchLab(FakeDesk(), store=ExperimentStore(':memory:'),
                      runner=runner)
    lab.start({'mode': 'walk_forward', 'file': str(strategy),
               'data': 'test', 'train': 50, 'test': 20, 'step': 20,
               'metrics': ['profit_ratio', 'sharpe', 'max_drawdown']})
    lab._thread.join(20)                                  # noqa: SLF001
    assert lab.status == 'ready', lab.error
    assert calls and calls[0] == ['profit_ratio', 'sharpe', 'max_drawdown']
    result = lab.result
    assert result['metrics'] == ['profit_ratio', 'sharpe', 'max_drawdown']
    assert set(result['summaries']) == {
        'profit_ratio', 'sharpe', 'max_drawdown'}
    assert set(result['heatmaps']) == set(result['metrics'])
    assert result['score'] is not None
    snapshot = lab.snapshot()
    assert 'test' in snapshot['data_names']
    assert 'sharpe' in snapshot['metrics']


def test_walk_forward_data_blank_uses_strategy_local_datas(tmp_path):
    _frame(120).to_csv(tmp_path / 'd.csv', index=False)
    strategy = tmp_path / 's_local.py'
    strategy.write_text(
        """from minibt import LocalDatas
class X:
    def setup(self, self_):
        self.data = self.get_kline(LocalDatas.test)
""",
        encoding='utf-8')
    calls = []

    def runner(file, frames, params):
        calls.append(list(frames))
        return {'strategies': [{'name': 'X', 'metrics': {
            'profit_ratio': 0.05}}]}

    lab = ResearchLab(FakeDesk(), store=ExperimentStore(':memory:'),
                      runner=runner)
    lab.start({'mode': 'walk_forward', 'file': str(strategy),
               'data': '', 'train': 40, 'test': 20, 'step': 20})
    lab._thread.join(20)                                  # noqa: SLF001
    assert lab.status == 'ready', lab.error
    assert calls and calls[0] == ['test']


def test_walk_forward_rejects_mismatched_local_data(tmp_path):
    data = tmp_path / 'other.csv'
    _frame(80).to_csv(data, index=False)
    strategy = tmp_path / 's.py'
    strategy.write_text(
        """from minibt import LocalDatas
class X:
    def setup(self):
        self.data = self.get_kline(LocalDatas.test)
""", encoding='utf-8')
    lab = ResearchLab(FakeDesk(), store=ExperimentStore(':memory:'),
                      runner=lambda *args, **kwargs: {})
    lab.start({'mode': 'walk_forward', 'file': str(strategy),
               'data': str(data), 'train': 40, 'test': 20})
    lab._thread.join(10)                                  # noqa: SLF001
    assert lab.status == 'error'
    assert 'LocalDatas' in lab.error or '数据文件' in lab.error


def test_patched_local_data_makes_get_kline_read_window_csv(tmp_path):
    import pandas as pd
    from minibt.data import tools
    from minibt.desk.research import _patched_local_data

    frame = _frame(5)
    original = tools.get_csv_path('test')
    with _patched_local_data({'test': frame}):
        patched = tools.get_csv_path('test')
        assert patched != original
        assert len(pd.read_csv(patched)) == 5
    assert tools.get_csv_path('test') == original
