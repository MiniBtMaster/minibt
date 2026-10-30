import asyncio
import html
import json
import importlib
import os
import pathlib
import sys
import tempfile
import time
from typing import Optional

from .export import CALLBACK_SHIM, PageExport
from .util import parse_event_message
from pylightcharts import abstract

# wx is imported by `WxChart` on first use: importing a GUI toolkit binds it for
# the whole process (see the Qt note below), and the browser / static / headless
# targets have no business doing that.


# ---------------------------------------------------------------------------
# Qt binding selection
#
# Importing two Qt bindings in one process loads conflicting Qt6 DLLs, which
# shows up later as "ImportError: DLL load failed while importing QtSvg". So we
# pick exactly one:
#   1. $PYLIGHTCHARTS_QT ("PyQt6" / "PySide6" / "PyQt5") if set
#   2. whichever binding the application already imported
#   3. otherwise probe in the historical order (PyQt5 -> PySide6 -> PyQt6)
# ---------------------------------------------------------------------------
_BINDINGS = (
    ('PyQt5', 'pyqtSlot', False),
    ('PySide6', 'Slot', True),
    ('PyQt6', 'pyqtSlot', False),
)


def select_qt_binding():
    """Return ``(module_name, slot_name, using_pyside6)`` or ``None``."""
    forced = os.environ.get('PYLIGHTCHARTS_QT', '').strip().lower()
    if forced:
        for name, slot, pyside in _BINDINGS:
            if name.lower() == forced:
                return name, slot, pyside
    for name, slot, pyside in _BINDINGS:
        if name in sys.modules:                     # already loaded by the host app
            return name, slot, pyside
    for name, slot, pyside in _BINDINGS:
        try:
            if importlib.util.find_spec(name) is not None:
                return name, slot, pyside
        except (ImportError, ValueError):
            continue
    return None


# The binding is imported lazily: `select_qt_binding()` above only *probes* (it
# looks at `sys.modules` and `find_spec`), so `import pylightcharts.widgets` no
# longer decides the Qt binding for the process. `QtChart` (or `_qt_backend()`)
# does the import, and a host app that later loads a different binding keeps
# working - mixing PySide6 with a PyQt6 app is not possible at all.
_QT: dict = {}


def _qt_backend() -> dict:
    """Import the selected Qt binding once and return its pieces.

    The returned dict has ``available`` plus (when available) ``name``,
    ``QObject``, ``Slot``, ``QUrl``, ``QTimer``, ``Qt``, ``QWebEngineView``,
    ``QWebChannel`` and ``Bridge`` (the QObject the page calls back into).
    """
    if _QT:
        return _QT
    binding = select_qt_binding()
    if binding is None:
        _QT['available'] = False
        return _QT

    name, slot, using_pyside6 = binding
    core = importlib.import_module(f'{name}.QtCore')
    try:
        webengine = importlib.import_module(f'{name}.QtWebEngineWidgets')
        channel = importlib.import_module(f'{name}.QtWebChannel')
        webengine_core = importlib.import_module(f'{name}.QtWebEngineCore')
    except ImportError as error:               # usually the QApplication ordering rule
        raise RuntimeError(
            f'{name}.QtWebEngineWidgets could not be imported: {error}\n'
            'Qt requires QtWebEngineWidgets to be imported (or '
            'Qt.AA_ShareOpenGLContexts to be set) BEFORE the QApplication is created.\n'
            'Call pylightcharts.qt.prepare_qt() (or import PyQt6.QtWebEngineWidgets) '
            'at the very top of your program.'
        ) from error

    qobject = core.QObject
    slot_factory = getattr(core, slot)

    class Bridge(qobject):                       # type: ignore[misc, valid-type]
        """Receives the page's callbacks over QWebChannel."""

        def __init__(self, chart):
            super().__init__()
            self.win = chart.win

        @slot_factory(str)
        def callback(self, message):
            emit_callback(self.win, message)

    _QT.update(
        available=True, name=name, using_pyside6=using_pyside6,
        QObject=qobject, Slot=slot_factory, QUrl=core.QUrl, QTimer=core.QTimer,
        Qt=getattr(core, 'Qt', None), QWebEngineView=webengine.QWebEngineView,
        QWebChannel=channel.QWebChannel,
        QWebEnginePage=webengine_core.QWebEnginePage, Bridge=Bridge,
    )
    return _QT


#: names that used to be module attributes; resolved on first access so that
#: `qt.py` / host code can keep asking for them without making the import eager
_LAZY_QT_NAMES = {'QWebEngineView', 'QWebChannel', 'QWebEnginePage', 'QObject',
                  'Slot', 'QUrl', 'QTimer', 'Qt', 'using_pyside6', 'Bridge'}


def _qwebchannel_file() -> str:
    """把 Qt 的 ``qwebchannel.js`` 落到包目录里，返回同源文件名（失败返回 ''）。

    注入大段 JS 文本（16KB+）和加载 ``qrc://`` 都属于"能不能成看环境"的做法：前者
    受 ``runJavaScript`` 载荷限制，后者是跨源加载、出错只报一句 ``Script error.``。
    写成一个同源文件、用 ``<script src="./qwebchannel.js">`` 引入最稳。
    """
    source = _qwebchannel_source()
    if not source:
        return ''
    target = pathlib.Path(__file__).resolve().parent / 'js' / 'qwebchannel.js'
    try:
        if not target.exists() or target.read_text(
                encoding='utf-8') != source:
            target.write_text(source, encoding='utf-8')
        return './qwebchannel.js'
    except OSError as error:
        print(f'[pylightcharts] could not write qwebchannel.js: {error}')
        return ''


