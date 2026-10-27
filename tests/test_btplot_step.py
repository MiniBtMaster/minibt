"""btplot 的「指标自带 step」路径：必须把指标登记到策略的 ``_btindicatordataset``。

历史 bug：``_BtplotStep`` 只在 ``next()`` 里调 ``ind.step()``，没有把指标作为**属性
赋值**，于是 ``Strategy.__setattr__`` 不登记 → 图表端拿不到任何指标 →
pylightcharts 模式下**指标与信号一片空白**（当时把 ``step`` 改名成 ``__step``、
让 btplot 走纯图表路径才会显示，但那样就丢了交易逻辑）。
"""
import numpy as np


def test_single_ema_cross_step_is_public():
    """`SingleEMACross` 的交易逻辑必须是**公开的** ``step``。

    写成 ``__step`` 会被名字 mangle 成 ``_SingleEMACross__step``，``btplot`` 的
    ``'step' in ind.__dict__`` 判定不到交易逻辑（回测/实时里 ``ind.step()`` 也调不到）。
    """
    from minibt import LocalDatas
    ind = LocalDatas.test.kline.tradingview.SingleEMACross()
    assert 'step' in ind.__dict__
    assert '_SingleEMACross__step' not in ind.__dict__
    assert callable(ind.step)


def test_make_step_strategy_registers_indicators_for_chart():
    """带 ``step`` 的指标也要出现在 ``_btindicatordataset`` 里（图表才画得出来）。"""
    from minibt import LocalDatas
    from minibt.utils import Config
    import minibt.btplot as btp

    k = LocalDatas.test.kline
    ind = k.tradingview.SingleEMACross()
    strat = btp._make_step_strategy(k, [ind], Config(theme='dark'),
                                    'SingleEMACross')
    strat._start_strategy_run()

    assert 'SingleEMACross' in strat._btindicatordataset, \
        list(strat._btindicatordataset.keys())
    frame = strat._btindicatordataset['SingleEMACross']
    cols = list(frame.pandas_object.columns)
    assert cols[:2] == ['ema_fast', 'ema_slow'], cols
    assert int(np.nansum(np.asarray(frame['long_signal'].values, dtype=float))) > 0
    assert int(np.nansum(np.asarray(frame['short_signal'].values, dtype=float))) > 0
    # 交易逻辑仍然在跑（有回测结果）
    assert strat._results, '带 step 的指标应当跑出回测结果'


def test_btplot_resets_stale_stop_lines():
    """btplot 出图前要清掉上一次回测留在 K 线上的止损/止盈线。

    K 线（``LocalDatas.xxx.kline``）在同一个 notebook / 进程里是**共享对象**：
    先用带 ``step`` 的指标跑一次 btplot（生成 ``stop_price`` / ``target_price``），
    再用同一个 K 线看别的指标时，止损线会泄漏成新图上的两条线 ✗。
    """
    import minibt.btplot as btp

    class _Setting:
        stop_lines = object()
        stop = object()
        isstop = True

    class _Kline:
        _klinesetting = _Setting()

    k = _Kline()
    btp._reset_kline_stop_lines(k)

    assert k._klinesetting.stop_lines is None
    assert k._klinesetting.stop is None
    assert k._klinesetting.isstop is False


def test_kline_reset_stop_lines_clears_shared_state():
    """`KLine.reset_stop_lines()` 清掉共享 K 线上的停止线 / 停止器 / 停止状态。"""
    from minibt import LocalDatas

    k = LocalDatas.test.kline
    setting = k._klinesetting
    setting.stop_lines = object()
    setting.stop = object()
    setting.isstop = True

    assert k.reset_stop_lines() is k
    assert setting.stop_lines is None
    assert setting.stop is None
    assert setting.isstop is False


def test_btplot_does_not_duplicate_indicator():
    """``_chain`` 去重：同一个指标不能被登记两次（否则图上画两遍）。"""
    from minibt import LocalDatas
    from minibt.utils import Config
    import minibt.btplot as btp

    k = LocalDatas.test.kline
    ind = k.tradingview.SingleEMACross()
    # btplot 内部会把 `indicator` 本身也放进 `indicators`，这里模拟那种输入
    strat = btp._make_step_strategy(k, [ind, ind], Config(theme='dark'), 'Dup')
    strat._start_strategy_run()
    names = list(strat._btindicatordataset.keys())
    assert len([n for n in names if n.startswith('SingleEMACross')]) == 1, names
