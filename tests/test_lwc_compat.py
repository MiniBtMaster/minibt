"""Drop-in compatibility with lightweight-charts-python.

`miniqt` / `minibt` were written against lightweight-charts-python, so this
test parses every `lightweight_charts` import they make, rewrites the package
name to `pylightcharts` and asserts the module and every imported name resolve.

It is skipped when those projects are not next to this repository.
"""
import ast
import importlib
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCES = [ROOT / 'miniqt', ROOT / 'minibt']
OLD = 'lightweight_charts'
NEW = 'pylightcharts'


def _collect_imports():
    """Every (module, [names], file) the downstream projects import."""
    found = {}
    for source in SOURCES:
        if not source.is_dir():
            continue
        for path in source.rglob('*.py'):
            try:
                tree = ast.parse(path.read_text(encoding='utf-8', errors='ignore'))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (node.module or '').startswith(OLD):
                    module = NEW + (node.module or '')[len(OLD):]
                    names = [alias.name for alias in node.names]
                    key = (module, tuple(names))
                    found.setdefault(key, path.relative_to(ROOT).as_posix())
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith(OLD):
                            module = NEW + alias.name[len(OLD):]
                            found.setdefault((module, ()), path.relative_to(ROOT).as_posix())
    return found


IMPORTS = _collect_imports()

pytestmark = pytest.mark.skipif(
    not IMPORTS,
    reason='miniqt / minibt are not present next to this repository',
)


def test_downstream_projects_are_present():
    assert IMPORTS, 'expected at least one lightweight_charts import'


@pytest.mark.parametrize('module,names', sorted(IMPORTS, key=lambda item: (item[0], item[1])))
def test_import_is_satisfied(module, names):
    origin = IMPORTS[(module, names)]
    try:
        loaded = importlib.import_module(module)
    except ImportError as error:                       # pragma: no cover - failure path
        pytest.fail(f'{origin}: cannot import {module!r} from pylightcharts ({error})')
    for name in names:
        assert hasattr(loaded, name), (
            f'{origin}: {module}.{name} is missing from pylightcharts'
        )


def test_widgets_backend_can_be_monkey_patched():
    """miniqt replaces these module globals to force PyQt6 over PySide6."""
    widgets = importlib.import_module(f'{NEW}.widgets')
    for attribute in ('QWebEngineView', 'QWebChannel', 'QObject', 'Slot',
                      'QUrl', 'QTimer', 'Bridge', 'using_pyside6', 'QtChart',
                      'emit_callback', 'using_pyside6'):
        assert hasattr(widgets, attribute), f'{NEW}.widgets.{attribute} is missing'
    # QtChart must read the globals at call time, otherwise patching is useless
    source = (ROOT / NEW / 'widgets.py').read_text(encoding='utf-8')
    for token in ('QWebEngineView(widget)', 'QWebChannel()', 'Bridge(self)', 'QTimer.singleShot'):
        assert token in source, f'QtChart no longer uses the module global {token}'


def test_migrated_minibt_charts_import_pylightcharts_directly():
    """minibt's two chart modules must not go back to the alias.

    They used to import ``lightweight_charts`` and monkey-patch its Qt globals
    to force PyQt6; they now import ``pylightcharts`` and let ``prepare_qt``
    choose the binding.  ``import lightweight_charts`` is still satisfied by the
    alias, so nothing else would notice a regression here - hence this check.
    """
    for relative in ('minibt/strategy/light_chart.py',
                     'minibt/strategy/light_chart_replay.py'):
        path = ROOT / relative
        if not path.exists():
            pytest.skip(f'{relative} is not present next to this repository')
        source = path.read_text(encoding='utf-8', errors='ignore')
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)

        assert not [name for name in imported if name.startswith(OLD)], \
            f'{relative} still imports {OLD}'
        assert any(name.startswith(NEW) for name in imported), \
            f'{relative} does not import {NEW}'
        # Qt refuses to import QtWebEngineWidgets once a QApplication exists, and
        # pylightcharts.widgets imports it, so the binding has to be chosen first.
        assert "prepare_qt('PyQt6')" in source, \
            f'{relative} must call prepare_qt("PyQt6") before building QApplication'
        assert 'using_pyside6' not in source, \
            f'{relative} still forces the binding by patching module globals'


