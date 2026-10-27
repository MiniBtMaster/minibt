# Migrating from lightweight-charts-python

`pylightcharts` keeps every class, method and module-level name of
[lightweight-charts-python](https://github.com/louisnw01/lightweight-charts-python),
so code written against it runs unchanged. There are two ways to switch, and they
can be mixed.

## Option 1: the alias shim (no edits at all)

```python
from pylightcharts.compat import install_alias

install_alias()                     # before any `import lightweight_charts`

import lightweight_charts           # -> pylightcharts
from lightweight_charts.util import Events
from lightweight_charts.widgets import QtChart
```

`install_alias()` installs a meta-path finder that maps the `lightweight_charts`
package **and every submodule** onto `pylightcharts`, so
`sys.modules['lightweight_charts'] is sys.modules['pylightcharts']` and
submodule imports resolve to the same module objects. Two properties make it safe
to drop into code whose imports you do not control:

- it imports nothing itself (no Qt binding, no pywebview) - you can call it as the
  first line of an entry point;
- it wins over a real `lightweight-charts-python` installation, so it does not
  matter which of the two happens to be installed.

`remove_alias()` undoes it.

## Option 2: change the imports

| lightweight-charts-python | pylightcharts |
|---|---|
| `from lightweight_charts import Chart` | `from pylightcharts import Chart` |
| `from lightweight_charts.abstract import AbstractChart, Line, Candlestick` | `from pylightcharts.abstract import ...` |
| `from lightweight_charts.drawings import HorizontalLine` | `from pylightcharts.drawings import HorizontalLine` |
| `from lightweight_charts.toolbox import ToolBox, json` | `from pylightcharts.toolbox import ToolBox, json` |
| `from lightweight_charts.util import Events, JSEmitter` | `from pylightcharts.util import Events, JSEmitter` |
| `from lightweight_charts.widgets import QtChart` | `from pylightcharts.widgets import QtChart` |
| `from lightweight_charts import topbar, table` | `from pylightcharts import topbar, table` |

The chart API itself is unchanged: `set()`, `update()`, `update_from_tick()`,
`create_line()`, `horizontal_line()`, `marker()`, `legend()`, drawing tools,
`chart.events`, and so on.

## The one behavioural difference: choosing the Qt backend

Everything above is a rename. The Qt backend is where the two packages differ,
because lightweight-charts-python **forces** a binding by replacing module globals
after import:

```python
import lightweight_charts
lightweight_charts.using_pyside6 = False
import lightweight_charts.widgets
lightweight_charts.widgets.QWebEngineView = QWebEngineView     # PyQt6 classes
lightweight_charts.widgets.QWebChannel = QWebChannel
lightweight_charts.widgets.QObject = QObject
lightweight_charts.widgets.Slot = pyqtSlot
lightweight_charts.widgets.QUrl = QUrl
lightweight_charts.widgets.QTimer = QTimer
lightweight_charts.widgets.Qt = Qt
lightweight_charts.widgets.Bridge = Bridge
```

`pylightcharts` chooses its binding **up front** instead, and that has to happen
before `QApplication`:

```python
from pylightcharts.qt import prepare_qt

prepare_qt('PyQt6')
```

The patching still *works* if you keep it - the globals are still read at call
time, and a test asserts that - but it is no longer necessary. What is necessary
is the ordering: see [Qt integration](qt.md) for the
`QtWebEngineWidgets`-before-`QApplication` rule and the exact `ImportError` you
get otherwise. Applications that imported `lightweight_charts` as their very first
step and patched the globals were, in effect, doing this dance by hand.

## What is guaranteed

`tests/test_lwc_compat.py` keeps the promise honest. It walks the `lightweight_charts`
imports of the downstream projects, rewrites the package name and asserts that
every module **and every imported name** resolves in `pylightcharts`. It also
checks that the module globals the old Qt route patches still exist and are read
at call time, that `install_alias()` stays lazy, and that importing
`pylightcharts` never loads a Qt binding by itself.

## New, and not in the original

Ported code is not limited to the original API. These are additions:

- `pylightcharts.indicators` - 17 indicators in pure pandas/numpy, plus
  `chart.add_sma()`-style helpers that refresh automatically on data changes;
- `pylightcharts.headless.HeadlessChart` - server-side PNG rendering;
- `pylightcharts.shapes` - declarative custom series;
- `pylightcharts.numeric` - yield-curve and options (non-time) axes;
- `pylightcharts.qt.prepare_qt()` - binding selection (above);
- `pylightcharts.compat.install_alias()` - the shim (above).

## License

The Python layer, GUI backends and drawing framework are derived from
lightweight-charts-python (MIT); the charting engine is TradingView Lightweight
Charts™ (Apache-2.0). Both are recorded in `LICENSE` and `NOTICE`, which ship with
the package.
