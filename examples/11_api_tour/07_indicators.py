"""全部内置技术指标 + 通用指标入口 + 原始指标函数。

覆盖的 API：
- 指标标签：`chart.legend(True)`（图例默认关闭），每条指标在标签里显示
  色块 / 名称 / 当前值；
- 指标逐点上色：`series.color_by(条件, 颜色, else_color=...)`（SMA 上升段
  绿、下降段红）；主图的蜡烛用 `chart.color_by(...)`；
- 指标快捷方法：`add_sma` / `add_ema` / `add_wma` / `add_bollinger` /
  `add_donchian` / `add_vwap` / `add_rsi` / `add_macd` / `add_stochastic` /
  `add_atr` / `add_obv` / `add_roc` / `add_williams_r` / `add_cci` /
  `add_mfi` / `add_keltner` / `add_adx`。
- 带体填充：`chart.fill_between(upper, lower, ...)`（两条指标线之间的色带）。
- 通用入口：`add_indicator(values, name, ...)` /
  `add_computed_series(compute, name, ...)`。
- 原始函数：`pylightcharts.indicators` 的 `sma` / `ema` / `bollinger` /
  `rsi` / `macd` / `atr`，直接调用后再交给 `add_indicator`。

运行：
    python examples/11_api_tour/07_indicators.py
"""
import numpy as np
import pandas as pd

from pylightcharts import Chart, indicators


def make_data(rows: int = 320) -> pd.DataFrame:
    """自包含的合成 OHLCV，避免依赖外部 csv。"""
    rng = np.random.default_rng(707)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.8)
    open_ = close + rng.standard_normal(rows) * 0.4
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.2, rows)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.2, rows)
    volume = rng.integers(1_000, 50_000, rows)
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    df = make_data()

    # 设置主图 K 线数据；所有 add_* 指标都会基于它自动同步
    chart.set(df)
    # legend(True)：打开图例（默认是关闭的，跟 lightweight-charts-python 一致，
    # 不调用 legend() 就只有图表、没有标签）。lines=True 才会显示每条指标的行：
    # 色块 + 名称 + 十字线所在那根的值，指标名称由 add_* 自动生成（如 'SMA 20'）。
    chart.legend(True)
    # 取内部已格式化的数据（time 为 epoch 秒），供原始指标函数使用
    frame = chart.candle_data

    # ------------------------------------------------------------------
    # 主图叠加类指标（pane_index=None -> 画在 K 线主图）
    # ------------------------------------------------------------------
    # 简单移动平均
    sma = chart.add_sma(source='close', length=20)
    # 指标线也能逐点上色：series.color_by(条件, 颜色, else_color=...)
    # 条件是布尔 Series / 数组 / callable(frame)，这里按"SMA 上升"染色
    rising = sma.data['value'].diff().fillna(0.0) > 0
    sma.color_by(rising, '#26A69A', else_color='#EF5350')
    # 指数移动平均
    chart.add_ema(source='close', length=50)
    # 加权移动平均
    chart.add_wma(source='close', length=30)
    # 布林带：返回 (upper, middle, lower) 三条线
    upper, middle, lower = chart.add_bollinger(
        source='close', length=20, std=2)
    # fill_between：把两条指标线之间的区域填色（布林带/肯特纳通道的"带体"）
    chart.fill_between(upper, lower, color='#2962FF', opacity=0.15)
    # 唐奇安通道：返回 (upper, middle, lower)
    chart.add_donchian(length=20)
    # 成交量加权均价（累计计算，内部标记为 full_only）
    chart.add_vwap()
    # 肯特纳通道：EMA ± multiplier × ATR
    chart.add_keltner(length=20, multiplier=2.0, atr_length=10)

    # ------------------------------------------------------------------
    # 独立面板的振荡类指标（pane_index 指定面板，避免 add_stochastic /
    # add_adx 的多条线各自新建面板）
    # ------------------------------------------------------------------
    # RSI：0..100，并带 70/30 超买超卖参考线
    chart.add_rsi(length=14, pane_index=1)
    # MACD：同一面板内画出 macd / signal / histogram 三条
    chart.add_macd(pane_index=2)
    # 随机指标 %K/%D
    chart.add_stochastic(k=14, d=3, smooth=3, pane_index=3)
    # 平均真实波幅 ATR
    chart.add_atr(length=14, pane_index=4)
    # 能量潮 OBV（需要 volume 列）
    chart.add_obv(pane_index=5)
    # 变动率 ROC（百分比）
    chart.add_roc(source='close', length=12, pane_index=6)
    # 威廉指标 %R（-100..0）
    chart.add_williams_r(length=14, pane_index=7)
    # 顺势指标 CCI
    chart.add_cci(length=20, pane_index=8)
    # 资金流量指标 MFI（需要 volume 列）
    chart.add_mfi(length=14, pane_index=9)
    # 平均趋向指标 ADX：返回 (adx, plus_di, minus_di)
    chart.add_adx(length=14, pane_index=10)

    # ------------------------------------------------------------------
    # 通用入口 add_indicator：传入已算好的时间索引 Series（静态，不重算）
    # ------------------------------------------------------------------
    raw_sma = indicators.sma(frame['close'], 60)
    raw_sma.index = frame['time'].values
    # 把静态计算序列挂到主图
    chart.add_indicator(raw_sma, name='raw SMA 60',
                        color='#FFD54F', line_width=1)

    # ------------------------------------------------------------------
    # 通用入口 add_computed_series：传入 compute(frame) 回调（数据变化时重算）
    # ------------------------------------------------------------------
    # 这里演示「最高价 - 最低价」，叠加在 RSI 面板上
    chart.add_computed_series(
        lambda data: data['high'] - data['low'],
        name='H-L range', kind='Histogram', pane_index=1,
        color='rgba(255, 255, 255, 0.25)')

    # ------------------------------------------------------------------
    # 直接调用 pylightcharts.indicators 的原始函数，再交给 add_indicator
    # ------------------------------------------------------------------
    # 原始 ema()
    raw_ema = indicators.ema(frame['close'], 60)
    raw_ema.index = frame['time'].values
    chart.add_indicator(raw_ema, name='raw EMA 60', color='#4DD0E1')
    # 原始 bollinger()：返回 dict，这里取上轨
    raw_boll_upper = indicators.bollinger(frame['close'], 20, 2)['upper']
    raw_boll_upper.index = frame['time'].values
    chart.add_indicator(raw_boll_upper, name='raw BB upper',
                        color='rgba(41, 98, 255, 0.8)', line_width=1)
    # 原始 rsi()
    raw_rsi = indicators.rsi(frame['close'], 14)
    raw_rsi.index = frame['time'].values
    chart.add_indicator(raw_rsi, name='raw RSI 14',
                        pane_index=1, color='#FF8A65')
    # 原始 macd()：返回 dict，这里取 macd 主线
    raw_macd_line = indicators.macd(frame['close'])['macd']
    raw_macd_line.index = frame['time'].values
    chart.add_indicator(raw_macd_line, name='raw MACD',
                        pane_index=2, color='#BA68C8')
    # 原始 atr()
    raw_atr = indicators.atr(frame, 14)
    raw_atr.index = frame['time'].values
    chart.add_indicator(raw_atr, name='raw ATR 14',
                        pane_index=4, color='#AED581')


def main() -> None:
    chart = Chart(width=1100, height=1050, title='pylightcharts - 全部指标')
    build(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()
