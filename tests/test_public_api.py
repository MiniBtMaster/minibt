"""Public API surface: ``_LAZY``, ``__all__`` and the ``TYPE_CHECKING`` imports
must agree, and importing the package must stay cheap (no GUI toolkit loaded).

The ``TYPE_CHECKING`` block in ``pylightcharts/__init__.py`` exists only for
static checkers, so nothing at runtime can keep it honest -- these tests parse
the file to do it instead.
"""
import ast
import os
import pathlib
import subprocess
import sys

import pytest

import pylightcharts

ROOT = pathlib.Path(__file__).resolve().parents[1]
INIT = pathlib.Path(pylightcharts.__file__).with_name('__init__.py')

#: modules that are only imported on first attribute access
DEFERRED = (
    'pylightcharts.chart',
    'pylightcharts.numeric',
    'pylightcharts.polygon_chart',
    'pylightcharts.widgets',
)

#: names that must never show up on the package (they leaked from ``import *``)
NOT_PUBLIC = ('pd', 'os', 'Optional', 'wx', 'webview', 'QObject')


def _init_tree():
    with open(INIT, encoding='utf-8') as handle:
        return ast.parse(handle.read())


def _lazy_table(tree):
    """``{'Chart': ('.chart', 'Chart'), ...}`` as written in ``_LAZY``."""
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if getattr(node.targets[0], 'id', None) != '_LAZY':
            continue
        return {
            key.value: (value.elts[0].value, value.elts[1].value)
            for key, value in zip(node.value.keys, node.value.values)
        }
    raise AssertionError('_LAZY not found in pylightcharts/__init__.py')


def _type_checking_imports(tree):
    """The ``TYPE_CHECKING`` block as ``{name: (module, attribute)}``."""
    imports = {}
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        if getattr(node.test, 'id', None) != 'TYPE_CHECKING':
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.ImportFrom):
                continue
            module = '.' * stmt.level + (stmt.module or '')
            for alias in stmt.names:
                imports[alias.asname or alias.name] = (module, alias.name)
    return imports


def _module_path(module):
    return 'pylightcharts.' + module.lstrip('.')


def test_lazy_names_are_listed_in_all():
    lazy = _lazy_table(_init_tree())
    exported = pylightcharts.__all__
    assert set(lazy) <= set(exported)
    assert len(exported) == len(set(exported)), 'duplicate in __all__'


def test_type_checking_block_mirrors_lazy_table():
    """Type checkers see the names through this block: it must match _LAZY."""
    assert _type_checking_imports(_init_tree()) == _lazy_table(_init_tree())


def test_lazy_entries_resolve_to_that_module_attribute():
    for name, (module, attribute) in _lazy_table(_init_tree()).items():
        value = getattr(pylightcharts, name)
        source = __import__(_module_path(module), fromlist=[attribute])
        assert getattr(source, attribute) is value, name
        assert value.__module__ == _module_path(module), name


def _project_table() -> dict:
    """``[project]`` from ``pyproject.toml``, or skip on Python < 3.11."""
    try:
        import tomllib
    except ImportError:  # pragma: no cover - Python < 3.11
        pytest.skip('tomllib requires Python 3.11+')
    with open(ROOT / 'pyproject.toml', 'rb') as handle:
        return tomllib.load(handle)['project']


def test_module_metadata_matches_pyproject():
    """The dunders must not drift from the packaging metadata."""
    project = _project_table()
    author = project['authors'][0]
    license_field = project['license']
    assert pylightcharts.__version__ == project['version']
    assert pylightcharts.__description__ == project['description']
    assert pylightcharts.__url__ == project['urls']['Homepage']
    assert pylightcharts.__author__ == author['name']
    assert pylightcharts.__email__ == author['email']
    declared = license_field.get('text', license_field)
    assert pylightcharts.__license__ == declared


def test_version_info_matches_version_string():
    parts = '.'.join(str(part) for part in pylightcharts.__version_info__)
    assert parts == pylightcharts.__version__


def test_metadata_is_exported():
    metadata = {
        '__author__', '__copyright__', '__description__', '__email__',
        '__license__', '__url__', '__version__', '__version_info__',
    }
    assert metadata <= set(pylightcharts.__all__)
    assert all(getattr(pylightcharts, name) for name in metadata)


def test_import_is_cheap_and_leaks_nothing():
    code = (
        'import sys, pylightcharts\n'
        f'loaded = [n for n in {DEFERRED!r} if n in sys.modules]\n'
        "assert not loaded, f'imported up front: {loaded}'\n"
        f'leaked = [n for n in {NOT_PUBLIC!r} if hasattr(pylightcharts, n)]\n'
        "assert not leaked, f'leaked into the namespace: {leaked}'\n"
        'assert pylightcharts.Chart.__module__ == "pylightcharts.chart"\n'
    )
    paths = [str(ROOT), os.environ.get('PYTHONPATH', '')]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(paths))
    result = subprocess.run(
        [sys.executable, '-c', code], cwd=str(ROOT), env=env,
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
