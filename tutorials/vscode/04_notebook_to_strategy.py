"""12.4 · 从 notebook 到策略

演示要点
--------
| 场景 | `btplot` 的显示方式 |
| --- | --- |
| Jupyter / Notebook | `display='auto'` → **内联**（不阻塞 kernel） |
| 普通脚本 | `display='auto'` → 打开浏览器 / 原生窗口 |
| 强制 | `display='inline'` / `'external'` |

**转成 `.py` 时最重要的一条**：加 `if __name__ == '__main__':`

Windows / macOS 用 **spawn** 启动渲染子进程，会**重新执行入口脚本**；
没有 main 保护，原生窗口永远起不来（`WindowStartError` / 卡住）。
`btplot` 检测到这种情况会自动换成浏览器版。

运行：``python tutorials/vscode/04_notebook_to_strategy.py``
文档：``minibt_docs/docs/minibt_ide/12.4_notebook.md``
"""

import os
import pathlib
import sys
import tempfile
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt.utils import main_guard_missing           # noqa: E402


def _check(source: str, name: str) -> bool:
    """把源码写进临时文件，再问 main_guard_missing 有没有保护。"""
    path = pathlib.Path(tempfile.gettempdir()) / name
    path.write_text(source, encoding='utf-8')
    return main_guard_missing(types.SimpleNamespace(__file__=str(path)))


def main(gui=None):
    # ① 没有 main 保护
    no_guard = 'from minibt import *\nLocalDatas.test.kline.macd().btplot()\n'
    print('① 没有 __main__ 保护 → 缺保护吗:', _check(no_guard, '_noguard.py'))

    # ② 有 main 保护
    guarded = ('from minibt import *\n\n'
               'def main():\n'
               '    LocalDatas.test.kline.macd().btplot()\n\n'
               "if __name__ == '__main__':\n    main()\n")
    print('② 有 __main__ 保护   → 缺保护吗:', _check(guarded, '_guard.py'))

    # ③ notebook → 脚本 的拆分建议
    print('③ 拆分建议：数据（get_kline）→ 指标（__init__）→ 交易（next）')
    print('④ notebook 里 btplot 用 display="auto" 内联；脚本里可显式 "external"')


if __name__ == '__main__':
    main()
