"""个人指标 / 策略（持久化）：让用户把自己的脚本加进 desk 的指标菜单。

配置：``~/.minibt/desk_personal.json``

```json
{"directories": [
    {"path": "D:/my_inds", "category": "my_inds", "kind": "indicator"},
    {"path": "D:/my_strats", "category": "my_strats", "kind": "strategy"}
]}
```

* **类别名 = 目录名**（同 miniqt）；
* 目录下每个 ``.py``（``_`` 开头跳过）都会被导入，然后按类型收集：

  - **指标**（``kind='indicator'``）：模块里**顶层函数**（可以带参数）都能当指标用；
    计算时调用 ``func(df, **params)``，返回值可以是 ``Series`` / ``DataFrame`` /
    ``ndarray``（和内置指标一样转成线）。
    可选：模块级 ``__desk_indicator__ = {'label': '…', 'overlap': True}``。
  - **策略**（``kind='strategy'``）：模块里 ``minibt.Strategy`` 的子类；这里只
    **登记 + 展示**（真正跑回测/实盘还是用 ``Bt``），保证菜单里能看到自己的策略 ✓。

* 路径**不存在**时自动跳过（下次也不会报错，只是列表里没有 ✓）；
* 导入失败只记一条错误，不影响别的脚本 ✓。
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import os
import sys
from typing import Any, Dict, List, Optional

#: 配置文件（就是一份 JSON；改坏了只是不加载 ✓）
CONFIG_FILE = os.path.join(os.path.expanduser('~'), '.minibt',
                           'desk_personal.json')

#: key 前缀（前端/后端靠它区分内置指标 ✓）
PREFIX = 'pi:'

_LOCK_MARK = '_desk_personal_module'

#: 已经报过错的 (路径, mtime)：同一个坏文件只提示一次 ✓
_BROKEN_FILES: set = set()


def _log(message: str) -> None:
    print(f'[desk-personal] {message}', flush=True)


# ------------------------------------------------------------------ 配置
def load_config() -> Dict[str, Any]:
    try:
        with open(CONFIG_FILE, encoding='utf-8') as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {'directories': []}
    except (OSError, ValueError) as error:
        _log(f'读配置失败：{error!r}')
        return {'directories': []}
    if not isinstance(data, dict):
        return {'directories': []}
    cleaned = []
    for item in data.get('directories') or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get('path') or '').strip()
        if not path:
            continue
        cleaned.append({
            'path': path,
            'category': str(item.get('category') or category_name(path)),
            'kind': 'strategy' if str(item.get('kind')) == 'strategy'
            else 'indicator',
        })
    return {'directories': cleaned}


def save_config(config: Dict[str, Any]) -> bool:
    try:
        folder = os.path.dirname(CONFIG_FILE)
        if folder:
            os.makedirs(folder, exist_ok=True)
        payload = json.dumps({'directories': list(
            (config or {}).get('directories') or [])}, ensure_ascii=False,
            indent=2)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as handle:
            handle.write(payload)
        return True
    except OSError as error:
        _log(f'写配置失败：{error!r}')
        return False


def category_name(path: str) -> str:
    name = os.path.basename(os.path.abspath(str(path or '')).rstrip('\\/'))
    return name or '我的脚本'


def directories() -> List[Dict[str, Any]]:
    """配置里的目录（**过滤掉已经不存在的** ✓）"""
    return [item for item in load_config()['directories']
            if os.path.isdir(item['path'])]


def add_directory(path: str, kind: str = 'indicator',
                  category: str = '') -> Dict[str, Any]:
    """登记一个目录（存在才登记；重复则更新 kind ✓）"""
    path = os.path.abspath(os.path.expanduser(str(path or '')))
    if not os.path.isdir(path):
        return {'ok': False, 'error': f'目录不存在：{path}'}
    kind = 'strategy' if kind == 'strategy' else 'indicator'
    config = load_config()
    entries = config['directories']
    for item in entries:
        if os.path.abspath(item['path']) == path:
            item['kind'] = kind
            if category:
                item['category'] = category
            save_config(config)
            return {'ok': True, 'path': path, 'kind': kind,
                    'category': item['category'], 'updated': True}
    entry = {'path': path, 'kind': kind,
             'category': category or category_name(path)}
    entries.append(entry)
    save_config(config)
    return {'ok': True, 'path': path, 'kind': kind,
            'category': entry['category'], 'updated': False}


def remove_directory(path_or_category: str) -> bool:
    config = load_config()
    key = str(path_or_category or '')
    kept = [item for item in config['directories']
            if item['path'] != key and item['category'] != key]
    if len(kept) == len(config['directories']):
        return False
    config['directories'] = kept
    return save_config(config)


# ------------------------------------------------------------------ 扫描
#: `(path, mtime) → module`：指标每拍重算时不要反复 exec 用户脚本 ✓
_MODULE_CACHE: Dict[Any, Any] = {}


def _import_file(py_path: str) -> Optional[Any]:
    """按路径导入模块（不污染 sys.path；同名互相不覆盖 ✓）"""
    try:
        stamp = (os.path.abspath(str(py_path)), os.path.getmtime(py_path))
    except OSError:
        return None
    cached = _MODULE_CACHE.get(stamp)
    if cached is not None:
        return cached
    name = f'desk_personal_{abs(hash(stamp))}'
    spec = importlib.util.spec_from_file_location(name, py_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as error:                                   # noqa: BLE001
        sys.modules.pop(name, None)
        # 同一个文件（同一 mtime）只提示一次：否则每保存一次都刷一屏 ✗
        stamp = (py_path, os.path.getmtime(py_path))
        if stamp not in _BROKEN_FILES:
            _BROKEN_FILES.add(stamp)
            hint = ''
            if isinstance(error, SyntaxError):
                hint = (f'（第 {error.lineno or 0} 行：{error.msg}）'
                        '—— 修好保存后会自动重新加载')
            _log(f'跳过 {os.path.basename(py_path)}：{type(error).__name__}{hint}')
        return None
    setattr(module, _LOCK_MARK, py_path)
    # 同一路径旧 mtime 的缓存删掉，避免越积越多 ✓
    for old_stamp in list(_MODULE_CACHE):
        if old_stamp[0] == stamp[0] and old_stamp != stamp:
            _MODULE_CACHE.pop(old_stamp, None)
    _MODULE_CACHE[stamp] = module
    return module


def _python_files(path: str) -> List[str]:
    try:
        names = sorted(os.listdir(path))
    except OSError:
        return []
    result = []
    for name in names:
        if name.startswith('_') or not name.endswith('.py'):
            continue
        full = os.path.join(path, name)
        if os.path.isfile(full):
            result.append(full)
    return result


def _params_of(func) -> List[Dict[str, Any]]:
    """函数签名 → 参数表（跳过 df/source/self 等 ✓）"""
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return []
    skip = {'df', 'data', 'source', 'self', 'kline', 'frame'}
    params = []
    for index, (name, parameter) in enumerate(signature.parameters.items()):
        if name in skip or name.startswith('_'):
            continue
        if parameter.kind in (inspect.Parameter.VAR_POSITIONAL,
                             inspect.Parameter.VAR_KEYWORD):
            continue
        default = parameter.default
        if default is inspect.Parameter.empty:
            continue
        if not isinstance(default, (bool, int, float, str)):
            continue
        kind = ('float' if isinstance(default, float)
                else ('int' if isinstance(default, int)
                      and not isinstance(default, bool)
                      else ('bool' if isinstance(default, bool) else 'str')))
        params.append({'name': name, 'default': default, 'type': kind})
    return params


def scan(kind: str = 'indicator') -> List[Dict[str, Any]]:
    """扫描所有登记的目录 → 菜单条目（指标：函数；策略：Strategy 子类 ✓）"""
    out: List[Dict[str, Any]] = []
    for entry in directories():
        if entry['kind'] != kind:
            continue
        category = entry['category']
        for py_path in _python_files(entry['path']):
            module = _import_file(py_path)
            if module is None:
                continue
            file_name = os.path.basename(py_path)
            if kind == 'indicator':
                out.extend(_scan_indicators(module, category, py_path,
                                            file_name))
            else:
                for name, obj in vars(module).items():
                    if name.startswith('_') or not inspect.isclass(obj):
                        continue
                    if getattr(obj, '__module__', '') != module.__name__:
                        continue
                    if not _is_strategy(obj):
                        continue
                    out.append({
                        'key': f'{PREFIX}{category}/{name}',
                        'name': name,
                        'label': f'{name} · {category}',
                        'group': f'个人策略 · {category}',
                        'overlap': False,
                        'params': [],
                        'path': py_path,
                        'file': file_name,
                        'personal': True,
                        'strategy': True,
                    })
    return out


def _is_strategy(obj) -> bool:
    try:
        from ..strategy.strategy import Strategy
        return (inspect.isclass(obj) and issubclass(obj, Strategy)
                and obj is not Strategy)
    except Exception:                                            # noqa: BLE001
        return False


# ------------------------------------------------------------------ 计算
def compute(frame, key: str, params: Optional[Dict[str, Any]] = None,
            limit: int = 600,
            errors: Optional[Dict[str, str]] = None
            ) -> List[Dict[str, Any]]:
    """算一个个人指标（``pi:<category>/<func>``）✓

    ``errors``：出错时填 ``{key: 错误信息}``（调用方据此不把指标加上去 ✓）
    """
    import numpy as np

    if frame is None or len(frame) == 0 or not str(key).startswith(PREFIX):
        return []
    category, _, name = str(key)[len(PREFIX):].partition('/')
    for entry in directories():
        if entry['kind'] != 'indicator' or entry['category'] != category:
            continue
        for py_path in _python_files(entry['path']):
            module = _import_file(py_path)
            if module is None:
                continue
            func = getattr(module, name, None)
            if _is_bt_indicator(func):
                # `BtIndicator` 类 → 用 KLine 实例化（带 PlotInfo 样式 ✓）
                return compute_class(frame, key, params, limit,
                                     errors=errors)
            if not callable(func) or not inspect.isfunction(func):
                continue
            values = {param['name']: param['default']
                      for param in _params_of(func)}
            values.update(params or {})
            try:
                result = func(frame, **values)
            except Exception as error:                           # noqa: BLE001
                _log(f'计算失败 {name}：{error!r}')
                if errors is not None:
                    errors[str(key)] = f'{type(error).__name__}: {error}'
                return []
            return _to_items(key, name, module, result, frame, np, limit)
    return []


def _to_items(key: str, name: str, module, result, frame, np,
              limit: int) -> List[Dict[str, Any]]:
    meta = getattr(module, '__desk_indicator__', {}) or {}
    color = str(meta.get('color') or '#ffb300')
    #: 函数式多列：一列一个颜色（以前全用同一个 `color` ✗）
    palette = ('#f6c343', '#2196f3', '#e91e63', '#26a69a',
               '#9c27b0', '#ff9800', '#00bcd4', '#8bc34a')
    stamps = []
    for value in frame['datetime'].tolist():
        try:
            stamps.append(int(value) // 1_000_000_000)
        except (TypeError, ValueError):
            stamps.append(0)
    columns: List[str] = []
    matrix = None
    if isinstance(result, np.ndarray):
        matrix = result if result.ndim == 2 else result.reshape(-1, 1)
    elif hasattr(result, 'columns'):
        columns = [str(column) for column in result.columns]
        matrix = result.to_numpy()
    elif hasattr(result, 'to_numpy'):
        matrix = result.to_numpy().reshape(-1, 1)
    if matrix is None or not len(matrix):
        return []
    rows = matrix.shape[0]
    offset = max(0, len(stamps) - rows)
    out = []
    for index in range(matrix.shape[1]):
        label = columns[index] if index < len(columns) else name
        series = []
        for row in range(rows):
            try:
                number = float(matrix[row][index])
            except (TypeError, ValueError, IndexError):
                number = None
            position = offset + row
            if position >= len(stamps):
                break
            # 保留 NaN 空白点，LWC 才会在缺口处断线 ✓
            if number is None or number != number:
                series.append([stamps[position], None])
                continue
            series.append([stamps[position], number])
        if not series:
            continue
        out.append({
            'key': f'{key}:{label}',
            'label': f'{name}.{label}' if len(columns) > 1 else name,
            'overlay': bool(meta.get('overlap')),
            # ★ 同一个指标的列共用**一个副图**（以前一列一个 pane ✗）
            'pane': name,
            'kind': 'line',
            # 多列 → 按列取色（单列仍用 meta.color ✓）
            'color': (palette[index % len(palette)]
                      if len(columns) > 1 else color),
            'data': series[-int(limit):],
        })
    return out


# --------------------------------------------------------------- 编辑器（P46）
#: 默认个人目录（首次使用时自动建 + 登记 ✓）
PERSONAL_ROOT = os.path.join(os.path.expanduser('~'), '.minibt', 'personal')

#: 两种源码（指标 / 策略）→ 子目录名
KIND_DIRS = {'indicator': 'indicators', 'strategy': 'strategies'}

#: 单文件大小上限（超过就不让编辑，避免把 20MB 的日志当代码打开 ✗）
MAX_SOURCE_BYTES = 512 * 1024

#: 编辑器里**可以打开**的文本类文件（.py 之外的 md / txt / json… 也算 ✓）
TEXT_SUFFIXES = ('.py', '.pyi', '.md', '.markdown', '.txt', '.json',
                 '.yaml', '.yml', '.toml', '.ini', '.cfg', '.csv', '.log',
                 '.sh', '.bat', '.ps1', '.html', '.css', '.js', '.ts')


def is_text_file(path: str) -> bool:
    """能不能在编辑器里打开（只按**后缀**判断，不问内容 ✓）"""
    return os.path.splitext(str(path or '').lower())[1] in TEXT_SUFFIXES

#: 指标模板（`BtIndicator` + 一个函数式入口；保存后能在「指标 → 个人」里加到图上）
INDICATOR_TEMPLATE = '''# -*- coding: utf-8 -*-
"""__NAME__ — 个人指标（minibt desk 编辑器生成）

