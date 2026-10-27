"""实时图「画线工具（toolbox）初始显示不稳定」—— 默认 False 却有时显示出来 ✗。

原因：显示/隐藏只是发一条

```js
if (chart.toolBox) chart.toolBox.div.style.display = 'none'
```

``toolBox`` **还没创建**时这条就是**空操作、而且不会再重试** ✗ → 之后工具箱被
建出来（默认是可见的 ✗）就一直显示着 ✗。所以“是否显示”取决于时序运气。

修法：先试一次；没有 ``toolBox`` 就**轮询**到它出现（最多 ~10s ✓）。
"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


class _Win:
    handlers = {}
    loaded = True


class _Chart:
    id = 'w_c1'
    win = _Win()

    def __init__(self):
        self.scripts = []

    def run_script(self, script, run_last=False):
        self.scripts.append((script, run_last))


def _stub():
    from minibt.strategy.strategy_window import StrategyWindow

    class _Stub:
        pass

    for name in ('_show_toolbox', '_hide_toolbox', '_apply_toolbox_visibility'):
        setattr(_Stub, name, getattr(StrategyWindow, name))
    stub = _Stub()
    stub.chart = _Chart()
    return stub


def test_hide_toolbox_retries_until_it_exists():
    """★ 回归：``toolBox`` 还没建好时不能只发一次空操作就完事 ✗"""
    stub = _stub()
    stub._hide_toolbox(run_last=True)
    script, run_last = stub.chart.scripts[-1]
    assert run_last is True                     # 页面加载后再跑 ✓
    assert 'setInterval' in script, '没有重试 → toolbox 会一直是显示的 ✗'
    assert '"none"' in script
    assert 'c.toolBox && c.toolBox.div' in script
    # 先试一次，成功就直接返回（不无谓地起定时器）
    assert 'if (apply()) { return; }' in script


def test_show_toolbox_uses_flex_and_retries():
    stub = _stub()
    stub._show_toolbox()
    script, run_last = stub.chart.scripts[-1]
    assert run_last is False                    # 立即执行 ✓
    assert '"flex"' in script and 'setInterval' in script


def test_setup_follows_toolbox_flag():
    """``_setup_toolbox`` 的初始显隐必须跟着 ``toolbox_initial`` ✓（源码约束）"""
    src = (REPO / 'minibt' / 'strategy' / 'strategy_window.py').read_text(
        encoding='utf-8')
    start = src.index('def _setup_toolbox')
    body = src[start:start + 1400]
    assert "self._toolbox_on = bool(getattr(self, 'toolbox_initial', False))" in body
    assert 'self._show_toolbox(run_last=True)' in body
    assert 'self._hide_toolbox(run_last=True)' in body


def test_toolbox_visibility_is_reapplied_on_contract_switch():
    """切合约时仍按当前开关重新应用 ✓（老行为不能丢）"""
    src = (REPO / 'minibt' / 'strategy' / 'strategy_window.py').read_text(
        encoding='utf-8')
    start = src.index('def set_contract')
    body = src[start:src.index('def set_backtest', start)]
    assert 'if self._toolbox_on:' in body and '_show_toolbox()' in body
