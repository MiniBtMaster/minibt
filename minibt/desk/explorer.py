"""资源管理器（P57）：给 desk 的「代码」页签提供文件树 / 右键操作 ✓

设计原则：

* **只碰用户自己选的根目录**（默认 `~/.minibt/personal`），拒绝目录穿越；
* 剪切 / 复制 / 粘贴的「剪贴板」只活在**当前 desk 进程**里（不写系统剪贴板，
  免得和用户其它程序打架）；
* 所有函数都返回 dict（`{'ok': bool, ...}`），不抛异常（前端直接显示 error ✓）。
"""
from __future__ import annotations

import os
import shutil
import time
from typing import Any, Dict, List, Optional

from . import personal as _pi

#: 默认根目录（和个人指标目录同一处，用户容易找 ✓）
DEFAULT_ROOT = _pi.PERSONAL_ROOT

#: 一次最多列多少条（防止选到 C:\ 把界面卡死 ✗）
MAX_ENTRIES = 3000

#: 剪贴板：`{path, mode}`（mode = copy / cut）
_CLIPBOARD: Dict[str, str] = {}


def _norm(path: str) -> str:
    return os.path.abspath(os.path.expanduser(str(path or '').strip()))


def root_of(stored: str = '') -> str:
    """当前根目录（不存在就回退到默认根 ✓）"""
    path = _norm(stored) if stored else ''
    if path and os.path.isdir(path):
        return path
    fallback = _norm(DEFAULT_ROOT)
    try:
        os.makedirs(fallback, exist_ok=True)
    except OSError:
        pass
    return fallback


def _allowed(path: str, root: str) -> bool:
    """只允许根目录之内（含子目录），且不越界 ✓"""
    real = _norm(path)
    base = _norm(root)
    if not real or not base:
        return False
    if real == base:
        return True
    return real.startswith(base + os.sep)


def entries(path: str = '', root: str = '') -> Dict[str, Any]:
    """列一个目录（文件夹在前，名字排序 ✓）"""
    base_root = root_of(root)
    target = _norm(path) if path else base_root
    # 默认根目录（个人目录）→ 先把 indicators/ strategies/ 建出来，否则首次
    # 打开看到的是「空目录」，建完文件才冒出来（体验很差 ✗）
    try:
        if target == base_root == _norm(DEFAULT_ROOT):
            _pi.ensure_directories()
    except Exception:                                            # noqa: BLE001
        pass
    if not _allowed(target, base_root):
        return {'ok': False, 'error': '超出根目录范围', 'root': base_root,
                'path': target, 'items': []}
    if not os.path.isdir(target):
        return {'ok': False, 'error': '目录不存在', 'root': base_root,
                'path': target, 'items': []}
    items: List[Dict[str, Any]] = []
    try:
        names = sorted(os.listdir(target),
                       key=lambda name: (not os.path.isdir(
                           os.path.join(target, name)), name.lower()))
    except OSError as error:
        return {'ok': False, 'error': f'读取失败：{error!r}',
                'root': base_root, 'path': target, 'items': []}
    for name in names[:MAX_ENTRIES]:
        if name in ('.git', '__pycache__', '.DS_Store'):
            continue
        full = os.path.join(target, name)
        is_dir = os.path.isdir(full)
        try:
            stat = os.stat(full)
            size, mtime = int(stat.st_size), float(stat.st_mtime)
        except OSError:
            size, mtime = 0, 0.0
        items.append({
            'name': name, 'path': full, 'dir': is_dir,
            'py': (not is_dir) and name.endswith('.py'),
            #: 文本类文件（.py 之外还有 md / txt / json…）→ 编辑器能打开 ✓
            'text': (not is_dir) and _pi.is_text_file(name),
            'size': size, 'mtime': mtime,
            'editable': (not is_dir) and size <= _pi.MAX_SOURCE_BYTES,
        })
    return {'ok': True, 'root': base_root, 'path': target,
            'parent': '' if target == base_root else os.path.dirname(target),
            'items': items, 'truncated': len(items) >= MAX_ENTRIES}


def _unique(path: str) -> str:
    """重名 → `name_2.py` 那样往后排 ✓"""
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    for index in range(2, 1000):
        candidate = f'{stem}_{index}{ext}'
        if not os.path.exists(candidate):
            return candidate
    return f'{stem}_{int(time.time())}{ext}'


