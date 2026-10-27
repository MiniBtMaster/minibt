"""行情「看起来不更新」的回归测试（天勤期货报价 / K 线占位帧）。

背景（用户实测）：

* 行情报价里「最新价 / 买一价 / 成交量…」显示 **NaN**，只有涨跌停价 /
  昨收 / 昨结算有值 —— 天勤的占位行情里这些字段就是 ``NaN``，以前直接
  透传给前端 → 表格显示字面量「NaN」（miniqt 是空单元格）；
* 「行情更新时间」比实际晚 **8 小时**（18:42 的行情显示成 02:42，
  看起来像隔夜缓存）—— ``Quote.datetime`` 本来就是**北京时间**，
  只有 K 线是 UTC 纳秒；
* 实时图表「打开只显示 2 根 K 线」—— ``_fast_call`` 不等初始化时
  ``get_kline_serial`` 返回的是**定长占位表**（``datetime = 0``、
  OHLC 全 NaN），长度一直等于请求宽度 → 后端判不出「长度变了」→
  只推增量 2 根。
"""
import json
import math
import pathlib

import pytest

from minibt.desk import protocol
from minibt.desk import symbols as _symbols

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


class _Quote:
    """天勤「盘前 / 未订阅完成」的占位行情（动态字段全是 NaN）"""

    last_price = float('nan')
    bid_price1 = float('nan')
    ask_price1 = float('nan')
    volume = 0
    pre_close = 5379.0
    pre_settlement = 5418.0
    upper_limit = 5743.0
    lower_limit = 5093.0
    price_tick = 1.0
    datetime = '2026-10-26 18:42:32.211000'      # ← 北京时间 ✓
    instrument_name = '豆一2701'


# ------------------------------------------------------------ 报价行
def test_quote_row_turns_nan_into_none():
    row = _symbols.quote_row('DCE.a2701', '豆一2701', _Quote())
    assert row['last'] is None                    # 不再是 NaN ✓
    assert row['bid_price1'] is None
    assert row['chg'] is None and row['chg_pct'] is None
    assert row['volume'] == 0
    # 静态字段（涨跌停 / 昨收 / 昨结）照旧保留 ✓
    assert row['upper_limit'] == 5743.0
    assert row['pre_close'] == 5379.0
    assert row['pre_settlement'] == 5418.0


def test_quote_row_json_has_no_nan_literal():
    """Qt 壳是 run_script（JS 能认 NaN），浏览器壳走 JSON.parse（不能 ✗）"""
    row = _symbols.quote_row('DCE.a2701', '豆一2701', _Quote())
    payload = protocol.encode_patch(protocol.patch_rows_update([row]))
    assert 'NaN' not in payload
    assert 'nan' not in payload.lower()
    data = json.loads(payload[len('window.__desk.applyPatch('):-2])
    assert data['rows'][0]['last'] is None


def test_quote_time_is_not_shifted_for_futures():
    """天勤 ``Quote.datetime`` 已是北京时间 → 不能再 +8 ✓"""
    from minibt.desk.feeds import FuturesFeed

    assert FuturesFeed.time_shift_hours == 8      # K 线仍是 UTC → +8 ✓
    assert FuturesFeed.quote_shift_hours == 0     # 报价不再平移 ✓
    feed = FuturesFeed.__new__(FuturesFeed)
    feed.api = object()
    feed._names = {}
    feed._lock = __import__('threading').Lock()
    row = feed.row_of('DCE.a2701', _Quote())
    assert row['quote_time'] == '18:42:32'        # 而不是 02:42:32 ✓


def test_placeholder_quote_time_is_blank():
    class _Empty:
        datetime = ''

    row = _symbols.quote_row('DCE.a2701', '', _Empty())
    assert row['quote_time'] == ''


# ------------------------------------------------------------ K 线占位帧
def _frame(rows):
    pd = pytest.importorskip('pandas')
    return pd.DataFrame(rows)


def test_bars_from_frame_drops_placeholder_rows():
    """天勤占位帧：datetime = 0、OHLC 全 NaN → 一根都不要 ✓"""
    frame = _frame({
        'datetime': [0, 0, 1_700_000_000_000_000_000],
        'open': [float('nan'), float('nan'), 10.0],
        'high': [float('nan'), float('nan'), 12.0],
        'low': [float('nan'), float('nan'), 9.0],
        'close': [float('nan'), float('nan'), 11.0],
        'volume': [float('nan'), float('nan'), 100],
    })
    bars = protocol.bars_from_frame(frame)
    assert len(bars) == 1
    assert bars[0]['time'] == 1_700_000_000
    assert bars[0]['close'] == 11.0
    assert math.isfinite(bars[0]['volume'])


def test_bars_from_frame_never_emits_nan():
    frame = _frame({'datetime': [1_700_000_000_000_000_000],
                    'open': [float('nan')], 'high': [float('nan')],
                    'low': [float('nan')], 'close': [1.0],
                    'volume': [float('nan')]})
    bar = protocol.bars_from_frame(frame)[0]
    assert all(math.isfinite(value) for key, value in bar.items())


def test_kline_signature_counts_only_real_bars():
    from minibt.desk.app import _kline_signature

    frame = _frame({
        'datetime': [0, 0, 1_700_000_000_000_000_000,
                     1_700_000_060_000_000_000],
        'close': [float('nan'), float('nan'), 10.0, 11.0],
    })
    count, first, last = _kline_signature(frame)
    assert count == 2
    assert first == 1_700_000_000 and last == 1_700_000_060
    # 全占位 → 0 根（别再推占位 K 线 ✓）
    empty = _frame({'datetime': [0, 0], 'close': [float('nan')] * 2})
    assert _kline_signature(empty) == (0, 0, 0)
    assert _kline_signature(None) == (0, 0, 0)


def test_refresh_tabs_uses_valid_bar_count_for_full_replace():
    """占位 → 有数据时必须**全量**重推（否则只推 2 根 ✗）"""
    source = _read('minibt/desk/app.py')
    assert "_kline_signature(frame)" in source
    assert "count != int(info.get('_kline_bars_len') or 0)" in source
    assert "_note_kline_state" in source
    # 旧的「按 len(frame) 判长度」逻辑已经不能再出现 ✓
    assert "_kline_frame_len') or 0)" not in source
