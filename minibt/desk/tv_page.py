"""minibt desk「指标和策略」页面后端（仿 TradingView 的 Indicators & Strategies ✓）

只针对 **minibt 自带的 TradingView 指标**（指标目录里 `tv:<类名>` 那一组）：

* **卡片列表**：分组（趋势 / 震荡 / 成交量…）/ 关键词 / 收藏 过滤 + 分页（每页 20）；
* **卡片缩略图**：本地没有就**现场生成 SVG**（`~/.minibt/desk/tv_cards/<key>.svg`），
  用户也可以在详情页点「截图」重新生成（和 miniqt 一样 ✓）；
* **详情**：指标简介（docstring）、**源码**（`inspect.getsource`，只读展示）、
  参数、图表（K 线 + 该指标，pylightcharts 的 `HeadlessChart` + 左侧画线工具箱 ✓）、
  收藏（⭐）、评论区（本地 JSON 落盘，先把框架搭起来 ✓）；
* 图表给两种壳：浏览器（`/tv_chart?key=`）与 Qt（`file://` 临时文件）✓
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional

#: 一页卡片数（仿 TradingView 一页 20 个 ✓）
TV_PAGE_SIZE = 24

#: 触发图标的 key 前缀
TV_PREFIX = 'tv:'

#: 缩略图缓存目录
CARD_DIR = os.path.join(os.path.expanduser('~'), '.minibt', 'desk',
                        'tv_cards')

#: 收藏 / 评论（本地落盘）
STATE_FILE = os.path.join(os.path.expanduser('~'), '.minibt', 'desk',
                          'tv_state.json')

#: 缩略图**计算**用多少根（取末尾；有些指标要更长的预热期 ✓）
THUMB_BARS = 400
#: 缩略图实际**画**多少根
THUMB_DRAW_BARS = 150
#: 详情页图表用多少根
CHART_BARS = 600

_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {'items': None, 'stamp': None}


# --------------------------------------------------------------------- 目录
def _safe_key(key: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in '-_.' else '_'
                   for ch in str(key or ''))[:120]


def _docstring(cls) -> str:
    """类的 docstring → 纯文本摘要（去掉 markdown 记号 / 空行 ✓）"""
    try:
        text = inspect.cleandoc(cls.__doc__ or '')
    except Exception:                                            # noqa: BLE001
        return ''
    lines: List[str] = []
    for line in text.splitlines():
        line = line.strip().lstrip('#').strip()
        if not line:
            if lines:
                break
            continue
        lines.append(line)
    return ' '.join(lines)


def _source(cls) -> str:
    try:
        return inspect.getsource(cls)
    except Exception:                                            # noqa: BLE001
        return ''


def _params(cls) -> Dict[str, Any]:
    try:
        raw = dict(getattr(cls, 'params', {}) or {})
    except Exception:                                            # noqa: BLE001
        return {}
    out: Dict[str, Any] = {}
    for key, value in raw.items():
        if key in ('lines', 'overlap', 'isplot', 'category', 'name'):
            continue
        if isinstance(value, (int, float, bool, str)):
            out[str(key)] = value
    return out


def catalog() -> List[Dict[str, Any]]:
    """指标目录里的 `tv:` 组（带简介 / 源码 / 参数 ✓，进程内缓存）"""
    from . import indicator_catalog as _cat
    stamp = ''
    try:
        stamp = str(_cat.schema_stamp())
    except Exception:                                            # noqa: BLE001
        stamp = ''
    with _LOCK:
        if _CACHE['items'] is not None and _CACHE['stamp'] == stamp:
            return _CACHE['items']
    items: List[Dict[str, Any]] = []
    for entry in _cat.catalog():
        key = str(entry.get('key') or '')
        if not key.startswith(TV_PREFIX):
            continue
        cls = entry.get('cls') or entry.get('class') or None
        if cls is None:
            cls = _lookup_class(key)
        name = str(entry.get('name') or key[len(TV_PREFIX):])
        items.append({
            'key': key,
            'name': name,
            'group': str(entry.get('group') or '指标'),
            'desc': _docstring(cls) if cls is not None else '',
            'params': _params(cls) if cls is not None else {},
            # ★ 源码**不要在这里取**：`inspect.getsource` 每个类 ~0.2s，
            #   114 个指标就是 20 多秒（列表卡死 ✗）→ 详情页才读 ✓
            'source': '',
            'overlap': bool(entry.get('overlap')),
            '_cls': cls,
        })
    items.sort(key=lambda row: (row['group'], row['name'].lower()))
    with _LOCK:
        _CACHE['items'] = items
        _CACHE['stamp'] = stamp
    return items


_CLASS_CACHE: Dict[str, Any] = {}


def _lookup_class(key: str):
    """`tv:<类名>` → `minibt.indicators.tradingview` 里的类 ✓"""
    name = str(key or '')[len(TV_PREFIX):]
    if not name:
        return None
    if name in _CLASS_CACHE:
        return _CLASS_CACHE[name]
    cls = None
    try:
        from ..indicators import tradingview as _tv
        cls = getattr(_tv, name, None)
        if not isinstance(cls, type):
            cls = None
    except Exception:                                            # noqa: BLE001
        cls = None
    _CLASS_CACHE[name] = cls
    return cls


# --------------------------------------------------------------- 收藏/评论
def load_state() -> Dict[str, Any]:
    try:
        with open(STATE_FILE, encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault('stars', [])
    data.setdefault('comments', {})
    return data


def save_state(data: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
    except OSError as error:                                     # noqa: BLE001
        print(f'[desk] 指标和策略：保存状态失败 {error!r}')


# --------------------------------------------------------------- 卡片列表
# ------------------------------------------------------- 用户自己的分组
def load_groups() -> List[Dict[str, str]]:
    """已添加的文件夹（不存在 / 不是目录的自动忽略 ✓）"""
    try:
        with open(GROUPS_FILE, 'r', encoding='utf-8') as handle:
            rows = json.load(handle)
    except (OSError, ValueError):
        rows = []
    out: List[Dict[str, str]] = []
    for row in rows if isinstance(rows, list) else []:
        path = str((row or {}).get('path') or '')
        if not path or not os.path.isdir(path):
            continue
        name = str((row or {}).get('name') or '').strip()
        name = name or os.path.basename(path.rstrip('\\/')) or path
        out.append({'path': os.path.abspath(path), 'name': name})
    return out


def save_groups(rows: List[Dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(GROUPS_FILE), exist_ok=True)
    with open(GROUPS_FILE, 'w', encoding='utf-8') as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)


#: 系统默认分组的 key（= 名称；用户分组都是绝对路径，不会撞 ✓）
BUILTIN_GROUP = 'TradingView'


def group_choices() -> List[Dict[str, Any]]:
    """下拉框的分组：`TradingView` + 用户添加的文件夹 ✓"""
    out: List[Dict[str, Any]] = [{
        'key': BUILTIN_GROUP, 'label': BUILTIN_GROUP, 'user': False,
        'builtin': True, 'count': len(catalog()),
    }]
    for row in load_groups():
        out.append({
            'key': row['path'], 'label': row['name'], 'user': True,
            'count': len(_user_entries(row['path'])),
        })
    return out


def add_group_payload(payload: Optional[dict] = None) -> Dict[str, Any]:
    """「添加指标和策略」→ 记住这个文件夹（分组名 = 文件夹名 ✓）"""
    payload = payload or {}
    path = os.path.abspath(os.path.expanduser(
        str(payload.get('path') or '').strip()))
    if not path or not os.path.isdir(path):
        return {'ok': False, 'reason': '请选择一个文件夹',
                'groups': group_choices()}
    rows = load_groups()
    name = (str(payload.get('name') or '').strip()
            or os.path.basename(path.rstrip('/' + chr(92))) or path)
    if name == BUILTIN_GROUP:
        name = f'{name} (2)'      # 别和系统默认分组重名 ✓
    rows = [row for row in rows if row['path'] != path]
    rows.append({'path': path, 'name': name})
    try:
        save_groups(rows)
    except OSError as error:                                     # noqa: BLE001
        return {'ok': False, 'reason': f'保存分组失败：{error}',
                'groups': group_choices()}
    return {'ok': True, 'path': path, 'name': name,
            'groups': group_choices(),
            'count': len(_user_entries(path))}


def remove_group_payload(payload: Optional[dict] = None) -> Dict[str, Any]:
    """「删除指标和策略」→ 从分组列表里去掉（文件不动 ✓）"""
    payload = payload or {}
    path = str(payload.get('path') or '')
    if not path or path == BUILTIN_GROUP:
        return {'ok': False, 'reason': 'TradingView 是系统默认分组，不能删除',
                'groups': group_choices()}
    rows = load_groups()
    kept = [row for row in rows if row['path'] != os.path.abspath(path)]
    try:
        save_groups(kept)
    except OSError as error:                                     # noqa: BLE001
        return {'ok': False, 'reason': f'保存分组失败：{error}',
                'groups': group_choices()}
    return {'ok': True, 'path': path, 'removed': len(rows) - len(kept),
            'groups': group_choices()}


def _docstring_of_path(path: str) -> str:
    """文件的模块 / 类 docstring 第一行（不执行代码 ✓）"""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            text = handle.read(20000)
    except OSError:
        return ''
    match = re.search(r'(?:^|\n)\s*(?:class|def)\s+\w+[^\n]*:\s*\n'
                      r'\s*(?:"""|\'\'\')\s*([^"\n]*)', text)
    if match:
        return match.group(1).strip()[:200]
    match = re.search(r'(?:"""|\'\'\')\s*([^"\n]*)', text)
    return match.group(1).strip()[:200] if match else ''


