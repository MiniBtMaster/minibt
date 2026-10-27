"""Contract symbol lookup must not depend on a hard-coded column index.

`MarketQuoteInterface.on_cell_double_clicked` used to read column 1 as the symbol.
The column set changes with the data source, and when it did the lookup returned
the *type* column instead, so double-clicking tried to open a chart for

    contains non-existent instrument: FUTURE

The lookup now resolves the column by header text and validates the result. These
tests pin that; they only need `QTableWidget`, not the whole window.

    pytest tests/test_miniqt_columns.py
"""
from __future__ import annotations

import os
import types

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

pytest.importorskip('PyQt6')
market_quote = pytest.importorskip('miniqt.app.view.market_quote_interface')

from PyQt6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem   # noqa: E402


@pytest.fixture(scope='module')
def app():
    yield QApplication.instance() or QApplication([])


def make_table(columns, *rows) -> QTableWidget:
    table = QTableWidget()
    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels(list(columns))
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
    return table


def holder_for(table):
    """Bind the lookup methods to a stand-in whose only attribute is the table."""
    holder = types.SimpleNamespace(
        tableWidget=table,
        COLUMN_ALIASES=market_quote.MarketQuoteInterface.COLUMN_ALIASES)
    holder._column_index = market_quote.MarketQuoteInterface._column_index.__get__(holder)
    holder._cell_text = market_quote.MarketQuoteInterface._cell_text.__get__(holder)
    holder._symbol_at = market_quote.MarketQuoteInterface._symbol_at.__get__(holder)
    return holder


def test_symbol_is_read_from_the_code_column(app):
    table = make_table(['序号', '代码', '名称', '类型', '交易所'],
                       ['1', 'SHFE.rb2610', '螺纹钢', 'FUTURE', 'SHFE'])
    holder = holder_for(table)
    assert holder._symbol_at(0) == 'SHFE.rb2610'
    assert holder._cell_text(0, market_quote.MarketQuoteInterface.COLUMN_ALIASES['type']) == 'FUTURE'


def test_symbol_survives_a_different_column_order(app):
    """The regression: with the symbol no longer in column 1, the old code returned
    the neighbouring value (the name, or the type) and opened a chart for it."""
    table = make_table(['序号', '名称', '代码', '类型'],
                       ['1', '螺纹钢', 'SHFE.rb2610', 'FUTURE'])
    assert holder_for(table)._symbol_at(0) == 'SHFE.rb2610'


def test_a_type_in_the_code_column_is_rejected(app):
    """Whatever put it there, 'FUTURE' is not an instrument: refuse instead of
    asking 天勤 for a chart of it."""
    table = make_table(['序号', '代码', '名称', '类型'],
                       ['1', 'FUTURE', '期货', 'FUTURE'])
    assert holder_for(table)._symbol_at(0) is None


def test_missing_code_column_is_not_an_error(app):
    table = make_table(['序号', '名称', '类型'], ['1', '螺纹钢', 'FUTURE'])
    holder = holder_for(table)
    assert holder._symbol_at(0) is None
    assert holder._cell_text(0, ('类型', 'type')) == 'FUTURE'
