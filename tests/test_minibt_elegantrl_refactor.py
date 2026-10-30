"""elegantrl 样本外改造的轻量测试：切分 / 独立 eval env。"""
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from minibt.elegantrl.train.config import resolve_eval_env  # noqa: E402
from minibt.elegantrl.train.splits import (  # noqa: E402
    split_dataframe, split_indices, walk_forward_windows,
)


def test_split_dataframe_respects_purge_and_order():
    df = list(range(100))
    train, val, test = split_dataframe(df, train=0.6, val=0.2, purge=5)
    assert train == list(range(0, 60))
    assert val == list(range(65, 85))
    assert test == list(range(90, 100))
    assert len(train) + len(val) + len(test) == 90


def test_split_indices_requires_enough_data():
    with pytest.raises(ValueError):
        split_indices(10, train=0.9, val=0.05, purge=50)


def test_walk_forward_windows_are_ordered_and_purged():
    windows = list(walk_forward_windows(
        100, train_size=30, val_size=10, test_size=10,
        step=10, purge=5))
    assert windows
    for w in windows:
        assert w.train_end + 5 == w.val_start
        assert w.val_end + 5 == w.test_start
        assert w.train_start < w.train_end < w.val_start
        assert w.val_start < w.val_end < w.test_start
        assert w.test_start < w.test_end <= 100


def test_resolve_eval_env_prefers_explicit_instance():
    train_env = object()
    val_env = object()
    args = SimpleNamespace(env_class=train_env, eval_env_class=None)
    assert resolve_eval_env(args) is train_env
    args.eval_env_class = val_env
    assert resolve_eval_env(args) is val_env


def test_equity_metrics_known_series():
    from minibt.elegantrl.train.metrics import equity_metrics

    # 100 -> 110 -> 99 -> 120
    m = equity_metrics([100, 110, 99, 120], periods_per_year=4)
    assert abs(m['total_return'] - 0.20) < 1e-12
    assert m['max_drawdown'] < -0.09
    assert m['final_equity'] == 120
    assert m['sharpe'] > 0


def test_returns_metrics_matches_equity():
    from minibt.elegantrl.train.metrics import equity_metrics, returns_metrics

    a = equity_metrics([100, 101, 103, 102, 105], periods_per_year=5)
    b = returns_metrics([0.01, 103 / 101 - 1, 102 / 103 - 1,
                         105 / 102 - 1], periods_per_year=5)
    assert abs(a['total_return'] - b['total_return']) < 1e-12
    assert abs(a['max_drawdown'] - b['max_drawdown']) < 1e-12


def test_evaluator_uses_eval_score_callback(tmp_path):
    pytest.importorskip('torch')
    import numpy as np
    import torch as th
    from types import SimpleNamespace
    from minibt.elegantrl.train.evaluator import Evaluator

    class Env:
        num_envs = 1
        max_step = 3
        min_start_length = 0

        def reset(self):
            return np.zeros(1, dtype=np.float32), {}

        def step(self, action):
            return np.zeros(1, dtype=np.float32), 1.0, True, False, {}

    args = SimpleNamespace(
        gpu_id=-1, eval_times=1, eval_per_step=1, save_gap=8,
        if_keep_save=False, if_over_write=False, eval_record_step=0,
        min_start_mode='fixed', eval_score=lambda env: 7.0,
    )
    evaluator = Evaluator(str(tmp_path), Env(), args)
    evaluator.evaluate_and_save(th.nn.Linear(1, 1), 1, 0.0,
                                (0.0, 0.0, ''))
    assert evaluator.max_r == 1.0
    assert evaluator.max_score == 7.0


def test_walk_forward_folds_and_callback():
    from minibt.elegantrl.train import make_folds, run_walk_forward

    folds = list(make_folds(
        list(range(100)), train_size=30, val_size=10,
        test_size=10, step=10, purge=5))
    assert folds
    assert folds[0].fit_range == (0, 30)
    assert folds[0].train == list(range(30))
    assert folds[0].val == list(range(35, 45))
    assert folds[0].test == list(range(50, 60))

    calls = []
    def factory(frame):
        return {'data': frame}

    def train_one(train, val, test):
        calls.append((len(train['data']), len(val['data']), len(test['data'])))
        return 'ok'

    results = list(run_walk_forward(
        list(range(100)), factory, train_one,
        train_size=30, val_size=10, test_size=10, step=10, purge=5))
    assert results and calls[0] == (30, 10, 10)
    assert all(r == 'ok' for _, r in results)


