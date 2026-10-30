"""12.2 · 让 `btplot` 在 VS Code 里显示

演示要点
--------
| 环节 | 说明 |
| --- | --- |
| 入口 | 编辑器标题栏「运行」按钮 / `Ctrl+Alt+M` |
| 引擎 | 扩展把 `gui` 强制成 **`pylightcharts_web`**（网页版，能嵌 webview） |
| 展示 | 活图用 **iframe + SSE**；静态页用快照页签 |
| 解释器 | `minibt.pythonPath` 必须指向装了 minibt 的那个 |

`runner/vscode_runner.py` 会接管：

```python
minibt.btplot._resolve_btplot_gui   # → 'pylightcharts_web'
RealtimeChart.__init__              # → browser=True, live=True
```

运行：``python tutorials/vscode/02_btplot_in_vscode.py``
文档：``minibt_docs/docs/minibt_ide/12.2_btplot.md``
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *                                  # noqa: E402,F403
from minibt.btplot import btplot                      # noqa: E402
from minibt.utils import main_guard_missing           # noqa: E402


def main(gui=None):
    # ① 环境自检（扩展起不来时先看这三行）
    print('① 解释器:', sys.executable)
    for module in ('minibt', 'pylightcharts', 'rich'):
        try:
            __import__(module)
            print(f'   {module}: OK')
        except Exception as error:                   # noqa: BLE001
            print(f'   {module}: FAIL {type(error).__name__} {error}')

    # ② btplot 的参数（扩展只改 gui/display，别的照旧）
    print('② btplot', str(inspect.signature(btplot))[:120], '…')
    print('   扩展用的参数：gui="pylightcharts_web"、display="external"')

    # ③ 入口脚本保护（原生窗口 spawn 需要）
    print('③ 本脚本缺 __main__ 保护吗:',
          main_guard_missing(), '（True 时 btplot 会自动换浏览器版）')

    # ④ 不真的出图（本页只做自检）
    print('④ 真看图：python test.py（或对任意指标 ind.btplot()）')


if __name__ == '__main__':
    main()
