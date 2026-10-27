"""指标数值表格：**跟随十字光标** + **实时刷新**。

覆盖的 API：

- 十字光标事件 ``chart.events.crosshair_move``（回调签名 ``(chart, time, price)``；
  鼠标在 K 线上时 ``time`` 是**秒**，移到空白处时是 ``''``）；
- 浮动表格 ``chart.create_table(..., draggable=True)`` +
  ``Table.clear / new_row / format``（表格可以按住拖动）；
- 实时：``chart.update`` + ``series.update`` + ``series.subscribe_data_changed``。

效果（就是原码指标左上角那块“数值表格”想要的交互）：

- 鼠标在 K 线上移动 -> 表格显示**鼠标所在时间**的指标值；
- 鼠标移出 K 线到空白处 -> 表格回到**最后一根**的值
  （表格一直显示，不像左上角图例标签那样会消失）；
- 实时追加一根 K 线 -> 指标线更新，表格同步刷新。

.. note::
   “跟随光标”靠的是 JS → Python 的十字光标事件，而这些事件由
   ``chart.show(block=True)`` 里的 asyncio 循环派发。如果在主线程上写
   ``while ...: time.sleep(3); chart.update(...)`` 的循环，主线程一直占着，
   光标事件就**永远不会被处理**（表现：移动鼠标表格不跟随，只有 K 线更新时才刷新）。
   所以下面把“定时追加一根”放到**后台线程**，主线程去跑 ``show(block=True)``。

运行::

    python examples/11_api_tour/25_live_value_table.py
"""
from __future__ import annotations

import threading

import numpy as np
import pandas as pd

from pylightcharts import Chart


def make_data(rows: int = 260) -> pd.DataFrame:
    """自包含合成 OHLCV。"""
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.7)
    open_ = close + rng.standard_normal(rows) * 0.35
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.0, rows)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.0, rows)
    return pd.DataFrame({
        'time': pd.date_range('2024-03-01', periods=rows, freq='D'),
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': rng.integers(1_000, 20_000, rows),
    })


def _ema(values, span: int) -> np.ndarray:
    return pd.Series(values, dtype='float64').ewm(
        span=span, adjust=False).mean().to_numpy()


