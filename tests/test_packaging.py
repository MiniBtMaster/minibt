"""Packaging checks: the built JS assets must exist and ship inside the wheel."""
import os
import pathlib
import re
import subprocess
import sys
import zipfile

import pytest

import pylightcharts

JS_ASSETS = ['bundle.js', 'lightweight-charts.js', 'index.html', 'styles.css']
JS_DIR = os.path.join(os.path.dirname(os.path.abspath(pylightcharts.__file__)), 'js')


def test_js_assets_exist():
    for name in JS_ASSETS:
        path = os.path.join(JS_DIR, name)
        assert os.path.isfile(path), f'missing {path} (run `npm run build` in jslib/)'
        assert os.path.getsize(path) > 100, f'{name} looks empty'


def test_index_html_references_all_assets():
    with open(os.path.join(JS_DIR, 'index.html'), encoding='utf-8') as handle:
        html = handle.read()
    for name in ('lightweight-charts.js', 'bundle.js', 'styles.css'):
        assert name in html, name


def test_bundle_exposes_the_bridge_api():
    with open(os.path.join(JS_DIR, 'bundle.js'), encoding='utf-8') as handle:
        bundle = handle.read()
    for symbol in ('invoke', 'register', 'decodeData'):
        assert f'.{symbol}=' in bundle, f'Lib.{symbol} missing from the bundle'


def _distribution_names(lines):
    """Pull bare distribution names out of requirement lines."""
    names = set()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('-'):
            continue
        name = re.split(r'[<>=!\[; ]', line, 1)[0].strip().lower()
        if name:
            names.add(name)
    return names


def test_requirements_txt_matches_pyproject():
    """`requirements.txt` must mirror `project.dependencies`."""
    try:
        import tomllib
    except ImportError:  # pragma: no cover - Python < 3.11
        pytest.skip('tomllib requires Python 3.11+')

    root = pathlib.Path(__file__).resolve().parents[1]
    with open(root / 'pyproject.toml', 'rb') as handle:
        pyproject = tomllib.load(handle)
    declared = _distribution_names(pyproject['project']['dependencies'])
    with open(root / 'requirements.txt', encoding='utf-8') as handle:
        required = _distribution_names(handle.readlines())
    assert required == declared, f'requirements.txt {sorted(required)} != pyproject {sorted(declared)}'


@pytest.mark.slow
def test_wheel_ships_js_assets(tmp_path):
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'wheel', '.', '--no-deps', '--no-build-isolation',
         '-w', str(tmp_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.skip(f'could not build a wheel here: {result.stderr[-300:]}')

    wheels = list(tmp_path.glob('pylightcharts-*.whl'))
    assert wheels, 'no wheel produced'
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
    for name in JS_ASSETS:
        assert f'pylightcharts/js/{name}' in names, f'{name} missing from the wheel'
    for name in ('panels/__init__.py', 'panels/data_grid.py',
                 'panels/sparkline.py'):
        assert f'pylightcharts/{name}' in names, \
            f'{name} missing from the wheel (subpackage not packaged)'


def test_panels_subpackage_is_packaged():
    """`pylightcharts.panels` must be discovered as a package.

    `packages = ["pylightcharts"]` (without the `packages.find` section) used
    to ship the top package but silently drop this subpackage from the wheel
    and the sdist.
    """
    from pylightcharts import panels
    assert panels.__file__, 'pylightcharts.panels has no file (not packaged?)'
    for symbol in ('DataGrid', 'Column', 'Sparkline', 'MarketData',
                   'Heatmap', 'Screener'):
        assert hasattr(panels, symbol), symbol


def test_version_is_consistent():
    """`pyproject.toml` / `__version__` / `__version_info__` 三处必须一致。"""
    root = pathlib.Path(__file__).resolve().parents[1]
    text = (root / 'pyproject.toml').read_text(encoding='utf-8')
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    assert match, 'version missing from pyproject.toml'
    version = match.group(1)
    assert pylightcharts.__version__ == version
    assert '.'.join(map(str, pylightcharts.__version_info__)) == version
    # `RELEASING.md` step 1 also pins the module docstring's `- Version:` line,
    # so the packaged README/docs cannot drift from the metadata.
    docstring = pylightcharts.__doc__ or ''
    assert f'- Version: {version}' in docstring, \
        f'`__init__` docstring does not say "- Version: {version}"'
