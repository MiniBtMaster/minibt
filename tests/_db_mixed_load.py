"""Child process: hammer the database with reads *and* writes at the same time.

Written when the store was DuckDB, whose connection could not be used concurrently:
the failure was a native abort (`_duckdb.pyd`, 0xc0000409) with no Python
traceback, so the host application simply disappeared.

It now guards the SQLite implementation, where the same load must stay clean and
must never take the process down. Run as a subprocess so a regression fails a test
instead of killing pytest:

    python tests/_db_mixed_load.py <db-path>
"""
import sys
import threading
import time

import pandas as pd

sys.path.insert(0, __import__('pathlib').Path(__file__).resolve().parents[1].as_posix())

from miniqt.app.common import database_manager as dbm       # noqa: E402

ROWS = 500
BATCH = 60
ROUNDS = 40


def frame(ids, value):
    return pd.DataFrame({
        'instrument_id': ids,
        'instrument_name': ids,
        'ins_class': ['CONT_MAIN'] * len(ids),
        'exchange_id': ['SHFE'] * len(ids),
        'price_tick': [float(value)] * len(ids),
    })


def main(db_path: str) -> int:
    manager_class = dbm.DatabaseManager
    manager_class._instance = None
    manager = manager_class(db_path)
    ids = [f'EX{i:05d}' for i in range(ROWS)]
    manager.save_symbol_info(frame(ids, 0.0))

    stop = threading.Event()
    errors = []

    def reader(name, call):
        while not stop.is_set():
            try:
                call()
            except Exception as error:              # noqa: BLE001
                errors.append(f'{name}: {type(error).__name__}: {error}')
                return

    readers = [
        threading.Thread(target=reader, args=('get_symbol_info',
                                              lambda: manager.get_symbol_info('CONT_MAIN'))),
        threading.Thread(target=reader, args=('get_search_table', manager.get_search_table)),
        threading.Thread(target=reader, args=('get_ins_class_map', manager.get_ins_class_map)),
        threading.Thread(target=reader, args=('has_data', manager.has_data)),
        threading.Thread(target=reader, args=('is_fresh_database', manager.is_fresh_database)),
    ]
    for thread in readers:
        thread.start()

    writers = []
    for index in range(3):
        def writer(offset=index):
            for round_no in range(ROUNDS):
                manager.save_symbol_info(frame(ids, offset + round_no))
                manager.delete_symbol_info(ins_class='CONT_MAIN', exchange_id='SHFE')
                manager.set_meta('contracts_refreshed_on', f'2026-02-{round_no + 1:02d}')
        thread = threading.Thread(target=writer)
        writers.append(thread)
        thread.start()

    for thread in writers:
        thread.join()
    time.sleep(0.2)
    stop.set()
    for thread in readers:
        thread.join()

    print(f'reader errors: {len(errors)}')
    for error in errors[:3]:
        print('  ', error)
    # the process surviving to here is the assertion
    print('MIXED_LOAD_OK', flush=True)
    manager.close()
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else ':memory:'))
