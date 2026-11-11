"""08 / 09 共用：加载 05 策略、生成 fold、构造策略、test 评估。"""
from __future__ import annotations

import importlib.util
import os
import pathlib

import torch as th

from minibt import LocalDatas
from minibt.elegantrl.train import (
    aggregate_actions, equity_metrics, make_folds,
)

_HERE = pathlib.Path(__file__).resolve().parent
_RL_MODULE = None


def hold_days():
    """惰性加载 05_rl_hold_days.py（文件名以数字开头，不能直接 import）。"""
    global _RL_MODULE
    if _RL_MODULE is None:
        path = _HERE / '05_rl_hold_days.py'
        spec = importlib.util.spec_from_file_location('rl_hold_days_common', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _RL_MODULE = module
    return _RL_MODULE


def make_fold():
    df = LocalDatas.test.kline.pandas_object
    folds = list(make_folds(
        df, train_size=600, val_size=200, test_size=200,
        step=1000, purge=60))
    return folds


def policy(role: str, frame, *, train: bool, steps: int, tag: str,
           fit_range=None, feature_state=None):
    """构造同一个 RLHoldDays 的 train / val / test 变体。"""
    return hold_days().RLHoldDays.copy(
        name=f'RLHoldDays_{role}',
        DATA=frame,
        FIT_RANGE=fit_range,
        FEATURE_STATE=feature_state,
        TRAIN=train,
        STEPS=steps,
        CWD=os.path.join(os.path.expanduser('~'), '.minibt', 'models',
                         f'rl_{role}_{tag}'),
    )


def run_test(actors, fold, steps: int, tag: str, feature_state=None):
    """在 ``fold.test`` 上用 1 个或多个 actor 推理，返回 (metrics, profits)。"""
    TestPolicy = policy(
        'test', fold.test, train=False, steps=steps, tag=tag,
        feature_state=feature_state)
    test = TestPolicy()
    test._prepare_before_strategy_start()
    test._state, _ = test.reset()
    test.device = next(actors[0].parameters()).device

    start = int(getattr(test, '_btindex', test.min_start_length))
    for _ in range(start, test.max_step):
        state = th.as_tensor(test._state, dtype=th.float32,
                             device=test.device).unsqueeze(0)
        actions = [actor(state).detach().cpu().numpy()[0]
                   for actor in actors]
        action = actions[0] if len(actions) == 1 else aggregate_actions(
            actions, if_discrete=True)
        test._state, _reward, terminated, truncated, _ = test.step(action)
        test._btindex += 1
        test._account.update_history()
        if terminated or truncated:
            break
    profits = test._account.get_profits()
    return equity_metrics(profits), profits


__all__ = ['hold_days', 'make_fold', 'policy', 'run_test']
