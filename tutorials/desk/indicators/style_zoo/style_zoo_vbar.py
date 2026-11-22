from minibt import *


class Vbar(BtIndicator):
    linestyle=dict(rsi=LineStyle(line_dash=LineDash.vbar,vbar_base=50.,vbar_up_color=Colors.red,vbar_down_color=Colors.green))

    def next(self):
        self.lines.rsi = self.close.rsi()