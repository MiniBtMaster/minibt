"""RL 实验门面：walk-forward / 多 seed / 报告 / 部署。

它只做编排，不绑定具体策略；单模型训练仍然由 Strategy 自己完成。
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

from .deploy import best_model_config, save_best_model
from .report import (
    best_runs, best_seed, save_walk_forward_html, save_walk_forward_report,
)
from .walk_forward import (
    Fold, WalkForwardRun, make_folds, run_walk_forward_ensemble,
    runs_to_frame, summarize_runs,
)
from .ensemble import seed_list, seed_dir


class RlExperiment:
    """一组 RL 实验（walk-forward × 多 seed）。

    ``make_strategy(frame, seed, role)`` 构造策略；``role`` 为
    ``train / val / test``（可通过 ``role_aware=False`` 改为两参数）。
    ``train_one(train, val, test, seed)`` 负责训练 / 选模并返回一个带
    ``profits`` 的对象（或任意 ``metrics_fn`` 能处理的对象）。
    """

    def __init__(
        self,
        df,
        make_strategy: Callable[..., Any],
        train_one: Callable[..., Any], *,
        seeds: Iterable[int] = (42,),
        train_size: int,
        val_size: int,
        test_size: int,
        step: int | None = None,
        purge: int = 0,
        role_aware: bool = True,
        metrics_fn: Callable[..., dict] | None = None,
    ):
        self.df = df
        self.make_strategy = make_strategy
        self.train_one = train_one
        self.seeds = tuple(int(x) for x in seeds) or seed_list(1)
        self.train_size = int(train_size)
        self.val_size = int(val_size)
        self.test_size = int(test_size)
        self.step = step
        self.purge = int(purge)
        self.role_aware = bool(role_aware)
        self.metrics_fn = metrics_fn
        self.runs: list[WalkForwardRun] = []
        self.folds: list[Fold] = []

    # ------------------------------------------------------------ 执行
    def walk_forward(self) -> list[WalkForwardRun]:
        self.runs = list(run_walk_forward_ensemble(
            self.df,
            self.make_strategy,
            self.train_one,
            seeds=self.seeds,
            train_size=self.train_size,
            val_size=self.val_size,
            test_size=self.test_size,
            step=self.step,
            purge=self.purge,
            role_aware=self.role_aware,
            metrics_fn=self.metrics_fn,
        ))
        self.folds = [run.fold for run in self.runs]
        return self.runs

    run = walk_forward

    # ------------------------------------------------------------ 选择
    def best_run(self, metric: str = 'sharpe') -> WalkForwardRun | None:
        runs = best_runs(self.runs, metric=metric, n=1)
        return runs[0] if runs else None

    def best_seed(self, metric: str = 'sharpe') -> int | None:
        return best_seed(self.runs, metric=metric)

    # ------------------------------------------------------------ 导出
    def to_frame(self):
        return runs_to_frame(self.runs)

    def summary(self):
        return summarize_runs(self.runs)

    def save_csv(self, path: str) -> str:
        from .walk_forward import save_runs_csv
        return save_runs_csv(self.runs, path)

    def save_report(self, path: str,
                    title: str = 'RL walk-forward report') -> str:
        return save_walk_forward_report(self.runs, path, title=title)

    def save_html(self, path: str,
                  title: str = 'RL walk-forward report') -> str:
        return save_walk_forward_html(self.runs, path, title=title)

    # ------------------------------------------------------------ 部署
    def deploy_config(self, metric: str = 'sharpe') -> dict:
        return best_model_config(self.runs, metric=metric)

    def deploy(self, target_dir: str, metric: str = 'sharpe') -> str:
        return save_best_model(self.runs, target_dir, metric=metric)


__all__ = ['RlExperiment']
