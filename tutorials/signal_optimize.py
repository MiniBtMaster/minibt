"""
test_optimize.py — signal_backtest 参数优化示例

使用 OptimizeConfig dataclass 统一管理优化参数，
覆盖网格搜索、Optuna贝叶斯优化、单目标、多目标、带权重等场景。
"""
from minibt import *

kline = LocalDatas.l2601_60.kline


# ---- 定义参数化指标 ----
class MyMA(BtIndicator):
    lines = ['ma1','ma2','long_signal', 'short_signal', 'exitlong_signal', 'exitshort_signal']
    params = dict(length1=10, length2=20)
    overlap=dict(ma1=True,ma2=True)

    def next(self):
        ma1 = self.close.sma(self.params.length1)
        ma2 = self.close.sma(self.params.length2)
        long_signal = ma1.cross_up(ma2)
        short_signal = ma1.cross_down(ma2)
        return ma1,ma2,long_signal, short_signal, short_signal, long_signal


ind = MyMA(kline)


print("=" * 60)
print("【示例 1】网格搜索 - 单目标（最大化夏普）")
print("=" * 60)
config1 = OptimizeConfig(
    params={'length1': (5, 30, 2), 'length2': (30, 60, 2)},
    target='sharpe',
    method='grid',
    n_jobs=4,
    output_dir='./results',
)
# result1 = ind.signal_backtest(optimize=config1)
# result1.pprint()

print("\n" + "=" * 60)
print("【示例 2】网格搜索 - 单目标（最小化最大回撤）")
print("=" * 60)
config2 = OptimizeConfig(
    params={'length1': (5, 30, 2), 'length2': (30, 60, 2)},
    target='max_drawdown',
    weights=-1.0,                          # 负值 = 最小化
    method='grid',
    n_jobs=4,
    output_dir='./results',
)
# result2 = ind.signal_backtest(optimize=config2)
# result2.pprint()

print("\n" + "=" * 60)
print("【示例 3】网格搜索 - 多目标（最小化回撤 + 最大化夏普，等权重）")
print("=" * 60)
config3 = OptimizeConfig(
    params={'length1': (5, 30, 2), 'length2': (30, 60, 2)},
    target=['max_drawdown', 'sharpe'],
    weights=(-1.0, 1.0),                  # 回撤最小化，夏普最大化
    method='grid',
    n_jobs=4,
    output_dir='./results',
)
# result3 = ind.signal_backtest(optimize=config3)
# result3.pprint()

print("\n" + "=" * 60)
print("【示例 4】网格搜索 - 多目标（夏普权重更高）")
print("=" * 60)
config4 = OptimizeConfig(
    params={'length1': (5, 30, 2), 'length2': (30, 60, 2)},
    target=['max_drawdown', 'sharpe', 'win_rate'],
    weights=(-1.0, 3.0, 1.5),             # 夏普权重 3.0（更重要），回撤 -1.0，胜率 1.5
    method='grid',
    n_jobs=4,
    output_dir='./results',
)
# result4 = ind.signal_backtest(optimize=config4)
# result4.pprint()

print("\n" + "=" * 60)
print("【示例 5】Optuna 贝叶斯优化 - 单目标")
print("=" * 60)
config5 = OptimizeConfig(
    params={'length1': (5, 30), 'length2': (30, 60)},
    target='calmar',
    method='optuna',
    config={'n_trials': 100, 'sampler': 'TPESampler'},
    n_jobs=4,
)
# result5 = ind.signal_backtest(optimize=config5)
# result5.pprint()
# result5.plot_optuna()

print("\n" + "=" * 60)
print("【示例 6】Optuna 贝叶斯优化 - 多目标最小化风险")
print("=" * 60)
config6 = OptimizeConfig(
    params={'length1': (5, 30), 'length2': (30, 60)},
    target=['max_drawdown', 'volatility', 'cvar'],
    weights=(-1.0, -1.0, -1.0),           # 全部最小化（风险越低越好）
    method='optuna',
    config={'n_trials': 100, 'sampler': 'NSGAIISampler'},
    n_jobs=4,
)
# result6 = ind.signal_backtest(optimize=config6)
# result6.pprint()
# result6.plot_optuna()

print("\n" + "=" * 60)
print("【示例 7】Optuna 贝叶斯优化 - 多目标（收益+风险平衡，带 CSV 导出）")
print("=" * 60)
config7 = OptimizeConfig(
    params={'length1': (5, 50), 'length2': (20, 80)},
    target=['sharpe', 'sortino', 'calmar', 'max_drawdown'],
    weights=(2.0, 1.5, 1.0, -1.0),        # 收益类最大化，风险类最小化
    method='optuna',
    config={'n_trials': 200, 'sampler': 'TPESampler', 'pruner': 'HyperbandPruner'},
    n_jobs=-1,                             # 使用全部 CPU 核心
    output_dir='./results',
)
# result7 = ind.signal_backtest(optimize=config7)
# result7.pprint()
# result7.plot_optuna()

print("\n" + "=" * 60)
print("【示例 8】最小化波动率（稳健型策略偏好）")
print("=" * 60)
config8 = OptimizeConfig(
    params={'length1': (5, 30), 'length2': (30, 60)},
    target='volatility',
    weights=-2.0,                          # 负值 + 高权重 = 强烈偏好低波动
    method='optuna',
    config={'n_trials': 100},
    n_jobs=2,
)
# result8 = ind.signal_backtest(optimize=config8)
# result8.pprint()

print("\n" + "=" * 60)
print("【示例 9】最小化连续亏损次数（稳健性优化）")
print("=" * 60)
config9 = OptimizeConfig(
    params={'length1': (5, 30), 'length2': (30, 60)},
    target='consecutive_losses',           # 连续亏损天数
    weights=-1.0,                          # 越小越好
    method='optuna',
    config={'n_trials': 80},
    n_jobs=2,
)
# result9 = ind.signal_backtest(optimize=config9)
# result9.pprint()

print("\n" + "=" * 60)
print("【示例 10】最大化利润因子 + 胜率（盈利效率优化）")
print("=" * 60)
config10 = OptimizeConfig(
    params={'length1': (5, 40), 'length2': (20, 80)},
    target=['profit_factor', 'win_rate'],
    weights=(2.0, 1.0),                    # 利润因子权重 2x
    method='optuna',
    config={'n_trials': 150},
    n_jobs=4,
)
# result10 = ind.signal_backtest(optimize=config10)
# result10.pprint()

print("\n" + "=" * 60)
print("【示例 11】不设权重（默认最大化所有目标 + 等权重 1.0）")
print("=" * 60)
config11 = OptimizeConfig(
    params={'length1': (5, 30), 'length2': (30, 60)},
    target=['sharpe', 'calmar'],
    # weights 不设置 → 默认 (1.0, 1.0)，最大化两个目标
    method='optuna',
    config={'n_trials': 100, 'sampler': 'NSGAIISampler'},
    n_jobs=4,
)
result11 = ind.signal_backtest(optimize=config11)
result11.pprint()
result11.plot_optuna()

print("\n" + "=" * 60)
print("所有示例定义完毕。取消注释即可运行对应示例。")
print("=" * 60)
