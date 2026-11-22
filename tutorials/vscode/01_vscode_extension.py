"""12.1 · VS Code 扩展 minibt-charts —— 安装与运行

演示要点
--------
扩展 = `vscode-minibt/`（`minibt-charts`），提供：

| 命令 | 快捷键 | 作用 |
| --- | --- | --- |
| `minibt.runInEditor` | `Ctrl+Alt+M` | 在编辑器页签里跑当前 `.py` |
| `minibt.showLog` | — | 策略日志（带进度） |
| `minibt.reloadChart` / `minibt.stopChart` | — | 刷新图表 / 停止进程 |
| `minibt.openInBrowser` / `minibt.showOutput` | — | 浏览器打开 / 原始输出 |

**唯一必须配对的设置**：`minibt.pythonPath` → 装了 `minibt` + `pylightcharts`
（+ 它们的依赖 `rich` 等）的那个解释器。

运行：``python tutorials/vscode/01_vscode_extension.py``
文档：``minibt_docs/docs/minibt_ide/12.1_vscode_extension.md``
"""

import json
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from minibt import *                                  # noqa: E402,F403


def main(gui=None):
    pkg_file = REPO / 'vscode-minibt' / 'package.json'
    if not pkg_file.exists():                        # 只装了 pip 包时
        print('（没找到 vscode-minibt/package.json，跳过清单打印）')
        return
    pkg = json.loads(pkg_file.read_text(encoding='utf-8'))
    print('① 扩展:', pkg.get('displayName'), 'v' + str(pkg.get('version')))

    commands = [item['command']
                for item in pkg['contributes']['commands']]
    print('② 命令:', commands)

    print('③ 设置（默认值）：')
    props = pkg['contributes']['configuration']['properties']
    for key, info in props.items():
        print(f'   {key:22s} 默认 {info.get("default")!r}')

    print('④ 快捷键:', [k['key'] for k in pkg['contributes']['keybindings']])

    # ⑤ 解释器自检：扩展起不来的头号原因
    print('⑤ 当前解释器:', sys.executable)
    for module in ('minibt', 'pylightcharts', 'rich'):
        try:
            __import__(module)
            print(f'   import {module}: OK')
        except Exception as error:                   # noqa: BLE001
            print(f'   import {module}: FAIL ({type(error).__name__})')
    print('   → 把这个 python.exe 填到 minibt.pythonPath')


if __name__ == '__main__':
    main()
