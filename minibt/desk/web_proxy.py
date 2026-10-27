"""Qt 壳里的「网页 tab」代理：`deskweb://host/path` → `https://host/path`。

**为什么需要它**：官网 / 文档站点会返回 `X-Frame-Options: SAMEORIGIN` 或
`Content-Security-Policy: frame-ancestors 'self'`，浏览器 / QtWebEngine 就
**禁止把页面放进 iframe**（用户实测：Chrome 报「防火墙或防病毒软件可能已阻止
您连接到网络」✗）。

而 `QWebEngineUrlSchemeHandler` 是我们自己答复请求的：**响应里根本没有这两个
头**，于是 iframe 里可以**真正加载整页**（脚本、样式、相对路径全部正常，不再
需要"抓 HTML + 内联 CSS"那种静态快照 ✓）。

顶层导航（直接 `load()`）本来就不受 `X-Frame-Options` 限制，但它会把 desk
自己的页面导航走 ✗ —— 所以走自定义 scheme + iframe 才是对的。

注册时机：`QWebEngineUrlScheme.registerScheme()` 必须在 `QApplication` / 
`QWebEngineProfile` 创建**之前**调用 —— `app_window.py` 在 import 时就注册 ✓
"""
from __future__ import annotations

import os
from typing import Dict, Optional

#: 自定义 scheme 名（前端写 `deskweb://host/path` ✓）
SCHEME = b'deskweb'
SCHEME_TEXT = SCHEME.decode()

#: 伪装成桌面 Chrome（有些站点没有 UA 直接 403 ✓）
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

_REGISTERED = False
_HANDLERS: Dict[int, object] = {}


def register_scheme() -> bool:
    """注册 `deskweb://`（幂等；**必须在 QApplication 之前** ✓）"""
    global _REGISTERED
    if _REGISTERED:
        return True
    try:
        from PyQt6.QtWebEngineCore import QWebEngineUrlScheme
    except Exception:                                        # noqa: BLE001
        return False
    try:
        scheme = QWebEngineUrlScheme(SCHEME)
        scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
        scheme.setFlags(
            QWebEngineUrlScheme.Flag.SecureScheme
            | QWebEngineUrlScheme.Flag.LocalAccessAllowed
            | QWebEngineUrlScheme.Flag.CorsEnabled
            | QWebEngineUrlScheme.Flag.FetchApiAllowed
        )
        QWebEngineUrlScheme.registerScheme(scheme)
        _REGISTERED = True
    except Exception as error:                               # noqa: BLE001
        print(f'[desk] 注册 {SCHEME_TEXT}:// 失败: {error!r}', flush=True)
        return False
    return True


def install(profile) -> bool:
    """把代理 handler 装到这个 profile 上（幂等 ✓）"""
    if profile is None:
        return False
    key = id(profile)
    if key in _HANDLERS:
        return True
    if not register_scheme():
        return False
    try:
        from PyQt6.QtWebEngineCore import (QWebEngineUrlRequestJob,
                                           QWebEngineUrlSchemeHandler)
        from PyQt6.QtCore import (QBuffer, QIODevice, QObject, QUrl,
                                  QUrlQuery)
        from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
    except Exception:                                        # noqa: BLE001
        return False

    class _Handler(QWebEngineUrlSchemeHandler):
        def __init__(self, parent: Optional[QObject] = None):
            super().__init__(parent)
            self.manager = QNetworkAccessManager(self)
            self._replies: Dict[int, object] = {}

        def requestStarted(self, job) -> None:              # noqa: N802
            url = job.requestUrl()
            print(f'[deskweb] {url.toString()}', flush=True)
            host = url.host()
            if not host:
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            target = QUrl(f'https://{host}{url.path() or "/"}')
            query = url.query()
            if query:
                target.setQuery(QUrlQuery(query))
            request = QNetworkRequest(target)
            try:
                request.setAttribute(
                    QNetworkRequest.Attribute.RedirectPolicyAttribute,
                    QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
                request.setHeader(
                    QNetworkRequest.KnownHeaders.UserAgentHeader, USER_AGENT)
                request.setRawHeader(b'Accept-Language',
                                     b'zh-CN,zh;q=0.9,en;q=0.8')
            except Exception:                                # noqa: BLE001
                pass
            reply = self.manager.get(request)
            self._replies[id(job)] = reply

            def finish() -> None:
                self._finish(job, reply)

            reply.finished.connect(finish)

        def _finish(self, job, reply) -> None:              # noqa: N802
            self._replies.pop(id(job), None)
            try:
                from PyQt6.QtWebEngineCore import QWebEngineUrlRequestJob
                from PyQt6.QtNetwork import QNetworkRequest
                from PyQt6.QtCore import QBuffer, QIODevice
            except Exception:                                # noqa: BLE001
                return
            status = reply.attribute(
                QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if status and int(status) >= 400:
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            data = reply.readAll()
            kind = reply.header(
                QNetworkRequest.KnownHeaders.ContentTypeHeader) or ''
            if isinstance(kind, str):
                kind = kind.encode('utf-8')
            buffer = QBuffer(job)                            # job 持有 → 不回收 ✓
            buffer.setData(data)
            buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            try:
                job.reply(kind or b'application/octet-stream', buffer)
            except Exception:                                # noqa: BLE001
                pass

    try:
        handler = _Handler(profile)
        profile.installUrlSchemeHandler(SCHEME, handler)
        _HANDLERS[key] = handler
    except Exception as error:                               # noqa: BLE001
        print(f'[desk] 安装 {SCHEME_TEXT}:// handler 失败: {error!r}',
              flush=True)
        return False
    return True


def rewrite(url: str) -> str:
    """`https://host/path` → `deskweb://host/path`（非 http(s) 原样返回 ✓）"""
    text = str(url or '').strip()
    if text.lower().startswith('https://'):
        return SCHEME_TEXT + '://' + text[8:]
    if text.lower().startswith('http://'):
        return SCHEME_TEXT + '://' + text[7:]
    return text
