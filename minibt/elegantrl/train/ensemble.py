"""多随机种子 / 动作集成的小工具。

ElegantRL 对 seed 很敏感；这里只提供**不绑定具体策略**的编排：

- ``seed_list``：生成常用 seed；
- ``seed_dir``：为每个 seed 生成独立模型目录；
- ``train_seed_ensemble``：对每个 seed 创建策略并训练；
- ``aggregate_actions``：离散动作多数投票 / 连续动作平均。
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Iterator

import numpy as np


def seed_list(count: int = 5, start: int = 42) -> tuple[int, ...]:
    """``(42, 43, ...)`` 形式的 seed 列表。"""
    count = max(1, int(count))
    return tuple(range(int(start), int(start) + count))


def seed_dir(base: str, seed: int) -> str:
    """给每个 seed 一个独立 cwd，避免覆盖 checkpoint。"""
    return f'{str(base).rstrip("_-/")}_seed{int(seed)}'


def train_seed_ensemble(make_strategy: Callable[[int], Any],
                        seeds: Iterable[int],
                        train_one: Callable[[Any], Any] | None = None
                        ) -> Iterator[tuple[int, Any]]:
    """逐个 seed 创建策略并训练。

    ``make_strategy(seed)`` 必须已经设置好 ``random_seed`` / ``cwd`` 等；
    ``train_one(strategy)`` 默认调用 ``strategy.train_agent()``。生成器让调用方
    可以边训练边保存结果，避免一次把所有模型放在内存里。
    """
    for seed in seeds:
        strategy = make_strategy(int(seed))
        if train_one is None:
            strategy.train_agent()
        else:
            train_one(strategy)
        yield int(seed), strategy


def aggregate_actions(actions, *, if_discrete: bool = False):
    """把多个 actor 的动作合成一个。

    Args:
        actions: ``list[array]``，每个 actor 一个动作数组；形状相同。
        if_discrete: True → 逐样本多数投票；False → 平均后裁剪到 [-1, 1]。

    Returns:
        与单个动作相同形状的 numpy 数组。
    """
    arr = np.asarray(actions)
    if arr.ndim == 0:
        return arr
    if if_discrete:
        # 形状 (n_actors, ...) → 对 axis=0 做多数投票
        out = np.empty(arr.shape[1:], dtype=arr.dtype)
        flat = arr.reshape(arr.shape[0], -1)
        voted = []
        for col in range(flat.shape[1]):
            values, counts = np.unique(flat[:, col], return_counts=True)
            voted.append(values[np.argmax(counts)])
        out[...] = np.asarray(voted).reshape(arr.shape[1:])
        return out
    return np.clip(arr.mean(axis=0), -1.0, 1.0)


__all__ = ['seed_list', 'seed_dir', 'train_seed_ensemble',
           'aggregate_actions']
