"""合约清单 / 类型与交易所映射（搬自 miniqt，纯数据，无 Qt 依赖）。"""
from __future__ import annotations

import math
from typing import Dict, List

#: 品种类型（miniqt `INS_CLASS_MAP` / `CONT_MAIN`）
DEFAULT_FUTURES_TYPES = [
    ('FUT', '期货'), ('CONT', '主连'), ('INDEX', '指数'),
    ('OPTION', '期权'), ('STOCK', '股票'), ('CONT_MAIN', '主力'),
]

#: 交易所（miniqt `EXCHANGE_ID_MAP`）
DEFAULT_EXCHANGES: Dict[str, List[tuple]] = {
    'FUT': [
        ('CFFEX', '中金所'), ('SHFE', '上期所'), ('DCE', '大商所'),
        ('CZCE', '郑商所'), ('INE', '能源交易所(原油)'),
        ('GFEX', '广州期货交易所'),
    ],
    'CONT': [
        ('CFFEX', '中金所'), ('SHFE', '上期所'), ('DCE', '大商所'),
        ('CZCE', '郑商所'), ('INE', '能源交易所(原油)'),
        ('GFEX', '广州期货交易所'), ('KQD', '外盘主连'),
    ],
    'INDEX': [
        ('CFFEX', '中金所'), ('SHFE', '上期所'), ('DCE', '大商所'),
        ('CZCE', '郑商所'), ('INE', '能源交易所(原油)'),
    ],
    'CONT_MAIN': [
        ('CFFEX', '中金所'), ('SHFE', '上期所'), ('DCE', '大商所'),
        ('CZCE', '郑商所'), ('INE', '能源交易所(原油)'),
        ('GFEX', '广州期货交易所'),
    ],
    'STOCK': [('SSE', '上交所'), ('SZSE', '深交所'), ('HK', '港股'), ('US', '美股')],
    'OPTION': [
        ('CFFEX', '中金所'), ('SHFE', '上期所'), ('DCE', '大商所'),
        ('CZCE', '郑商所'), ('INE', '能源交易所(原油)'),
        ('GFEX', '广州期货交易所'),
        ('HK_SECURITY', '港股期权'), ('US_SECURITY', '美股期权'),
    ],
}

#: 表格列（与 `jslib/src/desk/quote-page.ts` 的 `QUOTE_COLUMNS` 对应）
ROW_FIELDS = (
    'symbol', 'name', 'last', 'bid_price1', 'bid_volume1', 'ask_price1',
    'ask_volume1', 'upper_limit', 'lower_limit', 'chg', 'chg_pct', 'volume',
    'open', 'high', 'low', 'pre_close', 'pre_settlement', 'quote_time',
    'price_tick', 'decimals', 'spark',
)


def decimals_from_tick(tick, default: int = 2) -> int:
    """最小变动价位 → 小数位（1 → 0 位、0.5 → 1 位、0.01 → 2 位 ✓）

    ⚠ 天勤刚连上时 `price_tick` 可能是 **NaN**（还没收到数据）→
    `round(nan)` 会抛 `ValueError: cannot convert float NaN to integer`
    （用户实测「刷新失败」✗）→ 这里先挡掉 NaN / inf ✓
    """
    try:
        value = abs(float(tick))
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value) or value <= 0:
        return default
    for digits in range(0, 7):
        scaled = value * (10 ** digits)
        if abs(scaled - round(scaled)) < 1e-9:
            return digits
    return 6


def is_tradeable(symbol: str) -> bool:
    """这个合约**能不能下单**（主连 / 指数只是行情，不能交易 ✓）

    天勤里 `KQ.m@…`（主连）/ `KQ.i@…`（指数）是「虚拟合约」，
    `TqAccount` 对它们做 `get_position` / `insert_order` / `TargetPosTask`
    会**卡住或报错**（实盘用户实测：主连图表一打开整个终端就没数据 ✗）。
    所以交易相关的调用一律先过这一关 ✓
    """
    text = str(symbol or '').upper()
    if not text:
        return False
    return not text.startswith('KQ.')


def known_exchanges() -> set:
    """已知交易所前缀（`SHFE` / `DCE` / `SSE` …；缓存校验用 ✓）"""
    names = {str(key).upper() for key in DEFAULT_EXCHANGES}
    for items in DEFAULT_EXCHANGES.values():
        names.update(str(key).upper() for key, _ in items)
    names.update({'SSE', 'SZSE', 'BSE', 'HKEX', 'NASDAQ', 'NYSE', 'AMEX'})
    return names


