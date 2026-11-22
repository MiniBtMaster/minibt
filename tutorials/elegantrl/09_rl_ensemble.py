"""多 seed actor 集成推理（discrete 动作）。

流程::

    一个 fold
        ↓
    seed=42 / 43 ... 各训练一个 actor
        ↓
    每个 actor 单独在 test 评估
        ↓
    aggregate_actions(if_discrete=True) 多数投票
        ↓
    ensemble test 指标 + 最佳单 actor

运行::

    python tutorials/elegantrl/09_rl_ensemble.py --check
    python tutorials/elegantrl/09_rl_ensemble.py --steps 32 --seeds 2
    python tutorials/elegantrl/09_rl_ensemble.py --steps 32 --seeds 2 \
        --csv results/ens.csv --report results/ens.md --html results/ens.html
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from minibt.elegantrl.train import (  # noqa: E402
    WalkForwardRun, save_runs_csv, save_walk_forward_html,
    save_walk_forward_report, seed_list,
)
from _rl_common import make_fold, policy, run_test  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='多 seed actor 集成推理')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--steps', type=int, default=32)
    parser.add_argument('--seeds', type=int, default=2)
    parser.add_argument('--csv', default='')
    parser.add_argument('--report', default='')
    parser.add_argument('--html', default='')
    args = parser.parse_args()

    folds = make_fold()
    if not folds:
        print('数据不足')
        return 2
    fold = folds[0]
    seeds = seed_list(args.seeds)

    if args.check:
        print('seeds:', seeds)
        print('train:', len(fold.train), 'test:', len(fold.test))
        print('动作聚合: 离散多数投票')
        print('[example] ensemble 配置检查通过')
        return 0

    actors = []
    feature_state = None
    for seed in seeds:
        TrainPolicy = policy(
            'train', fold.train, train=True, steps=args.steps,
            tag=str(seed), fit_range=(0, len(fold.train)))
        train = TrainPolicy()
        train._prepare_before_strategy_start()
        # 所有 seed 用同一个 train fold；拿第一份预处理状态给 test 复用
        if feature_state is None:
            feature_state = train.get_quant_feature_state()
        print(f'training seed {seed}...')
        train.train_agent()
        train.load_agent()
        actors.append(train.actor)

    individual = []
    for seed, actor in zip(seeds, actors):
        m, equity = run_test(
            [actor], fold, args.steps, f'actor_{seed}',
            feature_state=feature_state)
        individual.append((seed, m, equity))
        print(f'actor seed {seed}:',
              {k: round(m[k], 5) for k in
               ('total_return', 'sharpe', 'max_drawdown')})

    metrics, _ensemble_equity = run_test(
        actors, fold, args.steps, 'ensemble',
        feature_state=feature_state)
    print('ensemble    :', {k: round(metrics[k], 5) for k in
                            ('total_return', 'sharpe', 'max_drawdown')})
    best = max(individual, key=lambda item: item[1].get('sharpe', -1e9))
    print(f'最佳单 actor: seed={best[0]} '
          f'sharpe={best[1].get("sharpe", 0):.4f}')

    if args.csv or args.report or args.html:
        runs = [WalkForwardRun(fold, seed, None, None, m, equity=equity)
                for seed, m, equity in individual]
        if args.csv:
            save_runs_csv(runs, args.csv)
            print('CSV:', args.csv)
        if args.report:
            save_walk_forward_report(runs, args.report,
                                     title='RL ensemble actors')
            print('报告:', args.report)
        if args.html:
            save_walk_forward_html(runs, args.html,
                                   title='RL ensemble actors')
            print('HTML:', args.html)
    print(f'[example] {len(actors)} 个 actor 的 ensemble 推理完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
