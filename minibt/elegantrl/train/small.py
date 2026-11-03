"""小样本 RL 的保守配置。"""
from __future__ import annotations

SMALL_NET_DIMS = (64, 32)
TINY_NET_DIMS = (32, 32)

#: 小样本优先尝试的离散算法（按经验排序，不强制）
SMALL_DISCRETE_AGENTS = (
    'discrete-ppo', 'd3qn', 'double-dqn', 'dueling-dqn', 'ensemble-dqn',
)


def small_model_kwargs(*, net_dims=SMALL_NET_DIMS, if_discrete: bool = True,
                       action_dim: int | None = None,
                       eval_env_class=None, eval_score=None,
                       min_start_mode: str = 'random',
                       **overrides) -> dict:
    """返回适合小样本的 ``set_model_params`` 参数。

    默认值刻意保守：CPU、单环境、小网络、短 horizon、固定 seed。
    数据量足够时再覆盖 ``net_dims`` / ``horizon_len`` / ``batch_size``。
    """
    kwargs = dict(
        if_discrete=bool(if_discrete),
        net_dims=tuple(net_dims),
        batch_size=64,
        horizon_len=128,
        repeat_times=2.0,
        eval_per_step=5e3,
        eval_times=1,
        gpu_id=-1,
        num_workers=1,
        num_threads=1,
        dropout_rate=0.1,
        random_seed=42,
        min_start_mode=str(min_start_mode),
    )
    if action_dim is not None:
        kwargs['action_dim'] = int(action_dim)
    if eval_env_class is not None:
        kwargs['eval_env_class'] = eval_env_class
    if eval_score is not None:
        kwargs['eval_score'] = eval_score
    kwargs.update(overrides)
    return kwargs


def apply_small_model_params(strategy, agent, **kwargs):
    """在 ``Strategy`` 上应用小样本默认参数。"""
    return strategy.set_model_params(
        agent, **small_model_kwargs(**kwargs))


__all__ = [
    'SMALL_NET_DIMS', 'TINY_NET_DIMS', 'SMALL_DISCRETE_AGENTS',
    'small_model_kwargs', 'apply_small_model_params',
]
