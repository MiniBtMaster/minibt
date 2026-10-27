"""Alias ``lightweight_charts`` to :mod:`pylightcharts`.

`pylightcharts` is a behavioural superset of
[lightweight-charts-python](https://github.com/louisnw01/lightweight-charts-python):
every class, method and module-level name is preserved (enforced by
``tests/test_lwc_compat.py``). That makes a zero-edit migration possible:

    from pylightcharts.compat import install_alias
    install_alias()                     # before any `import lightweight_charts`

    import lightweight_charts            # -> pylightcharts
    from lightweight_charts.widgets import QtChart

Why a meta-path finder instead of pre-registering ``sys.modules``
-----------------------------------------------------------------

Aliasing eagerly would import ``pylightcharts.widgets`` during
``install_alias()``. That module probes PyQt5 -> PySide6 -> PyQt6 and therefore
loads **PySide6's Qt6 DLLs into the process**. If the application then imports
the *other* binding (PyQt6's ``QtSvg``/``QtWebEngine``), Windows resolves Qt6
symbols against the already-loaded PySide6 DLLs and raises

    ImportError: DLL load failed while importing QtSvg

The finder below resolves ``lightweight_charts.<x>`` lazily, on first use, so the
import order is exactly what it would have been with the original package.

The modules are the *same objects*, so monkey-patching module globals (how Qt
backends force PyQt6 over PySide6) keeps working:

    import lightweight_charts.widgets
    lightweight_charts.widgets.QWebEngineView = PyQt6QWebEngineView
"""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
from typing import Optional

__all__ = ['install_alias', 'remove_alias', 'SUBMODULES', 'AliasFinder']

TARGET = 'pylightcharts'
ALIAS = 'lightweight_charts'

#: kept for documentation/inspection; the finder resolves anything under the
#: alias, these are just the ones downstream projects are known to use
SUBMODULES = (
    'abstract', 'chart', 'compat', 'drawings', 'headless', 'indicators',
    'indicators_api', 'numeric', 'polygon', 'price_scale', 'shapes', 'table',
    'toolbox', 'topbar', 'util', 'widgets',
)


class _AliasLoader(importlib.abc.Loader):
    """Hands back an already-imported module object under a different name."""

    def __init__(self, module) -> None:
        self._module = module

    def create_module(self, spec):                      # noqa: D102
        return self._module

    def exec_module(self, module):                      # noqa: D102
        pass


class AliasFinder(importlib.abc.MetaPathFinder):
    """Resolves `alias` and `alias.<sub>` onto `target` / `target.<sub>` lazily."""

    def __init__(self, alias: str = ALIAS, target: str = TARGET) -> None:
        self.alias = alias
        self.target = target

    def find_spec(self, fullname: str, path=None, target=None):     # noqa: D102
        if fullname == self.alias:
            real_name = self.target
        elif fullname.startswith(self.alias + '.'):
            real_name = self.target + fullname[len(self.alias):]
        else:
            return None
        module = importlib.import_module(real_name)
        is_package = hasattr(module, '__path__')
        spec = importlib.util.spec_from_loader(fullname, _AliasLoader(module), is_package=is_package)
        return spec


def _find_existing(alias: str) -> Optional[AliasFinder]:
    for finder in sys.meta_path:
        if isinstance(finder, AliasFinder) and finder.alias == alias:
            return finder
    return None


def install_alias(package: str = ALIAS, target: str = TARGET) -> None:
    """Make ``import <package>`` resolve to <target>.

    Nothing is imported up front, so whichever Qt binding the application loads
    first stays the only one loaded.
    """
    if _find_existing(package) is None:
        sys.meta_path.insert(0, AliasFinder(package, target))
    # an already-imported copy of the real package would shadow the finder
    for key in [k for k in list(sys.modules)
                if k == package or k.startswith(package + '.')]:
        del sys.modules[key]


def remove_alias(package: str = ALIAS) -> None:
    """Undo :func:`install_alias` (mainly useful in tests)."""
    finder = _find_existing(package)
    if finder is not None:
        sys.meta_path.remove(finder)
    for key in [k for k in list(sys.modules)
                if k == package or k.startswith(package + '.')]:
        del sys.modules[key]
