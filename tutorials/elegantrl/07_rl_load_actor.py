"""旧 ``77_1 / 700005`` 的“加载 actor 推理”整理版。

这两个旧文件的核心不是训练，而是：

    1. 构造同一个策略 / 特征 / 动作空间
    2. set_model_params(train=False, actor_path=...)
    3. load_agent() → 用 actor 推理回测

这个示例复用 ``05_rl_hold_days.py`` 的环境，只把 ``TRAIN`` 设为 False。
先跑一次 05 生成模型，再跑本文件：

    python tutorials/elegantrl/05_rl_hold_days.py --steps 64
    python tutorials/elegantrl/07_rl_load_actor.py --check
    python tutorials/elegantrl/07_rl_load_actor.py

也可以显式指定 actor：

    python tutorials/elegantrl/07_rl_load_actor.py \
        --actor ~/.minibt/models/rl_hold_discrete-ppo/act.pth
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import pathlib
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from minibt import Bt  # noqa: E402

_MODULE = pathlib.Path(__file__).with_name('05_rl_hold_days.py')
_SPEC = importlib.util.spec_from_file_location('rl_hold_days', _MODULE)
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)

DEFAULT_ACTOR = os.path.join(
    os.path.expanduser('~'), '.minibt', 'models',
    'rl_hold_discrete-ppo', 'act.pth')


def _policy(actor: str):
    return _MOD.RLHoldDays.copy(
        name='RLHoldDaysLoaded',
        TRAIN=False,
        ACTOR_PATH=actor,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='加载 RL actor 推理')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--actor', default=DEFAULT_ACTOR)
    args = parser.parse_args()
    actor = os.path.abspath(os.path.expanduser(args.actor))

    if not os.path.isfile(actor):
        print('找不到 actor:', actor)
        print('请先训练：python tutorials/elegantrl/05_rl_hold_days.py --steps 64')
        return 2

    policy = _policy(actor)
    if args.check:
        strategy = policy()
        strategy._prepare_before_strategy_start()
        print('actor:', actor)
        print('state_dim:', strategy.state_dim)
        print('action_dim:', strategy.action_dim)
        print('if_discrete:', strategy.if_discrete)
        print('[example] actor 推理配置检查通过')
        return 0

    bt = Bt(auto=False)
    bt.addstrategy(policy)
    bt.run(isplot=False, isreport=False)
    print('[example] actor 推理完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