两种写法 desk 都能直接加到图上：

1. **函数**：第一个参数是 K 线 DataFrame，返回 Series / DataFrame；
2. **`BtIndicator` 类**：写 `next()`（返回线数据），`lines` / `params` /
   `overlap` 由框架读成 PlotInfo（主图 or 副图、颜色、虚线都对 ✓）。

改完 Ctrl+S，就能在「指标 → 个人」里看到；点「加到图表」直接上屏。
"""
from minibt import BtIndicator


def __NAME__(frame, length: int = 20, color: str = '#ffb300'):
    """函数式指标：收盘价均线（desk 默认入口 ✓）"""
    close = frame['close']
    return close.rolling(int(length)).mean().rename('ma')


class __NAME___indicator(BtIndicator):
    """类式指标：`next()` 返回一条线（`overlap=True` = 画在主图 ✓）"""

    lines = ('ma',)
    params = dict(length=20)
    overlap = True

    def next(self):
        return self.close.rolling(int(self.params.length)).mean()
'''

STRATEGY_TEMPLATE = '''# -*- coding: utf-8 -*-
"""__NAME__ — 个人策略（minibt desk 编辑器生成）

⚠ desk 里**不能**直接跑策略（没有回测引擎）；写好后用：

    from minibt import Bt
    Bt(strategy=__NAME__).run()

