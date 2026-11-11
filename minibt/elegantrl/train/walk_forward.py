"""Walk-forward 训练/评估的小工具。

与 ``splits.py`` 的分工：

- ``splits.py``：只负责 index / DataFrame 切分；
- ``walk_forward.py``：把一个窗口变成 ``train / val / test`` 三份数据，
  并提供 ``run_walk_forward(...)`` 回调式执行器。

示例::

    from minibt.elegantrl.train.walk_forward import (
        make_folds, run_walk_forward)

    def make_strategy(frame, train=True):
        Policy = MyPolicy.copy(DATA=frame)
        return Policy()

    def train_one(train, val, test):
        train._rl_config.eval_env_class = val
        train.train_agent()
        return train

    for fold, trained in run_walk_forward(
        df, make_strategy, train_one,
        train_size=1200, val_size=300, test_size=300,
        step=300, purge=60,
    ):
        ...
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Iterator

from .splits import TimeWindow, walk_forward_windows
from .metrics import equity_metrics


@dataclass(frozen=True)
class Fold:
    """一份 walk-forward 数据，以及对应的 index 窗口。"""

    window: TimeWindow
    train: Any
    val: Any
    test: Any

    @property
    def fit_range(self) -> tuple[int, int]:
        """原始 df 上的训练区间（用于日志 / 全量数据）。"""
        return self.window.train_start, self.window.train_end

    @property
    def local_fit_range(self) -> tuple[int, int]:
        """局部 ``fold.train`` 上的 fit_range，可直接传给策略。"""
        return 0, self.window.train_end - self.window.train_start


def _take(frame, window: TimeWindow):
    """优先 DataFrame 的 iloc，兼容普通序列。"""
    def one(sl):
        part = frame.iloc[sl] if hasattr(frame, 'iloc') else frame[sl]
        return part.copy() if hasattr(part, 'copy') else part
    return one(window.train), one(window.val), one(window.test)


def make_folds(df, *, train_size: int, val_size: int, test_size: int,
               step: int | None = None,
               purge: int = 0) -> Iterator[Fold]:
    """按 walk-forward 窗口生成 ``Fold(train, val, test)``。"""
    for window in walk_forward_windows(
            len(df), train_size=train_size, val_size=val_size,
            test_size=test_size, step=step, purge=purge):
        train, val, test = _take(df, window)
        yield Fold(window, train, val, test)


def run_walk_forward(df, make_strategy: Callable[..., Any],
                     train_one: Callable[..., Any], *,
                     train_size: int, val_size: int, test_size: int,
                     step: int | None = None,
                     purge: int = 0) -> Iterator[tuple[Fold, Any]]:
    """对每个 fold 调用 ``train_one(train, val, test)``。

    ``make_strategy(frame)`` 负责把 DataFrame 变成同结构的 Strategy；
    ``train_one`` 负责设置独立 eval env、训练和选模。执行器不绑定具体策略，
    因此可用于 RL / 普通策略 / 自己的实验类。
    """
    for fold in make_folds(
            df, train_size=train_size, val_size=val_size,
            test_size=test_size, step=step, purge=purge):
        train = make_strategy(fold.train)
        val = make_strategy(fold.val)
        test = make_strategy(fold.test)
        result = train_one(train, val, test)
        yield fold, result


__all__ = ['Fold', 'make_folds', 'run_walk_forward']



@dataclass(frozen=True)
class WalkForwardRun:
    """一个 ``(fold, seed)`` 的训练结果。"""

    fold: Fold
    seed: int
    strategy: Any
    result: Any
    metrics: dict
    #: 可选：test / result 的权益曲线，HTML 报告可画迷你曲线
    equity: Any = None


def _default_metrics(result: Any, *envs: Any) -> dict:
    """默认从 result / env 的 ``profits`` 提取净指标。"""
    for obj in (result, *envs):
        if obj is None:
            continue
        equity = getattr(obj, 'profits', None)
        if equity is not None:
            try:
                return equity_metrics(equity)
            except Exception:
                continue
    return {}


def run_walk_forward_ensemble(
        df,
        make_strategy: Callable[..., Any],
        train_one: Callable[..., Any], *,
        seeds: Iterable[int] = (42,),
        train_size: int, val_size: int, test_size: int,
        step: int | None = None,
        purge: int = 0,
        metrics_fn: Callable[..., dict] | None = None,
        role_aware: bool = False,
) -> Iterator[WalkForwardRun]:
    """walk-forward × 多 seed 的高层编排。

    ``make_strategy(frame, seed)`` 负责构造同结构策略；
    ``train_one(train, val, test, seed)`` 负责设置独立 eval env、训练和选模；
    ``metrics_fn(fold, seed, result, strategy, test)`` 可覆盖默认净指标。

    只做编排，不绑定 ElegantRL / 普通策略；因此可以逐步迁移旧实验。
    """
    from .ensemble import seed_list
    seed_values = tuple(int(x) for x in seeds) or seed_list(1)
    for fold in make_folds(
            df, train_size=train_size, val_size=val_size,
            test_size=test_size, step=step, purge=purge):
        for seed in seed_values:
            if role_aware:
                train = make_strategy(fold.train, seed, role='train')
                val = make_strategy(fold.val, seed, role='val')
                test = make_strategy(fold.test, seed, role='test')
            else:
                train = make_strategy(fold.train, seed)
                val = make_strategy(fold.val, seed)
                test = make_strategy(fold.test, seed)
            result = train_one(train, val, test, seed)
            if metrics_fn is not None:
                metrics = dict(metrics_fn(fold, seed, result, train, test))
            else:
                metrics = _default_metrics(result, train, test)
            equity = None
            for obj in (result, train, test):
                eq = getattr(obj, 'profits', None)
                if eq is not None:
                    equity = eq
                    break
            yield WalkForwardRun(fold, seed, train, result, metrics,
                                 equity=equity)


def runs_to_frame(runs: Iterable[WalkForwardRun]):
    """把 run 转成 pandas DataFrame（便于汇总 / 导出 CSV）。"""
    import pandas as pd
    rows = []
    for index, run in enumerate(runs):
        row = {'fold': index, 'seed': run.seed}
        row.update(run.metrics)
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_runs(runs: Iterable[WalkForwardRun]):
    """按 seed 汇总 metrics：``mean`` / ``std``。"""
    df = runs_to_frame(runs)
    if df.empty:
        return df
    numeric = df.select_dtypes(include='number').columns.drop(
        'fold', errors='ignore')
    return df.groupby('seed')[list(numeric)].agg(['mean', 'std'])


def save_runs_csv(runs: Iterable[WalkForwardRun], path: str) -> str:
    """保存逐 fold / seed 的 metrics；父目录不存在会自动创建。"""
    import os
    df = runs_to_frame(runs)
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    df.to_csv(path, index=False)
    return path


__all__ = ['Fold', 'make_folds', 'run_walk_forward',
           'WalkForwardRun', 'run_walk_forward_ensemble',
           'runs_to_frame', 'summarize_runs', 'save_runs_csv']
