"""desk 的用户偏好：**指标收藏** + **指标模板**（持久化到 JSON）。

```
~/.minibt/desk_user_prefs.json
{
  "favorites": ["pta_macd", "pta_adx"],          // ★ 收藏的指标（key）
  "strategies": ["pi:my_strats/MyStrategy"],      // ★ 收藏的策略
  "templates": [
    {"key": "t1", "name": "pta_adx", "items": [{"key": "pta_adx", "params": {}}]}
  ]
}
```

* 模板 = **一组指标**（`items`），应用时**替换**当前图上的指标（同 miniqt）；
* 写坏了只是回到空偏好，不影响启动 ✓。
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List

#: 偏好文件（和别的 desk 数据放一起 ✓）
PREFS_FILE = os.path.join(os.path.expanduser('~'), '.minibt',
                          'desk_user_prefs.json')

def _empty() -> Dict[str, Any]:
    """空偏好（结构固定，前端不用判空 ✓）"""
    return {'favorites': [], 'strategies': [], 'templates': [],
            'layouts': [], 'settings': {}, 'exports': [], 'login': {},
            'watch': _clean_watch({})}


#: 登录信息里允许存的字段（期货 / 股票各一套 ✓）
LOGIN_FIELDS = {
    'futures': ('username', 'remember', 'real', 'broker', 'account',
                'trade_password'),
    'stocks': ('host', 'port', 'trade', 'trd_env', 'trd_market'),
}


def _clean_login(raw: Any) -> Dict[str, Any]:
    """只留白名单字段；**密码只在 `remember` 为真时才存** ✓"""
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    for kind, fields in LOGIN_FIELDS.items():
        block = raw.get(kind)
        if not isinstance(block, dict):
            continue
        values = {name: block.get(name) for name in fields
                  if block.get(name) not in (None, '')}
        # 记住密码 → 才把密码写进去（否则永远不落盘 ✓）
        if kind == 'futures' and values.get('remember') and block.get('password'):
            values['password'] = str(block.get('password'))
        if kind == 'futures' and values.get('remember') and block.get('trade_password'):
            values['trade_password'] = str(block.get('trade_password'))
        elif kind == 'futures':
            values.pop('trade_password', None)
        if values:
            out[kind] = values
    return out


#: 可重入锁（`set_setting` 持锁时还要调 `save()`，用 Lock 会自锁死 ✗）
_LOCK = threading.RLock()


#: 布局里每个指标要保留的样式字段（颜色 / 线宽 / 线型 / 显隐 / 主副图 ✓）
LAYOUT_INDICATOR_STYLE_KEYS = (
    'overlay', 'color', 'lineWidth', 'lineStyle', 'visible',
    'priceLine', 'priceLabel', 'crosshairMarker',
)


def clean_layout_indicator(entry: Any) -> Dict[str, Any]:
    """布局里的单个指标 → 只保留 key / params / 样式 ✓"""
    if not isinstance(entry, dict) or not entry.get('key'):
        return {}
    out: Dict[str, Any] = {
        'key': str(entry.get('key')),
        'params': dict(entry.get('params') or {}),
    }
    for name in LAYOUT_INDICATOR_STYLE_KEYS:
        if name in entry and entry.get(name) is not None:
            out[name] = entry[name]
    return out


#: 布局作用域：本地图表 / 实时看盘。两者互不混用 ✓
LAYOUT_SCOPES = ('realtime', 'local')


def _layout_scope(value: Any = None, cells: Any = None) -> str:
    """规范化布局作用域；旧布局没有 scope 时按合约名粗略迁移。"""
    scope = str(value or '').strip().lower()
    if scope in LAYOUT_SCOPES:
        return scope
    # 旧记录：本地 CSV 名称通常没有交易所前缀（pp2609_60），实时合约带点
    # （SHFE.ag2612）；没有可判断信息时默认实时。
    symbols = [str(cell.get('symbol') or '') for cell in (cells or [])
               if isinstance(cell, dict)]
    if symbols and all('.' not in symbol for symbol in symbols):
        return 'local'
    return 'realtime'


def load() -> Dict[str, Any]:
    try:
        with open(PREFS_FILE, encoding='utf-8') as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return _empty()
    except (OSError, ValueError):
        return _empty()
    if not isinstance(data, dict):
        return _empty()
    favorites = [str(item) for item in (data.get('favorites') or [])
                 if isinstance(item, str)]
    strategies = [str(item) for item in (data.get('strategies') or [])
                  if isinstance(item, str)]
    templates = []
    for item in data.get('templates') or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '').strip()
        if not name:
            continue
        entries = []
        for entry in item.get('items') or []:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get('key') or '').strip()
            if not key:
                continue
            entries.append({'key': key, 'params': dict(entry.get('params') or {})})
        if not entries:
            continue
        templates.append({'key': str(item.get('key') or name),
                          'name': name, 'items': entries})
    layouts = []
    for item in data.get('layouts') or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '').strip()
        if not name:
            continue
        cells = []
        for cell in item.get('cells') or []:
            if not isinstance(cell, dict):
                continue
            symbol = str(cell.get('symbol') or '').strip()
            if not symbol:
                continue
            indicators = []
            for entry in cell.get('indicators') or []:
                cleaned = clean_layout_indicator(entry)
                if cleaned:
                    indicators.append(cleaned)
            clean = {'symbol': symbol, 'indicators': indicators}
            strategy = cell.get('strategy')
            if isinstance(strategy, dict) and (
                    strategy.get('path') or strategy.get('name')):
                clean['strategy'] = {
                    'name': str(strategy.get('name') or ''),
                    'path': str(strategy.get('path') or ''),
                }
            cells.append(clean)
        if not cells:
            continue
        layouts.append({
            'key': str(item.get('key') or name), 'name': name,
            'favorite': bool(item.get('favorite')),
            'scope': _layout_scope(item.get('scope') or item.get('local'),
                                 cells),
            'cols': int(item.get('cols') or 1), 'rows': int(item.get('rows') or 1),
            'cycle': int(item.get('cycle') or 60), 'cells': cells,
        })
    values = data.get('settings')
    exports = []
    for item in data.get('exports') or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get('path') or '').strip()
        if not path:
            continue
        exports.append({'path': path, 'name': str(item.get('name') or ''),
                        'rows': int(item.get('rows') or 0),
                        'at': str(item.get('at') or '')})
    return {'favorites': favorites, 'strategies': strategies,
            'templates': templates, 'layouts': layouts,
            'settings': dict(values) if isinstance(values, dict) else {},
            'exports': exports[:EXPORT_LIMIT],
            'login': _clean_login(data.get('login')),
            'watch': _clean_watch(data.get('watch'))}


def save(data: Dict[str, Any]) -> bool:
    payload = {
        'favorites': [str(item) for item in (data.get('favorites') or [])],
        'strategies': [str(item) for item in (data.get('strategies') or [])],
        'templates': list(data.get('templates') or []),
        'layouts': list(data.get('layouts') or []),
        'settings': dict(data.get('settings') or {}),
        'exports': list(data.get('exports') or [])[:EXPORT_LIMIT],
        'login': _clean_login(data.get('login')),
        'watch': _clean_watch(data.get('watch')),
    }
    try:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return False
    with _LOCK:
        try:
            folder = os.path.dirname(PREFS_FILE)
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(PREFS_FILE, 'w', encoding='utf-8') as handle:
                handle.write(text)
            return True
        except OSError:
            return False


# ---------------------------------------------------------------- 自选
#: 「收藏 / 自选分组」的持久化（以前只在 localStorage → 重启就丢 ✗）
WATCH_LIMIT = 200


def _clean_watch(raw: Any) -> Dict[str, Any]:
    """收藏 + 自建分组 + pins（手动加入内置分组的合约）✓"""
    out: Dict[str, Any] = {'favorites': [], 'groups': [], 'pins': {}}
    if not isinstance(raw, dict):
        return out
    favorites = [str(item) for item in (raw.get('favorites') or [])
                 if isinstance(item, (str, int)) and str(item).strip()]
    out['favorites'] = list(dict.fromkeys(favorites))[:WATCH_LIMIT]
    groups = []
    for item in raw.get('groups') or []:
        if not isinstance(item, dict):
            continue
        group_id = str(item.get('id') or '').strip()
        label = str(item.get('label') or '').strip()
        if not group_id or not label:
            continue
        symbols = [str(symbol) for symbol in (item.get('symbols') or [])
                   if str(symbol).strip()]
        groups.append({'id': group_id, 'label': label,
                       'symbols': list(dict.fromkeys(symbols))[:WATCH_LIMIT]})
    out['groups'] = groups[:60]
    pins = raw.get('pins')
    if isinstance(pins, dict):
        out['pins'] = {
            str(key): list(dict.fromkeys(
                str(item) for item in value if str(item).strip()))[:WATCH_LIMIT]
            for key, value in pins.items() if isinstance(value, list)
        }
    return out


def watch() -> Dict[str, Any]:
    """收藏 / 自选分组（首页 + 行情报价共用 ✓）"""
    return dict(load().get('watch') or {})


def set_watch(payload: Any) -> Dict[str, Any]:
    """整份替换（前端改完就发整份，简单可靠 ✓）"""
    value = _clean_watch(payload if isinstance(payload, dict) else {})
    with _LOCK:
        data = load()
        data['watch'] = value
        save(data)
    return value


# ------------------------------------------------------------------ 登录
def login() -> Dict[str, Any]:
    """记住的登录信息（`{'futures': {...}, 'stocks': {...}}` ✓）"""
    return dict(load().get('login') or {})


def save_login(kind: str, values: Dict[str, Any]) -> Dict[str, Any]:
    """保存一种登录信息（期货 / 股票）；`remember=False` → 不存密码 ✓"""
    kind = 'stocks' if str(kind) == 'stocks' else 'futures'
    values = dict(values or {})
    block: Dict[str, Any] = {}
    for name in LOGIN_FIELDS[kind]:
        if name in values and values[name] not in (None, ''):
            block[name] = values[name]
    if kind == 'futures':
        block['remember'] = bool(values.get('remember'))
        if block['remember'] and values.get('password'):
            block['password'] = str(values['password'])
        if not block['remember']:
            block.pop('password', None)
            block.pop('trade_password', None)
    with _LOCK:
        data = load()
        current = dict(data.get('login') or {})
        if block:
            current[kind] = block
        else:
            current.pop(kind, None)
        data['login'] = current
        save(data)
    return login()


# ------------------------------------------------------------------ 收藏
def favorites(kind: str = 'indicator') -> List[str]:
    key = 'strategies' if str(kind) == 'strategy' else 'favorites'
    return list(load().get(key) or [])


def toggle_favorite(key: str, on: bool, kind: str = 'indicator') -> List[str]:
    key = str(key or '').strip()
    field = 'strategies' if str(kind) == 'strategy' else 'favorites'
    data = load()
    items = [item for item in (data.get(field) or []) if item != key]
    if on and key:
        items.insert(0, key)
    data[field] = items
    save(data)
    return items


# ------------------------------------------------------------------ 模板
def templates() -> List[Dict[str, Any]]:
    return list(load().get('templates') or [])


def save_template(name: str, items: List[Dict[str, Any]],
                  key: str = '') -> Dict[str, Any]:
    """新建/覆盖模板（同名视为覆盖 ✓）"""
    name = str(name or '').strip() or '未命名模板'
    entries = [{'key': str(item.get('key')), 'params': dict(item.get('params') or {})}
               for item in (items or []) if item.get('key')]
    data = load()
    current = [item for item in data.get('templates') or []
               if item.get('name') != name]
    record = {'key': str(key or name), 'name': name, 'items': entries}
    current.append(record)
    data['templates'] = current
    save(data)
    return record


def delete_template(key: str) -> bool:
    key = str(key or '')
    data = load()
    current = [item for item in data.get('templates') or []
               if str(item.get('key')) != key and str(item.get('name')) != key]
    if len(current) == len(data.get('templates') or []):
        return False
    data['templates'] = current
    return save(data)


def find_template(key: str):
    key = str(key or '')
    for item in templates():
        if str(item.get('key')) == key or str(item.get('name')) == key:
            return item
    return None


# ------------------------------------------------------------------ 布局
def layouts(scope: str | None = None) -> List[Dict[str, Any]]:
    items = list(load().get('layouts') or [])
    if scope is None:
        return items
    wanted = _layout_scope(scope)
    return [item for item in items if _layout_scope(item.get('scope')) == wanted]


def save_layout(name: str, cols: int, rows: int, cycle: int,
                cells: List[Dict[str, Any]], key: str = '',
                scope: str = 'realtime') -> Dict[str, Any]:
    """新建/覆盖布局（同名覆盖 ✓）"""
    name = str(name or '').strip() or '未命名布局'
    entries = []
    for cell in cells or []:
        symbol = str(cell.get('symbol') or '').strip()
        if not symbol:
            continue
        entry = {
            'symbol': symbol,
            'indicators': [
                cleaned for cleaned in (
                    clean_layout_indicator(item)
                    for item in (cell.get('indicators') or [])
                    if item.get('key')
                    and not str(item.get('key')).startswith(
                        ('editor:', 'st:')))
                if cleaned],
        }
        # ★ 本地图表：把「加到图表」的策略文件也存进布局 →
        #   下次应用布局时能把策略线一起恢复 ✓
        strategy = cell.get('strategy')
        if isinstance(strategy, dict) and (
                strategy.get('path') or strategy.get('name')):
            entry['strategy'] = {
                'name': str(strategy.get('name') or ''),
                'path': str(strategy.get('path') or ''),
            }
        entries.append(entry)
    scope = _layout_scope(scope, entries)
    record = {'key': str(key or name), 'name': name, 'favorite': False,
              'scope': scope,
              'cols': max(1, int(cols)), 'rows': max(1, int(rows)),
              'cycle': int(cycle), 'cells': entries}
    data = load()
    current = [item for item in data.get('layouts') or []
               if not (item.get('name') == name
                       and _layout_scope(item.get('scope')) == scope)]
    record['favorite'] = any(
        item.get('name') == name and item.get('favorite')
        and _layout_scope(item.get('scope')) == scope
        for item in data.get('layouts') or [])
    current.append(record)
    data['layouts'] = current
    save(data)
    return record


def delete_layout(key: str, scope: str | None = None) -> bool:
    key = str(key or '')
    wanted = _layout_scope(scope) if scope else None
    data = load()
    current = [item for item in data.get('layouts') or []
               if not ((str(item.get('key')) == key
                        or str(item.get('name')) == key)
                       and (wanted is None
                            or _layout_scope(item.get('scope')) == wanted))]
    if len(current) == len(data.get('layouts') or []):
        return False
    data['layouts'] = current
    return save(data)


def find_layout(key: str, scope: str | None = None):
    key = str(key or '')
    wanted = _layout_scope(scope) if scope else None
    for item in layouts():
        if str(item.get('key')) != key and str(item.get('name')) != key:
            continue
        if wanted is None or _layout_scope(item.get('scope')) == wanted:
            return item
    return None


def toggle_layout_favorite(key: str, on: bool,
                           scope: str | None = None) -> List[Dict[str, Any]]:
    key = str(key or '')
    wanted = _layout_scope(scope) if scope else None
    data = load()
    for item in data.get('layouts') or []:
        if str(item.get('key')) != key and str(item.get('name')) != key:
            continue
        if wanted is not None and _layout_scope(item.get('scope')) != wanted:
            continue
        item['favorite'] = bool(on)
    save(data)
    return layouts(scope) if scope else layouts()


# ---------------------------------------------------------------- 设置
#: 允许的设置项（白名单 —— 别让前端随便塞东西 ✓）
SETTING_KEYS = {
    'ticket_click_orders', 'ticket_decimals', 'legend_ohlc',
    'indicator_overlay_filter', 'indicator_section',
    'ticker_only_quoted',
    'watch_default_group',
    # ---- 「设置」页（P44）：系统设置 ----
    'theme_accent',            # 主题色（默认 / blue / green / purple / orange）
    'ui_zoom',                 # 界面缩放（1.0 / 0.8 / 0.9 / 1.1 / 1.25）
    # ---- 图表设置 ----
    'chart_font_size',         # 图表左上角标签字号（px）
    'chart_history',           # 期货历史长度（最多能加载多少根）
    'chart_data_length',       # 期货数据长度（初始显示 / 请求根数）
    'chart_color_up',          # 上涨颜色（'' = 默认）
    'chart_color_down',        # 下跌颜色（'' = 默认）
    'chart_color_crosshair',   # 鼠标标签（十字线标签）颜色
    'chart_crosshair_style',   # 十字线预设（classic / tradingview / native / neon / minimal）
    'position_line',           # 持仓线（所有图表；默认开 ✓）
    'order_line',              # 挂单线（所有图表；默认开 ✓）
    # ---- 指标 / 策略图表更新频率（设置 → 图表设置 → 指标刷新）----
    'indicator_refresh_interval_ms',  # 指标 / 策略 __init__ 更新间隔（10..3000ms）
    'indicator_custom_new_bar',       # VP / 表格只在新 K 线更新（默认关 = 按间隔）
    # ---- 设置页本体 / 动作（不走白名单也没关系，这里显式列出 ✓）----
    'app_theme',               # 应用主题（light / dark）
    'chart_reset',             # 恢复默认设置（前端触发一次重置 ✓）
    'dock_height',             # 底部面板高度（看盘窗口；可拖 ✓）
    'dock_height_local',       # 本地图表底部面板高度（默认 1/3 ✓）
    'explorer_root',           # 资源管理器根目录（编辑器文件树 ✓）
    # ---- 模拟账户（设置 → 模拟账户 ✓）----
    'sim_initial_cash',        # 账户初始现金
    'sim_fee_mode',            # 手续费模式：fixed / percent
    'sim_fee_value',           # 手续费数值（每手元 / 成交额百分比）
    # ---- 运行日志输出位置（P92）----
    'log_terminal',            # 终端输出（默认开 ✓）
    'log_ui',                  # 程序内输出（日志页 / 底部面板）
    # ---- 编辑器（P127）----
    'editor_format_on_save',   # 保存时自动格式化（ruff / black ✓）
    'editor_last_file',        # 上次打开的文件（下次启动自动恢复 ✓）
    # ---- 策略运行（「策略管理」弹窗里可改 ✓）----
    'strategy_next_on_new_bar',  # True=只在新 K 线跑 next；False=指标算完就跑
    'strategy_run_next',         # False=只算指标、不跑 next（纯指标策略）
    'strategy_live_retry',       # 策略实盘子进程崩了是否自动重启（默认关）
}


#: 「设置 → 图表设置 → 图表配置」页的恢复默认范围（不动主题 / 模拟账户 ✓）
CHART_CONFIG_KEYS = {
    'chart_history',
    'chart_data_length',
    'chart_font_size',
    'chart_crosshair_style',
    'position_line',
    'order_line',
    'indicator_refresh_interval_ms',
    'indicator_custom_new_bar',
}


def reset_chart_settings() -> Dict[str, Any]:
    """恢复**当前图表配置页**的默认值，不影响其它页面设置 ✓"""
    with _LOCK:
        data = load()
        values = dict(data.get('settings') or {})
        for key in CHART_CONFIG_KEYS:
            values.pop(key, None)
        # 合并前的旧键也清掉，避免 settings() 迁移又把旧值读回来 ✓
        for key in ('indicator_main_interval_ms',
                    'indicator_sub_interval_ms',
                    'indicator_custom_interval_ms'):
            values.pop(key, None)
        data['settings'] = values
        save(data)
    return values


def settings() -> Dict[str, Any]:
    """偏好设置（``ticket_click_orders`` 等 ✓）"""
    data = load()
    values = data.get('settings')
    values = dict(values) if isinstance(values, dict) else {}
    # 旧版三个间隔 → 合并后的一个；取第一个有效值 ✓
    if 'indicator_refresh_interval_ms' not in values:
        for old in ('indicator_main_interval_ms',
                    'indicator_sub_interval_ms',
                    'indicator_custom_interval_ms'):
            try:
                number = int(float(values.get(old)))
            except (TypeError, ValueError):
                continue
            if number > 0:
                values['indicator_refresh_interval_ms'] = max(
                    10, min(3000, number))
                break
    return values


def set_setting(key: str, value: Any) -> Dict[str, Any]:
    """写一个设置项（白名单外的忽略）✓ 返回全部设置"""
    key = str(key or '').strip()
    if key not in SETTING_KEYS:
        return settings()
    with _LOCK:
        data = load()
        values = dict(data.get('settings') or {})
        values[key] = value
        if key == 'indicator_refresh_interval_ms':
            for old in ('indicator_main_interval_ms',
                        'indicator_sub_interval_ms',
                        'indicator_custom_interval_ms'):
                values.pop(old, None)
        data['settings'] = values
        save(data)
    return values


#: 导出历史最多留 20 条 ✓
EXPORT_LIMIT = 20


def exports() -> List[Dict[str, Any]]:
    """最近的导出记录（新的在前 ✓）"""
    return list(load().get('exports') or [])


def record_export(path: str, name: str = '', rows: int = 0) -> List[Dict[str, Any]]:
    """记一条导出（同一个路径只留最新的那条 ✓）"""
    import time

    path = str(path or '').strip()
    if not path:
        return exports()
    entry = {'path': path, 'name': str(name or os.path.basename(path)),
             'rows': int(rows or 0), 'at': time.strftime('%Y-%m-%d %H:%M:%S')}
    with _LOCK:
        data = load()
        items = [item for item in (data.get('exports') or [])
                 if item.get('path') != path]
        items.insert(0, entry)
        data['exports'] = items[:EXPORT_LIMIT]
        save(data)
    return exports()


def remove_export(path: str) -> List[Dict[str, Any]]:
    """删掉一条导出记录（只删记录，**文件还在** ✓）"""
    path = str(path or '').strip()
    if not path:
        return exports()
    with _LOCK:
        data = load()
        data['exports'] = [item for item in (data.get('exports') or [])
                           if item.get('path') != path]
        save(data)
    return exports()


def clear_exports() -> List[Dict[str, Any]]:
    """清空导出历史（文件不动 ✓）"""
    with _LOCK:
        data = load()
        data['exports'] = []
        save(data)
    return []
