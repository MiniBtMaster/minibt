import asyncio
import ast
import json
import multiprocessing as mp
import sys
import typing
import webview
from webview.errors import JavascriptException

from pylightcharts import abstract
from .util import parse_event_message, FLOAT

import os
import threading
import time


def describe_js_error(error, script):
    """Turn a pywebview JavaScript error into a readable message."""
    detail = str(error)
    try:
        parsed = ast.literal_eval(detail)
        if isinstance(parsed, dict):
            name = parsed.get('name', 'Error')
            message = parsed.get('message', detail)
            line = parsed.get('line', '?')
            column = parsed.get('column', '?')
            detail = f'{name} ({line}:{column}): {message}'
    except Exception:
        pass
    snippet = script.strip().replace('\n', ' ')
    if len(snippet) > 300:
        snippet = snippet[:300] + '...'
    return f'{detail}\n  script: {snippet}'


class CallbackAPI:
    def __init__(self, emit_queue):
        self.emit_queue = emit_queue

    def callback(self, message: str):
        self.emit_queue.put(message)


class PyWV:
    def __init__(self, q, emit_q, return_q, loaded_event, closed_event):
        self.queue = q
        self.return_queue = return_q
        self.emit_queue = emit_q
        self.loaded_event = loaded_event
        # Set when a window is closed. Lives in the parent, which polls it as
        # `chart.is_alive`, so a plain `while chart.is_alive:` loop ends by itself
        # when the user closes the chart instead of hammering a dead webview.
        self.closed_event = closed_event

        self.is_alive = True

        self.callback_api = CallbackAPI(emit_q)
        self.windows: typing.List[webview.Window] = []
        #: 预热时 `start` 可能先到（窗口参数还没到），先存这儿
        self.pending_start = None
        self.loop()


    def create_window(
        self, width, height, x, y, screen=None, on_top=False,
        maximize=False, title=''
    ):
        screen = webview.screens[screen] if screen is not None else None
        if maximize:
            if screen is None:
                active_screen = webview.screens[0]
                width, height = active_screen.width, active_screen.height
            else:
                width, height = screen.width, screen.height

        self.windows.append(webview.create_window(
            title,
            url=abstract.INDEX,
            js_api=self.callback_api,
            width=width,
            height=height,
            x=x,
            y=y,
            screen=screen,
            on_top=on_top,
            # 不允许缩到比初始尺寸更小：窗口太窄时图表被挤没，还会让
            # evaluate_js 收不到回包、系列句柄报 null（图例标签消失不回来）
            min_size=(int(width), int(height)),
            background_color='#000000')
        )

        self.windows[-1].events.loaded += lambda: self.loaded_event.set()
        # Closing the window destroys the WebView2, and every later evaluate_js
        # on it fails inside pywebview's own error handler ("ObjectDisposedException:
        # WebView2"). Notice the close here so the loop stops and the parent can
        # see it.
        self.windows[-1].events.closed += self.on_window_closed

    def on_window_closed(self):
        self.is_alive = False
        if self.closed_event is not None:
            self.closed_event.set()
        self.emit_queue.put('exit')


    def _start_webview(self, debug):
        webview.start(debug=debug, func=self.loop)
        self.is_alive = False
        self.emit_queue.put('exit')

    def loop(self):
        # self.loaded_event.set()
        while self.is_alive:
            i, arg = self.queue.get()

            if i == 'start':
                if not self.windows:
                    # 预热场景：`prewarm()` 可能早于 `Chart(...)`（窗口参数还没到）。
                    # pywebview 要求先有窗口才能 start，所以把 start 记下来，
                    # 等第一个 create_window 到了再真正启动。
                    self.pending_start = arg
                    continue
                self._start_webview(arg)
                return
            if i == 'create_window':
                self.create_window(*arg)
                pending = getattr(self, 'pending_start', None)
                if pending is not None:
                    self.pending_start = None
                    self._start_webview(pending)
                    return
                continue

            window = self.windows[i]
            if arg == 'show':
                window.show()
            elif arg == 'hide':
                window.hide()
            elif not self.is_alive:
                # window already closed: skip the call, and answer pending
                # round-trips so they do not wait forever
                if arg.startswith('_~_~RETURN~_~_'):
                    rest = arg[len('_~_~RETURN~_~_'):]
                    request_id, separator, _ = rest.partition('~|~')
                    self.return_queue.put((
                        request_id if separator else None, False,
                        'the chart window has been closed'))
            elif arg.startswith('_~_~RETURN~_~_'):
                rest = arg[len('_~_~RETURN~_~_'):]
                request_id, separator, expression = rest.partition('~|~')
                if not separator:
                    request_id, expression = None, rest
                try:
                    self.return_queue.put((request_id, True, window.evaluate_js(expression)))
                except Exception as error:
                    self.return_queue.put((request_id, False, describe_js_error(error, expression)))
            else:
                try:
                    # Force the value to `undefined`: pywebview serializes the
                    # result of evaluate_js, and returning a live chart/pane/
                    # series object explodes into a huge structure with
                    # circular references.
                    window.evaluate_js(f'{arg}\n;undefined')
                except Exception as error:
                    # keep the message loop alive, just report the failure
                    print(f'[pylightcharts] {describe_js_error(error, arg)}', file=sys.stderr)