def _params_count(path: str) -> int:
    """用户脚本里 `params` 的**元素个数**（没有就是 0 ✓）

    支持这几种写法（tutorials 里都有）：
      * `params = dict(A=1, B=2)`
      * `params = {"A": 1, "B": 2}`
      * `params = SomeParams(A=1, B=2)`（自定义类 → 数关键字参数）
      * `self.params.A = 1` / `self.params.B = 2`（数不同的名字）
    只读源码（AST），不 import，避免副作用 ✓
    """
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            text = handle.read(200_000)
    except OSError:
        return 0
    import ast
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return 0
    names: Dict[str, None] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                # ---- self.params.A = 1 ----
                if (isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Attribute)
                        and target.value.attr == 'params'):
                    names[target.attr] = None
                    continue
                # ---- params = ... ----
                if not (isinstance(target, ast.Name)
                        and target.id == 'params'):
                    continue
                value = node.value
                if isinstance(value, ast.Dict):
                    for key in value.keys:
                        label = getattr(key, 'value', None)
                        if isinstance(label, str):
                            names[label] = None
                elif isinstance(value, ast.Call):
                    for keyword in value.keywords:
                        if keyword.arg:
                            names[keyword.arg] = None
                    for argument in value.args:
                        if isinstance(argument, ast.Constant) and isinstance(
                                argument.value, str):
                            names[argument.value] = None
    return len(names)


def _file_kind(path: str) -> str:
    """看类名 / 基类判断是策略还是指标（不 import，避免副作用 ✓）"""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            text = handle.read(60000)
    except OSError:
        return 'indicator'
    if re.search(r'class\s+\w+\s*\([^)]*Strategy[^)]*\)', text):
        return 'strategy'
    if re.search(r'class\s+\w+\s*\([^)]*BtIndicator[^)]*\)', text):
        return 'indicator'
    return 'strategy' if re.search(r'\bStrategy\b', text) else 'indicator'


def _user_entries(root: str) -> List[Dict[str, Any]]:
    """递归扫这个文件夹里的 .py（含子文件夹 ✓）"""
    out: List[Dict[str, Any]] = []
    root = os.path.abspath(root)
    for folder, _dirs, files in os.walk(root):
        for name in sorted(files):
            if not name.lower().endswith('.py') or name.startswith('_'):
                continue
            path = os.path.join(folder, name)
            if os.path.getsize(path) > 512 * 1024:
                continue
            try:
                stamp = int(os.path.getmtime(path))
            except OSError:
                stamp = 0
            out.append({
                'key': FILE_PREFIX + path,
                'name': os.path.splitext(name)[0],
                'group': os.path.basename(root.rstrip('\\/')) or root,
                'desc': _docstring_of_path(path),
                'params': _params_count(path), 'overlap': False,
                'kind': _file_kind(path),
                'path': path,
                'rel': os.path.relpath(path, root).replace('\\', '/'),
                'mtime': stamp,
                'user': True,
            })
    out.sort(key=lambda row: (-int(row.get('mtime') or 0),
                              str(row['name']).lower()))
    return out


def _user_row(entry: Dict[str, Any], stars: set, comments: dict) -> Dict[str, Any]:
    return {
        'key': entry['key'], 'name': entry['name'], 'group': entry['group'],
        'desc': entry['desc'][:200],
        'params': int(entry.get('params') or 0), 'overlap': False,
        'kind': entry.get('kind') or 'indicator',
        'star': entry['key'] in stars,
        'comments': len(comments.get(entry['key']) or []),
        # ★ 用户卡片也自动生成缩略图（指标画线 / 策略只画 K 线 ✓）
        'card': _existing_card(entry['key']), 'user': True,
        'path': entry['path'],
        'rel': entry.get('rel') or entry['name'],
    }


def _builtin_rows(stars: set, comments: dict) -> List[Dict[str, Any]]:
    """TradingView（系统默认分组）的卡片行 ✓"""
    rows: List[Dict[str, Any]] = []
    for item in catalog():
        rows.append({
            'key': item['key'],
            'name': item['name'],
            'group': item['group'],
            'desc': item['desc'][:200],
            'params': len(item['params']),
            'overlap': item['overlap'],
            'kind': 'indicator',
            'star': item['key'] in stars,
            'comments': len(comments.get(item['key']) or []),
            # ★ 只给**已存在**的缩略图路径：没有就空着，前端按需
            #   `tv_snapshot` 现场生成（一次 20 张、渐进加载，列表秒开 ✓）
            'card': _existing_card(item['key']),
            'user': False,
        })
    return rows