def test_rl_reset_index_modes():
    from types import SimpleNamespace
    from minibt import Strategy

    s = Strategy()
    s.config.min_start_length = 10
    s._rl_config = SimpleNamespace(train=True, min_start_mode='fixed',
                                   max_step=100)
    assert s.rl_reset_index() == 10

    s._rl_config.min_start_mode = 'incremental'
    s._rl_cursor_reset = True
    first = s.rl_reset_index()
    second = s.rl_reset_index()
    assert second == first + 1

    s._rl_config.min_start_mode = 'random'
    values = {s.rl_reset_index() for _ in range(30)}
    assert values and all(10 <= v <= 20 for v in values)


def test_seed_and_action_ensemble_helpers():
    import numpy as np
    from minibt.elegantrl.train import (
        aggregate_actions, seed_dir, seed_list, train_seed_ensemble,
    )

    assert seed_list(3, 10) == (10, 11, 12)
    assert seed_dir('/tmp/models/rl', 42).endswith('_seed42')

    calls = []
    def make(seed):
        return {'seed': seed, 'train_agent': lambda: calls.append(seed)}
    got = list(train_seed_ensemble(
        make, (1, 2), train_one=lambda st: calls.append(st['seed'])))
    assert calls == [1, 2] and [seed for seed, _ in got] == [1, 2]

    # 2 个 actor，2 个样本：多数投票
    a = aggregate_actions([[1, 0], [1, 2]], if_discrete=True)
    assert a.tolist() == [1, 0]
    # 连续动作平均 + clip
    b = aggregate_actions([[0.5, -0.5], [1.5, 0.5]], if_discrete=False)
    assert np.allclose(b, [1.0, 0.0])


def test_run_walk_forward_ensemble_and_frame():
    from minibt.elegantrl.train import (
        run_walk_forward_ensemble, runs_to_frame,
    )

    class Fake:
        def __init__(self, data, seed):
            self.data = data
            self.seed = seed
            self.profits = [100, 101, 102, 103]

    def make(frame, seed):
        return Fake(frame, seed)

    def train_one(train, val, test, seed):
        return train

    runs = list(run_walk_forward_ensemble(
        list(range(120)), make, train_one,
        seeds=(1, 2), train_size=40, val_size=15,
        test_size=15, step=20, purge=5))
    assert len(runs) >= 2
    assert runs[0].metrics['total_return'] > 0
    df = runs_to_frame(runs)
    assert {'fold', 'seed', 'total_return', 'sharpe'} <= set(df.columns)


def test_summarize_and_save_walk_forward_runs(tmp_path):
    from types import SimpleNamespace
    from minibt.elegantrl.train import (
        Fold, WalkForwardRun, save_runs_csv, summarize_runs,
    )

    fold = Fold(SimpleNamespace(train_start=0, train_end=10,
                                val_start=15, val_end=20,
                                test_start=25, test_end=30), [], [], [])
    runs = [
        WalkForwardRun(fold, 1, None, None, {'sharpe': 1.0, 'max_drawdown': -0.1}),
        WalkForwardRun(fold, 1, None, None, {'sharpe': 2.0, 'max_drawdown': -0.2}),
    ]
    summary = summarize_runs(runs)
    assert abs(float(summary.loc[1, ('sharpe', 'mean')]) - 1.5) < 1e-12
    target = save_runs_csv(runs, str(tmp_path / 'wf' / 'runs.csv'))
    assert (tmp_path / 'wf' / 'runs.csv').is_file()
    assert target.endswith('runs.csv')


def test_walk_forward_report(tmp_path):
    from types import SimpleNamespace
    from minibt.elegantrl.train import (
        Fold, WalkForwardRun, save_walk_forward_report, walk_forward_report,
    )

    fold = Fold(SimpleNamespace(train_start=0, train_end=10,
                                val_start=15, val_end=20,
                                test_start=25, test_end=30), [], [], [])
    runs = [WalkForwardRun(fold, 42, None, None,
                           {'sharpe': 1.2, 'max_drawdown': -0.1},
                           equity=[100, 101, 100, 103])]
    text = walk_forward_report(runs, title='WF test')
    assert '# WF test' in text and 'sharpe' in text
    path = save_walk_forward_report(runs, str(tmp_path / 'wf.md'))
    assert (tmp_path / 'wf.md').is_file()
    assert '# WF test' in path or path.endswith('wf.md')