def _qwebchannel_source() -> str:
    """Qt 的 ``qwebchannel.js`` 源码（读不到就返回空串）。

    以前是往页面里插 ``<script src="qrc:///qtwebchannel/qwebchannel.js">``：qrc 属于
    另一个源，加载/CDN 化一旦出问题，浏览器只报一句跨源的 "Script error."，页面加载
    正常但 ``window.pythonObject`` 永远不存在 —— 表现就是"窗口在、图全白"。改为从
    Python 侧读出同一份资源文本、以同源脚本注入，行为与 Qt 版本解耦。

    ``:/qtwebchannel/qwebchannel.js`` 这个资源是 ``QtWebChannel`` 模块被导入时才注册
    的，所以调用前必须先 ``_resolve('QWebChannel')``。
    """
    import sys

    try:
        binding = _qt_backend().get('name') or 'PyQt6'
        module = sys.modules.get(f'{binding}.QtCore')
        if module is None:
            import importlib
            module = importlib.import_module(f'{binding}.QtCore')
        handle = module.QFile(':/qtwebchannel/qwebchannel.js')
        if not handle.open(module.QIODevice.OpenModeFlag.ReadOnly):
            return ''
        return bytes(handle.readAll()).decode('utf-8')
    except Exception as error:            # 读不到就让调用方退回旧办法
        print(f'[pylightcharts] could not read qwebchannel.js: {error}')
        return ''


def _resolve(name: str):
    """The module global (a host override) if set, else the lazy backend.

    Downstream code (miniqt, `compat.py`) replaces `widgets.QWebEngineView` and
    friends to force a specific binding, so an explicitly set global always
    wins; otherwise the binding is imported on first use and cached in the
    module namespace.
    """
    if name in globals():
        return globals()[name]
    value = _qt_backend().get(name)
    globals()[name] = value
    return value


def __getattr__(name):
    if name in _LAZY_QT_NAMES:
        backend = _qt_backend()
        return backend.get(name) if name == 'using_pyside6' else backend.get(name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


try:
    from streamlit.components.v1 import html as sthtml
except ImportError:
    sthtml = None

try:
    from IPython.display import HTML, display
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="IPython.core.display")
except ImportError:
    HTML = None


def emit_callback(window, string):
    func, args = parse_event_message(window, string)
    if func is None:
        return
    # 回调出错不能带走调用方（widget 的定时器 / 消息循环），否则按钮会“全哑”
    try:
        if asyncio.iscoroutinefunction(func):
            asyncio.create_task(func(*args))
        else:
            func(*args)
    except Exception as error:
        print(f'[pylightcharts] 回调执行失败（已忽略）: {error}', file=sys.stderr)


def _log_js_error(*args):
    """JS 错误转发目标：把 ``console.error`` / ``window.onerror`` 打到 stderr ✓。"""
    print('[pylightcharts][js] ' + ' | '.join(str(a) for a in args),
          file=sys.stderr, flush=True)


class WxChart(abstract.AbstractChart):
    def __init__(self, parent, inner_width: float = 1.0, inner_height: float = 1.0,
                 scale_candles_only: bool = False, toolbox: bool = False,
                 attribution_logo: Optional[bool] = None):
        try:
            import wx
            import wx.html2
        except ImportError:
            raise ModuleNotFoundError(
                'wx.html2 was not found, and must be installed to use WxChart.')
        self.webview: wx.html2.WebView = wx.html2.WebView.New(parent)
        super().__init__(abstract.Window(self.webview.RunScript, 'window.wx_msg.postMessage.bind(window.wx_msg)'),
                         inner_width, inner_height, scale_candles_only, toolbox,
                         attribution_logo=attribution_logo)

        self.webview.Bind(wx.html2.EVT_WEBVIEW_LOADED, lambda e: wx.CallLater(500, self.win.on_js_load))
        self.webview.Bind(wx.html2.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, lambda e: emit_callback(self.win, e.GetString()))
        self.webview.AddScriptMessageHandler('wx_msg')

        self.webview.LoadURL("file://"+abstract.INDEX)

    def get_webview(self):
        return self.webview


