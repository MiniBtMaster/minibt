"""9.3 · KLine —— K 线对象（行情 / 持仓 / 下单 / 成本 / 周期转换）

演示要点
--------
`KLine` 是策略里最常用的数据对象：OHLCV + **所有指标** + 持仓/订单 +
成本参数 + 周期转换。

本页只演示**只读查询**（不下单）；下单接口见 10.x。

运行：``python tutorials/data/03_kline.py``
文档：``minibt_docs/docs/minibt_data/9.3_kline.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① 行情字段
    print('① 合约:', kline.symbol, '| 周期(秒):', kline.cycle,
          '| 根数:', len(kline))
    print('   时间:', kline.datetime.iloc[0], '→', kline.datetime.iloc[-1])
    print('   OHLCV 列:', list(kline.pandas_object.columns))
    print('   当前 bar:', kline.current_datetime, kline.current_close)

    # ② 持仓 / 账户（不跑回测时是空的）
    print('② position =', kline.position, '| cost_price =', kline.cost_price,
          '| float_profit =', kline.float_profit)

    # ③ 成本 / 合约参数
    print('③ price_tick =', kline.price_tick,
          '| volume_multiple =', kline.volume_multiple,
          '| margin_rate =', kline.margin_rate)
    print('   tick_commission =', kline.tick_commission,
          '| percent_commission =', kline.percent_commission,
          '| fixed_commission =', kline.fixed_commission)

    # ④ 止损线（回测里由 buy/sell 的 stop 生成）
    print('④ stop =', type(kline.stop).__name__,
          '| stop_lines =', type(kline.stop_lines).__name__)
    kline.set_stop_lines_style(
        stop=LineStyle(line_color=Colors.red, line_dash=LineDash.dashed))
    print('   set_stop_lines_style(stop=...) 后 stop_lines.line_style =',
          kline.stop_lines.line_style)

    # ⑤ 交易时段过滤（需要 tq 行情对象 —— 策略/实盘里才有）
    try:
        flt = kline.exclude_time('09:00', '10:00')
        print('⑤ exclude_time ->', type(flt).__name__)
        print('   can_trade(now) =', kline.can_trade())
    except Exception as error:                      # noqa: BLE001
        print('⑤ 交易时段接口需要 tq 行情对象（策略里才有）：',
              type(error).__name__, error)

    # ⑥ 特殊 K 线
    #    `Heikin_Ashi_Candles` / `Linear_Regression_Candles` 是**布尔标记**
    #    （这条 K 线是不是 HA / 线性回归），不是数据
    print('⑥ Heikin_Ashi_Candles ->', kline.Heikin_Ashi_Candles,
          '| Linear_Regression_Candles ->', kline.Linear_Regression_Candles)
    ha = kline.ha()                                  # ← 真正拿 HA 数据
    print('   kline.ha() ->', type(ha).__name__,
          '| 列:', list(ha.pandas_object.columns))

    # ⑦ 周期转换（resample）：目标周期必须是**主周期的整数倍**
    #    （test 是 300 秒 → 900 = 15 分钟）
    r = kline.resample(900, data_length=300)
    print('⑦ resample(900) ->', type(r).__name__, '| len:', len(r),
          '| cycle:', r.cycle)

    # ⑧ 蜡烛配色（写 plotinfo）
    kline.bull_color = '#2196f3'
    kline.bear_color = '#ff9800'
    print('⑧ candle_style =', kline.candle_style)


if __name__ == '__main__':
    main()
