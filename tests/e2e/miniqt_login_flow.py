"""Drive the real MainWindow through the post-login sequence, with a stub tq_api.

Logging in needs real 天勤 credentials, so this injects a null-object TqApi and
runs the whole chain the login success triggers:

    update_cont_quotes -> MarketQuoteInterface.on_cont_quotes_updated
      -> update_exchange_segments -> create_tq_api_qtimer (wait_update)
      -> the daily contract refresh (QTimer chain, DuckDB writes)
      -> __update_table -> _get_from_tq_api

It is how the post-login crash was tracked down, and it keeps that path testable
without an account. A crash here is a hard DuckDB abort, so it also serves as a
smoke test for the serialised database access.

    python tests/e2e/miniqt_login_flow.py
"""
import faulthandler
import os
import sys
import tempfile
import time
import traceback

TMP = tempfile.gettempdir()
LOG_PATH = os.path.join(TMP, 'probe2.log')
CRASH_PATH = os.path.join(TMP, 'probe2_crash.log')
open(LOG_PATH, 'w').close()
CRASH = open(CRASH_PATH, 'w', buffering=1)
faulthandler.enable(CRASH)


def log(*args):
    text = ' '.join(str(a) for a in args)
    with open(LOG_PATH, 'a', encoding='utf-8') as handle:
        handle.write(text + '\n')
    try:
        os.write(2, (text + '\n').encode('utf-8', 'replace'))
    except OSError:
        pass


def excepthook(kind, value, tb):
    log('EXCEPTION:', kind.__name__, value)
    traceback.print_exception(kind, value, tb, file=CRASH)


sys.excepthook = excepthook

ROOT = r'C:\Users\Lenovo\Desktop\pylightcharts'
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--ignore-certificate-errors'
sys.path.insert(0, ROOT)
os.chdir(os.path.join(ROOT, 'miniqt'))

from pylightcharts.compat import install_alias            # noqa: E402
install_alias()

from PyQt6.QtWebEngineWidgets import QWebEngineView        # noqa: E402,F401
from PyQt6.QtCore import QTimer                            # noqa: E402
from PyQt6.QtWidgets import QApplication                   # noqa: E402
app = QApplication(sys.argv)

import pandas as pd                                        # noqa: E402
from miniqt.app.common.config import cfg                   # noqa: E402,F401
from miniqt.app.common import database_manager as dbm       # noqa: E402
# fresh scratch database every run: otherwise 'contracts_refreshed_on' is
# already today and the daily refresh is skipped, hiding the code under test
#: point this at a database to run the flow against it (e.g. a corrupt file), which
#: is how the post-login crash was reproduced: `MINIQT_FLOW_DB=<path>`
_DB_PATH = os.environ.get('MINIQT_FLOW_DB') or os.path.join(
    tempfile.gettempdir(), 'miniqt_flow_scratch.sqlite3')
for _suffix in ('', '.wal'):
    if os.path.exists(_DB_PATH + _suffix):
        os.remove(_DB_PATH + _suffix)
dbm._db_manager = dbm.DatabaseManager(_DB_PATH)

from miniqt.app.view.main_window import MainWindow         # noqa: E402

EXCHANGES = {
    '期货': {'中金所': ['CFFEX.IF2609'], '上期所': ['SHFE.rb2610', 'SHFE.cu2608'],
             '大商所': ['DCE.m2609'], '郑商所': ['CZCE.TA609'],
             '能源交易所(原油)': ['INE.sc2608'], '广州期货交易所': ['GFEX.si2609'],
             '上交所': [], '深交所': [], '外盘主连': []},
    '主连': {'中金所': ['CFFEX.IF2609'], '上期所': [], '大商所': [], '郑商所': [],
             '能源交易所(原油)': [], '广州期货交易所': [], '上交所': [], '深交所': [],
             '外盘主连': []},
    '指数': {'中金所': [], '上期所': [], '大商所': [], '郑商所': [],
             '能源交易所(原油)': [], '广州期货交易所': [], '上交所': [], '深交所': [],
             '外盘主连': []},
    '股票': {'中金所': [], '上期所': [], '大商所': [], '郑商所': [],
             '能源交易所(原油)': [], '广州期货交易所': [], '上交所': ['SSE.600000'],
             '深交所': [], '外盘主连': []},
    '主力': {'中金所': ['CFFEX.IF2609'], '上期所': ['SHFE.rb2610'],
             '大商所': ['DCE.m2609'], '郑商所': ['CZCE.TA609'],
             '能源交易所(原油)': ['INE.sc2608'], '广州期货交易所': ['GFEX.si2609'],
             '上交所': [], '深交所': [], '外盘主连': []},
}

ALL_SYMBOLS = [s for group in EXCHANGES.values() for lst in group.values() for s in lst]


