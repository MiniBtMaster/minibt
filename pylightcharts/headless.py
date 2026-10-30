"""Server-side (headless) rendering.

`HeadlessChart` is an `AbstractChart` that records everything it would send to a
webview instead of opening one. `render()` then replays those scripts inside a
headless Chromium (Playwright if available, otherwise a Chrome/Edge CLI) and
returns the screenshot as PNG bytes.

    from pylightcharts.headless import HeadlessChart

    chart = HeadlessChart(width=1200, height=700)
    chart.set(df)
    chart.add_sma('close', 20)
    chart.add_rsi(14)
    chart.render('out.png')
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Optional

from .abstract import AbstractChart, Window
from .export import CALLBACK_SHIM, PageExport

_JS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'js')

_BROWSER_CANDIDATES = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    'google-chrome',
    'google-chrome-stable',
    'chromium',
    'chromium-browser',
    'chrome',
]


def find_browser() -> Optional[str]:
    """Locate a Chromium-family browser executable."""
    override = os.environ.get('PYLIGHTCHARTS_CHROME') or os.environ.get('CHROME')
    candidates = [override] if override else []
    candidates += _BROWSER_CANDIDATES
    for candidate in candidates:
        if not candidate:
            continue
        if os.path.isabs(candidate):
            if os.path.exists(candidate):
                return candidate
        else:
            found = shutil.which(candidate)
            if found:
                return found
    return None


class HeadlessChart(PageExport, AbstractChart):
    """A chart that never opens a window; use :meth:`render` to get a PNG."""

    def __init__(self, width: int = 1200, height: int = 700, **kwargs):
        self._viewport = (width, height)
        self._scripts = []
        window = Window(script_func=self._scripts.append)
        window.loaded = True  # execute scripts straight into the recorder
        window._return_q = None  # there is no webview to answer queries
        super().__init__(window, **kwargs)

    # ------------------------------------------------------------------

    def to_scripts(self) -> str:
        """All recorded bridge statements, as one JS program.

        Statements are separated with ``;`` so that ASI cannot merge two calls
        (e.g. a script ending in ``null`` followed by an IIFE starting with ``(``,
        which would run ``null(function(){...})`` and abort the rest ✓).
        """
        return '\n;\n'.join(self._scripts)

    def to_html(self, title: str = 'pylightcharts') -> str:
        """A self-contained HTML page that draws this chart."""
        with open(os.path.join(_JS_DIR, 'lightweight-charts.js'), encoding='utf-8') as handle:
            engine = handle.read()
        with open(os.path.join(_JS_DIR, 'bundle.js'), encoding='utf-8') as handle:
            bundle = handle.read()
        with open(os.path.join(_JS_DIR, 'styles.css'), encoding='utf-8') as handle:
            styles = handle.read()
        return (
            '<!DOCTYPE html><html><head><meta charset="utf-8">'
            f'<title>{title}</title><style>{styles}\n'
            'body { margin: 0; padding: 0; overflow: hidden; background: #000; }'
            '</style></head><body><div id="container"></div>'
            f'<script>{engine}</script><script>{bundle}</script>'
            f'{self._scripts_html()}'
            f'{CALLBACK_SHIM}'
            '</body></html>'
        )

    def _scripts_html(self) -> str:
        """图表脚本 → `<script>`。

        `MINIBT_DESK_SCRIPT_TRACE=1` 时**逐条 try/catch**（`self._scripts` 是
        **列表**，一条一个 JavaScript 语句）：某条抛错（例如
        lightweight-charts 的 `Value is null`）不会连带整页静默失败，而是把
        "第几条 + 该语句前 140 字符"记到 `window.__deskSLFail` ✓
        """
        if not os.environ.get('MINIBT_DESK_SCRIPT_TRACE'):
            return f'<script>{self.to_scripts()}</script>'
        parts = ['<script>window.__deskSLFail=[];</script>']
        for index, script in enumerate(self._scripts):
            head = str(script)[:140].replace(chr(92), chr(47))
            body = str(script).replace('</script>', '<' + chr(92) + '/script>')
            parts.append(
                '<script>try{' + chr(10) + body + chr(10)
                + '}catch(err){window.__deskSLFail.push(' + repr(str(index))
                + ' + ": " + String(err && err.message || err) + " | " + '
                + repr(head) + ')}</script>')
        return ''.join(parts)

    def render(self, path: Optional[str] = None, width: Optional[int] = None,
               height: Optional[int] = None, wait_ms: int = 1500,
               device_scale_factor: float = 1.0) -> bytes:
        """Render the chart to a PNG (headless Chromium).

        :param path: optional file path to write the PNG to.
        :param width/height: viewport size, defaults to the size given at construction.
        :param wait_ms: how long to let the browser render before capturing.
        :returns: the PNG file contents.
        """
        width = width or self._viewport[0]
        height = height or self._viewport[1]
        html = self.to_html()

        data = self._render_with_playwright(html, width, height, wait_ms, device_scale_factor)
        if data is None:
            data = self._render_with_cli(html, width, height, wait_ms)

        if path:
            with open(path, 'wb') as handle:
                handle.write(data)
        return data

    # ------------------------------------------------------------------

    def _render_with_playwright(self, html, width, height, wait_ms, device_scale_factor):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(
                viewport={'width': width, 'height': height},
                device_scale_factor=device_scale_factor,
            )
            page.set_content(html, wait_until='load')
            page.wait_for_timeout(wait_ms)
            data = page.screenshot(type='png')
            browser.close()
            return data

    def _render_with_cli(self, html, width, height, wait_ms):
        browser = find_browser()
        if not browser:
            raise RuntimeError(
                'No Chromium-family browser found for headless rendering. '
                'Install playwright, or set PYLIGHTCHARTS_CHROME to a browser path.'
            )
        with tempfile.TemporaryDirectory(prefix='pylightcharts-') as folder:
            html_path = os.path.join(folder, 'chart.html')
            png_path = os.path.join(folder, 'chart.png')
            with open(html_path, 'w', encoding='utf-8') as handle:
                handle.write(html)
            subprocess.run([
                browser,
                '--headless=new',
                '--disable-gpu',
                '--no-sandbox',
                '--hide-scrollbars',
                '--allow-file-access-from-files',
                f'--virtual-time-budget={wait_ms + 1000}',
                f'--window-size={width},{height}',
                f'--screenshot={png_path}',
                f'file://{html_path}',
            ], check=True, capture_output=True)
            with open(png_path, 'rb') as handle:
                return handle.read()