def test_best_seed_and_html_report(tmp_path):
    from types import SimpleNamespace
    from minibt.elegantrl.train import (
        Fold, WalkForwardRun, best_runs, best_seed,
        save_walk_forward_html,
    )

    fold = Fold(SimpleNamespace(train_start=0, train_end=10,
                                val_start=15, val_end=20,
                                test_start=25, test_end=30), [], [], [])
    runs = [
        WalkForwardRun(fold, 42, None, None, {'sharpe': 0.5},
                       equity=[100, 101]),
        WalkForwardRun(fold, 43, None, None, {'sharpe': 1.2},
                       equity=[100, 102]),
        WalkForwardRun(fold, 43, None, None, {'sharpe': 1.0},
                       equity=[100, 101]),
    ]
    assert best_seed(runs) == 43
    assert len(best_runs(runs, n=2)) == 2
    assert best_runs(runs, n=1)[0].metrics['sharpe'] == 1.2
    path = save_walk_forward_html(runs, str(tmp_path / 'wf.html'))
    assert (tmp_path / 'wf.html').is_file()
    assert path.endswith('wf.html')
    body = (tmp_path / 'wf.html').read_text(encoding='utf-8')
    assert '<html>' in body and '<svg' in body


def test_best_model_config_and_deploy(tmp_path):
    from types import SimpleNamespace
    from minibt.elegantrl.train import (
        Fold, WalkForwardRun, best_model_config, save_best_model,
    )

    cwd = tmp_path / 'model_42'
    cwd.mkdir()
    (cwd / 'act.pth').write_text('fake actor', encoding='utf-8')
    strategy = SimpleNamespace(_rl_config=SimpleNamespace(cwd=str(cwd)))
    fold = Fold(SimpleNamespace(train_start=0, train_end=10,
                                val_start=15, val_end=20,
                                test_start=25, test_end=30), [], [], [])
    runs = [WalkForwardRun(fold, 42, strategy, None,
                           {'sharpe': 1.5})]
    config = best_model_config(runs)
    assert config['seed'] == 42
    assert config['actor_path'].endswith('act.pth')
    target = tmp_path / 'deploy'
    save_best_model(runs, str(target))
    assert (target / 'actor.pth').read_text(encoding='utf-8') == 'fake actor'
    assert (target / 'config.json').is_file()


def test_deploy_load_actor(tmp_path):
    pytest.importorskip('torch')
    import torch
    from types import SimpleNamespace
    from minibt import Agents
    from minibt.elegantrl.train import (
        Fold, WalkForwardRun, best_model_config, load_best_actor, save_best_model,
    )

    cwd = tmp_path / 'seed42'
    cwd.mkdir()
    from minibt.elegantrl.train.config import Config
    from minibt.rl_utils import Activation, Loss, Optim
    acfg = Config()
    acfg.if_discrete = True
    acfg.Loss = Loss.MSELoss(reduction='none')
    acfg.Optim = Optim.AdamW()
    acfg.Activation = Activation.Tanh10()
    agent = Agents.AgentDiscretePPO([8], 3, 2, gpu_id=-1, args=acfg)
    torch.save(agent.act.state_dict(), cwd / 'act.pth')
    cfg = SimpleNamespace(
        cwd=str(cwd), agent_class=Agents.AgentDiscretePPO,
        net_dims=[8], state_dim=3, action_dim=2, if_discrete=True,
    )
    strategy = SimpleNamespace(_rl_config=cfg)
    fold = Fold(SimpleNamespace(train_start=0, train_end=10,
                                val_start=15, val_end=20,
                                test_start=25, test_end=30), [], [], [])
    runs = [WalkForwardRun(fold, 42, strategy, None, {'sharpe': 1.0})]
    config = best_model_config(runs)
    assert config['agent'] == 'AgentDiscretePPO'
    assert config['net_dims'] == [8]
    save_best_model(runs, str(tmp_path / 'deploy'))
    actor, loaded = load_best_actor(str(tmp_path / 'deploy'))
    assert loaded['seed'] == 42
    assert actor.training is False


def test_rl_experiment_facade(tmp_path):
    from minibt.elegantrl.train import RlExperiment

    class Fake:
        def __init__(self, frame, seed, role):
            self.frame = frame
            self.seed = seed
            self.role = role
            self.profits = [100, 101, 102]

    def make(frame, seed, role):
        return Fake(frame, seed, role)

    def train_one(train, val, test, seed):
        assert train.role == 'train' and val.role == 'val'
        return train

    exp = RlExperiment(
        list(range(120)), make, train_one,
        seeds=(42,), train_size=40, val_size=15,
        test_size=15, step=20, purge=5, role_aware=True,
    )
    runs = exp.walk_forward()
    assert runs and exp.best_run() is not None
    assert exp.best_seed() == 42
    assert 'sharpe' in exp.to_frame().columns
    assert exp.save_csv(str(tmp_path / 'wf.csv')).endswith('wf.csv')


def test_bt_rl_experiment_facade():
    from minibt import Bt
    from minibt.elegantrl.train import RlExperiment

    exp = Bt(auto=False).rl_experiment(
        list(range(100)), lambda frame, seed: None,
        lambda train, val, test, seed: train,
        seeds=(42,), train_size=30, val_size=10,
        test_size=10, step=10, purge=5, role_aware=False,
    )
    assert isinstance(exp, RlExperiment)


