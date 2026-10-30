"""The browser examples (`examples/12_browser/`): static page and live server.

Both build the same chart - one indicator on the main pane (SMA 20) and one on
a
sub-pane (RSI 14) - and differ only in how the page is published.
"""
import importlib.util
import json
import pathlib
import re
import subprocess
import threading
import time
import urllib.request

import numpy as np
import pandas as pd
import pytest

from pylightcharts.headless import find_browser

ROOT = pathlib.Path(__file__).resolve().parents[1]
BROWSER = ROOT / 'examples' / '12_browser'


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f'ex12_{name}',
                                                  BROWSER / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _chart(**kwargs):
    from pylightcharts import BrowserChart
    return BrowserChart(**kwargs)


# --------------------------------------------------------------------------
# shared chart shape
# --------------------------------------------------------------------------

@pytest.mark.parametrize('name', ['static', 'live'])
def test_browser_examples_have_a_main_and_a_sub_pane_indicator(name):
    module = _load(name)
    chart = _chart(width=1000, height=620)
    try:
        module.build(chart)
        js = chart.to_scripts() if hasattr(chart, 'to_scripts') else chart._html

        # main pane: an SMA overlay
        assert "'SMA 20'" in js or '"SMA 20"' in js
        # sub pane: RSI, created in a new pane
        assert "'RSI 14'" in js or '"RSI 14"' in js
        assert chart.pane_count() == 2
        # the candle data and the volume are there too
        assert 'setData' in js
    finally:
        chart.stop()


# --------------------------------------------------------------------------
# static
# --------------------------------------------------------------------------

def test_live_example_next_bar_moves_the_time_forward():
    """The bars must land *after* the history - in epoch seconds.

    `chart.candle_data['time']` already holds epoch seconds (the format the
    engine gets), so wrapping it in `pd.Timestamp(...)` treats the number as
    nanoseconds and every streamed bar lands in 1970: the chart looks frozen.
    """
    module = _load('live')
    chart = _chart(width=1000, height=620)
    try:
        module.build(chart)
        last = chart.candle_data.iloc[-1]
        assert int(last['time']) > 1_600_000_000      # a real epoch, not 1970

        bar = module.next_bar(last, 0)
        assert int(bar['time']) == int(last['time']) + 60
        assert bar['low'] <= bar['close'] <= bar['high']

        following = module.next_bar(bar, 1)
        assert int(following['time']) == int(bar['time']) + 60
    finally:
        chart.stop()


def test_static_example_writes_one_self_contained_page(tmp_path):
    module = _load('static')
    out = tmp_path / 'report.html'
    chart = _chart(width=1000, height=620, path=str(out))
    try:
        module.build(chart)
        written = chart.save_html(str(out))
    finally:
        chart.stop()

    page = pathlib.Path(written).read_text(encoding='utf-8')
    assert page.startswith('<!DOCTYPE html>') and page.rstrip().endswith('</html>')
    assert ' src=' not in page and '<link rel="stylesheet"' not in page
    assert page.count('<script>') == page.count('</script>')
    assert 'Lib.Handler' in page or 'Lib.invoke' in page
    # no server was started by the static example
    assert chart.url == '' and chart.clients == 0


@pytest.mark.skipif(find_browser() is None, reason='no browser to render with')
def test_static_example_page_renders(tmp_path):
    """Pixel check: the exported page must not be blank (or black)."""
    import numpy as np
    from PIL import Image

    module = _load('static')
    out = tmp_path / 'report.png'
    chart = _chart(width=900, height=520, path=str(tmp_path / 'r.html'))
    try:
        module.build(chart)
        page = chart.save_html(str(tmp_path / 'r.html'))
    finally:
        chart.stop()
    subprocess.run(
        [find_browser(), '--headless=new', '--disable-gpu', '--no-sandbox',
         '--allow-file-access-from-files', '--window-size=900,520',
         f'--screenshot={out}', str(BROWSER / 'browser_static.html')
         if False else pathlib.Path(page).as_uri()],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=90)
    image = np.asarray(Image.open(out).convert('RGB')).astype(int)
    non_black = int((image.sum(axis=2) > 30).sum())
    assert non_black > image.shape[0] * image.shape[1] * 0.05, non_black


# --------------------------------------------------------------------------
# live
# --------------------------------------------------------------------------

def test_live_example_streams_an_update_with_the_indicators():
    module = _load('live')
    chart = _chart(width=1000, height=620, live=True)
    frames = []

    def read_stream(url):
        request = urllib.request.Request(url + 'events')
        with urllib.request.urlopen(request, timeout=10) as response:
            while True:
                line = response.readline().decode('utf-8', 'replace').strip()
                if line.startswith('data: '):
                    frames.append(json.loads(line[6:])['script'])

    try:
        module.build(chart)
        url = chart.show(block=False, open_browser=False)
        threading.Thread(target=read_stream, args=(url,), daemon=True).start()
        deadline = time.time() + 5
        while chart.clients == 0 and time.time() < deadline:
            time.sleep(0.05)
        assert chart.clients == 1

        last = chart.candle_data.iloc[-1]
        bar = module.next_bar(last, 0)
        chart.update(bar)

        deadline = time.time() + 8
        joined = ''
        while time.time() < deadline:
            joined = '\n'.join(frames)
            if '.series.update(' in joined:
                break
            time.sleep(0.05)
        assert '.series.update(' in joined            # candles streamed
        # ... and with the *right* time (a 1970 bar means the chart never moves)
        candle_update = next(script for script in frames
                            if '.series.update(' in script)
        assert f'"time":{int(bar["time"])}' in candle_update.replace(' ', '')
        # the sub-pane indicator is streamed too (its series id appears)
        rsi = next(line for line in chart.lines() if line.name == 'RSI 14')
        assert rsi.id in joined
        sma = next(line for line in chart.lines() if line.name == 'SMA 20')
        assert sma.id in joined
    finally:
        chart.stop()
    assert chart.clients == 0
