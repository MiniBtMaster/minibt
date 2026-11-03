"""从 08 的部署目录加载 actor，复现 test 推理。

前置：

    python tutorials/elegantrl/08_walk_forward.py \
        --steps 64 --deploy results/deploy

运行：

    python tutorials/elegantrl/10_deploy_inference.py --check
    python tutorials/elegantrl/10_deploy_inference.py \
        --config results/deploy/config.json
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from minibt import LocalDatas  # noqa: E402
from minibt.elegantrl.train import (  # noqa: E402
    Fold, TimeWindow, load_best_actor,
)
from _rl_common import run_test  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='加载部署 actor 复现 test')
    parser.add_argument('--config', default=os.path.join(
        os.path.expanduser('~'), '.minibt', 'models', 'deploy', 'config.json'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()

    config_path = os.path.abspath(os.path.expanduser(args.config))
    if not os.path.isfile(config_path):
        print('找不到部署配置:', config_path)
        print('请先运行：')
        print('  python tutorials/elegantrl/08_walk_forward.py '
              '--steps 64 --deploy results/deploy')
        return 2

    actor, config = load_best_actor(config_path, device='cpu')
    fold_cfg = config.get('fold') or {}
    if not fold_cfg:
        print('config.json 缺少 fold 信息，请用新版 08 重新生成部署目录')
        return 2

    if args.check:
        print('config:', config_path)
        print('agent:', config.get('agent'))
        print('seed:', config.get('seed'))
        print('fold:', fold_cfg)
        print('metrics:', config.get('metrics'))
        print('[example] 部署 actor 检查通过')
        return 0

    df = LocalDatas.test.kline.pandas_object
    test = df.iloc[int(fold_cfg['test_start']):int(fold_cfg['test_end'])].copy()
    window = TimeWindow(
        int(fold_cfg['train_start']), int(fold_cfg['train_end']),
        int(fold_cfg['val_start']), int(fold_cfg['val_end']),
        int(fold_cfg['test_start']), int(fold_cfg['test_end']))
    fold = Fold(window, [], [], test)
    metrics, _equity = run_test([actor], fold, 1, 'deploy')
    print('test:', {k: round(float(metrics[k]), 5) for k in
                    ('total_return', 'sharpe', 'max_drawdown')})
    print('[example] 部署 actor test 推理完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
