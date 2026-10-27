"""插件总览（画廊）：所有 pylightcharts 插件按 TradingView 目录顺序排成网格。

移植自 miniqt 的「插件总览」页
（``miniqt/app/view/panels_gallery_interface.py``）——去掉 qfluentwidgets/ScrollArea，
改成独立 Qt 窗口：上面一张真实 ``QtChart``（Advanced Chart），下面一个 ``QtPanel``
用 CSS 网格铺开其余插件，整页可滚动。

运行::

    python examples/13_panels/10_gallery.py
    python examples/13_panels/10_gallery.py --snapshot gallery.png
    PYLIGHTCHARTS_QT=PyQt6 python examples/13_panels/10_gallery.py
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BINDING = os.environ.get('PYLIGHTCHARTS_QT') or 'PySide6'
os.environ['PYLIGHTCHARTS_QT'] = BINDING

from pylightcharts.qt import prepare_qt                      # noqa: E402

prepare_qt(BINDING)
QtCore = importlib.import_module(f'{BINDING}.QtCore')
QtWidgets = importlib.import_module(f'{BINDING}.QtWidgets')

import numpy as np                                           # noqa: E402
import pandas as pd                                          # noqa: E402

from _sample_data import group_by_exchange, make_items, make_rows  # noqa: E402
from pylightcharts import QtPanel, QtChart                   # noqa: E402
from pylightcharts.panels import (BrokerRating, BrokerReviews,  # noqa: E402
                                  Column, CompanyProfile, CryptoHeatmap,
                                  DataGrid, EconomicCalendar, EtfHeatmap,
                                  FilterBar, ForexHeatmap, FundamentalData,
                                  Heatmap, MarketData, MiniChart, NewsFeed,
                                  Screener, SeasonalChart, SingleTicker,
                                  SymbolInfo, SymbolOverview,
                                  TechnicalAnalysis, TextBlock, TickerTape,
                                  TickerTag, Tickers, TopStories, ta_summary)

# --------------------------------------------------------------------- 模拟数据
_PRODUCTS = ['聚乙烯', '聚丙烯', 'PVC', '螺纹钢', '橡胶', '沪铜', '沪铝', '沪锌',
             '沪镍', '沪金', '沪银', '铁矿石', '焦炭', '焦煤', '豆粕', '白糖']

MARKET_COLUMNS = [
    Column('symbol', '代码', width=1.4), Column('name', '名称', width=1.1),
    Column('last', '最新', type='number', color_by='sign'),
    Column('chg', '涨跌', type='change'),
    Column('chg_pct', '涨跌幅', type='percent'),
    Column('volume', '成交量', type='number', compact=True),
    Column('open_interest', '持仓量', type='number', compact=True),
    Column('spark', '走势', type='spark', width=1.4),
]
WORLD_COLUMNS = [
    Column('symbol', '代码', width=1.2), Column('name', '名称', width=1.6),
    Column('last', '最新', type='number', color_by='sign'),
    Column('chg', '涨跌', type='change'),
    Column('chg_pct', '涨跌幅', type='percent'),
]

#: (标题, 构建方法名) —— 顺序即 TradingView 目录顺序（Advanced Chart 在最上面）
SPECS = [
    ('2 · Symbol Overview', 'p_symbol_overview'),
    ('3 · Mini Chart', 'p_mini_chart'),
    ('4 · Seasonal Chart', 'p_seasonal'),
    ('5 · Market Summary', 'p_market_summary'),
    ('6 · Market Overview', 'p_market_overview'),
    ('7 · Market Data', 'p_market_data'),
    ('8 · World Market Summary', 'p_world_summary'),
    ('9 · Ticker Tape', 'p_ticker_tape'),
    ('10 · Ticker Tag', 'p_ticker_tag'),
    ('11 · Single Ticker', 'p_single_ticker'),
    ('12 · Tickers', 'p_tickers'),
    ('13 · Stock Heatmap', 'p_stock_heatmap'),
    ('14 · Crypto Coins Heatmap', 'p_crypto_heatmap'),
    ('15 · Forex Table', 'p_forex_heatmap'),
    ('16 · ETF Heatmap', 'p_etf_heatmap'),
    ('17 · Screener', 'p_screener'),
    ('18 · Cryptocurrency Market', 'p_crypto_market'),
    ('19 · Symbol Info', 'p_symbol_info'),
    ('20 · Technical Analysis', 'p_technical'),
    ('21 · Fundamental Data', 'p_fundamental'),
    ('22 · Company Profile', 'p_company_profile'),
    ('23 · Top Stories', 'p_top_stories'),
    ('24 · Economic Calendar', 'p_calendar'),
    ('25 · Economic Map', 'p_economic_map'),
    ('26 · Broker Rating', 'p_broker_rating'),
    ('27 · Broker Reviews', 'p_broker_reviews'),
]


def _world_rows(seed: int = 29) -> list:
    rng = random.Random(seed)
    names = [('US500', '标普500'), ('US100', '纳指100'), ('DE40', '德国DAX'),
             ('UK100', '富时100'), ('JP225', '日经225'), ('HK50', '恒生指数'),
             ('CN50', '富时A50'), ('FR40', '法国CAC40')]
    rows = []
    for symbol, name in names:
        last = 5000 + rng.random() * 20000
        change = (rng.random() - 0.5) * 300
        rows.append({'symbol': symbol, 'name': name, 'last': round(last, 1),
                     'chg': round(change, 1),
                     'chg_pct': round(change / last * 100, 2)})
    return rows


def _heat_items(count: int, names: list, seed: int = 7, shock: float = 5.0) -> list:
    rng = random.Random(seed)
    return [{'symbol': names[i % len(names)],
             'value': round(1 + rng.random() * 9, 2),
             'chg_pct': round((rng.random() - 0.5) * shock * 2, 2)}
            for i in range(count)]


def _crypto() -> list:
    return _heat_items(24, ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE',
                            'AVAX'], seed=11, shock=8)


def _forex() -> list:
    return _heat_items(12, ['EURUSD', 'USDJPY', 'GBPUSD', 'AUDUSD', 'USDCNH',
                            'USDCHF'], seed=13, shock=2)


def _etf() -> list:
    return _heat_items(16, ['SPY', 'QQQ', 'IWM', 'DIA', 'VTI', 'GLD', 'SLV',
                            'TLT'], seed=17, shock=4)


def _news() -> list:
    return [
        {'title': '央行维持利率不变，符合市场预期', 'source': 'Reuters',
         'time': '10:24', 'summary': '政策委员会一致决定维持利率不变。'},
        {'title': '某品种库存降至年内低位', 'source': '文华财经', 'time': '09:50'},
        {'title': '海外需求回暖，出口数据超预期', 'source': 'Bloomberg',
         'time': '08:31'},
    ]


def _calendar() -> list:
    return [
        {'time': '20:30', 'country': 'US', 'event': 'CPI 月率', 'importance': '高',
         'actual': '0.3%', 'forecast': '0.3%', 'previous': '0.4%'},
        {'time': '09:30', 'country': 'CN', 'event': '官方制造业 PMI',
         'importance': '高', 'actual': '50.2', 'forecast': '50.0',
         'previous': '49.8'},
        {'time': '14:00', 'country': 'DE', 'event': 'IFO 商业景气',
         'importance': '低', 'actual': '—', 'forecast': '87.5',
         'previous': '87.0'},
    ]


def _fundamentals() -> list:
    return [
        {'name': '市盈率(TTM)', 'value': 28.4, 'yoy': 0.12, 'period': '2024Q4'},
        {'name': '市净率', 'value': 6.1, 'yoy': -0.03, 'period': '2024Q4'},
        {'name': 'ROE', 'value': 0.36, 'yoy': 0.05, 'period': '2024Q4'},
    ]


def _ratings() -> list:
    return [
        {'broker': '高盛', 'rating': '买入', 'target': 210, 'upside': 0.10,
         'date': '2025-01-12'},
        {'broker': '摩根士丹利', 'rating': '增持', 'target': 205, 'upside': 0.07,
         'date': '2025-01-10'},
    ]


def _reviews() -> list:
    return [
        {'broker': '高盛', 'review': '服务稳定，研报质量高', 'score': 4.5,
         'date': '2025-01-05'},
        {'broker': '美银', 'review': '费率略高', 'score': 3.8, 'date': '2024-12-28'},
    ]


def _ohlcv(rows: int = 400, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.6)
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': close + rng.standard_normal(rows) * 0.3,
        'high': close + np.abs(rng.standard_normal(rows)) * 0.8,
        'low': close - np.abs(rng.standard_normal(rows)) * 0.8,
        'close': close,
        'volume': rng.integers(1_000, 20_000, rows)})


def _seasonal_frame(years: int = 6, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range('2018-01-01', periods=365 * years, freq='D')
    steps = np.arange(len(index))
    seasonal = 0.05 * np.sin(2 * np.pi * (steps / 365.25) - 0.6)
    close = 100 * np.exp(np.cumsum(rng.standard_normal(len(index)) * 0.008)
                         + seasonal)
    return pd.DataFrame({'time': index, 'close': close})


class Gallery(QtWidgets.QWidget):
    """Advanced Chart（QtChart）+ 其余插件（一个 QtPanel 的 DOM 网格）。"""

    CELL_HEIGHT = 340

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('pylightcharts · 插件总览（画廊）')
        self._rows = make_rows(80)
        self._ohlcv = _ohlcv()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.chart = QtChart(self)                       # ① Advanced Chart
        self.chart.get_webview().setFixedHeight(380)
        layout.addWidget(self.chart.get_webview())

        self.panel = QtPanel(self)                       # ② 其余插件
        layout.addWidget(self.panel.get_webview(), 1)

        self._build_gallery()
        QtCore.QTimer.singleShot(900, self._set_chart_data)

    # ---- Advanced Chart -------------------------------------------------
    def _set_chart_data(self):
        try:
            self.chart.layout(background_color='#0b0e14',
                              text_color='#d1d4dc')
            self.chart.candle_style(up_color='#26a69a', down_color='#ef5350',
                                    border_visible=False)
            self.chart.grid(color='rgba(42,46,57,0.6)')
            self.chart.precision(2)
            self.chart.legend(True, text='Advanced Chart')
            self.chart.set(self._ohlcv)
        except Exception as error:                                # noqa: BLE001
            print(f'[gallery] 图表数据失败: {error!r}')

    # ---- DOM 画廊 -------------------------------------------------------
    def _build_gallery(self):
        window = self.panel.win
        titles = [title for title, _ in SPECS]
        window.run_script(f"""
        (function () {{
            var html = document.documentElement, body = document.body;
            html.style.height = 'auto'; html.style.overflow = 'auto';
            body.style.height = 'auto'; body.style.overflow = 'auto';
            var c = document.getElementById('container');
            c.style.position = 'relative';
            c.style.left = c.style.top = c.style.right = c.style.bottom = '';
            c.style.height = 'auto';
            c.style.overflow = 'visible';
            c.style.background = '#0b0e14';
            c.style.padding = '14px';
            c.style.boxSizing = 'border-box';
            var grid = document.createElement('div');
            grid.style.cssText = 'display:grid;'
                + 'grid-template-columns:repeat(auto-fill,minmax(430px,1fr));'
                + 'gap:14px;grid-auto-rows:{self.CELL_HEIGHT}px';
            var titles = {json.dumps(titles)};
            titles.forEach(function (title, i) {{
                var item = document.createElement('div');
                item.style.cssText = 'display:flex;flex-direction:column;'
                    + 'min-width:0;min-height:0;background:#131722;'
                    + 'border:1px solid #2a2e39;border-radius:6px;overflow:hidden';
                var head = document.createElement('div');
                head.style.cssText = 'flex:0 0 auto;padding:6px 10px;'
                    + 'font:600 12px -apple-system,"Microsoft YaHei",sans-serif;'
                    + 'color:#9aa0aa;border-bottom:1px solid #2a2e39;'
                    + 'background:#1e222d';
                head.textContent = title;
                var cell = document.createElement('div');
                cell.id = '__g' + i;
                cell.style.cssText = 'flex:1 1 auto;min-height:0;position:relative';
                item.appendChild(head);
                item.appendChild(cell);
                grid.appendChild(item);
            }});
            c.appendChild(grid);
        }})();
        """)
        for index, (_title, method) in enumerate(SPECS):
            cell = f"document.getElementById('__g{index}')"
            try:
                getattr(self, method)(window, cell)
            except Exception as error:                            # noqa: BLE001
                print(f'[gallery] {method} 构建失败: {error!r}')

    # ---- 各插件构建 -----------------------------------------------------
    def p_symbol_overview(self, window, c):
        row = self._rows[0]
        SymbolOverview(window, {**row, 'exchange': row['exchange']},
                       decimals=0, container=c)

    def p_mini_chart(self, window, c):
        MiniChart(window, self._rows[1]['spark'], width=320, height=120,
                  container=c)

    def p_seasonal(self, window, c):
        SeasonalChart(window, color_scheme='cn', decimals=2,
                      container=c).from_frame(_seasonal_frame())

    def p_market_summary(self, window, c):
        groups = {'指数': _world_rows(31), '期货': self._rows[:24],
                  '外汇': [{'symbol': it['symbol'], 'last': round(1 + it['value'], 4),
                            'chg_pct': it['chg_pct']} for it in _forex()],
                  '加密': [{'symbol': it['symbol'],
                            'last': round(100 + it['value'] * 100),
                            'chg_pct': it['chg_pct']} for it in _crypto()[:12]]}
        MarketData(window, groups=groups, columns=MARKET_COLUMNS, container=c)

    def p_market_overview(self, window, c):
        MarketData(window, groups=group_by_exchange(self._rows),
                   columns=MARKET_COLUMNS, container=c)

    def p_market_data(self, window, c):
        DataGrid(window, MARKET_COLUMNS, container=c).set_rows(self._rows)

    def p_world_summary(self, window, c):
        DataGrid(window, WORLD_COLUMNS, container=c).set_rows(_world_rows())

    def p_ticker_tape(self, window, c):
        TickerTape(window, make_items(self._rows[:20]), speed=70, container=c)

    def p_ticker_tag(self, window, c):
        TickerTag(window, make_items(self._rows[:1]), show_name=True,
                  decimals=0, container=c)

    def p_single_ticker(self, window, c):
        SingleTicker(window, make_items(self._rows[:1]), show_name=True,
                     decimals=0, container=c)

    def p_tickers(self, window, c):
        Tickers(window, make_items(self._rows[:10]), show_name=True,
                decimals=0, container=c)

    def p_stock_heatmap(self, window, c):
        Heatmap(window, _heat_items(30, _PRODUCTS, seed=41), color_scheme='cn',
                container=c)

    def p_crypto_heatmap(self, window, c):
        CryptoHeatmap(window, _crypto(), color_scheme='cn', container=c)

    def p_forex_heatmap(self, window, c):
        ForexHeatmap(window, _forex(), color_scheme='cn', max_shock=2, container=c)

    def p_etf_heatmap(self, window, c):
        EtfHeatmap(window, _etf(), color_scheme='cn', container=c)

    def p_screener(self, window, c):
        window.run_script(
            f"var s=document.createElement('div');s.className='pylc-stack';"
            f"{c}.appendChild(s);window.__galScreen=s;")
        screener = Screener(window, self._rows, columns=MARKET_COLUMNS,
                            container='window.__galScreen')
        screener.save_preset('up', [('chg_pct', '>', 2)])
        bar = FilterBar(window, columns=['chg_pct', 'volume', 'open_interest'],
                        editable=True, container='window.__galScreen')
        screener.bind_filter_bar(bar)

    def p_crypto_market(self, window, c):
        rows = [{'symbol': it['symbol'], 'name': it['symbol'],
                 'last': round(100 + it['value'] * 1000),
                 'chg': round(it['chg_pct']), 'chg_pct': it['chg_pct'],
                 'volume': int(it['value'] * 1e6),
                 'open_interest': int(it['value'] * 5e5)} for it in _crypto()]
        DataGrid(window, MARKET_COLUMNS, container=c).set_rows(rows)

    def p_symbol_info(self, window, c):
        SymbolInfo(window, self._rows[2], decimals=0, container=c)

    def p_technical(self, window, c):
        TechnicalAnalysis(window, ta_summary(self._ohlcv), container=c)

    def p_fundamental(self, window, c):
        FundamentalData(window, _fundamentals(), container=c)

    def p_company_profile(self, window, c):
        CompanyProfile(window, {'name': '苹果公司', 'symbol': 'AAPL',
                                'exchange': 'NASDAQ', 'last': 190.2,
                                'chg': 1.5, 'chg_pct': 0.79},
                       html='<p>苹果公司设计、制造并销售智能设备并提供相关服务。</p>',
                       container=c)

    def p_top_stories(self, window, c):
        TopStories(window, _news(), container=c)

    def p_calendar(self, window, c):
        EconomicCalendar(window, _calendar(), container=c)

    def p_economic_map(self, window, c):
        TextBlock(window, text=('25 · Economic Map（占位）\n\n'
                                '世界地图着色暂未实现（按计划不做）。'), container=c)

    def p_broker_rating(self, window, c):
        BrokerRating(window, _ratings(), container=c)

    def p_broker_reviews(self, window, c):
        BrokerReviews(window, _reviews(), container=c)


def main() -> None:
    parser = argparse.ArgumentParser(description='插件总览（画廊）示例')
    parser.add_argument('--snapshot', metavar='PNG', default=None)
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    gallery = Gallery()
    if args.snapshot:
        gallery.resize(1400, 1600)

        def shoot() -> None:
            gallery.grab().save(args.snapshot)
            print(f'[example] 已保存截图: {args.snapshot}')
            app.quit()

        QtCore.QTimer.singleShot(4500, shoot)
    else:
        gallery.resize(1400, 900)
        gallery.show()
    app.exec()


if __name__ == '__main__':
    main()
