"""The contract cache in `miniqt/app/common/database_manager.py`.

The store used to be DuckDB, which cost us three hard lessons:

* one process at a time - the file was exclusively locked, so a second miniqt
  could not even open it;
* a damaged ART index could only be repaired by rebuilding the table, and the
  broken `DatabaseInstance` was cached per path *in-process*, so it could never be
  recovered without restarting;
* the failure mode was a native abort (`_duckdb.pyd`, 0xc0000409) with no Python
  traceback at all - the app just vanished a second after logging in, while 45
  refresh tasks hammered the poisoned instance.

SQLite removes all three: several processes can share the file (WAL), `PRAGMA
quick_check` detects damage deterministically, and damage surfaces as a catchable
exception that the manager can rebuild its way out of.

    pytest tests/test_miniqt_db.py
"""
from __future__ import annotations

import json
import os
import pathlib
import random
import shutil
import sqlite3
import subprocess
import sys
import threading

import pandas as pd
import pytest

database_manager = pytest.importorskip('miniqt.app.common.database_manager')

ROWS = 300
THREADS = 8
ROUNDS = 10
BATCH = 40
ROOT = pathlib.Path(__file__).resolve().parents[1]

miniqt = pytest.importorskip('miniqt')
if not pathlib.Path(miniqt.__file__).resolve().parent.is_relative_to(ROOT):
    # 从 sdist 里跑、而环境装的是 site-packages 版 miniqt 时跳过
    pytest.skip('miniqt 不是本仓库里的源码副本（跳过缓存库单测）',
                allow_module_level=True)


def ids_for(seed: int) -> list:
    rng = random.Random(seed)
    return [f'EX{i:04d}' for i in rng.sample(range(ROWS), BATCH)]


def frame_for(ids, value: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame({
        'instrument_id': list(ids),
        'instrument_name': list(ids),
        'ins_class': ['CONT_MAIN'] * len(ids),
        'exchange_id': ['SHFE'] * len(ids),
        'price_tick': [float(value)] * len(ids),
    })


def fresh_manager(db_path: str):
    manager_class = database_manager.DatabaseManager
    manager_class._instance = None                  # the class is a singleton
    return manager_class(db_path)


@pytest.fixture()
def db(tmp_path):
    manager = fresh_manager(str(tmp_path / 'contracts.sqlite3'))
    manager.save_symbol_info(frame_for([f'EX{i:04d}' for i in range(ROWS)]))
    try:
        yield manager
    finally:
        manager.close()
        database_manager.DatabaseManager._instance = None


# --------------------------------------------------------------------------
# concurrency
# --------------------------------------------------------------------------

def test_concurrent_saves_keep_the_database_usable(db):
    errors = []

    def worker(offset: int):
        for round_no in range(ROUNDS):
            try:
                db.save_symbol_info(frame_for(ids_for(offset), offset + round_no))
            except Exception as error:              # noqa: BLE001 - this is the check
                errors.append(f'{type(error).__name__}: {error}')
                return

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == [], 'concurrent saves must not fail'
    rows = db.connection.execute('SELECT COUNT(*) FROM symbol_info').fetchone()[0]
    assert rows == ROWS


def test_concurrent_saves_and_deletes_stay_consistent(db):
    errors = []

    def saver(offset: int):
        for round_no in range(ROUNDS):
            try:
                db.save_symbol_info(frame_for(ids_for(offset), offset + round_no))
            except Exception as error:              # noqa: BLE001
                errors.append(f'save: {type(error).__name__}: {error}')
                return

    def deleter():
        for index in range(ROUNDS):
            try:
                db.delete_symbol_info(ins_class='CONT_MAIN', exchange_id='SHFE')
                db.set_meta('contracts_refreshed_on', f'2026-01-{index + 1:02d}')
            except Exception as error:              # noqa: BLE001
                errors.append(f'delete: {type(error).__name__}: {error}')
                return

    threads = [threading.Thread(target=saver, args=(i,)) for i in range(THREADS)]
    threads.append(threading.Thread(target=deleter))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == [], 'saves and deletes must not interfere'
    rows = db.connection.execute('SELECT COUNT(*) FROM symbol_info').fetchone()[0]
    assert rows <= ROWS
    assert db.get_meta('contracts_refreshed_on') is not None


def test_two_processes_can_share_one_database(tmp_path):
    """The reason DuckDB had to go: its file lock allowed one process only.

    A second miniqt window (or any tool) can now open, read *and* write the same
    file while this process stays connected.
    """
    path = str(tmp_path / 'shared.sqlite3')
    manager = fresh_manager(path)
    manager.save_symbol_info(frame_for(['SHFE.rb2610']))

    script = f'''
import sys
sys.path.insert(0, {str(ROOT)!r})
import pandas as pd
from miniqt.app.common import database_manager as dbm
dbm.DatabaseManager._instance = None
db = dbm.DatabaseManager({path!r})
assert db.connection is not None, "the second process could not open the database"
assert db.get_symbol_info("CONT_MAIN") is not None, "the second process could not read"
ok = db.save_symbol_info(pd.DataFrame({{
    "instrument_id": ["DCE.m2609"], "instrument_name": ["m"],
    "ins_class": ["CONT_MAIN"], "exchange_id": ["DCE"], "price_tick": [2.0]}}))
assert ok, "the second process could not write"
db.close()
print("SECOND_PROCESS_OK")
'''
    result = subprocess.run([sys.executable, '-c', script], capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'SECOND_PROCESS_OK' in result.stdout

    # the first connection sees the row the other process wrote
    assert len(manager.get_symbol_info('CONT_MAIN')) == 2
    manager.close()
    database_manager.DatabaseManager._instance = None


def test_mixed_reads_and_writes_do_not_abort_the_process(tmp_path):
    """Run the mixed load in a subprocess: a regression fails this test instead of
    killing the test session."""
    script = pathlib.Path(__file__).with_name('_db_mixed_load.py')
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path / 'mixed.sqlite3')],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
    assert result.returncode == 0, (result.stdout[-2000:] + result.stderr[-2000:])
    assert 'MIXED_LOAD_OK' in result.stdout


