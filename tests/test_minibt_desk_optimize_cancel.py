"""参数优化取消：Optuna callback 调用 study.stop() ✓"""
from __future__ import annotations

from minibt.desk.strategy_lab import StrategyLab


class _Desk:
    def __init__(self):
        self.patches = []

    def push(self, patch):
        self.patches.append(patch)


def test_optuna_callback_stops_study_when_cancelled():
    lab = StrategyLab(_Desk(), 'cancel-test')
    lab._stop = True
    stopped = []

    class Study:
        def stop(self):
            stopped.append(True)

    class Trial:
        number = 2

    lab._optuna_callback(total=10)(Study(), Trial())
    assert stopped == [True]


def test_optuna_callback_progress_normal():
    lab = StrategyLab(_Desk(), 'progress-test')

    class Trial:
        number = 2

    lab._optuna_callback(total=10)(object(), Trial())
    assert lab.progress_current == 3
    assert lab.progress_total == 10


def test_run_with_cancel_installs_and_restores_check():
    lab = StrategyLab(_Desk(), 'cancel-run')

    class StrategyClass:
        pass

    class FakeBt:
        strategies = [StrategyClass]

        def run(self, **kwargs):
            check = getattr(StrategyClass, '_cancel_check')
            assert check() is False
            lab._stop = True
            assert check() is True

    lab._run_with_cancel(FakeBt())
    assert '_cancel_check' not in StrategyClass.__dict__