def test_js_internals_referenced_by_downstream_exist():
    """miniqt drives the chart through JS strings; those names must exist."""
    bundle = (ROOT / NEW / 'js' / 'bundle.js').read_text(encoding='utf-8')
    for token in ('legend', 'toolBox', '_drawingTool', 'clearDrawings',
                  'loadDrawings', 'saveDrawings', 'repositionOnTime',
                  'addNewDrawing', 'syncCharts', 'makeSearchBox', 'makeSpinner',
                  'setRootStyles', 'createToolBox'):
        assert token in bundle, f'Lib.Handler no longer exposes {token!r}'


# --------------------------------------------------------------------------
# alias shim: zero-edit migration
# --------------------------------------------------------------------------

def test_alias_shim_makes_lightweight_charts_importable():
    from pylightcharts.compat import install_alias, remove_alias

    # the real package may or may not be installed in this environment; the
    # shim must win either way.
    remove_alias()
    install_alias()
    try:
        import lightweight_charts  # noqa: F401  (the alias)

        assert sys.modules[OLD] is sys.modules[NEW]
        util_module = importlib.import_module(f'{OLD}.util')
        widgets_module = importlib.import_module(f'{OLD}.widgets')
        assert util_module is importlib.import_module(f'{NEW}.util')
        assert widgets_module is importlib.import_module(f'{NEW}.widgets')

        from lightweight_charts.util import Events, JSEmitter          # noqa: F401
        from lightweight_charts.abstract import AbstractChart           # noqa: F401
        from lightweight_charts.drawings import HorizontalLine          # noqa: F401
        from lightweight_charts.toolbox import ToolBox, json            # noqa: F401
        from lightweight_charts.widgets import QtChart                  # noqa: F401
    finally:
        remove_alias()


def test_alias_shim_supports_module_patching():
    """The Qt backend is forced by replacing module globals - must still work."""
    from pylightcharts.compat import install_alias, remove_alias

    install_alias()
    try:
        widgets = importlib.import_module(f'{OLD}.widgets')
        real = importlib.import_module(f'{NEW}.widgets')
        sentinel = object()
        widgets.QWebEngineView = sentinel
        assert real.QWebEngineView is sentinel            # same module object
    finally:
        remove_alias()


def test_default_jsemitter_signature_is_backwards_compatible():
    """`wrapper` must stay the 4th positional argument."""
    import inspect

    from pylightcharts.util import JSEmitter

    parameters = list(inspect.signature(JSEmitter.__init__).parameters)
    assert parameters[:5] == ['self', 'chart', 'name', 'on_iadd', 'wrapper']


def test_importing_pylightcharts_does_not_load_a_qt_binding():
    """Importing pylightcharts must not bind a GUI toolkit.

    The first Qt binding loaded wins for the whole process: `pylightcharts.widgets`
    probes PyQt5 -> PySide6 -> PyQt6, so importing it eagerly would load PySide6's
    Qt6 DLLs and break a PyQt6 application (`DLL load failed while importing QtSvg`).
    """
    import subprocess
    import textwrap

    code = textwrap.dedent(
        """
        import sys
        import pylightcharts
        bindings = sorted({m.split('.')[0] for m in sys.modules
                           if m.split('.')[0] in ('PyQt6', 'PyQt5', 'PySide6', 'wx')})
        print(','.join(bindings))
        """
    )
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True,
                   encoding='utf-8', errors='replace')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '', (
        f'importing pylightcharts loaded {result.stdout.strip()}'
    )


def test_install_alias_is_lazy():
    """install_alias() must not import anything itself."""
    from pylightcharts.compat import install_alias, remove_alias

    remove_alias()
    before = set(sys.modules)
    install_alias()
    try:
        # the alias itself pulls in nothing but pylightcharts
        added = {m for m in set(sys.modules) - before if m.startswith(NEW)}
        assert added <= {NEW, f'{NEW}.compat'}, f'install_alias imported {sorted(added)}'
        assert OLD not in sys.modules
        # ...but it resolves on demand
        module = importlib.import_module(OLD)
        assert module is sys.modules[NEW]
    finally:
        remove_alias()


# ---------------------------------------------------------------------------
# positional forwarding audit
#
# miniqt/minibt wrap the chart API with thin methods that forward to
# `self.chart.method(...)`. When pylightcharts renames or reorders a parameter
# such a wrapper silently feeds the wrong slot (e.g. `price_scale_id` landing in
# `scale_margin_top`) - that is exactly how `create_histogram` broke. This test
# re-checks every forwarded call against the current signatures.
# ---------------------------------------------------------------------------
import inspect  # noqa: E402


