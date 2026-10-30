"""tutorials/elegantrl 示例的轻量护栏。

只跑 ``--check``，不训练 / 不优化；真正的耗时用例在示例脚本里手动运行。
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'tutorials' / 'elegantrl'


def _run(name: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault('PYTHONIOENCODING', 'utf-8')
    return subprocess.run(
        [sys.executable, str(EXAMPLES / name), '--check'],
        cwd=ROOT, env=env, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=120,
    )


@pytest.mark.parametrize('name', [
    '01_next_optuna.py',
    '02_signal_cython_optimize.py',
    '04_parameter_bandit.py',
    '05_rl_hold_days.py',
    '06_rl_pair.py',
    '08_walk_forward.py',
    '09_rl_ensemble.py',
    '11_rl_experiment.py',
])
def test_optimizer_examples_check(name):
    result = _run(name)
    assert result.returncode == 0, result.stderr[-1000:]
    assert '检查通过' in result.stdout


def test_rl_position_example_check():
    pytest.importorskip('torch')
    result = _run('03_rl_position.py')
    assert result.returncode == 0, result.stderr[-1500:]
    assert 'state_dim:' in result.stdout
    assert '检查通过' in result.stdout
