"""富途（OpenD）优先的数据源：**快照 / 资金流 / 名称**（P2，v1.3.7-64）。

用户 2026-11-08：「优先使用富途获取信息，如果用户没连接富途才用 AkShare」。

富途 OpenAPI 能给的东西（本模块用到）：

| 能力 | 接口 | 说明 |
| --- | --- | --- |
| 快照（价格 / PE / PB / 市值 / 股息率 / 上市日 / 每手） | `get_market_snapshot` | **实时**，比东财稳 |
| 资金流（主力净流入） | `get_capital_flow` / `get_capital_distribution` | 东财也有但慢 |
| 名称 / 每手 | `get_stock_basicinfo` | 清单已在 `stocks.py` 用 |

富途**没有**新闻 / 财报 / 公告接口 → 这三类仍走 AkShare（会在回执里标 `source`）。

本模块**不新建连接**：直接用 desk 已经连好的 `StockApi._ctx`；没连富途就返回
`None`，调用方自动降级到 AkShare ✓。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .. import stocks as _stocks


def _futu():
    try:
        return _stocks.ensure_futu()
    except Exception:                                         # noqa: BLE001
        return None


def context(desk) -> Any:
    """拿 desk 上已连接的富途 `OpenQuoteContext`（没有 → None ✓）"""
    feed = getattr(desk, 'stocks', None)
    api = getattr(feed, 'api', None)
    return _stocks._ctx(api)


def available(desk) -> bool:
    return context(desk) is not None


def _num(value) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:                                      # NaN
        return None
    return number


def snapshot(desk, symbol: str) -> Dict[str, Any]:
    """个股 / 标的快照（PE / PB / 市值 / 股息率…）✓"""
    ctx = context(desk)
    if ctx is None:
        return {}
    code = _stocks.to_futu_code(symbol)
    if not code:
        return {}
    futu = _futu()
    ok = int(getattr(futu, 'RET_OK', 0)) if futu is not None else 0
    try:
        ret, frame = ctx.get_market_snapshot([code])
    except Exception as error:                                # noqa: BLE001
        return {'error': f'{type(error).__name__}: {error}'}
    if ret != ok or frame is None or getattr(frame, 'empty', True):
        return {'error': f'富途快照失败（ret={ret}）'}
    row = frame.to_dict('records')[0]
    fields = [
        ('name', '名称'), ('last_price', '最新价'), ('prev_close_price', '昨收'),
        ('open_price', '开盘'), ('high_price', '最高'), ('low_price', '最低'),
        ('volume', '成交量'), ('turnover', '成交额'),
        ('turnover_rate', '换手率'), ('pe_ratio', '市盈率'),
        ('pb_ratio', '市净率'), ('pe_ttm_ratio', '市盈率TTM'),
        ('dividend_ratio_ttm', '股息率TTM'),
        ('total_market_val', '总市值'), ('circular_market_val', '流通市值'),
        ('lot_size', '每手'), ('listing_date', '上市日期'),
        ('stock_owner', '所属'), ('suspension', '停牌'),
    ]
    out: Dict[str, Any] = {'symbol': symbol, 'source': 'futu',
                           'code': code}
    for key, label in fields:
        value = row.get(key)
        if value in (None, '', 'N/A'):
            continue
        number = _num(value)
        out[key] = round(number, 4) if number is not None else value
        out.setdefault('items', []).append(
            {'label': label, 'value': out.get(key)})
    return out


def capital_flow(desk, symbol: str) -> Dict[str, Any]:
    """资金流（主力 / 大单净流入；富途独有 ✓）"""
    ctx = context(desk)
    if ctx is None:
        return {}
    code = _stocks.to_futu_code(symbol)
    if not code:
        return {}
    futu = _futu()
    ok = int(getattr(futu, 'RET_OK', 0)) if futu is not None else 0
    out: Dict[str, Any] = {'symbol': symbol, 'source': 'futu'}
    try:
        ret, frame = ctx.get_capital_distribution(code)
        if ret == ok and frame is not None and not getattr(frame, 'empty', True):
            row = frame.to_dict('records')[-1]
            for key, label in (('capital_in_super', '超大单流入'),
                               ('capital_out_super', '超大单流出'),
                               ('capital_in_big', '大单流入'),
                               ('capital_out_big', '大单流出'),
                               ('capital_in_mid', '中单流入'),
                               ('capital_out_mid', '中单流出'),
                               ('capital_in_small', '小单流入'),
                               ('capital_out_small', '小单流出')):
                number = _num(row.get(key))
                if number is not None:
                    out[key] = number
                    out.setdefault('items', []).append(
                        {'label': label, 'value': round(number, 2)})
    except Exception as error:                                # noqa: BLE001
        out['error'] = f'{type(error).__name__}: {error}'
    try:
        ret, frame = ctx.get_capital_flow(code)
        if ret == ok and frame is not None and not getattr(frame, 'empty', True):
            row = frame.to_dict('records')[-1]
            inflow = _num(row.get('inflow'))
            if inflow is not None:
                out['inflow'] = round(inflow, 2)
                out.setdefault('items', []).append(
                    {'label': '净流入', 'value': round(inflow, 2)})
    except Exception:                                         # noqa: BLE001
        pass
    return out


def names(desk, symbols: List[str]) -> Dict[str, str]:
    """批量取名称（从快照里拿；失败返回空字典 ✓）"""
    ctx = context(desk)
    if ctx is None:
        return {}
    codes = [code for code in (_stocks.to_futu_code(item)
                               for item in symbols or []) if code]
    if not codes:
        return {}
    futu = _futu()
    ok = int(getattr(futu, 'RET_OK', 0)) if futu is not None else 0
    try:
        ret, frame = ctx.get_market_snapshot(codes)
        if ret != ok or frame is None or getattr(frame, 'empty', True):
            return {}
        out: Dict[str, str] = {}
        for row in frame.to_dict('records'):
            code = str(row.get('code') or '')
            name = str(row.get('name') or '')
            if code and name:
                out[_stocks.from_futu_code(code)] = name
        return out
    except Exception:                                         # noqa: BLE001
        return {}