class QtChart(abstract.AbstractChart):
    def __init__(self, widget=None, inner_width: float = 1.0, inner_height: float = 1.0,
                 scale_candles_only: bool = False, toolbox: bool = False,
                 attribution_logo: Optional[bool] = None):
        QWebEngineView = _resolve('QWebEngineView')
        if QWebEngineView is None:
            raise ModuleNotFoundError(
                'QWebEngineView was not found, and must be installed to use QtChart.')
        self.webview = QWebEngineView(widget)
        try:
            # 渲染进程崩了/恢复了都打一行（图表“卡住”时能区分是渲染进程问题 ✓）
            self.webview.renderProcessTerminated.connect(
                lambda *a: print(f'[pylightcharts] webview 渲染进程结束: {a}',
                                 flush=True))
            self.webview.renderProcessResponsive.connect(
                lambda: print('[pylightcharts] webview 恢复响应', flush=True))
        except Exception:                                        # noqa: BLE001
            pass
        super().__init__(abstract.Window(self.webview.page().runJavaScript, 'window.pythonObject.callback'),
                         inner_width, inner_height, scale_candles_only, toolbox,
                         attribution_logo=attribution_logo)
        # JS 错误转发：把 console.error / window.onerror 通过现有桥打到 stderr。
        # ★ 不用 QWebEnginePage 子类 + ``setPage``：换页会改变页面生命周期，
        #   可能与 GPU 表面创建竞态（把图弄成黑屏 ✗）。这里只覆盖两个全局钩子，
        #   不碰页面本身 ✓。
        try:
            self.win.handlers['__jserr'] = _log_js_error
            self.win.run_script(
                "(function () {"
                "  if (window.__pljserr) return;"
                "  window.__pljserr = true;"
                "  var send = function (m) {"
                "    try { window.callbackFunction('__jserr_~_' + m); } catch (e) {}"
                "  };"
                "  var origError = console.error;"
                "  console.error = function () {"
                "    send('console.error: ' + Array.prototype.slice.call(arguments).join(' '));"
                "    origError.apply(console, arguments);"
                "  };"
                "  window.onerror = function (msg, src, line, col) {"
                "    send('onerror: ' + msg + ' @' + src + ':' + line + ':' + col);"
                "  };"
                "})()"
            )
        except Exception:                                        # noqa: BLE001
            pass

        QWebChannel = _resolve('QWebChannel')
        Bridge = _resolve('Bridge')
        self.web_channel = QWebChannel()
        self.bridge = Bridge(self)
        self.web_channel.registerObject('bridge', self.bridge)
        self.webview.page().setWebChannel(self.web_channel)
        # PYLIGHTCHARTS_QWC_FALLBACK=1 时退回旧的 <script src="qrc://..."> 注入，
        # 用于把"我的同源注入"和"Qt 自己的 qrc 加载"两条路分开排查
        # 三条路，按稳定性排序：
        #   1) 同源文件 ./qwebchannel.js（默认，最稳）
        #   2) PYLIGHTCHARTS_QWC_URL=0 -> 退回直接注入文本
        #   3) PYLIGHTCHARTS_QWC_FALLBACK=1 -> 退回 <script src="qrc://...">
        import os as _os
        fallback = bool(_os.environ.get('PYLIGHTCHARTS_QWC_FALLBACK'))
        src_url = '' if fallback else _qwebchannel_file()
        qwebchannel_js = ('' if (fallback or src_url
                                 or _os.environ.get('PYLIGHTCHARTS_QWC_URL')
                                 == '0') else _qwebchannel_source())

        def _inject_web_channel(ok=None):
            bootstrap = (
                'if (typeof QWebChannel !== "undefined" && window.qt'
                ' && window.qt.webChannelTransport) {'
                ' new QWebChannel(qt.webChannelTransport, function (channel) {'
                ' window.pythonObject = channel.objects.bridge; }); }')
            if src_url:
                # 同源文件：小载荷，不依赖 qrc，也不受 runJavaScript 大小限制
                self.webview.page().runJavaScript(f'''
                let element = document.createElement("script")
                element.src = {src_url!r}
                element.onload = function () {{ {bootstrap} }}
                document.head.appendChild(element)
                ''')
            elif qwebchannel_js:
                # 同源注入：不再依赖 qrc 资源的加载行为
                self.webview.page().runJavaScript(
                    qwebchannel_js + "\n" + bootstrap)
            else:                             # 回退：老办法（<script src="qrc://...">）
                self.webview.page().runJavaScript('''
                let scriptElement = document.createElement("script")
                scriptElement.src = 'qrc:///qtwebchannel/qwebchannel.js'
                scriptElement.onload = function() {
                    var bridge = new QWebChannel(qt.webChannelTransport, function(channel) {
                        var pythonObject = channel.objects.bridge
                        window.pythonObject = pythonObject
                    })
                }
                document.head.appendChild(scriptElement)
                ''')

        self.webview.loadFinished.connect(_inject_web_channel)
        self.webview.loadFinished.connect(self._on_load_finished)
        Qt = _resolve('Qt')
        if _resolve('using_pyside6'):
            self.webview.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.webview.load(_resolve('QUrl').fromLocalFile(abstract.INDEX))

    def _on_load_finished(self):
        """等 QWebChannel 的 ``window.pythonObject`` 就绪后再 flush 队列脚本。

        ``qwebchannel.js`` 是在 ``loadFinished`` 里动态插入的，``pythonObject``
        何时可用不确定。旧实现固定等 200ms，冷启动时经常还没就绪，导致队列里第一个
        脚本 ``window.callbackFunction = window.pythonObject.callback`` 报
        ``Cannot read properties of undefined``，同一段拼接脚本后面的
        ``new Lib.Handler(...)`` 也被跳过 —— 于是 ``series`` / ``volumeSeries`` /
        ``legend`` 全部 undefined，图表打不开（再开一次因为 qwebchannel.js 已缓存
        才正常）。这里轮询 ``pythonObject``，就绪后再 ``on_js_load``；最多等 8 秒兜底。
        """
        QTimer = _resolve('QTimer')
        attempts = {'left': 160}      # 160 * 50ms = 8s

        def check():
            if self.win.loaded:
                return
            attempts['left'] -= 1
            if attempts['left'] <= 0:
                self.win.on_js_load()
                return
            self.webview.page().runJavaScript(
                'typeof window.pythonObject !== "undefined" && '
                'window.pythonObject !== null',
                lambda ready: self.win.on_js_load() if ready
                else QTimer.singleShot(50, check))

        QTimer.singleShot(50, check)

    def get_webview(self): return self.webview


