"""Shared pytest setup for the miniqt tests.

**一个 QApplication 必须活到整个测试会话结束。** PyQt6 在 ``QApplication`` 被回收时会
连带失效一批「无父对象、且在 app 之后创建」的 Qt 对象 —— qfluentwidgets 的全局
``qconfig`` 正是其中之一。以前每个测试模块各起一个 module 作用域的 app fixture，
模块一结束 app 被回收，下一个模块建控件时就炸::

    RuntimeError: wrapped C/C++ object of type QConfig has been deleted

所以这里用 session 作用域持有它（模块自己的 fixture 仍能通过 ``QApplication.instance()``
拿到同一个 app ✓）。
"""
from __future__ import annotations

import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

#: 持有的唯一 QApplication 引用（模块级，防止被 GC 回收 ✓）
_APP = None


@pytest.fixture(scope='session', autouse=True)
def _qt_app():
    global _APP
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:                       # pragma: no cover - no PyQt6
        yield None
        return
    # QtWebEngineWidgets must be imported (or Qt.AA_ShareOpenGLContexts set)
    # **before** the QApplication exists, otherwise a later import of
    # ``pylightcharts.widgets.QWebEngineView`` raises. Import it here first, so
    # the lazy-attribute tests can still resolve the Qt backend.
    try:
        import importlib
        importlib.import_module('PyQt6.QtWebEngineWidgets')
        importlib.import_module('PyQt6.QtWebEngineCore')
    except ImportError:                       # pragma: no cover - no webengine
        pass
    _APP = QApplication.instance() or QApplication([])
    yield _APP
    # 故意保留 _APP：不要在会话结束时删掉 app


@pytest.fixture(autouse=True)
def _flush_qt_deletions_between_tests():
    """每个测试后清掉待处理的 Qt 删除事件。

    miniqt 的窗口测试会建（并持有）完整的 ``QWidget`` 窗口，一个测试里排队的
    ``deleteLater`` 可能落到**下一个**测试的事件循环里，去碰已经析构的 C++
    对象 —— 表现为解释器直接崩掉（exit 127、没有 pytest 汇总）。测试之间
    flush 一次 ``DeferredDelete`` 就能让它稳定。
    """
    yield
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QCoreApplication, QEvent
    except ImportError:                       # pragma: no cover - no PyQt6
        return
    app = QApplication.instance()
    if app is None:
        return
    try:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
    except Exception:                         # noqa: BLE001 - 别盖掉真正的失败
        pass


@pytest.fixture(scope='session', autouse=True)
def _isolate_user_state(tmp_path_factory):
    """别让测试读到 / 执行**用户真实环境**里的个人指标目录。

    ``PylightchartsChartWindow.__init__`` 会 ``personal_indicators.ensure_loaded()``
    （扫目录 + ``exec`` 用户的脚本）；不加隔离的话测试会去读
    ``~/.miniqt/personal_indicators.json``、执行用户自己一大堆脚本
    （还会因脚本里的临时文件操作把 pytest 的 capture 文件搞关 ✗）。
    """
    try:
        from miniqt.app.common import personal_indicators
    except Exception:                         # pragma: no cover - no miniqt
        yield
        return
    original = personal_indicators.CONFIG_FILE
    personal_indicators.CONFIG_FILE = str(
        tmp_path_factory.mktemp('personal-indicators') / 'pi.json')
    personal_indicators.reset_cache()
    # 「我的策略」同理：别去读用户真实的 personal_strategies.json ✓
    try:
        from miniqt.app.common import strategy_catalog
        original_strategies = strategy_catalog.PERSONAL_CONFIG_FILE
        strategy_catalog.PERSONAL_CONFIG_FILE = str(
            tmp_path_factory.mktemp('personal-strategies') / 'ps.json')
    except Exception:                         # pragma: no cover - no miniqt
        original_strategies = None
    # 指标收藏 / 点赞评论统计：也别写用户真实文件 ✓
    original_favorites = original_stats = None
    try:
        from miniqt.app.common import indicator_favorites
        original_favorites = indicator_favorites.FAVORITES_FILE
        indicator_favorites.FAVORITES_FILE = str(
            tmp_path_factory.mktemp('favorites') / 'fav.json')
        indicator_favorites._CACHE.clear()
    except Exception:                         # pragma: no cover - no miniqt
        pass
    try:
        from miniqt.app.common import indicator_stats
        original_stats = indicator_stats.STATS_FILE
        indicator_stats.STATS_FILE = str(
            tmp_path_factory.mktemp('stats') / 'stats.json')
        indicator_stats._CACHE.clear()
    except Exception:                         # pragma: no cover - no miniqt
        pass
    yield
    personal_indicators.CONFIG_FILE = original
    personal_indicators.reset_cache()
    if original_strategies is not None:
        strategy_catalog.PERSONAL_CONFIG_FILE = original_strategies
    if original_favorites is not None:
        indicator_favorites.FAVORITES_FILE = original_favorites
        indicator_favorites._CACHE.clear()
    if original_stats is not None:
        indicator_stats.STATS_FILE = original_stats
        indicator_stats._CACHE.clear()


