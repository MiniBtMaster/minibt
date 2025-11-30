# -*- coding: utf-8 -*-
"""
minibt: 一站式量化交易策略开发库
=====================================
minibt 是一个专注于简化量化交易全流程的开发库，支持从策略编写、指标计算、
回测分析到实盘对接的完整链路，提供极简的API设计和丰富的工具链，助力快速落地量化想法。

核心功能:
- 内置丰富金融指标（TA-Lib、Pandas TA等），支持自定义指标扩展
- 高效回测引擎，支持多维度性能分析与参数优化
- 无缝对接实盘接口（如TQSDK），策略一键切换回测/实盘模式
- 集成可视化工具（Bokeh）与UI界面（PyQt），简化策略调试与分析

版本信息: v1.1.0
许可证: MIT License
GitHub仓库: https://github.com/MiniBtMaster/minibt
PyPI仓库: https://pypi.org/project/minibt/
项目教程：https://www.minibt.cn
联系邮箱：407841129@qq.com
"""
from .logger import LogLevel
from .elegantrl.agents import Agents, BestAgents
from .stop import BtStop
from .bt import Bt
from .strategy.strategy import Strategy
from .constant import *
from .utils import (
    Config,          # 策略配置类
    FILED,           # 数据字段常量
    OptunaConfig,    # 参数优化配置
    tq_auth,
    tq_account,
    Multiply,
    CandleStyle,
    LineStyle,
    SignalStyle,
    SpanStyle,
    PlotInfo,
    MaType,
    SignalLabel,
    pd,
    np
)
from .data.utils import LocalDatas  # 本地数据源管理
from .indicators import (
    BtIndicator,     # 指标计算入口类
    KLine,          # 带指标计算能力的数据集
    IndSeries, IndFrame,  # 数据类型定义
    PandasTa, TaLib,  # 第三方指标库封装
    StopMode, Stop,       # 止损相关类
    IndicatorClass, CoreIndicators,  # 指标基类与核心指标

)

__author__ = "owen"
__copyright__ = "Copyright (c) 2025 minibt开发团队"
__license__ = "MIT"
__version__ = "1.1.0"
__version_info__ = (1, 1, 0)
__description__ = "一站式量化交易策略开发库，简化从策略搭建到实盘交易的全流程"


# ------------------------------
# 公共接口导出（__all__定义）
# 仅暴露需要用户直接使用的类/函数/常量，隐藏内部实现
# ------------------------------
__all__ = [
    # 核心框架
    'Bt', 'Strategy',
    # 配置
    'Config', 'OptunaConfig', 'FILED',
    # 数据
    'LocalDatas', 'KLine',
    # 指标，只保留常用指标
    'BtIndicator', 'PandasTa', 'TaLib',
    'StopMode', 'Stop', 'IndicatorClass', 'CoreIndicators',
    # 工具
    'np', 'pd', 'tq_auth', 'tq_account', 'Multiply', 'BtStop',
    # 可视化样式
    'LineDash', 'Colors', 'Markers',
    'CandleStyle', 'LineStyle', 'SignalStyle', 'SpanStyle', 'PlotInfo', 'MaType', "SignalLabel",
    # 强化学习
    'Agents', 'BestAgents',
    # 类型
    'IndSeries', 'IndFrame', 'IndSeries', 'IndFrame',
    # 日志相关
    'LogLevel'
]


# ------------------------------
# 初始化逻辑
# ------------------------------

def _AnalysisIndicators_run(self, *args: list[pd.DataFrame], isplot=True, isreport: bool = False, **kwargs):
    """
    为DataFrame扩展的策略运行方法，支持直接基于DataFrame启动回测

    参数:
        self: pd.DataFrame - 作为主数据源的DataFrame
        *args: list[pd.DataFrame] - 额外数据源（可选）
        isplot: bool - 是否生成可视化图表（默认True）
        isreport: bool - 是否生成回测报告（默认False）
        **kwargs: 
            live: bool - 是否启用实盘模式（默认False）
            其他参数传递给Bt.run()

    返回:
        回测结果对象（包含收益、指标等信息）
    """
    live = kwargs.get('live', False)
    # 初始化回测引擎（根据live参数切换回测/实盘模式）
    bt = Bt(auto=live, live=live, quick_live=dict(live=live))
    # 过滤有效数据源（非空DataFrame）
    args = [self, *(arg for arg in args if isinstance(arg,
                    pd.DataFrame) and not arg.empty)]
    bt.adddata(*args)  # 添加数据源
    # 启动回测/实盘
    return bt.run(
        isplot=isplot,
        isreport=isreport,
        print_account=False,
        quick_start=True,
        quick_live=live,
        **kwargs
    )


# 为pandas.DataFrame动态添加run方法（方便用户直接调用）
setattr(pd.DataFrame, 'run', _AnalysisIndicators_run)

# 初始化本地数据源
LocalDatas.rewrite(True)
