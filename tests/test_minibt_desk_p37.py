"""P37：天勤 Entity 持仓表 / 布局分隔条按真实比例 / 指标设置齿轮 ✓"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


# ------------------------------------------------------- ① 天勤 Entity → 表格
class _Entity:
    """`tqsdk.objs.Entity` 的形状：**不是 dict 子类**，迭代拿到的是 key ✓"""

    def __init__(self, data):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def to_dict(self):
        return dict(self._data)


class _Pos:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _api():
    class Api:
        _account = _Pos(broker_id='', account_id='')

        def get_account(self, **kwargs):
            return _Pos(pre_balance=879783.61, balance=879783.61,
                        position_profit=157.5, close_profit=-157.5,
                        float_profit=157.5, commission=41.67,
                        margin=91667.40, frozen_margin=0.0,
                        frozen_commission=0.0, available=788116.54,
                        risk_ratio=0.1042)

        def get_position(self, **kwargs):
            return _Entity({
                'SHFE.ag2612': _Pos(instrument_id='SHFE.ag2612',
                                    pos_long=1, volume_long=1,
                                    pos_long_today=1,
                                    open_price_long=13862.98,
                                    position_price_long=13974.0,
                                    float_profit_long=157.5,
                                    market_value_long=139740.0,
                                    margin_long=91667.4),
            })

        def get_order(self, **kwargs):
            return _Entity({'o1': _Pos(instrument_id='SHFE.ag2612',
                                       status='ALIVE', direction='BUY',
                                       offset='OPEN', volume_orign=1,
                                       volume_left=1, limit_price=13974.0)})

        def get_trade(self, **kwargs):
            return _Entity({'t1': _Pos(instrument_id='SHFE.ag2612',
                                       direction='BUY', offset='OPEN',
                                       price=13862.98, volume=1,
                                       commission=41.67,
                                       trade_date_time='2026-10-19 '
                                                       '10:02:11.123')})
    return Api()


class _Desk:
    def feed_of(self, symbol=''):
        return type('F', (), {'kind': 'futures', 'api': _api()})()

    def decimals_of(self, symbol):
        return 1


def test_tqsdk_entity_is_expanded_to_rows():
    """金额卡片有数、持仓表却永远空 ✗ → 现在按字符串 key 展开 ✓"""
    from minibt.desk.accounts import record_rows

    rows = record_rows(_Entity({'a': _Pos(instrument_id='a'),
                                'b': _Pos(instrument_id='b')}))
    assert [row.instrument_id for row in rows] == ['a', 'b']


def test_position_table_shows_long_and_short():
    from minibt.desk.accounts import AccountView

    view = AccountView(_Desk())
    payload = view.payload(100, 'SHFE.ag2612')
    rows = payload['tables']['positions']['rows']
    assert len(rows) == 1
    code, side, total = rows[0][0], rows[0][1], rows[0][2]
    assert (code, side, total) == ('SHFE.ag2612', '买', '1')
    # 开仓价 ≠ 持仓均价（当日成交会被摊平 ✓）
    assert rows[0][4] == '13,863.0' and rows[0][5] == '13,974.0'
    assert rows[0][8] == '91,667.40'          # 占用保证金 ✓
    # 委托 / 成交表也有数 ✓
    assert payload['tables']['orders']['rows']
    trades = payload['tables']['trades']['rows']
    assert trades[0][6] == '10:02:11'         # 以前是 ':11.123' ✗


def test_clock_strips_date_and_millis():
    from minibt.desk.accounts import _clock

    assert _clock('2026-10-19 10:02:11.123') == '10:02:11'
    assert _clock('2026-10-19 10:02:11') == '10:02:11'
    assert _clock('10:02:11') == '10:02:11'


def test_trading_uses_shared_record_rows():
    trading = _read('minibt/desk/trading.py')
    # 记录统一走 accounts（含 tqsdk Entity 处理；`position_symbol` 也在这 ✓）
    assert 'from .accounts import position_symbol' in trading
    assert 'record_rows as _records' in trading
    assert "LONG_VOLUME = ('pos_long', 'volume_long')" in trading


# ------------------------------------------------------- ② 布局分隔条
def test_grid_resize_uses_measured_cell_size():
    """拖分隔条后左右宽窄不同 → 每格必须按**自己**的尺寸 resize ✓"""
    page = _read('jslib/src/desk/chart-page.ts')
    assert 'private cellElements: HTMLDivElement[] = [];' in page
    assert 'this.cellElements.push(cell);' in page
    # resize 逐格量尺寸（不再是 box.width / cols ✗）
    assert 'const cell = this.cellElements[index];' in page
    assert 'chart.resize(width, height);' in page
    # 拖动过程中就重算 + 分隔条跟着真实边界走
    assert '_scheduleResize()' in page
    assert '_positionSplitters()' in page


# ------------------------------------------------------- ③ 指标设置齿轮
def test_legend_gear_is_native_icon():
    legend = _read('jslib/src/general/legend.ts')
    assert 'export const GEAR = `' in legend        # 和 miniqt 同一个 ✓
    layer = _read('jslib/src/desk/indicator.ts')
    assert "import { GEAR } from '../general/legend';" in layer
    assert "${GEAR}" in layer
    page = _read('jslib/src/desk/chart-page.ts')
    assert '${GEAR}' in page
    assert '${isHidden ? EYE_CLOSED : EYE_OPEN}' in page
    assert "gear.textContent = '⚙'" not in page     # 丑 emoji 已移除 ✓
    css = _read('jslib/src/desk/desk.css')
    assert '.desk-legend-gear' in css and '.desk-legend-icon' in css
