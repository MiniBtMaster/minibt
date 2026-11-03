"""01 · `btplot(gui=Gui.Desk)`：一行把指标画进 desk 本地图表

```bash
python tutorials/desk/gui/01_btplot_style.py
```

跑起来会发生什么
----------------
1. 取内置本地数据 `LocalDatas.l2609_60`（DCE.l2609，1 分钟），
2. 算一条均线 + 上下轨，
3. `btplot(gui=Gui.Desk)` → desk 打开**本地图表**，把这条线「加到图表」。

样式（`linestyle` / `overlap`）就写在指标类里，desk 会按 PlotInfo 上色 ✓。
"""
from minibt import BtIndicator, Gui, LineDash, LineStyle, LocalDatas
import pandas as pd
import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)


from minibt import *                      # noqa: F401,F403


class MaQuick(BtIndicator):
    """最简指标：一条主图均线（`overlap=True`）+ 一条副图带宽。"""

    lines = ('ma', 'band')
    params = dict(length=20, k=2.0)

    #: 主图叠加（False = 独立副图）
    overlap = dict(ma=True, band=False)

    linestyle = dict(
        ma=LineStyle(line_color='#f6c343', line_width=2),
        band=LineStyle(line_color='#2196f3', line_width=1,
                       line_dash=LineDash.dashed),
    )

    #: 只画线、不显示左上角图例行（想看名字就删掉这一行）
    legend = dict(band=False)

    def next(self):
        close = pd.Series(self.close.values, dtype=float)
        ma = close.rolling(int(self.params.length)).mean()
        band = close.rolling(int(self.params.length)
                             ).std() * float(self.params.k)
        return ma.to_numpy(), band.to_numpy()


if __name__ == '__main__':
    kline = LocalDatas.l2609_60.kline
    # ★ 关键的一行：gui=Gui.Desk（等价 gui='desk'）
    MaQuick(kline).btplot(gui=Gui.Desk)