@pytest.fixture(autouse=True)
def _reset_minibt_strategy_instances():
    """每个测试后重置全局策略注册表（`Base._strategy_instances`）。

    `KLine.run(...)` 跑完会把默认策略从注册表里 `pop` 掉（留给它返回的 `Bt`）。
    之后的测试再用一个“已弹出的 sid”查 `strategy_instances[sid]` 时，`addict`
    的 `__missing__` 会报 `AttributeError: 'StrategyInstances' object has no
    attribute '__frozen'`（该属性从未初始化）—— 表现为测试互相污染。
    这里只重置测试态，不动生产代码。
    """
    yield
    try:
        import minibt.utils as _mu
        _mu.Base._strategy_instances = _mu.StrategyInstances()
    except Exception:                         # pragma: no cover - no minibt
        pass


@pytest.fixture(autouse=True)
def _desk_symbol_index(tmp_path, monkeypatch):
    """desk 全市场合约索引：测试里**禁用网络构建**，并把文件指到临时目录 ✓

    （否则 `Desk()` 会在后台线程去拉几万个合约，还会写用户主目录）
    """
    monkeypatch.setenv('MINIBT_DESK_NO_INDEX', '1')
    try:
        from minibt.desk import symbol_cache, symbol_index
        monkeypatch.setattr(symbol_index, 'INDEX_FILE',
                            str(tmp_path / 'desk_symbol_index.sqlite3'))
        # 合约缓存也别读用户主目录里那份（否则搜索结果数会跟本机有关 ✓）
        original = symbol_cache.SymbolCache.__init__

        def _init(self, path=None, ttl_hours=24.0):
            original(self, str(tmp_path / 'desk_symbols.sqlite3'), ttl_hours)

        monkeypatch.setattr(symbol_cache.SymbolCache, '__init__', _init)
    except Exception:                                            # noqa: BLE001
        pass
    yield


@pytest.fixture(autouse=True)
def _reset_indicator_catalog_memory():
    """`indicator_catalog` 有内存缓存（`_MEMORY`）—— 某个测试在“坏包”环境里
    建过目录后，后面的测试会拿到那份不完整的缓存（overlay/参数变少 ✗）。
    这里每个测试前后都清一次 ✓
    """
    try:
        from minibt.desk import indicator_catalog
        indicator_catalog._MEMORY['items'] = None
        indicator_catalog._MEMORY['stamp'] = None
        indicator_catalog._WARNED.clear()
    except Exception:                                            # noqa: BLE001
        pass
    yield
    try:
        from minibt.desk import indicator_catalog
        indicator_catalog._MEMORY['items'] = None
        indicator_catalog._MEMORY['stamp'] = None
    except Exception:                                            # noqa: BLE001
        pass
