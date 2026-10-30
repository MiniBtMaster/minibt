"""Qt 壳：``DeskWindow``（复用 ``pylightcharts.QtPanel`` 的桥接 + 脚本队列）。

之所以继承 ``QtPanel`` 而不是 `QtChart`：desk 是**纯 DOM 应用**，
不需要 pylightcharts 的 `#container` 图表布局；桥接（QWebChannel +
``window.callbackFunction`` + 脚本队列）完全一样 ✓。
"""
from __future__ import annotations

import json
from typing import Any, Optional

from . import protocol as _protocol

#: 宿主页（构建产物；`jslib` 的 postbuild 会拷进 pylightcharts/js/ ✓）
from .app import DESK_HTML


def ensure_webchannel_asset(html: str) -> bool:
    """在 ``html`` 所在目录准备 ``qwebchannel.js``（同源加载才有效 ✓）

    Returns:
        True → 同源文件可用；False → 需要退回「文本注入」（调用方设环境变量）
    """
    import os

    folder = os.path.dirname(str(html or ''))
    if not folder:
        return False
    target = os.path.join(folder, 'qwebchannel.js')
    try:
        if os.path.isfile(target) and os.path.getsize(target) > 1000:
            return True
    except OSError:
        pass

    source = ''
    # ① 先看已安装的 pylightcharts 有没有现成的
    try:
        import importlib.util as _util
        spec = _util.find_spec('pylightcharts')
        if spec is not None and spec.origin:
            candidate = os.path.join(os.path.dirname(spec.origin), 'js',
                                     'qwebchannel.js')
            if os.path.isfile(candidate):
                with open(candidate, encoding='utf-8') as handle:
                    source = handle.read()
    except Exception:                                            # noqa: BLE001
        source = ''
    # ② 没有就从 pylightcharts 里生成（需要先注册 QtWebChannel 资源 ✓）
    if not source:
        try:
            from pylightcharts import widgets as _widgets
            _widgets._resolve('QWebChannel')                     # noqa: SLF001
            source = _widgets._qwebchannel_source()              # noqa: SLF001
        except Exception as error:                               # noqa: BLE001
            print(f'[desk] 读取 qwebchannel.js 失败: {error!r}')
            return False
    if not source:
        return False
    try:
        with open(target, 'w', encoding='utf-8') as handle:
            handle.write(source)
        return True
    except OSError as error:
        print(f'[desk] 写 qwebchannel.js 失败（{error}）→ 改用文本注入')
        return False


def make_panel(QtPanel, parent, html: str):
    """建 ``QtPanel``：新版本直接传 ``url``，老版本(0.1.5)建完再 ``load`` ✓

    ⚠ 老版本 ``QtPanel.__init__`` 只接受 ``(widget=None)``，传 ``url=`` 会
    ``TypeError``（用户实测过的坑）。降级路径同样安全：``qwebchannel`` 是在
    ``loadFinished`` 上注入的，手动 ``load`` 后仍然会注入 ✓。
    """
    import os

    # ★ **关掉 QtWebEngine 的 HTTP/磁盘缓存**：`file://` 的 desk.js 会被缓存住，
    #   前端 rebuild 后仍然跑旧代码（用户实测"改了永远不生效"✗）。
    #   顺便打印 desk.html 里的 `?v=` 版本号，一眼看出当前跑的是哪次构建 ✓
    # ★ 测试 / 无头环境（QT_QPA_PLATFORM=offscreen）不要碰
    #   `QWebEngineProfile.defaultProfile()`：本机 QtWebEngine 会直接
    #   exit 127，把整个 pytest 进程带走（审计 2026-10-25）。
    #   真实桌面仍清缓存；无头可用 PYLIGHTCHARTS_NO_WEBENGINE_CACHE=1 关闭。
    offscreen = str(os.environ.get('QT_QPA_PLATFORM') or '').lower() == 'offscreen'
    skip_cache = (offscreen or
                  bool(os.environ.get('PYLIGHTCHARTS_NO_WEBENGINE_CACHE')))
    if not skip_cache:
        try:
            from PyQt6.QtWebEngineCore import QWebEngineProfile
            profile = QWebEngineProfile.defaultProfile()
            profile.setHttpCacheType(
                QWebEngineProfile.HttpCacheType.MemoryHttpCache)
            profile.clearHttpCache()
        except Exception:                                        # noqa: BLE001
            pass
    try:
        with open(html, encoding='utf-8') as handle:
            text = handle.read()
        import re as _re
        found = _re.search(r'desk\.js\?v=([a-z0-9]+)', text)
        print('[desk] desk.js v=%s (build token; changes when frontend rebuilds)'
              % (found.group(1) if found else 'none'))
    except OSError:
        pass

    # ★ 同源 qwebchannel.js 必须先就位，否则 bridge 永远 ready 不了 ✗
    if not ensure_webchannel_asset(html):
        os.environ.setdefault('PYLIGHTCHARTS_QWC_FALLBACK', '1')
    try:
        return QtPanel(parent, url=html)
    except TypeError:
        panel = QtPanel(parent)
        try:
            from PyQt6.QtCore import QUrl
            panel.webview.load(QUrl.fromLocalFile(html))
        except Exception as error:                               # noqa: BLE001
            print(f'[desk] 加载 desk.html 失败: {error!r}')
        return panel


def qt_timer(interval_ms: int, callback):
    """``QTimer.singleShot`` 的循环封装（避免持有 timer 引用）"""
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(int(interval_ms), callback)
    return callback

