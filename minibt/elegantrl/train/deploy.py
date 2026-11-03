"""从 walk-forward 结果里选择最佳模型并生成部署配置。"""
from __future__ import annotations

import json
import os
import shutil
from typing import Iterable

import torch

from .report import best_runs
from .walk_forward import WalkForwardRun


def _actor_path(run: WalkForwardRun) -> str:
    strategy = run.strategy
    cfg = getattr(strategy, '_rl_config', None)
    cwd = str(getattr(cfg, 'cwd', '') or '')
    if not cwd:
        return ''
    return os.path.join(cwd, 'act.pth')


def best_model_config(runs: Iterable[WalkForwardRun], *,
                      metric: str = 'sharpe') -> dict:
    """返回最佳 run 的部署配置（不复制文件）。"""
    best = best_runs(runs, metric=metric, n=1)
    if not best:
        return {}
    run = best[0]
    actor = _actor_path(run)
    cfg = getattr(run.strategy, '_rl_config', None)
    agent_cls = getattr(cfg, 'agent_class', None)
    config = {
        'seed': run.seed,
        'metric': metric,
        'score': float(run.metrics.get(metric, 0.0)),
        'fit_range': list(run.fold.local_fit_range),
        'cwd': os.path.dirname(actor) if actor else '',
        'actor_path': actor,
        'metrics': dict(run.metrics),
        'fold': {
            'train_start': run.fold.window.train_start,
            'train_end': run.fold.window.train_end,
            'val_start': run.fold.window.val_start,
            'val_end': run.fold.window.val_end,
            'test_start': run.fold.window.test_start,
            'test_end': run.fold.window.test_end,
        },
    }
    if agent_cls is not None:
        config.update({
            'agent': getattr(agent_cls, '__name__', str(agent_cls)),
            'net_dims': list(getattr(cfg, 'net_dims', ()) or ()),
            'state_dim': int(getattr(cfg, 'state_dim', 0) or 0),
            'action_dim': int(getattr(cfg, 'action_dim', 0) or 0),
            'if_discrete': bool(getattr(cfg, 'if_discrete', True)),
        })
    return config


def save_best_model(runs: Iterable[WalkForwardRun], target_dir: str,
                    *, metric: str = 'sharpe') -> str:
    """把最佳 actor 复制到目标目录，并写入 ``config.json``。

    目标目录会包含::

        actor.pth
        config.json
    """
    runs = list(runs)
    config = best_model_config(runs, metric=metric)
    os.makedirs(target_dir, exist_ok=True)
    actor = config.get('actor_path', '')
    deployed = os.path.join(target_dir, 'actor.pth')
    if actor and os.path.isfile(actor):
        shutil.copyfile(actor, deployed)
        config['deployed_actor'] = deployed
    with open(os.path.join(target_dir, 'config.json'), 'w',
              encoding='utf-8') as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)
    return os.path.join(target_dir, 'config.json')




def load_best_actor(config_or_dir: str, *, device: str = 'cpu'):
    """从部署目录 / config.json 加载 actor（eval 模式）。

    ``config_or_dir`` 可以是 ``config.json`` 或包含它的目录。
    """
    path = config_or_dir
    if os.path.isdir(path):
        path = os.path.join(path, 'config.json')
    with open(path, encoding='utf-8') as handle:
        config = json.load(handle)
    agent_name = config.get('agent')
    if not agent_name:
        raise ValueError('config.json 缺少 agent')
    from minibt import Agents
    from ...rl_utils import Loss, Optim, Activation
    agent_cls = getattr(Agents, agent_name, None)
    if agent_cls is None:
        raise ValueError(f'未知 agent: {agent_name}')
    actor_path = config.get('deployed_actor') or config.get('actor_path')
    if not actor_path:
        raise ValueError('config.json 缺少 actor_path')
    if not os.path.isabs(actor_path):
        actor_path = os.path.join(os.path.dirname(os.path.abspath(path)),
                                  actor_path)
    # 单独构造 actor 时也要补齐训练时由 set_model_params 注入的组件
    from .config import Config
    cfg = Config()
    cfg.agent_class = agent_cls
    cfg.if_discrete = bool(config.get('if_discrete', True))
    cfg.Loss = Loss.MSELoss(reduction='none')
    cfg.Optim = Optim.AdamW()
    cfg.Activation = Activation.Tanh10()
    actor = agent_cls(
        list(config['net_dims']), int(config['state_dim']),
        int(config['action_dim']), gpu_id=-1, args=cfg,
    ).act
    state = torch.load(actor_path, map_location=device, weights_only=False)
    if hasattr(state, 'state_dict'):
        state = state.state_dict()
    actor.load_state_dict(state)
    actor.to(device)
    actor.eval()
    return actor, config


__all__ = ['best_model_config', 'save_best_model', 'load_best_actor']
