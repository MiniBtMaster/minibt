"""desk 与 JS 之间的协议：**补丁下发** + **命令上报**。

* Python → JS：一条 JS 语句 ``window.__desk.applyPatch({...})``
* JS → Python：``window.callbackFunction('desk_~_<json>')``
  → :class:`~minibt.desk.app.Desk` 按 ``cmd`` 分发
"""
from __future__ import annotations

import json
import math
from typing import Any, Callable, Dict, Iterable, List, Optional

#: 回调名（JS 侧固定用它，见 `jslib/src/desk/transport.ts`）
CALLBACK = 'desk'

#: 一次 ``rows`` 补丁最多多少行（首屏分块推送，避免 1~2 MB 卡住渲染 ✓）
ROWS_CHUNK = 500


def encode_patch(patch: Dict[str, Any]) -> str:
    """补丁 → 可直接 ``run_script`` 的语句（紧凑 JSON ✓）

    ⚠ 标准 ``json.dumps`` 会写出 ``NaN`` / ``Infinity`` 这种**非法 JSON**：
    Qt 壳是 ``run_script``（JS 能认 NaN），但**浏览器壳 / SSE** 走的是
    ``JSON.parse`` → 一个 NaN 就让**整批补丁丢掉**（前端像卡死一样 ✗）。
    所以这里用 ``allow_nan=False`` 先试；只有真的含 NaN 才走清洗（平时零开销 ✓）。
    """
    return 'window.__desk.applyPatch(%s);' % _dumps(patch)


def _dumps(payload: Any) -> str:
    """紧凑 JSON；含 NaN / inf 时自动转成 ``null`` ✓"""
    try:
        return json.dumps(payload, ensure_ascii=False, default=str,
                          allow_nan=False, separators=(',', ':'))
    except (TypeError, ValueError):
        return json.dumps(_json_safe(payload), ensure_ascii=False,
                          default=str, allow_nan=False,
                          separators=(',', ':'))


def _json_safe(value: Any) -> Any:
    """递归把 NaN / inf 转成 ``None``（dict / list / tuple 都能处理 ✓）"""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def encode_command(payload: Any) -> str:
    """命令载荷 → ``callbackFunction`` 字符串（``desk_~_<json>``）"""
    return '%s_~_%s' % (CALLBACK, _dumps(payload))


def decode_command(message: str) -> Dict[str, Any]:
    """``desk_~_{"cmd":…}`` → dict（坏消息 → 空 dict ✓）"""
    text = str(message or '')
    marker = CALLBACK + '_~_'
    if text.startswith(marker):
        text = text[len(marker):]
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def chunked(items: Iterable[Any], size: int = ROWS_CHUNK) -> List[list]:
    """切块（首屏 6496 行 → 13 块 ✓）"""
    out: List[list] = []
    block: list = []
    for item in items:
        block.append(item)
        if len(block) >= int(size):
            out.append(block)
            block = []
    if block:
        out.append(block)
    return out


def patch_boot(theme: str = 'dark', title: str = 'minibt桌面端',
               markets: Any = None, home: bool = False) -> Dict[str, Any]:
    """`home=True` → 启动直接打开首页（只有**命令行带账号登录**时才为真 ✓）"""
    return {'type': 'boot', 'theme': theme, 'title': title,
            'markets': markets or {}, 'home': bool(home)}


def patch_markets(markets: Any) -> Dict[str, Any]:
    """连接状态变了（登录期货 / 连上富途 → 首页数据源 + 菜单立刻更新 ✓）"""
    return {'type': 'markets', 'markets': dict(markets or {})}


def patch_login(kind: str = 'futures', state: str = 'idle',
                ok: Optional[bool] = None, text: str = '',
                saved: Any = None) -> Dict[str, Any]:
    """登录状态（`pending` 登录中 / `ok` / `error` / `test` 测网关 ✓）"""
    patch: Dict[str, Any] = {'type': 'login', 'kind': str(kind),
                             'state': str(state), 'text': str(text or '')}
    if ok is not None:
        patch['ok'] = bool(ok)
    if saved is not None:
        patch['saved'] = dict(saved)
    return patch


def patch_chips(items, current: str = '', exchanges: bool = False) -> Dict[str, Any]:
    return {'type': 'exchanges' if exchanges else 'types',
            'items': list(items or []), 'current': str(current or '')}


def patch_rows_loading(text: str = '正在加载合约…') -> Dict[str, Any]:
    """报价表进入「加载中」（前端空表文案 + 状态栏 ✓）"""
    return {'type': 'rows_loading', 'text': str(text)}


def patch_rows(rows, replace: bool = True) -> Dict[str, Any]:
    return {'type': 'rows', 'rows': list(rows or []), 'replace': bool(replace)}


def patch_rows_update(rows) -> Dict[str, Any]:
    return {'type': 'rows_update', 'rows': list(rows or [])}


def patch_open_tab(symbol: str, name: str = '',
                   cycle: int | None = None) -> Dict[str, Any]:
    return {'type': 'open_tab', 'symbol': symbol, 'name': name, 'cycle': cycle}


def patch_close_tab(symbol: str) -> Dict[str, Any]:
    return {'type': 'close_tab', 'symbol': symbol}


def patch_kline(symbol: str, bars, replace: bool = True) -> Dict[str, Any]:
    return {'type': 'kline', 'symbol': symbol, 'bars': list(bars or []),
            'replace': bool(replace)}