def _epoch(times) -> list:
    """datetime -> epoch 秒（十字光标给的就是秒）。"""
    return (pd.to_datetime(times).astype('int64') // 10 ** 9).tolist()


class ValueTable:
    """把“某个时间点”上若干序列的值同步到一个可拖动的浮动表格。"""

    HEADINGS = ('Field', 'Value')

    def __init__(self, chart, position: str = 'top-left'):
        self.chart = chart
        self.table = chart.create_table(
            0.26, 0.22, self.HEADINGS,
            widths=(0.55, 0.45), alignments=('left', 'right'),
            position=position, draggable=True)
        self.rows: list = []
        self._times: list = []
        self._index: dict = {}
        self._values: dict = {}

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def set_data(self, rows, times, values) -> None:
        self.rows = list(rows)
        self._times = list(times)
        self._index = {t: i for i, t in enumerate(self._times)}
        self._values = {name: list(series) for name, series in values.items()}
        self.refresh()

    def append(self, time_value: int, values: dict) -> None:
        self._times.append(time_value)
        self._index[time_value] = len(self._times) - 1
        for name, value in values.items():
            self._values.setdefault(name, []).append(value)
        self.refresh()

    # ------------------------------------------------------------------
    # 十字光标
    # ------------------------------------------------------------------
    def on_crosshair(self, chart, time_value, price) -> None:
        index = (self._index.get(time_value)
                 if isinstance(time_value, (int, float)) else None)
        if index is None:
            self.refresh()                       # 移出 K 线 -> 最后一根
        else:
            self._render(index, f'hover {self._times[index]}')

    def refresh(self) -> None:
        """回到最后一根（表格一直显示，不会像图例那样消失）。"""
        if self._times:
            self._render(len(self._times) - 1, 'last')

    def _render(self, index: int, note: str) -> None:
        if not self._times:
            return
        index = max(0, min(index, len(self._times) - 1))
        self.table.clear()
        self.table.new_row(
            'Time', pd.Timestamp(self._times[index], unit='s').strftime(
                '%Y-%m-%d'))
        for name in self.rows:
            series = self._values.get(name) or []
            value = series[index] if 0 <= index < len(series) else None
            self.table.new_row(
                name, '-' if value is None else f'{float(value):.2f}')
        self.table.new_row('Cursor', note)


def build(chart) -> dict:
    """把示例用到的东西全部作用在传入的 chart 上（不打开窗口）。"""
    df = make_data()
    chart.set(df)
    chart.legend(True)
    chart.time_scale(right_offset=4)

    ema_fast = _ema(df['close'], 12)
    ema_slow = _ema(df['close'], 26)

    line_fast = chart.create_line('EMA 12', color='#26A69A', width=2)
    line_fast.set(pd.DataFrame({'time': df['time'], 'EMA 12': ema_fast}))
    line_slow = chart.create_line('EMA 26', color='#EF5350', width=2)
    line_slow.set(pd.DataFrame({'time': df['time'], 'EMA 26': ema_slow}))

    table = ValueTable(chart)
    table.set_data(
        ('EMA 12', 'EMA 26'),
        _epoch(df['time']),
        {'EMA 12': ema_fast, 'EMA 26': ema_slow},
    )
    chart.events.crosshair_move += table.on_crosshair

    # 实时：序列一变就刷新表格（scope = 'update' / 'full'）
    def on_data_changed(series, scope):
        table.refresh()

    line_fast.subscribe_data_changed(on_data_changed)
    line_slow.subscribe_data_changed(on_data_changed)
    return {
        'df': df, 'fast': ema_fast, 'slow': ema_slow,
        'table': table, 'line_fast': line_fast, 'line_slow': line_slow,
    }


def _next_ema(previous: float, value: float, span: int) -> float:
    alpha = 2.0 / (span + 1.0)
    return previous + alpha * (value - previous)


def append_bar(chart, state: dict) -> None:
    """追加一根合成 K 线，更新蜡烛 / 指标线 / 表格（模拟实时）。"""
    df = state['df']
    last = df.iloc[-1]
    rng = np.random.default_rng()
    close = float(last['close']) + float(rng.standard_normal()) * 0.7
    stamp = pd.Timestamp(last['time']) + pd.Timedelta(days=1)

    chart.update(pd.Series({
        'time': stamp, 'open': float(last['close']),
        'high': close + 1.0, 'low': close - 1.0,
        'close': close, 'volume': 1000,
    }))

    fast_next = _next_ema(float(state['fast'][-1]), close, 12)
    slow_next = _next_ema(float(state['slow'][-1]), close, 26)
    state['line_fast'].update(pd.Series({'time': stamp, 'EMA 12': fast_next}))
    state['line_slow'].update(pd.Series({'time': stamp, 'EMA 26': slow_next}))

    state['fast'] = np.append(state['fast'], fast_next)
    state['slow'] = np.append(state['slow'], slow_next)
    state['df'].loc[len(state['df'])] = {
        'time': stamp, 'open': float(last['close']),
        'high': close + 1.0, 'low': close - 1.0,
        'close': close, 'volume': 1000,
    }
    state['table'].append(int(stamp.value // 10 ** 9),
                          {'EMA 12': fast_next, 'EMA 26': slow_next})


def main() -> None:
    chart = Chart(width=1100, height=720,
                  title='pylightcharts - 指标数值表格（十字光标 + 实时）')
    state = build(chart)

    # 关键：**主线程必须去跑图表的事件循环**（show(block=True)），否则
    # JS 发回来的十字光标事件永远不会被处理 —— 表现就是“移动鼠标表格不跟随，
    # 只有 K 线更新时才刷新”。所以把“定时追加一根”放到后台线程里。
    stop = threading.Event()

    def feed() -> None:
        while not stop.wait(3.0):          # 每 3 秒追加一根
            if not chart.is_alive:
                break
            try:
                append_bar(chart, state)
            except Exception as error:      # 窗口提前关掉时队列会报错
                print('[example] append_bar 失败:', error)
                break

    threading.Thread(target=feed, daemon=True).start()
    try:
        chart.show(block=True)             # 主线程跑事件循环：处理光标 + 窗口事件
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()


if __name__ == '__main__':
    main()
