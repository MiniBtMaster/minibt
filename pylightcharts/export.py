"""Save a chart page as one self-contained HTML file.

The static targets of this package already build their page in memory (the
engine, the bridge bundle, the styles and the chart's own scripts are inlined):
`HeadlessChart.to_html` and `pylightcharts.widgets.StaticLWC`. This mixin adds
the two conveniences on top - writing that page to a file and opening it - so a
chart can be viewed in any browser **without a server, Node, npm or any extra
dependency**:

    chart = HeadlessChart(width=1200, height=700)
    chart.set(df)
    chart.save_html('chart.html')       # double-click it, host it, mail it

Widget callbacks cannot reach Python in a static page (there is no bridge). The
page dispatches them as a `pylightcharts-callback` DOM event instead, so host
JavaScript can still react:

    window.addEventListener('pylightcharts-callback',
                            (event) => console.log(event.detail));
"""
import os
import tempfile
import webbrowser

__all__ = ['PageExport', 'CALLBACK_SHIM']

#: makes `window.callbackFunction` harmless in a page without a Python bridge
CALLBACK_SHIM = """<script>
// static export: no python on the other end of the bridge, so widget callbacks
// become a DOM event (and never throw)
if (typeof window.callbackFunction !== 'function') {
  window.callbackFunction = (message) => window.dispatchEvent(
    new CustomEvent('pylightcharts-callback', { detail: message }));
}
</script>"""


class PageExport:
    """Mixin for charts whose whole page can be produced as a string."""

    def to_html(self) -> str:                       # pragma: no cover - abstract
        """The self-contained HTML page (implemented by the static charts)."""
        raise NotImplementedError

    def save_html(self, path, encoding: str = 'utf-8') -> str:
        """Write :meth:`to_html` to `path` and return the path."""
        path = os.fspath(path)
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with open(path, 'w', encoding=encoding) as handle:
            handle.write(self.to_html())
        return path

    def open_in_browser(self, path=None, new: int = 2) -> str:
        """Save the page to a temporary file and open it in the browser."""
        if path is None:
            path = os.path.join(tempfile.gettempdir(),
                                'pylightcharts-chart.html')
        path = self.save_html(path)
        webbrowser.open('file://' + os.path.abspath(path), new=new)
        return path
