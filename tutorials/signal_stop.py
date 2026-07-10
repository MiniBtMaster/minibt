# -*- coding: utf-8 -*-
"""signal_backtest 止损/止盈/持仓超时参数 全量测试

覆盖以下参数组合（每个用例独立测试）:
  1. 基准（无止损/无止盈）
  2. sl_stop + stop_mode=0（tick 模式固定止损）
  3. sl_stop + stop_mode=2（百分比模式固定止损）
  4. tp_stop + stop_mode=0（tick 模式固定止盈）
  5. tp_stop + stop_mode=2（百分比模式固定止盈）
  6. sl_trail=1（移动止损）
  7. sl_callback（动态止损回调）
  8. tp_callback（动态止盈回调）
  9. sl_callback_args（止损回调带附加参数）
 10. max_hold_bars（持仓超时强制离场）
 11. 组合：sl_stop + tp_stop（止损止盈并存）
 12. 组合：sl_stop + max_hold_bars（止损+超时共存）
 13. 组合：sl_trail + max_hold_bars（移动止损+超时共存）
 14. sl_stop + stop_mode=1（金额模式止损）
"""
import sys, io, os
import numpy as np

# 修复 Windows GBK 下 Rich 库的 emoji 编码问题
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from minibt import *

_kline = LocalDatas.l2601_60.kline

# ===== 公共 CCI 指标（所有测试共用）=====
class CCI(BtIndicator):
    isplot = dict(long_signal=False, short_signal=False)
    params = dict(CCI_PERIOD=10, CCI_UPPER=100, CCI_LOWER=-100)

    def next(self):
        CCI_PERIOD = self.params.CCI_PERIOD
        CCI_UPPER = self.params.CCI_UPPER
        CCI_LOWER = self.params.CCI_LOWER
        cci = self.close.cci(CCI_PERIOD)
        size = cci.size
        cci_state = np.ones(size)
        for i in range(CCI_PERIOD + 1, size):
            cci_state[i] = cci[i] > CCI_UPPER and 1. or (
                cci[i] < CCI_LOWER and -1. or cci[i - 1])
        cci_state = IndSeries(cci_state)
        long_signal = cci_state.cross_up(0.)
        short_signal = cci_state.cross_down(0.)
        return cci, long_signal, short_signal


_cci = CCI(_kline)
_tick = _kline.price_tick      # 最小波动单位
_mult = _kline.volume_multiple  # 合约乘数


# ====================================================================
# 辅助验证函数
# ====================================================================

def _assert_ok(name, result):
    """确认回测无异常，且返回了权益曲线"""
    assert result is not None, f"[{name}] result is None"
    assert result.profits is not None, f"[{name}] profits is None"
    assert len(result.profits) > 0, f"[{name}] profits empty"
    tp = getattr(result._account, '_total_profit', 0)
    tc = getattr(result._account, '_total_commission', 0)
    eq = result._account.balance
    print(f"  [PASS] {name}  equity={eq:.2f}  total_profit={tp:.2f}  total_fee={tc:.2f}")


def _chk(name, condition):
    """断言并打印"""
    assert condition, f"[{name}] FAILED"
    return True


# ====================================================================
# Test 1: 基准 — 无任何止损止盈
# ====================================================================
def test_1_baseline():
    """纯信号进场/出场，不加止损止盈"""
    print("\n=== Test 1: Baseline (no stop) ===")
    r = _cci.signal_backtest(commission=1.0, com_type=1, isplot=False, isreport=False)
    _assert_ok("1_baseline", r)
    return r


