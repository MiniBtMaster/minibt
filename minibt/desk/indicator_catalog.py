"""完整指标库目录（P6）：把 `minibt.indicators` 反射成可搜索的目录。

`minibt` 的指标是 `@tobtind` 装饰的方法，分布在几个库里：

| 前缀 | 库 | 数量（本机） |
| --- | --- | --- |
| `pta_` | PandasTA | ~170 |
| `ti_` | TuLip | ~100 |
| `tqta_` | 天勤 TA | ~60 |
| `pine_` | Pine | ~57 |
| `btind_` | BtInd | ~36 |
| `tqfunc_` | 天勤函数 | ~27 |

装饰器会把 `_decorator_args`（含 `overlap`）挂到 wrapper 上，参数表用
`inspect.signature(wrapper.__wrapped__)` 反射 —— 所以新增指标**不用改本文件** ✓。

目录会缓存到 ``~/.minibt/desk_indicators.json``（minibt 版本变化时自动重建）。
"""
from __future__ import annotations

import inspect
import json
import os
import threading
from typing import Any, Dict, List, Optional

#: 前缀 → (minibt 类名, 展示名)
LIBS = (
    ('pta', 'PandasTa', 'PandasTA'),
    ('ti', 'TuLip', 'TuLip'),
    ('tqta', 'TqTa', '天勤TA'),
    ('pine', 'Pine', 'Pine'),
    ('btind', 'BtInd', 'BtInd'),
    ('tqfunc', 'TqFunc', '天勤函数'),
    ('talib', 'TaLib', 'TA-Lib'),
    ('finta', 'FinTa', 'FinTa'),
    ('pair', 'Pair', 'Pair'),
    ('factor', 'Factors', 'Factors'),
)

#: **多合约**库：指标 / 衡量标准 / 策略内置指标都不加载（用户要求 ✓）
EXCLUDED_PREFIXES = {'pair', 'factor'}

#: 前缀 → minibt 类名（用来读各库的 `NON_KLINE_INDICATORS` ✓）
PREFIX_CLASS = {prefix: class_name for prefix, class_name, _ in LIBS}


def _non_kline_names(prefix: str) -> set:
    """某个库声明为「不是 K 线指标」的方法名（数学 / 逻辑 / 时间工具）✓"""
    class_name = PREFIX_CLASS.get(str(prefix or ''))
    if not class_name:
        return set()
    try:
        import minibt
        root = getattr(minibt, 'IndicatorClass', None)
        library = getattr(root, class_name, None) if root is not None else None
        return set(getattr(library, 'NON_KLINE_INDICATORS', ()) or ())
    except Exception:                                        # noqa: BLE001
        return set()


def _catalog_allowed(item: Dict[str, Any]) -> bool:
    """目录最终过滤：Pair/Factors + 各库 NON_KLINE_INDICATORS ✓"""
    prefix = str(item.get('prefix') or '')
    if prefix in EXCLUDED_PREFIXES:
        return False
    if prefix in ('tradingview', 'tv'):
        return True
    name = str(item.get('name') or '')
    return name not in _non_kline_names(prefix)

#: 目录前缀 → **KLine 上的访问器**（`.pta` / `.talib` / `.pine` …）
#:
#: ⚠ 目录里的 key 是 `pta_bbands` / `talib_SMA` 这种「前缀_名字」，而
#: `CoreIndicators(...).indicators.pta_bbands()` 返回的只是**裸 DataFrame**
#: （**没有 `PlotInfo`**）→ desk 以前拿不到样式，只能全部当副图 + 全是折线 ✗。
#: 真正带样式的入口是 `kline.pta.bbands()` / `kline.talib.SMA()` →
#: 返回 **`IndFrame` / `IndSeries`，带 `_plotinfo`**（overlap / isplot /
#: linestyle / bandstyle / signalstyle / tablestyle ✓）——和 miniqt 同源。
ACCESSOR_OF = {
    'pta': 'pta', 'tqta': 'tqta', 'tqfunc': 'tqfunc', 'ti': 'tulip',
    'btind': 'btind', 'talib': 'talib', 'finta': 'finta', 'pine': 'pine',
    'pair': 'pairtrading', 'factor': 'factors',
}

#: `line_dash` → Lightweight Charts 的 `LineStyle` 数值（0 实线 / 1 点 / 2 虚）
#: `LineDash` → Lightweight Charts 线型（0 实 / 1 点 / 2 虚 / 3 长虚 / 4 稀疏点）
#: ⚠ 必须覆盖 ``minibt.utils.LineDash`` 的**全部**取值 —— 少一个就会
#: 静默退回实线（以前 `dotdash` / `large_dashed` 就是画成实线的 ✗）
DASH_STYLE = {
    'solid': 0, 'dotted': 1, 'dot': 1, 'dashed': 2, 'dash': 2,
    'large_dash': 3, 'large-dash': 3, 'large_dashed': 3, 'large-dashed': 3,
    'longdash': 3, 'long_dash': 3, 'dashdot': 2, 'dotdash': 2,
    'dash_dot': 2, 'dot_dash': 2,
    'sparse_dotted': 4, 'sparse-dotted': 4, 'sparse_dot': 4,
}

#: 信号箭头形状（`SignalStyle.marker`）→ LWC 的 `shape`
MARKER_SHAPE = {
    'arrowup': 'arrowUp', 'arrow_up': 'arrowUp', 'triangleup': 'arrowUp',
    'triangle': 'arrowUp', 'triangle_dot': 'arrowUp',
    'arrowdown': 'arrowDown', 'arrow_down': 'arrowDown',
    'triangledown': 'arrowDown', 'inverted_triangle': 'arrowDown',
    'circle': 'circle', 'circle_dot': 'circle', 'circle_cross': 'circle',
    'circle_x': 'circle', 'circle_y': 'circle', 'dot': 'circle',
    'square': 'square', 'square_cross': 'square', 'square_x': 'square',
    'cross': 'square', 'asterisk': 'square', 'dash': 'square',
}

#: TradingView 组（`BtIndicator` 子类；计算时传 **KLine** ✓）
TRADINGVIEW_PREFIX = 'tv:'

#: 缓存文件（和别的 desk 数据放一起 ✓）
CACHE_FILE = os.path.join(os.path.expanduser('~'), '.minibt',
                          'desk_indicators.json')

#: 反射时忽略的参数名（框架内部）
_SKIP_PARAMS = {'self', 'source', 'data', 'df', 'index', 'replay',
                'isreplay', 'lines', 'overlap', 'isplot', 'category',
                'ismain', 'isresample', 'iscustom', 'plot_index', 'name'}

_LOCK = threading.Lock()
_MEMORY: Dict[str, Any] = {'items': None, 'stamp': None}

#: ★ 结构版本：**目录结构 / 分组 / 参数区间规则**变了就 +1，
#: 这样即使 minibt 版本号没动也不会命中旧缓存 ✓（P16 那次就是踩到这一点）
CATALOG_SCHEMA = 7

#: 名字一看就是**画在价格轴上**的指标（元数据缺失时兜底，比如 TuLip ✓）
_OVERLAY_NAMES = {
    'ma', 'sma', 'ema', 'wma', 'dema', 'tema', 'trima', 'kama', 'zlema',
    'hma', 'alma', 't3', 'vwma', 'vwap', 'rma', 'expma', 'dma', 'bias',
    'boll', 'bbands', 'bband', 'envelope', 'env', 'keltner', 'donchian',
    'dc', 'supertrend', 'sar', 'pmax', 'midpoint', 'midprice', 'avgprice',
    'hl2', 'hlc3', 'ohlc4', 'ichimoku', 'alligator', 'rngfilt', 'linreg',
    'linreg_slope', 'trendline', 'price', 'pricechannel', 'ma_envelope',
}


def _guess_overlay(name: str) -> bool:
    """主图叠加启发式（只在元数据说“不是”时兜底 ✓）"""
    key = str(name or '').strip().lower()
    if not key:
        return False
    if key in _OVERLAY_NAMES:
        return True
    # ma20 / ema5 / boll20 / sma60 …
    for token in ('ma', 'sma', 'ema', 'wma', 'dema', 'tema', 'boll', 'bbands'):
        rest = key[len(token):]
        if key.startswith(token) and rest.isdigit():
            return True
    for token in ('_ma', '_ema', '_sma', '_wma', '_boll', '_vwap', '_sar'):
        if key.endswith(token):
            return True
    return False

#: 信号线名字提示（`long_signal` / `short_signal` / `buy`…）
SIGNAL_HINTS = ('signal', 'arrow', 'marker', 'entry', 'exit', 'trigger',
                'buy', 'sell', 'long', 'short')

#: 买卖箭头颜色（和迷你 K 线图一致 ✓）
SIGNAL_BUY_COLOR = '#26a69a'
SIGNAL_SELL_COLOR = '#ef5350'


def minibt_version() -> str:
    try:
        import minibt
        return str(getattr(minibt, '__version__', '?'))
    except Exception:                                            # noqa: BLE001
        return '?'