def list_payload(payload: Optional[dict] = None) -> Dict[str, Any]:
    """卡片列表（关键词 / 分组 / 收藏 tab / 分页 ✓）

    `group` 取值：
      * `''`            → **全部分组**（TradingView + 用户添加的文件夹，合并分页）
      * `'TradingView'` → 系统默认分组
      * `<绝对路径>`     → 用户添加的文件夹（递归扫 .py）
    """
    payload = payload or {}
    query = str(payload.get('query') or '').strip().lower()
    star_only = bool(payload.get('star')) or str(
        payload.get('tab') or '') == 'star'
    group = str(payload.get('group') or '')
    try:
        page = max(1, int(payload.get('page') or 1))
    except (TypeError, ValueError):
        page = 1
    try:
        size = max(1, min(100, int(payload.get('size') or TV_PAGE_SIZE)))
    except (TypeError, ValueError):
        size = TV_PAGE_SIZE
    state = load_state()
    stars = set(str(item) for item in state.get('stars') or [])
    comments = state.get('comments') or {}

    rows: List[Dict[str, Any]] = []
    if group == BUILTIN_GROUP:
        rows = _builtin_rows(stars, comments)
        group_label = BUILTIN_GROUP
    elif group:
        # ★ 用户自己的文件夹（递归扫所有 .py ✓）
        known = {row['path'] for row in load_groups()}
        path = os.path.abspath(os.path.expanduser(group))
        entries = _user_entries(path) if path in known else []
        for entry in entries:
            rows.append(_user_row(entry, stars, comments))
        group_label = (os.path.basename(path.rstrip('/' + chr(92)))
                       or path)
    else:
        # ★ 「全部分组」= TradingView + 所有用户分组（一起分页 ✓）
        group_label = '全部分组'
        rows = _builtin_rows(stars, comments)
        for row in load_groups():
            for entry in _user_entries(row['path']):
                rows.append(_user_row(entry, stars, comments))
    if star_only:
        # ★ 收藏页 = 我收藏过、并且**现在仍然在**默认 / 用户分组里的条目
        #   （收藏过的文件所在分组被删掉 → 扫不到 → 不再显示 ✓ 需求 5）
        if group:
            rows = _builtin_rows(stars, comments) if group == BUILTIN_GROUP \
                else rows
            if group != BUILTIN_GROUP:
                known = {row['path'] for row in load_groups()}
                path = os.path.abspath(os.path.expanduser(group))
                rows = [_user_row(entry, stars, comments)
                        for entry in (_user_entries(path) if path in known
                                      else [])]
            else:
                rows = _builtin_rows(stars, comments)
        else:
            rows = _builtin_rows(stars, comments)
            for row in load_groups():
                rows += [_user_row(entry, stars, comments)
                         for entry in _user_entries(row['path'])]
        rows = [row for row in rows if row['star']]
    if query:
        rows = [row for row in rows
                if query in ' '.join([
                    str(row.get('name') or ''), str(row.get('group') or ''),
                    str(row.get('desc') or ''), str(row.get('rel') or ''),
                ]).lower()]
    # ★ 「热门」排序：我收藏过的 > 评论多的 > 名字（稳定、可复现 ✓）
    rows.sort(key=lambda row: (not row['star'], -row['comments'],
                               row['name'].lower()))
    total = len(rows)
    pages = max(1, (total + size - 1) // size)
    page = min(page, pages)
    start = (page - 1) * size
    return {'items': rows[start:start + size], 'total': total, 'page': page,
            'pages': pages, 'size': size,
            'groups': group_choices(), 'group': group,
            'groupLabel': group_label, 'star': star_only}


def reload_payload(payload: Optional[dict] = None,
                   progress=None) -> Dict[str, Any]:
    """「重载图表」：把当前这一页的卡片**重算 + 重新截图** ✓

    先删掉旧封面（SVG / PNG），再逐张重新生成；`progress(key, path)` 每完成
    一张回调一次（desk 会顺手把新图推给前端，卡片立刻变 ✓）。
    """
    payload = payload or {}
    theme = str(payload.get('theme') or 'light')
    data = list_payload({**payload, 'theme': theme})
    rows = data.get('items') or []
    safe_keys = []
    for row in rows:
        key = str(row.get('key') or '')
        if not key:
            continue
        safe = _safe_key(key)
        if not safe:
            continue
        # 删旧封面（png 优先，其次 svg；两个主题都删 → 真的重算 ✓）
        for name in os.listdir(CARD_DIR) if os.path.isdir(CARD_DIR) else []:
            if not name.startswith(safe):
                continue
            if name.endswith('.svg') or name.endswith('.png'):
                try:
                    os.remove(os.path.join(CARD_DIR, name))
                except OSError:
                    pass
        safe_keys.append(key)
    done = 0
    failed = []
    for key in safe_keys:
        try:
            url = snapshot_data_url(key, theme)
        except Exception:                                        # noqa: BLE001
            url = ''
        if not url:
            failed.append(key)
            continue
        done += 1
        if callable(progress):
            try:
                progress(key, url)
            except Exception:                                    # noqa: BLE001
                pass
    return {'ok': True, 'total': len(safe_keys), 'done': done,
            'failed': failed, 'theme': theme}


def reload_card_payload(payload: Optional[dict] = None,
                       progress=None) -> Dict[str, Any]:
    """「重载图表」（单张卡片）：删掉它的封面后**按主题各生成一套** ✓"""
    payload = payload or {}
    key = str(payload.get('key') or '')
    if not key:
        return {'ok': False, 'reason': '没有指标 key'}
    safe = _safe_key(key)
    if not safe:
        return {'ok': False, 'reason': 'key 不合法'}
    for name in (os.listdir(CARD_DIR) if os.path.isdir(CARD_DIR) else []):
        if name.startswith(safe) and (name.endswith('.svg')
                                      or name.endswith('.png')):
            try:
                os.remove(os.path.join(CARD_DIR, name))
            except OSError:
                pass
    made: Dict[str, str] = {}
    for theme in ('light', 'dark'):
        try:
            url = snapshot_data_url(key, theme)
        except Exception:                                        # noqa: BLE001
            url = ''
        if not url:
            continue
        made[theme] = url
        if callable(progress):
            try:
                progress(key, url, theme)
            except Exception:                                    # noqa: BLE001
                pass
    return {'ok': bool(made), 'key': key, 'themes': sorted(made),
            'failed': [] if made else [key]}


def star_payload(payload: Optional[dict] = None) -> Dict[str, Any]:
    payload = payload or {}
    key = str(payload.get('key') or '')
    on = bool(payload.get('on'))
    if not key:
        return {'ok': False}
    state = load_state()
    if payload.get('query'):
        # ★ 只读查询（图表页打开时把 ⭐ 状态同步过来 ✓）
        stars = set(str(item) for item in state.get('stars') or [])
        return {'ok': True, 'key': key, 'on': key in stars,
                'stars': len(stars), 'query': True}
    stars = [str(item) for item in state.get('stars') or []]
    if on and key not in stars:
        stars.append(key)
    elif not on and key in stars:
        stars.remove(key)
    state['stars'] = stars
    save_state(state)
    return {'ok': True, 'key': key, 'on': on, 'stars': len(stars)}


def comment_payload(payload: Optional[dict] = None) -> Dict[str, Any]:
    """评论区：新增 / 删除（`action='add' | 'remove'`）✓"""
    payload = payload or {}
    key = str(payload.get('key') or '')
    action = str(payload.get('action') or 'add')
    state = load_state()
    comments = state.get('comments') or {}
    rows = list(comments.get(key) or [])
    if action == 'remove':
        cid = str(payload.get('id') or '')
        rows = [row for row in rows if str(row.get('id')) != cid]
    else:
        text = str(payload.get('text') or '').strip()
        if not text:
            return {'ok': False, 'reason': '评论不能为空'}
        rows.append({'id': hashlib.sha1(
            f'{time.time()}-{text}'.encode('utf-8')).hexdigest()[:10],
            'text': text[:500], 'at': time.strftime('%Y-%m-%d %H:%M')})
    comments[key] = rows
    state['comments'] = comments
    save_state(state)
    # 回给前端的也按「新的在前」排序（和详情页一致 ✓）
    return {'ok': True, 'key': key, 'comments': list(reversed(rows))}


def detail_payload(payload: Optional[dict] = None) -> Dict[str, Any]:
    payload = payload or {}
    key = str(payload.get('key') or '')
    if key.startswith(FILE_PREFIX):
        # 用户自己的文件：源码原样读出来（不加头 ✓）
        path = key[len(FILE_PREFIX):]
        if not os.path.isfile(path):
            return {'ok': False, 'reason': f'文件不存在：{path}'}
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                text = handle.read()
        except OSError as error:                                  # noqa: BLE001
            return {'ok': False, 'reason': str(error)}
        state = load_state()
        stars = set(str(row) for row in state.get('stars') or [])
        return {
            'ok': True, 'key': key, 'name': os.path.splitext(
                os.path.basename(path))[0],
            'group': os.path.basename(os.path.dirname(path)),
            'desc': _docstring_of_path(path), 'source': text,
            'params': {}, 'overlap': False, 'kind': _file_kind(path),
            'star': key in stars, 'comments': [],
            'card': '', 'theme': str(payload.get('theme') or 'light'),
            'path': path, 'user': True,
        }
    item = next((row for row in catalog() if row['key'] == key), None)
    if item is None:
        return {'ok': False, 'reason': f'未知指标：{key}'}
    state = load_state()
    stars = set(str(row) for row in state.get('stars') or [])
    # ★ 评论**新的在前**（刚发的马上出现在第一条 ✓）
    comments = list(reversed((state.get('comments') or {}).get(key) or []))
    source = _source(item.get('_cls')) if item.get('_cls') is not None else ''
    return {
        'ok': True,
        'key': item['key'], 'name': item['name'], 'group': item['group'],
        'desc': item['desc'], 'source': source,
        'params': item['params'], 'overlap': item['overlap'],
        'star': key in stars, 'comments': comments,
        'card': snapshot_path(key),
        'theme': str(payload.get('theme') or 'light'),
        # 详情页「数据」下拉（LocalDatas 里能用的那几个 ✓）
        'symbols': available_symbols(),
        'symbol': str(payload.get('symbol') or 'test'),
    }


# ------------------------------------------------------------- 缩略图 / 图表
#: 用户自己添加的「指标和策略」文件夹（分组）
GROUPS_FILE = os.path.join(os.path.expanduser('~'), '.minibt', 'desk',
                           'tv_groups.json')
#: 用户分组的 key 前缀（`file:<绝对路径>` = 单个脚本 ✓）
FILE_PREFIX = 'file:'

#: 缩略图**格式版本**：SVG 里带 `<!-- minibt-thumb:N -->` 标记，
#: 老版本生成的缓存（比如还烘焙着「指标 / 策略」角标的那批）会自动失效、
#: 重新生成 —— 否则卡片上会出现「旧角标 + 新 HTML 角标」**双重标注** ✗
#: （用户实测 2026-11-03）
THUMB_VERSION = 2

_FRAME_CACHE: Dict[str, Any] = {'frame': None}
#: 每个数据集的 K 线缓存（详情页切数据不用重读 CSV ✓）
_SYMBOL_CACHE: Dict[str, Any] = {}


def available_symbols() -> List[str]:
    """详情页可切换的数据集（`LocalDatas` 里带 kline 的那几个 ✓）"""
    from .. import LocalDatas
    out: List[str] = []
    for name in ('test', 'l2609_60', 'pp2609_60'):
        if hasattr(LocalDatas, name):
            out.append(name)
    return out or ['test']


def _symbol_frame(symbol: str = ''):
    """取某个数据集的 K 线（带缓存；空了退回 `test` ✓）"""
    name = str(symbol or 'test')
    if name in _SYMBOL_CACHE:
        return _SYMBOL_CACHE[name]
    from .. import LocalDatas
    frame = None
    try:
        frame = getattr(getattr(LocalDatas, name), 'kline').pandas_object
    except Exception:                                            # noqa: BLE001
        frame = None
    if frame is None or getattr(frame, 'empty', True):
        frame = getattr(LocalDatas.test.kline, 'pandas_object', None)
    if frame is None or getattr(frame, 'empty', True):
        return None
    _SYMBOL_CACHE[name] = frame
    return frame


def _thumb_frame():
    """缩略图用的 K 线（`LocalDatas.test` 最近 THUMB_BARS 根，带缓存 ✓）"""
    if _FRAME_CACHE['frame'] is not None:
        return _FRAME_CACHE['frame']
    from .. import LocalDatas
    try:
        kline = LocalDatas.test.kline
        frame = getattr(kline, 'pandas_object', None)
    except Exception:                                            # noqa: BLE001
        frame = None
    if frame is None or getattr(frame, 'empty', True):
        return None
    frame = frame.tail(THUMB_BARS).reset_index(drop=True)
    _FRAME_CACHE['frame'] = frame
    return frame


def _compute(key: str, frame,
             params: Optional[dict] = None) -> List[Dict[str, Any]]:
    from . import indicator_catalog as _cat
    try:
        overrides = {key: dict(params or {})} if params else {}
        return _cat.compute(frame, [key], overrides,
                            limit=len(frame)) or []
    except Exception as error:                                   # noqa: BLE001
        print(f'[desk] 指标和策略：{key} 计算失败 {error!r}')
        return []


def _line_points(item: Dict[str, Any], times: List[Any]) -> List[List[float]]:
    index = {int(stamp): position for position, stamp in enumerate(times)}
    out: List[List[float]] = []
    for row in item.get('data') or []:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        try:
            stamp = int(row[0])
            value = float(row[1])
        except (TypeError, ValueError):
            continue
        position = index.get(stamp)
        if position is None or value != value:
            continue
        out.append([position, value])
    return out


def _fmt(value: float) -> str:
    if abs(value) >= 1e4:
        return f'{value:,.0f}'
    if abs(value) >= 100:
        return f'{value:.1f}'
    return f'{value:.2f}'


def _thumb_source(key: str) -> Dict[str, Any]:
    """缩略图信息：`{name, kind, user, path}`（支持 `tv:` / `file:` ✓）"""
    if key.startswith(FILE_PREFIX):
        path = key[len(FILE_PREFIX):]
        return {'name': os.path.splitext(os.path.basename(path))[0],
                'kind': _file_kind(path), 'user': True, 'path': path,
                'desc': _docstring_of_path(path)}
    item = next((row for row in catalog() if row['key'] == key), None)
    return {'name': (item or {}).get('name') or key,
            'kind': 'indicator', 'user': False, 'path': '',
            'desc': (item or {}).get('desc') or ''}


def _strategy_items(path: str, frame) -> List[Dict[str, Any]]:
    """用户策略：**跑一遍**（画线 / 信号），给缩略图用 ✓

    和「加到图表」同一条路（`strategy_overlay.run_overlay`，只在这个小 frame 上跑
    一次，不交易、不常驻）；出错就只画 K 线（不让卡片裂掉 ✓）
    """
    try:
        from . import personal as _pi
        from . import strategy_overlay as _overlay
        module = _pi._import_file(path)
        if module is None:
            return []
        found = _overlay.classes_of(module) or {}
        classes = found.get('strategy') or []
        if not classes:
            return []
        result = _overlay.run_overlay(
            frame, classes[0], symbol='test', cycle=60, replay=True)
        return list(result.get('items') or [])
    except Exception as error:                                   # noqa: BLE001
        print(f'[desk] 用户策略缩略图 {path} 失败 {error!r}')
        return []


def _thumb_items(key: str, frame) -> List[Dict[str, Any]]:
    """缩略图上的指标线（用户指标按路径算；策略跑一遍取线 ✓）"""
    info = _thumb_source(key)
    if not info.get('user'):
        return _compute(key, frame)
    if info.get('kind') == 'strategy':
        return _strategy_items(info['path'], frame)
    try:
        from . import personal as _pi
        return _pi.compute_path(frame, info['path'],
                                limit=max(1, len(frame))) or []
    except Exception as error:                                   # noqa: BLE001
        print(f'[desk] 用户指标缩略图 {info["path"]} 失败 {error!r}')
        return []


def thumbnail_svg(key: str, theme: str = 'light') -> str:
    """卡片缩略图（纯 SVG，不依赖浏览器 ✓）——K 线 + 指标线 + 角标"""
    source = _thumb_source(key)
    name = source['name']
    dark = str(theme or '').lower() == 'dark'
    bg = '#0f1115' if dark else '#ffffff'
    grid = 'rgba(255,255,255,.06)' if dark else 'rgba(0,0,0,.06)'
    text = '#d8d9db' if dark else '#131722'
    muted = '#8b93a1' if dark else '#787b86'
    up = '#ef5350' if dark else '#d93b3b'
    down = '#26a69a' if dark else '#1f9d55'
    width, height = 480, 320
    frame = _thumb_frame()
    if frame is None:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
                f'height="{height}"><rect width="100%" height="100%" '
                f'fill="{bg}"/></svg>')
    times = [int(value) for value in frame['datetime'].astype('int64') // 10 ** 9]
    closes = [float(value) for value in frame['close']]
    highs = [float(value) for value in frame['high']]
    lows = [float(value) for value in frame['low']]
    opens = [float(value) for value in frame['open']]
    # 只用**最后 THUMB_DRAW_BARS 根**画（前面的是预热数据 ✓）
    frame = frame.tail(THUMB_DRAW_BARS).reset_index(drop=True)
    times = [int(value) for value in
             frame['datetime'].astype('int64') // 10 ** 9]
    closes = [float(value) for value in frame['close']]
    highs = [float(value) for value in frame['high']]
    lows = [float(value) for value in frame['low']]
    opens = [float(value) for value in frame['open']]
    items = _thumb_items(key, frame)
    # ★ 指标样式跟图一致（用户 2026-11-02 反馈：自动缩略图"没截到样式"）：
    #   `color` / `lineWidth` / `lineStyle`（点 / 虚 / 长虚）/ `upColor`+`downColor`
    #   （柱状）/ `markers`（信号箭头）/ `spans`（参考线）/ `visible=false` 跳过 ✓
    overlay_kinds = ('line', 'hist', 'candles')
    overlays = [row for row in items
                if row.get('overlay') and row.get('kind') in overlay_kinds
                and row.get('visible') is not False]
    subs = [row for row in items
            if not row.get('overlay') and row.get('kind') in ('line', 'hist')
            and row.get('visible') is not False]
    markers = [row for row in items if row.get('kind') == 'marker'
               and row.get('visible') is not False]
    spans = [row for row in items if row.get('kind') == 'span'
             and row.get('visible') is not False]
    price_top, price_bottom = 34, height - (88 if subs else 26)
    base_low, base_high = min(lows), max(highs)
    span = (base_high - base_low) or 1.0
    step = (width - 24) / max(1, len(closes))

    def px(position: float) -> float:
        return 12 + (position + 0.5) * step

    def py(value: float) -> float:
        return price_bottom - (value - base_low) / span * (price_bottom - price_top)

    def dash_of(style) -> str:
        """LWC 的 LineStyle → SVG dasharray（0 实线 / 1 点 / 2 虚 / 3 长虚 ✓）"""
        try:
            value = int(style or 0)
        except (TypeError, ValueError):
            value = 0
        return {1: '2 3', 2: '6 4', 3: '14 6'}.get(value, '')

    def width_of(row) -> float:
        try:
            value = float(row.get('lineWidth') or 0)
        except (TypeError, ValueError):
            value = 0.0
        return max(0.8, min(3.0, value or 1.2))

    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">'
        f'<!-- minibt-thumb:{THUMB_VERSION} -->',
        f'<rect width="100%" height="100%" fill="{bg}"/>',
    ]
    for ratio in (0.25, 0.5, 0.75):
        y = price_top + (price_bottom - price_top) * ratio
        parts.append(f'<line x1="12" y1="{y:.1f}" x2="{width - 12}" '
                     f'y2="{y:.1f}" stroke="{grid}" stroke-width="1"/>')
    # K 线（细柱 + 影线）
    body = max(1.0, step * 0.62)
    for index, close in enumerate(closes):
        x = px(index)
        top = py(max(opens[index], close))
        bottom = py(min(opens[index], close))
        colour = up if close >= opens[index] else down
        parts.append(f'<line x1="{x:.1f}" y1="{py(highs[index]):.1f}" '
                     f'x2="{x:.1f}" y2="{py(lows[index]):.1f}" '
                     f'stroke="{colour}" stroke-width="1"/>')
        parts.append(f'<rect x="{x - body / 2:.1f}" y="{top:.1f}" '
                     f'width="{body:.1f}" '
                     f'height="{max(1.0, bottom - top):.1f}" fill="{colour}"/>')
    palette = ['#2196f3', '#ff9800', '#9c27b0', '#00bcd4', '#e91e63']
    # 主图叠加线（价格范围把它们自己的值也算进去 ✓）
    for order, row in enumerate(overlays[:4]):
        if row.get('kind') == 'hist':
            continue                       # 主图柱状（罕见）由下面副图画法兜底 ✓
        points = _line_points(row, times)
        if not points:
            continue
        values = [value for _, value in points]
        low, high = min(values), max(values)
        if low < base_low or high > base_high:
            low_all, high_all = min(base_low, low), max(base_high, high)
            scale_span = (high_all - low_all) or 1.0
            to_y = lambda value, low_all=low_all, scale_span=scale_span: (
                price_bottom - (value - low_all) / scale_span
                * (price_bottom - price_top))
        else:
            to_y = py
        path = ' '.join(f'{px(position):.1f},{to_y(value):.1f}'
                        for position, value in points)
        dash = dash_of(row.get('lineStyle'))
        parts.append(
            f'<polyline points="{path}" fill="none" '
            f'stroke="{_escape(row.get("color") or palette[order])}" '
            f'stroke-width="{width_of(row):.2f}" opacity=".95"'
            + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')
    # 副图（自己一段比例；线 / 柱状都按样式画 ✓）
    if subs:
        sub_top = price_bottom + 12
        sub_bottom = height - 26
        for order, row in enumerate(subs[:3]):
            points = _line_points(row, times)
            if not points:
                continue
            values = [value for _, value in points]
            low, high = min(values), max(values)
            if row.get('kind') == 'hist':
                base = row.get('base')
                try:
                    base = float(base)
                except (TypeError, ValueError):
                    base = 0.0
                low, high = min(low, base), max(high, base)
            span2 = (high - low) or 1.0

            def sub_y(value: float, low=low, span2=span2) -> float:
                return (sub_bottom
                        - (value - low) / span2 * (sub_bottom - sub_top))

            colour = _escape(row.get('color') or palette[order])
            if row.get('kind') == 'hist':
                # 柱状：涨 / 跌各用自己的颜色（`upColor` / `downColor` ✓）
                up_colour = _escape(row.get('upColor') or colour)
                down_colour = _escape(row.get('downColor') or colour)
                zero = sub_y(base)
                bar = max(1.0, step * 0.55)
                for position, value in points:
                    top = sub_y(max(value, base))
                    bottom = sub_y(min(value, base))
                    parts.append(
                        f'<rect x="{px(position) - bar / 2:.1f}" '
                        f'y="{top:.1f}" width="{bar:.1f}" '
                        f'height="{max(1.0, bottom - top):.1f}" '
                        f'fill="{up_colour if value >= base else down_colour}"'
                        f' opacity=".9"/>')
                if base:
                    parts.append(
                        f'<line x1="12" y1="{zero:.1f}" x2="{width - 12}" '
                        f'y2="{zero:.1f}" stroke="{grid}" stroke-width="1"/>')
                continue
            path = ' '.join(f'{px(position):.1f},{sub_y(value):.1f}'
                            for position, value in points)
            dash = dash_of(row.get('lineStyle'))
            parts.append(
                f'<polyline points="{path}" fill="none" stroke="{colour}" '
                f'stroke-width="{width_of(row):.2f}" opacity=".9"'
                + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')
        parts.append(f'<line x1="12" y1="{price_bottom + 6}" '
                     f'x2="{width - 12}" y2="{price_bottom + 6}" '
                     f'stroke="{grid}" stroke-width="1"/>')
    # 信号箭头（买 / 卖）：和图上一样按 marker 的颜色 / 方向画小三角 ✓
    index_by_time = {int(stamp): position
                     for position, stamp in enumerate(times)}
    for row in markers[:4]:
        for marker in (row.get('markers') or [])[:80]:
            try:
                stamp = int(marker.get('time'))
                price = float(marker.get('price'))
            except (TypeError, ValueError):
                continue
            position = index_by_time.get(stamp)
            if position is None:
                continue
            glyph = str(marker.get('glyph') or '')
            buy = marker.get('buy')
            if buy is None:
                buy = glyph.endswith('up')
            x = px(position)
            y = py(price)
            colour = _escape(marker.get('color') or row.get('color') or up)
            size = 4.0
            if buy:
                points_attr = (f'{x:.1f},{y - size:.1f} {x - size:.1f},'
                               f'{y + size:.1f} {x + size:.1f},{y + size:.1f}')
            else:
                points_attr = (f'{x:.1f},{y + size:.1f} {x - size:.1f},'
                               f'{y - size:.1f} {x + size:.1f},{y - size:.1f}')
            parts.append(f'<polygon points="{points_attr}" fill="{colour}" '
                         f'opacity=".9"/>')
    # 参考线（`spanstyle`）✓
    for row in spans[:4]:
        for item in (row.get('spans') or [])[:6]:
            try:
                price = float(item.get('price'))
            except (TypeError, ValueError):
                continue
            if not (base_low <= price <= base_high):
                continue
            dash = dash_of(item.get('lineStyle'))
            parts.append(
                f'<line x1="12" y1="{py(price):.1f}" x2="{width - 12}" '
                f'y2="{py(price):.1f}" opacity=".6" '
                f'stroke="{_escape(item.get("color") or muted)}" '
                f'stroke-width="1"'
                + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')
    # 名称（右上角的「指标 / 策略」标记改由前端 HTML 画 —— 手动截图把封面换成
    # PNG 后也要有标记 ✓；这里把类型写进页脚，信息不丢）
    tag = '策略' if source.get('kind') == 'strategy' else '指标'
    if source.get('user'):
        tag = f'我的{tag}'      # 用户自己的标「我的」（页脚里也带上 ✓）
    parts.append(f'<text x="14" y="21" fill="{text}" font-size="13" '
                 f'font-family="sans-serif">{_escape(name)}</text>')
    footer = ('我的指标' if source.get('user') else 'TradingView')
    if source.get('user'):
        footer = source.get('path', '').replace(chr(92), '/').rsplit('/', 1)[-1]
    parts.append(f'<text x="14" y="{height - 8}" fill="{muted}" '
                 f'font-size="10" font-family="sans-serif">'
                 f'{_escape(footer)} · {_escape(tag)} · '
                 f'{len(closes)} 根 · {_fmt(base_low)}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def _escape(text: str) -> str:
    return (str(text or '').replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


#: 生成的个人脚本头部（用户要求：`# coding: utf-8` + `from minibt import *` ✓）
#: `minibt.__all__` 里有 `BtIndicator` / `Strategy` / `np` / `pd` / `LineStyle`
#: 这些（用户可能用到图表样式），比只 import 一个类更准确 ✓
SCRIPT_HEADER = ('# coding: utf-8\n'
                 'from minibt import *\n\n\n')
#: 策略版头部（同一个头部；类名不同而已 ✓）
SCRIPT_HEADER_STRATEGY = SCRIPT_HEADER


def script_header(kind: str = 'indicator') -> str:
    return (SCRIPT_HEADER_STRATEGY if str(kind) == 'strategy'
            else SCRIPT_HEADER)


#: 生成代码时**丢掉**的样板 import（sys.path 那套 / minibt 由头部提供 ✓）
BOILERPLATE_MODULES = {'os', 'sys', 'pathlib'}
BOILERPLATE_NAMES = {'_os', '_sys', '_ROOT'}


def _is_boilerplate_import(node) -> bool:
    """`import os as _os` / `from minibt import *` / sys.path 这类都不需要 ✓"""
    import ast
    if isinstance(node, ast.Import):
        return all(alias.name.split('.')[0] in BOILERPLATE_MODULES
                   for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        module = str(node.module or '')
        if module.split('.')[0] == 'minibt':
            return True                       # 头部 `from minibt import *` ✓
        return module.split('.')[0] in BOILERPLATE_MODULES
    return False


def _node_names(node) -> set:
    """一个定义里**引用到的名字**（用来找它依赖的类 / 函数 ✓）"""
    import ast
    out = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            out.add(child.id)
        elif isinstance(child, ast.Attribute):
            # ★ `BtStop.ATRDynamicStop` 这类**属性引用**也要算依赖：
            #   用户的停止类写在同一个文件里，只有把 `ATRDynamicStop` 带进
            #   生成代码，策略 import 后 `BtStop.ATRDynamicStop` 才认得 ✓
            out.add(child.attr)
    return out


def extract_source(text: str, kind: str = 'indicator') -> str:
    """从用户文件里取「对应的类 + 它依赖的类 / 函数」+ 真正的 import ✓

    只要加载的是指标 / 策略本身（不是整个文件），所以：
    ① 先按 kind 选根节点（`Strategy` / `BtIndicator` 子类）；
    ② **依赖闭包**：类体里引用到的其它顶层类 / 函数（比如策略里用的
       `CCI` 指标类）一起带上（用户 2026-11-02 要求 ✓）；
    ③ import 只留真正用得到的（`numpy` / 别的库），样板（`os` / `sys` /
       `sys.path` 那几行 / `from minibt import …`）全部去掉（头部已给 ✓）。
    """
    import ast
    raw = str(text or '')
    try:
        tree = ast.parse(raw)
    except SyntaxError:
        return raw
    lines = raw.splitlines(keepends=True)

    def segment(node) -> str:
        start = min([node.lineno] + [d.lineno for d in
                                     getattr(node, 'decorator_list', [])])
        end = getattr(node, 'end_lineno', node.lineno) or node.lineno
        return ''.join(lines[start - 1:end]).rstrip()

    imports: List[str] = []
    classes: List[Any] = []
    functions: List[Any] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if _is_boilerplate_import(node):
                continue
            imports.append((ast.get_source_segment(raw, node) or '').strip())
        elif isinstance(node, ast.ClassDef):
            classes.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node)

    # ① 根：匹配 kind 的类（没有就退化成全部普通类 / 函数）
    def bases_of(node) -> str:
        return ' '.join(ast.unparse(base) for base in node.bases)

    roots: List[Any] = []
    for node in classes:
        bases = bases_of(node)
        if kind == 'strategy' and 'Strategy' in bases:
            roots.append(node)
        elif kind != 'strategy' and ('BtIndicator' in bases
                                     or 'Indicator' in bases):
            roots.append(node)
    if not roots:
        roots = [node for node in classes if not node.bases] or list(functions)

    # ② 依赖闭包：被引用到的其它顶层定义也带上（`CCIStrategy` → `CCI` ✓）
    by_name = {node.name: node for node in classes + functions}
    chosen: List[Any] = []
    seen = set()

    def visit(node) -> None:
        if node.name in seen:
            return
        seen.add(node.name)
        chosen.append(node)
        for name in _node_names(node):
            target = by_name.get(name)
            if target is not None:
                visit(target)

    for root in roots:
        visit(root)

    body = '\n\n\n'.join(segment(node) for node in chosen).strip()
    head = '\n'.join(item for item in imports if item).strip()
    parts = [part for part in (head, body) if part]
    return '\n\n\n'.join(parts) + ('\n' if parts else '')


def script_path(key: str) -> str:
    """指标 → 个人指标目录里的 .py 路径（`~/.minibt/personal/indicators` ✓）"""
    from . import personal as _pi
    folder = os.path.join(_pi.PERSONAL_ROOT, _pi.KIND_DIRS.get(
        'indicator', 'indicators'))
    cls = _lookup_class(key)
    name = getattr(cls, '__name__', '') or _safe_key(key) or 'indicator'
    name = ''.join(ch if ch.isalnum() or ch in '_-' else '_'
                   for ch in str(name)) or 'indicator'
    return os.path.join(folder, f'{name}.py')


#: 新模板头部（用来判断老生成文件要不要重建 ✓）
HEADER_MARK = 'from minibt import *'
#: 老脚本自愈时补的那一行（`np` / `LineStyle` 都在 `minibt` 里 ✓）
TV_IMPORT_LINE = 'from minibt import *  # noqa: F401,F403'


def needs_rebuild(text: str) -> bool:
    """这是我们生成的脚本、但头部不是新模板 → 需要重建 ✓"""
    lines = [line.strip() for line in str(text or '').splitlines()[:3]]
    if not lines or lines[0] != '# coding: utf-8':
        return False                     # 用户自己的文件：不动 ✓
    if HEADER_MARK in lines:
        return False                     # 已经是新模板 ✓
    return any(line.startswith('from minibt import ') for line in lines) \
        or lines[1:2] == [''] and len(lines) > 1


def _ensure_tv_import(text: str, path: str = '') -> str:
    """老生成的脚本缺 `from minibt.indicators.tradingview import *` → 补上 ✓

    只对**我们自己生成的**脚本动手（头部是 `# coding: utf-8` +
    `from minibt import BtIndicator / Strategy`），用户自己的文件一个字都不改；
    补完写回磁盘（下次启动就不再 `NameError` ✓）。
    """
    raw = str(text or '')
    if HEADER_MARK in raw or 'tradingview import' in raw:
        return raw
    lines = raw.splitlines()
    head = [line.strip() for line in lines[:4]]
    if head[:1] != ['# coding: utf-8']:
        return raw
    if not any(line.startswith('from minibt import ')
               for line in head[:3]):
        return raw
    insert_at = next((index for index, line in enumerate(lines[:4])
                      if line.strip().startswith('from minibt import ')), 1)
    lines.insert(insert_at + 1, TV_IMPORT_LINE)
    fixed = chr(10).join(lines) + (chr(10) if raw.endswith(chr(10)) else '')
    if path:
        try:
            with open(path, 'w', encoding='utf-8', newline='') as handle:
                handle.write(fixed)
        except OSError:
            pass
    return fixed


def script_payload(payload: Optional[dict] = None) -> Dict[str, Any]:
    """把 TradingView 指标的源码落成**持久化**的 .py，并回给前端打开 ✓

    - 目录 = minibt 的个人指标目录（`~/.minibt/personal/indicators`，
      自动登记成「我的指标」→ 之后能在指标菜单里直接用 ✓）；
    - 文件**已存在就不覆盖**（用户改过的版本优先 ✓）；
    - 内容 = `# coding: utf-8` + `from minibt import BtIndicator` + 原始源码。
    """
    payload = payload or {}
    # ★ 用户自己的指标 / 策略：**分类持久化**到个人目录（需求 3 / 4 ✓）
    #   - 指标 → `~/.minibt/personal/indicators/<名>.py`
    #   - 策略 → `~/.minibt/personal/strategies/<名>.py`
    #   - 内容 = 头部（`# coding` + `from minibt import BtIndicator/Strategy`）
    #     + 文件里**对应的那个类**（不是整个文件 ✓）；
    #   - 已经生成过就直接加载（用户改过 / 点保存的版本优先 ✓）
    raw_path = str(payload.get('path') or '')
    if raw_path:
        source_path = os.path.abspath(os.path.expanduser(raw_path))
        if not os.path.isfile(source_path):
            return {'ok': False, 'reason': f'文件不存在：{source_path}'}
        try:
            from . import personal as _pi
            _pi.ensure_directories()          # 两个目录建好 + 登记 ✓
        except Exception as error:                                 # noqa: BLE001
            return {'ok': False, 'reason': f'创建个人目录失败：{error}'}
        kind = _file_kind(source_path)
        folder = os.path.join(_pi.PERSONAL_ROOT, _pi.KIND_DIRS.get(
            kind, 'strategies'))
        stem = os.path.splitext(os.path.basename(source_path))[0]
        stem = ''.join(ch if ch.isalnum() or ch in '_-' else '_'
                       for ch in stem) or 'script'
        target = os.path.join(folder, f'{stem}.py')
        created = False
        rebuilt = False
        try:
            existing = ''
            if os.path.isfile(target):
                with open(target, 'r', encoding='utf-8',
                          errors='replace') as handle:
                    existing = handle.read()
            # ★ 老模板（头部不是 `from minibt import *`）→ 用新模板重建：
            #   顺便把策略依赖的指标类（`CCIStrategy` → `CCI`）也带进来 ✓
            if not existing or needs_rebuild(existing):
                with open(source_path, 'r', encoding='utf-8',
                          errors='replace') as handle:
                    original = handle.read()
                body = extract_source(original, kind)
                os.makedirs(folder, exist_ok=True)
                with open(target, 'w', encoding='utf-8', newline='') as handle:
                    handle.write(script_header(kind) + body)
                created = not existing
                rebuilt = bool(existing)
            with open(target, 'r', encoding='utf-8') as handle:
                text = handle.read()
            text = _ensure_tv_import(text, target)
        except OSError as error:                                   # noqa: BLE001
            return {'ok': False, 'reason': f'写入失败：{error}'}
        return {'ok': True, 'path': target, 'name': os.path.basename(target),
                'text': text, 'created': created, 'rebuilt': rebuilt,
                'user': True, 'kind': kind, 'source_path': source_path}
    key = str(payload.get('key') or '')
    if not key:
        return {'ok': False, 'reason': '没有指标 key'}
    try:
        from . import personal as _pi
        _pi.ensure_directories()          # 目录不存在 / 没登记 → 这里建好 ✓
    except Exception as error:                                    # noqa: BLE001
        return {'ok': False, 'reason': f'创建个人目录失败：{error}'}
    cls = _lookup_class(key)
    if cls is None:
        return {'ok': False, 'reason': f'未知指标：{key}'}
    path = script_path(key)
    created = False
    try:
        existing = ''
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8', errors='replace') as handle:
                existing = handle.read()
        # ★ 老模板（不是 `from minibt import *`）→ 按新模板重建 ✓
        if not existing or needs_rebuild(existing):
            source = _source(cls)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8', newline='') as handle:
                handle.write(SCRIPT_HEADER + source.rstrip() + chr(10))
            created = not existing
        with open(path, 'r', encoding='utf-8') as handle:
            text = handle.read()
    except OSError as error:                                       # noqa: BLE001
        return {'ok': False, 'reason': f'写入脚本失败：{error}'}
    return {'ok': True, 'key': key, 'path': path,
            'name': os.path.basename(path), 'text': text,
            'created': created}


def _theme_suffix(theme: str = '') -> str:
    return '_dark' if str(theme or '').lower() == 'dark' else ''


def _svg_is_current(path: str) -> bool:
    """缩略图是不是**当前版本**生成的（看 SVG 头部的版本标记 ✓）"""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            head = handle.read(220)
    except OSError:
        return False
    return f'minibt-thumb:{THUMB_VERSION}' in head


def _card_png(key: str, theme: str = '') -> str:
    """用户在图表里截图 → 覆盖卡片封面的 PNG（**按主题各一套** ✓）

    文件名：`<key>_light.png` / `<key>_dark.png`（老版本只有 `<key>.png`，
    按浅色兜底）。**不跨主题回退** —— 深色主题绝不能显示浅色截图（反之亦然），
    否则「当前是浅色，卡片却显示深色图」✗（用户 2026-11-02 实测）。
    """
    safe = _safe_key(key)
    if not safe:
        return ''
    dark = str(theme or '').lower() == 'dark'
    names = [f'{safe}_{"dark" if dark else "light"}.png']
    if not dark:
        names.append(f'{safe}.png')       # 老版本（不分主题）= 浅色 ✓
    for name in names:
        path = os.path.join(CARD_DIR, name)
        if os.path.isfile(path):
            return path
    return ''


def save_card_png(key: str, raw: bytes, theme: str = '') -> str:
    """把图表截图写成卡片封面（按主题覆盖旧图 ✓）；写不了就返回 ''"""
    safe = _safe_key(key)
    if not safe or not raw:
        return ''
    suffix = '_dark' if str(theme or '').lower() == 'dark' else '_light'
    try:
        os.makedirs(CARD_DIR, exist_ok=True)
        path = os.path.join(CARD_DIR, f'{safe}{suffix}.png')
        with open(path, 'wb') as handle:
            handle.write(raw)
        # 同主题的旧 SVG 封面删掉（否则白白留着 ✓）
        for name in os.listdir(CARD_DIR):
            if name.startswith(f'{safe}{suffix}') and name.endswith('.svg'):
                try:
                    os.remove(os.path.join(CARD_DIR, name))
                except OSError:
                    pass
        return path
    except OSError:
        return ''


def _existing_card(key: str, theme: str = 'light') -> str:
    """已经生成过的缩略图路径（没生成返回 ''，前端再按需请求 ✓）"""
    png = _card_png(key, theme)
    if png:
        return png
    safe = _safe_key(key)
    if not safe:
        return ''
    suffix = _theme_suffix(theme)
    path = os.path.join(CARD_DIR, f'{safe}{suffix}.svg')
    if not os.path.isfile(path):
        return ''
    # ★ 老格式（没有版本标记）→ 视为没有：前端会请求 `tv_snapshot`，
    #   由 `snapshot_path()` 重新生成并覆盖（不会再出现双重角标 ✓）
    return path if _svg_is_current(path) else ''


def snapshot_payload(payload: Optional[dict] = None) -> Dict[str, Any]:
    """按需生成（或重新生成）一张卡片缩略图 → data URI ✓

    `force=True` 时**重新截图**（详情页的「截图」按钮 / 用户手动刷新 ✓）
    """
    payload = payload or {}
    key = str(payload.get('key') or '')
    theme = str(payload.get('theme') or 'light')
    if not key:
        return {'ok': False}
    if payload.get('force'):
        safe = _safe_key(key)
        suffix = '_dark' if theme.lower() == 'dark' else ''
        for name in (f'{safe}{suffix}.svg', f'{safe}.svg', f'{safe}.png',
                     f'{safe}_light.png', f'{safe}_dark.png'):
            try:
                os.remove(os.path.join(CARD_DIR, name))
            except OSError:
                pass
    url = snapshot_data_url(key, theme)
    if not url:
        return {'ok': False, 'key': key}
    return {'ok': True, 'key': key, 'dataUrl': url, 'theme': theme,
            'path': snapshot_path(key, theme)}


def snapshot_path(key: str, theme: str = 'light') -> str:
    """缩略图路径（**没有就现场生成**；返回绝对路径，前端用 file/data URI ✓）

    ★ 用户的**图表截图**（PNG，深 / 浅各一套）优先：以前这里只找 `.svg`
    → 截图之后又白生成一张 SVG 封面（`_on_screenshot` 的 `snapshot_payload`
    会顺手写盘 ✗）。
    """
    safe = _safe_key(key)
    if not safe:
        return ''
    png = _card_png(key, theme)
    if png:
        return png
    suffix = '_dark' if str(theme or '').lower() == 'dark' else ''
    path = os.path.join(CARD_DIR, f'{safe}{suffix}.svg')
    if os.path.isfile(path) and _svg_is_current(path):
        return path
    try:
        os.makedirs(CARD_DIR, exist_ok=True)
        svg = thumbnail_svg(key, theme)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(svg)
        return path
    except OSError as error:                                     # noqa: BLE001
        print(f'[desk] 指标和策略：缩略图写入失败 {error!r}')
        return ''


def snapshot_data_url(key: str, theme: str = 'light') -> str:
    """缩略图的 data URI（浏览器 / Qt 都能直接用，不用静态路由 ✓）"""
    png = _card_png(key, theme)
    path = png or snapshot_path(key, theme)
    if not path or not os.path.isfile(path):
        return ''
    try:
        with open(path, 'rb') as handle:
            raw = handle.read()
    except OSError:
        return ''
    import base64
    if png:
        return 'data:image/png;base64,' + base64.b64encode(
            raw).decode('ascii')
    return ('data:image/svg+xml;base64,'
            + base64.b64encode(raw).decode('ascii'))


def chart_html(key: str, theme: str = 'light',
               params: Optional[dict] = None,
               symbol: str = '') -> str:
    """详情页图表：K 线 + 该指标（pylightcharts `HeadlessChart`，带画线工具箱 ✓）

    `params` = 用户在详情页改过的参数（只给这个指标 ✓）
    `symbol` = 数据集名（`LocalDatas` ✓）
    """
    from pylightcharts.headless import HeadlessChart
    from . import miniqt_backtest_chart as _chart
    dark = str(theme or '').lower() == 'dark'
    frame = _symbol_frame(symbol)
    if frame is None or getattr(frame, 'empty', True):
        raise RuntimeError('没有可用的 K 线')
    frame = frame.tail(CHART_BARS).reset_index(drop=True).copy()
    frame['time'] = _chart.to_chart_time(frame['datetime'])
    chart = HeadlessChart(width=1280, height=720, toolbox=True)
    if not dark:
        try:
            chart.theme('light')
        except Exception:                                        # noqa: BLE001
            pass
    chart.set(frame[['time', 'open', 'high', 'low', 'close', 'volume']])
    chart.fit()
    items = _compute(key, frame, params)
    _apply_items(chart, frame, items)
    _chart._style_pane_separators(chart, dark)
    title = f'minibt · {key[len(TV_PREFIX):]}'
    data = str(symbol or 'test')
    if data and data != 'test':
        title += f' · {data}'
    html = chart.to_html(title=title)
    return _chart._inject_driver(html, dark)


def _apply_items(chart, frame, items: List[Dict[str, Any]]) -> None:
    """把指标条目录出的 items 画到图（line / hist；marker / candles 先跳过 ✓）"""
    import numpy as np
    import pandas as pd

    stamps = [int(value) for value in
              pd.to_datetime(frame['time']).astype('int64') // 10 ** 9]
    index = {int(stamp): position for position, stamp in enumerate(stamps)}
    for row in items:
        kind = str(row.get('kind') or 'line')
        if kind not in ('line', 'hist'):
            continue
        positions, values = [], []
        for point in row.get('data') or []:
            try:
                stamp, value = int(point[0]), float(point[1])
            except (TypeError, ValueError, IndexError):
                continue
            position = index.get(stamp)
            if position is None or not np.isfinite(value):
                continue
            positions.append(position)
            values.append(value)
        if not positions:
            continue
        payload = pd.DataFrame({'time': [stamps[p] for p in positions],
                                'value': values})
        payload['time'] = pd.to_datetime(payload['time'], unit='s')
        overlay = bool(row.get('overlay'))
        label = str(row.get('label') or '')
        try:
            if overlay:
                series = chart.add_series(
                    'Histogram' if kind == 'hist' else 'Line', name=label,
                    **(dict(base=float(row.get('base') or 0.))
                       if kind == 'hist' else {}))
            else:
                pane = chart.add_pane()
                series = chart.pane_add_series(
                    pane, 'Histogram' if kind == 'hist' else 'Line',
                    name=label,
                    **(dict(base=float(row.get('base') or 0.))
                       if kind == 'hist' else {}))
            series.set(payload)
        except Exception:                                        # noqa: BLE001
            continue


def chart_file(key: str, theme: str = 'light',
               params: Optional[dict] = None,
               symbol: str = '') -> str:
    """Qt 壳（`file://`）：把图表 HTML 写成临时文件，返回 `file://` 地址 ✓"""
    html = chart_html(key, theme, params=params, symbol=symbol)
    digest = hashlib.sha1(html.encode('utf-8')).hexdigest()[:16]
    folder = os.path.join(tempfile.gettempdir(), 'minibt_tv_charts')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f'{_safe_key(key)}_{digest}.html')
    if not os.path.isfile(path):
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(html)
    from pathlib import Path
    return Path(path).as_uri()
