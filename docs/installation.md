# Installation

```bash
pip install pylightcharts
```

The JavaScript bundle is shipped inside the wheel, so **Node is not required** at
install time.

## Backends

The desktop `Chart` uses [pywebview](https://pywebview.flowrl.com/), which is
installed automatically. Optional backends:

=== "Browser (static HTML)"

    No extra dependency - the engine and the bridge ship with the package:

    ```python
    from pylightcharts import BrowserChart

    chart = BrowserChart(width=1200, height=700)
    chart.set(df)
    chart.add_sma('close', 20)
    chart.show()                 # writes one .html file and opens it
    ```

    The page is self-contained (open it from `file://`, host it, mail it). There
    is no Python bridge in a browser, so widget callbacks become
    `pylightcharts-callback` DOM events instead of Python calls.

    For a **live** chart - real-time watching, driven from Python - pass
    `live=True`:

    ```python
    chart = BrowserChart(width=1200, height=700, live=True)
    chart.set(history)
    chart.show(block=False)          # serves + opens a tab, returns the URL
    while True:
        chart.update(next_bar())     # appears in the browser immediately
        time.sleep(1)
    ```

    That is a small stdlib HTTP + Server-Sent-Events server (still **zero** extra
    dependency and nothing written to disk): updates stream to every open tab and
    widget callbacks are posted back into Python. A reload re-sends the current
    data (`resync=True`).

=== "Jupyter"

    ```bash
    pip install "pylightcharts[jupyter]"
    ```

    ```python
    from pylightcharts import JupyterChart
    JupyterChart(...)
    ```

=== "Qt"

    ```bash
    pip install "pylightcharts[qt]"       # PySide6
    ```

    For a PyQt6 application, install PyQt6 and its web engine instead - and tell
    `pylightcharts` which binding to use **before** the `QApplication` exists:

    ```bash
    pip install PyQt6 PyQt6-WebEngine
    ```

    ```python
    from pylightcharts.qt import prepare_qt
    prepare_qt('PyQt6')
    app = QApplication([])
    ```

    See [Qt integration](guide/qt.md) - the ordering matters, and Qt is not shy
    about saying so if you get it wrong.

=== "Headless rendering"

    ```bash
    pip install "pylightcharts[e2e]"    # playwright + pillow
    playwright install chromium
    ```

    A local Chrome/Edge also works without Playwright; set
    `PYLIGHTCHARTS_CHROME=/path/to/chrome` if it is not auto-detected.

## From source

```bash
git clone https://github.com/MiniBtMaster/pylightcharts
cd pylightcharts
cd jslib && npm install && npm run build && cd ..
pip install -e .                       # or: pip install -r requirements-dev.txt
```

`pyproject.toml` is the source of truth for dependencies; `requirements.txt` and
`requirements-dev.txt` mirror it for `pip install -r` workflows (a test enforces
that they stay in sync).

## Requirements

- Python 3.9+
- `pandas` (>=1.5), `numpy` (>=1.23), `pywebview` (>=5.0.5) — desktop charts
- `PyQt6` / `PySide6` (+ the matching WebEngine package) for embedded Qt charts
- `pillow` / `playwright` only for headless rendering