def schema_stamp() -> str:
    """缓存版本 = minibt 版本 + **目录结构版本** + 库/分组定义 ✓"""
    parts = [
        minibt_version(),
        f'schema{CATALOG_SCHEMA}',
        ','.join(f'{prefix}:{name}:{label}' for prefix, name, label in LIBS),
        TRADINGVIEW_PREFIX,
        ','.join(SIGNAL_HINTS),
        ','.join(sorted(_SKIP_PARAMS)),
    ]
    return '|'.join(parts)


# ---------------------------------------------------------------- 目录
def catalog(refresh: bool = False) -> List[Dict[str, Any]]:
    """完整目录（带缓存；``refresh=True`` 强制重建 ✓）"""
    stamp = schema_stamp()
    with _LOCK:
        if not refresh and _MEMORY['items'] is not None \
                and _MEMORY['stamp'] == stamp:
            return _MEMORY['items']
    items = None if refresh else _read_cache(stamp)
    if items is None:
        items = _build()
        _write_cache(stamp, items)
    with _LOCK:
        _MEMORY['items'] = items
        _MEMORY['stamp'] = stamp
    return items


def entry(key: str) -> Optional[Dict[str, Any]]:
    """按 key（``pta_sma``）查目录项 ✓"""
    for item in catalog():
        if item['key'] == key:
            return item
    return None


def _build() -> List[Dict[str, Any]]:
    """构建完整目录（**miniqt 同源** ✓）

    `minibt.IndicatorClass` 的每个属性就是一个指标库（PandasTa / TqTa / …），
    `dir(库)` 里的 callable 就是指标 —— 和 `MiniBtInitWorker` 完全一致；
    拿不到 `IndicatorClass`（极旧版本）才退回模块反射 ✓
    """
    items: List[Dict[str, Any]] = []
    try:
        items.extend(_build_from_indicator_class())
    except Exception as error:                                   # noqa: BLE001
        print(f'[desk] IndicatorClass 枚举失败（退回模块反射）: {error!r}')
    # ★ 再补一遍模块反射（`IndicatorClass` 只暴露一部分，比如 TqFunc 12/27）
    seen = {item['key'] for item in items}
    try:
        for entry in _build_from_modules():
            if entry['key'] not in seen:
                seen.add(entry['key'])
                items.append(entry)
    except Exception as error:                                   # noqa: BLE001
        print(f'[desk] 模块反射失败: {error!r}')
    # ★ 最后一层兜底：直接枚举 `CoreIndicators(...).indicators`（compute 用的
    #   就是它）—— 前面两条路都失败时（用户实测「指标目录为空」✗）也能列出来
    seen_now = {item['key'] for item in items}
    try:
        for entry in _build_from_core():
            if entry['key'] not in seen_now:
                seen_now.add(entry['key'])
                items.append(entry)
    except Exception as error:                                   # noqa: BLE001
        print(f'[desk] CoreIndicators 枚举失败: {error!r}')
    tv = _tradingview_items()
    if tv:
        have = {item['key'] for item in items}
        items.extend([entry for entry in tv if entry['key'] not in have])
    else:
        try:
            _ensure_tradingview_names(items)      # 兜底：只有名字（无参数）
        except Exception:                                        # noqa: BLE001
            pass
    # ★ 最后统一过滤：Pair / Factors 是多合约专用；各库的数学 / 逻辑 /
    #   时间工具在 NON_KLINE_INDICATORS 里，不是可画的 K 线指标 ✓
    items = [item for item in items if _catalog_allowed(item)]
    items.sort(key=lambda item: (item['group'], item['name'].lower()))
    return items


#: 库类名 → **具体模块**（`minibt.indicators.xxx`）
#:
#: ⚠ 用户机器上出现过
#: ``ImportError: cannot import name 'CoreIndicators' from 'minibt.indicators'
#: (unknown location)`` —— 说明 `minibt.indicators` 是个**没加载成功的包**
#: （namespace package / `__init__` 没跑完）。所以这里一律**直接 import 子模块**
#: （`minibt.indicators.core` 之类），不依赖包级 `__init__` ✓
LIB_MODULES = {
    'PandasTa': 'pandas_ta',
    'TqTa': 'tqta',
    'TqFunc': 'tqfunc',
    'TuLip': 'tulip',
    'BtInd': 'btind',
    'TaLib': 'talib',
    'FinTa': 'finta',
    'Pair': 'pair',
    'Factors': 'factors',
    'Pine': 'pine',
    'TradingView': 'tradingview',
}


def _submodule(name: str):
    """`import minibt.indicators.<name>`（绕开包级 `__init__` ✓）

    再兜一层：**按文件路径加载**（`minibt/indicators/<name>.py`）——
    有的安装里 `minibt.indicators` 目录在、但 `.py` 没被装进去 / 包是 namespace
    形式，`import` 会报 `No module named 'minibt.indicators.xxx'`（用户实测 ✗）。
    """
    import importlib
    import importlib.util
    import os

    try:
        return importlib.import_module(f'minibt.indicators.{name}')
    except Exception as error:                                   # noqa: BLE001
        path = _module_file(name)
        if path is None:
            raise error
        # ★ 用**真实包名**注册进 sys.modules —— `core.py` 里有
        #   `from .factors import Factors` 这种相对导入，名字不对就会炸 ✗
        full = f'minibt.indicators.{name}'
        spec = importlib.util.spec_from_file_location(full, path)
        if spec is None or spec.loader is None:
            raise error
        cached = _FILE_MODULES.get(name)
        if cached is not None:
            return cached
        module = importlib.util.module_from_spec(spec)
        import sys as _sys
        previous = _sys.modules.get(full)
        _sys.modules[full] = module      # 相对导入（`from .factors import …`）需要 ✓
        try:
            spec.loader.exec_module(module)
        except Exception:                                        # noqa: BLE001
            if previous is not None:
                _sys.modules[full] = previous
            else:
                _sys.modules.pop(full, None)
            raise
        finally:
            # ⚠ 用完**还原**：别把 sys.modules 里的真模块换掉 ——
            #   否则 `BtIndicator` 变成两个不同的类，`issubclass` 全 False，
            #   TradingView 指标会整批消失（参数/overlap 也没了 ✗）
            if previous is not None:
                _sys.modules[full] = previous
            else:
                _sys.modules.pop(full, None)
        _FILE_MODULES[name] = module
        return module


def _module_file(name: str) -> Optional[str]:
    """找 `minibt/indicators/<name>.py` 的真实路径（安装不完整时也能用 ✓）"""
    import os

    folder = os.path.join(_minibt_root() or '', 'indicators')
    if not folder or not os.path.isdir(folder):
        return None
    for candidate in (f'{name}.py', os.path.join(name, '__init__.py')):
        path = os.path.join(folder, candidate)
        if os.path.isfile(path):
            return path
    return None


def _minibt_root() -> Optional[str]:
    """`minibt` 包所在目录（拿不到 → None）✓"""
    import os

    try:
        import minibt
        path = getattr(minibt, '__file__', None)
        if path:
            return os.path.dirname(os.path.abspath(path))
        paths = list(getattr(minibt, '__path__', []) or [])
        return os.path.abspath(paths[0]) if paths else None
    except Exception:                                            # noqa: BLE001
        return None


def _library(class_name: str):
    """取库类（PandasTa / TaLib / …）—— 多条路都试一遍 ✓"""
    # 1) 包级属性（正常情况最快）
    try:
        import minibt.indicators as package
        value = getattr(package, class_name, None)
        if value is not None:
            return value
    except Exception:                                            # noqa: BLE001
        pass
    # 2) 具体子模块（包 __init__ 坏了也能用 ✓）
    module_name = LIB_MODULES.get(class_name)
    if module_name:
        try:
            module = _submodule(module_name)
            value = getattr(module, class_name, None)
            if value is not None:
                return value
        except Exception as error:                               # noqa: BLE001
            _warn_install(error)
    # 3) `minibt` 顶层（`from minibt import PandasTa`）
    try:
        import minibt
        return getattr(minibt, class_name, None)
    except Exception:                                            # noqa: BLE001
        return None


def core_indicators():
    """取 `CoreIndicators` 类（**不**依赖包级 `__init__` ✓）"""
    try:
        from minibt.indicators import CoreIndicators
        return CoreIndicators
    except Exception:                                            # noqa: BLE001
        pass
    module = _submodule('core')            # ← 关键：直接进 `core.py`
    return getattr(module, 'CoreIndicators')


#: `minibt.IndicatorClass` 属性名 → (prefix, 中文标签)；顺序同 miniqt ✓
INDICATOR_CLASS_LIBS = {
    'PandasTa': ('pta', 'PandasTA'),
    'TqTa': ('tqta', '天勤TA'),
    'TqFunc': ('tqfunc', '天勤函数'),
    'TuLip': ('ti', 'TuLip'),
    'BtInd': ('btind', 'BtInd'),
    'TaLib': ('talib', 'TA-Lib'),
    'FinTa': ('finta', 'FinTa'),
    'Pair': ('pair', 'Pair'),
    'Factors': ('factor', 'Factors'),
}

