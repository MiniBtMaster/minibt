"""12.5 · 打包 / 发布 / FAQ

演示要点
--------
| 做什么 | 命令 |
| --- | --- |
| 打 Python 包 | `python -m build`（产物在 `dist/`） |
| 装本地包 | `pip install -e .` |
| 打 VS Code 扩展 | `cd vscode-minibt && npx @vscode/vsce package` |
| 发布扩展 | `npx @vscode/vsce publish` / `npx ovsx publish` |
| 打文档 | `mkdocs build -f minibt_docs/mkdocs.yml` |

运行：``python tutorials/vscode/05_packaging_faq.py``
文档：``minibt_docs/docs/minibt_ide/12.5_packaging_faq.md``
"""

import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import minibt                                          # noqa: E402
import pylightcharts                                   # noqa: E402


def main(gui=None):
    print('① 版本: minibt', minibt.__version__,
          '| pylightcharts', getattr(pylightcharts, '__version__', '?'))
    print('   解释器:', sys.executable)

    print('② 打包命令：')
    for line in ('python -m build',
                 'pip install -e .',
                 'cd vscode-minibt && npx @vscode/vsce package',
                 'mkdocs build -f minibt_docs/mkdocs.yml'):
        print('   ', line)

    print('③ 产物检查：dist/*.whl、vscode-minibt/minibt-charts-*.vsix')

    print('④ FAQ（高频三问）：')
    print('   - 图表只有坐标轴/一片黑：watermark 返回活对象把渲染进程卡死（见 changelog 0.1.4）')
    print("   - ModuleNotFoundError: 'rich'：minibt.pythonPath 指错解释器")
    print('   - 原生窗口起不来：脚本缺 __main__ 保护 → 用浏览器版')


if __name__ == '__main__':
    main()