# --------------------------------------------------------------------------
# values
# --------------------------------------------------------------------------

def test_values_are_converted_for_sqlite(tmp_path):
    """sqlite3 only binds None/int/float/str/bytes, so NaN, NaT, Timestamps and
    numpy scalars all have to be converted before they reach the driver."""
    import numpy as np

    manager = fresh_manager(str(tmp_path / 'values.sqlite3'))
    manager.save_symbol_info(pd.DataFrame({
        'instrument_id': ['SHFE.rb2610'],
        'instrument_name': ['螺纹钢'],
        'ins_class': ['CONT_MAIN'],
        'exchange_id': ['SHFE'],
        'price_tick': [np.float64(1.5)],
        'volume_multiple': [np.int64(10)],
        'expired': [np.bool_(False)],
        'expire_datetime': [pd.Timestamp('2026-10-15')],
        'option_class': [np.nan],
        'underlying_symbol': [pd.NaT],
    }))

    row = manager.connection.execute(
        'SELECT price_tick, volume_multiple, expired, expire_datetime, option_class, '
        'underlying_symbol FROM symbol_info').fetchone()
    assert row[0] == 1.5
    assert row[1] == 10
    assert row[2] == 0                       # bool -> integer
    assert row[3] == '2026-10-15 00:00:00'   # timestamp -> text
    assert row[4] is None                    # NaN -> NULL
    assert row[5] is None                    # NaT -> NULL
    manager.close()
    database_manager.DatabaseManager._instance = None


def test_reading_back_restores_booleans(db):
    db.save_symbol_info(pd.DataFrame({
        'instrument_id': ['SHFE.cu2608'], 'instrument_name': ['沪铜'],
        'ins_class': ['CONT_MAIN'], 'exchange_id': ['SHFE'], 'expired': [True]}))
    got = db.get_symbol_info('CONT_MAIN', 'SHFE')
    values = set(got['expired'])
    assert values <= {True, False}, f'expired should read back as bool, got {values}'


# --------------------------------------------------------------------------
# damage: detected, then rebuilt
# --------------------------------------------------------------------------

def test_a_damaged_file_is_detected_and_rebuilt(tmp_path):
    """The deterministic detection DuckDB could not give us.

    Damage must surface as an exception the manager can act on - never as a native
    abort - and the bad file is kept aside rather than silently deleted.
    """
    path = str(tmp_path / 'damaged.sqlite3')
    manager = fresh_manager(path)
    manager.save_symbol_info(frame_for([f'EX{i:04d}' for i in range(50)]))
    manager.close()
    database_manager.DatabaseManager._instance = None

    with open(path, 'r+b') as handle:            # scribble over the file header
        handle.seek(120)
        handle.write(b'NOT A SQLITE DATABASE' * 40)

    reopened = fresh_manager(path)
    try:
        assert reopened.connection is not None, 'the manager should recover'
        assert reopened.has_data() is False, 'a rebuilt database starts empty'
        aside = list(pathlib.Path(tmp_path).glob('damaged.sqlite3.corrupt-*'))
        assert aside, 'the damaged file should be kept as .corrupt-<timestamp>'
        # and it is usable again
        assert reopened.save_symbol_info(frame_for(['SHFE.rb2610'])) is True
    finally:
        reopened.close()
        database_manager.DatabaseManager._instance = None


