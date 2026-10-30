"""实时更新的滚动成交量分布图：数据推进时分布图跟着更新，且仍跟随鼠标。

= `26_volume_profile.py` + 实时：

- 后台线程每 2 秒追加一根 K 线：`chart.update(...)` 推蜡烛，
  `vp_series.update({...})` 把**这一根的分布**推给 VP（`rendererDraw` 读的
  就是每行数据，所以逐点 `update` 即可，不需要整段重发）。
- `vmax` 是**逐行列**：量做大时柱长比例跟着变；同一屏内跨根仍然可比。
- 鼠标跟随照旧 —— `add_vp` 挂的纯 JS 十字线监听（`addCrosshairListener` +
  `series.applyOptions({})` 强制重绘）不依赖 Python，所以主线程在跑事件循环、
  后台线程在推数据，两边互不干扰。

实现细节在同目录 `_volume_profile.py`（`26`/`27` 共用）。

运行：
    python examples/11_api_tour/27_volume_profile_live.py
"""
import os
import sys
import threading

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pylightcharts import Chart                                    # noqa: E402
from _volume_profile import (BINS, WINDOW, add_vp, build_frame,    # noqa: E402
                             make_data, reset_vp_hover, volume_profile)

BAR_SECONDS = 86400          # 日线
VALUE_KEYS = [f'vp{j}' for j in range(BINS)]


def _profile_row(df: pd.DataFrame, window: int = WINDOW):
    """只算**最后一根**的 ``(lo, hi, row)``（与 `volume_profile` 同一规则）。"""
    seg = df.iloc[-window:]
    lo = float(seg['low'].min())
    hi = float(seg['high'].max())
    row = np.zeros(BINS, dtype=float)
    if hi > lo:
        width = (hi - lo) / BINS
        typical = ((seg['high'] + seg['low'] + seg['close']) / 3.0).to_numpy(float)
        idx = np.clip(((typical - lo) / width).astype(int), 0, BINS - 1)
        np.add.at(row, idx, seg['volume'].to_numpy(float))
    return lo, hi, row


def build(chart) -> dict:
    df = make_data(rows=300)
    lo, hi, matrix = volume_profile(df)

    chart.set(df)
    frame = build_frame(chart, df, lo, hi, matrix)
    series = add_vp(chart, frame, 'volume profile',
                    pane_index=None, price_mode=True)
    return {'df': df, 'series': series, 'vmax': float(matrix.max() or 1.0)}


def append_bar(chart, state: dict) -> None:
    """追加一根合成 K 线，并把这一根的成交量分布推给 VP。"""
    df = state['df']
    last = df.iloc[-1]
    rng = np.random.default_rng()
    close = float(last['close']) + float(rng.standard_normal()) * 0.7
    high = max(float(last['close']), close) + abs(float(rng.standard_normal())) * 0.8
    low = min(float(last['close']), close) - abs(float(rng.standard_normal())) * 0.8
    volume = int(rng.integers(1_000, 50_000))
    stamp = pd.Timestamp(last['time']) + pd.Timedelta(seconds=BAR_SECONDS)

    # 蜡烛推进（chart.update 会把 datetime 转成 epoch 秒）
    chart.update(pd.Series({
        'time': stamp, 'open': float(last['close']), 'high': high,
        'low': low, 'close': close, 'volume': volume,
    }))
    bar = {'time': stamp, 'open': float(last['close']), 'high': high,
           'low': low, 'close': close, 'volume': volume}
    state['df'].loc[len(state['df'])] = bar

    # 这一根的分布 -> VP（逐点 update；time 用 epoch 秒，与 candle_data 一致）
    lo, hi, row = _profile_row(state['df'])
    state['vmax'] = max(state['vmax'], float(row.max()))
    point = {'time': int(stamp.value // 10 ** 9), 'lo': lo, 'hi': hi,
             'vmax': state['vmax']}
    point.update({key: float(value) for key, value in zip(VALUE_KEYS, row)})
    state['series'].update(point)
    # ★ 实时更新优先于鼠标跟随：数据一变就把鼠标坐标清掉，本帧先画**最新**一根；
    #   鼠标再动一下才重新跟随（与 `25_live_value_table.py` 的表格一致）。
    reset_vp_hover(chart, state['series'])


def main() -> None:
    chart = Chart(width=1100, height=760,
                  title='pylightcharts - 滚动成交量分布（实时）')
    state = build(chart)

    # 主线程必须跑图表事件循环（show(block=True)），否则十字线事件（鼠标跟随）
    # 永远不会被处理；所以定时推数据放到后台线程里。
    stop = threading.Event()

    def feed() -> None:
        while not stop.wait(2.0):           # 每 2 秒追加一根
            if not chart.is_alive:
                break
            try:
                append_bar(chart, state)
            except Exception as error:      # 窗口提前关掉时队列会报错
                print('[example] append_bar 失败:', error)
                break

    threading.Thread(target=feed, daemon=True).start()
    try:
        chart.show(block=True)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()


if __name__ == '__main__':
    main()
