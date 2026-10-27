#!/usr/bin/env python3
"""把 ``tutorials/`` 里的例子渲染成 PNG，供 ``minibt_docs`` 使用。

为什么不用原生窗口
------------------
``btplot(gui='pylightcharts')`` 会开一个 PyQt6 + WebView2 的**原生窗口**，
适合用户本地看，但不适合脚本批量跑（要有桌面会话、还要管窗口生命周期）。
这里改成**同一套渲染器的静态网页**：

* 用 ``gui='pylightcharts_web'``（网页版）；
* 补丁掉 ``pylightcharts.widgets.BrowserChart.show``：只把页面写成
  HTML（``live=False`` 时本来就是静态页），**不开浏览器**；
* 再用 headless Edge / Chrome 的 ``--screenshot`` 把 HTML 截成 PNG。

所以文档里的图和用户本地看到的是**同一个 lightweight-charts 渲染器**，
只是少了原生窗口的标题栏。

用法::

    # 单个例子 → 指定 PNG
    python scripts/capture_docs_images.py tutorials/styles/01_plotinfo_overview.py \
        --out minibt_docs/docs/minibt_styles/images/01_plotinfo_overview.png

    # 整个目录 → 统一输出到 <out-dir>/<例子同名>.png
    python scripts/capture_docs_images.py tutorials/styles \
        --out-dir minibt_docs/docs/minibt_styles/images

    # 只写 HTML，不截图（调样式时用）
    python scripts/capture_docs_images.py tutorials/styles \
        --html-dir /tmp/docs_html

依赖：本机有 Chrome / Edge（``pylightcharts.headless.find_browser`` 能找到）。
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import pathlib
import runpy
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Windows 控制台默认 GBK：minibt 的提示里有 ✗ / → 等字符，直接 print 会
# UnicodeEncodeError 把渲染打断 —— 统一改成 UTF-8（不行就替换字符）。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:                                        # noqa: BLE001
        pass

from pylightcharts.headless import find_browser            # noqa: E402
from pylightcharts.widgets import BrowserChart             # noqa: E402

#: 当前这一轮要写出的静态 HTML 路径（由 ``show`` 补丁读取）。
_HTML_TARGET = ''

#: 本次运行里出现的 **live** 图表：``[(url, chart), ...]``
#: （``btplot`` 是静态页；``Bt().run(gui='pylightcharts_web')`` 是 SSE 活图）
_LIVE_TARGETS: list = []

_ORIGINAL_SHOW = BrowserChart.show


def _patched_show(self, block=None, path=None, open_browser=None, port=None):
    """强制：静态页写到 ``_HTML_TARGET``、活图只记 URL；都不弹浏览器、不阻塞。"""
    result = _ORIGINAL_SHOW(self, block=False, path=_HTML_TARGET,
                            open_browser=False, port=port)
    if isinstance(result, str) and result.startswith('http'):
        _LIVE_TARGETS.append((result, self))
    return result


BrowserChart.show = _patched_show                   # type: ignore[assignment]


def load_example(path: pathlib.Path):
    """按文件路径导入例子模块（不触发它自己的 ``__main__``）。"""
    name = f'_docs_example_{path.stem}'
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise SystemExit(f'导入失败：{path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def render(example: pathlib.Path, html: pathlib.Path):
    """跑一遍例子。

    返回 ``('live', url, chart)`` 或 ``('html', path, None)``：

    * ``btplot(...)`` → 静态页（写 HTML 文件）；
    * ``Bt().run(gui='pylightcharts_web')`` → 本地 SSE 活图（只有 URL）。
    """
    global _HTML_TARGET
    html.parent.mkdir(parents=True, exist_ok=True)
    if html.exists():
        html.unlink()
    _HTML_TARGET = str(html)
    _LIVE_TARGETS.clear()
    module = load_example(example)
    main = getattr(module, 'main', None)
    if callable(main):
        # 统一走网页版：同一渲染器、不弹窗
        main(gui='pylightcharts_web')
    else:
        runpy.run_path(str(example), run_name='__main__')
    if _LIVE_TARGETS:
        url, chart = _LIVE_TARGETS[-1]
        return 'live', url, chart
    if not html.exists():
        raise SystemExit(f'例子既没写 HTML、也没起服务（是不是没画图？）：{example}')
    return 'html', html, None


def _shoot(target: str, png: pathlib.Path, width: int, height: int,
           virtual_time: bool) -> pathlib.Path:
    """headless Edge/Chrome 截图（``target`` 是 file URI 或 http URL）。"""
    browser = find_browser()
    if not browser:
        raise SystemExit('找不到 Chrome / Edge（可用环境变量 '
                         'PYLIGHTCHARTS_CHROME 指定）')
    png.parent.mkdir(parents=True, exist_ok=True)
    if png.exists():
        png.unlink()
    profile = os.path.join(tempfile.gettempdir(), '_minibt_docs_browser_profile')
    cmd = [
        browser, '--headless=new', '--disable-gpu', '--no-sandbox',
        '--hide-scrollbars', f'--window-size={width},{height}',
        f'--user-data-dir={profile}',
        f'--screenshot={png.resolve()}',
    ]
    if virtual_time:
        # 静态页：让 requestAnimationFrame / 定时器跑完再截。
        # ⚠ 活图（SSE）**不能**加：Chrome 会等网络空闲 → 永远等不到（实测挂 90s）
        cmd.append('--virtual-time-budget=6000')
    cmd.append(target)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not png.exists():
        raise SystemExit('截图失败：\n' + (result.stderr or '')[-1200:])
    return png


def screenshot_html(html: pathlib.Path, png: pathlib.Path,
                    width: int = 1600, height: int = 900) -> pathlib.Path:
    """静态页 → PNG。"""
    return _shoot(html.resolve().as_uri(), png, width, height, True)


def screenshot_url(url: str, png: pathlib.Path,
                   width: int = 1600, height: int = 900) -> pathlib.Path:
    """活图（SSE）→ PNG（不加 virtual-time-budget，否则会挂）。"""
    return _shoot(url, png, width, height, False)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='把 tutorials 例子渲染成 PNG')
    parser.add_argument('target', help='例子 .py 或目录')
    parser.add_argument('--out', default='', help='单个例子的输出 PNG')
    parser.add_argument('--out-dir', default='',
                        help='目录模式：输出目录（文件名 = 例子同名 .png）')
    parser.add_argument('--html-dir', default='',
                        help='目录模式：把中间 HTML 也留在这里（调试用）')
    parser.add_argument('--html-only', action='store_true',
                        help='只写 HTML、不截图')
    parser.add_argument('--width', type=int, default=1600)
    parser.add_argument('--height', type=int, default=900)
    args = parser.parse_args(argv)

    target = pathlib.Path(args.target)
    if not target.is_absolute():
        target = ROOT / target
    if not target.exists():
        raise SystemExit(f'找不到 {target}')

    examples = ([target] if target.is_file()
                else sorted(p for p in target.rglob('*.py')
                            if not p.name.startswith('_')))
    if not examples:
        raise SystemExit(f'{target} 里没有 .py')

    html_root = pathlib.Path(args.html_dir) if args.html_dir else pathlib.Path(
        tempfile.gettempdir()) / '_minibt_docs_html'
    out_dir = pathlib.Path(args.out_dir) if args.out_dir else None

    failed = []
    for example in examples:
        html = html_root / (example.stem + '.html')
        try:
            kind, target, chart = render(example, html)
        except SystemExit:
            raise
        except Exception as error:                            # noqa: BLE001
            failed.append(f'{example.relative_to(ROOT)}: {error}')
            print(f'[capture] FAIL {example.name}: {error}', flush=True)
            continue
        if args.html_only:
            print(f'[capture] {kind}  {example.name} -> {target}', flush=True)
            continue
        png = (pathlib.Path(args.out) if args.out
               else (out_dir or html_root) / (example.stem + '.png'))
        try:
            if kind == 'live':
                screenshot_url(target, png, args.width, args.height)
            else:
                screenshot_html(html, png, args.width, args.height)
        except SystemExit as error:
            failed.append(f'{example.relative_to(ROOT)}: {error}')
            print(f'[capture] FAIL {example.name}: {error}', flush=True)
            continue
        finally:
            if chart is not None:
                try:
                    chart.stop()
                except Exception:                            # noqa: BLE001
                    pass
        print(f'[capture] OK   {example.name} ({kind}) -> {png}', flush=True)

    if failed:
        print('\n失败：', flush=True)
        for item in failed:
            print('  ' + item, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