#: miniqt 直接排除的库（`Pair`/`Factors`/`FinTa`/`TuLip` 不画在 K 线上）
#: —— desk 还是列出来（只是画的时候可能没线），和之前一致 ✓


def _build_from_indicator_class() -> List[Dict[str, Any]]:
    """用 `minibt.IndicatorClass` 枚举（miniqt `MiniBtInitWorker` 同源 ✓）"""
    import inspect

    import minibt

    root = getattr(minibt, 'IndicatorClass', None)
    if root is None:
        return []
    items: List[Dict[str, Any]] = []
    for attr_name in dir(root):
        if attr_name.startswith('_'):
            continue
        mapping = INDICATOR_CLASS_LIBS.get(attr_name)
        if mapping is None:
            continue
        prefix, label = mapping
        library = getattr(root, attr_name, None)
        if library is None:
            continue
        skip = set(getattr(library, 'NON_KLINE_INDICATORS', ()) or ())
        for name in dir(library):
            if name.startswith('_') or name in skip:
                continue
            func = getattr(library, name, None)
            if func is None or not callable(func):
                continue
            args = getattr(func, '_decorator_args', None) or {}
            overlap = args.get('overlap', False)
            if isinstance(overlap, dict):
                overlap = any(bool(value) for value in overlap.values())
            if not overlap:
                overlap = _guess_overlay(name)      # 元数据缺失时兜底 ✓
            items.append({
                'key': f'{prefix}_{name}',
                'prefix': prefix,
                'name': name,
                'label': f'{name} · {label}',
                'group': label,
                'overlap': bool(overlap),
                'params': _params_of(func),
            })
    return items


def _ensure_tradingview_names(items: List[Dict[str, Any]]) -> None:
    """把 TradingView 的指标名也补上（若 `_tradingview_items()` 掏不到类 ✓）

    只在 `TradingView` 门面上有、但模块里反射不到时用（给个「名字 + 参数」占位）。
    """
    known = {item['key'] for item in items if item['group'] == 'TradingView'}
    if known:
        return
    try:
        facade = getattr(_submodule('tradingview'), 'TradingView')
    except Exception as error:                                   # noqa: BLE001
        print(f'[desk] TradingView 门面导入失败: {error!r}')
        return
    for name in dir(facade):
        if name.startswith('_'):
            continue
        func = getattr(facade, name, None)
        if func is None or not callable(func):
            continue
        items.append({
            'key': f'{TRADINGVIEW_PREFIX}{name}',
            'prefix': 'tradingview',
            'name': name,
            'label': f'{name} · TradingView',
            'group': 'TradingView',
            'overlap': _guess_overlay(name),
            'params': [],
        })


def _build_from_modules() -> List[Dict[str, Any]]:
    """老路：反射 `minibt.indicators.<类>`（`IndicatorClass` 不可用时才走 ✓）"""
    items: List[Dict[str, Any]] = []
    for prefix, class_name, label in LIBS:
        library = _library(class_name)
        if library is None:
            continue
        for name, func in vars(library).items():
            if name.startswith('_') or not callable(func):
                continue
            if not hasattr(func, '_decorator_args'):
                continue
            overlap = func._decorator_args.get('overlap', False)  # noqa: SLF001
            if isinstance(overlap, dict):
                overlap = any(bool(value) for value in overlap.values())
            if not overlap:
                overlap = _guess_overlay(name)
            items.append({
                'key': f'{prefix}_{name}',
                'prefix': prefix,
                'name': name,
                'label': f'{name} · {label}',
                'group': label,
                'overlap': bool(overlap),
                'params': _params_of(func),
            })
    return items


def _tradingview_items() -> List[Dict[str, Any]]:
    """`BtIndicator` 子类（minibt 的 TradingView 指标库 ✓）"""
    try:
        import inspect
        module = _submodule('tradingview')
        BtIndicator = getattr(_submodule('core'), 'BtIndicator')
    except Exception:                                            # noqa: BLE001
        return []
    items = []
    for name, cls in sorted(vars(module).items()):
        if not inspect.isclass(cls) or cls is BtIndicator:
            continue
        if not issubclass(cls, BtIndicator):
            continue
        if getattr(cls, '__module__', '') != module.__name__:
            continue
        params = []
        for param_name, default in (getattr(cls, 'params', {}) or {}).items():
            safe = _jsonable(default)
            if safe is _SKIP:
                continue
            kind = ('float' if isinstance(safe, float)
                    else ('int' if isinstance(safe, int)
                          and not isinstance(safe, bool)
                          else ('bool' if isinstance(safe, bool) else 'str')))
            param = {'name': str(param_name), 'default': safe, 'type': kind}
            if kind == 'int':
                param.update(min=max(1, int(safe)), max=max(int(safe) * 4, 100),
                             step=1)
            elif kind == 'float':
                param.update(min=0.0, max=max(abs(float(safe)) * 4, 10.0),
                             step=0.1)
            params.append(param)
        doc = (inspect.getdoc(cls) or '').strip().split('\n')[0][:80]
        overlap = bool(getattr(cls, 'overlap', False)) or _guess_overlay(name)
        items.append({
            'key': f'{TRADINGVIEW_PREFIX}{name}',
            'prefix': 'tradingview',
            'name': name,
            'label': f'{name} · TradingView',
            'group': 'TradingView',
            'overlap': overlap,
            'params': params,
            'desc': doc,
            'kind': 'class',
        })
    return items


def _params_of(func) -> List[Dict[str, Any]]:
    target = getattr(func, '__wrapped__', func)
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        return []
    params = []
    for name, parameter in signature.parameters.items():
        if name in _SKIP_PARAMS or name.startswith('_'):
            continue
        if parameter.kind in (inspect.Parameter.VAR_POSITIONAL,
                             inspect.Parameter.VAR_KEYWORD):
            continue
        default = parameter.default
        if default is inspect.Parameter.empty:
            continue
        default = _jsonable(default)
        if default is _SKIP:
            continue                     # 默认值是个类/对象 → 没法填表单 ✗
        kind = 'float' if isinstance(default, float) else (
            'int' if isinstance(default, int) and not isinstance(default, bool)
            else ('bool' if isinstance(default, bool) else 'str'))
        param = {'name': name, 'default': default, 'type': kind}
        # ★ 参数区间（模板 / 参数优化入口用 ✓）
        if kind == 'int':
            param.update(min=max(1, int(default)), max=max(int(default) * 4, 100),
                         step=1)
        elif kind == 'float':
            param.update(min=0.0, max=max(abs(float(default)) * 4, 10.0),
                         step=0.1)
        params.append(param)
    return params


#: 标记：默认值不可 JSON 化
_SKIP = object()


def _jsonable(value):
    """默认值 → 能在 JSON 里传的原语（numpy 标量也转 ✓）"""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        import numpy as np
        if isinstance(value, np.generic):
            return value.item()
    except Exception:                                            # noqa: BLE001
        pass
    return _SKIP


def defaults(item: Dict[str, Any]) -> Dict[str, Any]:
    return {param['name']: param['default'] for param in item.get('params', [])}


# ---------------------------------------------------------------- 计算
def compute(frame, keys: List[str],
            params: Optional[Dict[str, Dict[str, Any]]] = None,
            limit: int = 600) -> List[Dict[str, Any]]:
    """按目录 key 算指标（返回 `indicator.ts` 的 items ✓）

    Args:
        frame: K 线 DataFrame（需含 ``datetime`` / OHLCV）
        keys: ``['pta_sma', 'tqta_BOLL']``
        params: ``{'pta_sma': {'length': 20}}``（缺省 → 目录默认值）
    """
    import numpy as np

    if frame is None or len(frame) == 0 or not keys:
        return []
    CoreIndicators = core_indicators()

    stamps = _stamps(frame)
    core = CoreIndicators(frame)
    calculator = getattr(core, 'indicators', core)
    kline = None
    last_error = None
    output: List[Dict[str, Any]] = []
    for key in keys:
        item = entry(key)
        if item is None:
            continue
        if str(key).startswith(TRADINGVIEW_PREFIX):
            # ★ TradingView 指标需要 KLine（不是裸 DataFrame ✓）
            if kline is None:
                kline = _kline_of(frame)
            values = {param['name']: param['default']
                      for param in item.get('params', [])}
            values.update((params or {}).get(key) or {})
            if kline is None:
                continue
            try:
                result = _tv_class(key)(kline, **values)
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] TradingView 指标 {key} 计算失败: {error!r}')
                continue
            # TradingView 指标（minibt 内置）也带 `PlotInfo` —— 主/副图、色带、
            # 信号箭头、统计表全在它身上（用户要求按样式加载 ✓）
            output.extend(_to_items(key, item, _pandas_of(result), stamps, np,
                                    limit, frame,
                                    getattr(result, '_plotinfo', None)))
            continue
        overrides = (params or {}).get(key) or {}
        values = {**defaults(item), **overrides}
        # ★ 优先走 `kline.<访问器>.<名字>()` —— 只有它返回**带 `PlotInfo`** 的
        #   `IndFrame`（主/副图、线型、色带、信号、表格全在里面 ✓）；
        #   `CoreIndicators(...).indicators.xxx()` 是裸 DataFrame（没样式 ✗）
        result = None
        if kline is None:
            kline = _kline_of(frame)       # 带 PlotInfo 的计算入口要它 ✓
        for call in (_plotinfo_calls(kline, key, values),
                     _plain_calls(calculator, key, values)):
            for function in call:
                try:
                    result = function()
                except Exception as error:                       # noqa: BLE001
                    result = None
                    last_error = error
                    continue
                if result is not None:
                    break
            if result is not None:
                break
        if result is None:
            print(f'[desk] 指标 {key} 计算失败: {last_error!r}')
            continue
        plotinfo = getattr(result, '_plotinfo', None)
        output.extend(_to_items(key, item, result, stamps, np, limit, frame,
                                plotinfo))
    return output