class QtPanel:
    """A Qt WebEngine page that hosts **DOM panels** (DataGrid / Sparkline).

    The chart-less counterpart of :class:`QtChart`: it brings up the same host
    page, bridge and script queue, but adds no chart engine. Create panels on
    :attr:`win` and add :meth:`get_webview` to a layout::

        from pylightcharts import QtPanel
        from pylightcharts.panels import DataGrid, Column

        panel = QtPanel(parent)
        grid = DataGrid(panel.win, columns=[Column('symbol', '代码')])
        grid.set_rows(rows)
        layout.addWidget(panel.get_webview())
    """

    def __init__(self, widget=None, url=None):
        """``url`` 不传 → 图表宿主页 ``index.html``；传路径 → 自定义页面
        （例如 minibt desk 的 ``desk.html``，桥接/脚本队列完全一致 ✓）"""
        QWebEngineView = _resolve('QWebEngineView')
        if QWebEngineView is None:
            raise ModuleNotFoundError(
                'QWebEngineView was not found, and must be installed to use QtPanel.')
        self.webview = QWebEngineView(widget)
        self.win = abstract.Window(self.webview.page().runJavaScript,
                                   'window.pythonObject.callback')
        # A panel page has no chart handler to lay the container out, so make
        # ``#container`` fill the viewport. DataGrid then virtualises against a
        # real height instead of the (auto) content height.
        self.win.run_script(
            "(function(){var c=document.getElementById('container');"
            "if(c){c.style.position='absolute';c.style.left='0';c.style.top='0';"
            "c.style.right='0';c.style.bottom='0';}})();")

        QWebChannel = _resolve('QWebChannel')
        Bridge = _resolve('Bridge')
        self.web_channel = QWebChannel()
        self.bridge = Bridge(self)
        self.web_channel.registerObject('bridge', self.bridge)
        self.webview.page().setWebChannel(self.web_channel)

        # 与 QtChart 相同的三条 qwebchannel 注入路径（同源文件 / 文本注入 /
        # qrc 回退），QtPanel 没有图表，只需要 bridge 就绪即可。
        import os as _os
        fallback = bool(_os.environ.get('PYLIGHTCHARTS_QWC_FALLBACK'))
        src_url = '' if fallback else _qwebchannel_file()
        qwebchannel_js = ('' if (fallback or src_url
                                 or _os.environ.get('PYLIGHTCHARTS_QWC_URL')
                                 == '0') else _qwebchannel_source())

        def _inject_web_channel(ok=None):
            bootstrap = (
                'if (typeof QWebChannel !== "undefined" && window.qt'
                ' && window.qt.webChannelTransport) {'
                ' new QWebChannel(qt.webChannelTransport, function (channel) {'
                ' window.pythonObject = channel.objects.bridge; }); }')
            if src_url:
                self.webview.page().runJavaScript(f'''
                let element = document.createElement("script")
                element.src = {src_url!r}
                element.onload = function () {{ {bootstrap} }}
                document.head.appendChild(element)
                ''')
            elif qwebchannel_js:
                self.webview.page().runJavaScript(
                    qwebchannel_js + "\n" + bootstrap)
            else:
                self.webview.page().runJavaScript('''
                let scriptElement = document.createElement("script")
                scriptElement.src = 'qrc:///qtwebchannel/qwebchannel.js'
                scriptElement.onload = function() {
                    var bridge = new QWebChannel(qt.webChannelTransport, function(channel) {
                        var pythonObject = channel.objects.bridge
                        window.pythonObject = pythonObject
                    })
                }
                document.head.appendChild(scriptElement)
                ''')

        self.webview.loadFinished.connect(_inject_web_channel)
        self.webview.loadFinished.connect(self._on_load_finished)
        try:
            Qt = _resolve('Qt')
            if _resolve('using_pyside6'):
                self.webview.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        except Exception:                                        # noqa: BLE001
            # 绑定探测 / 枚举名差异不该影响面板创建
            pass
        # ★ QtPanel 支持自定义宿主页（如 minibt desk 的 desk.html ✓）
        self.webview.load(_resolve('QUrl').fromLocalFile(url or abstract.INDEX))

    def _on_load_finished(self):
        """等 ``window.pythonObject`` 就绪后再 flush 面板脚本队列（同 QtChart）。"""
        QTimer = _resolve('QTimer')
        attempts = {'left': 160}      # 160 * 50ms = 8s

        def check():
            if self.win.loaded:
                return
            attempts['left'] -= 1
            if attempts['left'] <= 0:
                self.win.on_js_load()
                return
            self.webview.page().runJavaScript(
                'typeof window.pythonObject !== "undefined" && '
                'window.pythonObject !== null',
                lambda ready: self.win.on_js_load() if ready
                else QTimer.singleShot(50, check))

        QTimer.singleShot(50, check)

    def get_webview(self):
        return self.webview


