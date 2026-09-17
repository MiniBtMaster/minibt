from __future__ import annotations

from .base import tobtind
from ..utils import TYPE_CHECKING#, np, LineStyle, LineDash

if TYPE_CHECKING:
    from typing_ import *
    from .core import *
    
class Pine:
    
    _perfixes: str = "pine_"
    _df: IndFrame | IndSeries

    def __init__(self, data):
        self._df = data
    
    @tobtind(overlap=False, lib="pine")
    def normalize(self, lo=0.0, hi=1.0, **kwargs) -> IndSeries:
        """MLExtensions normalize: 扩展窗口历史 min/max 归一化
        所需字段：close"""
        ...
        
    @tobtind(overlap=False, lib="pine")
    def cci(self, n: int = 10,**kwargs) -> IndSeries:
        """Pine ta.cci: (src - sma) / (0.015 * mean|src - sma|)
        所需字段：close"""
        ...
        
    @tobtind(overlap=False, lib="pine")
    def wavetrend(self,n1=10, n2=11,talib: bool | None = None, **kwargs) -> IndSeries:
        """Pine ta.wavetrend: 波形趋势
        所需字段：high,low,close"""
        ...
        
    @tobtind(overlap=True, lib="pine")
    def rma(self, n=20,**kwargs) -> IndSeries:
        """Pine ta.rma: alpha=1/n, 以最初 n 个非NaN值的 SMA 播种, 之后递归
        所需字段：close"""
        ...
        
    @tobtind(overlap=False, lib="pine")
    def adx_wilder(self, n=20,**kwargs) -> IndSeries:
        """MLExtensions 风格的 Wilder ADX (累加器平滑 + rma)
        所需字段：high,low,close"""
        ...
    
    @tobtind(overlap=False, lib="pine")
    def barssince(self,**kwargs) -> IndSeries:
        """Pine ta.barssince: 距上次 cond 为 True 的 bar 数, 从未发生为 NaN
        所需字段：close"""
        ...
        
    @tobtind(overlap=False, lib="pine")
    def rsi(self, n=20,**kwargs) -> IndSeries:
        """Pine ta.rsi: Wilder 平滑 RSI
        所需字段：close"""
        ...
        
    @tobtind(overlap=True, lib="pine")
    def ema(self, n=20,**kwargs) -> IndSeries:
        """Pine ta.ema: Wilder 平滑 EMA
        所需字段：close"""
        ...
        