def _split_key(key: str):
    """``pta_bbands`` → ``('pta', 'bbands')``（前缀 + 指标名 ✓）"""
    text = str(key)
    for prefix in sorted(ACCESSOR_OF, key=len, reverse=True):
        if text.startswith(prefix + '_'):
            return prefix, text[len(prefix) + 1:]
    return '', text


def _plotinfo_calls(kline, key: str, values: Dict[str, Any]) -> List[Any]:
    """走 KLine 访问器（**带 `PlotInfo`** 的唯一入口 ✓）

    例：``pta_bbands`` → ``kline.pta.bbands(**values)``
    """
    if kline is None:
        return []
    prefix, name = _split_key(key)
    accessor = ACCESSOR_OF.get(prefix)
    if not accessor or not name:
        return []
    group = getattr(kline, accessor, None)
    function = getattr(group, name, None)
    if not callable(function):
        return []

    def call():
        return function(**values)

    return [call]


def _plain_calls(calculator, key: str, values: Dict[str, Any]) -> List[Any]:
    """老路：裸 DataFrame（**没有 PlotInfo**，只在访问器不可用时兜底 ✓）"""
    function = getattr(calculator, key, None)
    if not callable(function):
        return []

    def call():
        return function(**values)

    return [call]


def _line_style(plotinfo, name: str) -> Dict[str, Any]:
    """取某根线的 `LineStyle`（`PlotInfo.linestyle[name]` ✓）"""
    styles = getattr(plotinfo, 'linestyle', None) or {}
    try:
        style = styles.get(name) if hasattr(styles, 'get') else styles[name]
    except Exception:                                            # noqa: BLE001
        style = None
    if style is None:
        return {}
    return {key: getattr(style, key, None)
            for key in ('line_dash', 'line_width', 'line_color', 'vbar_base',
                        'vbar_up_color', 'vbar_down_color', 'vbar_color_base',
                        'price_line', 'price_label')}


