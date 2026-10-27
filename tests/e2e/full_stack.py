"""Full-stack end-to-end test: real pywebview window -> real v5 renderer.

Run it on a desktop session (it opens a window and closes itself):

    python tests/e2e/full_stack.py

It exercises the Phase 1 generic bridge from actual Python code:
`create_area` / `add_series` go through `Lib.invoke(..., "addSeries", ...)`.
"""
import math
import os
import sys
import threading
import time

import pandas as pd

from pylightcharts import Chart

TIMEOUT = 60


def _watchdog():
    time.sleep(TIMEOUT)
    print(f'WATCHDOG: no result after {TIMEOUT}s, exiting', flush=True)
    os._exit(2)


PIXEL_PROBE = """
(function () {
    const canvases = Array.from(document.querySelectorAll('canvas'));
    let drawn = 0, total = 0;
    for (const c of canvases) {
        const ctx = c.getContext('2d');
        if (!ctx || !c.width || !c.height) continue;
        const d = ctx.getImageData(0, 0, c.width, c.height).data;
        for (let i = 0; i < d.length; i += 4) {
            total++;
            if (d[i] > 20 || d[i + 1] > 20 || d[i + 2] > 20) drawn++;
        }
    }
    return [canvases.length, drawn, total];
})()
"""


def make_data(n=120):
    rows = []
    for i in range(n):
        o = 100 + math.sin(i / 5) * 10
        rows.append({
            'time': pd.Timestamp('2024-01-01') + pd.Timedelta(days=i),
            'open': o, 'high': o + 3, 'low': o - 3, 'close': o + (1 if i % 2 else -1),
        })
    return pd.DataFrame(rows)


def main():
    threading.Thread(target=_watchdog, daemon=True).start()

    chart = Chart(width=900, height=600, title='pylightcharts full-stack test')
    df = make_data()

    chart.set(df)

    # Phase 1: series created purely through the generic bridge
    area = chart.create_area(name='close', line_color='#00e676', top_color='rgba(0,230,118,0.3)')
    area.set(df)
    baseline = chart.add_series('Baseline', name='close', base_value=100.0)
    baseline.set(df)

    # Phase 3: indicators (pure pandas) - overlays on price, oscillators in new panes
    chart.add_sma('close', 20)
    chart.add_bollinger('close', 20, 2)
    rsi_series = chart.add_rsi(14)          # pane 1
    chart.add_macd()           # pane 2

    # Phase 3: drawing tools (Fibonacci / measure / parallel channel)
    chart.fibonacci(df['time'].iloc[20], float(df['close'].iloc[20]),
                    df['time'].iloc[90], float(df['close'].iloc[90]))
    chart.measure(df['time'].iloc[20], float(df['close'].iloc[20]),
                  df['time'].iloc[60], float(df['close'].iloc[60]))
    chart.parallel_channel(df['time'].iloc[20], float(df['close'].iloc[20]),
                           df['time'].iloc[90], float(df['close'].iloc[90]), offset=4.0)

    chart.show(block=False)
    time.sleep(4)  # let the webview load + first render

    # Phase 2: native panes, created live (needs a webview round-trip)
    live_pane = chart.add_pane()
    pane_line = chart.add_series('Line', 'close', pane_index=live_pane, color='#00ffff')
    pane_line.set(df)
    chart.set_pane_stretch(live_pane, 1.5)
    chart.get_price_scale('right').set_mode('normal')
    time.sleep(1)

    canvases, drawn, total = chart.win.run_script_and_get(PIXEL_PROBE)
    print(f'canvases={canvases} nonBlackPx={drawn}/{total}')

    pane_count = chart.pane_count()
    counts = [
        chart.win.run_script_and_get(f'{chart.id}.chart.panes()[{i}].getSeries().length')
        for i in range(pane_count)
    ]
    print(f'panes={pane_count} series_per_pane={counts}')

    assert canvases >= 1, 'no canvas rendered'
    assert drawn > 1000, 'chart canvas looks empty'
    assert pane_count >= 4, f'expected >=4 panes, got {pane_count}'
    assert counts[0] >= 5, f'price pane should hold overlays, got {counts[0]}'
    assert counts[1] >= 1, 'RSI pane should contain its series'
    assert counts[2] >= 3, 'MACD pane should contain macd/signal/histogram'
    assert counts[live_pane] >= 1, 'live pane should contain the pane line'

    # ---- API coverage checks against the live chart ----
    print('version        :', chart.version())
    print('auto_size      :', chart.auto_size_active())
    print('series_type    :', chart.series_type())
    print('data_by_index  :', chart.data_by_index(10))
    print('last_value     :', chart.last_value_data())
    print('price<->coord  :', chart.price_to_coordinate(100.0), chart.coordinate_to_price(100))
    print('area pane_index:', area.get_pane_index())
    print('series_order   :', area.series_order())
    print('time_scale w/h :', chart.time_scale_width(), chart.time_scale_height())
    print('visible_range  :', chart.get_visible_range())
    print('logical->coord :', chart.logical_to_coordinate(10))
    print('pane h/stretch :', chart.pane_height(0), chart.pane_stretch_factor(0))
    print('pane_size      :', chart.pane_size())

    assert chart.series_type() == 'Candlestick'
    assert chart.price_to_coordinate(100.0) is not None
    assert isinstance(chart.data_by_index(10), dict)

    # price lines
    price_line = chart.create_price_line(105.0, color='#00e676', title='entry')
    time.sleep(0.3)
    assert len(chart.price_lines()) == 1
    print('price_line opts:', price_line.options())
    price_line.remove()
    assert chart.price_lines() == []

    # crosshair control
    chart.set_crosshair_position(100.0, df['time'].iloc[50])
    time.sleep(0.2)
    chart.clear_crosshair_position()

    # time scale control
    chart.scroll_to_real_time()
    chart.set_visible_logical_range(0, 60)
    chart.reset_time_scale()

    # indicator auto-refresh on a live bar update
    rsi_before = chart.win.eval_js(f'{rsi_series.id}.series.data().length')
    next_time = df['time'].iloc[-1] + pd.Timedelta(days=1)
    chart.update(pd.Series({'time': next_time, 'open': 100.0, 'high': 101.0,
                            'low': 99.0, 'close': 100.5, 'volume': 100}))
    time.sleep(0.4)
    rsi_after = chart.win.eval_js(f'{rsi_series.id}.series.data().length')
    print(f'indicator update: RSI {rsi_before} -> {rsi_after}')
    assert rsi_after == rsi_before + 1, 'RSI did not follow the chart update'

    # events subscribe / unsubscribe
    chart.events.crosshair_move += lambda c, t, p: None
    chart.events.dblclick += lambda c, t, p: None
    chart.events.crosshair_move.unsubscribe()
    chart.events.dblclick.unsubscribe()
    print('events         : ok')

    # JS errors must surface as BridgeError (not silently return None)
    from pylightcharts.util import BridgeError
    try:
        chart.win.invoke_get(f'{chart.id}.chart', 'noSuchMethod')
        raise AssertionError('expected a BridgeError')
    except BridgeError as error:
        print('bridge error   :', str(error).splitlines()[0][:90])

    print('FULL_STACK_OK')
    chart.exit()
    os._exit(0)


if __name__ == '__main__':
    main()