`self.get_kline()` 拿到 K 线（不传参数 = 用回测/看盘给的那一份 ✓）。
"""
from minibt import Strategy


class __NAME__(Strategy):
    """示例：双均线交叉"""

    params = dict(fast=5, slow=20, size=1)

    def __init__(self):
        self.kline = self.get_kline()
        close = self.kline.close
        self.fast = close.rolling(int(self.params.fast)).mean()
        self.slow = close.rolling(int(self.params.slow)).mean()

    def next(self):
        fast = self.fast[-1]
        slow = self.slow[-1]
        if fast != fast or slow != slow:
            return
        if fast > slow and self.position == 0:
            self.buy(size=self.params.size)
        elif fast < slow and self.position > 0:
            self.sell(size=self.position)
'''


def ensure_directories() -> Dict[str, str]:
    """保证两个默认目录存在并**登记**到配置里（幂等 ✓）"""
    out: Dict[str, str] = {}
    for kind, folder in KIND_DIRS.items():
        path = os.path.join(PERSONAL_ROOT, folder)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as error:
            _log(f'创建目录失败 {path}: {error!r}')
            continue
        out[kind] = path
        known = {os.path.abspath(item['path'])
                 for item in load_config()['directories']}
        if os.path.abspath(path) not in known:
            add_directory(path, kind=kind,
                          category='我的指标' if kind == 'indicator'
                          else '我的策略')
    return out


def _safe_file(name: str, kind: str = 'indicator') -> Optional[str]:
    """``名称`` → 磁盘路径（只允许**本目录内**的 .py，防目录穿越 ✗）"""
    folder = os.path.join(PERSONAL_ROOT, KIND_DIRS.get(kind, 'indicators'))
    raw = str(name or '').strip()
    # 带路径分隔符的名字**直接拒绝**（比静默改名更不容易让人困惑 ✓）
    if any(char in raw for char in ('/', chr(92))) or '..' in raw:
        return None
    text = os.path.basename(raw)
    if not text:
        return None
    if not text.endswith('.py'):
        text += '.py'
    bad = ('\\', '/', ':', '*', '?', '"', '<', '>', '|')
    if any(char in text for char in bad):
        return None
    return os.path.join(folder, text)


def _entries(kind: str) -> List[Dict[str, Any]]:
    """某个 kind 的文件清单（默认目录 + 用户登记的目录 ✓）"""
    ensure_directories()
    items: List[Dict[str, Any]] = []
    seen = set()
    for entry in directories():
        if entry['kind'] != kind:
            continue
        for path in _python_files(entry['path']):
            real = os.path.abspath(path)
            if real in seen:
                continue
            seen.add(real)
            try:
                size = os.path.getsize(real)
                mtime = os.path.getmtime(real)
            except OSError:
                size, mtime = 0, 0.0
            items.append({
                'name': os.path.basename(real),
                'path': real,
                'kind': kind,
                'category': entry['category'],
                'default': os.path.abspath(entry['path']).startswith(
                    os.path.abspath(PERSONAL_ROOT)),
                'size': size,
                'mtime': mtime,
                'editable': size <= MAX_SOURCE_BYTES,
            })
    items.sort(key=lambda item: (not item['default'],
                                 str(item['category']).lower(),
                                 item['name'].lower()))
    return items


def list_files() -> Dict[str, Any]:
    """编辑器文件树：``{indicators: [...], strategies: [...], root: ...}`` ✓"""
    ensure_directories()
    return {'root': PERSONAL_ROOT,
            'indicators': _entries('indicator'),
            'strategies': _entries('strategy')}


def read_file(path: str) -> Dict[str, Any]:
    """读一个文本文件（`.py` 之外也支持 md / txt / json… ✓）"""
    real = os.path.abspath(str(path or ''))
    if not is_text_file(real) or not os.path.isfile(real):
        return {'ok': False, 'error': f'文件不存在 / 不支持的类型：{real}'}
    try:
        size = os.path.getsize(real)
        if size > MAX_SOURCE_BYTES:
            return {'ok': False, 'error': f'文件太大（{size} 字节），不打开'}
        with open(real, encoding='utf-8') as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as error:
        return {'ok': False, 'error': f'读取失败：{error!r}'}
    if real.lower().endswith(('.py', '.pyi')):
        kind = ('strategy' if (os.sep + KIND_DIRS['strategy']) in real
                or 'strateg' in real.lower() else 'indicator')
    else:
        kind = 'text'
    return {'ok': True, 'path': real, 'name': os.path.basename(real),
            'kind': kind, 'text': text, 'mtime': os.path.getmtime(real)}


def check_source(text: str, filename: str = '<editor>') -> Dict[str, Any]:
    """语法检查（`compile()` 只解析不执行 ✓）+ 顺带认一下类名"""
    source = str(text or '')
    try:
        compile(source, filename, 'exec')
    except SyntaxError as error:
        return {'ok': False, 'line': int(error.lineno or 0),
                'col': int(error.offset or 0),
                'error': f'{type(error).__name__}: {error.msg}'}
    except (ValueError, TypeError) as error:                     # noqa: BLE001
        return {'ok': False, 'line': 0, 'col': 0, 'error': repr(error)}
    import ast as _ast
    kinds = []
    try:
        tree = _ast.parse(source)
        for node in tree.body:
            if not isinstance(node, _ast.ClassDef):
                continue
            bases = [getattr(base, 'id', getattr(base, 'attr', ''))
                     for base in node.bases]
            if 'BtIndicator' in bases:
                kinds.append({'kind': 'indicator', 'name': node.name})
            elif 'Strategy' in bases:
                kinds.append({'kind': 'strategy', 'name': node.name})
    except SyntaxError:
        pass
    return {'ok': True, 'line': 0, 'col': 0, 'error': '', 'defines': kinds}


def _under_root(path: str, root: str) -> bool:
    real = os.path.abspath(str(path or ''))
    base = os.path.abspath(str(root or ''))
    return bool(real and base) and (real == base or
                                    real.startswith(base + os.sep))


def write_file(path: str, text: str, *, check: bool = True,
               root: str = '') -> Dict[str, Any]:
    """保存（先语法检查，报错就不写盘）

    ``root`` = 编辑器当前资源管理器根目录；不传时只允许个人目录 /
    已登记目录。这样 HTTP / 编辑器命令都不能借保存写任意路径 ✓
    """
    real = os.path.abspath(str(path or ''))
    if not is_text_file(real):
        return {'ok': False, 'error': '只能保存文本类文件（.py / .md / .txt …）'}
    if root:
        allowed = _under_root(real, root)
    else:
        allowed = _under_root(real, PERSONAL_ROOT) or any(
            _under_root(real, entry.get('path') or '')
            for entry in directories())
    if not allowed:
        return {'ok': False, 'error': '只能保存个人目录 / 当前资源管理器根目录内的文件'}
    # 非 Python 文件不做语法检查（md / json / txt 没有 Python 语法 ✓）
    check = bool(check) and real.lower().endswith(('.py', '.pyi'))
    folder = os.path.dirname(real) or PERSONAL_ROOT
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError as error:
        return {'ok': False, 'error': f'创建目录失败：{error!r}'}
    if check:
        result = check_source(text, real)
        if not result.get('ok'):
            return {'ok': False, 'error': result.get('error', '语法错误'),
                    'line': result.get('line', 0), 'col': result.get('col', 0)}
    try:
        with open(real, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(str(text or ''))
    except OSError as error:
        return {'ok': False, 'error': f'写入失败：{error!r}'}
    return {'ok': True, 'path': real, 'name': os.path.basename(real),
            'mtime': os.path.getmtime(real)}


def delete_file(path: str) -> Dict[str, Any]:
    """删文件（只能删个人目录 / 登记目录里的 ✓）"""
    real = os.path.abspath(str(path or ''))
    if not real.endswith('.py') or not os.path.isfile(real):
        return {'ok': False, 'error': '文件不存在'}
    root = os.path.abspath(PERSONAL_ROOT)
    allowed = any(real.startswith(os.path.abspath(entry['path']))
                  for entry in directories())
    if not real.startswith(root) and not allowed:
        return {'ok': False, 'error': '只能删除个人目录里的文件'}
    try:
        os.remove(real)
    except OSError as error:
        return {'ok': False, 'error': f'删除失败：{error!r}'}
    return {'ok': True, 'path': real}


def create_file(kind: str, name: str,
                overwrite: bool = False) -> Dict[str, Any]:
    """按模板新建（指标 / 策略 ✓）"""
    kind = 'strategy' if kind == 'strategy' else 'indicator'
    target = _safe_file(name, kind)
    if target is None:
        return {'ok': False, 'error': '文件名不合法'}
    if os.path.exists(target) and not overwrite:
        return {'ok': False, 'error': f'已存在：{os.path.basename(target)}',
                'exists': True, 'path': target}
    template = STRATEGY_TEMPLATE if kind == 'strategy' else INDICATOR_TEMPLATE
    title = os.path.splitext(os.path.basename(target))[0]
    text = template.replace('__NAME__', title)
    result = write_file(target, text, check=False)
    if not result.get('ok'):
        return result
    ensure_directories()
    return {'ok': True, 'path': target, 'name': os.path.basename(target),
            'kind': kind, 'text': text}


# ------------------------------------------------------- BtIndicator 类（P57）
def _bt_indicator_cls():
    """`BtIndicator` 基类（拿不到就返回 None，不影响函数式指标 ✓）"""
    try:
        from ..indicators.core import BtIndicator
        return BtIndicator
    except Exception:                                            # noqa: BLE001
        try:
            from minibt import BtIndicator
            return BtIndicator
        except Exception:                                        # noqa: BLE001
            return None


def _is_bt_indicator(obj) -> bool:
    base = _bt_indicator_cls()
    if base is None or not inspect.isclass(obj):
        return False
    try:
        return issubclass(obj, base) and obj is not base
    except Exception:                                            # noqa: BLE001
        return False


def _class_params(cls) -> List[Dict[str, Any]]:
    """`BtIndicator.params`（dict / 属性）→ 参数表 ✓"""
    raw = getattr(cls, 'params', None)
    if isinstance(raw, dict):
        items = dict(raw)
    else:
        items = {}
        for name in dir(cls):
            if name.startswith('_'):
                continue
            value = getattr(cls, name, None)
            if isinstance(value, (bool, int, float, str)):
                items[name] = value
    params = []
    for name, value in items.items():
        if not isinstance(value, (bool, int, float, str)):
            continue
        kind = ('float' if isinstance(value, float)
                else ('int' if isinstance(value, int)
                      and not isinstance(value, bool)
                      else ('bool' if isinstance(value, bool) else 'str')))
        params.append({'name': str(name), 'default': value, 'type': kind})
    params.sort(key=lambda item: item['name'])
    return params


def _scan_indicators(module, category: str, py_path: str,
                     file_name: str) -> List[Dict[str, Any]]:
    """一个模块里的指标：**函数** + `BtIndicator` 子类（都列出来 ✓）"""
    meta = getattr(module, '__desk_indicator__', {}) or {}
    out: List[Dict[str, Any]] = []
    for name, obj in vars(module).items():
        if name.startswith('_'):
            continue
        if getattr(obj, '__module__', '') != module.__name__:
            continue
        if inspect.isclass(obj):
            if not _is_bt_indicator(obj):
                continue
            out.append({
                'key': f'{PREFIX}{category}/{name}',
                'name': name,
                'label': f'{name} · {category}',
                'group': f'个人指标 · {category}',
                'overlap': bool(_class_overlap(obj)),
                'params': _class_params(obj),
                'path': py_path,
                'file': file_name,
                'personal': True,
                'cls': True,           # 前端/后端靠它区分「类」和「函数」✓
                'lines': list(getattr(obj, 'lines', ()) or ()),
            })
            continue
        if not inspect.isfunction(obj):
            continue
        out.append({
            'key': f'{PREFIX}{category}/{name}',
            'name': name,
            'label': f'{meta.get("label") or name} · {category}',
            'group': f'个人指标 · {category}',
            'overlap': bool(meta.get('overlap')),
            'params': _params_of(obj),
            'path': py_path,
            'file': file_name,
            'personal': True,
        })
    return out


def _class_overlap(cls) -> bool:
    """类上的 `overlap`（bool / dict 都认 ✓）"""
    value = getattr(cls, 'overlap', False)
    if isinstance(value, dict):
        return any(bool(item) for item in value.values())
    return bool(value)


def compute_class(frame, key: str,
                  params: Optional[Dict[str, Any]] = None,
                  limit: int = 600,
                  errors: Optional[Dict[str, str]] = None
                  ) -> List[Dict[str, Any]]:
    """算一个 **`BtIndicator` 类**（用 KLine 实例化 → 带 PlotInfo 样式 ✓）"""
    if frame is None or len(frame) == 0 or not str(key).startswith(PREFIX):
        return []
    category, _, name = str(key)[len(PREFIX):].partition('/')
    for entry in directories():
        if entry['kind'] != 'indicator' or entry['category'] != category:
            continue
        for py_path in _python_files(entry['path']):
            module = _import_file(py_path)
            if module is None:
                continue
            cls = getattr(module, name, None)
            if not _is_bt_indicator(cls):
                continue
            try:
                from . import indicator_catalog as _cat
                kline = _cat._kline_of(frame)
                if kline is None:
                    return []
                instance = cls(kline, **(params or {}))
            except Exception as error:                           # noqa: BLE001
                _log(f'指标类 {name} 计算失败：{error!r}')
                if errors is not None:
                    errors[str(key)] = f'{type(error).__name__}: {error}'
                return []
            plotinfo = getattr(instance, '_plotinfo', None)
            _apply_class_watermark(plotinfo, cls)
            overlap = _class_overlap(cls)
            if plotinfo is not None:
                try:
                    overlap = bool(_per(plotinfo.overlap, name, overlap))
                except Exception:                                # noqa: BLE001
                    pass
            try:
                from . import indicator_catalog as _cat
                item = {'name': name, 'overlap': overlap}
                items = _cat._to_items(key, item, instance,
                                       _cat._stamps(frame), _np(),
                                       limit, frame, plotinfo)
                # ★ 只有**本类自己**写了 `watermark` 才保留水印条目：
                #   minibt 的 PlotInfo 在多个指标之间会串（实测 StyleZoo_Osc
                #   也带上了 Main 的 'STYLE ZOO' ✗）
                if not isinstance(
                        (getattr(cls, '__dict__', {}) or {}).get('watermark'),
                        (str,)) and not _is_watermark(cls):
                    items = [entry for entry in items
                             if entry.get('kind') != 'watermark']
                return items
            except Exception as error:                           # noqa: BLE001
                _log(f'指标类 {name} 转线条失败：{error!r}')
                if errors is not None:
                    errors[str(key)] = f'{type(error).__name__}: {error}'
                return []
    return []


def check_strategy_file(path: str) -> Dict[str, Any]:
    """回测 / 参数优化前的体检（**只读源码，不执行** ✓）

    返回 ``{ok, reason, strategies, has_op_config}``：

    1. 文件存在吗？
    2. **语法**能过吗（`ast.parse`）？
    3. 有 ``Strategy`` 子类吗（按 AST 找 ``class X(...Strategy)``）？
    4. 策略里有没有 ``op_config``（参数优化才需要）？

    只看源码、不 import，避免用户脚本的副作用（读文件 / 连数据库 / 跑回测）✗
    """
    import ast

    real = os.path.abspath(str(path or ''))
    if not real or not os.path.isfile(real):
        return {'ok': False, 'reason': f'文件不存在：{real or "(空路径)"}',
                'strategies': [], 'has_op_config': False}
    try:
        with open(real, encoding='utf-8') as handle:
            source = handle.read()
    except OSError as error:
        return {'ok': False, 'reason': f'读文件失败：{error!r}',
                'strategies': [], 'has_op_config': False}
    try:
        tree = ast.parse(source, filename=real)
    except SyntaxError as error:
        line = error.lineno or 0
        where = f'第 {line} 行' if line else ''
        return {'ok': False,
                'reason': f'语法错误（{where}）：{error.msg}',
                'strategies': [], 'has_op_config': False}

    def _base_name(node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Subscript):                 # Generic[...] 之类
            return _base_name(node.value)
        return ''

    strategies = []
    has_op_config = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [_base_name(base) for base in node.bases]
        if not any('Strategy' in name for name in bases):
            continue
        strategies.append(node.name)
        for child in node.body:
            # `op_config = dict(...)` / `op_config: dict = ...` / `def op_config`
            if isinstance(child, (ast.Assign, ast.AnnAssign)):
                targets = (child.targets if isinstance(child, ast.Assign)
                           else [child.target])
                for target in targets:
                    if isinstance(target, ast.Name) and target.id == 'op_config':
                        has_op_config = True
            if isinstance(child, ast.FunctionDef) and child.name == 'op_config':
                has_op_config = True
    if strategies:
        return {'ok': True, 'reason': '', 'strategies': strategies,
                'has_op_config': has_op_config, 'mode': 'strategy'}

    # ---- 没有 Strategy：再看看是不是**指标信号**（miniqt 同款 ✓）----
    # `class X(BtIndicator)` + 有 `long_signal`/`short_signal` 就能
    # `ind.signal_backtest(...)` 回测 / 优化；返回的实例本身也是 `Strategy`
    # 子类（`SignalIndicatorStrategy`），所以出图 / 交易记录链路完全复用 ✓
    indicators = []
    signal_names = {'long_signal', 'short_signal',
                    'exitlong_signal', 'exitshort_signal'}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [_base_name(base) for base in node.bases]
        if not any('Indicator' in name for name in bases):
            continue
        found = False
        for child in node.body:
            names = []
            if isinstance(child, (ast.Assign, ast.AnnAssign)):
                targets = (child.targets if isinstance(child, ast.Assign)
                           else [child.target])
                names = [t.id for t in targets if isinstance(t, ast.Name)]
            elif isinstance(child, ast.FunctionDef):
                names = [child.name]
            if any(name in signal_names for name in names):
                found = True
                break
            # `lines = ['ma1', 'long_signal', ...]` 也算 ✓
            if isinstance(child, (ast.Assign, ast.AnnAssign)):
                try:
                    value = child.value
                    if isinstance(value, (ast.List, ast.Tuple)):
                        elements = [elt.value for elt in value.elts
                                    if isinstance(elt, ast.Constant)]
                        if any(str(item) in signal_names for item in elements):
                            found = True
                            break
                except Exception:                                # noqa: BLE001
                    pass
        if found:
            indicators.append(node.name)
    indicator_op_config = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name not in indicators:
            continue
        for child in node.body:
            targets = []
            if isinstance(child, ast.Assign):
                targets = child.targets
            elif isinstance(child, ast.AnnAssign):
                targets = [child.target]
            if any(isinstance(t, ast.Name) and t.id == 'op_config'
                   for t in targets):
                indicator_op_config = True
    if indicators:
        return {'ok': True, 'reason': '', 'strategies': indicators,
                'has_op_config': indicator_op_config, 'mode': 'indicator'}
    return {'ok': False,
            'reason': ('这个文件里既没有 `Strategy` 子类，也没有带交易信号的'
                       ' `BtIndicator`（要 `long_signal` / `short_signal`'
                       ' 或 `exitlong_signal` / `exitshort_signal`）'),
            'strategies': [], 'has_op_config': False, 'mode': 'none'}


def _apply_class_watermark(plotinfo, cls) -> None:
    """类体里写的 ``watermark = WaterMark(...)`` / ``watermark = '文字'``
    → 落到 ``PlotInfo.watermark`` ✓

    ``BtIndicator`` 的构造参数只转发 ``linestyle / spanstyle / bandstyle /
    tablestyle ...``，**不转发 ``watermark``**，所以类属性会被静默丢掉；
    这里补一次（只影响个人指标类，不动 minibt 本体 ✓）
    """
    if plotinfo is None:
        return
    if getattr(plotinfo, 'watermark', None) is not None:
        return
    raw = (getattr(cls, '__dict__', {}) or {}).get('watermark')
    if raw is None or raw is False:
        return
    try:
        from ..utils import WaterMark
    except Exception:                                            # noqa: BLE001
        return
    if not isinstance(raw, (WaterMark, str)):      # `property` / True 之类一律忽略
        return
    if isinstance(raw, WaterMark):
        plotinfo.watermark = raw
    elif raw.strip():
        plotinfo.watermark = WaterMark(text=raw.strip())


def _is_watermark(cls) -> bool:
    """类体里写的是不是 `WaterMark(...)` ✓"""
    raw = (getattr(cls, '__dict__', {}) or {}).get('watermark')
    try:
        from ..utils import WaterMark
        return isinstance(raw, WaterMark)
    except Exception:                                            # noqa: BLE001
        return False


def _per(value, name: str, default):
    """PlotInfo 的 bool / dict / list 三种写法 ✓"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return value.get(name, default)
    if isinstance(value, (list, tuple)):
        return bool(value[0]) if value else default
    return bool(value)


def _np():
    import numpy as np
    return np


def has_class(key: str) -> bool:
    """这个 `pi:` key 是不是 **BtIndicator 类**（compute 分流用 ✓）"""
    if not str(key).startswith(PREFIX):
        return False
    category, _, name = str(key)[len(PREFIX):].partition('/')
    for entry in directories():
        if entry['kind'] != 'indicator' or entry['category'] != category:
            continue
        for py_path in _python_files(entry['path']):
            module = _import_file(py_path)
            if module is None:
                continue
            if _is_bt_indicator(getattr(module, name, None)):
                return True
    return False
