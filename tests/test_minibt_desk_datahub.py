"""本地数据平台：质检 / 重采样 / 换月复权 / Tick 聚合 / 行情库。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from minibt.desk import datahub
from minibt.desk.datahub import (DataCatalog, book_snapshot, duckdb_available,
                                 normalize_ohlcv, quality_report, read_table,
                                 resample_bars, roll_contracts, ticks_to_bars,
                                 to_parquet)


def _frame(rows=120, symbol='SHFE.demo', start='2024-01-01', volume=10.0):
    close = 100 + np.arange(rows, dtype=float)
    return pd.DataFrame({
        'datetime': pd.date_range(start, periods=rows, freq='1min'),
        'open': close - 0.5, 'high': close + 1.0,
        'low': close - 1.0, 'close': close,
        'volume': volume, 'symbol': symbol,
    })


def test_normalize_ohlcv_renames_and_sorts():
    raw = pd.DataFrame({
        'time': ['2024-01-01 00:02', '2024-01-01 00:01'],
        'o': [2, 1], 'h': [3, 2], 'l': [1, 0], 'c': [2, 1], 'v': [5, 4],
    })
    frame = normalize_ohlcv(raw, symbol='X')
    assert list(frame.columns[:6]) == list(datahub.COLUMNS)
    assert frame['datetime'].is_monotonic_increasing
    assert frame['symbol'].iloc[0] == 'X'
    assert frame['close'].tolist() == [1, 2]


def test_quality_report_flags_bad_bars():
    frame = _frame(20)
    frame.loc[1, 'high'] = 0          # high < low
    frame.loc[2, 'close'] = np.nan    # missing price
    frame.loc[3, 'volume'] = 0
    report = quality_report(frame)
    kinds = {item['kind'] for item in report['issues']}
    assert {'ohlc_inconsistent', 'missing_price', 'zero_volume'} <= kinds
    assert report['score'] < 100
    assert report['ok'] is False
    assert quality_report(pd.DataFrame())['score'] == 0.0


def test_resample_and_align():
    frame = _frame(30)
    out = resample_bars(frame, '5min')
    assert len(out) == 6
    assert out['volume'].iloc[0] == 50
    assert out['close'].iloc[0] == frame['close'].iloc[4]


def test_roll_contracts_ratio_and_difference():
    first = _frame(30, symbol='A')
    second = _frame(30, symbol='B', start='2024-01-01 00:30')
    second[['open', 'high', 'low', 'close']] *= 2
    ratio = roll_contracts({'A': first, 'B': second}, mode='ratio')
    assert len(ratio) == 60
    # 换月点之后的价格应回到 A 的量级（比例复权）
    assert ratio['close'].iloc[-1] < 250
    diff = roll_contracts({'A': first, 'B': second}, mode='difference')
    assert len(diff) == 60
    none = roll_contracts({'A': first, 'B': second}, mode='none')
    assert none['close'].iloc[-1] == second['close'].iloc[-1]


def test_ticks_to_bars_and_book_snapshot():
    ticks = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=120, freq='1s'),
        'last_price': 100 + np.arange(120) * 0.1,
        'volume': 1,
        'bid_price1': 99.9, 'ask_price1': 100.1,
        'bid_volume1': 3, 'ask_volume1': 4,
    })
    bars = ticks_to_bars(ticks, seconds=60)
    assert len(bars) == 2
    assert bars['close'].iloc[0] == pytest.approx(ticks['last_price'].iloc[59])
    snap = book_snapshot(ticks)
    assert snap['bid_price1'] == 99.9
    assert snap['ask_volume1'] == 4


def test_read_and_export_parquet(tmp_path):
    if not duckdb_available():
        pytest.skip('需要 duckdb 写 Parquet')
    frame = _frame(20)
    csv_path = tmp_path / 'demo.csv'
    frame.to_csv(csv_path, index=False)
    loaded = read_table(str(csv_path), symbol='demo')
    assert len(loaded) == 20
    parquet = to_parquet(loaded, str(tmp_path / 'demo.parquet'))
    again = read_table(parquet)
    assert len(again) == 20
    assert again['close'].iloc[-1] == loaded['close'].iloc[-1]


def test_catalog_scan_quality_and_sql(tmp_path):
    frame = _frame(40, symbol='rb')
    frame.to_csv(tmp_path / 'rb2610_60.csv', index=False)
    (tmp_path / 'broken.csv').write_text('a,b\n1,2\n', encoding='utf-8')
    catalog = DataCatalog([str(tmp_path)])
    items = catalog.refresh(force=True)
    names = {item['name'] for item in items}
    assert {'rb2610_60', 'broken'} <= names
    missing = next(item for item in items if item['name'] == 'broken')
    assert 'error' in missing
    report = catalog.quality('rb2610_60')
    assert report['rows'] == 40
    resampled = catalog.resample('rb2610_60', '5min')
    assert len(resampled) == 8
    rolled = catalog.roll(['rb2610_60'], mode='ratio')
    assert len(rolled) == 40
    if duckdb_available():
        rows = catalog.query('SELECT * FROM rb2610_60 LIMIT 3')
        assert len(rows) == 3
        with pytest.raises(ValueError):
            catalog.query('DELETE FROM rb2610_60')
    snapshot = catalog.snapshot()
    assert snapshot['type'] == 'datahub'
    assert snapshot['folders'] == [str(tmp_path)]


def test_default_folders_include_builtin_local_datas():
    from minibt.desk.datahub import default_folders
    folders = default_folders()
    assert any(path.replace(chr(92), '/').endswith('/minibt/data/test')
               for path in folders), folders
    catalog = DataCatalog(folders)
    names = {item['name'] for item in catalog.refresh(force=True)}
    assert {'test', 'l2609_60', 'pp2609_60'} <= names
