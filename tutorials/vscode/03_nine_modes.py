"""12.3 · 九种图表模式速查（3 引擎 × 3 场景）

演示要点
--------
| 场景 / 引擎 | Bokeh | pylightcharts 原生 | pylightcharts 网页 |
| --- | --- | --- | --- |
| 回测 | `Bt().run(gui=Gui.Bokeh)` | `gui=Gui.Pylightcharts` | `gui=Gui.PylightchartsWeb` |
| 回放 | `Bt(replay=True).run(gui=Gui.Bokeh)` | 同上加 `replay=True` | 同上加 `replay=True` |
| 实时 | `Bt(live=True).addTqapi(...).run(gui=Gui.Bokeh)` | 同上 | 同上 |

对应示例在 `tutorials/plots/01..09_*`（每个模式一个文件），外加
`10_live_bokeh_mock.py`（**无需账号**的本地 mock 实时）。

运行：``python tutorials/vscode/03_nine_modes.py``
文档：``minibt_docs/docs/minibt_ide/12.3_nine_modes.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *                                  # noqa: E402,F403

ENGINES = (('Bokeh', 'Gui.Bokeh', 'bokeh'),
           ('pylightcharts 原生', 'Gui.Pylightcharts', 'native'),
           ('pylightcharts 网页', 'Gui.PylightchartsWeb', 'web'))
SCENES = (('回测', '{cls}().run({gui})'),
          ('回放', '{cls}(replay=True).run({gui})'),
          ('实时', '{cls}(live=True).addTqapi(tq_auth(...)).run({gui})'))


def main(gui=None):
    print('① Gui 枚举:', [getattr(Gui, n) for n in
                          ('Bokeh', 'Pylightcharts', 'PylightchartsWeb')])

    print('② 九种组合（把 {cls}/{gui} 代进去即可）：')
    for scene, template in SCENES:
        for label, gui_value, _key in ENGINES:
            line = template.format(cls='Bt', gui=gui_value)
            print(f'   {scene:4s} × {label:18s} → {line}')

    print('③ 对应示例：tutorials/plots/01..09（回测/回放/实时 × 三引擎）')
    print('   无账号演示实时：tutorials/plots/10_live_bokeh_mock.py（MockLiveFeed）')
    print('④ VS Code 扩展会强制 pylightcharts_web（见 12.2）')


if __name__ == '__main__':
    main()