#: 原生窗口子进程没能就绪时给出的提示
_NATIVE_WINDOW_HINT = """[pylightcharts] 原生窗口启动失败：负责界面的子进程没有就绪。

Windows / macOS 用 spawn 方式启动子进程，它会**把你的入口脚本重新执行一遍**，
所以入口脚本必须带 main 保护，否则子进程里会再跑一次你的代码（窗口永远出不来）：

    if __name__ == '__main__':
        ...          # 你的绘图 / 回测 / 回放 / 实时代码

不想加保护的话，用网页版（不起子进程）即可：
    gui='pylightcharts_web'（= 'browser'），或者 bokeh 的 gui='bokeh'
"""


class WindowStartError(RuntimeError):
    """原生窗口（:class:`Chart` / :class:`QtChart`）的子进程起不来。

    最常见的原因是入口脚本没有 ``if __name__ == '__main__':`` 保护：Windows
    的 spawn 会重新执行入口脚本，子进程里又建一次窗口，于是永远等不到就绪
    （旧版本会一直卡在 ``loaded_event.wait()``）。浏览器版
    （``BrowserChart`` / ``gui='pylightcharts_web'``）没有这个限制。
    """

    def __init__(self, message: str = _NATIVE_WINDOW_HINT):
        super().__init__(message)


class WebviewHandler():
    def __init__(self) -> None:
        self._reset()
        self.debug = False

    def _reset(self):
        self.loaded_event = mp.Event()
        self.return_queue = mp.Queue()
        self.function_call_queue = mp.Queue()
        self.emit_queue = mp.Queue()
        self.closed_event = mp.Event()
        self.wv_process = mp.Process(
            target=PyWV, args=(
                self.function_call_queue, self.emit_queue,
                self.return_queue, self.loaded_event, self.closed_event
            ),
            daemon=True
        )
        self.max_window_num = -1

    def create_window(
        self, width, height, x, y, screen=None, on_top=False,
        maximize=False, title=''
    ):
        self.function_call_queue.put((
            'create_window',
            (width, height, x, y, screen, on_top, maximize, title)
        ))
        self.max_window_num += 1
        return self.max_window_num

    def prewarm(self) -> None:
        """提前把渲染子进程拉起来（`webview.start()` + 页面加载 ≈ 2 秒）。

        窗口初始化很贵，而且以前是**最后一步**才做：脚本先 import、再算指标、
        再建图，最后才 `show()` —— 那 2 秒完全串行在末尾，看起来就是"半天不出图"。
        提前调一次 `prewarm()`（或在 `Chart(...)` 之后立刻调），这 2 秒就能和
        指标计算 / 建图重叠。可重复调用（幂等）。
        """
        if self.__dict__.get('_prewarmed'):
            return
        self.__dict__['_prewarmed'] = True
        self.loaded_event.clear()
        try:
            self.wv_process.start()
        except RuntimeError as error:      # 父进程自己还在 spawn 引导阶段
            self.__dict__['_prewarmed'] = False
            raise WindowStartError() from error
        self.function_call_queue.put(('start', self.debug))

    def start(self, timeout: float = 30.0):
        self.prewarm()
        # 子进程起不来会**很快退出**（例如缺 main 保护时 spawn 直接抛错），
        # 所以这里不能无限等 —— 否则整个脚本看起来像卡死。
        deadline = time.monotonic() + timeout
        while not self.loaded_event.wait(0.05):
            if not self.wv_process.is_alive():
                raise WindowStartError()
            if time.monotonic() > deadline:
                raise WindowStartError(
                    _NATIVE_WINDOW_HINT
                    + "（等待子进程就绪已超过 %.0f 秒）" % timeout)

    def show(self, window_num):
        self.function_call_queue.put((window_num, 'show'))

    def hide(self, window_num):
        self.function_call_queue.put((window_num, 'hide'))

    def evaluate_js(self, window_num, script):
        self.function_call_queue.put((window_num, script))

    def exit(self):
        if self.wv_process.is_alive():
            self.wv_process.terminate()
            self.wv_process.join()
        self._reset()