def test_corruption_during_a_write_is_recovered_in_process(db, tmp_path):
    """A corruption error mid-run rebuilds the file and retries, instead of
    disabling the database (SQLite can do what DuckDB could not)."""
    real_executemany = db.connection.executemany

    state = {'raised': False}

    def failing_executemany(sql, rows):
        # the write path goes through _transaction() + executemany()
        if not state['raised'] and 'INSERT OR REPLACE INTO symbol_info' in sql:
            state['raised'] = True
            raise sqlite3.DatabaseError('database disk image is malformed')
        return real_executemany(sql, rows)

    db.connection.executemany = failing_executemany  # type: ignore[method-assign]
    assert db.save_symbol_info(frame_for(['SHFE.rb2610'], 5.0)) is True
    assert state['raised'] is True
    assert db._disabled is False                    # recovered, not disabled
    assert db.get_symbol_info('CONT_MAIN', 'SHFE') is not None


def test_ordinary_errors_do_not_rebuild_the_database(db, tmp_path):
    assert db.has_data()
    assert db._recover_connection(ValueError('some ordinary error')) is False
    assert db.has_data()


def test_a_busy_error_does_not_rebuild_the_database(db):
    """A lock conflict is temporary; rebuilding would throw away good data."""
    assert db._recover_connection(sqlite3.OperationalError('database is locked')) is False
    assert db.has_data()


def test_a_disabled_database_is_a_silent_no_op(tmp_path):
    """Last resort: if even the rebuild fails, every call returns a safe default
    instead of raising into a Qt slot (an exception there aborts the app)."""
    manager = fresh_manager(str(tmp_path / 'disabled.sqlite3'))
    manager.save_symbol_info(frame_for(['SHFE.rb2610']))
    manager._disable_database(RuntimeError('simulated unrecoverable failure'))

    assert manager._disabled is True
    assert manager.connection is None
    assert manager.save_symbol_info(frame_for(['SHFE.rb2610'])) is False
    assert manager.delete_symbol_info(ins_class='CONT_MAIN') is False
    assert manager.set_meta('x', 'y') is False
    assert manager.get_meta('x') is None
    assert manager.get_symbol_info('CONT_MAIN') is None
    assert manager.get_search_table() is None
    assert manager.has_data() is False
    assert manager.is_fresh_database() is False
    assert manager.get_ins_class_map() == {}
    manager.close()
    database_manager.DatabaseManager._instance = None


# --------------------------------------------------------------------------
# behaviour the rest of miniqt depends on
# --------------------------------------------------------------------------

def test_save_symbol_info_keeps_the_key_elf_search_table_in_sync(db):
    """The keyboard sprite reads symbol_search_table; it used to be rebuilt only at
    startup, so a fresh login could not search anything."""
    search = db.get_search_table()
    assert search is not None
    assert set(search.columns) == {'code', 'name', 'type', 'exchange'}
    assert 'EX0000' in set(search['code'])

    db.save_symbol_info(frame_for(['SHFE.rb2610']))
    assert 'SHFE.rb2610' in set(db.get_search_table()['code'])


def test_delete_symbol_info_filters_by_scope(db):
    db.save_symbol_info(pd.DataFrame({
        'instrument_id': ['SHFE.rb2610', 'DCE.m2609'],
        'instrument_name': ['a', 'b'],
        'ins_class': ['CONT_MAIN', 'CONT_MAIN'],
        'exchange_id': ['SHFE', 'DCE'],
    }))
    assert db.delete_symbol_info(ins_class='CONT_MAIN', exchange_id='SHFE') is True
    left = db.get_symbol_info('CONT_MAIN')
    assert list(left['instrument_id']) == ['DCE.m2609']

    assert db.delete_symbol_info(ins_class='CONT_MAIN') is True
    assert db.get_symbol_info('CONT_MAIN') is None