def operate(action: str, payload: Dict[str, Any],
            root: str = '') -> Dict[str, Any]:
    """右键操作：new_file / new_folder / rename / delete / copy / cut / paste ✓"""
    base_root = root_of(root)
    action = str(action or '').strip().lower()
    target = _norm(payload.get('path') or base_root)
    name = str(payload.get('name') or '').strip()

    if action in ('copy', 'cut'):
        if not _allowed(target, base_root) or not os.path.exists(target):
            return {'ok': False, 'error': '目标不存在'}
        _CLIPBOARD['path'] = target
        _CLIPBOARD['mode'] = action
        return {'ok': True, 'clipboard': dict(_CLIPBOARD)}

    if action == 'paste':
        source = _CLIPBOARD.get('path') or ''
        mode = _CLIPBOARD.get('mode') or 'copy'
        if not source or not os.path.exists(source):
            return {'ok': False, 'error': '剪贴板是空的'}
        folder = target if os.path.isdir(target) else os.path.dirname(target)
        if not _allowed(folder, base_root):
            return {'ok': False, 'error': '超出根目录范围'}
        dest = _unique(os.path.join(folder, os.path.basename(source)))
        try:
            if os.path.isdir(source):
                shutil.copytree(source, dest)
            else:
                shutil.copy2(source, dest)
            if mode == 'cut':
                try:
                    if os.path.isdir(source):
                        shutil.rmtree(source)
                    else:
                        os.remove(source)
                except OSError:
                    pass
                _CLIPBOARD.clear()
        except OSError as error:
            return {'ok': False, 'error': f'粘贴失败：{error!r}'}
        return {'ok': True, 'path': dest, 'clipboard': dict(_CLIPBOARD)}

    if not name and action != 'delete':
        return {'ok': False, 'error': '名字不能为空'}
    bad = ('\\', '/', ':', '*', '?', '"', '<', '>', '|')
    if any(char in name for char in bad) or name in ('.', '..'):
        return {'ok': False, 'error': '名字不合法'}

    if action == 'new_file':
        folder = target if os.path.isdir(target) else os.path.dirname(target)
        if not _allowed(folder, base_root):
            return {'ok': False, 'error': '超出根目录范围'}
        path = _unique(os.path.join(folder, name))
        try:
            os.makedirs(folder, exist_ok=True)
            with open(path, 'x', encoding='utf-8', newline='\n') as handle:
                handle.write('')
        except OSError as error:
            return {'ok': False, 'error': f'新建失败：{error!r}'}
        return {'ok': True, 'path': path}

    if action == 'new_folder':
        folder = target if os.path.isdir(target) else os.path.dirname(target)
        if not _allowed(folder, base_root):
            return {'ok': False, 'error': '超出根目录范围'}
        path = _unique(os.path.join(folder, name))
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as error:
            return {'ok': False, 'error': f'新建失败：{error!r}'}
        return {'ok': True, 'path': path}

    if action == 'rename':
        if not _allowed(target, base_root) or not os.path.exists(target):
            return {'ok': False, 'error': '目标不存在'}
        folder = os.path.dirname(target)
        dest = os.path.join(folder, name)
        if _norm(dest) == target:
            return {'ok': True, 'path': target}
        if os.path.exists(dest):
            return {'ok': False, 'error': '同名文件已存在'}
        try:
            os.rename(target, dest)
        except OSError as error:
            return {'ok': False, 'error': f'重命名失败：{error!r}'}
        return {'ok': True, 'path': dest, 'old': target}

    if action == 'delete':
        if not _allowed(target, base_root) or not os.path.exists(target):
            return {'ok': False, 'error': '目标不存在'}
        if _norm(target) == base_root:
            return {'ok': False, 'error': '不能删除根目录'}
        try:
            if os.path.isdir(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
        except OSError as error:
            return {'ok': False, 'error': f'删除失败：{error!r}'}
        return {'ok': True, 'path': target}

    return {'ok': False, 'error': f'未知操作 {action!r}'}


def personal_dirs() -> Dict[str, List[str]]:
    """登记过的个人目录（指标 / 策略）—— 「刷新指标策略」按钮要靠它判断 ✓"""
    out: Dict[str, List[str]] = {'indicator': [], 'strategy': []}
    for entry in _pi.directories():
        kind = 'strategy' if entry.get('kind') == 'strategy' else 'indicator'
        out[kind].append(_norm(entry.get('path') or ''))
    return out


def is_personal(path: str) -> Optional[str]:
    """这个目录是不是「我的脚本 / 我的策略」登记目录 → 返回 kind ✓"""
    real = _norm(path)
    for kind, dirs in personal_dirs().items():
        if any(real == item for item in dirs if item):
            return kind
    return None


def format_python(text: str) -> Dict[str, Any]:
    """格式化源码：优先 black / yapf，都没有就做**保守清理** ✓

    保守清理 = 去行尾空白 + Tab 换 4 空格 + 结尾补一个换行（不改语义）。
    """
    source = str(text or '')
    for tool in ('black', 'ruff', 'yapf'):
        try:
            if tool == 'black':
                import black
                return {'ok': True, 'text': black.format_str(
                    source, mode=black.Mode()), 'tool': 'black'}
            if tool == 'ruff':
                # `ruff format`（black 兼容风格，装了就优先用它，比 black 快 ✓）
                import subprocess
                import shutil
                exe = shutil.which('ruff')
                if not exe:
                    continue
                out = subprocess.run(
                    [exe, 'format', '--stdin-filename', 'editor.py', '-'],
                    input=source, capture_output=True, text=True,
                    timeout=20, encoding='utf-8', errors='replace',
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if out.returncode == 0 and (out.stdout or '').strip():
                    return {'ok': True, 'text': out.stdout, 'tool': 'ruff'}
                continue
            import yapf  # noqa: F401
            from yapf.yapflib.yapf_api import FormatCode
            formatted, _changed = FormatCode(source)
            return {'ok': True, 'text': formatted, 'tool': 'yapf'}
        except Exception:                                        # noqa: BLE001
            continue
    cleaned = []
    for line in source.splitlines():
        cleaned.append(line.expandtabs(4).rstrip())
    result = '\n'.join(cleaned).rstrip('\n') + '\n'
    return {'ok': True, 'text': result, 'tool': 'basic'}