def test_reward_costs_and_risk():
    from minibt.elegantrl.train import (
        RewardConfig, RewardModel, compute_reward,
    )

    cfg = RewardConfig(
        commission_rate=0.001, slippage_rate=0.0005,
        risk_penalty=0.05,
    )
    # 0.01 毛收益 - 0.001 手续费 - 0.0005 滑点 - 0.005 回撤惩罚
    reward = compute_reward(
        0.0, 1.0, 0.01, equity=0.9, peak_equity=1.0, config=cfg)
    assert abs(reward - 0.0035) < 1e-12
    breakdown = compute_reward(
        0.0, 1.0, 0.01, equity=0.9, peak_equity=1.0,
        config=cfg, return_breakdown=True)
    assert breakdown.turnover == 1.0
    assert breakdown.drawdown < 0

    model = RewardModel(cfg)
    first = model.step(0.0, 1.0, 0.01)
    second = model.step(1.0, 0.0, -0.01)
    assert first > 0 and second < 0
    assert model.peak_equity >= model.equity


def test_position_state_features():
    from minibt.elegantrl.train import PositionState, append_state_features

    state = PositionState(1.0, 3, 0.02, -0.1)
    f = state.features(max_holding_days=10.0)
    assert f.tolist() == pytest.approx([1.0, 0.3, 0.02, -0.1])
    assert append_state_features([[1, 2]], state).shape == (6,)


def test_small_model_kwargs():
    from minibt.elegantrl.train import small_model_kwargs

    kw = small_model_kwargs(if_discrete=True, action_dim=3,
                            min_start_mode='incremental')
    assert kw['net_dims'] == (64, 32)
    assert kw['action_dim'] == 3
    assert kw['min_start_mode'] == 'incremental'
    assert kw['gpu_id'] == -1


def test_evaluator_best_actor_is_restored(tmp_path):
    pytest.importorskip('torch')
    import numpy as np
    import torch as th
    from types import SimpleNamespace
    from minibt.elegantrl.train.evaluator import (
        Evaluator, best_actor_path, restore_best_actor,
    )

    class Env:
        num_envs = 1
        max_step = 2
        min_start_length = 0
        score = 1.0

        def reset(self):
            return np.zeros(1, dtype=np.float32), {}

        def step(self, action):
            return np.zeros(1, dtype=np.float32), 1.0, True, False, {}

    cwd = tmp_path / 'models'
    cwd.mkdir()
    env = Env()
    args = SimpleNamespace(
        gpu_id=-1, eval_times=1, eval_per_step=1, save_gap=8,
        if_keep_save=True, if_over_write=False, eval_record_step=0,
        min_start_mode='fixed', eval_score=lambda e: e.score,
    )
    evaluator = Evaluator(str(cwd), env, args)
    evaluator.save_training_curve_jpg = lambda: None
    actor = th.nn.Linear(1, 1)

    evaluator.evaluate_and_save(actor, 1, 0.0, (0.0, 0.0, ''))
    first = best_actor_path(str(cwd))
    assert first and first.endswith('.pt')
    env.score = 3.0
    evaluator.evaluate_and_save(actor, 1, 0.0, (0.0, 0.0, ''))
    best = best_actor_path(str(cwd))
    assert best and best != first
    # 模拟训练结束最终保存 act.pth，再恢复验证最优
    th.save(actor, cwd / 'act.pth')
    restored = restore_best_actor(str(cwd))
    assert restored and (cwd / 'act.pth').is_file()
    assert cwd.joinpath('best_actor.txt').is_file()


def test_quant_feature_state_reuses_train_scaler():
    import numpy as np
    from minibt import Strategy

    class Ind:
        def __init__(self, values):
            self.values = np.asarray(values, dtype=np.float32)

    def make_strategy(start, stop):
        s = Strategy()
        s._btindicatordataset = {
            'a': Ind(np.arange(start, stop)),
            'b': Ind(np.linspace(start + 1, stop, stop - start)),
        }
        return s

    train = make_strategy(0, 20)
    train._process_quant_features(
        normalize_method='standard', fit_range=(0, 10))
    state = train.get_quant_feature_state()
    assert state and state['scaler'] is not None

    # 模拟 val：不同数据长度，但只 transform，不重新 fit
    val = make_strategy(100, 110)
    val.set_quant_feature_state(state)
    out = val._process_quant_features(
        normalize_method='standard', feature_state=state)
    assert out.shape == (10, 2)
    assert np.allclose(
        val._quant_feature_state['scaler'].mean_,
        state['scaler'].mean_)
