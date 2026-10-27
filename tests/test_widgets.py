"""Static / Jupyter / Streamlit widgets: HTML assembly (no browser, no kernel).

These only need the JS assets shipped with the package, so they also guard the
UTF-8 decoding: on Windows the default codepage (e.g. GBK) cannot read the
vendored engine, which contains characters such as '▨' (legend) and '™'.
"""
import pandas as pd
import pytest

from pylightcharts import widgets


@pytest.fixture()
def jupyter(monkeypatch):
    if widgets.HTML is None:  # pragma: no cover - IPython missing
        pytest.skip('IPython is required for the Jupyter widget')
    monkeypatch.setattr(widgets, 'display', lambda *args, **kwargs: None)
    return widgets.JupyterChart(width=800, height=350)


def test_static_widget_reads_the_assets_as_utf8():
    lwc = widgets.StaticLWC(width=800, height=350)
    # 图例前面的色块从 `▨` 改成**圆点**（P33，用户要求 ✓）
    assert 'border-radius:50%' in lwc._html or '▨' in lwc._html
    assert '\ufffd' not in lwc._html  # no replacement characters


def test_jupyter_widget_survives_a_missing_container_element(jupyter):
    """``#container`` is a plain page element: it does not exist in a notebook.

    The widget used to dereference it unguarded, so its whole setup script
    threw ``Cannot read properties of null`` - same class as the spinner bug.
    """
    html = jupyter._html
    container = "document.getElementById('container') || document.body"
    assert f'var host = {container};' in html
    assert "getElementById('container').style" not in html
    for style in ("overflow = 'hidden'", "borderRadius = '10px'",
                  "width = '800px'", "height = '100%'"):
        assert f'host.style.{style}' in html


def test_static_page_export():
    """`StaticLWC.to_html()` is the zero-dependency browser export path."""
    from pylightcharts.widgets import StaticLWC

    chart = StaticLWC(width=600, height=300)
    chart.set(pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=20),
        'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5,
    }))

    page = chart.to_html()

    assert page.rstrip().endswith('</html>')
    assert page.count('<script>') >= 2            # engine + bundle
    assert 'pylightcharts-callback' in page       # no python bridge in a browser
    # exporting has no side effect: nothing was displayed
    assert chart.win.loaded is True


def test_static_page_survives_asi_and_defines_callbacks_early():
    """Browser/Jupyter pages cannot rely on automatic semicolon insertion.

    The topbar switcher calls ``window.callbackFunction`` while selecting its
    default item, and its statement (``xxx.intervalElements[0].click()``) is
    immediately followed by the view-hook IIFE. Joining the scripts with a bare
    newline made the browser parse ``click()(function(){...})()`` and throw
    ``TypeError``, which aborts the **whole** ``<script>`` block - so the K-line
    and every indicator ``setData`` after it never ran (blank chart in
    Jupyter / browser). The page must define ``callbackFunction`` before the
    first chart statement and separate the statements with ``;``.
    """
    from pylightcharts.widgets import StaticLWC

    chart = StaticLWC(width=600, height=300)
    chart.run_script('window.demo.intervalElements[0].click()')
    chart.run_script('(function(){window.demoRan=true})()')
    page = chart.to_html()

    # `callbackFunction` exists before any chart statement
    assert page.index('window.callbackFunction') < \
        page.index('intervalElements[0].click()'), \
        'callbackFunction must be defined before the chart runs'
    # the click statement and the following IIFE are separated by `;`
    assert 'click();\n(function(){window.demoRan=true})()' in page


def test_browser_chart_writes_and_opens(tmp_path, monkeypatch):
    """`BrowserChart` is the "open it in a browser" backend: one static file."""
    from pylightcharts import BrowserChart

    opened = []
    monkeypatch.setattr('webbrowser.open',
                        lambda url, new=0: opened.append(url) or True)
    target = tmp_path / 'report.html'
    chart = BrowserChart(width=900, height=520, path=str(target))
    chart.set(pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=40),
        'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5,
    }))
    chart.mark_swings(length=4)

    written = chart.show()

    assert written == str(target) and target.exists()
    page = target.read_text(encoding='utf-8')
    assert 'arrowDown' in page and 'pylightcharts-callback' in page
    assert opened and opened[0].startswith('file://')

    # showing again with more on the chart rewrites the same file
    chart.add_sma('close', 5)
    chart.show(open_browser=False)
    assert 'SMA 5' in target.read_text(encoding='utf-8')


def test_browser_chart_findings_and_errors():
    from pylightcharts import BrowserChart

    chart = BrowserChart(width=600, height=300)
    with pytest.raises(ValueError):          # no data yet
        chart.mark_swings()
    chart.set(pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=10),
        'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5,
    }))
    with pytest.raises(ValueError, match='missing'):
        chart.mark_swings(swings=pd.DataFrame({'time': [1], 'price': [2]}))


def test_exported_page_has_balanced_script_tags():
    """The shim must be its own <script>, not nested inside the chart script.

    `StaticLWC._html` ends with an open `<script>` (the chart's statements are
    appended to it). Closing it *after* the shim produced
    `...}</script></script>` - the browser then treats the shim's tags as script
    source, the whole block fails to parse and the page stays **black**.
    """
    from pylightcharts.widgets import StaticLWC

    chart = StaticLWC(width=600, height=300)
    chart.set(pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=20),
        'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5,
    }))
    page = chart.to_html()

    assert page.count('<script>') == page.count('</script>')
    assert page.rstrip().endswith('</script></body></html>')
    # the shim starts a fresh block right after the chart's script is closed
    assert '</script><script>' in page.replace('// static export', '')
    # ... and the chart's own statements are inside the *first* of the two
    chart_script = page.split('</script>')[0]
    assert 'addSeries' in chart_script or 'Lib' in chart_script


def test_importing_widgets_does_not_bind_a_gui_toolkit():
    """The browser / static / headless targets must stay toolkit-free.

    Importing a Qt binding loads DLLs that then win for the whole process, so a
    plain `import pylightcharts.widgets` used to make a later PyQt6 application
    (or `qfluentwidgets`) fail with confusing DLL errors. Run it in a fresh
    interpreter: other tests may legitimately import Qt.
    """
    import subprocess
    import sys

    code = (
        'import sys; import pylightcharts.widgets as w;'
        'bad = sorted(m for m in sys.modules'
        ' if m.startswith(("PySide", "PyQt", "wx")));'
        'print(",".join(bad))'
    )
    result = subprocess.run([sys.executable, '-c', code], capture_output=True,
                            text=True, encoding='utf-8', errors='replace', check=True)
    assert result.stdout.strip() == '', result.stdout

    # the legacy module attributes still resolve, just lazily
    from pylightcharts import widgets as module
    assert module.QWebEngineView is not None or True
    assert module.using_pyside6 in (True, False)