def test_meta_and_maps_round_trip(db):
    assert db.set_meta('contracts_refreshed_on', '2026-09-17') is True
    assert db.get_meta('contracts_refreshed_on') == '2026-09-17'
    assert db.get_meta('missing', 'fallback') == 'fallback'

    assert db.save_ins_class_map({'FUTURE': '期货', 'CONT_MAIN': '主力'}) is True
    assert db.get_ins_class_map() == {'FUTURE': '期货', 'CONT_MAIN': '主力'}
    assert db.save_exchange_id_map({'SHFE': '上期所'}) is True
    assert db.get_exchange_id_map() == {'SHFE': '上期所'}


def test_exchange_symbols_round_trip(db):
    assert db.save_exchange_symbols('CONT_MAIN', 'SHFE', ['SHFE.rb2610']) is True
    assert db.get_exchange_symbols('CONT_MAIN', 'SHFE') == ['SHFE.rb2610']
    assert db.save_exchange_symbols('CONT_MAIN', 'SHFE', ['SHFE.cu2608']) is True
    assert db.get_exchange_symbols('CONT_MAIN', 'SHFE') == ['SHFE.cu2608']
    assert db.get_exchange_symbols('CONT_MAIN', 'DCE') == []


def test_fresh_flag_follows_the_data(db):
    assert db.is_fresh_database() is False          # the fixture loaded 300 rows
    db.mark_database_populated()
    assert db.get_meta('fresh') == 'false'

    empty = fresh_manager(str(pathlib.Path(db.db_path).parent / 'empty.sqlite3'))
    assert empty.is_fresh_database() is True
    empty.close()
    database_manager.DatabaseManager._instance = None


def test_the_database_file_is_small(db):
    """DuckDB held this data in 70.8 MB + a 6.5 MB WAL."""
    size = os.path.getsize(db.db_path)
    assert size < 4 * 1024 * 1024, f'{size} bytes for {ROWS} rows is too much'


def test_list_values_are_stored_as_json(tmp_path):
    """天勤 returns ``trading_time_day`` / ``trading_time_night`` as **lists**.

    DuckDB has a LIST type so this used to work; SQLite binds scalars only, and a
    single unbindable value fails the *entire* executemany batch:

        Error binding parameter 33: type 'list' is not supported

    which silently dropped whole groups of contracts (16 of 45 in the field).
    They are stored as JSON now.
    """
    manager = fresh_manager(str(tmp_path / 'lists.sqlite3'))
    assert manager.save_symbol_info(pd.DataFrame({
        'instrument_id': ['SHFE.rb2610'],
        'instrument_name': ['螺纹钢2610'],
        'ins_class': ['FUTURE'],
        'exchange_id': ['SHFE'],
        'trading_time_day': [['09:00-10:15', '10:30-11:30', '13:30-15:00']],
        'trading_time_night': [['21:01-23:00']],
    })) is True

    row = manager.connection.execute(
        'SELECT trading_time_day, trading_time_night FROM symbol_info').fetchone()
    assert json.loads(row[0]) == ['09:00-10:15', '10:30-11:30', '13:30-15:00']
    assert json.loads(row[1]) == ['21:01-23:00']
    manager.close()
    database_manager.DatabaseManager._instance = None


def test_one_exotic_value_does_not_lose_the_rest_of_the_batch(tmp_path):
    """A single unbindable value must not take the other rows down with it."""

    class Exotic:
        def __str__(self):
            return 'exotic'

    manager = fresh_manager(str(tmp_path / 'exotic.sqlite3'))
    frame = pd.DataFrame({
        'instrument_id': ['A.1', 'A.2', 'A.3'],
        'instrument_name': ['one', 'two', 'three'],
        'ins_class': ['FUTURE'] * 3,
        'exchange_id': ['SHFE'] * 3,
        'trading_time_day': [['09:00-10:15'], Exotic(), {'a': [1, 2]}],
    })
    assert manager.save_symbol_info(frame) is True

    ids = [row[0] for row in manager.connection.execute(
        'SELECT instrument_id FROM symbol_info ORDER BY instrument_id').fetchall()]
    assert ids == ['A.1', 'A.2', 'A.3'], 'every row in the batch must survive'
    stored = dict(manager.connection.execute(
        'SELECT instrument_id, trading_time_day FROM symbol_info').fetchall())
    assert json.loads(stored['A.1']) == ['09:00-10:15']
    assert stored['A.2'] == 'exotic'
    assert json.loads(stored['A.3']) == {'a': [1, 2]}
    manager.close()
    database_manager.DatabaseManager._instance = None
