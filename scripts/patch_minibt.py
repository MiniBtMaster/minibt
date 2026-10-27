"""Apply the pandas-guard patch to a minibt checkout (idempotent, self-verifying).

    python scripts/patch_minibt.py                 # patch ../minibt (default)
    python scripts/patch_minibt.py --minibt PATH
    python scripts/patch_minibt.py --check         # exit 1 if not patched
    python scripts/patch_minibt.py --no-verify

Why this exists: ``minibt/indicators/core.py`` ends with

    pd.DataFrame.__call__ = _call_
    pd.Series.__call__ = _call_

so that ``df(...)`` builds a ``KLine`` / ``IndFrame`` / ``IndSeries``. That makes
*every* Series callable, and pandas routes the condition of ``where`` / ``mask`` /
``clip`` (and ``iloc[callable]``) through ``pandas.core.common.apply_if_callable``,
which **invokes** anything callable:

    cond = common.apply_if_callable(cond, self)   # -> cond(self)

The boolean mask is then replaced by a mis-aligned object and the result changes
silently — no exception, no warning:

    (close.diff().iloc[1:]).clip(lower=0).min()   # 0 -> -1.65

Measured blast radius in minibt itself: 30 ``.clip(`` / 344 ``.where(`` /
4 ``.mask(`` call sites. In pristine pandas a Series/DataFrame is *not* callable,
so excluding pandas objects from ``apply_if_callable`` restores upstream semantics
exactly, while the ``df(...)`` sugar keeps working.

minibt is not under version control here, so this script is the way to re-apply
the guard after a minibt update — and to verify an existing checkout.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = pathlib.Path('indicators') / 'core.py'

#: minibt is gitignored inside this repo; fall back to a plain sibling directory
DEFAULT_MINIBT = next(
    (candidate for candidate in (ROOT / 'minibt', ROOT.parent / 'minibt')
     if (candidate / TARGET).exists()),
    ROOT / 'minibt')

#: the line that proves the guard is in place
MARKER = '_pd_guarded_apply_if_callable'

#: anchor: the two assignments that create the problem
ANCHOR = 'pd.Series.__call__ = _call_'

GUARD = '''

# 双保险：恢复 pandas 本来的语义 —— 在原生 pandas 里 Series/DataFrame 都不是可调用
# 对象，因此“把某个 Series 当作回调”永远不是有效用法。直接把 pandas 对象从
# apply_if_callable 里排除，等价于上游行为，且不依赖 _call_ 内部怎么实现。
try:
    from pandas.core import common as _pd_common

    _pd_apply_if_callable = _pd_common.apply_if_callable

    def _pd_guarded_apply_if_callable(maybe_callable, obj, **kwargs):
        if isinstance(maybe_callable, (pd.Series, pd.DataFrame)):
            return maybe_callable
        return _pd_apply_if_callable(maybe_callable, obj, **kwargs)

    _pd_common.apply_if_callable = _pd_guarded_apply_if_callable
except Exception:                     # pragma: no cover - pandas 内部结构变动
    pass
'''

VERIFY = r'''
import numpy as np, pandas as pd
import minibt

series = pd.Series(100 + np.cumsum(np.random.default_rng(1).standard_normal(80)))
delta = series.diff().iloc[1:]
problems = []
if not np.isclose(delta.clip(lower=0.0).min(), 0.0):
    problems.append(f"clip(lower=0).min() == {delta.clip(lower=0.0).min()!r}, expected 0")
if not np.isclose(delta.where(delta > 0, 0.0).min(), 0.0):
    problems.append("Series.where() returned a negative where it must be 0")
if not np.isclose(delta.mask(delta < 0, 0.0).min(), 0.0):
    problems.append("Series.mask() returned a negative where it must be 0")
if not isinstance(series(), minibt.IndSeries):
    problems.append("the `series(...)` sugar no longer builds an IndSeries")
if problems:
    print('FAIL: ' + '; '.join(problems))
    raise SystemExit(1)
print('OK: pandas conditions are correct and the df(...) sugar still works')
'''


def patch_source(text: str) -> tuple:
    """Return ``(text, changed)``. Idempotent: a guarded file is left alone."""
    if MARKER in text:
        return text, False
    if ANCHOR not in text:
        raise SystemExit(
            f'cannot find {ANCHOR!r} - is this really minibt/indicators/core.py?')
    # insert right after the assignment line, keeping whatever follows it
    text = re.sub(rf'(?m)^({re.escape(ANCHOR)}[ \t]*)$', rf'\1{GUARD}', text, count=1)
    return text, True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--minibt', default=str(DEFAULT_MINIBT),
                        help='minibt checkout (default: %(default)s)')
    parser.add_argument('--check', action='store_true',
                        help='only report whether the guard is present')
    parser.add_argument('--no-verify', action='store_true',
                        help='skip the subprocess verification')
    args = parser.parse_args(argv)

    path = pathlib.Path(args.minibt).expanduser().resolve() / TARGET
    if not path.exists():
        print(f'error: {path} does not exist', file=sys.stderr)
        return 2

    text = path.read_text(encoding='utf-8')
    patched, changed = patch_source(text)

    if args.check:
        print(f'{"patched" if not changed else "NOT patched"}: {path}')
        return 0 if not changed else 1

    if changed:
        backup = path.with_suffix(path.suffix + '.bak')
        shutil.copy2(path, backup)
        path.write_text(patched, encoding='utf-8')
        print(f'patched  : {path}')
        print(f'backup   : {backup}')
    else:
        print(f'already  : {path} is guarded, nothing to do')

    if not args.no_verify:
        result = subprocess.run([sys.executable, '-c', VERIFY], cwd=str(path.parents[2]),
                                capture_output=True, text=True)
        output = (result.stdout + result.stderr).strip().splitlines()
        print('verify   :', output[-1] if output else '(no output)')
        return result.returncode
    return 0


if __name__ == '__main__':
    sys.exit(main())
