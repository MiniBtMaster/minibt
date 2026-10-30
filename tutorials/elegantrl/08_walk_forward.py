"""Walk-forward + 独立验证环境（使用 05 的 RLHoldDays 策略）。

流程::

    make_fold(df) → train / val / test
        ↓
    train：FIT_RANGE=fold.local_fit_range
    validation：独立 eval_env，不参与训练
    test：加载训练好的 actor，最后只报告一次
        ↓
    equity_metrics(test) + CSV / Markdown / HTML / deploy

运行::

    python tutorials/elegantrl/08_walk_forward.py --check
    python tutorials/elegantrl/08_walk_forward.py --steps 64
    python tutorials/elegantrl/08_walk_forward.py --all-folds --steps 64 \
        --csv results/wf.csv --report results/wf.md \
        --html results/wf.html --deploy results/deploy
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
    WalkForwardRun, best_runs, best_seed, save_best_model, save_runs_csv,
    save_walk_forward_html, save_walk_forward_report, seed_list,
    summarize_runs,
)
from _rl_common import make_fold, policy, run_test  # noqa: E402


def _run_fold(fold, fold_index: int, seed: int, steps: int) -> WalkForwardRun:
    tag = f'{fold_index}_{seed}'
    TrainPolicy = policy(
        'train', fold.train, train=True, steps=steps, tag=tag,
        fit_range=fold.local_fit_range)

    train = TrainPolicy()
    train._prepare_before_strategy_start()
    # ★ train 已 fit 好 scaler / PCA / 异常值阈值 / 保留列
    feature_state = train.get_quant_feature_state()

    # validation 只做评估：train=True 让它走 reward 分支，不真正下单；
    # 同时复用 train 的预处理状态，避免 val 自己 fit 造成口径不一致 ✓
    ValPolicy = policy(
        'val', fold.val, train=True, steps=steps, tag=tag,
        feature_state=feature_state)
    val = ValPolicy()
    val._prepare_before_strategy_start()

    # 独立验证环境：Evaluator 用它选模
    train._rl_config.eval_env_class = val
    train.train_agent()
    train.load_agent()

    # test 也复用 train 的预处理状态；run_test 返回 test 净指标 + 权益曲线
    metrics, equity = run_test(
        [train.actor], fold, steps, f'fold{fold_index}_{seed}',
        feature_state=feature_state)
    return WalkForwardRun(fold, seed, train, None, metrics, equity=equity)


def main() -> int:
    parser = argparse.ArgumentParser(description='RL walk-forward 示例')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--steps', type=int, default=64)
    parser.add_argument('--fold', type=int, default=0)
    parser.add_argument('--all-folds', action='store_true')
    parser.add_argument('--seeds', type=int, default=1,
                        help='每个 fold 跑几个 seed（默认 1）')
    parser.add_argument('--csv', default='./results/walk_forward.csv')
    parser.add_argument('--report', default='',
                        help='可选 Markdown 报告路径')
    parser.add_argument('--html', default='',
                        help='可选 HTML 报告路径')
    parser.add_argument('--deploy', default='',
                        help='把最佳 actor 复制到该目录并写 config.json')
    parser.add_argument('--metric', default='sharpe',
                        help='最佳 run 的指标（默认 sharpe）')
    args = parser.parse_args()

    folds = make_fold()
    if not folds:
        print('数据不足，无法生成 fold')
        return 2
    selected = folds if args.all_folds else [
        folds[min(args.fold, len(folds) - 1)]]
    seeds = seed_list(args.seeds)

    if args.check:
        print('fold 数:', len(folds), '| 本次:', len(selected))
        print('seeds:', seeds)
        print('fold[0] 窗口:', selected[0].window)
        print('train:', len(selected[0].train),
              'val:', len(selected[0].val),
              'test:', len(selected[0].test))
        print('fit_range(original):', selected[0].fit_range)
        print('fit_range(local):', selected[0].local_fit_range)
        print('train / validation / test 环境相互独立')
        print('[example] walk-forward 配置检查通过')
        return 0

    runs = []
    for fold_index, fold in enumerate(selected):
        for seed in seeds:
            print(f'[fold {fold_index} seed {seed}] training...')
            run = _run_fold(fold, fold_index, seed, args.steps)
            runs.append(run)
            m = run.metrics
            print(f'  test: total_return={m.get("total_return", 0):.5f} '
                  f'sharpe={m.get("sharpe", 0):.4f} '
                  f'max_drawdown={m.get("max_drawdown", 0):.5f}')

    if len(runs) > 1:
        save_runs_csv(runs, args.csv)
        print('汇总:')
        print(summarize_runs(runs).to_string())
        print('CSV:', args.csv)
        if args.report:
            save_walk_forward_report(runs, args.report)
            print('报告:', args.report)
        if args.html:
            save_walk_forward_html(runs, args.html)
            print('HTML:', args.html)
        print(f'最佳 seed(按 {args.metric}):',
              best_seed(runs, metric=args.metric))
        best = best_runs(runs, metric=args.metric, n=1)[0]
        cwd = getattr(getattr(best.strategy, '_rl_config', None),
                      'cwd', '')
        print(f'最佳 run: seed={best.seed} '
              f'{args.metric}={best.metrics.get(args.metric, 0):.5f}')
        if cwd:
            print('最佳模型目录:', cwd)

    if args.deploy:
        path = save_best_model(runs, args.deploy, metric=args.metric)
        print('部署配置:', path)
    print(f'[example] walk-forward 完成（{len(runs)} 个 run）')
    print('模型目录: ~/.minibt/models/rl_*_*')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