class Chart(abstract.AbstractChart):
    _main_window_handlers = None
    WV: WebviewHandler = WebviewHandler()
    _is_alive: bool = False

    def __init__(
        self,
        width: int = 800,
        height: int = 600,
        x: int = None,
        y: int = None,
        title: str = '',
        screen: int = None,
        on_top: bool = False,
        maximize: bool = False,
        debug: bool = False,
        toolbox: bool = False,
        inner_width: float = 1.0,
        inner_height: float = 1.0,
        scale_candles_only: bool = False,
        position: FLOAT = 'left',
        attribution_logo: bool = False,
        keyboard: bool = True,
        keyboard_step: float = 0.1
    ):
        Chart.WV.debug = debug
        self._i = Chart.WV.create_window(
                    width, height, x, y, screen, on_top, maximize, title
                )

        window = abstract.Window(
                    script_func=lambda s: Chart.WV.evaluate_js(self._i, s),
                    js_api_code='pywebview.api.callback'
                )

        abstract.Window._return_q = Chart.WV.return_queue

        self.is_alive = True

        if Chart._main_window_handlers is None:
            super().__init__(window, inner_width, inner_height,
                             scale_candles_only, toolbox, position=position,
                             attribution_logo=attribution_logo, keyboard=keyboard,
                             keyboard_step=keyboard_step)
            Chart._main_window_handlers = self.win.handlers
        else:
            window.handlers = Chart._main_window_handlers
            super().__init__(window, inner_width, inner_height,
                             scale_candles_only, toolbox, position=position,
                             attribution_logo=attribution_logo, keyboard=keyboard)

    @property
    def is_alive(self) -> bool:
        """True while the chart window is open.

        It turns False as soon as the window is closed (the webview process sets
        the shared event) or :meth:`exit` is called, so a live loop can simply
        run ``while chart.is_alive:`` and end cleanly when the user closes the
        chart.
        """
        return self._is_alive and not Chart.WV.closed_event.is_set()

    @is_alive.setter
    def is_alive(self, value: bool) -> None:
        self._is_alive = bool(value)

    def show(self, block: bool = False):
        """
        Shows the chart window.\n
        :param block: blocks execution until the chart is closed.
        """
        if not self.win.loaded:
            Chart.WV.start()
            self.win.on_js_load()
        else:
            Chart.WV.show(self._i)
        if block:
            try:
                asyncio.run(self.show_async())
            except (KeyboardInterrupt, asyncio.CancelledError):
                # Windows 上 pywebview 的消息循环被 Ctrl+C 打断时，asyncio.run
                # 会抛 CancelledError/KeyboardInterrupt —— 这是正常退出路径，
                # 打一整页堆栈会让人以为出错了。
                print('[pylightcharts] 窗口已关闭')

    async def show_async(self):
        self.show(block=False)
        try:
            from pylightcharts import polygon
            [asyncio.create_task(self.polygon.async_set(*args)) for args in polygon._set_on_load]
            while 1:
                while Chart.WV.emit_queue.empty() and self.is_alive:
                    await asyncio.sleep(0.05)
                if not self.is_alive:
                    return
                response = Chart.WV.emit_queue.get()
                if response == 'exit':
                    Chart.WV.exit()
                    self.is_alive = False
                    return
                else:
                    # ★ 单个回调（包括消息解析）出错绝不能带走整个事件循环：
                    #   否则窗口还在，但整个界面的按钮全没反应
                    #   （回放“突然卡死”的典型成因 ✗）。
                    try:
                        func, args = parse_event_message(self.win, response)
                        if func is not None:
                            if asyncio.iscoroutinefunction(func):
                                await func(*args)
                            else:
                                func(*args)
                    except Exception as error:
                        print('[pylightcharts] 回调处理失败（已忽略，事件循环继续）: '
                              f'{error!r} 消息={response[:200]!r}',
                              file=sys.stderr)
        except KeyboardInterrupt:
            return

    def hide(self):
        """
        Hides the chart window.\n
        """
        self._q.put((self._i, 'hide'))

    def exit(self):
        """
        Exits and destroys the chart window.\n
        """
        Chart.WV.exit()
        self.is_alive = False
