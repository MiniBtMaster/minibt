"""RlExperiment / Bt.rl_experiment 的使用例子。

演示如何把单模型 Strategy 的训练，交给高层实验门面：

    RlExperiment(df, make_strategy, train_one, ...)
        ↓
    walk_forward()
        ↓
    summary / best_seed / best_run
        ↓
    CSV / Markdown / HTML / deploy

运行::

    python tutorials/elegantrl/11_rl_experiment.py --check
    python tutorials/elegantrl/11_rl_experiment.py --steps 32
    python tutorials/elegantrl/11_rl_experiment.py --steps 32 --bt
"""
from __future__ import annotations

import argparse
import os
import sys
from types import SimpleNamespace

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from minibt import Bt, LocalDatas  # noqa: E402
from minibt.elegantrl.train import (  # noqa: E402
    RlExperiment, equity_metrics, make_folds, seed_list,
)
from _rl_common import policy  # noqa: E402

_FOLD = 0


def make_strategy(frame, seed, role):
    """给 RlExperiment 的 role-aware 工厂。"""
    global _FOLD
    tag = f'{_FOLD}_{seed}'
    if role == 'train':
        _FOLD += 1
    return policy(
        role, frame,
        train=(role != 'test'),
        steps=_STEPS,
        tag=tag,
        fit_range=(0, len(frame)) if role == 'train' else None,
    )()


def train_one(train, val, test, seed):
    """训练一个 fold；返回带 profits 的结果对象。"""
    train._prepare_before_strategy_start()
    val._prepare_before_strategy_start()
    test._prepare_before_strategy_start()
    train._rl_config.eval_env_class = val
    train.train_agent()
    train.load_agent()

    test.actor = train.actor
    test.device = train.device
    test._state, _ = test.reset()
    test._execute_core_trading_loop()
    return SimpleNamespace(profits=test.profits)


_STEPS = 32


def main() -> int:
    global _STEPS
    parser = argparse.ArgumentParser(description='RlExperiment 使用示例')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--steps', type=int, default=32)
    parser.add_argument('--seeds', type=int, default=1)
    parser.add_argument('--bt', action='store_true',
                        help='从 Bt.rl_experiment 入口创建')
    parser.add_argument('--csv', default='')
    parser.add_argument('--report', default='')
    parser.add_argument('--html', default='')
    parser.add_argument('--deploy', default='')
    args = parser.parse_args()
    _STEPS = int(args.steps)

    df = LocalDatas.test.kline.pandas_object
    folds = list(make_folds(
        df, train_size=600, val_size=200, test_size=200,
        step=1000, purge=60))
    if not folds:
        print('数据不足')
        return 2

    if args.check:
        print('fold 数:', len(folds))
        print('seeds:', seed_list(args.seeds))
        print('工厂签名: make_strategy(frame, seed, role)')
        print('train_one 签名: train_one(train, val, test, seed)')
        print('[example] RlExperiment 配置检查通过')
        return 0

    factory = Bt(auto=False).rl_experiment if args.bt else RlExperiment
    exp = factory(
        df, make_strategy, train_one,
        seeds=seed_list(args.seeds),
        train_size=600, val_size=200, test_size=200,
        step=1000, purge=60,
        role_aware=True,
    )
    runs = exp.walk_forward()
    print('runs:', len(runs))
    print(exp.summary().to_string())
    print('best seed:', exp.best_seed())
    best = exp.best_run()
    if best is not None:
        print('best test:', {k: round(float(best.metrics[k]), 5) for k in
                             ('total_return', 'sharpe', 'max_drawdown')
                             if k in best.metrics})
    if args.csv:
        print('CSV:', exp.save_csv(args.csv))
    if args.report:
        print('报告:', exp.save_report(args.report))
    if args.html:
        print('HTML:', exp.save_html(args.html))
    if args.deploy:
        print('部署配置:', exp.deploy(args.deploy))
    print('[example] RlExperiment 完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