def _signatures():
    from pylightcharts import (abstract, drawings, price_scale, table, toolbox,
                               topbar)
    classes = [
        abstract.AbstractChart, abstract.SeriesCommon, abstract.Line,
        abstract.Histogram, abstract.BridgeSeries, abstract.CustomSeries,
        abstract.GenericSeries, abstract.Area, abstract.Bar,
        abstract.Baseline, abstract.Candlestick, abstract.Window,
        # 绘图（水平线位线等）也在子项目里转发（例 ``line.options(color,
        # style, width, text)``）—— 不收它们就会报
        # “does not bind to any signature” 的假警 ✗
        drawings.Drawing, drawings.HorizontalLine, drawings.VerticalLine,
        drawings.RayLine, drawings.Position,
        price_scale.PriceScale, price_scale.PriceLine, table.Table,
        toolbox.ToolBox, topbar.TopBar,
    ]
    found = {}
    for cls in classes:
        for name, member in vars(cls).items():
            if name.startswith('_') or not callable(member):
                continue
            try:
                found.setdefault(name, []).append(inspect.signature(member))
            except (TypeError, ValueError):
                pass
    return found


_CHART_RECEIVERS = {'chart', 'subchart', 'series', 'line', 'hist', 'candle',
                    'main_chart', 'base_chart', 'lwc'}
_PLACEHOLDER = object()


def _is_chart_receiver(node):
    if isinstance(node, ast.Name):
        return node.id in _CHART_RECEIVERS
    if isinstance(node, ast.Attribute):
        return node.attr in _CHART_RECEIVERS
    return False


def _binds(signature, call):
    args = [_PLACEHOLDER] * len(call.args)
    kwargs = {}
    for keyword in call.keywords:
        if keyword.arg is None or isinstance(keyword.value, ast.Starred):
            return True
        kwargs[keyword.arg] = _PLACEHOLDER
    try:
        signature.bind(None, *args, **kwargs)
        return True
    except TypeError:
        return False


def _positional_names(signature):
    return [p.name for p in signature.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)][1:]


@pytest.mark.parametrize('source', SOURCES, ids=lambda p: p.name)
def test_downstream_wrappers_match_the_signatures(source):
    signatures = _signatures()
    findings = []
    paths = ([p for p in source.rglob('*.py') if '__pycache__' not in str(p)]
             if source.is_dir() else [])
    if not paths:
        pytest.skip(f'{source.name} is not next to this repository')

    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding='utf-8', errors='ignore'))
        except SyntaxError:
            continue
        for func in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            params = [a.arg for a in func.args.args if a.arg != 'self']
            for call in [n for n in ast.walk(func) if isinstance(n, ast.Call)]:
                callee = call.func
                if not isinstance(callee, ast.Attribute):
                    continue
                if callee.attr not in signatures:
                    continue
                if not _is_chart_receiver(callee.value):
                    continue
                sigs = signatures[callee.attr]
                if not any(_binds(sig, call) for sig in sigs):
                    findings.append(
                        f'{path.relative_to(ROOT)}:{call.lineno}: {func.name} -> '
                        f'{callee.attr}(...) does not bind to any signature')
                    continue
                names = [a.id for a in call.args if isinstance(a, ast.Name)]
                if len(names) != len(call.args) or not names:
                    continue
                if not all(name in params for name in names):
                    continue
                # a name that lines up with *any* overload of that method is fine
                # (`set` exists on both the chart and the series classes)
                bad = None
                for sig in sigs:
                    target = _positional_names(sig)
                    if len(target) < len(names):
                        continue
                    pairs = [f'{n}->{target[i]}'
                             for i, n in enumerate(names) if n != target[i]]
                    if not pairs:
                        bad = None
                        break
                    bad = (sig, pairs)
                if bad:
                    sig, pairs = bad
                    findings.append(
                        f'{path.relative_to(ROOT)}:{call.lineno}: {func.name} '
                        f'forwards {names} to {callee.attr}{sig} ({", ".join(pairs)})')
    assert not findings, 'positional forwarding is out of sync:\n' + '\n'.join(findings)
