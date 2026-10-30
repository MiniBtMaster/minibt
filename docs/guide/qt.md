# Qt integration

`QtChart` embeds the chart in a `QWebEngineView` and drives it over `QWebChannel`.
That is the backend to use when the chart has to live inside a real desktop
application: it is an ordinary widget you can put in any layout, with drawing
tools, events and panes all working.

```python
from PyQt6.QtWidgets import QApplication
from pylightcharts.qt import prepare_qt          # <- before QApplication

prepare_qt('PyQt6')
app = QApplication([])

from pylightcharts.widgets import QtChart
chart = QtChart(toolbox=True)
chart.set(df)
chart.add_sma('close', 20)
chart.get_webview().resize(1200, 700)
chart.get_webview().show()
app.exec()
```

Those first two imports are not decoration - skip them and Qt raises at the
first chart. The two sections below explain why.

## Pick the binding before anything touches Qt

`pylightcharts` uses one Qt binding per process; **the first one loaded wins**,
because Qt cannot mix PyQt6 and PySide6 in a single interpreter (loading both
ends in `ImportError: DLL load failed while importing QtSvg`). The binding is
chosen in this order:

1. `$PYLIGHTCHARTS_QT` (`PyQt6` / `PySide6` / `PyQt5`), if set
2. whichever binding the application has **already imported**
3. otherwise a probe, in the historical order `PyQt5` → `PySide6` → `PyQt6`

Rule 3 is the trap: a PyQt6 application that happens to have PySide6 installed
too gets PySide6. So say what you want, up front:

```python
from pylightcharts.qt import prepare_qt

prepare_qt('PyQt6')      # sets $PYLIGHTCHARTS_QT and imports the backend
```

`prepare_qt()` returns the `QWebEngineView` class, sets `$PYLIGHTCHARTS_QT` and
imports `pylightcharts.widgets`. An application that has **already** imported its
binding is covered by rule 2 - that is enough - but `prepare_qt()` is still the
clearest way to say it.

## QtWebEngineWidgets comes first, always

`QtWebEngineWidgets` must be imported **before** a `QCoreApplication` exists.
Import it afterwards and Qt refuses:

```
ImportError: QtWebEngineWidgets must be imported or Qt.AA_ShareOpenGLContexts
must be set before a QCoreApplication instance is created
```

`pylightcharts.widgets` imports it as soon as the module loads, so the order is:

```python
prepare_qt('PyQt6')      # 1. binding + QtWebEngineWidgets
app = QApplication([])   # 2. only now
import pylightcharts.widgets
```

The same applies when the chart lives in a bigger application: do this before the
host application builds its `QApplication`, not when the first chart window opens.

!!! tip "Coming from lightweight-charts-python"
    That package forced a binding by *replacing module globals* after the fact
    (`lightweight_charts.using_pyside6 = False`, then
    `lightweight_charts.widgets.QWebEngineView = <PyQt6 class>`). None of that is
    needed here - see [Migrating](migration.md).

## The widget

```python
QtChart(widget=None, inner_width=1.0, inner_height=1.0,
        scale_candles_only=False, toolbox=False)
```

| | |
|---|---|
| `widget` | optional parent widget |
| `inner_width` / `inner_height` | fractions of the parent, so `1.0, 1.0` fills it |
| `scale_candles_only` | scale the price axis on candles only (indicators may stick out) |
| `toolbox` | show the drawing-tool toolbar |
| `get_webview()` | the `QWebEngineView`, i.e. what you add to a layout |
| `sync(other, crosshairs_only=False)` | tie two charts' time axes together |

```python
splitter = QSplitter()
splitter.addWidget(price_chart.get_webview())
splitter.addWidget(volume_chart.get_webview())

price_chart.sync(volume_chart)                    # same time axis, linked crosshair
price_chart.sync(volume_chart, crosshairs_only=True)
```

Charts are otherwise regular `AbstractChart`s: `set()`, `update()`,
`add_sma()`/`add_rsi()`/…, drawing tools, `chart.events`, panes. See
[Charts and data](charts.md) and [Events](events.md).

## Screenshots and shutdown

```python
chart.get_webview().page().runJavaScript(
    f'{chart.id}.chart.takeScreenshot().toDataURL()', save_png)
```

`runJavaScript` is asynchronous: the callback runs later, on the Qt event loop.
Close the window normally (`close()` / `app.quit()`); Qt tears the web views down
at process exit, so let the event loop unwind instead of exiting from inside a Qt
callback.

## Chromium is chatty

QtWebEngine's Chromium runs its own network machinery (component updates, domain
reliability, Safe Browsing) as soon as the first page loads. On a blocked or
offline network that lands in *your* startup output:

```
handshake failed; returned -1, SSL error code 1, net_error -101
```

Those requests have nothing to do with the chart - the page `pylightcharts` loads
is local and pulls no external resource - so switch them off before the
`QApplication` exists:

```python
import os

os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = ' '.join([
    '--disable-background-networking',
    '--disable-component-update',
    '--disable-domain-reliability',
    '--disable-client-side-phishing-detection',
    '--disable-breakpad',
    '--disable-sync',
    '--no-pings',
    '--no-first-run',
])
```

Add `--log-level=3` to silence Chromium's own logging entirely. It also hides the
harmless GPU warnings (`shared_image`, `gl_surface_egl`) that show up on some
drivers and in offscreen/CI sessions.

## Complete example

`examples/10_qt_migration/qt_migration.py` builds a PyQt6 window with candles,
indicator lines, a watermark, a trend line and markers, then screenshots itself.