def chips(items):
    """``[(key, label), …]`` → ``[{'key':…, 'label':…}, …]``（给 JS 用 ✓）"""
    return [{'key': str(key), 'label': str(label)} for key, label in items]


def row(**values) -> dict:
    """只保留已知字段（多余的丢掉，缺失的补 None ✓）"""
    """只保留已知字段（多余的丢掉，缺失的补 None ✓）"""
    return {field: values.get(field) for field in ROW_FIELDS}


def quote_row(symbol: str, name: str, quote, *, spark=None,
              shift_hours: int = 0) -> dict:
    """天勤 / ``StockApi`` 的 quote → 报价表一行（涨跌用昨结算算，同 miniqt ✓）

    ⚠ ``Quote.datetime`` 是**北京时间字符串**（tqsdk 文档：
    “行情从交易所发出的时间(北京时间)”），而 ``KLine.datetime`` 才是
    UTC 纳秒。以前两边都按 +8 平移 → 「行情更新时间」比实际**晚 8 小时**
    （用户看到 18:42 的行情显示成 02:42，误以为数据是隔夜缓存 ✗）。
    """
    last = _num(getattr(quote, 'last_price', None))
    pre_settle = _num(getattr(quote, 'pre_settlement', None))
    pre_close = _num(getattr(quote, 'pre_close', None))
    base = pre_settle if pre_settle else pre_close
    chg = (last - base) if (last is not None and base) else None
    chg_pct = (chg / base * 100.0) if (chg is not None and base) else None
    return row(
        symbol=symbol, name=name or getattr(quote, 'name', '') or '',
        last=last,
        bid_price1=_num(getattr(quote, 'bid_price1', None)),
        bid_volume1=_num(getattr(quote, 'bid_volume1', None)),
        ask_price1=_num(getattr(quote, 'ask_price1', None)),
        ask_volume1=_num(getattr(quote, 'ask_volume1', None)),
        upper_limit=_num(getattr(quote, 'upper_limit', None)),
        lower_limit=_num(getattr(quote, 'lower_limit', None)),
        chg=chg, chg_pct=chg_pct,
        volume=_num(getattr(quote, 'volume', None)),
        open=_num(getattr(quote, 'open', None)),
        high=_num(getattr(quote, 'highest', None)),
        low=_num(getattr(quote, 'lowest', None)),
        pre_close=pre_close, pre_settlement=pre_settle,
        quote_time=_clock(getattr(quote, 'datetime', ''), shift_hours),
        price_tick=_num(getattr(quote, 'price_tick', None)),
        decimals=decimals_from_tick(getattr(quote, 'price_tick', None)),
        spark=spark,
    )


def _num(value):
    """安全转 float：``None`` / 非法 / **NaN / inf** → ``None`` ✓

    天勤的占位行情（开盘前 / 未订阅）里 ``last_price`` 是 **NaN**；
    以前直接透传 → JSON 里出现 ``NaN``，前端表格就显示字面量
    「NaN」（miniqt 是空单元格 → 用户以为 desk 数据全坏了 ✗）。
    """
    try:
        number = None if value is None else float(value)
    except (TypeError, ValueError):
        return None
    if number is None or not math.isfinite(number):
        return None
    return number

def _clock(value, shift_hours: int = 0) -> str:
    """天勤 ``datetime``（UTC）→ 本地 ``HH:MM:SS``（默认不平移 ✓）"""
    text = str(value or '').strip()
    if not text:
        return ''
    if shift_hours:
        try:
            import datetime as _dt

            stamp = _dt.datetime.fromisoformat(text.replace('Z', ''))
            stamp = stamp + _dt.timedelta(hours=int(shift_hours))
            return stamp.strftime('%H:%M:%S')
        except Exception:                                        # noqa: BLE001
            pass
    # 有微秒时 `text[-8:]` 会变成 "0.123456" ✗ → 先去掉小数部分 ✓
    head = text.split('.')[0]
    clock = head[-8:]
    # 占位行情的时间可能是 0 / nan → 不要显示成乱码 ✓
    return clock if clock[:2].isdigit() else ''