class StaticLWC(PageExport, abstract.AbstractChart):
    def __init__(self, width=None, height=None, inner_width=1, inner_height=1,
                 scale_candles_only: bool = False, toolbox=False,
                 autosize=True, attribution_logo: Optional[bool] = None):

        # the assets are UTF-8 (they contain characters such as the legend's
        # U+25A8 and the engine's trademark sign); without an explicit encoding
        # Windows falls back to the ANSI codepage (e.g. GBK) and raises
        # UnicodeDecodeError
        css_path = abstract.INDEX.replace('index.html', 'styles.css')
        js_path = abstract.INDEX.replace('index.html', 'bundle.js')
        lwc_path = abstract.INDEX.replace('index.html',
                                          'lightweight-charts.js')
        with open(css_path, encoding='utf-8') as f:
            css = f.read()
        with open(js_path, encoding='utf-8') as f:
            js = f.read()
        with open(lwc_path, encoding='utf-8') as f:
            lwc = f.read()

        with open(abstract.INDEX, encoding='utf-8') as f:
            self._html = f.read() \
                .replace('<link rel="stylesheet" href="./styles.css">', f"<style>{css}</style>")                 .replace('<link rel="stylesheet" href="styles.css">', f"<style>{css}</style>") \
                .replace(' src="./lightweight-charts.js">', f'>{lwc}') \
                .replace(' src="./bundle.js">', f'>{js}') \
                .replace('</body>\n</html>', '<script>')
        # `window.callbackFunction` 必须在**第一条图表语句之前**就存在：顶栏
        # switcher 在选中默认项时会调它（`intervalElements[0].click()`），而
        # `CALLBACK_SHIM`（静态页）与 live 适配器都是**最后**才拼进页面的，
        # 之前会在这里抛 `window.callbackFunction is not a function`，同样中断
        # 整个 <script> 块（Jupyter / 浏览器里 K 线与指标全都不画）。这里先放
        # 一个安全的 DOM 事件兜底；后面 live 适配器会用真正的 fetch 版覆盖它。
        self._html += (
            "\nif (typeof window.callbackFunction !== 'function') {"
            " window.callbackFunction = (message) => window.dispatchEvent("
            "new CustomEvent('pylightcharts-callback', { detail: message })); }")

        super().__init__(
            abstract.Window(run_script=self.run_script),
            inner_width, inner_height, scale_candles_only, toolbox,
            autosize, attribution_logo=attribution_logo)
        self.width = width
        self.height = height

    def run_script(self, script, run_last=False):
        if run_last:
            self.win.final_scripts.append(script)
        elif self.win.loaded and self.win.bulk_run.enabled:
            # `chart.batch()` 里：先攒着，退出时合成一段再落到页面 / 推送
            self.win.bulk_run.add_script(script)
        else:
            # 用 `;` 断开：脚本之间**不能靠自动分号插入（ASI）**连接 —— 有的
            # 语句以 `)` 结尾且不带分号（如 topbar 的 `xxx.intervalElements[0].click()`）
            # 而紧接着的是 `(function(){...})()`，拼在一起会变成
            # `click()(function(){...})()`，在页面加载时抛 TypeError 并**中断整个
            # <script> 块**，后面的 K 线 / 指标 setData 全都不执行（Jupyter / 浏览器
            # 里只剩一张空图；原生窗口逐条下发，所以没这个问题）。
            self._html += ';\n' + script

    def load(self):
        if self.win.loaded:
            return
        self.win.loaded = True
        for script in self.win.final_scripts:
            self._html += ';\n' + script
        self._load()

    def to_html(self) -> str:
        """The whole page as one self-contained HTML string.

        Unlike :meth:`load` this has no side effect (nothing is displayed), so a
        chart that was never shown can still be exported:

            chart.save_html('chart.html')       # or open_in_browser()
        """
        if not self.win.loaded:
            self.win.loaded = True
            self.win.scripts.extend(self.win.final_scripts)
            for script in self.win.scripts:
                # `;` 断开，理由同 :meth:`run_script`（防 ASI 把两条语句粘在一起）
                self._html += ';\n' + script
        # `_html` is left with an open <script> on purpose (the chart's own
        # statements are appended to it): close it *before* the shim, otherwise
        # the shim's tags end up inside the chart script, the whole block fails
        # to parse and the page stays black.
        return f'{self._html}</script>{CALLBACK_SHIM}</body></html>'

    def _load(self): pass


class StreamlitChart(StaticLWC):
    def __init__(self, width=None, height=None, inner_width=1, inner_height=1,
                 scale_candles_only: bool = False, toolbox: bool = False,
                 attribution_logo: Optional[bool] = None):
        super().__init__(width, height, inner_width, inner_height, scale_candles_only,
                         toolbox, attribution_logo=attribution_logo)

    def _load(self):
        if sthtml is None:
            raise ModuleNotFoundError('streamlit.components.v1.html was not found, and must be installed to use StreamlitChart.')
        sthtml(f'{self._html}</script></body></html>', width=self.width, height=self.height)