# ====================================================================
# Test 2: sl_stop + stop_mode=0（按 tick 数固定止损）
# ====================================================================
def test_2_sl_stop_tick():
    """设置 3 个 tick 止损"""
    print("\n=== Test 2: sl_stop=3, stop_mode=0 (tick) ===")
    r = _cci.signal_backtest(
        sl_stop=3, stop_mode=0,  # 亏损 3 个 tick 离场
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("2_sl_tick", r)
    # 有止损的权益应 <= 无常止损（或持平）
    return r


# ====================================================================
# Test 3: sl_stop + stop_mode=2（百分比模式止损）
# ====================================================================
def test_3_sl_stop_pct():
    """开仓价反向 1% 止损"""
    print("\n=== Test 3: sl_stop=0.01, stop_mode=2 (percent) ===")
    r = _cci.signal_backtest(
        sl_stop=0.01, stop_mode=2,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("3_sl_pct", r)
    return r


# ====================================================================
# Test 4: tp_stop + stop_mode=0（按 tick 数固定止盈）
# ====================================================================
def test_4_tp_stop_tick():
    """盈利 20 个 tick 止盈"""
    print("\n=== Test 4: tp_stop=20, stop_mode=0 (tick) ===")
    r = _cci.signal_backtest(
        tp_stop=20, stop_mode=0,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("4_tp_tick", r)
    return r


# ====================================================================
# Test 5: tp_stop + stop_mode=2（百分比模式止盈）
# ====================================================================
def test_5_tp_stop_pct():
    """开仓价同向 3% 止盈"""
    print("\n=== Test 5: tp_stop=0.03, stop_mode=2 (percent) ===")
    r = _cci.signal_backtest(
        tp_stop=0.03, stop_mode=2,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("5_tp_pct", r)
    return r


# ====================================================================
# Test 6: sl_trail=1 移动止损
# ====================================================================
def test_6_trailing_stop():
    """启用移动止损：止损线向有利方向跟踪，永不后退"""
    print("\n=== Test 6: sl_trail=1, sl_stop=10, stop_mode=0 ===")
    r = _cci.signal_backtest(
        sl_stop=10, stop_mode=0, sl_trail=1,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("6_trail", r)
    return r


# ====================================================================
# Test 7: sl_callback 动态止损回调
# ====================================================================
def test_7_sl_callback():
    """使用 @stop_callback 装饰器，实现简单动态止损"""
    @stop_callback
    def my_sl(bar_idx, direction, entry, price, ref, cur_dist, tick, mult, size, args_data, args_count):
        # 固定返回 5 个 tick 止损，演示回调基本用法
        return 5.0 * tick

    print("\n=== Test 7: sl_callback (dynamic stop) ===")
    r = _cci.signal_backtest(
        sl_callback=my_sl,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("7_sl_callback", r)
    return r


# ====================================================================
# Test 8: tp_callback 动态止盈回调
# ====================================================================
def test_8_tp_callback():
    """使用 @stop_callback 装饰器，实现简单动态止盈"""
    @stop_callback  # 同签名，用于 tp_callback 传参
    def my_tp(bar_idx, direction, entry, price, ref, cur_dist, tick, mult, size, args_data, args_count):
        # 固定止盈 20 个 tick
        return 20.0 * tick

    print("\n=== Test 8: tp_callback (dynamic take-profit) ===")
    r = _cci.signal_backtest(
        tp_callback=my_tp,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("8_tp_callback", r)
    return r


# ====================================================================
# Test 9: sl_callback_args — 回调带附加参数
# ====================================================================
def test_9_sl_callback_args():
    """回调从 args_data 动态读取每 bar 的止损距离"""
    # 构建一个随 bar 变化的止损数组（前紧后松）
    n = len(_kline)
    dynamic_sl = np.full(n, 3.0)  # 默认 3 tick
    dynamic_sl[n // 2:] = 8.0     # 后半段放宽到 8 tick

    @stop_callback
    def my_sl(bar_idx, direction, entry, price, ref, cur_dist, tick, mult, size, args_data, args_count):
        if args_count > bar_idx:
            return args_data[bar_idx] * tick
        return cur_dist  # 不变

    print("\n=== Test 9: sl_callback_args (dynamic per-bar stop) ===")
    r = _cci.signal_backtest(
        sl_callback=my_sl,
        sl_callback_args=(dynamic_sl,),
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("9_callback_args", r)
    return r


# ====================================================================
# Test 10: max_hold_bars — 持仓超时强制离场
# ====================================================================
def test_10_max_hold_bars():
    """持仓最多 5 根 K 线后强制平仓"""
    print("\n=== Test 10: max_hold_bars=5 ===")
    r = _cci.signal_backtest(
        max_hold_bars=5,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("10_max_hold", r)
    # 极端情况：如果某笔交易没被反向信号出场，则 max_hold_bars 生效
    # 这里仅验证不崩溃
    return r


# ====================================================================
# Test 11: 组合 sl_stop + tp_stop（止损止盈并存）
# ====================================================================
def test_11_sl_and_tp():
    """止损 1% + 止盈 3%，谁先触发谁执行"""
    print("\n=== Test 11: sl_stop=0.01, tp_stop=0.03, stop_mode=2 ===")
    r = _cci.signal_backtest(
        sl_stop=0.01, tp_stop=0.03, stop_mode=2,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("11_sl_tp", r)
    return r


# ====================================================================
# Test 12: 组合 sl_stop + max_hold_bars（止损 + 超时共存）
# ====================================================================
def test_12_sl_plus_max_hold():
    """止损 2% + 持仓最大 10 bar，谁先到谁离场"""
    print("\n=== Test 12: sl_stop=0.02, stop_mode=2, max_hold_bars=10 ===")
    r = _cci.signal_backtest(
        sl_stop=0.02, stop_mode=2,
        max_hold_bars=10,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("12_sl+maxhold", r)
    return r


# ====================================================================
# Test 13: 组合 sl_trail + max_hold_bars（移动止损 + 超时共存）
# ====================================================================
def test_13_trail_plus_max_hold():
    """移动止损 5 tick + 持仓最大 8 bar"""
    print("\n=== Test 13: sl_stop=5, stop_mode=0, sl_trail=1, max_hold_bars=8 ===")
    r = _cci.signal_backtest(
        sl_stop=5, stop_mode=0, sl_trail=1,
        max_hold_bars=8,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("13_trail+maxhold", r)
    return r


# ====================================================================
# Test 14: sl_stop + stop_mode=1（金额模式止损）
# ====================================================================
def test_14_sl_stop_amount():
    """亏损 300 元止损（按金额）"""
    print("\n=== Test 14: sl_stop=300, stop_mode=1 (amount) ===")
    r = _cci.signal_backtest(
        sl_stop=300, stop_mode=1,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("14_sl_amount", r)
    return r


# ====================================================================
# Test 15: 组合 sl_callback + tp_callback（动态止损+动态止盈共存）
# ====================================================================
def test_15_sl_callback_and_tp_callback():
    """同时使用动态止损和动态止盈回调"""
    @stop_callback
    def my_sl(bar_idx, direction, entry, price, ref, cur_dist, tick, mult, size, args_data, args_count):
        return 3.0 * tick

    @stop_callback
    def my_tp(bar_idx, direction, entry, price, ref, cur_dist, tick, mult, size, args_data, args_count):
        return 15.0 * tick

    print("\n=== Test 15: sl_callback + tp_callback ===")
    r = _cci.signal_backtest(
        sl_callback=my_sl,
        tp_callback=my_tp,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("15_both_callbacks", r)
    return r


# ====================================================================
# Test 16: 组合 sl_callback + sl_callback_args + max_hold_bars（全面组合）
# ====================================================================
def test_16_full_combo():
    """动态止损回调(带参数) + 持仓超时，最全面的组合测试"""
    n = len(_kline)
    atr_mult = np.linspace(1.0, 3.0, n)  # 随时间变大

    @stop_callback
    def my_sl(bar_idx, direction, entry, price, ref, cur_dist, tick, mult, size, args_data, args_count):
        # args_data[0] 是 base，args_data[1+bar_idx] 是每个 bar 的乘数
        base = args_data[0] if args_count > 0 else 1.0
        m = args_data[1 + bar_idx] if args_count > 1 + bar_idx else 1.0
        return base * m * tick

    print("\n=== Test 16: sl_callback + sl_callback_args + max_hold_bars ===")
    r = _cci.signal_backtest(
        sl_callback=my_sl,
        sl_callback_args=(3.0, atr_mult),  # base=3, per-bar multipliers
        max_hold_bars=20,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("16_full_combo", r)
    return r


# ====================================================================
# Test 17: 极限值 — max_hold_bars=1（持仓 1 bar 强制离场）
# ====================================================================
def test_17_max_hold_1():
    """极端值：max_hold_bars=1，几乎是入场即离场"""
    print("\n=== Test 17: max_hold_bars=1 (extreme) ===")
    r = _cci.signal_backtest(
        max_hold_bars=1,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("17_maxhold=1", r)
    return r


# ====================================================================
# Test 18: stop_mode=0 较大止损值（类无止盈止损效果）
# ====================================================================
def test_18_large_sl():
    """止损非常大（1000 tick），实际等同于没有止损"""
    print("\n=== Test 18: sl_stop=1000, stop_mode=0 (very large SL) ===")
    r = _cci.signal_backtest(
        sl_stop=1000, stop_mode=0,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("18_large_sl", r)
    return r


# ====================================================================
# Test 19: tp_stop + stop_mode=1（金额模式止盈）
# ====================================================================
def test_19_tp_stop_amount():
    """盈利 500 元止盈（按金额）"""
    print("\n=== Test 19: tp_stop=500, stop_mode=1 (amount) ===")
    r = _cci.signal_backtest(
        tp_stop=500, stop_mode=1,
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("19_tp_amount", r)
    return r


# ====================================================================
# Test 20: 多合约标的 sl_callback_args（标量+数组混传）
# ====================================================================
def test_20_mixed_callback_args():
    """sl_callback_args 同时包含标量和数组，验证展平逻辑"""
    n = len(_kline)
    coef_arr = np.linspace(0.5, 2.0, n)

    @stop_callback
    def my_sl(bar_idx, direction, entry, price, ref, cur_dist, tick, mult, size, args_data, args_count):
        # args_data[0] = base_tick (标量)
        # args_data[1 : 1+n] = coef_arr (数组)
        if args_count < 1 + n + 1:
            return 0.0
        base = args_data[0]
        coef = args_data[1 + bar_idx]
        return base * coef * tick

    print("\n=== Test 20: sl_callback_args (scalar + array) ===")
    r = _cci.signal_backtest(
        sl_callback=my_sl,
        sl_callback_args=(5.0, coef_arr),
        commission=1.0, com_type=1, isplot=False, isreport=False,
    )
    _assert_ok("20_mixed_args", r)
    return r


# ====================================================================
# 主流程
# ====================================================================
if __name__ == "__main__":
    import time

    start = time.time()
    passed = 0
    failed = 0

    tests = [
        test_1_baseline,
        test_2_sl_stop_tick,
        test_3_sl_stop_pct,
        test_4_tp_stop_tick,
        test_5_tp_stop_pct,
        test_6_trailing_stop,
        test_7_sl_callback,
        test_8_tp_callback,
        test_9_sl_callback_args,
        test_10_max_hold_bars,
        test_11_sl_and_tp,
        test_12_sl_plus_max_hold,
        test_13_trail_plus_max_hold,
        test_14_sl_stop_amount,
        test_15_sl_callback_and_tp_callback,
        test_16_full_combo,
        test_17_max_hold_1,
        test_18_large_sl,
        test_19_tp_stop_amount,
        test_20_mixed_callback_args,
    ]

    for fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            failed += 1
            import traceback
            print(f"  [FAIL] {fn.__name__} -> {e}")
            traceback.print_exc()

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"  Total: {len(tests)} | Passed: {passed} | Failed: {failed}")
    print(f"  Time: {elapsed:.2f}s")
    print(f"{'='*60}")

    if failed > 0:
        exit(1)
