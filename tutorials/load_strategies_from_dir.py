"""
MiniBT 从文件/目录加载策略 — 完整示例
======================================
演示 `Bt.addstrategy()` 的多种调用方式，特别是通过字符串路径从 .py 文件
或目录中自动发现并加载 Strategy 子类。

核心原理（见 minibt/bt.py _load_strategies）：
  - 传入字符串时，框架自动调用 _load_strategies(path) 递归发现 Strategy 子类
  - 支持四种路径格式：目录（扫描 *.py）、.py 文件、纯模块名（自动补 .py）、
    点号分隔的包路径（如 'tutorials.strategy.cci' → 自动还原为文件路径）
  - 每个 .py 文件可包含任意数量的 Strategy 子类（全部自动发现）

前提条件：
    运行此脚本前，确保当前工作目录下存在 `cci.py`（含 CCIStrategy）和
    `cmo.py`（含 CMOStrategy）两个策略文件。
"""
from minibt import *


if __name__ == "__main__":
    # ==================================================================
    # 方式一：模块名字符串（当前目录，省略 .py 后缀）
    #
    # addstrategy('cci') → 在当前目录找 cci.py → 导入 CCIStrategy
    # addstrategy('cmo') → 在当前目录找 cmo.py → 导入 CMOStrategy
    #
    # 框架内部：path.with_suffix('.py') 自动补全，然后 importlib.import_module
    # 适用：策略文件与运行脚本在同一工作目录下，最简单快捷。
    # ==================================================================

    # Bt().addstrategy('cci', 'cmo').run(gui=Gui.LightChart)

    # ==================================================================
    # 方式二：显式 .py 文件路径
    #
    # 直接传入完整的 .py 文件路径，框架检测到 path.suffix == '.py' 后，
    # 通过 spec_from_file_location 直接加载该文件。
    #
    # 适用：策略文件在任意位置，不想修改 sys.path。
    # ==================================================================

    # Bt().addstrategy('./cci.py', './cmo.py').run(gui=Gui.LightChart)
    # Bt().addstrategy('/path/to/my_strategies/cci.py').run()

    # ==================================================================
    # 方式三：加载整个目录（批量导入）
    #
    # 传入一个文件夹路径，框架检测到 path.is_dir() == True 后，
    # 会扫描该目录下所有 *.py 文件（排除 __init__.py），自动导入其中的所有 Strategy 子类。
    #
    # 适用：策略文件分散在一个目录中，想要一次性全部加载。
    # 注意：目录下每个 .py 文件若包含多个 Strategy 子类，全部都会被添加。
    # ==================================================================

    # Bt().addstrategy('.').run(gui=Gui.LightChart)            # 加载当前目录所有策略
    # Bt().addstrategy('./my_strategies').run()                # 加载子目录所有策略

    # ==================================================================
    # 方式四：Python 包导入路径（点号分隔）
    #
    # 使用标准的 Python 模块导入语法，如 'tutorials.strategy.cci'。
    # 框架自动将点号路径还原为文件系统路径（点→斜杠，末段补 .py）：
    #   'tutorials.strategy.cci'  →  'tutorials/strategy/cci.py'
    #
    # 如果还原后的文件不存在，则尝试 importlib.import_module() 直接导入。
    #
    # 适用：策略组织为标准 Python 包结构，当前工作目录即项目根目录。
    # ==================================================================

    bt = Bt().addstrategy('strategy/cci.py', 'strategy/cmo.py').run(gui=Gui.LightChart)

    # ==================================================================
    # 方式五：混合传入（Strategy 类 + 字符串）
    #
    # addstrategy 同时支持 Strategy 子类和字符串路径混用：
    #   - 类是 issubclass(arg, Strategy) → 直接追加
    #   - 字符串是 isinstance(arg, str) → 调 _load_strategies 自动发现
    #
    # 适用：部分策略内联定义，部分从外部文件加载。
    # ==================================================================

    # from cci import CCIStrategy                 # 直接导入
    # Bt().addstrategy(CCIStrategy, 'cmo').run()  # 类 + 字符串混用

    # ==================================================================
    # 方式六：带参数传递（kwargs）
    #
    # addstrategy 的 **kwargs 会通过 setattr 设置到每个策略类上。
    # 无论是直接传入 Strategy 类还是字符串路径，参数均生效。
    #
    # 适用：同一策略类需要不同参数组合运行多份实例时。
    # ==================================================================

    # Bt().addstrategy('cci', params=dict(CCI_PERIOD=14, CCI_UPPER=120)).run()

    # ==================================================================
    # 方式七：实盘模式 — 从文件加载策略
    #
    # 结合 Bt(live=True) 和字符串路径加载，实盘运行从外部文件导入的策略。
    # ==================================================================

    # bt = Bt(live=True)
    # bt.addstrategy('cci', 'cmo')
    # bt.addTqapi(tq_auth=tq_auth(
    #     user_name="天勤账号", password="天勤密码"
    # ))
    # bt.run()                                 # 图表模式
    # bt.run(isplot=False)                     # 后台串行
    # bt.run(isplot=False, run_parallel=True)  # 并行模式

    # ==================================================================
    # 注意事项：
    #   1. 字符串加载时，框架自动发现每个 .py 文件中所有 Strategy 子类，
    #      而非固定取第一个。若一个文件包含多个策略类，全部都会被添加。
    #   2. 若模块导入失败（ModuleNotFoundError），框架自动降级使用
    #      spec_from_file_location 从文件路径直接加载，兼容性很好。
    #   3. 目录加载排除 __init__.py，避免重复导入包自身。
    #   4. 回测时搭配 gui=Gui.LightChart 启用图形界面。
    #   5. 实盘时需确保天勤账号密码正确，且有对应合约的行情权限。
    # ==================================================================