class BrowserChart(StaticLWC):
    """A chart shown in a normal browser tab - static or live.

    Same idea as `QtChart` / `WxChart` / `StreamlitChart`: another way to look
    at
    a chart, with no GUI toolkit and no extra dependency.

    **Static** (default) writes one self-contained HTML file (engine, bridge and
    styles inlined), so `file://` is enough::

        chart = BrowserChart(width=1200, height=700)
        chart.set(df)
        chart.add_sma('close', 20)
        chart.show()                 # writes + opens the file

    **Live** (`live=True`) serves the same page from a tiny stdlib HTTP server
    (Server-Sent Events, no dependency) and streams everything you do afterwards
    to every open tab - a real-time dashboard, not a snapshot::

        chart = BrowserChart(width=1200, height=700, live=True, port=8123)
        chart.set(df)
        chart.show(block=False)      # serves + opens a tab, returns the URL
        while True:
            chart.update(next_bar())  # appears in the browser immediately
            time.sleep(1)

    `port=0` (default) picks a free port, so the URL changes every run. Pass a
    fixed `port=` to keep one address across runs (reload instead of a new tab);
    if that port is busy the server falls back to a free one and warns -
    `chart.url` always holds the real address (`port_fallback=False` raises
    instead).

    Live tabs also get the widget callbacks (`chart.topbar[...]`, table clicks,
    `chart.events`): the page posts them back and they run in this process.
    Nothing is written to disk while live - the data lives in memory, exactly
    where the chart keeps it. When a tab connects (or reloads) it is sent the
    current data once (`resync=True`, the default) so it starts complete, then
    only the changes follow; pass `resync=False` to skip that re-send.

    Everything that defines the *layout* (series, panes, indicators, the top
    bar) should be created **before** `show()`: the page served to a new tab is
    the state at that moment, while the stream that follows carries the data
    updates - a series created later only exists in the tabs that were open at
    the time. If a tab looks stale it also shows a red "disconnected" banner
    once the stream ends (the python side stopped, or the port changed).

    What *doesn't* work in either mode are the readback APIs
    (`chart_options()`, `screenshot()`, `constants.verify()`, ...): a browser tab
    has no synchronous reply channel (same as `HeadlessChart`).
    """

    def __init__(self, width=None, height=None, inner_width: float = 1.0,
                 inner_height: float = 1.0, scale_candles_only: bool = False,
                 toolbox: bool = False, autosize: bool = True,
                 attribution_logo: Optional[bool] = None,
                 path: Optional[str] = None, live: bool = False,
                 host: str = '127.0.0.1', port: int = 0,
                 port_fallback: bool = True, resync: bool = True,
                 status: bool = True, token: Optional[str] = None):
        # before super(): the constructor already runs scripts, and the
        # override below looks at these flags
        self._server = None
        self._streaming = False
        self._run = ''
        super().__init__(width, height, inner_width, inner_height,
                         scale_candles_only, toolbox, autosize,
                         attribution_logo=attribution_logo)
        self.path = path
        self.live = live
        self.host = host
        self.port = port
        #: a busy *fixed* port falls back to a free one (with a warning)
        self.port_fallback = port_fallback
        self.resync = resync
        #: show a small "live" badge that also reports failures
        self.status = status
        #: required by the server when set (needed when the chart is reachable
        #: from the network, e.g. `host='0.0.0.0'` to look at it on a phone)
        self.token = token

    # ------------------------------------------------------------------ live
    @property
    def url(self) -> str:
        """The URL of the live server (empty until :meth:`show`)."""
        return self._server.url if self._server is not None else ''

    @property
    def clients(self) -> int:
        """How many browser tabs are connected to the live chart."""
        return self._server.clients if self._server is not None else 0

    def run_script(self, script: str, run_last: bool = False):
        """While live, new statements are streamed instead of accumulated."""
        if getattr(self, '_streaming', False) and self._server is not None:
            # `chart.batch()` 里也要先攒着：否则 K 线 / 指标会拆成多条推送，
            # 浏览器逐条渲染时看着就是“K 线先动、指标慢半拍”
            if self.win.bulk_run.enabled:
                self.win.bulk_run.add_script(script)
            else:
                self._server.push(script)
            return
        super().run_script(script, run_last)

    def show(self, block: Optional[bool] = None, path: Optional[str] = None,
             open_browser: Optional[bool] = None, port: Optional[int] = None) -> str:
        """Publish the chart: write (static) or serve (live) and open a tab.

        :param block: wait until Ctrl+C. Defaults to ``True`` for a live chart
            (it has to keep serving) and is ignored for a static one.
        :param path: static mode only - where to write the file.
        :param open_browser: open a tab (default ``True``).
        :param port: live mode only - override the port (0 = pick a free one).
        :return: the file path (static) or the URL (live).
        """
        if not self.live:
            target = path or self.path or os.path.join(
                tempfile.gettempdir(), 'pylightcharts-chart.html')
            written = self.save_html(target)
            if open_browser is not False:
                import webbrowser
                webbrowser.open('file://' + os.path.abspath(written), new=2)
            return written

        from .server import LiveServer
        import secrets
        self._run = secrets.token_hex(4)          # identifies this show() call
        if self._server is None:
            self._server = LiveServer(
                page=self._live_page,
                on_callback=self._on_browser_callback,
                on_connect=self._resync if self.resync else None,
                host=self.host,
                port=self.port if port is None else port,
                fallback=self.port_fallback,
                run=self._run,
                token=self.token,
            )
        self._server.run = self._run
        self._server.start()
        self._streaming = True
        if open_browser is not False:
            import webbrowser
            # a per-run query keeps the browser from reusing a tab that still
            # shows an *older* page (the address stays the one printed below)
            query = f'run={self._run}'
            if self.token:
                from urllib.parse import quote
                query = f'token={quote(self.token)}&' + query
            webbrowser.open(f'{self._server.url}?{query}', new=2)
            if self.token:
                print('[pylightcharts] the page needs its token: '
                      f'{self._server.url}?{query}')
        if block if block is not None else True:
            try:
                while self._server.running:
                    time.sleep(0.2)
            except KeyboardInterrupt:
                pass
            finally:
                self.stop()
        return self._server.url

    def stop(self) -> None:
        """Stop serving the live chart (open tabs keep the last state)."""
        self._streaming = False
        if self._server is not None:
            self._server.stop()

    # -------------------------------------------------------------- internals
    def _live_page(self) -> str:
        """The page plus the live adapter (SSE in, callbacks out)."""
        adapter = """<script>
// --- live bridge ----------------------------------------------------------
// Python -> page: Server-Sent Events, with a long-polling fallback for
// environments that cut long-lived HTTP (proxies, antivirus); page -> Python:
// POST /callback. Both carry the token when one is required.
const pylightchartsToken = %TOKEN%;
const pylightchartsUrl = (path, extra) => {
  const query = [
    pylightchartsToken ? 'token=' + encodeURIComponent(pylightchartsToken) : '',
    extra || '',
  ].filter(Boolean).join('&');
  return query ? path + '?' + query : path;
};
// which run this page belongs to: frames from another run are rejected
window.pylightchartsRun = %RUN%;
window.pylightchartsLiveCount = 0;
window.pylightchartsTransport = 'sse';
window.pylightchartsPollClient = '';

window.callbackFunction = (message) => {
  fetch(pylightchartsUrl('/callback'), {
    method: 'POST', body: String(message),
    headers: pylightchartsToken ? {'X-Auth-Token': pylightchartsToken} : {},
  }).catch(() => {});
};

// a hidden counter (usable as a "live" badge by the host page) ...
const pylightchartsLiveBadge = document.createElement('div');
pylightchartsLiveBadge.id = 'pylightcharts-live';
pylightchartsLiveBadge.dataset.pylightchartsStatus = 'connecting';
if (!%STATUS%) { pylightchartsLiveBadge.style.display = 'none'; }
pylightchartsLiveBadge.style.cssText =
  'position:fixed;right:8px;bottom:8px;z-index:9999;padding:2px 8px;'
  + 'border-radius:10px;font:11px/1.6 system-ui,sans-serif;'
  + 'background:rgba(20,22,28,0.85);color:#9aa4b2;'
  + 'border:1px solid rgba(255,255,255,0.12)';
pylightchartsLiveBadge.textContent = 'live · 0';
document.body.appendChild(pylightchartsLiveBadge);

// ... and a banner shown when the stream is gone (python stopped, port moved)
const pylightchartsLost = document.createElement('div');
pylightchartsLost.id = 'pylightcharts-live-lost';
pylightchartsLost.textContent =
  'pylightcharts: the live chart is disconnected - start the script again and '
  + 'use the URL it prints (every run picks a new port), or press F5';
pylightchartsLost.style.cssText =
  'position:fixed;left:0;right:0;bottom:0;z-index:10000;display:none;'
  + 'padding:6px 10px;font:12px/1.4 system-ui,sans-serif;text-align:center;'
  + 'background:#7f1d1d;color:#fff';
document.body.appendChild(pylightchartsLost);

const pylightchartsConnected = () => {
  pylightchartsLost.style.display = 'none';
  pylightchartsLiveBadge.dataset.pylightchartsStatus = 'connected';
  pylightchartsLiveBadge.style.color = '#4ade80';
  pylightchartsLiveBadge.textContent = 'live · ' + window.pylightchartsLiveCount;
};

const pylightchartsApply = (payload) => {
  // a page from an earlier run (fixed port, stale handle names) can never apply
  // these scripts: say so, show the banner and stop instead of half-updating
  if (payload.run !== window.pylightchartsRun) {
    pylightchartsLiveBadge.dataset.pylightchartsStatus = 'stale';
    pylightchartsLiveBadge.style.color = '#f87171';
    pylightchartsLiveBadge.textContent = 'live · stale tab (F5)';
    pylightchartsLost.textContent = 'pylightcharts: this tab belongs to an '
      + 'earlier run of the script - press F5 to reload the current chart';
    pylightchartsLost.style.display = 'block';
    window.pylightchartsTransport = 'stopped';
    if (window.pylightchartsLive) { window.pylightchartsLive.close(); }
    return;
  }
  try {
    (0, eval)(payload.script);
    window.pylightchartsLiveCount += 1;
    pylightchartsLiveBadge.textContent =
      'live · ' + window.pylightchartsLiveCount;
  } catch (error) {
    console.error('pylightcharts live script failed', error);
    pylightchartsLiveBadge.dataset.pylightchartsStatus = 'error';
    pylightchartsLiveBadge.style.color = '#f87171';
    pylightchartsLiveBadge.textContent = 'live · ' + error.message;
  }
};

// long-polling transport: plain request/response, works where SSE does not
async function pylightchartsPoll() {
  if (window.pylightchartsTransport !== 'poll') return;
  try {
    const url = pylightchartsUrl('/poll', window.pylightchartsPollClient
      ? 'client=' + encodeURIComponent(window.pylightchartsPollClient) : '');
    const response = await fetch(url);
    if (!response.ok) throw new Error('poll ' + response.status);
    const data = await response.json();
    window.pylightchartsPollClient = data.client;
    data.scripts.forEach(pylightchartsApply);
    pylightchartsConnected();
  } catch (error) {
    pylightchartsLiveBadge.dataset.pylightchartsStatus = 'disconnected';
    pylightchartsLiveBadge.style.color = '#f87171';
    pylightchartsLiveBadge.textContent = 'live · disconnected';
    pylightchartsLost.style.display = 'block';
  }
  setTimeout(pylightchartsPoll, 100);
}

const pylightchartsUsePolling = () => {
  window.pylightchartsTransport = 'poll';
  if (window.pylightchartsLive) {
    try { window.pylightchartsLive.close(); } catch (error) { /* gone */ }
  }
  pylightchartsPoll();
};

if (new URLSearchParams(location.search).get('transport') === 'poll') {
  pylightchartsUsePolling();
} else {
  window.pylightchartsLive = new EventSource(pylightchartsUrl('/events'));
  window.pylightchartsLive.onopen = pylightchartsConnected;
  window.pylightchartsLive.onmessage = (event) => pylightchartsApply(
    JSON.parse(event.data));
  window.pylightchartsLive.onerror = () => {
    if (window.pylightchartsTransport === 'sse') {
      pylightchartsUsePolling();          // cut by a proxy? keep going
      return;
    }
    pylightchartsLiveBadge.dataset.pylightchartsStatus = 'disconnected';
    pylightchartsLiveBadge.style.color = '#f87171';
    pylightchartsLiveBadge.textContent = 'live · disconnected';
    pylightchartsLost.style.display = 'block';
  };
}
</script>"""
        adapter = adapter.replace('%STATUS%', 'true' if self.status else 'false')
        adapter = adapter.replace('%RUN%', json.dumps(self._run or ''))
        adapter = adapter.replace('%TOKEN%', json.dumps(self.token or ''))
        page = self.to_html()
        if '</body>' in page:
            return page.replace('</body>', adapter + '</body>', 1)
        return page + adapter

    def _on_browser_callback(self, message: str) -> None:
        """A widget callback arrived from the browser (HTTP thread)."""
        try:
            func, args = parse_event_message(self.win, message)
            if func is not None:
                func(*args)
        except Exception as error:
            print(f'[pylightcharts] 回调执行失败（已忽略）: {error}',
                  file=sys.stderr)

    def _resync(self) -> list:
        """Scripts that bring a (re)connecting tab up to date."""
        collected: list = []
        real = self.run_script

        def collect(script, run_last=False):
            collected.append(script)

        self.run_script = collect
        try:
            self._emit_snapshot()
        finally:
            self.run_script = real
        return collected

    def _emit_snapshot(self) -> None:
        """Re-send the current data (candles, volume and every series)."""
        from .util import encode_series_data
        frame = getattr(self, 'candle_data', None)
        if frame is not None and not frame.empty:
            self.run_script(
                f'{self.id}.series.setData({encode_series_data(frame)})')
            volume = self._volume_data(frame)
            if volume is not None:
                self.run_script(
                    f'{self.id}.volumeSeries.setData({encode_series_data(volume)})')
        for series in self._lines:
            data = getattr(series, 'data', None)
            if data is not None and not data.empty:
                # `series.id` 可能已经不在了（Python 侧删了序列，但这里还留着 /
                # 或旧标签页）：一个缺失的句柄**不能中断整批 snapshot**，否则
                # 页面右下角会亮 `Cannot read properties of undefined
                # (reading 'series')`，后面的序列也不再更新 ✗。
                self.run_script(
                    f'(function(){{ var s = {series.id};'
                    f' if (s && s.series) s.series.setData('
                    f'{encode_series_data(data)}); }})()')