def _per_line(value, name: str, index: int, default=None):
    """`PlotInfo.overlap` / `isplot` 三种写法都支持 ✓

    ``True/False``（全体）· ``{'线名': bool}``（按名）· ``[bool, ...]``（按序）
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return value.get(name, default)
    if isinstance(value, (list, tuple)):
        return value[index] if index < len(value) else default
    return bool(value)


def _iter_styles(raw) -> List[Any]:
    """`BandList` / `SpanList` / 单个对象 / dict → ``[对象, ...]`` ✓"""
    if raw is None:
        return []
    if isinstance(raw, dict):
        return list(raw.values())
    vars_ = getattr(raw, 'vars', None)
    if isinstance(vars_, dict):
        return list(vars_.values())
    if isinstance(raw, (list, tuple, set)):
        return list(raw)
    return [raw]


def _style_of(style, *keys):
    """按多个别名取样式字段（`fill_color` / `line_color` …）✓"""
    for key in keys:
        value = getattr(style, key, None)
        if value not in (None, ''):
            return value
    return None


def _rgba(color: str, alpha: float) -> str:
    """`#rrggbb` + alpha → `rgba(...)`（LWC 的填充色要带透明度 ✓）"""
    text = str(color or '').strip()
    try:
        alpha = max(0.0, min(1.0, float(alpha)))
    except (TypeError, ValueError):
        alpha = 0.15
    if text.startswith('#') and len(text) in (7, 4):
        if len(text) == 4:
            text = '#' + ''.join(char * 2 for char in text[1:])
        try:
            red = int(text[1:3], 16)
            green = int(text[3:5], 16)
            blue = int(text[5:7], 16)
            return f'rgba({red},{green},{blue},{alpha:.3f})'
        except ValueError:
            pass
    return text


def _signal_color(label: str, index: int, colors) -> str:
    """信号线配色：买 / 多 → 绿，卖 / 空 → 红，其它轮转 ✓"""
    name = str(label).lower()
    if any(hint in name for hint in ('long', 'buy', 'bull', 'up')):
        return SIGNAL_BUY_COLOR
    if any(hint in name for hint in ('short', 'sell', 'bear', 'down')):
        return SIGNAL_SELL_COLOR
    return colors[index % len(colors)]


def _is_signal_line(label: str, values: List[float]) -> bool:
    """是不是**信号列**（`long_signal` / `short_signal` / `buy`…）

    两道门槛：名字里有信号提示词 **且** 取值是离散的少数状态
    （1 / -1 / 0、100 / -100、形态编号…）→ 当箭头画 ✓
    """
    name = str(label).lower()
    if not any(hint in name for hint in SIGNAL_HINTS):
        return False
    distinct = {round(float(value), 6) for value in values
                if value is not None}
    distinct.discard(0.0)
    if not distinct or len(distinct) > 24:
        return False
    return True


def _signal_markers(values: List[List[float]], frame,
                    above: Optional[bool] = None,
                    name: str = '',
                    size: Optional[int] = None,
                    glyph: Optional[str] = None,
                    label_size: Optional[int] = None,
                    label_color: Optional[str] = None) -> List[Dict[str, Any]]:
    """信号值 → LWC markers

    ``above`` 为 ``None`` 时按取值符号判断（正=下方买 / 负=上方卖）；
    指标用 ``SignalStyle.key`` 声明了位置就以它为准 ✓
    """
    markers: List[Dict[str, Any]] = []
    highs: Dict[int, float] = {}
    lows: Dict[int, float] = {}
    if frame is not None:
        try:
            for stamp, high, low in zip(_stamps(frame),
                                        frame['high'].tolist(),
                                        frame['low'].tolist()):
                highs[int(stamp)] = float(high)
                lows[int(stamp)] = float(low)
        except Exception:                                        # noqa: BLE001
            highs, lows = {}, {}
    for stamp, value in values:
        stamp = int(stamp)
        if not value or value != value:          # 0 / NaN = 没有信号 ✓
            continue
        # ★ 方向优先看**信号名**：`short_signal` 的值也是 +1，
        #   只按正负判断会把空头画成向上箭头 ✗
        low = str(name or '').lower()
        if any(word in low for word in ('short', 'sell', 'exit')):
            buy = False if above is None else (not above)
        elif any(word in low for word in ('long', 'buy')):
            # `long_signal` 一般是 0/1；但也兼容 -1 = 空头信号 ✓
            # （以前这里一律 buy=True，负数也画成买 ✗）
            buy = value > 0 if above is None else (not above)
        else:
            buy = value > 0 if above is None else (not above)
        price = lows.get(stamp) if buy else highs.get(stamp)
        markers.append({
            'time': stamp,
            'position': 'belowBar' if buy else 'aboveBar',
            'shape': 'arrowUp' if buy else 'arrowDown',
            'color': SIGNAL_BUY_COLOR if buy else SIGNAL_SELL_COLOR,
            'text': 'B' if buy else 'S',
            'price': price,
            'buy': buy,
            'size': size,          # `SignalStyle(size=8)` ✓
            # 自定义序列的 glyph：`arrow_up` / `triangle` / `inverted_triangle`…
            'glyph': (str(glyph).strip() if glyph else
                      ('arrow_up' if buy else 'arrow_down')),
            'textSize': label_size,
            'textColor': label_color,
        })
    return markers


def _candle_item(columns, matrix, stamps, item, plotinfo, key, np):
    """四列 OHLC → 蜡烛型指标（`candlestyle` 配色 ✓）

    `btplot`/bokeh 一直支持"蜡烛型指标"（如 Heikin-Ashi、CDV），desk 之前
    **没有渲染** → 加了指标却一根线都不画（用户实测 ✗）。这里把
    `open/high/low/close` 四列转成前端能画的 `kind='candles'`。

    判定：列名（不区分大小写、去掉前缀）同时含 open/high/low/close ✓
    """
    try:
        names = [str(column).strip().lower() for column in columns]
    except Exception:                                            # noqa: BLE001
        return None
    index: Dict[str, int] = {}
    for position, name in enumerate(names):
        short = name.split('.')[-1].split('_')[-1]
        for want in ('open', 'high', 'low', 'close'):
            if want in index:
                continue
            if short == want or name == want or name.endswith('.' + want):
                index[want] = position
    if len(index) < 4:
        return None
    style = getattr(plotinfo, 'candlestyle', None)
    bull = str(getattr(style, 'bull', '') or '') or '#26a69a'
    bear = str(getattr(style, 'bear', '') or '') or '#ef5350'
    rows = matrix.shape[0]
    offset = max(0, len(stamps) - rows)
    data: List[list] = []
    for row in range(rows):
        position = offset + row
        if position >= len(stamps):
            break
        try:
            o = float(matrix[row][index['open']])
            h = float(matrix[row][index['high']])
            lo = float(matrix[row][index['low']])
            c = float(matrix[row][index['close']])
        except (TypeError, ValueError, IndexError):
            continue
        if o != o or c != c:                     # NaN
            continue
        data.append([stamps[position], [o, h, lo, c]])
    if not data:
        return None
    return {
        'key': f'{key}:candles',
        'label': str(item.get('name') or key),
        'kind': 'candles',
        'overlay': bool(item.get('overlap')),
        # ⚠ 叠加主图时 `pane` 必须和其它主图指标一致（空/同名都行，
        #   前端按 `overlay → paneIndex 0` 处理 ✓）
        'pane': '' if item.get('overlap') else str(item.get('name') or key),
        'color': bull,
        'upColor': bull,
        'downColor': bear,
        'priceLine': False,
        'priceLabel': False,
        'legend': True,
        'source': key,
        'data': data,               # [time, [open, high, low, close]] ✓
    }


#: VP 横条的"满量程"按多少根 K 线宽算（`profile_frac × 它` = 最长那档 ✓）
VP_SPAN_BARS = 60


def _vp_item(columns, matrix, stamps, frame, item, plotinfo, key, np):
    """成交量分布（Volume Profile）→ `shapeRows` 里的**横向矩形条** ✓

    minibt 的约定（`RollingVolumeProfile` / `VPStyle`）：

    * 指标输出 ``(K 线根数, 档数)`` 的矩阵，列 = 等宽价格档；
    * 第 i 行的价格区间 = ``[min(low[i-price_bars+1:i+1]), max(high[...])]``，
      第 j 档中心 = ``lo + (j + 0.5) * (hi - lo) / N``；
    * 位置固定在**可视最右端**（这里画在**最后一根 K 线**上），向左生长。

    配色/尺寸全部取 `vpstyle`（`bar_color` / `poc_color` / `fill_alpha` /
    `bin_ratio` / `profile_frac` / `line_color` / `line_width`）✓
    """
    try:
        names = [str(column).strip().lower() for column in columns]
    except Exception:                                            # noqa: BLE001
        return None
    category = str(getattr(plotinfo, 'category', '') or '').strip().lower()
    looks_vp = category == 'vp' or (
        names and all(name.startswith('vp') for name in names[:3]))
    if not looks_vp or matrix.shape[1] < 2:
        return None
    bins = int(matrix.shape[1])
    if not len(stamps):
        return None
    try:
        from ..utils import vp_style_values
        style = vp_style_values(getattr(plotinfo, 'vpstyle', None))
    except Exception:                                            # noqa: BLE001
        style = {'bar_color': '#3498db', 'poc_color': '#f39c12',
                 'highlight_poc': True, 'fill_alpha': 0.6,
                 'line_color': 'white', 'line_width': 0.4,
                 'profile_frac': 0.30, 'bin_ratio': 0.88,
                 'price_bars': None}
    price_bars = style.get('price_bars') or 120
    row = matrix.shape[0] - 1
    lo = hi = None
    try:
        window = frame.iloc[max(0, row - int(price_bars) + 1):row + 1]
        lo = float(window['low'].min())
        hi = float(window['high'].max())
    except Exception:                                            # noqa: BLE001
        lo = hi = None
    if lo is None or hi is None or not (hi > lo):
        return None
    try:
        values = [float(value) for value in matrix[row]]
    except Exception:                                            # noqa: BLE001
        return None
    peak = max(values) if values else 0.0
    if peak <= 0:
        return None
    p_uniform = (hi - lo) / bins
    bar_color = str(style.get('bar_color') or '#3498db')
    poc_color = str(style.get('poc_color') or '#f39c12')
    alpha = float(style.get('fill_alpha') or 0.6)
    border = style.get('line_color')
    border_width = float(style.get('line_width') or 0.4)
    frac = float(style.get('profile_frac') or 0.30)
    bin_ratio = float(style.get('bin_ratio') or 0.88)

    _NAMED = {
        'skyblue': (135, 206, 235), 'orange': (255, 165, 0),
        'lime': (0, 255, 0), 'tomato': (255, 99, 71),
        'white': (255, 255, 255), 'red': (255, 0, 0),
        'green': (0, 128, 0), 'blue': (0, 0, 255),
        'gold': (255, 215, 0), 'steelblue': (70, 130, 180),
        'gray': (128, 128, 128), 'grey': (128, 128, 128),
    }

    def _rgba(color: str) -> str:
        text = str(color or '').strip()
        named = _NAMED.get(text.lower())
        if named:
            return f'rgba({named[0]}, {named[1]}, {named[2]}, {alpha:.2f})'
        if text.startswith('#') and len(text) == 7:
            try:
                r = int(text[1:3], 16)
                g = int(text[3:5], 16)
                b = int(text[5:7], 16)
                return f'rgba({r}, {g}, {b}, {alpha:.2f})'
            except ValueError:
                return text
        return text

    peak_index = values.index(peak)
    shapes: List[Dict[str, Any]] = []
    for index, value in enumerate(values):
        if value <= 0:
            continue
        center = lo + (index + 0.5) * p_uniform
        half = p_uniform * bin_ratio / 2.0
        # 宽度：`profile_frac` × **固定可视跨度（约 60 根）** × 量占比
        # （以前按档数算出来只有 0.1 根宽 → 看着像小刻度 ✗）
        width = max(1.5, frac * float(VP_SPAN_BARS) * (value / peak))
        color = (_rgba(poc_color)
                 if style.get('highlight_poc', True) and index == peak_index
                 else _rgba(bar_color))
        shape = {'type': 'rect', 'from': center - half, 'to': center + half,
                 'left': -width, 'right': 0.0, 'fillColor': color}
        if border and border_width:
            shape['borderColor'] = str(border)
            shape['borderWidth'] = max(0.1, border_width)
        shapes.append(shape)
    if not shapes:
        return None
    # ★ 整张矩阵 + 每根的滚动档区（`[lo, hi]`）一起下发：
    #   前端要画"**鼠标所在那根**的分布"（minibt `_vp_interactive` 同款 ✓），
    #   只发最后一行是做不到的 ✗
    try:
        import numpy as _np
        _lows = frame['low'].to_numpy(dtype=float)
        _highs = frame['high'].to_numpy(dtype=float)
        _n = int(matrix.shape[0])
        _lo_arr = [_np.nanmin(_lows[max(0, i - int(price_bars) + 1):i + 1])
                   for i in range(min(_n, len(_lows)))]
        _hi_arr = [_np.nanmax(_highs[max(0, i - int(price_bars) + 1):i + 1])
                   for i in range(min(_n, len(_highs)))]
    except Exception:                                            # noqa: BLE001
        _lo_arr, _hi_arr = [], []
    return {
        'key': f'{key}:vp',
        'label': str(item.get('name') or key),
        'kind': 'vp',            # ★ 前端特殊处理：贴**可视范围右边缘** ✓
        'overlay': True,               # 叠在主图右侧 ✓
        'pane': '',
        'color': bar_color,
        'data': [],
        'markers': [],
        'shapeRows': [{'time': int(stamps[-1]), 'value': float(lo + (hi - lo) / 2),
                       'shapes': shapes}],
        # ★ VP 自绘层（前端 canvas，贴右边缘 + 鼠标跟随 ✓）
        'vpMatrix': [[float(v) for v in row] for row in matrix.tolist()],
        'vpLo': [float(v) for v in _lo_arr],
        'vpHi': [float(v) for v in _hi_arr],
        'vpStyle': dict(style),
        'vpBars': int(price_bars),
    }


def _signal_shape_rows(markers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """LWC 原生 marker → **自定义序列**的数据行（`minibt.markers.Markers` ✓）

    输出 ``[{time, value, shapes: [{type:'marker', marker:'triangle', …}]}]``，
    和回测图 `apply_signals` 用的格式一致 —— 缩放跟手、回放能截断 ✓
    """
    try:
        from ..markers import Markers
    except Exception:                                            # noqa: BLE001
        return []
    payload = []
    for marker in markers or []:
        price = marker.get('price')
        if price is None:
            continue
        payload.append({
            'time': marker.get('time'),
            'price': price,
            'up': bool(marker.get('buy', True)),
            'color': marker.get('color'),
            'text': marker.get('text') or '',
            'size': int(marker.get('size') or 0),      # `SignalStyle(size=…)` ✓
            'shape': marker.get('glyph'),              # `SignalStyle.marker` ✓
            'textSize': marker.get('textSize'),        # `set_label("B", 14)` ✓
            'textColor': marker.get('textColor'),
        })
    return Markers.series(payload)


def _to_items(key: str, item: dict, result, stamps: List[int], np,
              limit: int, frame=None, plotinfo=None) -> List[Dict[str, Any]]:
    """Series / DataFrame / ndarray → 若干条线（**按 `PlotInfo` 出样式** ✓）

    `PlotInfo` 决定的东西（和 miniqt 看盘窗口完全一致）：

    * ``overlap``：``True`` → **主图叠加**（画在 K 线上）/ ``False`` → 副图；
      也支持 ``{'线名': bool}`` → 同一指标**有的线在主图、有的在副图** ✓
    * ``isplot``：``False`` 的列**不画**（只是数据列）✓
    * ``linestyle[name]``：颜色 / 线宽 / ``line_dash``
      （``vbar`` → **柱状**，也带 `vbar_base` / 涨跌色）✓
    * ``bandstyle``：两条线之间**填充**（`kind: 'band'`）✓
    * ``signalstyle``：信号线 → **买卖箭头** ✓
    * ``tablestyle``：指标自带统计表（`kind: 'table'`）✓
    """
    colors = ('#f6c343', '#2196f3', '#e91e63', '#26a69a', '#9c27b0',
              '#ff9800', '#00bcd4', '#8bc34a')
    columns: List[str] = []
    matrix = None
    if hasattr(result, 'columns'):                     # DataFrame
        columns = [str(column) for column in result.columns]
        matrix = result.to_numpy()
    elif isinstance(result, np.ndarray):
        matrix = result if result.ndim == 2 else result.reshape(-1, 1)
    elif hasattr(result, 'to_numpy'):                  # Series
        matrix = result.to_numpy().reshape(-1, 1)
    else:
        return []
    if matrix is None or not len(matrix):
        return []
    lines = [str(name) for name in (getattr(plotinfo, 'lines', None) or [])]
    # ★ **蜡烛型指标**：四列 open/high/low/close → 一条 `kind='candles'`
    #   （配色取 `candlestyle.bull / bear`，没配就跟随主题 ✓）
    candle = _candle_item(columns, matrix, stamps, item, plotinfo, key, np)
    if candle is not None:
        return [candle]
    # ★ **成交量分布**（`category='vp'` / `vp0..vpN` 列）→ 横向直方图（画在柱上）
    vp = _vp_item(columns, matrix, stamps, frame, item, plotinfo, key, np)
    if vp is not None:
        return [vp]
    pane_name = str(item.get('name') or key)
    rows = matrix.shape[0]
    offset = max(0, len(stamps) - rows)                # 尾部对齐 ✓
    out: List[Dict[str, Any]] = []
    series_by_name: Dict[str, List[list]] = {}
    # `isplot=False` 的列是**纯数据列**、不画 ✓；但有的指标（AutoChartPatterns
    # 这类只在 `signalstyle` 里画图形的）**所有列**都是 False —— 那时一根线都
    # 不画等于「点了没反应」✗，所以全 False 时退回「都画」✓
    plot_flags = []
    for index in range(matrix.shape[1]):
        label = columns[index] if index < len(columns) else item['name']
        style_name = label if label in lines else (
            lines[index] if index < len(lines) else label)
        plot_flags.append(_per_line(getattr(plotinfo, 'isplot', None),
                                    style_name, index, True) is not False)
    if not any(plot_flags):
        plot_flags = [True] * matrix.shape[1]
    for index in range(matrix.shape[1]):
        label = columns[index] if index < len(columns) else item['name']
        # `PlotInfo` 的线名和列名可能差一个 `_` 前缀（`line_filed` = `_xxx` ✓）
        style_name = label if label in lines else (
            lines[index] if index < len(lines) else label)
        # ★ `isplot=False` 的**信号列**仍然要处理：它们是箭头载体，
        #   不是普通折线（ScalpingPullBackTool 的 long_signal/short_signal ✓）。
        #   以前这里先 continue，导致 `signalstyle` 完全失效 ✗。
        series: List[list] = []
        for row in range(rows):
            try:
                number = float(matrix[row][index])
            except (TypeError, ValueError, IndexError):
                number = None
            position = offset + row
            if position >= len(stamps):
                break
            # ★ NaN 也要保留成空白点：LWC 只有看到 `{time}` 才断线；
            #   直接丢掉会让缺口两边连起来（Chandelier_Exit 等指标 ✗）
            if number is None or number != number:
                series.append([stamps[position], None])
                continue
            series.append([stamps[position], number])
        if not series:
            continue
        name = f'{item["name"]}.{label}' if len(columns) > 1 else item['name']
        style = _line_style(plotinfo, style_name) if plotinfo is not None else {}
        dash = str(style.get('line_dash') or '').strip().lower()
        color = style.get('line_color') or _signal_color(label, index, colors)
        width = style.get('line_width')
        overlay = _per_line(getattr(plotinfo, 'overlap', None), style_name,
                            index, bool(item.get('overlap')))
        trimmed = series[-int(limit):]
        series_by_name[style_name] = trimmed
        base = {
            'key': f'{key}:{label}',
            'label': name,
            'overlay': bool(overlay),
            'pane': pane_name,          # 同一指标的线共用一个 pane ✓
            'color': color,
            'lineWidth': max(1, int(round(float(width or 1.3)))),
            'lineStyle': DASH_STYLE.get(dash, 0),
            'seriesName': style_name,
            # `LineStyle.price_line/price_label`：右侧价格线 / 价格标签 ✓
            'priceLine': bool(style.get('price_line', True)),
            'priceLabel': bool(style.get('price_label', True)),
            # `PlotInfo.legend`：False 时不生成图例行（线照样画 ✓）
            'legend': _per_line(getattr(plotinfo, 'legend', None),
                                style_name, index, True) is not False,
            # ★ 删菜单按「指标」分组（一个指标可能有好几条线 ✓）
            'source': key,
        }
        # ---- 信号列：`SignalStyle` 指到的线 → 买卖箭头 ✓
        declared = _signal_style_of(plotinfo, style_name)
        heuristic = _is_signal_line(label, [value for _, value in trimmed])
        if declared or heuristic:
            markers = _signal_markers(trimmed, frame,
                                      declared.get('above'), str(label),
                                      declared.get('size'),
                                      declared.get('marker'),
                                      declared.get('label_size'),
                                      declared.get('label_color'))
            texts = _signal_texts_of(plotinfo, style_name, rows, offset, stamps)
            fixed = declared.get('text') or ''
            for marker in markers:
                marker['shape'] = declared.get('shape') or marker['shape']
                marker['color'] = declared.get('color') or marker['color']
                # 逐点文字 > `SignalStyle.label` 固定文字 > 默认 B/S ✓
                marker['text'] = (texts.get(int(marker['time']))
                                  or fixed or marker.get('text') or '')
            # ★ 信号列**永远**只当箭头：`SignalStyle` 声明了就算一条信号都没有
            #   也不画线（以前没有箭头时会退化成一条 0/1 的平线 ✗）
            # ★ 用**自定义序列**画（`kind='shapes'`）而不是 LWC 原生 marker：
            #   原生 marker 不计入缩放、回放截不掉（用户实测 ✗）
            # 自定义序列的数据行（前端支持 `kind='shapes'` 后直接切过去 ✓）
            # ⚠ 变量别叫 `rows`：上面 `rows = matrix.shape[0]` 是循环上界 ✗
            shape_rows = _signal_shape_rows(markers)
            out.append({**base, 'kind': 'marker', 'overlay': True,
                        'pane': 'main',        # 箭头永远在主图 ✓
                        'markers': markers,    # 原生 marker（当前前端用）
                        'shapeRows': shape_rows,   # 自定义序列行（前端切 shapes 用 ✓）
                        'data': []})
            continue
        if not plot_flags[index]:
            continue                                   # 普通数据列 → 不画 ✓
        # ---- `line_dash='vbar'` → 柱状（MACD 柱 / 成交量 ✓）
        if dash in ('vbar', 'bar', 'histogram', 'column'):
            hist = dict(base)
            hist['kind'] = 'hist'
            hist['base'] = _num_or(style.get('vbar_base'), 0.0)
            # 没配涨跌色 → 留空，前端按主题的涨/跌色上色（和 miniqt 一致 ✓）
            hist['upColor'] = style.get('vbar_up_color') or None
            hist['downColor'] = style.get('vbar_down_color') or None
            hist['data'] = trimmed
            out.append(hist)
            continue
        out.append({**base, 'kind': 'line', 'data': trimmed})
    # ---- `bandstyle`：两条线之间填充 ✓
    for band in _iter_styles(getattr(plotinfo, 'bandstyle', None)):
        lower = str(_style_of(band, 'lower', 'lower_line') or '')
        upper = str(_style_of(band, 'upper', 'upper_line') or '')
        if not lower or not upper:
            continue
        if not series_by_name.get(lower) or not series_by_name.get(upper):
            continue                              # 两端都画出来才填 ✓
        try:
            alpha = float(_style_of(band, 'fill_alpha', 'alpha') or 0.15)
        except (TypeError, ValueError):
            alpha = 0.15
        out.append({
            'key': f'{key}:band:{lower}:{upper}',
            'label': f'{item["name"]} 色带',
            'kind': 'band',
            'overlay': bool(_per_line(getattr(plotinfo, 'overlap', None),
                                      upper, 0, True)),
            'pane': pane_name,
            'color': _rgba(_style_of(band, 'fill_color', 'color') or '#4682B4',
                           alpha),
            'lowerKey': f'{key}:{_column_of(columns, lower)}',
            'upperKey': f'{key}:{_column_of(columns, upper)}',
            'data': [],
        })
    # ---- `spanstyle`：水平参考线（0 / 30 / 70 这种 ✓）
    spans = _spans_of(plotinfo)
    if spans:
        overlay = _per_line(getattr(plotinfo, 'overlap', None), '', 0,
                            bool(item.get('overlap')))
        out.append({
            'key': f'{key}:span',
            'label': f'{item["name"]} 参考线',
            'kind': 'span',
            'overlay': bool(overlay),
            'pane': pane_name,
            'color': spans[0].get('color') or '',
            'source': key,
            'spans': spans,
            'data': [],
        })
    # ---- `watermark`：图表大水印 ✓
    mark = getattr(plotinfo, 'watermark', None)
    text = str(getattr(mark, 'text', '') or '').strip() if mark else ''
    if text:
        out.append({
            'key': f'{key}:watermark',
            'label': text,
            'kind': 'watermark',
            'overlay': True,
            'pane': '',
            'color': '',
            'fontSize': int(_num_or(getattr(mark, 'font_size', 44), 44)),
            'source': key,
            'data': [],
        })
    # ---- `tablestyle`：指标自带统计表 ✓
    table = _table_of(plotinfo, item, key)
    if table:
        out.append(table)
    return out


def _spans_of(plotinfo) -> List[Dict[str, Any]]:
    """`PlotInfo.spanstyle` → 水平参考线（`kind: 'span'`）✓

    每个 `SpanStyle` 的 ``location`` 是**数值**（价格 / 振荡值），
    不是 K 线时间 → 图表侧用 LWC 的 `createPriceLine` 画一条横线 ✓
    """
    out: List[Dict[str, Any]] = []
    for style in _iter_styles(getattr(plotinfo, 'spanstyle', None)):
        try:
            location = float(_style_of(style, 'location', 'value'))
        except (TypeError, ValueError):
            continue
        if location != location:                     # NaN → 跳过 ✓
            continue
        dash = str(_style_of(style, 'line_dash', 'lineStyle') or '').strip().lower()
        try:
            width = float(_style_of(style, 'line_width', 'width') or 1)
        except (TypeError, ValueError):
            width = 1.0
        out.append({
            'price': location,
            'color': str(_style_of(style, 'line_color', 'color')
                         or '#666666'),
            'lineStyle': DASH_STYLE.get(dash, 2),
            'lineWidth': max(1, min(4, int(round(width)))),
        })
    return out


def _num_or(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _column_of(columns: List[str], style_name: str) -> str:
    """`PlotInfo` 的线名 → 实际列名（列名可能是 `_xxx` ✓）"""
    if style_name in columns:
        return style_name
    for column in columns:
        if column.lstrip('_') == style_name.lstrip('_'):
            return column
    return style_name


def _signal_texts_of(plotinfo, name: str, rows: int,
                     offset: int, stamps: List[int]) -> Dict[int, str]:
    """`PlotInfo.signal_texts[name]` → `{时间戳: 文本}`（逐点信号文字 ✓）

    minibt 里它是**和 K 线等长**的 object 数组，没文字的位置是 NaN；
    这里按行位置换算成时间戳，图表侧直接挂到箭头 `text` 上 ✓
    """
    raw = getattr(plotinfo, 'signal_texts', None)
    if not raw:
        return {}
    try:
        column = raw.get(name) if hasattr(raw, 'get') else raw[name]
    except Exception:                                            # noqa: BLE001
        return {}
    if column is None:
        return {}
    try:
        values = list(column)
    except TypeError:
        return {}
    out: Dict[int, str] = {}
    for row in range(min(rows, len(values))):
        value = values[row]
        if value is None:
            continue
        try:
            if isinstance(value, float) and value != value:       # NaN
                continue
        except Exception:                                        # noqa: BLE001
            pass
        text = str(value).strip()
        if not text or text.lower() == 'nan':
            continue
        position = offset + row
        if 0 <= position < len(stamps):
            out[int(stamps[position])] = text
    return out


def _signal_text(value) -> Optional[str]:
    """`set_label("B")` 可能是 `SignalLabel(text='B')` → 取 `.text` ✓"""
    if value is None:
        return None
    text = str(getattr(value, 'text', value) or '').strip()
    return text or None


def _signal_glyph(marker) -> str:
    """`SignalStyle.marker` → 自定义序列的 glyph

    ⚠ `Markers.triangle` / `inverted_triangle` 在**信号**里一直是箭头
    （和 LWC 原生 `arrowUp` / `arrowDown` 同观感），所以这里映射成箭头；
    `Markers` 本身的三角形语义不变（散点图仍可用 triangle ✓）
    """
    text = str(marker or '').strip()
    return {'triangle': 'arrow_up', 'triangle_dot': 'arrow_up',
            'inverted_triangle': 'arrow_down',
            'arrowup': 'arrow_up', 'arrowdown': 'arrow_down',
            'arrow_up': 'arrow_up', 'arrow_down': 'arrow_down',
            }.get(text, text or 'arrow_up')


def _signal_style_of(plotinfo, name: str) -> Dict[str, Any]:
    """`PlotInfo.signalstyle[name]` → `{color, shape, size}` ✓"""
    styles = getattr(plotinfo, 'signalstyle', None) or {}
    try:
        style = styles.get(name)
    except Exception:                                            # noqa: BLE001
        style = None
    if style is None or getattr(style, 'show', True) is False:
        return {}
    marker = str(getattr(style, 'marker', '') or '').strip().lower()
    # `SignalStyle.key`：'low' = 画在下方（买）/ 'high' = 画在上方（卖）✓
    key_name = str(getattr(style, 'key', '') or '').strip().lower()
    label = getattr(style, 'label', None)
    label_text = getattr(label, 'text', None) or (
        label if isinstance(label, str) else None)
    return {
        'color': getattr(style, 'color', None),
        'shape': MARKER_SHAPE.get(marker),
        # 默认按引擎取（pylightcharts 8 / bokeh 12）✓
        'size': (style.resolved_size('pylightcharts')
                 if hasattr(style, 'resolved_size')
                 else getattr(style, 'size', None)),
        'marker': _signal_glyph(getattr(style, 'marker', '')),
        'above': True if key_name == 'high' else (
            False if key_name == 'low' else None),
        'text': _signal_text(label_text),
        'label_size': getattr(label_text, 'size', None),      # set_label("B", 14)
        'label_color': getattr(label_text, 'color', None),
    }


#: 动态表格钩子（`table_rows(index=None)`）—— `compute()` 时登记，
#: `table_row_at` 命令按 key 取出来按**鼠标所在行**重算 ✓
TABLE_HOOKS: Dict[str, Any] = {}


def table_rows_at(key: str, index: Optional[int]) -> List[List[str]]:
    """按行号取动态表格（`index=None` → 最后一根，与实时一致 ✓）"""
    hook = TABLE_HOOKS.get(key)
    if not callable(hook):
        return []
    try:
        dynamic = hook(index=index) or [] if index is not None else hook() or []
    except Exception:                                            # noqa: BLE001
        try:
            dynamic = hook() or []
        except Exception:                                        # noqa: BLE001
            return []
    rows: List[List[str]] = []
    for row in dynamic:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            rows.append([str(row[0]), str(row[1])])
        elif isinstance(row, dict):
            rows.append([str(row.get('label') or row.get('name') or ''),
                         str(row.get('value', ''))])
    return rows


def _table_of(plotinfo, item: dict, key: str) -> Optional[Dict[str, Any]]:
    """`PlotInfo.tablestyle` → 前端可以画的表格（`kind: 'table'` ✓）"""
    style = getattr(plotinfo, 'tablestyle', None)
    if style is None or getattr(style, 'show', True) is False:
        return None
    headings = [str(text) for text in (getattr(style, 'headings', ()) or ())]
    raw_rows = getattr(style, 'rows', None)
    rows: List[list] = []
    if isinstance(raw_rows, (list, tuple)):
        for row in raw_rows:
            if isinstance(row, (list, tuple)):
                rows.append([str(cell) for cell in row])
    # ★ 动态表格：`def table_rows(self, index=None, values=None)` 钩子
    #   （minibt 把它绑在 IndFrame 上；`tradingview` 指标用它显示当前形态/状态 ✓）
    hook = getattr(plotinfo, 'table_rows', None)
    if callable(hook):
        TABLE_HOOKS[key] = hook          # ★ 登记：鼠标移动时按行号重算 ✓
    if callable(hook) and not rows:
        try:
            dynamic = hook() or []
        except Exception:                                        # noqa: BLE001
            dynamic = []
        for row in dynamic:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                rows.append([str(row[0]), str(row[1])])
            elif isinstance(row, dict):
                label = row.get('label') or row.get('name') or ''
                value = row.get('value', '')
                rows.append([str(label), str(value)])
        if rows and not headings:
            headings = ['项目', '值']
    if not headings and not rows:
        return None
    return {
        'key': f'{key}:table',
        'label': str(getattr(style, 'header', None) or item.get('name') or key),
        'kind': 'table',
        'overlay': True,
        'pane': '',
        'color': '',
        'position': str(getattr(style, 'position', 'top-right') or 'top-right'),
        'headings': headings,
        'rows': rows,
        'data': [],
    }


def _stamps(frame) -> List[int]:
    out: List[int] = []
    values = frame['datetime'].tolist()
    for value in values:
        try:
            out.append(int(value) // 1_000_000_000)
        except (TypeError, ValueError):
            out.append(0)
    return out


# ---------------------------------------------------------------- 缓存
def _read_cache(stamp: str) -> Optional[List[dict]]:
    try:
        with open(CACHE_FILE, encoding='utf-8') as handle:
            data = json.load(handle)
    except Exception:                                            # noqa: BLE001
        return None
    if not isinstance(data, dict) or data.get('version') != stamp:
        return None
    items = data.get('items')
    return items if isinstance(items, list) and items else None


def _write_cache(stamp: str, items: List[dict]) -> None:
    """**先序列化再写**：序列化失败时不会留下半截 JSON ✓"""
    try:
        payload = json.dumps({'version': stamp, 'items': items},
                             ensure_ascii=False)
    except Exception as error:                                   # noqa: BLE001
        print(f'[desk] 指标目录序列化失败: {error!r}')
        return
    try:
        folder = os.path.dirname(CACHE_FILE)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(CACHE_FILE, 'w', encoding='utf-8') as handle:
            handle.write(payload)
    except Exception:                                            # noqa: BLE001
        pass


_KLINE_CACHE: Dict[Any, Any] = {}


def _tv_class(key: str):
    """`tv:Xxx` → `BtIndicator` 子类 ✓"""
    import inspect
    module = _submodule('tradingview')
    name = str(key)[len(TRADINGVIEW_PREFIX):]
    cls = getattr(module, name, None)
    if not inspect.isclass(cls):
        raise KeyError(f'未知 TradingView 指标 {name}')
    return cls


def _kline_of(frame):
    """DataFrame → KLine（带缓存；缺列自动补默认 ✓）

    缓存 key 必须包含 **首尾时间 + 长度 + 最后 close**：
    * 旧实现只看最后一根时间 → 同一根 K 线内 close 更新时一直用旧 KLine ✗；
    * 增量计算用「尾部窗口」时长度不同，旧实现还会误复用全量 KLine ✗。
    """
    try:
        from ..constants import FILED
    except Exception:                                            # noqa: BLE001
        FILED = None
    try:
        data = frame.copy()
        if 'symbol' not in data.columns:
            data['symbol'] = 'DESK'
        if 'duration' not in data.columns:
            data['duration'] = 60
        if 'price_tick' not in data.columns:
            data['price_tick'] = 0.01
        if 'volume_multiple' not in data.columns:
            data['volume_multiple'] = 1.0
        first = data['datetime'].iloc[0]
        last = data['datetime'].iloc[-1]
        # 可能是 Timestamp（.value = ns）或 int ns ✓
        first_stamp = int(getattr(first, 'value', first))
        last_stamp = int(getattr(last, 'value', last))
        try:
            last_close = round(float(data['close'].iloc[-1]), 8)
        except Exception:                                    # noqa: BLE001
            last_close = 0.0
        symbol = str(data['symbol'].iloc[0] if 'symbol' in data else '')
        signature = (symbol, first_stamp, last_stamp, len(data), last_close)
        cached = _KLINE_CACHE.get(signature)
        if cached is not None:
            return cached
        KLine = getattr(_submodule('core'), 'KLine')
        kline = KLine(data)
        if len(_KLINE_CACHE) >= 8:
            _KLINE_CACHE.clear()
        _KLINE_CACHE[signature] = kline
        return kline
    except Exception as error:                                   # noqa: BLE001
        print(f'[desk] 构造 KLine 失败（TradingView 指标需要它）: {error!r}')
        return None


def _pandas_of(result):
    """IndSeries / IndFrame → pandas 对象（给 `_to_items` 用 ✓）"""
    for attr in ('pandas_object', '_df'):
        value = getattr(result, attr, None)
        if value is not None:
            return value
    return result

#: `CoreIndicators.indicators` 的名字前缀 → (prefix, 标签) ✓
CORE_PREFIXES = (
    ('pta_', 'pta', 'PandasTA'),
    ('talib_', 'talib', 'TA-Lib'),
    ('finta_', 'finta', 'FinTa'),
    ('tqta_', 'tqta', '天勤TA'),
    ('tqfunc_', 'tqfunc', '天勤函数'),
    ('ti_', 'ti', 'TuLip'),
    ('btind_', 'btind', 'BtInd'),
    ('pine_', 'pine', 'Pine'),
    ('pair_', 'pair', 'Pair'),
    ('factor_', 'factor', 'Factors'),
)

#: 造一个只够反射用的最小 K 线（**不联网** ✓）
_CORE_TINY = None


def _tiny_frame():
    """2 根假 K 线（反射指标签名用，代价很小 ✓）"""
    global _CORE_TINY
    if _CORE_TINY is not None:
        return _CORE_TINY
    import numpy as np
    import pandas as pd

    close = np.array([100.0, 101.0])
    _CORE_TINY = pd.DataFrame({
        'datetime': [1_700_000_000 * 10 ** 9, 1_700_000_060 * 10 ** 9],
        'open': close - 0.5, 'high': close + 1.0, 'low': close - 1.0,
        'close': close, 'volume': np.ones(2),
        'symbol': 'TINY', 'duration': 60, 'price_tick': 0.01,
        'volume_multiple': 1.0,
    })
    return _CORE_TINY


def _build_from_core() -> List[Dict[str, Any]]:
    """枚举 `CoreIndicators(...).indicators`（= 计算时真正用的入口 ✓）"""
    CoreIndicators = core_indicators()

    core = CoreIndicators(_tiny_frame())
    calculator = getattr(core, 'indicators', core)
    names = [name for name in dir(calculator) if not name.startswith('_')]
    items: List[Dict[str, Any]] = []
    for name in names:
        for raw_prefix, prefix, label in CORE_PREFIXES:
            if not name.startswith(raw_prefix):
                continue
            short = name[len(raw_prefix):]
            func = getattr(calculator, name, None)
            if not callable(func):
                continue
            items.append({
                'key': f'{prefix}_{short}',
                'prefix': prefix,
                'name': short,
                'label': f'{short} · {label}',
                'group': label,
                'overlap': _guess_overlay(short),
                'params': _params_of(func),
            })
            break
    return items

_WARNED: set = set()

#: 按文件加载过的模块（缓存，别重复 exec ✓）
_FILE_MODULES: Dict[str, Any] = {}


def _warn_install(error) -> None:
    """指标模块缺失 → 提示一次「怎么修」（用户机器上是安装不完整 ✓）"""
    key = str(error)[:80]
    if key in _WARNED:
        return
    _WARNED.add(key)
    print(f'[desk] 指标模块加载失败: {error!r}')
    print('[desk] ⚠ 当前 `minibt` 安装里缺少指标实现文件。修复（任选一种）：')
    print('[desk]   1) 清残留目录（最常见）：删掉 site-packages 里的')
    print('[desk]      site-packages/minibt（只剩 __pycache__ 的那种），再 '
          '`pip install -e minibt`')
    print('[desk]      —— 这个空目录会让 `minibt` 变成 namespace 包，'
          '报 (unknown location) ✗')
    print('[desk]   2) 重装：cd <repo>/minibt && '
          'python -m pip install -e .')
    print('[desk]   3) 直接用源码跑：cd <repo> && '
          'python -m minibt desk …')


def diagnose() -> Dict[str, Any]:
    """诊断：哪个库可用 / 缺什么（`--check` 与选择器错误提示用 ✓）"""
    import os

    root = _minibt_root()
    folder = os.path.join(root or '', 'indicators')
    files = []
    if folder and os.path.isdir(folder):
        files = sorted(name for name in os.listdir(folder) if name.endswith('.py'))
    missing = []
    for class_name, module_name in LIB_MODULES.items():
        if _library(class_name) is None:
            missing.append(f'{class_name}({module_name})')
    return {'root': root, 'indicators_dir': folder, 'files': files,
            'missing': missing, 'ok': not missing}
