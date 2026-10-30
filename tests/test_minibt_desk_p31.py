"""P31：天勤行情泵（wait_update）+ 指标模块缺失诊断 ✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


# ------------------------------------------------------------ 行情泵
def test_tick_pumps_tqsdk():
    """tqsdk 必须调 wait_update，否则行情永远不更新（用户实测冻在 10:30 ✗）"""
    app = _read('minibt/desk/app.py')
    assert 'def pump(self, timeout: float = None)' in app
    # ⚠ tqsdk 的 deadline 是**绝对时间戳**，不是“等多少秒” ✓
    assert 'wait(deadline=time.time() + span)' in app
    assert 'PUMP_DEADLINE = 0.05' in app
    assert "step('行情泵', self.pump)" in app


def test_pump_called_by_tick():
    from minibt.desk import app as appmod
    from minibt.desk import user_prefs
    import tempfile

    tmp = tempfile.mkdtemp()
    user_prefs.PREFS_FILE = str(pathlib.Path(tmp) / 'p.json')

    import time as _time

    calls = []

    class FakeApi:
        def wait_update(self, deadline=None):
            calls.append(deadline)
            return True

    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.futures = type('F', (), {'api': FakeApi()})()
    desk.feeds = [desk.futures]
    desk._tick_at = 0
    before = _time.time()
    desk.tick()
    assert len(calls) == 1
    # tqsdk 的 deadline 是**绝对时间戳**（不是秒数）✓
    assert before <= calls[0] <= _time.time() + 1.0
    desk._tick_at = 0
    desk.tick()
    assert len(calls) == 2


def test_pump_survives_api_error():
    from minibt.desk import app as appmod

    class BadApi:
        def wait_update(self, deadline=None):
            raise RuntimeError('并发使用')

    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.futures = type('F', (), {'api': BadApi()})()
    desk.pump()          # 不能抛 ✓
    desk.pump()          # 第二次不再刷日志
    logs = [row for row in desk.sent if '"type":"log"' in str(row)]
    assert len(logs) == 1


# ------------------------------------------------------------ 指标模块诊断
def test_diagnose_reports_ok():
    from minibt.desk import indicator_catalog as cat

    info = cat.diagnose()
    assert info['ok'] is True
    assert info['missing'] == []
    assert info['files'] and 'core.py' in info['files']


def test_submodule_falls_back_to_file(tmp_path, monkeypatch):
    """包是 namespace / `.py` 没装进去时，按**文件路径**加载 ✓"""
    import sys
    import types

    from minibt.desk import indicator_catalog as cat

    import minibt
    root = pathlib.Path(minibt.__file__).parent
    broken = types.ModuleType('minibt.indicators')
    broken.__path__ = [str(root / 'indicators')]
    monkeypatch.setitem(sys.modules, 'minibt.indicators', broken)
    monkeypatch.setattr(minibt, 'indicators', broken, raising=False)
    # 让 import_module 失败（模拟「没装进去」）
    import importlib

    real_import = importlib.import_module

    def fake_import(name, *args, **kwargs):
        # 只让「目标模块」导不进来（相对导入的兄弟模块仍然可以 ✓）
        if name == 'minibt.indicators.core':
            raise ModuleNotFoundError(f"No module named '{name}'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, 'import_module', fake_import)

    module = cat._submodule('core')       # ← 走文件路径兜底
    assert hasattr(module, 'CoreIndicators')


def test_warn_install_prints_hint(capsys):
    from minibt.desk import indicator_catalog as cat

    cat._WARNED.clear()
    cat._warn_install(ModuleNotFoundError("No module named 'x'"))
    out = capsys.readouterr().out
    assert 'pip install -e .' in out
    cat._warn_install(ModuleNotFoundError("No module named 'x'"))   # 只提示一次
    assert capsys.readouterr().out == ''


def test_cli_check_reports_indicators():
    cli = _read('minibt/cli.py')
    assert "report['indicators']" in cli
    assert 'indicator_catalog as _cat' in cli
    # P53：Windows GBK 控制台会把 ✓/✗/⚠ 打成 UnicodeEncodeError（`--check`
    # 最后一行直接崩）→ **输出**统一改成 `[OK] / [X] / [!]`
    # （注释/文档里的 ✓ 不影响运行，不用改 ✓）
    assert '[指标] [!] 缺少：' in cli
    assert '（有数据 [OK]）' in cli
    outputs = [line for line in cli.splitlines()
               if 'log(' in line or 'print(' in line]
    for line in outputs:
        for mark in ('✓', '✗', '⚠'):
            assert mark not in line, line


def test_pump_drops_non_existent_contract_subscription():
    from minibt.desk import app as appmod

    dropped = []

    class BadApi:
        def wait_update(self, deadline=None):
            raise RuntimeError(
                "查询合约服务报错 failed to execute graphql operation, "
                "errors: [variable instrument_id: [rb2701] contains "
                "non-existent instrument: rb2701]")

    class Feed:
        api = BadApi()

        def drop_symbol(self, symbol):
            dropped.append(symbol)

    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.futures = Feed()
    desk.pump()
    assert 'rb2701' in dropped
    logs = [row for row in desk.sent if '"type":"log"' in str(row)]
    assert any('已移除无效订阅' in str(row) for row in logs)