def patch_toast(text: str, level: str = 'info', actions=None,
                detail: str = '') -> Dict[str, Any]:
    """轻提示（``actions`` = 按钮，``detail`` = 小字/悬浮完整路径 ✓）"""
    patch: Dict[str, Any] = {'type': 'toast', 'text': text, 'level': level}
    if actions:
        patch['actions'] = list(actions)
    if detail:
        patch['detail'] = str(detail)
    return patch


def patch_status(text: str) -> Dict[str, Any]:
    return {'type': 'status', 'text': text}


def bars_from_frame(frame, bar_count: int = 0) -> List[Dict[str, Any]]:
    """K 线 DataFrame → JS 的 ``{time, open, high, low, close, volume}`` ✓

    ``time`` 用**秒**（LWC 认 unix 秒；天勤给的是**纳秒** ✓）。

    ⚠ 天勤的 ``get_kline_serial`` 在数据还没到之前会返回一个**定长占位表**
    （``datetime = 0``，OHLC 全是 NaN；desk 用 ``_fast_call`` 不阻塞 UI，
    所以首拍拿到的就是这个）。以前这些占位行被当成 K 线推送：

      * 时间全是 0 / 价格是 NaN → LWC ``setData`` 直接报错 / 只画出 1~2 根；
      * 之后长度一直是 ``width``（占位行的数量）不变，后端便不再全量重推
        → 图表“打开只显示 2 根 K 线”就卡住了（用户实测 ✗）。

    所以这里直接**丢掉占位行**（时间无效 / 收盘价 NaN）✓。
    """
    # ⚠ `len(SimpleNamespace)` 会抛 TypeError（富途某些路径把 quote 当 frame 传
    #   进来 → 刷新节拍每 0.5s 报一次「刷新失败」✗）→ 先确认是表格 ✓
    if frame is None or not hasattr(frame, 'to_dict'):
        return []
    if len(frame) == 0:
        return []
    rows = frame.tail(int(bar_count)).to_dict('records') if bar_count else \
        frame.to_dict('records')
    out: List[Dict[str, Any]] = []
    for item in rows:
        stamp = item.get('datetime')
        if stamp is None:
            continue
        try:
            seconds = int(stamp) // 1_000_000_000
        except (TypeError, ValueError):
            continue                      # NaN / 非数字 → 占位行 ✓
        if seconds <= 0:
            continue                      # 占位行（datetime = 0）✓
        close = _finite(item.get('close'))
        if close is None:
            continue                      # 没有成交价的占位行 ✓
        out.append({'time': seconds,
                    'open': _finite(item.get('open')) or 0.0,
                    'high': _finite(item.get('high')) or 0.0,
                    'low': _finite(item.get('low')) or 0.0,
                    'close': close,
                    'volume': _finite(item.get('volume')) or 0.0})
    return out


def _finite(value):
    """数值字段：``None`` / NaN / inf → ``None``（JSON 不能出现 NaN ✗）"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def valid_bars(frame, bar_count: int = 0) -> int:
    """这一帧里**真正有数据的** K 线根数（占位行不算 ✓）

    天勤那张表长度是**定长**（= 请求宽度），占位行会被真实数据从尾部逐步
    顶替；所以「根数变没变」不能看 ``len(frame)``，要看这个 ✓。
    """
    return len(bars_from_frame(frame, bar_count))


#: 右键周期菜单（与 `jslib/src/desk/chart-page.ts` 的 CYCLES 对齐 ✓）
PERIOD_MENU = (
    (30, '30秒'), (60, '1分'), (300, '5分'), (900, '15分'),
    (1800, '30分'), (3600, '1时'), (86400, '1日'),
)


def patch_preview(data: Optional[Dict[str, Any]] = None,
                  x: int = 0, y: int = 0, hide: bool = False) -> Dict[str, Any]:
    """左键「合约概览」气泡（``hide=True`` → 关掉 ✓）"""
    return {'type': 'preview', 'data': data or {}, 'x': int(x), 'y': int(y),
            'hide': bool(hide)}


def patch_menu(x: int, y: int, symbol: str = '', name: str = '',
               items=None) -> Dict[str, Any]:
    """右键菜单（点某项 → 前端直接 ``open_chart``，不用再来回 ✓）

    默认结构：``打开图表`` + ``周期 ›``（二级菜单里放所有周期 ✓）
    """
    return {'type': 'menu', 'x': int(x), 'y': int(y),
            'symbol': str(symbol or ''), 'name': str(name or ''),
            'items': list(items if items is not None else
                          default_menu_items())}


def default_menu_items() -> List[Dict[str, Any]]:
    """行情报价右键菜单：打开图表 + 周期（**二级菜单** ✓）"""
    return [
        {'label': '打开图表', 'cycle': None},
        {'label': '周期', 'submenu': [
            {'label': label, 'cycle': cycle}
            for cycle, label in PERIOD_MENU]},
    ]


def patch_close_menu() -> Dict[str, Any]:
    return {'type': 'close_menu'}


def patch_ticker(items) -> Dict[str, Any]:
    return {'type': 'ticker', 'items': list(items or [])}


def make_router(table: Dict[str, Callable]) -> Callable[[str], Any]:
    """命令表 → ``router(message)``（未知命令返回 None，不抛错 ✓）"""
    def dispatch(message: str):
        payload = decode_command(message)
        if not payload:
            return None
        handler = table.get(str(payload.get('cmd') or ''))
        if handler is None:
            return None
        return handler(payload.get('payload') if 'payload' in payload
                       else payload)
    return dispatch