# ★ `deskweb://` 必须在 QApplication 之前注册（网页 tab 用它绕开 X-Frame-Options ✓）
try:
    from . import web_proxy as _web_proxy

    _web_proxy.register_scheme()
except Exception:                                            # noqa: BLE001
    _web_proxy = None



class DeskWindow:
    """Qt 窗口：加载 ``desk.html`` 并把命令接回 :class:`~minibt.desk.app.Desk`"""

    def __init__(self, desk, parent=None):
        from pylightcharts.widgets import QtPanel

        self.desk = desk
        #: 复用 QtPanel：桥接 / qwebchannel / 脚本队列全都现成 ✓
        #: （pylightcharts >= 0.1.6 支持 ``url=``；老版本自动降级 ✓）
        self.panel = make_panel(QtPanel, parent, DESK_HTML)
        self.webview = self.panel.webview
        self.win = self.panel.win

        # 网页 tab 的 `deskweb://` 代理（剥掉 X-Frame-Options / frame-ancestors ✓）
        try:
            if _web_proxy is not None:
                _web_proxy.install(self.webview.page().profile())
        except Exception as error:                           # noqa: BLE001
            print(f'[desk] 网页代理不可用: {error!r}')

        self.win.handlers[_protocol.CALLBACK] = self._on_command
        desk.sender = self._send
        desk.pick_directory = self._pick_directory
        # ★ 连接 tqsdk 会阻塞主线程 → 给它一个"抽空处理界面消息"的入口
        #   （`_run_connect()` 在阻塞调用前会调它，至少能重绘 / 响应关闭 ✓）
        try:
            from PyQt6.QtWidgets import QApplication
            desk.pump_events = QApplication.processEvents
        except Exception:                                    # noqa: BLE001
            pass
        self._start_outbox_timer()

        self._send_config()
        self._on_load = None
        # ⚠ 不用 `deskweb://`：QtWebEngine 在 `file://` 页面里加载**自定义 scheme
        #   的 iframe** 会被安全策略拦掉（实测 handler 的 requestStarted 根本不
        #   触发 ✗）→ 统一走「后端抓取 + 内联资源」那条路（见 `web.py`）✓
        try:
            self.win.run_script('window.__deskWebProxy = false;')
        except Exception:                                    # noqa: BLE001
            pass
        self.webview.loadFinished.connect(self._on_loaded)

    # ------------------------------------------------------------ 启动
    def _send_config(self) -> None:
        """启动前先把配置塞进去（页面里 transport 自动识别为 qt ✓）"""
        config = {
            'transport': 'qt',
            'theme': self.desk.theme,
            'title': self.desk.title,
        }
        self.win.run_script('window.__deskConfig = %s;'
                            % json.dumps(config, ensure_ascii=False))

    def _on_loaded(self, ok: bool = True) -> None:
        if ok:
            self.win.run_script('window.__deskConfig = window.__deskConfig || '
                                '%s;' % json.dumps({'transport': 'qt'}))

    def _pick_directory(self, title: str = '选择目录') -> str:
        """Qt 系统目录选择框（个人指标/策略导入 ✓）"""
        from PyQt6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self.webview, title, '')
        return str(path or '')

    # ------------------------------------------------------------ 桥
    def _send(self, script: str) -> None:
        self.win.run_script(script)

    def _start_outbox_timer(self) -> None:
        """后台线程的补丁（指标计算 / 索引构建）由这个小定时器在主线程发出 ✓

        以前在后台线程直接 `runJavaScript` → **硬崩无 traceback**
        （用户实测：点指标闪退）；`QTimer.singleShot` 在非 Qt 线程里也不会触发，
        所以改成「发件箱 + 主线程定时器」✓
        """
        from PyQt6.QtCore import QTimer
        # DeskWindow 不是 QObject（`QtPanel` 包装层）→ 定时器不给 parent ✓
        self._outbox_timer = QTimer()
        self._outbox_timer.setInterval(60)
        self._outbox_timer.timeout.connect(self.desk.flush_outbox)
        self._outbox_timer.start()

    def _on_command(self, *args) -> None:
        """``desk_~_<json>`` → ``Desk.handle``（sync handler ✓）"""
        message = args[0] if args else ''
        try:
            self.desk.handle(str(message))
        except Exception as error:                               # noqa: BLE001
            print(f'[desk] 命令失败: {error!r}')

    # ------------------------------------------------------------ Qt API
    def resize(self, width: int, height: int) -> None:
        self.webview.resize(int(width), int(height))

    def show(self) -> None:
        self.webview.setWindowTitle(self.desk.title)
        self.webview.show()

    def setWindowTitle(self, title: str) -> None:                # noqa: N802
        self.webview.setWindowTitle(title)

    def get_webview(self):
        return self.webview

    #: `QApplication.exec()` 之后关窗即退出 ✓
    def close(self) -> None:
        # ★ 关窗口前**停掉策略实盘**：否则 desk 进程还在后台跑 →
        #   关掉界面后仍在下单（用户实测 ✗）
        live = None
        try:
            live = getattr(self.desk, '_strategy_live', None)
            self.desk.stop_strategy_live()
        except Exception:                                    # noqa: BLE001
            pass
        # ★ 停止后如果实盘线程还没退（tqsdk 的 `close()` 可能卡住）→ 直接
        #   结束进程，保证"关了界面不再下单"（用户实测过后台继续下单 ✗）
        try:
            if live is not None and live.running:
                import os as _os
                print('[desk] 策略实盘线程未退出 → 结束进程（防继续下单）')
                self.webview.close()
                _os._exit(0)
        except Exception:                                    # noqa: BLE001
            pass
        self.webview.close()