class StubTqApi:
    """Simulates the CFFEX/SHFE case: query_cont_quotes returns nothing, so the
    main contracts must come from the 主连 (KQ.m@) underlying instead."""

    MAIN_BY_EXCHANGE = {'CFFEX': ['CFFEX.IF2609'], 'SHFE': ['SHFE.rb2610']}

    def query_cont_quotes(self, exchange_id=None):
        # 天勤在中金所/上期所上有时返回空列表（主连的 underlying 边缺失）
        return []

    def query_quotes(self, ins_class=None, exchange_id=None, **kwargs):
        if ins_class == 'CONT':
            return [f'KQ.m@{symbol}' for symbol in self.MAIN_BY_EXCHANGE.get(exchange_id, [])]
        return []

    def __getattr__(self, name):
        # the real TqApi has many more methods (wait_update, is_changing, ...);
        # behave like a null object so the whole post-login chain can run
        def _noop(*args, **kwargs):
            log(f'  [stub] tq_api.{name}() -> None')
            return None
        return _noop

    def query_symbol_info(self, symbols=None):
        if symbols is None:
            symbols = ALL_SYMBOLS
        symbols = list(symbols)
        underlying = []
        for symbol in symbols:
            if symbol.startswith('KQ.m@'):
                target = symbol.split('@', 1)[1]
                product = target.split('.')[1][:2] if '.' in target else 'xx'
                underlying.append(f'{target.split(".")[0]}.{product}2610')
            else:
                underlying.append(None)
        return pd.DataFrame({
            'instrument_id': symbols,
            'instrument_name': [f'name-{s}' for s in symbols],
            'ins_class': ['CONT' if s.startswith('KQ.m@') else 'FUTURE' for s in symbols],
            'exchange_id': [s.split('.')[-1] if False else s.split('.')[0].replace('KQ.m@', '')
                            for s in symbols],
            'underlying_symbol': underlying,
            'price_tick': [1.0] * len(symbols),
            # 天勤把交易时段给成字符串列表：SQLite 只认标量，这类值曾让整批写入
            # 失败（Error binding parameter 33: type 'list' is not supported）
            'trading_time_day': [['09:00-10:15', '13:30-15:00']] * len(symbols),
            'trading_time_night': [['21:01-23:00']] * len(symbols),
        })

def main():
    log('--- constructing MainWindow ---')
    window = MainWindow()
    log('MainWindow ok; tq_object =', type(window.tq_object).__name__)
    window.show()

    # simulate what a successful futures login does
    window.tq_api = StubTqApi()
    window.login_status.update({'futures': True})

    def fake_update_cont_quotes():
        log('  [stub] update_cont_quotes -> filling exchanges and emitting')
        window.tq_object.exchanges = EXCHANGES
        window.tq_object.cont_quotes_updated.emit()

    window.tq_object.update_cont_quotes = fake_update_cont_quotes

    log('--- update_cont_quotes() (LoginWindow calls this after login) ---')
    window.update_cont_quotes()

    deadline = time.time() + 25
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)

    mqi = window.marketQuoteInterface
    table = mqi.tableWidget
    log('--- table ---')
    log('  columns:', [table.horizontalHeaderItem(c).text()
                        for c in range(min(table.columnCount(), 8))])
    log('  rows   :', table.rowCount())
    for row in range(min(table.rowCount(), 2)):
        log(f'  row{row}  :', [table.item(row, c).text() if table.item(row, c) else None
                               for c in range(min(table.columnCount(), 5))])
    log('  (row0, col1) symbol =', table.item(0, 1).text() if table.item(0, 1) else None)
    # the main-contract group must have been rewritten from the 主连 underlying
    db = dbm._db_manager
    for exchange in ('CFFEX', 'SHFE'):
        rows = db.get_symbol_info('CONT_MAIN', exchange)
        ids = [] if rows is None else sorted(rows['instrument_id'].tolist())
        log(f'CONT_MAIN/{exchange:5}:', ids)

    log('refresh state      :', mqi._refresh_state)
    log('contracts refreshed:', mqi.contracts_refreshed_on())
    log('segments built     :', mqi.segmentedWidget.currentRouteKey())
    log('is_update_segments :', mqi.is_update_exchange_segments)
    saved = db.connection.execute('SELECT COUNT(*) FROM symbol_info').fetchone()[0]
    log('contract rows saved:', saved)
    log('database disabled  :', getattr(db, '_disabled', 'n/a'))
    log('connection alive   :', getattr(db, 'connection', None) is not None)
    # surviving this far *is* the assertion: a poisoned DuckDB used to take the
    # whole process down in native code while the 45 refresh tasks ran
    log('RESULT_OK')


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        log('UNCAUGHT:')
        traceback.print_exc(file=CRASH)
        log(traceback.format_exc())
