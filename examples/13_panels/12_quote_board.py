"""QuoteBoard：行情报价（类型 / 交易所分类 + 报价表 + 滚动条）。

这是 miniqt「行情报价」页的开源版组件 —— 把 `DataGrid` + `Ticker` 拼起来，并加上：

- **类型 chips**：期货 / 主连 / 指数 / 期权 / 股票 / 主力
- **交易所 chips**：中金所 / 上期所 / 大商所 / 郑商所 / 能源 / 广期所 / 港股 / 美股
- 顶部搜索（本地过滤）+ 行数 + 「刷新」（绕过缓存重拉）
- **加载中 / 暂无数据** 两种空表文案 —— 不会「永远在加载」✓
- 事件：单击 / 双击 / 右键 / 筛选变化 / 刷新

本例用合成数据模拟「按类型 + 交易所切分」，把回调打到控制台；
接真实行情只要把 `rows_for()` 换成 ``tq_api.query_quotes`` / futu 快照即可。

运行::

    python examples/13_panels/12_quote_board.py
    python examples/13_panels/12_quote_board.py --snapshot quote_board.png
    python examples/13_panels/12_quote_board.py --check      # 只校验数据/事件
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ★ 优先用**仓库里**的 pylightcharts（QuoteBoard 是 0.1.6 新增的插件；
#   已发布的 0.1.5 里没有 → 不加这行会 ImportError ✓）
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if os.path.isdir(os.path.join(_REPO, 'pylightcharts')):
    sys.path.insert(0, _REPO)

BINDING = os.environ.get('PYLIGHTCHARTS_QT') or 'PySide6'
os.environ['PYLIGHTCHARTS_QT'] = BINDING

from pylightcharts.qt import prepare_qt                      # noqa: E402

prepare_qt(BINDING)
QtCore = importlib.import_module(f'{BINDING}.QtCore')
QtWidgets = importlib.import_module(f'{BINDING}.QtWidgets')

from _sample_data import make_rows                          # noqa: E402
from pylightcharts import QtPanel                           # noqa: E402
from pylightcharts.panels import Column, QuoteBoard          # noqa: E402

#: 类型 chips（和 miniqt 一致 ✓）
TYPES = [
    ('FUT', '期货'), ('CONT', '主连'), ('INDEX', '指数'),
    ('OPTION', '期权'), ('STOCK', '股票'), ('MAIN', '主力'),
]

#: 每种类型的交易所 chips
EXCHANGES = {
    'FUT': [('CFFEX', '中金所'), ('SHFE', '上期所'), ('DCE', '大商所'),
            ('CZCE', '郑商所'), ('INE', '能源交易所(原油)'),
            ('GFEX', '广州期货交易所')],
    'CONT': [('CFFEX', '中金所'), ('SHFE', '上期所'), ('DCE', '大商所'),
             ('KQD', '外盘主连')],
    'INDEX': [('CFFEX', '中金所'), ('SHFE', '上期所')],
    'OPTION': [('SHFE', '上期所'), ('DCE', '大商所'), ('CZCE', '郑商所')],
    'STOCK': [('SSE', '上交所'), ('SZSE', '深交所'), ('HK', '港股'),
              ('US', '美股')],
    'MAIN': [('CFFEX', '中金所'), ('SHFE', '上期所'), ('DCE', '大商所')],
}

#: 期权表多两列（行权价 / 到期日）✓
OPTION_EXTRA = [
    Column('strike', '行权价', width=1.0, type='number', trim=True),
    Column('expiry', '到期日', width=1.1),
]

COLUMNS = [
    Column('symbol', '代码', width=1.7),
    Column('name', '名称', width=1.3),
    Column('last', '最新价', type='number', decimals=3, trim=True,
           color_by='sign'),
    Column('bid_price1', '买一价', type='number', decimals=3, trim=True),
    Column('bid_volume1', '买一量', type='number', decimals=0),
    Column('ask_price1', '卖一价', type='number', decimals=3, trim=True),
    Column('ask_volume1', '卖一量', type='number', decimals=0),
    Column('chg', '涨跌', type='change', decimals=3),
    Column('chg_pct', '涨跌幅', type='percent', decimals=2),
    Column('volume', '成交量', type='number', decimals=0, compact=True),
    Column('open', '今开盘', type='number', decimals=3, trim=True),
    Column('high', '最高价', type='number', decimals=3, trim=True),
    Column('low', '最低价', type='number', decimals=3, trim=True),
    Column('pre_close', '昨收盘', type='number', decimals=3, trim=True),
    Column('open_interest', '持仓量', type='number', decimals=0, compact=True),
    Column('spark', '走势', width=1.4, type='spark'),
]

#: 合成数据缓存（按 ``类型:交易所`` 分，模拟后端分类加载 ✓）
_CACHE: dict = {}


def rows_for(kind: str, exchange: str) -> list:
    """某个「类型 + 交易所」的合约（合成数据；真实场景换成行情接口 ✓）"""
    key = (kind, exchange)
    if key in _CACHE:
        return _CACHE[key]
    rows = make_rows(120)
    for index, row in enumerate(rows):
        row['symbol'] = f'{exchange}.{row["symbol"].split(".")[-1]}'
        row['exchange'] = exchange
        if kind == 'STOCK':
            row['chg_pct'] = round(row['chg_pct'] / 10, 2)   # 股票波动小一点
        if kind == 'OPTION':
            row['strike'] = 3000 + index * 50
            row['expiry'] = f'2026-{12 - index % 6:02d}-15'
    _CACHE[key] = rows
    return rows


def build(panel: QtPanel) -> QuoteBoard:
    board = QuoteBoard(
        panel.win,
        columns=COLUMNS,
        types=TYPES,
        exchanges=EXCHANGES['FUT'],
        type='FUT',
        exchange='CFFEX',
        show_ticker=True,
        row_height=28,
        font_size=12,
    )
    # 首屏：先「加载中」，再推数据（真实场景就是网络请求的 1~2 秒 ✓）
    board.set_loading(True, '正在加载 CFFEX 合约…')

    def load(kind: str, exchange: str) -> None:
        rows = rows_for(kind or 'FUT', exchange or 'CFFEX')
        board.set_rows(rows)
        board.set_count(f'{len(rows)} 行')
        board.set_ticker(rows[:12])
        board.set_column_visibility('strike', kind == 'OPTION')
        board.set_column_visibility('expiry', kind == 'OPTION')

    def on_filter(kind: str, exchange: str, text: str) -> None:
        print(f'[example] 筛选 类型={kind} 交易所={exchange} 搜索={text!r}')
        board.set_exchanges(EXCHANGES.get(kind, []),
                            exchange or (EXCHANGES.get(kind) or [('', '')])[0][0])
        board.set_loading(True, f'正在加载 {kind} / {exchange} 合约…')
        # 真实场景：这里去调行情接口，拿到后再 set_rows ✓
        load(kind, exchange)

    board.on_filter(on_filter)
    board.on_click(
        lambda symbol, x, y: print(f'[example] 单击 {symbol} @ ({x},{y})'
                                   '（可弹「合约概览」气泡）'))
    board.on_double_click(lambda symbol: print(f'[example] 双击 {symbol}（开图）'))
    board.on_context(lambda symbol: print(f'[example] 右键 {symbol}（周期菜单）'))
    board.on_refresh(lambda: print('[example] 刷新（绕过缓存重拉）'))
    load('FUT', 'CFFEX')
    return board


def main() -> None:
    parser = argparse.ArgumentParser(description='QuoteBoard 行情报价示例')
    parser.add_argument('--snapshot', metavar='PNG', default=None)
    parser.add_argument('--check', action='store_true',
                        help='只校验数据（不开窗口）')
    args = parser.parse_args()

    if args.check:
        for kind in ('FUT', 'STOCK', 'OPTION'):
            exchange = (EXCHANGES[kind] or [('', '')])[0][0]
            rows = rows_for(kind, exchange)
            assert rows and {'symbol', 'name', 'last'} <= set(rows[0])
            print(f'  {kind:6} {exchange:6} → {len(rows)} 行 '
                  f'（首行 {rows[0]["symbol"]} {rows[0]["name"]}）')
        print('[example] QuoteBoard 数据检查通过')
        return

    app = QtWidgets.QApplication(sys.argv)
    panel = QtPanel()
    build(panel)
    view = panel.get_webview()

    if args.snapshot:
        view.resize(1280, 760)
        panel.win.run_script(
            "document.getElementById('container').style.height='760px';")

        def shoot() -> None:
            view.grab().save(args.snapshot)
            print(f'[example] 已保存截图: {args.snapshot}')
            app.quit()

        QtCore.QTimer.singleShot(3500, shoot)
    else:
        view.show()
    app.exec()


if __name__ == '__main__':
    main()
