"""``y_margin``（K 线价格轴**上下留白**）—— 文档与代码必须一致 ✓。

以前 ``Bt.run`` 的 docstring 里**根本没提**这个参数 ✗（用户反馈），而它其实一直
在用：`run(y_margin=...)` → `RealtimeChart` / `ReplayWindow` →
`StrategyWindow._apply_y_margin()` → 每个 pane 价格轴的 `scaleMargins` ✓。
"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_normalise_y_margin_semantics():
    """文档里写的每一种写法都要真的这么算 ✓"""
    from minibt.utils import DEFAULT_Y_MARGIN, normalise_y_margin

    assert DEFAULT_Y_MARGIN == 0.1
    assert normalise_y_margin(None) == (0.1, 0.1)          # 不传 → 默认 10% ✓
    assert normalise_y_margin(0.1) == (0.1, 0.1)          # 单值 → 上下同值 ✓
    assert normalise_y_margin((0.1, 0.02)) == (0.1, 0.02)    # (top, bottom) ✓
    assert normalise_y_margin([0.04]) == (0.04, 0.04)        # 单元素列表 ✓
    assert normalise_y_margin((0.2, 0.1)) == (0.2, 0.1)      # LWC 原样 ✓
    assert normalise_y_margin(0.0) == (0.0, 0.0)             # 铺满 ✓
    assert normalise_y_margin(5) == (0.9, 0.9)               # 上限 0.9 ✓
    assert normalise_y_margin('x') == (0.1, 0.1)           # 非法值回退默认 ✓


def test_run_docstring_documents_y_margin():
    """★ 回归：``Bt.run`` 的注释里必须有 y_margin，且要点齐全 ✓"""
    from minibt.bt import Bt

    doc = Bt.run.__doc__ or ''
    assert 'y_margin' in doc, 'Bt.run 的注释没写 y_margin ✗'
    for keyword in ('价格轴上下留白', 'scaleMargins', '10%',
                    '0.2, 0.1', 'bokeh', '副图'):
        assert keyword in doc, f'注释里缺了关键说明：{keyword} ✗'


def test_apply_y_margin_covers_every_pane():
    """源码约束：留白要落到**每个 pane**（主图 + 各指标副图）✓"""
    src = (REPO / 'minibt' / 'strategy' / 'strategy_window.py').read_text(
        encoding='utf-8')
    start = src.index('def _apply_y_margin')
    body = src[start:start + 1400]
    assert 'scaleMargins' in body or 'margins' in body.lower()
    # 遍历所有 pane（panes() / for … pane）
    assert 'for' in body and 'pane' in body


def test_y_margin_reaches_both_chart_paths():
    """回测展示 / 回放 两条链路都要把它透传下去 ✓"""
    src = (REPO / 'minibt' / 'bt.py').read_text(encoding='utf-8')
    assert "kwargs.pop('y_margin', None)" in src
    assert src.count('y_margin=y_margin') >= 3


# --------------------------------------------------------------------------- #
# 参数归属：应该写在 Config 里（图表的设置），run 只做临时覆盖 ✓
# --------------------------------------------------------------------------- #
def test_config_has_y_margin_field():
    """★ ``Config.y_margin`` 存在，且默认 None（= 用 DEFAULT_Y_MARGIN ✓）"""
    from minibt.utils import Config, DEFAULT_Y_MARGIN

    assert hasattr(Config(), 'y_margin'), 'Config 里没有 y_margin ✗'
    assert Config().y_margin is None
    assert DEFAULT_Y_MARGIN == 0.1, '默认值应为 10% ✓'


def test_resolve_y_margin_priority():
    """优先级：run 覆盖 > 策略 ``self.y_margin`` > ``Config.y_margin`` > 默认 ✓"""
    from minibt.utils import Config, resolve_y_margin

    class _S:
        pass

    plain = _S(); plain.config = Config()
    assert resolve_y_margin(plain) == (0.1, 0.1)          # 默认 10% ✓

    cfg = _S(); cfg.config = Config(y_margin=0.08)
    assert resolve_y_margin(cfg) == (0.08, 0.08)            # Config 生效 ✓

    both = _S(); both.config = Config(y_margin=0.08)
    both.y_margin = (0.1, 0.02)
    assert resolve_y_margin(both) == (0.1, 0.02)            # 策略里写优先 ✓
    assert resolve_y_margin(both, 0.0) == (0.0, 0.0)        # run 覆盖最高 ✓
    assert resolve_y_margin(None) == (0.1, 0.1)           # 没策略 → 默认 ✓


def test_result_page_reapplies_y_margin():
    """★ 回归：切到**回测结果页**后要重新套一次留白 ✓

    （那一页会新建一堆副图 pane（其余合约/权益/回撤/盈亏）；以前
    ``set_contract`` 在 INFO_PAGES 分支**提前 return** ✗ → 这些 pane 一直是
    LWC 原样的 (0.2, 0.1)，和主图不一致 ✗。）
    """
    src = (REPO / 'minibt' / 'strategy' / 'strategy_window.py').read_text(
        encoding='utf-8')
    start = src.index('if contract in INFO_PAGES:')
    body = src[start:start + 400]
    assert 'self._show_info(contract)' in body
    assert 'self._apply_y_margin()' in body, '结果页没重新套留白 ✗'
    assert body.index('self._show_info(contract)') <         body.index('self._apply_y_margin()')


def test_run_resolves_y_margin_from_config():
    """``run()`` 要把 y_margin 解析成「run 覆盖 > 策略/Config > 0.1」✓"""
    src = (REPO / 'minibt' / 'bt.py').read_text(encoding='utf-8')
    assert 'def _resolve_y_margin' in src
    assert src.count('_resolve_y_margin(') >= 4      # 定义 1 + 三条链路 ✓
    assert "kwargs.pop('y_margin', None)" in src     # 仍接受 run 覆盖 ✓
