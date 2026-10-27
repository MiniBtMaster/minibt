"""Check that the sdist is a *self-testable* source tree.

`pylightcharts` ships two artifacts:

* the **wheel** - only ``pylightcharts/`` (plus ``js/`` assets and the
  ``licenses/`` files). Nothing else.
* the **sdist** - the full source tree, because the test suite and the
  examples reference ``examples/``, ``scripts/``, ``docs/`` and
  ``requirements.txt``; without them ``pytest`` on an unpacked sdist fails
  (that is exactly what ``MANIFEST.in`` fixes - see ``RELEASING.md`` step 6).

Usage::

    python -m build
    python scripts/check_sdist.py          # exit code 1 on any problem
"""
from __future__ import annotations

import glob
import pathlib
import sys
import tarfile
import tempfile

# Paths the unpacked sdist must contain for `pytest tests -q` to pass.
REQUIRED = (
    'MANIFEST.in',
    'requirements.txt',
    'mkdocs.yml',
    'docs/api.md',
    'examples/11_api_tour/02_series_types.py',
    'examples/13_panels/12_quote_board.py',
    'examples/13_panels/15_alert_dialog.py',
    'scripts/patch_minibt.py',
    'tests/_db_mixed_load.py',          # not `test*` - distutils would skip it
    'tests/test_examples.py',
    'pylightcharts/js/bundle.js',
    'pylightcharts/js/lightweight-charts.js',
    'pylightcharts/js/index.html',
    'pylightcharts/js/styles.css',
    # subpackage: `packages = ["pylightcharts"]` used to drop this one
    'pylightcharts/panels/__init__.py',
    'pylightcharts/panels/data_grid.py',
    'LICENSE',
    'NOTICE',
)

# Directories that must never end up in a release artifact.
FORBIDDEN = ('node_modules', 'minibt', 'tutorials', 'minibt_docs')


def unpack(archive: pathlib.Path) -> pathlib.Path:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='sdist-check-'))
    with tarfile.open(archive) as handle:
        try:
            handle.extractall(tmp, filter='data')       # Python >= 3.12
        except TypeError:                               # pragma: no cover
            handle.extractall(tmp)
    roots = [item for item in tmp.iterdir() if item.is_dir()]
    if len(roots) != 1:
        raise SystemExit(f'unexpected sdist layout: {roots}')
    return roots[0]


def main() -> int:
    archives = sorted(glob.glob('dist/*.tar.gz'))
    if not archives:
        print('no dist/*.tar.gz - run `python -m build` first')
        return 1
    archive = pathlib.Path(archives[-1])
    root = unpack(archive)
    problems = []

    for name in REQUIRED:
        if not (root / name).exists():
            problems.append(f'missing from the sdist: {name}')

    for path in root.rglob('*'):
        relative = path.relative_to(root)
        top = relative.parts[0]
        if top in FORBIDDEN:
            problems.append(f'forbidden in the sdist: {relative}')
        elif path.is_dir() and path.name in ('node_modules', '__pycache__'):
            problems.append(f'forbidden in the sdist: {relative}')
        elif path.suffix in ('.pyc', '.so'):
            problems.append(f'forbidden in the sdist: {relative}')

    print(f'{archive.name}: {len(list(root.rglob("*")))} paths')
    for problem in problems:
        print(f'  PROBLEM {problem}')
    if problems:
        return 1
    print('  OK - self-testable (manifest + no junk)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
