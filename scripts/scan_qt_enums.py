"""Find Qt enum members that do not exist at runtime (PySide6-style flat access).

Qt for Python 6 removed the "flat" enum access that PySide6 still allows, so a
PySide6 -> PyQt6 migration can leave lines like

    webview.setContextMenuPolicy(Qt.CustomContextMenu)     # scoped in PyQt6

which blow up on the code path that reaches them.

**`qtpy` restores the flat access process-wide** (it promotes every enum member
onto the real PyQt6 classes), and qtpy arrives
with qfluentwidgets/qframelesswindow — so in a real miniqt run those lines work.
The compat layer is therefore imported before scanning (pass ``--no-compat`` to
see what PyQt6 alone would reject); what is left after that is a genuine miss.

    python scripts/scan_qt_enums.py miniqt
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

#: qtpy promotes the members onto the real PyQt6 modules when its shims import
COMPAT = ('qtpy.QtCore', 'qtpy.QtGui', 'qtpy.QtWidgets')


def load_compat() -> list:
    """Import whatever restores flat enum access in this environment."""
    loaded = []
    for module in COMPAT:
        try:
            __import__(module)
            loaded.append(module)
        except ImportError:
            continue
    return loaded


load_compat()

from PyQt6 import QtCore, QtGui, QtWidgets        # noqa: E402

CLASSES = {}
for module in (QtCore, QtGui, QtWidgets):
    for name in dir(module):
        value = getattr(module, name)
        if isinstance(value, type):
            CLASSES.setdefault(name, value)

PATTERN = re.compile(r'\b(Qt|Q[A-Z]\w*)\s*\.\s*([A-Za-z_]\w*)')
SKIP_MEMBERS = {'pyqtSignal', 'pyqtSlot', 'pyqtProperty'}


def scoped_name(cls, member: str):
    """The PyQt6 spelling, e.g. Qt.CustomContextMenu -> Qt.ContextMenuPolicy.CustomContextMenu."""
    for enum_name in dir(cls):
        if enum_name.startswith('_'):
            continue
        enum = getattr(cls, enum_name, None)
        if isinstance(enum, type) and member in dir(enum):
            return f'{cls.__name__}.{enum_name}.{member}'
    return None


def scan(paths):
    findings = []
    for root in paths:
        for path in sorted(pathlib.Path(root).rglob('*.py')):
            try:
                text = path.read_text(encoding='utf-8', errors='replace')
            except Exception:
                continue
            lines = text.splitlines()
            for index, line in enumerate(lines, start=1):
                stripped = line.lstrip()
                if stripped.startswith('#'):
                    continue
                for match in PATTERN.finditer(line):
                    class_name, member = match.group(1), match.group(2)
                    if member in SKIP_MEMBERS:
                        continue
                    cls = CLASSES.get(class_name)
                    if cls is None or hasattr(cls, member):
                        continue
                    fix = scoped_name(cls, member)
                    if fix is None:
                        continue          # not an enum member at all: ignore
                    findings.append((str(path), index, match.group(0), fix, line.strip()))
    return findings


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('targets', nargs='*', default=['miniqt'],
                        help='directories to scan (default: miniqt)')
    parser.add_argument('--no-compat', action='store_true',
                        help='do not load qtpy.enums_compat first')
    args = parser.parse_args(argv[1:])

    targets = args.targets or ['miniqt']
    loaded = [] if args.no_compat else load_compat()
    # the module-level call above already loaded it; --no-compat cannot undo that
    if args.no_compat and loaded:
        print('note: qtpy.enums_compat was already imported by this process\n')

    findings = scan(targets)
    if not findings:
        print(f'no runtime-invalid enum members in {", ".join(targets)}'
              f'{f" (compat: {loaded[0]})" if loaded else ""}')
        return 0
    for path, line, bad, fix, source in findings:
        print(f'{path}:{line}')
        print(f'    {source}')
        print(f'    {bad}  ->  {fix}')
    print(f'\n{len(findings)} invalid enum member(s)')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
