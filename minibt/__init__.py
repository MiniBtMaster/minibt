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

版本信息: v1.0.0
许可证: MIT License
项目主页: https://github.com/MiniBtMaster/minibt (示例地址)
"""


# ------------------------------
# 元数据定义
# ------------------------------
__author__ = "owen"
__copyright__ = "Copyright (c) 2024 minibt开发团队"
__license__ = "MIT"
__version__ = "1.0.0"
__version_info__ = (1, 0, 0)  # 版本元组，便于程序内版本判断
__description__ = "一站式量化交易策略开发库，简化从策略搭建到实盘交易的全流程"


# ------------------------------
# 核心模块导入（按功能分组）
# ------------------------------

# 1. 核心框架（回测引擎、策略基类）
from .bt import Bt
from .strategy.strategy import Strategy
from .core import *  # 核心工具类（内部依赖）

# 2. 配置与常量
from .constant import *
from .utils import (
    Config,          # 策略配置类
    FILED,           # 数据字段常量
    OptunaConfig     # 参数优化配置
)

# 3. 数据处理
from .data.utils import LocalDatas  # 本地数据源管理
from .sqlitedata import MySqlite    # 本地数据库工具

# 4. 指标系统
from .indicators import (
    BtIndicator,     # 指标计算入口类
    BtData,          # 带指标计算能力的数据集
    series, dataframe,  # 数据类型定义
    TuLip, PandasTa, TaLib,  # 第三方指标库封装
    StopMode, Stop,       # 止损相关类
    IndicatorClass, CoreIndicators  # 指标基类与核心指标
)

# 5. 工具与类型
from .utils import (
    np, pd,          # 导出numpy和pandas（方便用户直接使用）
    tq_auth, tq_account,  # TQ实盘认证工具
    Multiply,        # 数值计算工具
    # 可视化样式配置
    LineDash, Colors, Markers,
    CandleStyle, LineStyle, SignalStyle, SpanStyle, PlotInfo, MaType
)

# 6. 止损模块
import minibt.stop.stop as BtStop

# 7. 强化学习模块
from .elegantrl.agents import Agents, BestAgents

# 8. UI界面模块


def miniqt(): ...  # 后续完善文档字符串


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
    'LocalDatas', 'MySqlite', 'BtData',
    # 指标
    'BtIndicator', 'TuLip', 'PandasTa', 'TaLib',
    'StopMode', 'Stop', 'IndicatorClass', 'CoreIndicators',
    # 工具
    'np', 'pd', 'tq_auth', 'tq_account', 'Multiply', 'BtStop',
    # 可视化样式
    'LineDash', 'Colors', 'Markers',
    'CandleStyle', 'LineStyle', 'SignalStyle', 'SpanStyle', 'PlotInfo', 'MaType',
    # 强化学习
    'Agents', 'BestAgents',
    # UI
    'miniqt',
    # 类型
    'series', 'dataframe'
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

# 初始化本地数据源（rewrite=True表示允许覆盖旧数据缓存）
LocalDatas.rewrite(True)


def miniqt():
    """
    ## 开发中，不可用
    启动minibt的可视化交互界面（基于PyQt5与Fluent Widgets）

    功能:
        - 策略代码编辑与管理
        - 回测结果可视化分析
        - 实时行情监控
        - 策略参数配置与优化

    依赖:
        - PyQt5: 图形界面基础库
        - qfluentwidgets: 现代化UI组件库

    使用说明:
        直接调用miniqt()即可启动界面，支持多语言切换（通过配置文件设置）
    """
    import os
    import sys

    from PyQt5.QtCore import Qt, QTranslator
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QApplication
    from qfluentwidgets import FluentTranslator

    # 导入本地UI配置与主窗口
    from .miniqt.app.common.config import cfg
    from .miniqt.app.view.main_window import MainWindow

    # ------------------------------
    # 高DPI适配配置
    # ------------------------------
    if cfg.get(cfg.dpiScale) == "Auto":
        # 自动DPI缩放（适合多显示器场景）
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    else:
        # 手动设置缩放比例（用户指定）
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
        os.environ["QT_SCALE_FACTOR"] = str(cfg.get(cfg.dpiScale))
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)  # 启用高DPI图片

    # ------------------------------
    # 应用初始化
    # ------------------------------
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)  # 避免控件层级问题

    # ------------------------------
    # 国际化配置（多语言支持）
    # ------------------------------
    locale = cfg.get(cfg.language).value  # 从配置获取语言
    translator = FluentTranslator(locale)  # Fluent组件翻译
    galleryTranslator = QTranslator()
    galleryTranslator.load(locale, "gallery", ".", ":/gallery/i18n")  # 本地UI翻译
    app.installTranslator(translator)
    app.installTranslator(galleryTranslator)

    # ------------------------------
    # 启动主窗口
    # ------------------------------
    w = MainWindow()
    w.show()
    w.setMicaEffectEnabled(True)  # 启用云母特效（Windows 11+）

    # 进入事件循环
    app.exec_()
