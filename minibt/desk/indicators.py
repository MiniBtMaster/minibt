"""常用指标（P2b）：MA / EMA / BOLL / MACD / KDJ / RSI。

只算 **7 个常用指标**（完整指标库是 P6 —— 那一步走 `minibt.indicators` 反射）。

数据形状（前端 `indicator.ts` 直接吃）::

    {'type': 'indicator', 'symbol': 'SHFE.rb2610',
     'items': [
        {'key': 'MA5', 'label': 'MA5', 'overlay': True, 'kind': 'line',
         'color': '#f6c343', 'data': [[1700000000, 3600.1], ...]},
        {'key': 'MACD_DIF', 'label': 'DIF', 'overlay': False, 'kind': 'line',
         'pane': 'MACD', 'color': '#4caf50', 'data': [...]},
     ]}
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

#: 指标目录（工具栏「指标」菜单的数据源）✓
CATALOG = [
    {'key': 'MA', 'label': 'MA 均线', 'overlay': True,
     'params': [{'name': 'length', 'label': '周期', 'default': 20,
                 'type': 'int'}]},
    {'key': 'EMA', 'label': 'EMA 指数均线', 'overlay': True,
     'params': [{'name': 'length', 'label': '周期', 'default': 12,
                 'type': 'int'}]},
    {'key': 'BOLL', 'label': 'BOLL 布林带', 'overlay': True,
     'params': [{'name': 'length', 'label': '周期', 'default': 20,
                 'type': 'int'},
                {'name': 'width', 'label': '倍数', 'default': 2,
                 'type': 'float'}]},
    {'key': 'MACD', 'label': 'MACD', 'overlay': False, 'pane': 'MACD',
     'params': [{'name': 'fast', 'label': '快线', 'default': 12,
                 'type': 'int'},
                {'name': 'slow', 'label': '慢线', 'default': 26,
                 'type': 'int'},
                {'name': 'signal', 'label': '信号', 'default': 9,
                 'type': 'int'}]},
    {'key': 'KDJ', 'label': 'KDJ', 'overlay': False, 'pane': 'KDJ',
     'params': [{'name': 'length', 'label': '周期', 'default': 9,
                 'type': 'int'},
                {'name': 'k', 'label': 'K 平滑', 'default': 3,
                 'type': 'int'},
                {'name': 'd', 'label': 'D 平滑', 'default': 3,
                 'type': 'int'}]},
    {'key': 'RSI', 'label': 'RSI', 'overlay': False, 'pane': 'RSI',
     'params': [{'name': 'length', 'label': '周期', 'default': 14,
                 'type': 'int'}]},
]

#: 每个指标的默认颜色（前端也会用它）
COLORS = {
    'MA': ['#f6c343', '#2196f3', '#e91e63', '#8bc34a', '#00bcd4'],
    'EMA': ['#ff9800', '#9c27b0'],
    'BOLL': ['#78909c', '#26a69a', '#26a69a'],
    'MACD': ['#4caf50', '#ef5350', '#90a4ae'],
    'KDJ': ['#f6c343', '#2196f3', '#e91e63'],
    'RSI': ['#ab47bc'],
}


def _catalog_item(key: str) -> Optional[dict]:
    for item in CATALOG:
        if item['key'] == key:
            return item
    return None


def default_params(key: str) -> Dict[str, Any]:
    item = _catalog_item(key) or {}
    return {param['name']: param['default'] for param in item.get('params', [])}


def _stamps(frame) -> List[int]:
    """天勤纳秒 → unix 秒 ✓"""
    out: List[int] = []
    for value in frame['datetime'].tolist():
        try:
            out.append(int(value) // 1_000_000_000)
        except (TypeError, ValueError):
            out.append(0)
    return out


def _series(stamps: List[int], values) -> List[list]:
    out: List[list] = []
    for stamp, value in zip(stamps, values):
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number != number:                 # NaN
            continue
        out.append([stamp, number])
    return out


def compute(symbol: str, frame, selected: List[Dict[str, Any]],
            limit: int = 600,
            errors: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """按 ``selected``（``[{key, params}]``）算一整套线，返回一个补丁 ✓

    ``errors``：出错的指标 `{key: 错误信息}`（调用方据此**不把指标加到图上**
    并弹窗提醒 ✓）
    """
    payload: Dict[str, Any] = {'type': 'indicator', 'symbol': symbol,
                               'items': []}
    if frame is None or len(frame) == 0:
        return payload
    try:
        close = frame['close'].astype('float64')
    except Exception:                                        # noqa: BLE001
        return payload
    stamps = _stamps(frame)
    for entry in selected or []:
        key = str(entry.get('key') or '').upper()
        params = {**default_params(key), **(entry.get('params') or {})}
        try:
            items = _build(key, frame, close, stamps, params)
        except Exception as error:                               # noqa: BLE001
            print(f'[desk] 指标 {key} 计算失败: {error!r}')
            if errors is not None:
                errors[key] = f'{type(error).__name__}: {error}'
            items = []
        for item in items:
            item['data'] = item['data'][-int(limit):]
            item.setdefault('source', key)      # 删菜单按「指标」分组 ✓
            payload['items'].append(item)
    return payload


def _build(key: str, frame, close, stamps: List[int],
           params: Dict[str, Any]) -> List[dict]:
    colors = COLORS.get(key, ['#90a4ae'])
    length = int(params.get('length') or 20)
    if key == 'MA':
        values = close.rolling(max(2, length)).mean()
        return [_line(f'MA{length}', f'MA{length}', stamps, values, colors[0])]
    if key == 'EMA':
        span = max(2, length)
        values = close.ewm(span=span, adjust=False).mean()
        return [_line(f'EMA{span}', f'EMA{span}', stamps, values, colors[0])]
    if key == 'BOLL':
        window = max(2, length)
        middle = close.rolling(window).mean()
        deviation = close.rolling(window).std(ddof=0)
        width = float(params.get('width') or 2)
        return [
            _line(f'BOLL{window}UP', f'BOLL 上轨', stamps,
                  middle + deviation * width, colors[1]),
            _line(f'BOLL{window}', 'BOLL 中轨', stamps, middle, colors[0]),
            _line(f'BOLL{window}DN', 'BOLL 下轨', stamps,
                  middle - deviation * width, colors[2]),
        ]
    if key == 'MACD':
        fast = max(2, int(params.get('fast') or 12))
        slow = max(fast + 1, int(params.get('slow') or 26))
        signal = max(2, int(params.get('signal') or 9))
        dif = close.ewm(span=fast, adjust=False).mean() - \
            close.ewm(span=slow, adjust=False).mean()
        dea = dif.ewm(span=signal, adjust=False).mean()
        histogram = (dif - dea) * 2.0
        return [
            _line('MACD_DIF', 'DIF', stamps, dif, colors[0], pane='MACD'),
            _line('MACD_DEA', 'DEA', stamps, dea, colors[1], pane='MACD'),
            _hist('MACD_HIST', 'MACD', stamps, histogram, colors[2],
                  pane='MACD'),
        ]
    if key == 'KDJ':
        window = max(2, length)
        low = frame['low'].astype('float64').rolling(window).min()
        high = frame['high'].astype('float64').rolling(window).max()
        span = (high - low).replace(0, float('nan'))
        rsv = ((close - low) / span * 100.0).fillna(50.0)
        k_period = max(1, int(params.get('k') or 3))
        d_period = max(1, int(params.get('d') or 3))
        k = rsv.ewm(alpha=1.0 / k_period, adjust=False).mean()
        d = k.ewm(alpha=1.0 / d_period, adjust=False).mean()
        j = 3.0 * k - 2.0 * d
        return [
            _line('KDJ_K', 'K', stamps, k, colors[0], pane='KDJ'),
            _line('KDJ_D', 'D', stamps, d, colors[1], pane='KDJ'),
            _line('KDJ_J', 'J', stamps, j, colors[2], pane='KDJ'),
        ]
    if key == 'RSI':
        window = max(2, length)
        delta = close.diff()
        gain = delta.clip(lower=0.0)
        loss = (-delta).clip(lower=0.0)
        avg_gain = gain.ewm(alpha=1.0 / window, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / window, adjust=False).mean()
        rsi = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss.replace(0, float('nan')))
        return [_line(f'RSI{window}', f'RSI{window}', stamps, rsi, colors[0],
                      pane='RSI')]
    return []


def _line(key: str, label: str, stamps: List[int], values, color: str,
          pane: str = '') -> dict:
    item = {'key': key, 'label': label, 'overlay': not pane, 'kind': 'line',
            'color': color, 'data': _series(stamps, values)}
    if pane:
        item['pane'] = pane
    return item


def _hist(key: str, label: str, stamps: List[int], values, color: str,
          pane: str = '') -> dict:
    item = {'key': key, 'label': label, 'overlay': not pane, 'kind': 'hist',
            'color': color, 'data': _series(stamps, values)}
    if pane:
        item['pane'] = pane
    return item
