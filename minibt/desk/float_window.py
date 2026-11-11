# coding: utf-8
"""把 AI 悬浮窗**浮到主窗口外**（独立的小置顶窗口；v1.3.7-42 / -49）。

做法（零 npm，复用现有 Qt 桥）：

```
main window (desk.html)                    float window (desk.html?pi=float)
        │                                          │
        └──────── 同一个 Desk / 同一个 Qt 桥 ────────┘
```

* 浮窗 = 再建一个 `QtPanel`（`pylightcharts` 的窗口 + QWebEngineView），
  加载 `desk.html?pi=float`；前端 `index.ts` 见到这个参数就**只渲染悬浮窗**；
* 两个窗口都要收补丁 → 把 `desk.sender` 包一层，往所有窗口广播；
* 浮窗置顶（`WindowStaysOnTopHint`）+ 无边框可选（默认保留系统标题栏）；
* 关掉浮窗只是隐藏，再次打开直接 `show()` 复用（不重新建浏览器）。

## 为什么需要「死页保护」（v1.3.7-49）

用户实测：**浮窗关掉之后**（尤其大模型连不上、每秒都有 `pi_event` 补丁时）
stderr 里开始刷

```
runJavaScript: disabled in Discarded state
runJavaScript: disabled in Discarded state
```

QtWebEngine 在页面被关闭 / 渲染进程结束 / 页面被 discard 之后，
`page().runJavaScript()` 就只剩这句警告；而我们的 `desk.sender` 广播还
握着那个**已经死掉的**面板，于是**每一条补丁刷一行**（看起来像死循环 ✗）。

修法三层（任一层生效就不会再刷）：

1. **发之前先验活**：`shiboken6.isValid()` + `page().lifecycleState() != Discarded`
   + `webview` 还在，任何一项不满足就**跳过**；
2. **一次失败就注销**：`both()` 广播时如果某个浮窗发不出去，立刻把它从
   `_STATE['senders']` 里摘掉（不再每拍重试 ✓）；
3. **关窗 / 销毁信号兜底**：`destroyed` / `lifecycleChanged` → 自动注销 +
   `desk.sender` 还原成原来的单窗口发送函数。
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from .app import DESK_HTML
from . import protocol as _protocol

#: 当前浮窗（单例）✓
_STATE: Dict[str, Any] = {
    'panel': None,
    'senders': [],
    'wrapped': False,
    'desk': None,
    'previous': None,
    'last_error': '',
}


# --------------------------------------------------------------------- 存活判断
def _alive(widget) -> bool:
    """Qt 控件还活着吗（`shiboken6.isValid` 不存在时退化为 True ✓）"""
    if widget is None:
        return False
    try:
        import shiboken6
    except Exception:                                        # noqa: BLE001
        return True
    try:
        return bool(shiboken6.isValid(widget))
    except Exception:                                        # noqa: BLE001
        return False


def _page_usable(panel) -> bool:
    """浮窗页面还能跑 JS 吗（被 discard / 已销毁 → False ✓）"""
    view = getattr(panel, 'webview', None)
    if not _alive(view):
        return False
    try:
        page = view.page()
    except Exception:                                        # noqa: BLE001
        return False
    if page is None or not _alive(page):
        return False
    try:
        from PyQt6.QtWebEngineCore import QWebEnginePage
        state = page.lifecycleState()
        if state == QWebEnginePage.LifecycleState.Discarded:
            return False
    except Exception:                                        # noqa: BLE001
        pass
    return True


def _send_to(panel, script: str) -> bool:
    """往浮窗发一条脚本；发不出去返回 False（调用方会把它注销 ✓）"""
    if not _page_usable(panel):
        return False
    try:
        panel.win.run_script(script)
        return True
    except RuntimeError:                                     # 页面已销毁
        return False
    except Exception:                                        # noqa: BLE001
        return False


def _drop_sender(sender: Optional[Callable], reason: str = '') -> None:
    """注销一个浮窗发送函数（关窗 / 页面 discard 后不再每拍重试 ✓）"""
    senders: List[Callable] = _STATE['senders']
    if sender is None:
        return
    for index, item in enumerate(list(senders)):
        if item is sender:
            senders.pop(index)
            if reason:
                _STATE['last_error'] = reason
            return


def _detach_all() -> None:
    """浮窗没了：清发送函数 + 还原 `desk.sender`（单窗口，别再过一层 ✓）"""
    _STATE['senders'] = []
    desk = _STATE.get('desk')
    previous = _STATE.get('previous')
    if _STATE['wrapped'] and desk is not None and callable(previous):
        try:
            desk.sender = previous
        except Exception:                                    # noqa: BLE001
            pass
    _STATE['wrapped'] = False
    _STATE['previous'] = None


def _attach_sender(desk) -> None:
    """`desk.sender` 包一层：主窗口 + 浮窗都收到补丁 ✓

    ★ 广播时**逐个验活**：发不出去的（用户已关窗 / 页面被 discard）
      立刻从列表里摘掉，不会每拍都往死页面塞脚本 ✓
    """
    if _STATE['wrapped']:
        return
    previous = desk.sender
    senders: List[Callable] = _STATE['senders']
    _STATE['desk'] = desk
    _STATE['previous'] = previous

    def both(script: str) -> None:
        if callable(previous):
            try:
                previous(script)
            except Exception:                                # noqa: BLE001
                pass
        for func in list(senders):
            try:
                ok = bool(func(script))
            except Exception:                                # noqa: BLE001
                ok = False
            if not ok:
                _drop_sender(func, '浮窗已关闭 / 页面已丢弃：已停止推送')

    desk.sender = both
    _STATE['wrapped'] = True


def _config_script(desk) -> str:
    config = {
        'transport': 'qt',
        'theme': desk.theme,
        'title': desk.title,
        'float': True,
    }
    return ('window.__deskConfig = %s;'
            % json.dumps(config, ensure_ascii=False))


# --------------------------------------------------------------------- 打开 / 关闭
def open_float(desk) -> str:
    """打开（或复用）悬浮窗外窗；返回 `''` = 成功，否则错误文本 ✓"""
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWidgets import QApplication
    from pylightcharts.widgets import QtPanel

    from .app_window import make_panel

    app = QApplication.instance()
    if app is None:
        return '没有 Qt 应用（浏览器壳不支持独立浮窗）'

    panel = _STATE.get('panel')
    if panel is not None and _page_usable(panel):
        try:
            panel.webview.show()
            _raise(panel)
            # 关窗期间我们不发脚本（见 `_send`）→ 重新打开时补一次配置 / 刷新 ✓
            _push_config(panel, desk)
            return ''
        except Exception:                                    # noqa: BLE001
            pass
    if panel is not None:
        # 页面已经 discard / widget 已销毁 → 丢掉重开（不然只会刷警告 ✗）
        close_float(desk)
        _STATE['panel'] = None

    try:
        panel = make_panel(QtPanel, None, DESK_HTML)
    except Exception as error:                                # noqa: BLE001
        return f'创建浮窗失败：{error!r}'

    win = panel.win
    # 命令回来还是走同一个 Desk ✓
    win.handlers[_protocol.CALLBACK] = (
        lambda *args: _on_command(desk, *args))
    _attach_sender(desk)

    def _send(script: str) -> bool:
        """浮窗自己的发送函数（返回 False = 已失效，广播会注销它 ✓）

        ★ 浮窗**关掉（隐藏）时不发**：Qt 对隐藏页面随时可能 discard，
          往它跑 JS 只会刷 `disabled in Discarded state`（用户实测 ✗）；
          重新打开时 `open_float()` 会补一次配置 + `refresh()`。
        """
        view = getattr(panel, 'webview', None)
        try:
            if view is not None and not view.isVisible():
                return True                  # 只是关着 → 保留 sender，不报错
        except Exception:                                    # noqa: BLE001
            pass
        if not _send_to(panel, script):
            _detach_all()
            return False
        return True

    _STATE['senders'].append(_send)
    _STATE['panel'] = panel
    # ★ 关窗 / 页面销毁 / 被 discard 都要**主动注销**（否则每秒都在往死页发 ✗）
    try:
        panel.webview.destroyed.connect(
            lambda *_: _on_float_gone(desk, panel, '浮窗窗口已销毁'))
    except Exception:                                        # noqa: BLE001
        pass
    try:
        panel.webview.renderProcessTerminated.connect(
            lambda *_: _on_float_gone(desk, panel, '浮窗渲染进程结束'))
    except Exception:                                        # noqa: BLE001
        pass
    try:
        page = panel.webview.page()
        page.destroyed.connect(
            lambda *_: _on_float_gone(desk, panel, '浮窗页面已销毁'))
        changed = getattr(page, 'lifecycleChanged', None)
        if changed is not None:
            changed.connect(
                lambda state: _on_lifecycle(desk, panel, state))
    except Exception:                                        # noqa: BLE001
        pass

    # 置顶 + 合适的初始大小
    try:
        from PyQt6.QtCore import Qt
        panel.webview.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        panel.webview.setWindowTitle('PI')
        panel.webview.resize(420, 520)
    except Exception:                                        # noqa: BLE001
        pass

    url = QUrl.fromLocalFile(DESK_HTML)
    url.setQuery('pi=float')
    try:
        panel.webview.load(url)
    except Exception as error:                                # noqa: BLE001
        return f'加载浮窗页面失败：{error!r}'
    try:
        panel.webview.show()
        _raise(panel)
    except Exception:                                        # noqa: BLE001
        pass
    # 主题配置在页面加载后再塞一次（`desk.html` 的 script 顺序不保证 ✓）
    try:
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(400, lambda: _push_config(panel, desk))
    except Exception:                                        # noqa: BLE001
        pass
    desk.push_log('AI 浮窗已打开（独立置顶窗口）', 'info')
    return ''


def _on_lifecycle(desk, panel, state) -> None:
    """页面生命周期变化：被 Qt **丢掉**（Discarded）→ 停止推送 ✓"""
    try:
        from PyQt6.QtWebEngineCore import QWebEnginePage
        if state == QWebEnginePage.LifecycleState.Discarded:
            _on_float_gone(desk, panel, '浮窗页面已丢弃（Discarded）')
    except Exception:                                        # noqa: BLE001
        pass


def _on_float_gone(desk, panel, reason: str) -> None:
    """浮窗没了：注销广播 + 丢掉引用（下次 ⧉ 会重新建 ✓）"""
    if _STATE.get('panel') is not panel:
        return
    _STATE['panel'] = None
    _detach_all()
    _STATE['last_error'] = str(reason or '')
    try:
        if desk is not None:
            desk.push_log(f'独立浮窗已关闭：{reason}（已停止推送，不会刷警告 ✓）',
                          'info')
    except Exception:                                        # noqa: BLE001
        pass


def close_float(desk=None) -> None:
    panel = _STATE.get('panel')
    _STATE['panel'] = None
    _detach_all()
    if panel is None:
        return
    # 先把信号断开，避免 close() 过程中又回调进来 ✓
    try:
        panel.webview.destroyed.disconnect()
    except Exception:                                        # noqa: BLE001
        pass
    try:
        page = panel.webview.page()
        page.destroyed.disconnect()
        changed = getattr(page, 'lifecycleChanged', None)
        if changed is not None:
            changed.disconnect()
    except Exception:                                        # noqa: BLE001
        pass
    try:
        panel.webview.close()
    except Exception:                                        # noqa: BLE001
        pass


def float_state() -> Dict[str, Any]:
    """调试 / 测试用：当前浮窗状态（不碰 Qt ✓）"""
    return {'open': _STATE.get('panel') is not None,
            'senders': len(_STATE.get('senders') or []),
            'wrapped': bool(_STATE.get('wrapped')),
            'last_error': str(_STATE.get('last_error') or '')}


def _push_config(panel, desk) -> None:
    # ★ 走同一个「验活 + 失败即注销」通道，别绕过去直接 run_script ✗
    if not _page_usable(panel):
        return
    _send_to(panel, _config_script(desk))
    _send_to(panel, 'if (window.__deskFloat) window.__deskFloat.refresh();')


def _raise(panel) -> None:
    try:
        panel.webview.raise_()
        panel.webview.activateWindow()
    except Exception:                                        # noqa: BLE001
        pass


def _on_command(desk, *args) -> None:
    message = args[0] if args else ''
    try:
        desk.handle(str(message))
    except Exception as error:                               # noqa: BLE001
        print(f'[desk] 浮窗命令失败: {error!r}')