class JupyterChart(StaticLWC):
    def __init__(self, width: int = 800, height=350, inner_width=1, inner_height=1,
                 scale_candles_only: bool = False, toolbox: bool = False,
                 attribution_logo: Optional[bool] = None):
        super().__init__(width, height, inner_width, inner_height, scale_candles_only,
                         toolbox, False, attribution_logo=attribution_logo)

        self.run_script(f'''
            var host = document.getElementById('container') || document.body;
            for (var i = 0; i < document.getElementsByClassName("tv-lightweight-charts").length; i++) {{
                    var element = document.getElementsByClassName("tv-lightweight-charts")[i];
                    element.style.overflow = "visible"
                }}
            host.style.overflow = 'hidden'
            host.style.borderRadius = '10px'
            host.style.width = '{self.width}px'
            host.style.height = '100%'
            ''')
        self.run_script(f'{self.id}.chart.resize({width}, {height})')

    def _load(self):
        if HTML is None:
            raise ModuleNotFoundError('IPython.display.HTML was not found, and must be installed to use JupyterChart.')
        html_code = html.escape(f"{self._html}</script></body></html>")
        iframe = f'<iframe width="{self.width}" height="{self.height}" frameBorder="0" srcdoc="{html_code}"></iframe>'
        display(HTML(iframe))
