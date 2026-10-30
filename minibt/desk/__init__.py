"""行情终端（desk）：**报价窗口 + 看盘窗口**，UI 全部是 JS/TS。

设计要点
--------
* UI 在 `pylightcharts/js/desk.html` + `desk.js`（源码 `jslib/src/desk/`）；
* Python 只做「数据 + 交易 + 推送」，通过 `window.__desk.applyPatch(...)` 更新界面；
* 界面上的动作通过 `window.callbackFunction('desk_~_<json>')` 回到
  :class:`~minibt.desk.app.Desk` 的命令表；
* **传输层可换**（`transport`）：Qt（QWebChannel）/ 浏览器（SSE + POST）/
  minibt-charts 自带后端。

最小用法::

    from minibt import Desk, tq_auth

    desk = Desk(title='MiniBT Desk')
    desk.add_futures(tq_auth=tq_auth('账号', '密码'))   # 期货（模拟/实盘）
    desk.add_stocks()                                  # 富途 OpenD（可选）
    desk.run()

命令速查
--------
两种写法完全等价（`pip install` 后可以省掉 `python -m`）::

    python -m minibt desk …      # 仓库里直接能用（无需安装入口）
    minibt desk …                # 安装后的命令行入口

一、启动方式
~~~~~~~~~~~~
* **桌面窗口（默认）** —— 原生 Qt 窗口，可多屏 / 拖拽 / 贴边::

    python -m minibt desk
    python -m minibt desk --theme light
    python -m minibt desk --title "我的行情终端"

* **浏览器壳** —— 起 `127.0.0.1` 本地服务，并自动打开系统浏览器::

    python -m minibt desk --browser
    python -m minibt desk --browser --port 8000
    python -m minibt desk --browser --port 8000 --theme dark

* **只起服务、不弹浏览器** —— 给 VS Code 扩展 / iframe / 自己的外壳托管::

    python -m minibt desk --browser --no-browser
    python -m minibt desk --browser --no-browser --json
    # --json 会额外打印一行就绪信息：
    # {"ready": true, "url": "http://127.0.0.1:56651/", "port": 56651, …}

二、连接场景
~~~~~~~~~~~~
* **期货 + 股票**（天勤快期模拟 + 本机 FutuOpenD）::

    python -m minibt desk --user 账号 --password 密码

* **只连期货**（跳过股票，FutuOpenD 没开也不报错）::

    python -m minibt desk --user 账号 --password 密码 --no-stocks

* **只连股票**（不传天勤账号即可；FutuOpenD 不需要账号）::

    python -m minibt desk
    python -m minibt desk --futu-host 192.168.1.20 --futu-port 11111

* **离线演示**（不连任何网关，用演示数据看界面）::

    python -m minibt desk --offline
    python -m minibt desk --offline --browser

* **浏览器 + 真实行情**::

    python -m minibt desk --browser --user 账号 --password 密码
    python -m minibt desk --browser --no-stocks          # 只期货

> 多账户（`TqMultiAccount`）、实盘账户、自定义初始资金等请用 Python API
> （:class:`Desk` / :meth:`Desk.add_futures` / :meth:`Desk.add_stocks`）；
> 命令行只走「快期模拟 + FutuOpenD」。

三、排障与自动化
~~~~~~~~~~~~~~~~
* **连接体检**（只打印各市场合约数量，不打开窗口）::

    python -m minibt desk --check
    python -m minibt desk --user 账号 --password 密码 --check
    python -m minibt desk --no-stocks --check

* **机器可读的体检报告**（方便脚本 / CI / 贴日志）::

    python -m minibt desk --check --json

* **固定端口 + 不弹浏览器**（VS Code / 远程开发 / 反向代理）::

    python -m minibt desk --browser --no-browser --port 8000

* **密码不落命令行**（走环境变量，`ps` / 日志里看不到明文）::

    # PowerShell
    $env:MINIBT_TQ_USER = '账号'
    $env:MINIBT_TQ_PASSWORD = '密码'
    python -m minibt desk --browser

    # bash / zsh
    MINIBT_TQ_USER=账号 MINIBT_TQ_PASSWORD=密码 \
        python -m minibt desk --browser

  支持的环境变量：`MINIBT_TQ_USER` / `MINIBT_TQ_PASSWORD` /
  `MINIBT_FUTU_HOST` / `MINIBT_FUTU_PORT` / `MINIBT_DESK_TITLE` /
  `MINIBT_DESK_THEME` / `MINIBT_DESK_PORT` / `MINIBT_DESK_BROWSER` /
  `MINIBT_DESK_NO_BROWSER` / `MINIBT_DESK_OFFLINE` /
  `MINIBT_DESK_NO_STOCKS`。**命令行显式给的参数永远优先**。

> 返回码：`0` = 正常 / 体检有数据；`2` = 一路行情都没连上（或体检没数据）。

四、参数速查
~~~~~~~~~~~~
====================  ============================================
参数                  说明
====================  ============================================
``--user``            天勤账号（快期）；不传 = 只连股票
``--password``        天勤密码（建议改用 ``MINIBT_TQ_PASSWORD``）
``--futu-host``       FutuOpenD 地址，默认 ``127.0.0.1``
``--futu-port``       FutuOpenD 端口，默认 ``11111``
``--no-stocks``       不连股票（只期货）
``--offline``         离线演示（不连任何网关）
``--browser``         浏览器壳（本地 HTTP + SSE）
``--no-browser``      浏览器壳但不自动打开系统浏览器
``--port``            浏览器壳端口，``0`` = 随机空闲端口
``--theme``           ``dark`` / ``light``
``--title``           窗口标题（默认「minibt桌面端」）
``--check``           只做连接体检，不打开窗口
``--json``            ``--check`` 报告 / 浏览器壳就绪信息用 JSON 输出
====================  ============================================

五、最小演示入口
~~~~~~~~~~~~~~~~
不想记参数时可以直接跑 ``demo``（默认离线）::

    python -m minibt.desk.demo --offline
    python -m minibt.desk.demo --browser
    python -m minibt.desk.demo --futures 账号 密码
    python -m minibt.desk.demo --stocks

文档：``minibt_docs/docs/minibt_desk/13.1_desk.md``
"""

from __future__ import annotations

__all__ = ['Desk', 'DEFAULT_FUTURES_TYPES', 'DEFAULT_EXCHANGES']


def __getattr__(name):                       # 惰性：别让 import minibt 拉起 Qt
    # ⚠ 只处理**自己导出的名字**：其它名字必须立刻抛 AttributeError，
    #   否则 `from . import symbols` 这类子模块导入会无限递归 ✗
    if name == 'Desk':
        from .app import Desk
        return Desk
    if name == 'DeskWindow':
        from .app_window import DeskWindow
        return DeskWindow
    if name == 'protocol':
        import importlib
        return importlib.import_module(__name__ + '.protocol')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
