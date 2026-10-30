"""Headless rendering tests. These need a Chromium-family browser, so they are
skipped when none is found."""
import os

import numpy as np
import pandas as pd
import pytest

from pylightcharts import shapes
from pylightcharts.headless import HeadlessChart, find_browser


def _has_renderer() -> bool:
    if find_browser() is not None:
        return True
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _has_renderer(),
    reason='no renderer (install playwright or set PYLIGHTCHARTS_CHROME)',
)


def _data(rows=200):
    rng = np.random.default_rng(5)
    close = 100 + np.cumsum(rng.standard_normal(rows))
    return pd.DataFrame({
        'time': pd.date_range('2023-01-01', periods=rows, freq='D'),
        'open': close, 'high': close + 1, 'low': close - 1, 'close': close,
        'volume': rng.integers(1, 1000, rows),
    })


def test_to_html_is_self_contained():
    chart = HeadlessChart(width=800, height=500)
    chart.set(_data())
    html = chart.to_html()
    assert 'LightweightCharts' in html
    assert 'new Lib.Handler' in html
    assert 'setData' in html


def test_pane_count_is_tracked_without_a_webview():
    chart = HeadlessChart()
    chart.set(_data())
    chart.add_rsi(14)
    chart.add_macd()
    assert chart.pane_count() == 3


def test_render_produces_a_non_blank_chart(tmp_path):
    chart = HeadlessChart(width=900, height=600)
    chart.set(_data())
    chart.add_sma('close', 20)
    chart.add_bollinger('close', 20, 2)
    chart.add_rsi(14)

    out = tmp_path / 'chart.png'
    png = chart.render(str(out))

    assert png[:8] == b'\x89PNG\r\n\x1a\n'
    assert out.exists() and out.stat().st_size > 5000

    image_module = pytest.importorskip('PIL.Image')
    image = image_module.open(out).convert('RGB')
    pixels = np.asarray(image)
    non_black = (pixels.sum(axis=2) > 30).mean()
    assert non_black > 0.03, f'chart looks blank (non-black ratio {non_black:.3f})'


def test_render_custom_series(tmp_path):
    chart = HeadlessChart(width=900, height=600)
    df = _data()
    chart.set(df)
    series = chart.add_custom_series('ranges')
    series.set(df, shapes=lambda row: shapes.range_bar(row['low'], row['high'],
                                                       color='rgba(255, 0, 0, 0.9)'))

    out = tmp_path / 'custom.png'
    chart.render(str(out))

    image_module = pytest.importorskip('PIL.Image')
    pixels = np.asarray(image_module.open(out).convert('RGB'))
    reddish = ((pixels[:, :, 0].astype(int) - pixels[:, :, 1]) > 60).sum()
    assert reddish > 200, f'custom shapes did not render (reddish px {reddish})'


# --------------------------------------------------------------------------
# static HTML export (no server, no npm, no extra dependency)
# --------------------------------------------------------------------------

def test_to_html_is_one_self_contained_page():
    chart = HeadlessChart(width=900, height=600)
    chart.set(_data())
    chart.add_sma('close', 20)

    page = chart.to_html(title='my chart')

    assert page.startswith('<!DOCTYPE html>') and page.rstrip().endswith('</html>')
    assert '<title>my chart</title>' in page
    # engine + bundle + styles are inlined, nothing is fetched from disk
    assert 'LightweightCharts' in page or 'lightweight-charts' in page.lower()
    assert 'Lib.Handler' in page or 'Lib.invoke' in page
    assert '<link rel="stylesheet"' not in page
    assert ' src=' not in page
    # the chart's own scripts are there too
    assert 'addSeries' in page
    # widget callbacks become a DOM event instead of throwing
    assert 'pylightcharts-callback' in page


def test_save_html_writes_the_page(tmp_path):
    chart = HeadlessChart(width=600, height=400)
    chart.set(_data(80))

    out = tmp_path / 'nested' / 'chart.html'
    written = chart.save_html(str(out))

    assert written == str(out) and out.exists()
    assert out.read_text(encoding='utf-8') == chart.to_html()


def test_open_in_browser_saves_and_opens(tmp_path, monkeypatch):
    chart = HeadlessChart(width=600, height=400)
    chart.set(_data(80))
    opened = []
    monkeypatch.setattr('webbrowser.open',
                        lambda url, new=0: opened.append((url, new)) or True)

    path = chart.open_in_browser(str(tmp_path / 'chart.html'))

    assert opened and opened[0][0].startswith('file://')
    assert str(tmp_path / 'chart.html') in opened[0][0].replace('/', os.sep) \
        or 'chart.html' in opened[0][0]
    assert (tmp_path / 'chart.html').exists()
    assert path
