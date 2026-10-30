"""End-to-end benchmark: JSON source transfer vs binary buffer transfer.

Run on a desktop session (opens a window):

    python tests/e2e/benchmark.py [rows]

It measures how long `chart.set(df)` takes until the webview has applied the
data, for both encodings.
"""
import os
import sys
import threading
import time

import numpy as np
import pandas as pd

from pylightcharts import Chart
from pylightcharts import util as putil


def make_data(rows):
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.standard_normal(rows))
    return pd.DataFrame({
        'time': pd.date_range('2015-01-01', periods=rows, freq='min'),
        'open': close, 'high': close + 1, 'low': close - 1, 'close': close,
        'volume': rng.integers(1, 1000, rows),
    })


def main():
    rows = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000

    def watchdog():
        time.sleep(180)
        print('WATCHDOG', flush=True)
        os._exit(2)
    threading.Thread(target=watchdog, daemon=True).start()

    df = make_data(rows)
    chart = Chart(width=900, height=600, title='pylightcharts benchmark')
    chart.show(block=False)
    time.sleep(4)

    results = {}
    for label, threshold in (('json', 10 ** 9), ('binary', 0)):
        putil.BINARY_DATA_THRESHOLD = threshold
        chart.set(df.head(500))          # warm up / reset
        chart.win.eval_js('1+1')
        start = time.perf_counter()
        chart.set(df)
        chart.win.eval_js('1+1')         # queued after setData -> waits for it
        elapsed = time.perf_counter() - start
        results[label] = elapsed
        print(f'{label:>6}: {elapsed:.3f}s', flush=True)

    speedup = results['json'] / results['binary'] if results['binary'] else float('inf')
    print(f'rows={rows} binary is {speedup:.1f}x faster than json')

    chart.exit()
    os._exit(0)


if __name__ == '__main__':
    main()
