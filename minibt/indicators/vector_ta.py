"""**vta** 指标库（第三方库，**可选依赖** ✓）

* 入口：`kline.vta.<指标名>(...)`（前缀 `vta_`）
* 数据源：调用它的 IndFrame 自己（`prices`→`close`、`high/low/open/volume`）
* 共 **209 个指标**；不支持的成员在 `NON_KLINE_INDICATORS` 里（desk 不显示）
* 生成：`scripts/gen_ext_libs.py`（**别手改本文件** ✓）
* docstring：`scripts/gen_ext_lib_docs.py` + `scripts/ext_lib_docs.json`

安装：`py -3.12 -m pip install vta`
"""

from __future__ import annotations

from .base import tobtind
from ..signals import Compare, Threshold
from ..utils import Colors, LineDash, LineStyle
from ..utils import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_ import *
    from .core import *

#: 全部指标名（`batch()` / 文档用 ✓）
_INDICATOR_NAMES = ('absolute_strength_index_oscillator', 'accumulation_swing_index', 'acosc', 'ad', 'adaptive_macd', 'adaptive_momentum_oscillator', 'adosc', 'advance_decline_line', 'adx', 'adxr', 'alphatrend', 'ao', 'apo', 'aroon', 'aroonosc', 'aso', 'atr', 'atr_percentile', 'avsl', 'bollinger_bands', 'bop', 'buff_averages', 'bull_power_vs_bear_power', 'cci', 'cci_cycle', 'cfo', 'cg', 'chandelier_exit', 'cmo', 'corrected_moving_average', 'correl_hl', 'cvi', 'cwma', 'dec_osc', 'decycler', 'dema', 'demand_index', 'di', 'didi_index', 'directional_imbalance_index', 'disparity_index', 'dm', 'dma', 'donchian', 'donchian_channel_width', 'dpo', 'dual_ulcer_index', 'dvdiqqe', 'dx', 'dynamic_momentum_index', 'edcf', 'efi', 'ehlers_adaptive_cg', 'ehlers_autocorrelation_periodogram', 'ehlers_detrending_filter', 'ehlers_ecema', 'ehlers_fm_demodulator', 'ehlers_kama', 'ehlers_linear_extrapolation_predictor', 'ehlers_pma', 'ehlers_smoothed_adaptive_momentum', 'ehlers_undersampled_double_moving_average', 'ehma', 'ema', 'emv', 'epma', 'er', 'eri', 'ewma_volatility', 'fisher', 'fosc', 'fractal_dimension_index', 'fwma', 'garman_klass_volatility', 'gatorosc', 'gmma_oscillator', 'gopalakrishnan_range_index', 'highpass', 'historical_volatility', 'historical_volatility_percentile', 'hma', 'impulse_macd', 'intraday_momentum_index', 'jma', 'jsa', 'kairi_relative_index', 'kama', 'kase_peak_oscillator_with_divergences', 'kaufmanstop', 'kdj', 'keltner', 'keltner_channel_width_oscillator', 'kst', 'kurtosis', 'kvo', 'l1_ehlers_phasor', 'l2_ehlers_signal_to_noise', 'linear_correlation_oscillator', 'linear_regression_intensity', 'linearreg_angle', 'linearreg_intercept', 'linearreg_slope', 'linreg', 'maaq', 'mab', 'macd_wave_signal_pro', 'market_meanness_index', 'marketefi', 'mass', 'mean_ad', 'medium_ad', 'medprice', 'midpoint', 'midprice', 'mod_god_mode', 'mom', 'momentum_ratio_oscillator', 'msw', 'mwdx', 'nadaraya_watson_envelope', 'nama', 'natr', 'nma', 'nonlinear_regression_zero_lag_moving_average', 'normalized_volume_true_range', 'nvi', 'obv', 'on_balance_volume_oscillator', 'ott', 'parkinson_volatility', 'percentile_nearest_rank', 'pivot', 'pma', 'possible_rsi', 'ppo', 'premier_rsi_oscillator', 'pretty_good_oscillator', 'price_density_market_noise', 'projection_oscillator', 'psychological_line', 'pvi', 'pwma', 'qqe', 'qstick', 'range_filter', 'rank_correlation_index', 'reflex', 'roc', 'rocp', 'rocr', 'rogers_satchell_volatility', 'rolling_skewness_kurtosis', 'rolling_z_score_trend', 'rsi', 'rsx', 'sar', 'sgf', 'sinwma', 'sma', 'smma', 'squeeze_momentum', 'sqwma', 'srwma', 'stc', 'stoch', 'stochastic_connors_rsi', 'stochastic_money_flow_index', 'stochf', 'supersmoother', 'supersmoother_3_pole', 'supertrend', 'swma', 'tema', 'tilson', 'trend_continuation_factor', 'trend_direction_force_index', 'trend_follower', 'trend_trigger_factor', 'trendflex', 'trima', 'trix', 'tsf', 'tsi', 'ttm_squeeze', 'ttm_trend', 'twiggs_money_flow', 'ui', 'ultosc', 'var', 'velocity', 'velocity_acceleration_convergence_divergence_indicator', 'vertical_horizontal_filter', 'vlma', 'volatility_quality_index', 'volatility_ratio_adaptive_rsx', 'volume_weighted_rsi', 'volume_weighted_stochastic_rsi', 'volume_zone_oscillator', 'vosc', 'voss', 'vpt', 'wad', 'wclprice', 'wilders', 'willr', 'wma', 'zig_zag_channels', 'zlema', 'zscore')


class VectorTa:
    """## VectorTa —— vector-ta 指标库（209 个指标）

    vector-ta 是用 Rust 实现的向量化指标库，除了经典指标外还带一批较新的量化指标（Ehlers 类 / 波动率锥 / 回撤统计等）。

    ### 📘 **原库文档**
    - https://pypi.org/project/vector-ta/

    ### 入口与返回
    - 入口：`kline.vector_ta.<指标名>(...)`（前缀 `vector_ta_`）
    - 返回：`IndSeries`（单线）或 `IndFrame`（多线），索引与调用它的 K 线 / 指标对齐
    - 主图 / 副图：装饰器 `overlap=True` 的均线、通道类叠在主图，其余（振荡、量能、统计、形态）在副图

    ### 指标分类（共 209 个）
    **趋势（79）**：adaptive_macd、adx、adxr、alphatrend、aroon、aroonosc、avsl、buff_averages、cg、chandelier_exit、corrected_moving_average、cwma、decycler、dema、di、dm、dma、donchian …（共 79 个）
    **动量（62）**：absolute_strength_index_oscillator、acosc、adaptive_momentum_oscillator、ao、apo、aso、bop、bull_power_vs_bear_power、cci、cci_cycle、cfo、cmo、dec_osc、directional_imbalance_index、disparity_index、dpo、dvdiqqe、dynamic_momentum_index …（共 62 个）
    **波动率（21）**：atr、atr_percentile、bollinger_bands、cvi、donchian_channel_width、dual_ulcer_index、ewma_volatility、garman_klass_volatility、gopalakrishnan_range_index、historical_volatility、historical_volatility_percentile、keltner_channel_width_oscillator、mass、natr、normalized_volume_true_range、parkinson_volatility、rogers_satchell_volatility、ttm_squeeze …（共 21 个）
    **成交量（19）**：accumulation_swing_index、ad、adosc、demand_index、efi、emv、kvo、marketefi、mean_ad、medium_ad、nvi、obv、on_balance_volume_oscillator、pvi、twiggs_money_flow、volume_zone_oscillator、vosc、vpt …（共 19 个）
    **形态（1）**：zig_zag_channels
    **统计（19）**：correl_hl、didi_index、ehlers_autocorrelation_periodogram、ehlers_detrending_filter、er、fractal_dimension_index、kurtosis、l1_ehlers_phasor、l2_ehlers_signal_to_noise、linear_correlation_oscillator、linear_regression_intensity、market_meanness_index、msw、percentile_nearest_rank、price_density_market_noise、rank_correlation_index、rolling_skewness_kurtosis、rolling_z_score_trend …（共 19 个）
    **其他（8）**：advance_decline_line、ehlers_linear_extrapolation_predictor、highpass、medprice、midpoint、midprice、pivot、wclprice

    ### 使用说明
    1. 直接调用（返回框架内置指标，可直接画图 / 参与计算）：
    >>> rsi = self.data.rsi(period=14)      # 副图
    >>> ma = self.data.exponential_moving_average(length=20)  # 主图叠加
    2. 取结果：
    >>> rsi.new           # 最新一根的值
    >>> rsi.prev          # 上一根的值
    >>> rsi[-20:]         # 最近 20 根（支持切片）
    3. 策略里可直接当条件用：
    >>> if rsi.new < 30:  # 超卖区，可再叠加其它指标过滤

    ### 注意事项
    - 周期类参数按「K 线根数」计，传 0 / 负数会被原库拒绝；参数留空则回落到默认值
    - 需要两条序列的指标（相关、协整、比较类）要显式传 `real1=` / `b=` 等第二序列
    - 本文件的 docstring 由 `scripts/gen_ext_lib_docs.py` 生成，**别手改**（改 `scripts/ext_lib_docs.json` 再跑脚本 ✓）
    - `kernel` 参数只影响速度（`auto` / `scalar` / `avx2` / `avx512`），不影响数值结果
    - 可选依赖：没装本库时整个类自动消失，框架其余功能不受影响
    """
    _perfixes: str = "vta_"
    _df: IndFrame | IndSeries

    def __init__(self, data):
        self._df = data
    @tobtind(lib="vta", overlap=False, lines=['absolute_strength_index_oscillator_1', 'absolute_strength_index_oscillator_2', 'absolute_strength_index_oscillator_3'])
    def absolute_strength_index_oscillator(self, ema_length: int | None = None, signal_length: int | None = None, kernel: str | None = None, **kwargs) -> IndFrame:
        """绝对强度振荡器 · absolute_strength_index_oscillator（动量）
        ---------
            以快慢EMA差值衡量价格绝对强度，并与信号线比较。指标上穿信号线偏多、下穿偏空，
            可判断动量强弱。

        参数:
        ---------
            >>> ema_length (int): EMA 周期. 默认: None
            >>> signal_length (int): 信号线平滑周期. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 3 条线 — absolute_strength_index_oscillator_1, absolute_strength_index_oscillator_2, absolute_strength_index_oscillator_3

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.absolute_strength_index_oscillator(ema_length=None, signal_length=None, kernel=None)    # 副图
            >>> out.columns               # 线名: absolute_strength_index_oscillator_1, absolute_strength_index_oscillator_2, absolute_strength_index_oscillator_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.absolute_strength_index_oscillator(close, ema_length=None, signal_length=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['accumulation_swing_index'])
    def accumulation_swing_index(self, daily_limit: float = 10000.0, kernel: str | None = None, **kwargs) -> IndSeries:
        """累积摆动指标 · accumulation_swing_index（成交量）
        ---------
            用每日涨跌配合成交量累积的摆动指标。与价格出现背离时提示趋势动能衰竭，适合确认量价配合。

        参数:
        ---------
            >>> daily_limit (float): 阈值 / 目标值. 默认: 10000.0
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — accumulation_swing_index

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.accumulation_swing_index(daily_limit=10000.0, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.accumulation_swing_index(open, high, low, close, daily_limit=10000.0, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['acosc_1', 'acosc_2'])
    def acosc(self, kernel: str | None = None, **kwargs) -> IndFrame:
        """加速振荡指标 · acosc（动量）
        ---------
            衡量均线动量的加速度（AC）。上穿零轴表示动量加速转强，下穿转弱，属先行类动量指标。

        参数:
        ---------
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — acosc_1, acosc_2

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.acosc(kernel=None)    # 副图
            >>> out.columns               # 线名: acosc_1, acosc_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.acosc(high, low, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ad'])
    def ad(self, kernel: str | None = None, **kwargs) -> IndSeries:
        """累积派发线 · ad（成交量）
        ---------
            按收盘在日内区间的位置加权成交量并累加。数值上升说明资金吸筹，与价格背离常预示趋势反转。

        参数:
        ---------
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ad

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.ad(kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ad(high, low, close, volume, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['macd', 'signal', 'histogram'], linestyle={'histogram': LineStyle(line_dash=LineDash.vbar, vbar_base=0.0, vbar_up_color=Colors.bull_color, vbar_down_color=Colors.bear_color)})
    def adaptive_macd(self, length: int = 14, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9, kernel: str | None = None, **kwargs) -> IndFrame:
        """自适应MACD · adaptive_macd（趋势）
        ---------
            基于自适应均线的MACD，反应更灵敏。MACD上穿信号线偏多、下穿偏空，柱状图变化显示动量转向。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> fast_period (int): 快线周期. 默认: 12
            >>> slow_period (int): 慢线周期. 默认: 26
            >>> signal_period (int): 信号线平滑周期. 默认: 9
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 3 条线 — macd, signal, histogram

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.adaptive_macd(length=14, fast_period=12, slow_period=26, signal_period=9, kernel=None)    # 副图
            >>> out.columns               # 线名: macd, signal, histogram
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.adaptive_macd(close, length=14, fast_period=12, slow_period=26, signal_period=9, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['adaptive_momentum_oscillator_1', 'adaptive_momentum_oscillator_2'])
    def adaptive_momentum_oscillator(self, length: int | None = None, smoothing_length: int | None = None, **kwargs) -> IndFrame:
        """自适应动量振荡器 · adaptive_momentum_oscillator（动量）
        ---------
            按波动自适应调整周期的动量指标。上穿零轴或信号线偏多、下穿偏空，用于捕捉动能转折。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: None
            >>> smoothing_length (int): 计算周期（K 线根数）. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — adaptive_momentum_oscillator_1, adaptive_momentum_oscillator_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.adaptive_momentum_oscillator(length=None, smoothing_length=None)    # 副图
            >>> out.columns               # 线名: adaptive_momentum_oscillator_1, adaptive_momentum_oscillator_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.adaptive_momentum_oscillator(close, length=None, smoothing_length=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['adosc'])
    def adosc(self, short_period: int = 12, long_period: int = 26, kernel: str | None = None, **kwargs) -> IndSeries:
        """佳庆振荡指标 · adosc（成交量）
        ---------
            累积派发线的快慢EMA之差。正值放大显示资金流入加速，负值显示流出加速，可确认趋势方向。

        参数:
        ---------
            >>> short_period (int): 短周期. 默认: 12
            >>> long_period (int): 长周期. 默认: 26
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — adosc

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.adosc(short_period=12, long_period=26, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.adosc(high, low, close, volume, short_period=12, long_period=26, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['advance_decline_line'])
    def advance_decline_line(self, kernel: str | None = None, **kwargs) -> IndSeries:
        """涨跌线 · advance_decline_line（其他）
        ---------
            累计上涨家数减下跌家数的市场广度指标。与指数背离常预示大盘走弱或走强，用于研判整体市场。

        参数:
        ---------
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — advance_decline_line

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.advance_decline_line(kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.advance_decline_line(close, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['adx'])
    def adx(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """平均趋向指数 · adx（趋势）
        ---------
            衡量趋势强度而不辨方向。ADX高于25表示趋势明确，低于20多为震荡，可用于筛选顺势行情。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — adx

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.adx(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.adx(high, low, close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['adxr'])
    def adxr(self, period: int | None = None, kernel: str | None = None, **kwargs) -> IndSeries:
        """ADX评级 · adxr（趋势）
        ---------
            ADX与其前期值的平均，进一步平滑趋势强度。数值高且上行表示趋势稳固，回落表示趋势减弱。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — adxr

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.adxr(period=None, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.adxr(high, low, close, period=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['alphatrend_1', 'alphatrend_2'])
    def alphatrend(self, coeff: float = 1.0, period: int = 14, no_volume: bool = False, kernel: str | None = None, **kwargs) -> IndFrame:
        """Alpha趋势线 · alphatrend（趋势）
        ---------
            主图趋势跟踪线，结合价格与成交量给出多空轨道。价格在线上方偏多、下方偏空，
            可作追踪止损。

        参数:
        ---------
            >>> coeff (float): 系数. 默认: 1.0
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> no_volume (bool): 原库参数（默认值见签名）. 默认: False
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 2 条线 — alphatrend_1, alphatrend_2

        数据:
        ---------
            >>> open, high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.alphatrend(coeff=1.0, period=14, no_volume=False, kernel=None)    # 主图叠加
            >>> out.columns               # 线名: alphatrend_1, alphatrend_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.alphatrend(open, high, low, close, volume, coeff=1.0, period=14, no_volume=False, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ao'])
    def ao(self, short_period: int = 12, long_period: int = 26, kernel: str | None = None, **kwargs) -> IndSeries:
        """动量震荡指标 · ao（动量）
        ---------
            5与34周期均线之差。上穿零轴且柱体转正偏多，下穿偏空，用于衡量动量强弱与转折。

        参数:
        ---------
            >>> short_period (int): 短周期. 默认: 12
            >>> long_period (int): 长周期. 默认: 26
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ao

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.ao(short_period=12, long_period=26, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ao(high, low, short_period=12, long_period=26, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['apo'])
    def apo(self, short_period: int = 12, long_period: int = 26, kernel: str | None = None, **kwargs) -> IndSeries:
        """绝对价格振荡器 · apo（动量）
        ---------
            快慢EMA之差，反映价格动量方向。零轴上方偏多、下方偏空，数值扩大表示趋势加速。

        参数:
        ---------
            >>> short_period (int): 短周期. 默认: 12
            >>> long_period (int): 长周期. 默认: 26
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — apo

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.apo(short_period=12, long_period=26, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.apo(close, short_period=12, long_period=26, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['aroon_down', 'aroon_up'])
    def aroon(self, length: int = 25, kernel: str | None = None, **kwargs) -> IndFrame:
        """阿隆指标 · aroon（趋势）
        ---------
            以最高价与最低价出现的时间衡量趋势。上线在上为上升趋势、下线在上为下降趋势，
            接近100趋势强。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 25
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — aroon_down, aroon_up

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.aroon(length=25, kernel=None)    # 副图
            >>> out.columns               # 线名: aroon_down, aroon_up
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.aroon(high, low, length=25, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['aroonosc'])
    def aroonosc(self, length: int = 25, kernel: str | None = None, **kwargs) -> IndSeries:
        """阿隆振荡器 · aroonosc（趋势）
        ---------
            Aroon上线减下线。正值偏多、负值偏空，绝对值大小反映趋势形成的新鲜度与力度。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 25
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — aroonosc

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.aroonosc(length=25, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.aroonosc(high, low, length=25, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['aso_1', 'aso_2'])
    def aso(self, period: int | None = None, mode: str | None = None, kernel: str | None = None, **kwargs) -> IndFrame:
        """绝对强度振荡器 · aso（动量）
        ---------
            基于价格偏离均线的绝对强度构造的双线振荡器。上穿信号线偏多、下穿偏空，用于判断动能强弱。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: None
            >>> mode (str): 计算模式（原库枚举值）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — aso_1, aso_2

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.aso(period=None, mode=None, kernel=None)    # 副图
            >>> out.columns               # 线名: aso_1, aso_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.aso(open, high, low, close, period=None, mode=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['atr'])
    def atr(self, length: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """平均真实波幅 · atr（波动率）
        ---------
            衡量价格平均波动幅度。ATR升高表示波动加大，常用于设置止损距离、目标位与仓位规模。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — atr

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.atr(length=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.atr(high, low, close, length=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['atr_percentile'])
    def atr_percentile(self, atr_length: int = 10, percentile_length: int = 50, kernel: str | None = None, **kwargs) -> IndSeries:
        """ATR百分位 · atr_percentile（波动率）
        ---------
            当前ATR在历史区间中的百分位。处于高位说明波动极端，处于低位说明行情过度平静。

        参数:
        ---------
            >>> atr_length (int): ATR 计算周期. 默认: 10
            >>> percentile_length (int): 计算周期（K 线根数）. 默认: 50
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — atr_percentile

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.atr_percentile(atr_length=10, percentile_length=50, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.atr_percentile(high, low, close, atr_length=10, percentile_length=50, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['avsl'])
    def avsl(self, fast_period: int | None = None, slow_period: int | None = None, multiplier: float | None = None, kernel: str | None = None, **kwargs) -> IndSeries:
        """自适应波动率止损 · avsl（趋势）
        ---------
            主图止损线，随价格与波动率自适应移动。价格上穿转多、下穿转空，可作为追踪止损依据。

        参数:
        ---------
            >>> fast_period (int): 快线周期. 默认: None
            >>> slow_period (int): 慢线周期. 默认: None
            >>> multiplier (float): ATR / 标准差倍数（决定通道与止损宽度）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — avsl

        数据:
        ---------
            >>> low, close, volume

        使用案例:
        ---------
            >>> out = self.data.avsl(fast_period=None, slow_period=None, multiplier=None, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.avsl(low, close, volume, fast_period=None, slow_period=None, multiplier=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['upper', 'middle', 'lower'])
    def bollinger_bands(self, period: int = 14, devup: float = 2.0, devdn: float = 2.0, matype: str = 'sma', devtype: int = 0, kernel: str | None = None, **kwargs) -> IndFrame:
        """布林带 · bollinger_bands（波动率）
        ---------
            均线加减标准差形成的通道。触及上下轨提示超买超卖或突破，带宽收窄预示波动率降低。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> devup (float): 宽度 / 倍数系数. 默认: 2.0
            >>> devdn (float): 宽度 / 倍数系数. 默认: 2.0
            >>> matype (str): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 'sma'
            >>> devtype (int): 宽度 / 倍数系数. 默认: 0
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — upper, middle, lower

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.bollinger_bands(period=14, devup=2.0, devdn=2.0, matype='sma', devtype=0, kernel=None)    # 主图叠加
            >>> out.columns               # 线名: upper, middle, lower
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.bollinger_bands(close, period=14, devup=2.0, devdn=2.0, matype='sma', devtype=0, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['bop'])
    def bop(self, **kwargs) -> IndSeries:
        """均势指标 · bop（动量）
        ---------
            收盘价在日内区间中相对位置的强弱比。正值表示买方占优、负值卖方占优，可判断多空力量对比。

        参数:
        ---------
            >>> 无（直接用 K 线数据计算）

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — bop

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.bop()    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.bop(open, high, low, close)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['buff_averages_1', 'buff_averages_2'])
    def buff_averages(self, fast_period: int = 12, slow_period: int = 26, kernel: str | None = None, **kwargs) -> IndFrame:
        """缓冲均线 · buff_averages（趋势）
        ---------
            带缓冲区的快慢均线。快线上穿慢线偏多、下穿偏空，缓冲区可过滤震荡中的假信号。

        参数:
        ---------
            >>> fast_period (int): 快线周期. 默认: 12
            >>> slow_period (int): 慢线周期. 默认: 26
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 2 条线 — buff_averages_1, buff_averages_2

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.buff_averages(fast_period=12, slow_period=26, kernel=None)    # 主图叠加
            >>> out.columns               # 线名: buff_averages_1, buff_averages_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.buff_averages(close, volume, fast_period=12, slow_period=26, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['bull_power_vs_bear_power'])
    def bull_power_vs_bear_power(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """多空力量对比 · bull_power_vs_bear_power（动量）
        ---------
            用最高价、最低价与均线的偏离比较多空力量。正值强势、负值弱势，可观察力量转化与背离。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — bull_power_vs_bear_power

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.bull_power_vs_bear_power(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.bull_power_vs_bear_power(open, high, low, close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['cci'])
    def cci(self, period: int = 20, kernel: str | None = None, **kwargs) -> IndSeries:
        """顺势指标 · cci（动量）
        ---------
            衡量价格偏离统计均值的程度。高于+100强势、低于-100弱势，也常用于判断超买超卖。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cci

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.cci(period=20, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.cci(close, period=20, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['cci_cycle'])
    def cci_cycle(self, length: int = 14, factor: float = 0.5, kernel: str | None = None, **kwargs) -> IndSeries:
        """周期CCI · cci_cycle（动量）
        ---------
            经周期滤波处理的CCI变体，噪声更少。穿越±100或零轴提示趋势与超买超卖状态变化。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> factor (float): 灵敏度系数（宽度 / 阈值 / 加速步长）. 默认: 0.5
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cci_cycle

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.cci_cycle(length=14, factor=0.5, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.cci_cycle(close, length=14, factor=0.5, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['cfo'])
    def cfo(self, period: int = 14, scalar: float = 2.0, kernel: str | None = None, **kwargs) -> IndSeries:
        """钱德预测振荡器 · cfo（动量）
        ---------
            以线性回归斜率归一化得到的动量振荡。零轴上方偏多、下方偏空，用于判断趋势方向与力度。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> scalar (float): 缩放系数. 默认: 2.0
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cfo

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.cfo(period=14, scalar=2.0, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.cfo(close, period=14, scalar=2.0, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['cg'])
    def cg(self, period: int | None = None, **kwargs) -> IndSeries:
        """重心指标 · cg（趋势）
        ---------
            以加权价格重心与当前价格比较的指标。重心高于价格偏多、低于偏空，转折常先于价格出现。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cg

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.cg(period=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.cg(close, period=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['chandelier_exit_1', 'chandelier_exit_2'])
    def chandelier_exit(self, period: int | None = None, mult: str | None = None, use_close: str | None = None, kernel: str | None = None, **kwargs) -> IndFrame:
        """吊灯止损 · chandelier_exit（趋势）
        ---------
            基于最高最低价与ATR的主图追踪止损线。跌破多头线转空、升破空头线转多，用于离场。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: None
            >>> mult (str): ATR / 标准差倍数（决定通道与止损宽度）. 默认: None
            >>> use_close (str): 原库参数（默认值见签名）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 2 条线 — chandelier_exit_1, chandelier_exit_2

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.chandelier_exit(period=None, mult=None, use_close=None, kernel=None)    # 主图叠加
            >>> out.columns               # 线名: chandelier_exit_1, chandelier_exit_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.chandelier_exit(high, low, close, period=None, mult=None, use_close=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['cmo'])
    def cmo(self, period: int | None = None, kernel: str | None = None, **kwargs) -> IndSeries:
        """钱德动量振荡器 · cmo（动量）
        ---------
            用涨跌幅之和计算动量，取值-100至100。高于+50超买、低于-50超卖，也可配合零轴看动量。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cmo

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.cmo(period=None, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.cmo(close, period=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['corrected_moving_average'])
    def corrected_moving_average(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """修正均线 · corrected_moving_average（趋势）
        ---------
            对均线滞后进行补偿的移动平均。价格在其上方偏多、下方偏空，转折比普通均线更贴近价格。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — corrected_moving_average

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.corrected_moving_average(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.corrected_moving_average(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['correl_hl'])
    def correl_hl(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """高低价相关性 · correl_hl（统计）
        ---------
            计算最高价与最低价的相关系数。数值偏低说明区间波动异常，偏高说明高低点同步移动。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — correl_hl

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.correl_hl(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.correl_hl(high, low, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['cvi'])
    def cvi(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """蔡金波动率指标 · cvi（波动率）
        ---------
            用高低价差的EMA与其均线比较衡量波动率。指标上升表示波动放大，可辅助确认突破有效性。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — cvi

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.cvi(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.cvi(high, low, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['cwma'])
    def cwma(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """自定义加权均线 · cwma（趋势）
        ---------
            按递减权重平滑价格的加权移动平均。价格上穿偏多、下穿偏空，兼顾平滑与较低滞后。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — cwma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.cwma(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.cwma(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['dec_osc'])
    def dec_osc(self, hp_period: int = 125, k: float = 1.0, kernel: str | None = None, **kwargs) -> IndSeries:
        """去周期振荡器 · dec_osc（动量）
        ---------
            用高通滤波去除趋势后的振荡线。零轴上下穿越反映短周期波动方向，适合周期摆动交易。

        参数:
        ---------
            >>> hp_period (int): 计算周期（K 线根数）. 默认: 125
            >>> k (float): 平滑 / 放大系数（原库同名参数）. 默认: 1.0
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — dec_osc

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.dec_osc(hp_period=125, k=1.0, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.dec_osc(close, hp_period=125, k=1.0, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['decycler'])
    def decycler(self, hp_period: int | None = None, k: float | None = None, kernel: str | None = None, **kwargs) -> IndSeries:
        """去周期线 · decycler（趋势）
        ---------
            剔除短周期波动的趋势基线。价格在其上方偏多、下方偏空，可用于识别主趋势方向。

        参数:
        ---------
            >>> hp_period (int): 计算周期（K 线根数）. 默认: None
            >>> k (float): 平滑 / 放大系数（原库同名参数）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — decycler

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.decycler(hp_period=None, k=None, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.decycler(close, hp_period=None, k=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['dema'])
    def dema(self, period: int = 20, kernel: str | None = None, **kwargs) -> IndSeries:
        """双指数均线 · dema（趋势）
        ---------
            用两重EMA组合以降低滞后的均线。价格上穿偏多、下穿偏空，能更快反映趋势转折。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — dema

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.dema(period=20, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.dema(close, period=20, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['demand_index_1', 'demand_index_2'])
    def demand_index(self, len_bs: str | None = None, len_bs_ma: str | None = None, len_di_ma: str | None = None, ma_type: str | None = None, kernel: str | None = None, **kwargs) -> IndFrame:
        """需求指数 · demand_index（成交量）
        ---------
            结合成交量与价格变化衡量买盘需求强弱。指数上升表示需求增强，与价格背离提示动能不足。

        参数:
        ---------
            >>> len_bs (str): 原库参数（默认值见签名）. 默认: None
            >>> len_bs_ma (str): 原库参数（默认值见签名）. 默认: None
            >>> len_di_ma (str): 原库参数（默认值见签名）. 默认: None
            >>> ma_type (str): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — demand_index_1, demand_index_2

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.demand_index(len_bs=None, len_bs_ma=None, len_di_ma=None, ma_type=None, kernel=None)    # 副图
            >>> out.columns               # 线名: demand_index_1, demand_index_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.demand_index(high, low, close, volume, len_bs=None, len_bs_ma=None, len_di_ma=None, ma_type=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['di_1', 'di_2'])
    def di(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndFrame:
        """动向指标 · di（趋势）
        ---------
            分别衡量上涨与下跌方向的动向强度（+DI/-DI）。正DI上穿负DI偏多、下穿偏空，
            可判断方向。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — di_1, di_2

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.di(period=14, kernel=None)    # 副图
            >>> out.columns               # 线名: di_1, di_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.di(high, low, close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['didi_index_1', 'didi_index_2'])
    def didi_index(self, short_length: int | None = None, medium_length: int | None = None, long_length: int | None = None, kernel: str | None = None, **kwargs) -> IndFrame:
        """迪迪指数 · didi_index（统计）
        ---------
            比较短中长周期均线的聚散程度。三线由聚而散表示趋势启动，由散而聚表示趋势收敛。

        参数:
        ---------
            >>> short_length (int): 计算周期（K 线根数）. 默认: None
            >>> medium_length (int): 计算周期（K 线根数）. 默认: None
            >>> long_length (int): 计算周期（K 线根数）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — didi_index_1, didi_index_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.didi_index(short_length=None, medium_length=None, long_length=None, kernel=None)    # 副图
            >>> out.columns               # 线名: didi_index_1, didi_index_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.didi_index(close, short_length=None, medium_length=None, long_length=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap={'directional_imbalance_index_1': False, 'directional_imbalance_index_2': False, 'directional_imbalance_index_3': False, 'directional_imbalance_index_4': False, 'directional_imbalance_index_5': True, 'directional_imbalance_index_6': True}, lines=['directional_imbalance_index_1', 'directional_imbalance_index_2', 'directional_imbalance_index_3', 'directional_imbalance_index_4', 'directional_imbalance_index_5', 'directional_imbalance_index_6'])
    def directional_imbalance_index(self, length: int = 14, period: int = 14, kernel: str | None = None, **kwargs) -> IndFrame:
        """方向失衡指数 · directional_imbalance_index（动量）
        ---------
            统计不同方向K线占比以衡量买卖失衡。偏向一侧说明单边力量较强，多线显示不同阈值区间。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 6 条线 — directional_imbalance_index_1, directional_imbalance_index_2, directional_imbalance_index_3, directional_imbalance_index_4, directional_imbalance_index_5, directional_imbalance_index_6

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.directional_imbalance_index(length=14, period=14, kernel=None)    # 主图叠加
            >>> out.columns               # 线名: directional_imbalance_index_1, directional_imbalance_index_2, directional_imbalance_index_3, directional_imbalance_index_4, directional_imbalance_index_5, directional_imbalance_index_6
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.directional_imbalance_index(high, low, length=14, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['disparity_index'])
    def disparity_index(self, ema_period: int = 14, lookback_period: int = 14, smoothing_period: int = 9, smoothing_type: str = 'ema', kernel: str | None = None, **kwargs) -> IndSeries:
        """乖离率指数 · disparity_index（动量）
        ---------
            价格对均线的偏离率经平滑处理。正乖离过大易回落、负乖离过大易反弹，用于超买超卖判断。

        参数:
        ---------
            >>> ema_period (int): EMA 周期. 默认: 14
            >>> lookback_period (int): 计算周期（K 线根数）. 默认: 14
            >>> smoothing_period (int): 计算周期（K 线根数）. 默认: 9
            >>> smoothing_type (str): 平滑周期. 默认: 'ema'
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — disparity_index

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.disparity_index(ema_period=14, lookback_period=14, smoothing_period=9, smoothing_type='ema', kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.disparity_index(close, ema_period=14, lookback_period=14, smoothing_period=9, smoothing_type='ema', kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['dm_1', 'dm_2'])
    def dm(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndFrame:
        """动向运动 · dm（趋势）
        ---------
            分别计算上升与下降方向运动量（+DM/-DM）。是ADX、DI等趋势类指标的计算基础。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — dm_1, dm_2

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.dm(period=14, kernel=None)    # 副图
            >>> out.columns               # 线名: dm_1, dm_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.dm(high, low, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['dma'])
    def dma(self, hull_length: int = 7, ema_length: int = 20, ema_gain_limit: int = 50, hull_ma_type: str = 'WMA', kernel: str | None = None, **kwargs) -> IndSeries:
        """偏差均线 · dma（趋势）
        ---------
            结合Hull与EMA的自适应均线。平滑且反应灵敏，价格在其上方偏多、下方偏空，可作趋势基准。

        参数:
        ---------
            >>> hull_length (int): 计算周期（K 线根数）. 默认: 7
            >>> ema_length (int): EMA 周期. 默认: 20
            >>> ema_gain_limit (int): 对应子指标的周期（原库同名参数）. 默认: 50
            >>> hull_ma_type (str): 原库参数（默认值见签名）. 默认: 'WMA'
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — dma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.dma(hull_length=7, ema_length=20, ema_gain_limit=50, hull_ma_type='WMA', kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.dma(close, hull_length=7, ema_length=20, ema_gain_limit=50, hull_ma_type='WMA', kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['donchian_1', 'donchian_2', 'donchian_3'])
    def donchian(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndFrame:
        """唐奇安通道 · donchian（趋势）
        ---------
            由周期内最高价与最低价构成的价格通道。突破上轨偏多、跌破下轨偏空，中轨为趋势参考。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — donchian_1, donchian_2, donchian_3

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.donchian(period=14, kernel=None)    # 主图叠加
            >>> out.columns               # 线名: donchian_1, donchian_2, donchian_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.donchian(high, low, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['donchian_channel_width'])
    def donchian_channel_width(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """唐奇安通道宽度 · donchian_channel_width（波动率）
        ---------
            通道上下轨之间的宽度。宽度扩大表示波动上升，收窄表示进入盘整，可用于突破前预警。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — donchian_channel_width

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.donchian_channel_width(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.donchian_channel_width(high, low, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['dpo'])
    def dpo(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """区间震荡指标 · dpo（动量）
        ---------
            去除趋势后的价格与均线偏离。围绕零轴摆动，可用于识别周期高低点与超买超卖状态。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — dpo

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.dpo(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.dpo(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['dual_ulcer_index_1', 'dual_ulcer_index_2', 'dual_ulcer_index_3'])
    def dual_ulcer_index(self, period: int = 14, auto_threshold: bool = True, threshold: float = 0.5, kernel: str | None = None, **kwargs) -> IndFrame:
        """双重溃疡指数 · dual_ulcer_index（波动率）
        ---------
            同时衡量回撤深度与回撤持续时间。数值越高表示承受的痛苦越大，可用于比较下行风险。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> auto_threshold (bool): 阈值 / 目标值. 默认: True
            >>> threshold (float): 触发阈值. 默认: 0.5
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 3 条线 — dual_ulcer_index_1, dual_ulcer_index_2, dual_ulcer_index_3

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.dual_ulcer_index(period=14, auto_threshold=True, threshold=0.5, kernel=None)    # 副图
            >>> out.columns               # 线名: dual_ulcer_index_1, dual_ulcer_index_2, dual_ulcer_index_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.dual_ulcer_index(close, period=14, auto_threshold=True, threshold=0.5, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['dvdiqqe_1', 'dvdiqqe_2', 'dvdiqqe_3', 'dvdiqqe_4'])
    def dvdiqqe(self, period: int | None = None, smoothing_period: int | None = None, fast_multiplier: str | None = None, slow_multiplier: str | None = None, volume_type: str | None = None, center_type: str | None = None, tick_size: str | None = None, kernel: str | None = None, **kwargs) -> IndFrame:
        """成交量加权QQE · dvdiqqe（动量）
        ---------
            结合成交量、方向与ATR的量化定性振荡器。快线上穿慢线偏多、下穿偏空，并带超买超卖阈值。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: None
            >>> smoothing_period (int): 计算周期（K 线根数）. 默认: None
            >>> fast_multiplier (str): 快线周期. 默认: None
            >>> slow_multiplier (str): 慢线周期. 默认: None
            >>> volume_type (str): 原库参数（默认值见签名）. 默认: None
            >>> center_type (str): 原库参数（默认值见签名）. 默认: None
            >>> tick_size (str): 原库参数（默认值见签名）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 4 条线 — dvdiqqe_1, dvdiqqe_2, dvdiqqe_3, dvdiqqe_4

        数据:
        ---------
            >>> open, high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.dvdiqqe(period=None, smoothing_period=None, fast_multiplier=None, slow_multiplier=None, volume_type=None, center_type=None, tick_size=None, kernel=None)    # 副图
            >>> out.columns               # 线名: dvdiqqe_1, dvdiqqe_2, dvdiqqe_3, dvdiqqe_4
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.dvdiqqe(open, high, low, close, volume, period=None, smoothing_period=None, fast_multiplier=None, slow_multiplier=None, volume_type=None, center_type=None, tick_size=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['dx'])
    def dx(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """动向指数 · dx（趋势）
        ---------
            由+DI与-DI标准化得到的趋势强度。数值越高方向性越强，是ADX的原始形式。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — dx

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.dx(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.dx(high, low, close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['dynamic_momentum_index'])
    def dynamic_momentum_index(self, rsi_period: int = 14, volatility_period: int = 5, volatility_sma_period: int = 10, upper_limit: int = 30, lower_limit: int = 5, kernel: str | None = None, **kwargs) -> IndSeries:
        """动态动量指数 · dynamic_momentum_index（动量）
        ---------
            按波动率动态调整阈值的RSI类指标。指标在动态上下限间变化，使超买超卖判断更灵敏。

        参数:
        ---------
            >>> rsi_period (int): RSI 计算周期. 默认: 14
            >>> volatility_period (int): 计算周期（K 线根数）. 默认: 5
            >>> volatility_sma_period (int): 计算周期（K 线根数）. 默认: 10
            >>> upper_limit (int): 阈值 / 目标值. 默认: 30
            >>> lower_limit (int): 阈值 / 目标值. 默认: 5
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — dynamic_momentum_index

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.dynamic_momentum_index(rsi_period=14, volatility_period=5, volatility_sma_period=10, upper_limit=30, lower_limit=5, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.dynamic_momentum_index(close, rsi_period=14, volatility_period=5, volatility_sma_period=10, upper_limit=30, lower_limit=5, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['edcf'])
    def edcf(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """指数衰减趋势线 · edcf（趋势）
        ---------
            对价格作指数衰减滤波的主图趋势线。价格在其上方偏多、下方偏空，可平滑噪声并跟踪趋势。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — edcf

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.edcf(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.edcf(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['efi'])
    def efi(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """力量指数 · efi（成交量）
        ---------
            用价格变化乘以成交量衡量多空力量。正值偏多、负值偏空，经均线平滑后可判断趋势强弱。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — efi

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.efi(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.efi(close, volume, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ehlers_adaptive_cg_1', 'ehlers_adaptive_cg_2'])
    def ehlers_adaptive_cg(self, alpha: float | None = None, **kwargs) -> IndFrame:
        """自适应重心 · ehlers_adaptive_cg（趋势）
        ---------
            采用自适应周期的重心类指标。重心上穿价格或零轴偏多、下穿偏空，可捕捉短周期转折。

        参数:
        ---------
            >>> alpha (float): 平滑系数 / 显著性水平. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — ehlers_adaptive_cg_1, ehlers_adaptive_cg_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ehlers_adaptive_cg(alpha=None)    # 副图
            >>> out.columns               # 线名: ehlers_adaptive_cg_1, ehlers_adaptive_cg_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ehlers_adaptive_cg(close, alpha=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ehlers_autocorrelation_periodogram_1', 'ehlers_autocorrelation_periodogram_2'])
    def ehlers_autocorrelation_periodogram(self, min_period: int | None = None, max_period: int | None = None, avg_length: int | None = None, enhance: str | None = None, kernel: str | None = None, **kwargs) -> IndFrame:
        """自相关周期图 · ehlers_autocorrelation_periodogram（统计）
        ---------
            用自相关估计市场主导周期及其强度。可判断当前主导周期长度，辅助周期分析与参数选择。

        参数:
        ---------
            >>> min_period (int): 最小周期. 默认: None
            >>> max_period (int): 最大周期. 默认: None
            >>> avg_length (int): 计算周期（K 线根数）. 默认: None
            >>> enhance (str): 原库参数（默认值见签名）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — ehlers_autocorrelation_periodogram_1, ehlers_autocorrelation_periodogram_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ehlers_autocorrelation_periodogram(min_period=None, max_period=None, avg_length=None, enhance=None, kernel=None)    # 副图
            >>> out.columns               # 线名: ehlers_autocorrelation_periodogram_1, ehlers_autocorrelation_periodogram_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ehlers_autocorrelation_periodogram(close, min_period=None, max_period=None, avg_length=None, enhance=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ehlers_detrending_filter_1', 'ehlers_detrending_filter_2'])
    def ehlers_detrending_filter(self, length: int = 14, kernel: str | None = None, **kwargs) -> IndFrame:
        """去趋势滤波器 · ehlers_detrending_filter（统计）
        ---------
            去除趋势后输出去趋势价格及其波动幅度。可观察短周期波动方向并据此判断超买超卖。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — ehlers_detrending_filter_1, ehlers_detrending_filter_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ehlers_detrending_filter(length=14, kernel=None)    # 副图
            >>> out.columns               # 线名: ehlers_detrending_filter_1, ehlers_detrending_filter_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ehlers_detrending_filter(close, length=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['ehlers_ecema'])
    def ehlers_ecema(self, length: int = 14, gain_limit: int = 50, pine_compatible: bool = False, confirmed_only: bool = False, kernel: str | None = None, **kwargs) -> IndSeries:
        """误差修正均线 · ehlers_ecema（趋势）
        ---------
            用误差修正方式平滑价格的指数均线。价格在其上方偏多、下方偏空，兼顾平滑与低滞后。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> gain_limit (int): 阈值 / 目标值. 默认: 50
            >>> pine_compatible (bool): 原库参数（默认值见签名）. 默认: False
            >>> confirmed_only (bool): 原库参数（默认值见签名）. 默认: False
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — ehlers_ecema

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ehlers_ecema(length=14, gain_limit=50, pine_compatible=False, confirmed_only=False, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ehlers_ecema(close, length=14, gain_limit=50, pine_compatible=False, confirmed_only=False, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ehlers_fm_demodulator'])
    def ehlers_fm_demodulator(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """FM解调器 · ehlers_fm_demodulator（动量）
        ---------
            把价格视作调频信号解调出相位变化。上穿零轴表示周期上行、下穿表示下行，用于周期择时。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ehlers_fm_demodulator

        数据:
        ---------
            >>> open, close

        使用案例:
        ---------
            >>> out = self.data.ehlers_fm_demodulator(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ehlers_fm_demodulator(open, close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['ehlers_kama'])
    def ehlers_kama(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """考夫曼自适应均线 · ehlers_kama（趋势）
        ---------
            按效率比自动调整平滑速度的均线。趋势时灵敏、震荡时平滑，价格上穿偏多、下穿偏空。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — ehlers_kama

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ehlers_kama(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ehlers_kama(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ehlers_linear_extrapolation_predictor_1', 'ehlers_linear_extrapolation_predictor_2'])
    def ehlers_linear_extrapolation_predictor(self, high_pass_length: int | None = None, low_pass_length: int | None = None, gain: str | None = None, bars_forward: str | None = None, signal_mode: str | None = None, kernel: str | None = None, **kwargs) -> IndFrame:
        """线性外推预测器 · ehlers_linear_extrapolation_predictor（其他）
        ---------
            用线性外推预测未来若干根K线的价格。预测线上穿实际价偏多、下穿偏空，可提前判断方向。

        参数:
        ---------
            >>> high_pass_length (int): 计算周期（K 线根数）. 默认: None
            >>> low_pass_length (int): 计算周期（K 线根数）. 默认: None
            >>> gain (str): 原库参数（默认值见签名）. 默认: None
            >>> bars_forward (str): 原库参数（默认值见签名）. 默认: None
            >>> signal_mode (str): 信号线平滑周期. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — ehlers_linear_extrapolation_predictor_1, ehlers_linear_extrapolation_predictor_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ehlers_linear_extrapolation_predictor(high_pass_length=None, low_pass_length=None, gain=None, bars_forward=None, signal_mode=None, kernel=None)    # 副图
            >>> out.columns               # 线名: ehlers_linear_extrapolation_predictor_1, ehlers_linear_extrapolation_predictor_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ehlers_linear_extrapolation_predictor(close, high_pass_length=None, low_pass_length=None, gain=None, bars_forward=None, signal_mode=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['ehlers_pma_1', 'ehlers_pma_2'])
    def ehlers_pma(self, kernel: str | None = None, **kwargs) -> IndFrame:
        """预测型均线 · ehlers_pma（趋势）
        ---------
            含预测成分的主图移动平均，能提前反映价格转向。价格上穿偏多、下穿偏空，适合趋势跟踪。

        参数:
        ---------
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 2 条线 — ehlers_pma_1, ehlers_pma_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ehlers_pma(kernel=None)    # 主图叠加
            >>> out.columns               # 线名: ehlers_pma_1, ehlers_pma_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ehlers_pma(close, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ehlers_smoothed_adaptive_momentum'])
    def ehlers_smoothed_adaptive_momentum(self, alpha: float = 0.07, cutoff: float = 8.0, kernel: str | None = None, **kwargs) -> IndSeries:
        """平滑自适应动量 · ehlers_smoothed_adaptive_momentum（动量）
        ---------
            经平滑滤波提取的自适应动量振荡。零轴上下变化反映动量方向，过零与斜率变化可用于择时。

        参数:
        ---------
            >>> alpha (float): 平滑系数 / 显著性水平. 默认: 0.07
            >>> cutoff (float): 原库参数（默认值见签名）. 默认: 8.0
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ehlers_smoothed_adaptive_momentum

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ehlers_smoothed_adaptive_momentum(alpha=0.07, cutoff=8.0, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ehlers_smoothed_adaptive_momentum(close, alpha=0.07, cutoff=8.0, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ehlers_undersampled_double_moving_average_1', 'ehlers_undersampled_double_moving_average_2'])
    def ehlers_undersampled_double_moving_average(self, fast_length: int = 6, slow_length: int = 12, sample_length: int = 5, kernel: str | None = None, **kwargs) -> IndFrame:
        """欠采样双均线 · ehlers_undersampled_double_moving_average（趋势）
        ---------
            对降采样价格计算双均线后再插值。快线上穿慢线偏多、下穿偏空，可有效减少噪声干扰。

        参数:
        ---------
            >>> fast_length (int): 快线周期. 默认: 6
            >>> slow_length (int): 慢线周期. 默认: 12
            >>> sample_length (int): 计算周期（K 线根数）. 默认: 5
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — ehlers_undersampled_double_moving_average_1, ehlers_undersampled_double_moving_average_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ehlers_undersampled_double_moving_average(fast_length=6, slow_length=12, sample_length=5, kernel=None)    # 副图
            >>> out.columns               # 线名: ehlers_undersampled_double_moving_average_1, ehlers_undersampled_double_moving_average_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ehlers_undersampled_double_moving_average(close, fast_length=6, slow_length=12, sample_length=5, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['ehma'])
    def ehma(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """埃勒斯Hull均线 · ehma（趋势）
        ---------
            Hull风格的快速均线，滞后较小。价格上穿偏多、下穿偏空，适合捕捉趋势启动与转折。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — ehma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ehma(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ehma(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['ema'])
    def ema(self, period: int = 20, kernel: str | None = None, **kwargs) -> IndSeries:
        """指数移动平均 · ema（趋势）
        ---------
            对近期价格赋予更高权重的均线。价格在其上方偏多、下方偏空，常作趋势基准与止损参考。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — ema

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ema(period=20, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ema(close, period=20, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['emv'])
    def emv(self, kernel: str | None = None, **kwargs) -> IndSeries:
        """简易波动指标 · emv（成交量）
        ---------
            结合价格变动与成交量衡量推动价格的难易。上穿零轴偏多、下穿偏空，可判断趋势可持续性。

        参数:
        ---------
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — emv

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.emv(kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.emv(high, low, close, volume, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['epma'])
    def epma(self, period: int = 14, offset: int = 0, kernel: str | None = None, **kwargs) -> IndSeries:
        """端点移动平均 · epma（趋势）
        ---------
            以回归端点计算并可前后偏移的均线。价格上穿偏多、下穿偏空，偏移参数可提前或延后信号。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> offset (int): 中心偏移（0~1，越大越靠右）. 默认: 0
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — epma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.epma(period=14, offset=0, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.epma(close, period=14, offset=0, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['er'])
    def er(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """效率比 · er（统计）
        ---------
            净变动与总波动路径之比，取值0至1。接近1表示趋势干净，接近0表示噪声大，可用于自适应参数。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — er

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.er(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.er(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['eri_1', 'eri_2'])
    def eri(self, period: int = 14, ma_type: str = 'ema', kernel: str | None = None, **kwargs) -> IndFrame:
        """ERI振荡指标 · eri（动量）
        ---------
            以指定均线平滑的振荡指标。上穿信号线偏多、下穿偏空，用于判断短周期动量转折与强弱。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> ma_type (str): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 'ema'
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — eri_1, eri_2

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.eri(period=14, ma_type='ema', kernel=None)    # 副图
            >>> out.columns               # 线名: eri_1, eri_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.eri(high, low, close, period=14, ma_type='ema', kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ewma_volatility'])
    def ewma_volatility(self, lambda_: float = 0.94, kernel: str | None = None, **kwargs) -> IndSeries:
        """指数加权波动率 · ewma_volatility（波动率）
        ---------
            用指数加权方式估计收益率的波动水平。数值升高表示市场风险加大，可用于仓位与止损设置。

        参数:
        ---------
            >>> lambda_ (float): 衰减系数 λ. 默认: 0.94
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ewma_volatility

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ewma_volatility(lambda_=0.94, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ewma_volatility(close, lambda_=0.94, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['fisher_1', 'fisher_2'])
    def fisher(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndFrame:
        """费雪变换 · fisher（动量）
        ---------
            对价格所处位置作费雪变换以放大转折。上穿信号线偏多、下穿偏空，处于极值区提示超买超卖。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — fisher_1, fisher_2

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.fisher(period=14, kernel=None)    # 副图
            >>> out.columns               # 线名: fisher_1, fisher_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.fisher(high, low, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['fosc'])
    def fosc(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """预测振荡器 · fosc（动量）
        ---------
            用线性回归预测价格与收盘价的偏离百分比，判断趋势延续或转折，正值偏强、负值偏弱。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — fosc

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.fosc(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.fosc(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['fractal_dimension_index'])
    def fractal_dimension_index(self, length: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """分形维度指数 · fractal_dimension_index（统计）
        ---------
            按分形维度衡量价格序列的粗糙程度，数值越低趋势越平滑，越高越接近随机波动。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — fractal_dimension_index

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.fractal_dimension_index(length=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.fractal_dimension_index(close, length=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['fwma'])
    def fwma(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """斐波那契加权均线 · fwma（趋势）
        ---------
            按斐波那契数列给近端价格更高权重的均线，比普通均线灵敏，用于顺势跟踪与回调支撑。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — fwma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.fwma(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.fwma(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['garman_klass_volatility'])
    def garman_klass_volatility(self, lookback: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """Garman-Klass波动率 · garman_klass_volatility（波动率）
        ---------
            用开高低收四个价格估计的波动率，比仅用收盘价更有效；数值升高表示市场波动加剧。

        参数:
        ---------
            >>> lookback (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — garman_klass_volatility

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.garman_klass_volatility(lookback=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.garman_klass_volatility(open, high, low, close, lookback=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['gatorosc_1', 'gatorosc_2', 'gatorosc_3', 'gatorosc_4'])
    def gatorosc(self, jaws_length: int = 13, jaws_shift: int = 8, teeth_length: int = 8, teeth_shift: int = 5, lips_length: int = 5, lips_shift: int = 3, kernel: str | None = None, **kwargs) -> IndFrame:
        """鳄鱼振荡器 · gatorosc（趋势）
        ---------
            以三条平滑均线差值构成的柱状图显示趋势启动与衰竭，柱体扩张表示趋势增强，
            收缩表示盘整。

        参数:
        ---------
            >>> jaws_length (int): 计算周期（K 线根数）. 默认: 13
            >>> jaws_shift (int): 平移根数. 默认: 8
            >>> teeth_length (int): 计算周期（K 线根数）. 默认: 8
            >>> teeth_shift (int): 平移根数. 默认: 5
            >>> lips_length (int): 计算周期（K 线根数）. 默认: 5
            >>> lips_shift (int): 平移根数. 默认: 3
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 4 条线 — gatorosc_1, gatorosc_2, gatorosc_3, gatorosc_4

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.gatorosc(jaws_length=13, jaws_shift=8, teeth_length=8, teeth_shift=5, lips_length=5, lips_shift=3, kernel=None)    # 副图
            >>> out.columns               # 线名: gatorosc_1, gatorosc_2, gatorosc_3, gatorosc_4
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.gatorosc(close, jaws_length=13, jaws_shift=8, teeth_length=8, teeth_shift=5, lips_length=5, lips_shift=3, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['gmma_oscillator_1', 'gmma_oscillator_2'])
    def gmma_oscillator(self, gmma_type: str = 'guppy', smooth_length: int = 1, signal_length: int = 13, anchor_minutes: int = 0, interval_minutes: str | None = None, kernel: str | None = None, **kwargs) -> IndFrame:
        """顾比均线振荡器 · gmma_oscillator（趋势）
        ---------
            以短期与长期顾比均线组的差值衡量多空力量，上穿零轴偏多、下穿偏空，适合判断趋势转换。

        参数:
        ---------
            >>> gmma_type (str): 原库参数（默认值见签名）. 默认: 'guppy'
            >>> smooth_length (int): 平滑周期. 默认: 1
            >>> signal_length (int): 信号线平滑周期. 默认: 13
            >>> anchor_minutes (int): 原库参数（默认值见签名）. 默认: 0
            >>> interval_minutes (str): 原库参数（默认值见签名）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — gmma_oscillator_1, gmma_oscillator_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.gmma_oscillator(gmma_type='guppy', smooth_length=1, signal_length=13, anchor_minutes=0, interval_minutes=None, kernel=None)    # 副图
            >>> out.columns               # 线名: gmma_oscillator_1, gmma_oscillator_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.gmma_oscillator(close, gmma_type='guppy', smooth_length=1, signal_length=13, anchor_minutes=0, interval_minutes=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['gopalakrishnan_range_index'])
    def gopalakrishnan_range_index(self, length: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """Gopalakrishnan区间指数 · gopalakrishnan_range_index（波动率）
        ---------
            综合高低价区间与均线偏离度量趋势强度，数值走高表示单边趋势明显，走低则震荡为主。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — gopalakrishnan_range_index

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.gopalakrishnan_range_index(length=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.gopalakrishnan_range_index(high, low, length=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['highpass'])
    def highpass(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """高通滤波 · highpass（其他）
        ---------
            埃勒斯高通滤波器，滤除长期趋势只保留短期波动，用于识别主导周期与短线超买超卖。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — highpass

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.highpass(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.highpass(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['historical_volatility'])
    def historical_volatility(self, lookback: int = 20, annualization_days: float = 250.0, kernel: str | None = None, **kwargs) -> IndSeries:
        """历史波动率 · historical_volatility（波动率）
        ---------
            收益率标准差年化得到的历史波动率，反映近期实际波动幅度，常用于风险与仓位管理。

        参数:
        ---------
            >>> lookback (int): 计算周期（K 线根数）. 默认: 20
            >>> annualization_days (float): 原库参数（默认值见签名）. 默认: 250.0
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — historical_volatility

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.historical_volatility(lookback=20, annualization_days=250.0, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.historical_volatility(close, lookback=20, annualization_days=250.0, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['historical_volatility_percentile_1', 'historical_volatility_percentile_2'])
    def historical_volatility_percentile(self, length: int = 14, annual_length: int = 252, kernel: str | None = None, **kwargs) -> IndFrame:
        """历史波动率百分位 · historical_volatility_percentile（波动率）
        ---------
            比较当前波动率在其历史分布中的位置，低位常伴随后续扩张，高位提示波动回落风险。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> annual_length (int): 计算周期（K 线根数）. 默认: 252
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — historical_volatility_percentile_1, historical_volatility_percentile_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.historical_volatility_percentile(length=14, annual_length=252, kernel=None)    # 副图
            >>> out.columns               # 线名: historical_volatility_percentile_1, historical_volatility_percentile_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.historical_volatility_percentile(close, length=14, annual_length=252, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['hma'])
    def hma(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """Hull均线 · hma（趋势）
        ---------
            用加权均线组合大幅降低滞后的平滑均线，贴价快、转向灵，适合捕捉趋势方向与拐点。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — hma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.hma(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.hma(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['macd', 'signal', 'histogram'], linestyle={'histogram': LineStyle(line_dash=LineDash.vbar, vbar_base=0.0, vbar_up_color=Colors.bull_color, vbar_down_color=Colors.bear_color)})
    def impulse_macd(self, length_ma: int = 34, length_signal: int = 9, kernel: str | None = None, **kwargs) -> IndFrame:
        """脉冲MACD · impulse_macd（动量）
        ---------
            以MACD系统衡量趋势动量，柱状图扩张表示动量加强，柱体收缩或反向提示动能衰竭。

        参数:
        ---------
            >>> length_ma (int): 计算周期（K 线根数）. 默认: 34
            >>> length_signal (int): 计算周期（K 线根数）. 默认: 9
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 3 条线 — macd, signal, histogram

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.impulse_macd(length_ma=34, length_signal=9, kernel=None)    # 副图
            >>> out.columns               # 线名: macd, signal, histogram
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.impulse_macd(high, low, close, length_ma=34, length_signal=9, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['intraday_momentum_index_1', 'intraday_momentum_index_2', 'intraday_momentum_index_3', 'intraday_momentum_index_4'])
    def intraday_momentum_index(self, length: int | None = None, length_ma: str | None = None, mult: str | None = None, length_bb: str | None = None, apply_smoothing: str | None = None, low_band: str | None = None, kernel: str | None = None, **kwargs) -> IndFrame:
        """日内动量指数 · intraday_momentum_index（动量）
        ---------
            结合价格与波动带的日内动量指标，超越上轨偏强、跌破下轨偏弱，可辅助短线进退。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: None
            >>> length_ma (str): 计算周期（K 线根数）. 默认: None
            >>> mult (str): ATR / 标准差倍数（决定通道与止损宽度）. 默认: None
            >>> length_bb (str): 计算周期（K 线根数）. 默认: None
            >>> apply_smoothing (str): 平滑周期. 默认: None
            >>> low_band (str): 原库参数（默认值见签名）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 4 条线 — intraday_momentum_index_1, intraday_momentum_index_2, intraday_momentum_index_3, intraday_momentum_index_4

        数据:
        ---------
            >>> open, close

        使用案例:
        ---------
            >>> out = self.data.intraday_momentum_index(length=None, length_ma=None, mult=None, length_bb=None, apply_smoothing=None, low_band=None, kernel=None)    # 副图
            >>> out.columns               # 线名: intraday_momentum_index_1, intraday_momentum_index_2, intraday_momentum_index_3, intraday_momentum_index_4
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.intraday_momentum_index(open, close, length=None, length_ma=None, mult=None, length_bb=None, apply_smoothing=None, low_band=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['jma'])
    def jma(self, period: int = 14, phase: float = 50.0, power: int = 2, kernel: str | None = None, **kwargs) -> IndSeries:
        """Jurik均线 · jma（趋势）
        ---------
            低噪声、低滞后的自适应均线，斜率向上偏多、向下偏空，常用来替代普通均线跟踪趋势。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> phase (float): 相位（周期类指标的相位偏移）. 默认: 50.0
            >>> power (int): 幂次 / 放大指数. 默认: 2
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — jma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.jma(period=14, phase=50.0, power=2, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.jma(close, period=14, phase=50.0, power=2, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['jsa'])
    def jsa(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """Jurik平滑均线 · jsa（趋势）
        ---------
            Jurik平滑算法构造的均线，兼顾平滑与响应速度，用于判断趋势方向与动态支撑阻力。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — jsa

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.jsa(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.jsa(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['kairi_relative_index'])
    def kairi_relative_index(self, length: int = 14, ma_type: str = 'SMA', kernel: str | None = None, **kwargs) -> IndSeries:
        """Kairi相对指数 · kairi_relative_index（动量）
        ---------
            收盘价相对均线的偏离百分比，正值表示高于均线偏强，负值表示偏弱，可用于均值回归。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> ma_type (str): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 'SMA'
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — kairi_relative_index

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.kairi_relative_index(length=14, ma_type='SMA', kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.kairi_relative_index(close, volume, length=14, ma_type='SMA', kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['kama'])
    def kama(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """考夫曼自适应均线 · kama（趋势）
        ---------
            按效率比自动调节速度的自适应均线，趋势快时灵敏、震荡时平滑，用于过滤噪声跟踪趋势。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — kama

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.kama(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.kama(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['kase_peak_oscillator_with_divergences_1', 'kase_peak_oscillator_with_divergences_2', 'kase_peak_oscillator_with_divergences_3', 'kase_peak_oscillator_with_divergences_4', 'kase_peak_oscillator_with_divergences_5', 'kase_peak_oscillator_with_divergences_6', 'kase_peak_oscillator_with_divergences_7', 'kase_peak_oscillator_with_divergences_8', 'kase_peak_oscillator_with_divergences_9'])
    def kase_peak_oscillator_with_divergences(self, deviations: str | None = None, short_cycle: str | None = None, long_cycle: str | None = None, sensitivity: str | None = None, all_peaks_mode: str | None = None, lb_r: str | None = None, lb_l: str | None = None, range_upper: str | None = None, range_lower: str | None = None, plot_bull: str | None = None, plot_hidden_bull: str | None = None, plot_bear: str | None = None, plot_hidden_bear: str | None = None, kernel: str | None = None, **kwargs) -> IndFrame:
        """Kase峰谷振荡器(含背离) · kase_peak_oscillator_with_divergences（动量）
        ---------
            基于统计极值的振荡器并标注牛熊及隐藏背离，用于识别超买超卖与潜在反转信号。

        参数:
        ---------
            >>> deviations (str): 宽度 / 倍数系数. 默认: None
            >>> short_cycle (str): 原库参数（默认值见签名）. 默认: None
            >>> long_cycle (str): 原库参数（默认值见签名）. 默认: None
            >>> sensitivity (str): 原库参数（默认值见签名）. 默认: None
            >>> all_peaks_mode (str): 原库参数（默认值见签名）. 默认: None
            >>> lb_r (str): 原库参数（默认值见签名）. 默认: None
            >>> lb_l (str): 原库参数（默认值见签名）. 默认: None
            >>> range_upper (str): 原库参数（默认值见签名）. 默认: None
            >>> range_lower (str): 原库参数（默认值见签名）. 默认: None
            >>> plot_bull (str): 原库参数（默认值见签名）. 默认: None
            >>> plot_hidden_bull (str): 原库参数（默认值见签名）. 默认: None
            >>> plot_bear (str): 原库参数（默认值见签名）. 默认: None
            >>> plot_hidden_bear (str): 原库参数（默认值见签名）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 9 条线 — kase_peak_oscillator_with_divergences_1, kase_peak_oscillator_with_divergences_2, kase_peak_oscillator_with_divergences_3, kase_peak_oscillator_with_divergences_4, kase_peak_oscillator_with_divergences_5, kase_peak_oscillator_with_divergences_6, kase_peak_oscillator_with_divergences_7, kase_peak_oscillator_with_divergences_8, kase_peak_oscillator_with_divergences_9

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.kase_peak_oscillator_with_divergences(deviations=None, short_cycle=None, long_cycle=None, sensitivity=None, all_peaks_mode=None, lb_r=None, lb_l=None, range_upper=None, range_lower=None, plot_bull=None, plot_hidden_bull=None, plot_bear=None, plot_hidden_bear=None, kernel=None)    # 副图
            >>> out.columns               # 线名: kase_peak_oscillator_with_divergences_1, kase_peak_oscillator_with_divergences_2, kase_peak_oscillator_with_divergences_3, kase_peak_oscillator_with_divergences_4, kase_peak_oscillator_with_divergences_5, kase_peak_oscillator_with_divergences_6, kase_peak_oscillator_with_divergences_7, kase_peak_oscillator_with_divergences_8, kase_peak_oscillator_with_divergences_9
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.kase_peak_oscillator_with_divergences(high, low, close, deviations=None, short_cycle=None, long_cycle=None, sensitivity=None, all_peaks_mode=None, lb_r=None, lb_l=None, range_upper=None, range_lower=None, plot_bull=None, plot_hidden_bull=None, plot_bear=None, plot_hidden_bear=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['kaufmanstop'])
    def kaufmanstop(self, period: int = 14, mult: float = 2.0, direction: str = 'long', ma_type: str = 'sma', kernel: str | None = None, **kwargs) -> IndSeries:
        """考夫曼止损线 · kaufmanstop（趋势）
        ---------
            以考夫曼效率均线加波动倍数的追踪止损线，价格在其上方维持多头，用于动态止盈止损。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> mult (float): ATR / 标准差倍数（决定通道与止损宽度）. 默认: 2.0
            >>> direction (str): 原库参数（默认值见签名）. 默认: 'long'
            >>> ma_type (str): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 'sma'
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — kaufmanstop

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.kaufmanstop(period=14, mult=2.0, direction='long', ma_type='sma', kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.kaufmanstop(high, low, period=14, mult=2.0, direction='long', ma_type='sma', kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['k', 'd', 'j'])
    def kdj(self, fast_k_period: int = 9, slow_k_period: int = 3, slow_k_ma_type: str = 'sma', slow_d_period: int = 3, slow_d_ma_type: str = 'sma', kernel: str | None = None, **kwargs) -> IndFrame:
        """KDJ随机指标 · kdj（动量）
        ---------
            随机指标的K、D、J三线，用超买超卖区与金叉死叉判断短线转折，J值波动最敏感。

        参数:
        ---------
            >>> fast_k_period (int): 计算周期（K 线根数）. 默认: 9
            >>> slow_k_period (int): 计算周期（K 线根数）. 默认: 3
            >>> slow_k_ma_type (str): 慢线周期. 默认: 'sma'
            >>> slow_d_period (int): 计算周期（K 线根数）. 默认: 3
            >>> slow_d_ma_type (str): 慢线周期. 默认: 'sma'
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 3 条线 — k, d, j

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.kdj(fast_k_period=9, slow_k_period=3, slow_k_ma_type='sma', slow_d_period=3, slow_d_ma_type='sma', kernel=None)    # 副图
            >>> out.columns               # 线名: k, d, j
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.kdj(high, low, close, fast_k_period=9, slow_k_period=3, slow_k_ma_type='sma', slow_d_period=3, slow_d_ma_type='sma', kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['keltner_1', 'keltner_2', 'keltner_3'])
    def keltner(self, period: int = 14, multiplier: float = 3.0, ma_type: str = 'ema', kernel: str | None = None, **kwargs) -> IndFrame:
        """肯特纳通道 · keltner（趋势）
        ---------
            以均线加ATR倍数构成的通道，价格触及上下轨显示突破或超买超卖，通道宽度反映波动。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> multiplier (float): ATR / 标准差倍数（决定通道与止损宽度）. 默认: 3.0
            >>> ma_type (str): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 'ema'
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — keltner_1, keltner_2, keltner_3

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.keltner(period=14, multiplier=3.0, ma_type='ema', kernel=None)    # 主图叠加
            >>> out.columns               # 线名: keltner_1, keltner_2, keltner_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.keltner(high, low, close, period=14, multiplier=3.0, ma_type='ema', kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['keltner_channel_width_oscillator_1', 'keltner_channel_width_oscillator_2'])
    def keltner_channel_width_oscillator(self, length: int = 14, multiplier: float = 3.0, use_exponential: bool = True, bands_style: str = 'Average True Range', atr_length: int = 10, kernel: str | None = None, **kwargs) -> IndFrame:
        """肯特纳通道宽度振荡器 · keltner_channel_width_oscillator（波动率）
        ---------
            把肯特纳通道宽度做归一化，读数升高表示波动扩张、降低表示收缩，可预判突破或盘整。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> multiplier (float): ATR / 标准差倍数（决定通道与止损宽度）. 默认: 3.0
            >>> use_exponential (bool): 原库参数（默认值见签名）. 默认: True
            >>> bands_style (str): 原库参数（默认值见签名）. 默认: 'Average True Range'
            >>> atr_length (int): ATR 计算周期. 默认: 10
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — keltner_channel_width_oscillator_1, keltner_channel_width_oscillator_2

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.keltner_channel_width_oscillator(length=14, multiplier=3.0, use_exponential=True, bands_style='Average True Range', atr_length=10, kernel=None)    # 副图
            >>> out.columns               # 线名: keltner_channel_width_oscillator_1, keltner_channel_width_oscillator_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.keltner_channel_width_oscillator(high, low, close, length=14, multiplier=3.0, use_exponential=True, bands_style='Average True Range', atr_length=10, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['kst_1', 'kst_2'])
    def kst(self, sma_period1: str | None = None, sma_period2: str | None = None, sma_period3: str | None = None, sma_period4: str | None = None, roc_period1: str | None = None, roc_period2: str | None = None, roc_period3: str | None = None, roc_period4: str | None = None, signal_period: int | None = None, kernel: str | None = None, **kwargs) -> IndFrame:
        """确然指标KST · kst（动量）
        ---------
            多个不同周期变动率的加权总和并配信号线，衡量中长期动量，上穿信号线偏多。

        参数:
        ---------
            >>> sma_period1 (str): 对应子指标的周期（原库同名参数）. 默认: None
            >>> sma_period2 (str): 对应子指标的周期（原库同名参数）. 默认: None
            >>> sma_period3 (str): 对应子指标的周期（原库同名参数）. 默认: None
            >>> sma_period4 (str): 对应子指标的周期（原库同名参数）. 默认: None
            >>> roc_period1 (str): 对应子指标的周期（原库同名参数）. 默认: None
            >>> roc_period2 (str): 对应子指标的周期（原库同名参数）. 默认: None
            >>> roc_period3 (str): 对应子指标的周期（原库同名参数）. 默认: None
            >>> roc_period4 (str): 对应子指标的周期（原库同名参数）. 默认: None
            >>> signal_period (int): 信号线平滑周期. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — kst_1, kst_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.kst(sma_period1=None, sma_period2=None, sma_period3=None, sma_period4=None, roc_period1=None, roc_period2=None, roc_period3=None, roc_period4=None, signal_period=None, kernel=None)    # 副图
            >>> out.columns               # 线名: kst_1, kst_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.kst(close, sma_period1=None, sma_period2=None, sma_period3=None, sma_period4=None, roc_period1=None, roc_period2=None, roc_period3=None, roc_period4=None, signal_period=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['kurtosis'])
    def kurtosis(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """峰度 · kurtosis（统计）
        ---------
            衡量收益率分布尾部厚度的统计量，峰度高表示极端行情出现概率大，风险偏高。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — kurtosis

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.kurtosis(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.kurtosis(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['kvo'])
    def kvo(self, short_period: int | None = None, long_period: int | None = None, kernel: str | None = None, **kwargs) -> IndSeries:
        """Klinger量价振荡器 · kvo（成交量）
        ---------
            结合成交量与价格方向的量能指标，柱体正负与信号线交叉反映资金进出与趋势确认。

        参数:
        ---------
            >>> short_period (int): 短周期. 默认: None
            >>> long_period (int): 长周期. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — kvo

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.kvo(short_period=None, long_period=None, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.kvo(high, low, close, volume, short_period=None, long_period=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['l1_ehlers_phasor'])
    def l1_ehlers_phasor(self, domestic_cycle_length: int = 15, kernel: str | None = None, **kwargs) -> IndSeries:
        """一阶相位器 · l1_ehlers_phasor（统计）
        ---------
            埃勒斯相位器用反正切求价格波动的相位，判断当前周期处于上升段还是下降段。

        参数:
        ---------
            >>> domestic_cycle_length (int): 计算周期（K 线根数）. 默认: 15
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — l1_ehlers_phasor

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.l1_ehlers_phasor(domestic_cycle_length=15, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.l1_ehlers_phasor(close, domestic_cycle_length=15, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['l2_ehlers_signal_to_noise'])
    def l2_ehlers_signal_to_noise(self, smooth_period: int = 10, kernel: str | None = None, **kwargs) -> IndSeries:
        """二阶信噪比 · l2_ehlers_signal_to_noise（统计）
        ---------
            用平滑后的信噪比区分趋势与噪声，数值高说明趋势信号强，低时市场偏杂乱。

        参数:
        ---------
            >>> smooth_period (int): 平滑周期. 默认: 10
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — l2_ehlers_signal_to_noise

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.l2_ehlers_signal_to_noise(smooth_period=10, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.l2_ehlers_signal_to_noise(high, low, close, smooth_period=10, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['linear_correlation_oscillator'])
    def linear_correlation_oscillator(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """线性相关振荡器 · linear_correlation_oscillator（统计）
        ---------
            用价格与时间的相关系数衡量趋势线性程度，接近正负1表示强趋势，接近0为无序震荡。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — linear_correlation_oscillator

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.linear_correlation_oscillator(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.linear_correlation_oscillator(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['linear_regression_intensity'])
    def linear_regression_intensity(self, lookback_period: int = 12, range_tolerance: float = 90.0, linreg_length: int = 90, kernel: str | None = None, **kwargs) -> IndSeries:
        """线性回归强度 · linear_regression_intensity（统计）
        ---------
            结合回归斜率与区间容忍度评估趋势强度，数值越高表示趋势越稳定可靠。

        参数:
        ---------
            >>> lookback_period (int): 计算周期（K 线根数）. 默认: 12
            >>> range_tolerance (float): 原库参数（默认值见签名）. 默认: 90.0
            >>> linreg_length (int): 计算周期（K 线根数）. 默认: 90
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — linear_regression_intensity

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.linear_regression_intensity(lookback_period=12, range_tolerance=90.0, linreg_length=90, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.linear_regression_intensity(close, lookback_period=12, range_tolerance=90.0, linreg_length=90, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['linearreg_angle'])
    def linearreg_angle(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """线性回归角度 · linearreg_angle（趋势）
        ---------
            把回归斜率换算成角度，正值表示上行、负值表示下行，角度绝对值反映趋势陡峭度。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — linearreg_angle

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.linearreg_angle(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.linearreg_angle(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['linearreg_intercept'])
    def linearreg_intercept(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """线性回归截距 · linearreg_intercept（趋势）
        ---------
            回归直线的截距，反映回归窗口的基准价位，可与价格比较判断偏离程度。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — linearreg_intercept

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.linearreg_intercept(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.linearreg_intercept(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['linearreg_slope'])
    def linearreg_slope(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """线性回归斜率 · linearreg_slope（趋势）
        ---------
            回归直线的斜率，正值越大上行越快、负值越大下行越快，用于量化趋势方向与力度。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — linearreg_slope

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.linearreg_slope(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.linearreg_slope(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['linreg'])
    def linreg(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """线性回归线 · linreg（趋势）
        ---------
            窗口内的最小二乘回归值，作为平滑的趋势基准，价格在其上方偏多、下方偏空。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — linreg

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.linreg(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.linreg(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['maaq'])
    def maaq(self, period: int = 14, fast_period: int = 12, slow_period: int = 26, kernel: str | None = None, **kwargs) -> IndSeries:
        """自适应快慢均线 · maaq（趋势）
        ---------
            依据快慢周期差异自适应调整的均线，兼顾平滑与灵敏，用于顺势跟踪与买卖点参考。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> fast_period (int): 快线周期. 默认: 12
            >>> slow_period (int): 慢线周期. 默认: 26
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — maaq

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.maaq(period=14, fast_period=12, slow_period=26, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.maaq(close, period=14, fast_period=12, slow_period=26, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['mab_1', 'mab_2', 'mab_3'])
    def mab(self, fast_period: int = 12, slow_period: int = 26, devup: float = 1.0, devdn: float = 1.0, fast_ma_type: str = 'sma', slow_ma_type: str = 'sma', kernel: str | None = None, **kwargs) -> IndFrame:
        """均线带 · mab（趋势）
        ---------
            快慢均线加减偏离构成的通道，中轨判趋势方向，上下轨作突破或超买超卖参考。

        参数:
        ---------
            >>> fast_period (int): 快线周期. 默认: 12
            >>> slow_period (int): 慢线周期. 默认: 26
            >>> devup (float): 宽度 / 倍数系数. 默认: 1.0
            >>> devdn (float): 宽度 / 倍数系数. 默认: 1.0
            >>> fast_ma_type (str): 快线周期. 默认: 'sma'
            >>> slow_ma_type (str): 慢线周期. 默认: 'sma'
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — mab_1, mab_2, mab_3

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.mab(fast_period=12, slow_period=26, devup=1.0, devdn=1.0, fast_ma_type='sma', slow_ma_type='sma', kernel=None)    # 主图叠加
            >>> out.columns               # 线名: mab_1, mab_2, mab_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.mab(close, fast_period=12, slow_period=26, devup=1.0, devdn=1.0, fast_ma_type='sma', slow_ma_type='sma', kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['macd_wave_signal_pro_1', 'macd_wave_signal_pro_2', 'macd_wave_signal_pro_3', 'macd_wave_signal_pro_4'])
    def macd_wave_signal_pro(self, kernel: str | None = None, **kwargs) -> IndFrame:
        """MACD波信号 · macd_wave_signal_pro（动量）
        ---------
            在MACD基础上输出多条波峰波谷与信号线，用于识别动量转折、背离和入场时机。

        参数:
        ---------
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 4 条线 — macd_wave_signal_pro_1, macd_wave_signal_pro_2, macd_wave_signal_pro_3, macd_wave_signal_pro_4

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.macd_wave_signal_pro(kernel=None)    # 副图
            >>> out.columns               # 线名: macd_wave_signal_pro_1, macd_wave_signal_pro_2, macd_wave_signal_pro_3, macd_wave_signal_pro_4
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.macd_wave_signal_pro(open, high, low, close, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['market_meanness_index_1', 'market_meanness_index_2'])
    def market_meanness_index(self, length: int = 14, source_mode: str = 'Price', kernel: str | None = None, **kwargs) -> IndFrame:
        """市场均值回归指数 · market_meanness_index（统计）
        ---------
            统计相邻价格涨跌的一致性，数值越低越偏趋势、越高越适合均值回归思路。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> source_mode (str): 输入序列（默认取 close）. 默认: 'Price'
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — market_meanness_index_1, market_meanness_index_2

        数据:
        ---------
            >>> open, close

        使用案例:
        ---------
            >>> out = self.data.market_meanness_index(length=14, source_mode='Price', kernel=None)    # 副图
            >>> out.columns               # 线名: market_meanness_index_1, market_meanness_index_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.market_meanness_index(open, close, length=14, source_mode='Price', kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['marketefi'])
    def marketefi(self, kernel: str | None = None, **kwargs) -> IndSeries:
        """市场力度指数 · marketefi（成交量）
        ---------
            以价格变动乘以成交量衡量多空力量，正柱表示买盘主导、负柱表示卖压主导。

        参数:
        ---------
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — marketefi

        数据:
        ---------
            >>> high, low, volume

        使用案例:
        ---------
            >>> out = self.data.marketefi(kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.marketefi(high, low, volume, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['mass'])
    def mass(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """质量指数 · mass（波动率）
        ---------
            高低价区间平滑比值衡量反转风险，指标升破关键位常预示趋势见顶或见底。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — mass

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.mass(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.mass(high, low, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['mean_ad'])
    def mean_ad(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """平均累积派发线 · mean_ad（成交量）
        ---------
            累积派发线的均值平滑，反映资金净流方向，与价格同向确认趋势、背离提示转折。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — mean_ad

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.mean_ad(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.mean_ad(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['medium_ad'])
    def medium_ad(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """中期累积派发线 · medium_ad（成交量）
        ---------
            中期平滑的累积派发线，过滤短期噪声，用于观察资金净流向的中期变化。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — medium_ad

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.medium_ad(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.medium_ad(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['medprice'])
    def medprice(self, kernel: str | None = None, **kwargs) -> IndSeries:
        """中位价 · medprice（其他）
        ---------
            最高价与最低价的平均值，比收盘价更平滑地体现价格中枢，常作其他指标的输入。

        参数:
        ---------
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — medprice

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.medprice(kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.medprice(high, low, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['midpoint'])
    def midpoint(self, period: int | None = None, kernel: str | None = None, **kwargs) -> IndSeries:
        """中点价 · midpoint（其他）
        ---------
            窗口内最高价与最低价的中点，代表区间中枢，可作支撑阻力与通道中轨参考。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — midpoint

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.midpoint(period=None, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.midpoint(close, period=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['midprice'])
    def midprice(self, period: int = 20, kernel: str | None = None, **kwargs) -> IndSeries:
        """区间中价 · midprice（其他）
        ---------
            一段时间最高价与最低价均值构成的平滑线，用于判断价格相对区间中枢的位置。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — midprice

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.midprice(period=20, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.midprice(high, low, period=20, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['mod_god_mode_1', 'mod_god_mode_2', 'mod_god_mode_3'])
    def mod_god_mode(self, n1: str | None = None, n2: str | None = None, n3: str | None = None, mode: str | None = None, use_volume: str | None = None, kernel: str | None = None, **kwargs) -> IndFrame:
        """多周期趋势模式 · mod_god_mode（趋势）
        ---------
            综合多条不同周期均线判断趋势状态，多线同向确认方向，交叉错乱提示可能转向。

        参数:
        ---------
            >>> n1 (str): 原库参数（默认值见签名）. 默认: None
            >>> n2 (str): 原库参数（默认值见签名）. 默认: None
            >>> n3 (str): 原库参数（默认值见签名）. 默认: None
            >>> mode (str): 计算模式（原库枚举值）. 默认: None
            >>> use_volume (str): 原库参数（默认值见签名）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 3 条线 — mod_god_mode_1, mod_god_mode_2, mod_god_mode_3

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.mod_god_mode(n1=None, n2=None, n3=None, mode=None, use_volume=None, kernel=None)    # 副图
            >>> out.columns               # 线名: mod_god_mode_1, mod_god_mode_2, mod_god_mode_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.mod_god_mode(high, low, close, volume, n1=None, n2=None, n3=None, mode=None, use_volume=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['mom'])
    def mom(self, period: int = 10, kernel: str | None = None, **kwargs) -> IndSeries:
        """动量 · mom（动量）
        ---------
            当前价格与前若干周期价格的差值，正负与大小反映涨跌速度，零轴穿越可判动量转向。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 10
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — mom

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.mom(period=10, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.mom(close, period=10, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['momentum_ratio_oscillator_1', 'momentum_ratio_oscillator_2'])
    def momentum_ratio_oscillator(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndFrame:
        """动量比率振荡器 · momentum_ratio_oscillator（动量）
        ---------
            以正负动量之比构造的振荡器，高于零表示上行动量占优，低于零表示下行动量占优。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — momentum_ratio_oscillator_1, momentum_ratio_oscillator_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.momentum_ratio_oscillator(period=14, kernel=None)    # 副图
            >>> out.columns               # 线名: momentum_ratio_oscillator_1, momentum_ratio_oscillator_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.momentum_ratio_oscillator(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['msw_1', 'msw_2'])
    def msw(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndFrame:
        """Mesa正弦波 · msw（统计）
        ---------
            测量价格周期的相位与振幅，相位穿越可提前提示周期转折，用于择时与周期识别。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — msw_1, msw_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.msw(period=14, kernel=None)    # 副图
            >>> out.columns               # 线名: msw_1, msw_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.msw(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['mwdx'])
    def mwdx(self, factor: float = 0.5, kernel: str | None = None, **kwargs) -> IndSeries:
        """市场波方向指数 · mwdx（趋势）
        ---------
            结合方向性波幅判断趋势方向与强度，数值上行且与价格同向时趋势较为可靠。

        参数:
        ---------
            >>> factor (float): 灵敏度系数（宽度 / 阈值 / 加速步长）. 默认: 0.5
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — mwdx

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.mwdx(factor=0.5, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.mwdx(close, factor=0.5, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['nadaraya_watson_envelope_1', 'nadaraya_watson_envelope_2'])
    def nadaraya_watson_envelope(self, bandwidth: float = 8.0, multiplier: float = 3.0, lookback: int = 500, kernel: str | None = None, **kwargs) -> IndFrame:
        """NW核回归通道 · nadaraya_watson_envelope（趋势）
        ---------
            核回归平滑曲线加波动带构成，曲线作趋势基准，触及上下轨提示超买超卖或反转。

        参数:
        ---------
            >>> bandwidth (float): 带宽（平滑或通道宽度）. 默认: 8.0
            >>> multiplier (float): ATR / 标准差倍数（决定通道与止损宽度）. 默认: 3.0
            >>> lookback (int): 计算周期（K 线根数）. 默认: 500
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 2 条线 — nadaraya_watson_envelope_1, nadaraya_watson_envelope_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.nadaraya_watson_envelope(bandwidth=8.0, multiplier=3.0, lookback=500, kernel=None)    # 主图叠加
            >>> out.columns               # 线名: nadaraya_watson_envelope_1, nadaraya_watson_envelope_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.nadaraya_watson_envelope(close, bandwidth=8.0, multiplier=3.0, lookback=500, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['nama'])
    def nama(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """非滞后自适应均线 · nama（趋势）
        ---------
            用非滞后平滑算法贴近价格的均线，能更快反映拐点，用于趋势跟踪与止损参考。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — nama

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.nama(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.nama(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['natr'])
    def natr(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """归一化ATR · natr（波动率）
        ---------
            ATR除以收盘价得到的百分比波动率，便于跨品种比较波动大小与设定止损。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — natr

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.natr(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.natr(high, low, close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['nma'])
    def nma(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """自然均线 · nma（趋势）
        ---------
            对近期价格自然加权的平滑均线，趋势方向由其斜率体现，可作为动态支撑阻力。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — nma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.nma(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.nma(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['nonlinear_regression_zero_lag_moving_average_1', 'nonlinear_regression_zero_lag_moving_average_2'])
    def nonlinear_regression_zero_lag_moving_average(self, zlma_period: int = 15, regression_period: int = 15, kernel: str | None = None, **kwargs) -> IndFrame:
        """非线性回归零滞后均线 · nonlinear_regression_zero_lag_moving_average（趋势）
        ---------
            用非线性回归与零滞后均线组合，减少滞后并提前提示趋势变化，用于买卖点判断。

        参数:
        ---------
            >>> zlma_period (int): 计算周期（K 线根数）. 默认: 15
            >>> regression_period (int): 计算周期（K 线根数）. 默认: 15
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — nonlinear_regression_zero_lag_moving_average_1, nonlinear_regression_zero_lag_moving_average_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.nonlinear_regression_zero_lag_moving_average(zlma_period=15, regression_period=15, kernel=None)    # 副图
            >>> out.columns               # 线名: nonlinear_regression_zero_lag_moving_average_1, nonlinear_regression_zero_lag_moving_average_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.nonlinear_regression_zero_lag_moving_average(close, zlma_period=15, regression_period=15, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['normalized_volume_true_range_1', 'normalized_volume_true_range_2', 'normalized_volume_true_range_3', 'normalized_volume_true_range_4', 'normalized_volume_true_range_5'])
    def normalized_volume_true_range(self, true_range_style: str | None = None, outlier_range: str | None = None, atr_length: int | None = None, volume_length: int | None = None, **kwargs) -> IndFrame:
        """归一化量价波幅 · normalized_volume_true_range（波动率）
        ---------
            把真实波幅与成交量归一化后对比，量价同时放大趋势更可信，背离提示动能不足。

        参数:
        ---------
            >>> true_range_style (str): 原库参数（默认值见签名）. 默认: None
            >>> outlier_range (str): 原库参数（默认值见签名）. 默认: None
            >>> atr_length (int): ATR 计算周期. 默认: None
            >>> volume_length (int): 计算周期（K 线根数）. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 5 条线 — normalized_volume_true_range_1, normalized_volume_true_range_2, normalized_volume_true_range_3, normalized_volume_true_range_4, normalized_volume_true_range_5

        数据:
        ---------
            >>> open, high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.normalized_volume_true_range(true_range_style=None, outlier_range=None, atr_length=None, volume_length=None)    # 副图
            >>> out.columns               # 线名: normalized_volume_true_range_1, normalized_volume_true_range_2, normalized_volume_true_range_3, normalized_volume_true_range_4, normalized_volume_true_range_5
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.normalized_volume_true_range(open, high, low, close, volume, true_range_style=None, outlier_range=None, atr_length=None, volume_length=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['nvi'])
    def nvi(self, kernel: str | None = None, **kwargs) -> IndSeries:
        """负成交量指数 · nvi（成交量）
        ---------
            仅在成交量萎缩日累积价格变化，用于跟踪主力资金的长期累积与派发。

        参数:
        ---------
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — nvi

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.nvi(kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.nvi(close, volume, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['obv'])
    def obv(self, kernel: str | None = None, **kwargs) -> IndSeries:
        """能量潮OBV · obv（成交量）
        ---------
            按涨跌方向累加成交量，与价格同向时确认趋势，出现背离时提示趋势可能反转。

        参数:
        ---------
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — obv

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.obv(kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.obv(close, volume, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['on_balance_volume_oscillator_1', 'on_balance_volume_oscillator_2'])
    def on_balance_volume_oscillator(self, obv_length: int = 20, ema_length: int = 9, kernel: str | None = None, **kwargs) -> IndFrame:
        """OBV振荡器 · on_balance_volume_oscillator（成交量）
        ---------
            OBV相对其均线的偏离与信号线比较，柱体正负反映资金流入流出的强弱变化。

        参数:
        ---------
            >>> obv_length (int): 计算周期（K 线根数）. 默认: 20
            >>> ema_length (int): EMA 周期. 默认: 9
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — on_balance_volume_oscillator_1, on_balance_volume_oscillator_2

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.on_balance_volume_oscillator(obv_length=20, ema_length=9, kernel=None)    # 副图
            >>> out.columns               # 线名: on_balance_volume_oscillator_1, on_balance_volume_oscillator_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.on_balance_volume_oscillator(close, volume, obv_length=20, ema_length=9, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ott'])
    def ott(self, period: int = 14, percent: float = 0.1, ma_type: str = 'VAR', kernel: str | None = None, **kwargs) -> IndSeries:
        """优化趋势跟踪线 · ott（趋势）
        ---------
            基于均线并按百分比调节的趋势跟踪线，价格站上偏多、跌破偏空，可作止盈止损。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> percent (float): 比例阈值（小数，0.1 = 10%）. 默认: 0.1
            >>> ma_type (str): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 'VAR'
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ott

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ott(period=14, percent=0.1, ma_type='VAR', kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ott(close, period=14, percent=0.1, ma_type='VAR', kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['parkinson_volatility_1', 'parkinson_volatility_2'])
    def parkinson_volatility(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndFrame:
        """Parkinson波动率 · parkinson_volatility（波动率）
        ---------
            仅用最高最低价估计的波动率，对日内振幅敏感，数值走高表示波动扩大。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — parkinson_volatility_1, parkinson_volatility_2

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.parkinson_volatility(period=14, kernel=None)    # 副图
            >>> out.columns               # 线名: parkinson_volatility_1, parkinson_volatility_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.parkinson_volatility(high, low, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['percentile_nearest_rank'])
    def percentile_nearest_rank(self, length: int = 14, percentage: float = 50.0, kernel: str | None = None, **kwargs) -> IndSeries:
        """最近秩百分位 · percentile_nearest_rank（统计）
        ---------
            取窗口内价格的指定百分位值，用于构造分位支撑阻力或评估当前价格的相对位置。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> percentage (float): 比例阈值（小数，0.1 = 10%）. 默认: 50.0
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — percentile_nearest_rank

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.percentile_nearest_rank(length=14, percentage=50.0, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.percentile_nearest_rank(close, length=14, percentage=50.0, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['pivot_1', 'pivot_2', 'pivot_3', 'pivot_4', 'pivot_5', 'pivot_6', 'pivot_7', 'pivot_8', 'pivot_9'])
    def pivot(self, mode: int = 3, kernel: str | None = None, **kwargs) -> IndFrame:
        """枢轴点 · pivot（其他）
        ---------
            由上一根K线计算枢轴及多级支撑阻力位，用于判断关键价位与潜在转折区域。

        参数:
        ---------
            >>> mode (int): 计算模式（原库枚举值）. 默认: 3
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 9 条线 — pivot_1, pivot_2, pivot_3, pivot_4, pivot_5, pivot_6, pivot_7, pivot_8, pivot_9

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.pivot(mode=3, kernel=None)    # 主图叠加
            >>> out.columns               # 线名: pivot_1, pivot_2, pivot_3, pivot_4, pivot_5, pivot_6, pivot_7, pivot_8, pivot_9
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.pivot(open, high, low, close, mode=3, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['pma_1', 'pma_2'])
    def pma(self, kernel: str | None = None, **kwargs) -> IndFrame:
        """价格平滑均线 · pma（趋势）
        ---------
            对价格做平滑处理得到的均线，方向与斜率用于判断趋势，可作支撑阻力参考。

        参数:
        ---------
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — pma_1, pma_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.pma(kernel=None)    # 副图
            >>> out.columns               # 线名: pma_1, pma_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.pma(close, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['possible_rsi_1', 'possible_rsi_2', 'possible_rsi_3', 'possible_rsi_4'])
    def possible_rsi(self, period: int = 14, rsi_mode: str = 'regular', norm_period: int = 100, normalization_mode: str = 'gaussian_fisher', normalization_length: int = 15, nonlag_period: int = 15, dynamic_zone_period: int = 20, buy_probability: float = 0.2, sell_probability: float = 0.2, signal_type: str = 'zeroline_crossover', run_highpass: bool = False, highpass_period: int = 15, kernel: str | None = None, **kwargs) -> IndFrame:
        """概率化RSI · possible_rsi（动量）
        ---------
            把RSI经归一化与概率映射后给出买卖区与信号，用于量化超买超卖与入场概率。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> rsi_mode (str): 对应子指标的周期（原库同名参数）. 默认: 'regular'
            >>> norm_period (int): 计算周期（K 线根数）. 默认: 100
            >>> normalization_mode (str): 原库参数（默认值见签名）. 默认: 'gaussian_fisher'
            >>> normalization_length (int): 计算周期（K 线根数）. 默认: 15
            >>> nonlag_period (int): 计算周期（K 线根数）. 默认: 15
            >>> dynamic_zone_period (int): 计算周期（K 线根数）. 默认: 20
            >>> buy_probability (float): 原库参数（默认值见签名）. 默认: 0.2
            >>> sell_probability (float): 原库参数（默认值见签名）. 默认: 0.2
            >>> signal_type (str): 信号线平滑周期. 默认: 'zeroline_crossover'
            >>> run_highpass (bool): 原库参数（默认值见签名）. 默认: False
            >>> highpass_period (int): 计算周期（K 线根数）. 默认: 15
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 4 条线 — possible_rsi_1, possible_rsi_2, possible_rsi_3, possible_rsi_4

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.possible_rsi(period=14, rsi_mode='regular', norm_period=100, normalization_mode='gaussian_fisher', normalization_length=15, nonlag_period=15, dynamic_zone_period=20, buy_probability=0.2, sell_probability=0.2, signal_type='zeroline_crossover', run_highpass=False, highpass_period=15, kernel=None)    # 副图
            >>> out.columns               # 线名: possible_rsi_1, possible_rsi_2, possible_rsi_3, possible_rsi_4
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.possible_rsi(close, period=14, rsi_mode='regular', norm_period=100, normalization_mode='gaussian_fisher', normalization_length=15, nonlag_period=15, dynamic_zone_period=20, buy_probability=0.2, sell_probability=0.2, signal_type='zeroline_crossover', run_highpass=False, highpass_period=15, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ppo'])
    def ppo(self, fast_period: int | None = None, slow_period: int | None = None, ma_type: str | None = None, kernel: str | None = None, **kwargs) -> IndSeries:
        """百分比价格振荡器 · ppo（动量）
        ---------
            快慢均线的百分比差值，类似MACD但可跨品种比较，正负与穿越反映动量强弱。

        参数:
        ---------
            >>> fast_period (int): 快线周期. 默认: None
            >>> slow_period (int): 慢线周期. 默认: None
            >>> ma_type (str): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ppo

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ppo(fast_period=None, slow_period=None, ma_type=None, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ppo(close, fast_period=None, slow_period=None, ma_type=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['premier_rsi_oscillator'])
    def premier_rsi_oscillator(self, rsi_length: int | None = None, stoch_length: int | None = None, smooth_length: int | None = None, kernel: str | None = None, **kwargs) -> IndSeries:
        """优选RSI振荡器 · premier_rsi_oscillator（动量）
        ---------
            RSI再经随机化与平滑处理的振荡器，减少钝化，超买超卖与交叉用于短线择时。

        参数:
        ---------
            >>> rsi_length (int): RSI 计算周期. 默认: None
            >>> stoch_length (int): 计算周期（K 线根数）. 默认: None
            >>> smooth_length (int): 平滑周期. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — premier_rsi_oscillator

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.premier_rsi_oscillator(rsi_length=None, stoch_length=None, smooth_length=None, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.premier_rsi_oscillator(close, rsi_length=None, stoch_length=None, smooth_length=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['pretty_good_oscillator'])
    def pretty_good_oscillator(self, length: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """PGO振荡器 · pretty_good_oscillator（动量）
        ---------
            以均线偏离标准差归一的振荡器，衡量价格相对趋势的偏离程度，极值提示回归风险。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — pretty_good_oscillator

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.pretty_good_oscillator(length=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.pretty_good_oscillator(high, low, close, length=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['price_density_market_noise_1', 'price_density_market_noise_2'])
    def price_density_market_noise(self, length: int = 14, eval_period: int = 200, kernel: str | None = None, **kwargs) -> IndFrame:
        """价格密度噪声 · price_density_market_noise（统计）
        ---------
            用价格在区间内的分布密度衡量市场噪声，噪声高时信号易失真，低时趋势更清晰。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> eval_period (int): 计算周期（K 线根数）. 默认: 200
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — price_density_market_noise_1, price_density_market_noise_2

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.price_density_market_noise(length=14, eval_period=200, kernel=None)    # 副图
            >>> out.columns               # 线名: price_density_market_noise_1, price_density_market_noise_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.price_density_market_noise(high, low, close, length=14, eval_period=200, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['projection_oscillator_1', 'projection_oscillator_2'])
    def projection_oscillator(self, length: int = 14, smooth_length: int = 4, kernel: str | None = None, **kwargs) -> IndFrame:
        """投影振荡器 · projection_oscillator（动量）
        ---------
            基于线性回归斜率与均线构造的振荡器，柱体与信号线交叉反映趋势动量变化。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> smooth_length (int): 平滑周期. 默认: 4
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — projection_oscillator_1, projection_oscillator_2

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.projection_oscillator(length=14, smooth_length=4, kernel=None)    # 副图
            >>> out.columns               # 线名: projection_oscillator_1, projection_oscillator_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.projection_oscillator(high, low, close, length=14, smooth_length=4, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['psychological_line'])
    def psychological_line(self, length: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """心理线 · psychological_line（动量）
        ---------
            统计窗口内上涨周期占比，反映市场看多心理；数值过高易回调，过低易反弹。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — psychological_line

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.psychological_line(length=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.psychological_line(close, length=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['pvi'])
    def pvi(self, initial_value: str | None = None, kernel: str | None = None, **kwargs) -> IndSeries:
        """正成交量指标 · pvi（成交量）
        ---------
            仅在成交量放大时按涨幅累积的指数。与价格走势背离时提示量能不足或资金异动，
            用于验证趋势真伪。

        参数:
        ---------
            >>> initial_value (str): 原库参数（默认值见签名）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — pvi

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.pvi(initial_value=None, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.pvi(close, volume, initial_value=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['pwma'])
    def pwma(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """帕斯卡加权均线 · pwma（趋势）
        ---------
            以帕斯卡三角分布加权的移动平均，中间权重最高。曲线平滑、滞后适中，用于判断趋势方向与支撑阻力。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — pwma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.pwma(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.pwma(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['qqe_1', 'qqe_2'])
    def qqe(self, rsi_period: int = 14, smoothing_factor: int = 5, fast_factor: float = 4.236, kernel: str | None = None, **kwargs) -> IndFrame:
        """定量定性估算 · qqe（动量）
        ---------
            平滑RSI与其ATR通道信号线组成。两线交叉及穿越50中轴可判断动量转折，越界处提示超买超卖。

        参数:
        ---------
            >>> rsi_period (int): RSI 计算周期. 默认: 14
            >>> smoothing_factor (int): 平滑周期. 默认: 5
            >>> fast_factor (float): 快线周期. 默认: 4.236
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — qqe_1, qqe_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.qqe(rsi_period=14, smoothing_factor=5, fast_factor=4.236, kernel=None)    # 副图
            >>> out.columns               # 线名: qqe_1, qqe_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.qqe(close, rsi_period=14, smoothing_factor=5, fast_factor=4.236, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['qstick'])
    def qstick(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """Q棒指标 · qstick（动量）
        ---------
            取收盘与开盘差值的均值，衡量多空实体力量对比。零轴上方偏多、下方偏空，穿越零轴为交易信号。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — qstick

        数据:
        ---------
            >>> open, close

        使用案例:
        ---------
            >>> out = self.data.qstick(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.qstick(open, close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['range_filter_1', 'range_filter_2', 'range_filter_3'])
    def range_filter(self, range_size: float = 2.618, range_period: int = 14, smooth_range: bool = True, smooth_period: int = 27, kernel: str | None = None, **kwargs) -> IndFrame:
        """区间过滤线 · range_filter（趋势）
        ---------
            用波动幅度构造上下轨并输出过滤后的趋势线。价格突破上轨或下轨确认趋势反转，
            适合跟踪主趋势。

        参数:
        ---------
            >>> range_size (float): 原库参数（默认值见签名）. 默认: 2.618
            >>> range_period (int): 计算周期（K 线根数）. 默认: 14
            >>> smooth_range (bool): 平滑周期. 默认: True
            >>> smooth_period (int): 平滑周期. 默认: 27
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — range_filter_1, range_filter_2, range_filter_3

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.range_filter(range_size=2.618, range_period=14, smooth_range=True, smooth_period=27, kernel=None)    # 主图叠加
            >>> out.columns               # 线名: range_filter_1, range_filter_2, range_filter_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.range_filter(close, range_size=2.618, range_period=14, smooth_range=True, smooth_period=27, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['rank_correlation_index'])
    def rank_correlation_index(self, length: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """秩相关指数 · rank_correlation_index（统计）
        ---------
            价格与时间的秩相关系数，衡量趋势的单调性与强度。接近±1表示趋势稳健，接近0表示震荡无序。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rank_correlation_index

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.rank_correlation_index(length=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.rank_correlation_index(close, length=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['reflex'])
    def reflex(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """反射指标 · reflex（动量）
        ---------
            以回归斜率平滑价格后取差分，反映趋势加速度。上穿零轴看多、下穿零轴看空，
            反应较为灵敏。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — reflex

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.reflex(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.reflex(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['roc'])
    def roc(self, period: int = 10, kernel: str | None = None, **kwargs) -> IndSeries:
        """变动率 · roc（动量）
        ---------
            当前价相对N周期前价格的百分比变化，衡量动量速度。上穿零轴偏多，数值极端时提示超买超卖。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 10
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — roc

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.roc(period=10, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.roc(close, period=10, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['rocp'])
    def rocp(self, period: int = 10, kernel: str | None = None, **kwargs) -> IndSeries:
        """变动率百分比 · rocp（动量）
        ---------
            价格变化量除以前期价格，即相对涨幅的比例。数值反映动量强弱，便于跨品种比较趋势力度。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 10
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rocp

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.rocp(period=10, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.rocp(close, period=10, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['rocr'])
    def rocr(self, period: int = 10, kernel: str | None = None, **kwargs) -> IndSeries:
        """变动率比率 · rocr（动量）
        ---------
            当前价除以前N周期价格。大于1表示上涨、小于1表示下跌，用于判断相对动量与趋势方向。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 10
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rocr

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.rocr(period=10, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.rocr(close, period=10, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['rogers_satchell_volatility_1', 'rogers_satchell_volatility_2'])
    def rogers_satchell_volatility(self, lookback: int = 8, signal_length: int = 8, kernel: str | None = None, **kwargs) -> IndFrame:
        """罗杰斯-萨切尔波动率 · rogers_satchell_volatility（波动率）
        ---------
            基于开高低收的漂移无关波动率估计。数值走高代表波动加剧，与信号线比较可判断波动趋势变化。

        参数:
        ---------
            >>> lookback (int): 计算周期（K 线根数）. 默认: 8
            >>> signal_length (int): 信号线平滑周期. 默认: 8
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — rogers_satchell_volatility_1, rogers_satchell_volatility_2

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.rogers_satchell_volatility(lookback=8, signal_length=8, kernel=None)    # 副图
            >>> out.columns               # 线名: rogers_satchell_volatility_1, rogers_satchell_volatility_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.rogers_satchell_volatility(open, high, low, close, lookback=8, signal_length=8, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['rolling_skewness_kurtosis_1', 'rolling_skewness_kurtosis_2'])
    def rolling_skewness_kurtosis(self, length: int = 14, smooth_length: int = 3, kernel: str | None = None, **kwargs) -> IndFrame:
        """滚动偏度与峰度 · rolling_skewness_kurtosis（统计）
        ---------
            滚动窗口内收益分布的偏度与峰度。偏度反映涨跌不对称，峰度反映极端行情概率，
            用于评估风险形态。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> smooth_length (int): 平滑周期. 默认: 3
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — rolling_skewness_kurtosis_1, rolling_skewness_kurtosis_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.rolling_skewness_kurtosis(length=14, smooth_length=3, kernel=None)    # 副图
            >>> out.columns               # 线名: rolling_skewness_kurtosis_1, rolling_skewness_kurtosis_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.rolling_skewness_kurtosis(close, length=14, smooth_length=3, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['rolling_z_score_trend_1', 'rolling_z_score_trend_2'])
    def rolling_z_score_trend(self, lookback_period: int = 20, kernel: str | None = None, **kwargs) -> IndFrame:
        """滚动Z分趋势 · rolling_z_score_trend（统计）
        ---------
            价格相对滚动均值的标准化偏离及其平滑趋势。偏离越大越极端，可用于均值回归或趋势跟踪判断。

        参数:
        ---------
            >>> lookback_period (int): 计算周期（K 线根数）. 默认: 20
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — rolling_z_score_trend_1, rolling_z_score_trend_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.rolling_z_score_trend(lookback_period=20, kernel=None)    # 副图
            >>> out.columns               # 线名: rolling_z_score_trend_1, rolling_z_score_trend_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.rolling_z_score_trend(close, lookback_period=20, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['rsi'])
    def rsi(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """相对强弱指标 · rsi（动量）
        ---------
            基于平均涨跌幅的0至100振荡指标。70以上超买、30以下超卖，也常观察中轴穿越与背离。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rsi

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.rsi(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.rsi(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['rsx'])
    def rsx(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """平滑相对强弱指标 · rsx（动量）
        ---------
            经多级平滑处理的RSI，噪声更少、拐点更圆滑。用法类似RSI，可判断超买超卖与动量转向。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — rsx

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.rsx(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.rsx(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['sar'])
    def sar(self, acceleration: str | None = None, maximum: str | None = None, kernel: str | None = None, **kwargs) -> IndSeries:
        """抛物线转向 · sar（趋势）
        ---------
            随价格加速移动的止损点序列。点位在价格下方为多头、上方为空头，被价格穿越时提示趋势反转。

        参数:
        ---------
            >>> acceleration (str): 抛物线加速因子（起步步长，SA 的 0.02）. 默认: None
            >>> maximum (str): 抛物线加速因子上限（SA 的 0.2）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — sar

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.sar(acceleration=None, maximum=None, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.sar(high, low, acceleration=None, maximum=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['sgf'])
    def sgf(self, period: int = 14, poly_order: int = 2, kernel: str | None = None, **kwargs) -> IndSeries:
        """萨维茨基-戈莱滤波 · sgf（趋势）
        ---------
            多项式最小二乘平滑滤波，去噪同时保留峰谷形态。可提取平滑趋势，斜率变化反映方向与拐点。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> poly_order (int): 原库参数（默认值见签名）. 默认: 2
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — sgf

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.sgf(period=14, poly_order=2, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.sgf(close, period=14, poly_order=2, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['sinwma'])
    def sinwma(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """正弦加权均线 · sinwma（趋势）
        ---------
            以正弦权重加权的移动平均，中心权重较高。平滑价格的同时对近期变化较敏感，
            用于判断趋势方向。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — sinwma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.sinwma(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.sinwma(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['sma'])
    def sma(self, period: int = 20, kernel: str | None = None, **kwargs) -> IndSeries:
        """简单移动平均 · sma（趋势）
        ---------
            N周期算术平均价。价格在其上方偏多、下方偏空，常作趋势基准，并配合多均线交叉产生信号。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — sma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.sma(period=20, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.sma(close, period=20, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['smma'])
    def smma(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """平滑移动平均 · smma（趋势）
        ---------
            Wilder式递推平滑均线，对新数据反应较慢。可有效过滤噪声，适合跟踪中长期趋势与止损参考。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — smma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.smma(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.smma(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['squeeze_momentum_2', 'squeeze_momentum_3'])
    def squeeze_momentum(self, length_bb: int = 20, mult_bb: float = 2.0, length_kc: int = 20, mult_kc: float = 1.5, kernel: str | None = None, **kwargs) -> IndFrame:
        """挤压动量 · squeeze_momentum（动量）
        ---------
            用布林带与肯特纳通道判断波动挤压，配合动量柱显示方向。挤压释放后的动量强弱预示突破行情。

        参数:
        ---------
            >>> length_bb (int): 计算周期（K 线根数）. 默认: 20
            >>> mult_bb (float): 宽度 / 倍数系数. 默认: 2.0
            >>> length_kc (int): 计算周期（K 线根数）. 默认: 20
            >>> mult_kc (float): 宽度 / 倍数系数. 默认: 1.5
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — squeeze_momentum_2, squeeze_momentum_3

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.squeeze_momentum(length_bb=20, mult_bb=2.0, length_kc=20, mult_kc=1.5, kernel=None)    # 副图
            >>> out.columns               # 线名: squeeze_momentum_2, squeeze_momentum_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.squeeze_momentum(high, low, close, length_bb=20, mult_bb=2.0, length_kc=20, mult_kc=1.5, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['sqwma'])
    def sqwma(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """平方加权均线 · sqwma（趋势）
        ---------
            权重按平方递增的加权均线，更强调近期价格。比线性加权更灵敏，用于较快跟踪趋势变化。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — sqwma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.sqwma(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.sqwma(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['srwma'])
    def srwma(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """平方根加权均线 · srwma（趋势）
        ---------
            权重按平方根递增的加权均线，灵敏度介于简单与线性加权之间。兼顾平滑与响应，
            用于判断趋势。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — srwma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.srwma(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.srwma(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['stc'])
    def stc(self, fast_period: int = 12, slow_period: int = 26, k_period: int = 14, d_period: int = 3, fast_ma_type: str = 'ema', slow_ma_type: str = 'ema', kernel: str | None = None, **kwargs) -> IndSeries:
        """沙夫趋势周期 · stc（动量）
        ---------
            对MACD做双重随机化的0至100周期指标。上穿25偏多、下穿75偏空，擅长识别趋势拐点。

        参数:
        ---------
            >>> fast_period (int): 快线周期. 默认: 12
            >>> slow_period (int): 慢线周期. 默认: 26
            >>> k_period (int): K 线平滑周期. 默认: 14
            >>> d_period (int): D 线平滑周期. 默认: 3
            >>> fast_ma_type (str): 快线周期. 默认: 'ema'
            >>> slow_ma_type (str): 慢线周期. 默认: 'ema'
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — stc

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.stc(fast_period=12, slow_period=26, k_period=14, d_period=3, fast_ma_type='ema', slow_ma_type='ema', kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.stc(close, fast_period=12, slow_period=26, k_period=14, d_period=3, fast_ma_type='ema', slow_ma_type='ema', kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['k', 'd'])
    def stoch(self, fastk_period: int = 14, slowk_period: int = 3, slowk_ma_type: str = 'sma', slowd_period: int = 3, slowd_ma_type: str = 'sma', kernel: str | None = None, **kwargs) -> IndFrame:
        """随机指标 · stoch（动量）
        ---------
            收盘价在N周期高低区间中的相对位置，输出K、D两线。K上穿D为买入信号，80以上超买、
            20以下超卖。

        参数:
        ---------
            >>> fastk_period (int): K 线平滑周期. 默认: 14
            >>> slowk_period (int): 计算周期（K 线根数）. 默认: 3
            >>> slowk_ma_type (str): 慢线周期. 默认: 'sma'
            >>> slowd_period (int): 计算周期（K 线根数）. 默认: 3
            >>> slowd_ma_type (str): 慢线周期. 默认: 'sma'
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — k, d

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.stoch(fastk_period=14, slowk_period=3, slowk_ma_type='sma', slowd_period=3, slowd_ma_type='sma', kernel=None)    # 副图
            >>> out.columns               # 线名: k, d
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.stoch(high, low, close, fastk_period=14, slowk_period=3, slowk_ma_type='sma', slowd_period=3, slowd_ma_type='sma', kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['k', 'd'])
    def stochastic_connors_rsi(self, stoch_length: int = 3, smooth_k: int = 3, smooth_d: int = 3, rsi_length: int = 3, updown_length: int = 2, roc_length: int = 100, kernel: str | None = None, **kwargs) -> IndFrame:
        """随机化康纳斯RSI · stochastic_connors_rsi（动量）
        ---------
            对康纳斯RSI再做随机化得到K、D线。对短期超买超卖更敏感，适合短周期反转与择时。

        参数:
        ---------
            >>> stoch_length (int): 计算周期（K 线根数）. 默认: 3
            >>> smooth_k (int): 平滑周期. 默认: 3
            >>> smooth_d (int): 平滑周期. 默认: 3
            >>> rsi_length (int): RSI 计算周期. 默认: 3
            >>> updown_length (int): 计算周期（K 线根数）. 默认: 2
            >>> roc_length (int): 对应子指标的周期（原库同名参数）. 默认: 100
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — k, d

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.stochastic_connors_rsi(stoch_length=3, smooth_k=3, smooth_d=3, rsi_length=3, updown_length=2, roc_length=100, kernel=None)    # 副图
            >>> out.columns               # 线名: k, d
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.stochastic_connors_rsi(close, stoch_length=3, smooth_k=3, smooth_d=3, rsi_length=3, updown_length=2, roc_length=100, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['k', 'd'])
    def stochastic_money_flow_index(self, stoch_k_length: int = 14, stoch_k_smooth: int = 3, stoch_d_smooth: int = 3, mfi_length: int = 14, kernel: str | None = None, **kwargs) -> IndFrame:
        """随机化资金流量 · stochastic_money_flow_index（动量）
        ---------
            对资金流量指标MFI做随机化处理，输出K、D线。结合价与量判断超买超卖及资金强弱变化。

        参数:
        ---------
            >>> stoch_k_length (int): 计算周期（K 线根数）. 默认: 14
            >>> stoch_k_smooth (int): 平滑周期. 默认: 3
            >>> stoch_d_smooth (int): 平滑周期. 默认: 3
            >>> mfi_length (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — k, d

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.stochastic_money_flow_index(stoch_k_length=14, stoch_k_smooth=3, stoch_d_smooth=3, mfi_length=14, kernel=None)    # 副图
            >>> out.columns               # 线名: k, d
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.stochastic_money_flow_index(close, volume, stoch_k_length=14, stoch_k_smooth=3, stoch_d_smooth=3, mfi_length=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['k', 'd'])
    def stochf(self, fastk_period: int | None = None, fastd_period: int | None = None, fastd_matype: str | None = None, kernel: str | None = None, **kwargs) -> IndFrame:
        """快速随机指标 · stochf（动量）
        ---------
            未做慢速平滑的随机K、D线，反应灵敏但噪声较多。用于捕捉短线动量变化与快速反转。

        参数:
        ---------
            >>> fastk_period (int): K 线平滑周期. 默认: None
            >>> fastd_period (int): D 线平滑周期. 默认: None
            >>> fastd_matype (str): D 线均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — k, d

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.stochf(fastk_period=None, fastd_period=None, fastd_matype=None, kernel=None)    # 副图
            >>> out.columns               # 线名: k, d
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.stochf(high, low, close, fastk_period=None, fastd_period=None, fastd_matype=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['supersmoother'])
    def supersmoother(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """超平滑滤波线 · supersmoother（趋势）
        ---------
            两极点超平滑滤波，滞后小而噪声低。曲线斜率转向常作为趋势转折的早期提示。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — supersmoother

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.supersmoother(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.supersmoother(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['supersmoother_3_pole'])
    def supersmoother_3_pole(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """三极点超平滑滤波线 · supersmoother_3_pole（趋势）
        ---------
            三极点版本更平滑、滞后略大，噪声抑制更强。适合跟踪平缓的中长期趋势与判断拐点。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — supersmoother_3_pole

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.supersmoother_3_pole(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.supersmoother_3_pole(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['supertrend_1'])
    def supertrend(self, period: int = 14, factor: float = 0.5, kernel: str | None = None, **kwargs) -> IndSeries:
        """超级趋势 · supertrend（趋势）
        ---------
            基于ATR的通道式趋势线，线在价格下方为多头、上方为空头。翻向即趋势反转信号，
            可直接作止损。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> factor (float): 灵敏度系数（宽度 / 阈值 / 加速步长）. 默认: 0.5
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — supertrend_1

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.supertrend(period=14, factor=0.5, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.supertrend(high, low, close, period=14, factor=0.5, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['swma'])
    def swma(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """对称加权均线 · swma（趋势）
        ---------
            按对称权重（如1-2-2-1）加权的移动平均，平滑且无明显滞后偏向。用于判断趋势方向与支撑阻力。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — swma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.swma(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.swma(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['tema'])
    def tema(self, period: int = 20, kernel: str | None = None, **kwargs) -> IndSeries:
        """三重指数均线 · tema（趋势）
        ---------
            三次EMA组合以降低滞后，比EMA更贴近价格。趋势拐点出现更早，但需防震荡中的假信号。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — tema

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.tema(period=20, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.tema(close, period=20, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['tilson'])
    def tilson(self, period: int = 14, volume_factor: str | None = None, kernel: str | None = None, **kwargs) -> IndSeries:
        """蒂尔森T3均线 · tilson（趋势）
        ---------
            T3多重EMA平滑并可叠加成交量因子，曲线顺滑且滞后小。可作趋势跟踪线与均线交叉依据。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> volume_factor (str): 宽度 / 倍数系数. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — tilson

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.tilson(period=14, volume_factor=None, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.tilson(close, period=14, volume_factor=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['trend_continuation_factor_1', 'trend_continuation_factor_2'])
    def trend_continuation_factor(self, length: int = 14, kernel: str | None = None, **kwargs) -> IndFrame:
        """趋势延续因子 · trend_continuation_factor（趋势）
        ---------
            衡量趋势持续性的因子及其信号线。数值抬升表示趋势仍在延续，转折向下提示趋势可能衰竭。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — trend_continuation_factor_1, trend_continuation_factor_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.trend_continuation_factor(length=14, kernel=None)    # 副图
            >>> out.columns               # 线名: trend_continuation_factor_1, trend_continuation_factor_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.trend_continuation_factor(close, length=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['trend_direction_force_index'])
    def trend_direction_force_index(self, length: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """趋势方向力指数 · trend_direction_force_index（趋势）
        ---------
            结合价格方向与波动力度评估趋势力量。正值多头占优、负值空头占优，可用于过滤逆势交易。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — trend_direction_force_index

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.trend_direction_force_index(length=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.trend_direction_force_index(close, length=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['trend_follower'])
    def trend_follower(self, matype: str = 'ema', trend_period: int = 20, ma_period: int = 20, channel_rate_percent: float = 1.0, use_linear_regression: bool = True, linear_regression_period: int = 5, kernel: str | None = None, **kwargs) -> IndSeries:
        """趋势跟随线 · trend_follower（趋势）
        ---------
            以均线叠加百分比通道构建的趋势跟随线。价格在线上方偏多、下方偏空，适合中期顺势持仓。

        参数:
        ---------
            >>> matype (str): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 'ema'
            >>> trend_period (int): 计算周期（K 线根数）. 默认: 20
            >>> ma_period (int): 计算周期（K 线根数）. 默认: 20
            >>> channel_rate_percent (float): 比例阈值（小数，0.1 = 10%）. 默认: 1.0
            >>> use_linear_regression (bool): 原库参数（默认值见签名）. 默认: True
            >>> linear_regression_period (int): 计算周期（K 线根数）. 默认: 5
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — trend_follower

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.trend_follower(matype='ema', trend_period=20, ma_period=20, channel_rate_percent=1.0, use_linear_regression=True, linear_regression_period=5, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.trend_follower(high, low, close, volume, matype='ema', trend_period=20, ma_period=20, channel_rate_percent=1.0, use_linear_regression=True, linear_regression_period=5, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['trend_trigger_factor'])
    def trend_trigger_factor(self, length: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """趋势触发因子 · trend_trigger_factor（趋势）
        ---------
            依据波动幅度计算趋势触发阈值。价格突破触发线时确认趋势启动或结束，用于择时进出场。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — trend_trigger_factor

        数据:
        ---------
            >>> high, low

        使用案例:
        ---------
            >>> out = self.data.trend_trigger_factor(length=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.trend_trigger_factor(high, low, length=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['trendflex'])
    def trendflex(self, period: int | None = None, kernel: str | None = None, **kwargs) -> IndSeries:
        """趋势柔性指标 · trendflex（趋势）
        ---------
            对价格变化做加权平滑得到的柔性趋势线。上穿零轴偏多、下穿偏空，对趋势反转较灵敏。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — trendflex

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.trendflex(period=None, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.trendflex(close, period=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['trima'])
    def trima(self, period: int = 20, kernel: str | None = None, **kwargs) -> IndSeries:
        """三角移动平均 · trima（趋势）
        ---------
            权重呈三角分布的移动平均，双重平滑、噪声低。曲线圆滑，适合判断中长期趋势与支撑阻力。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — trima

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.trima(period=20, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.trima(close, period=20, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['trix'])
    def trix(self, period: int = 10, kernel: str | None = None, **kwargs) -> IndSeries:
        """三重指数平滑均值 · trix（动量）
        ---------
            三重EMA平滑后的变化率，反映长期动量。上穿零轴偏多、下穿偏空，与价格背离可预警反转。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 10
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — trix

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.trix(period=10, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.trix(close, period=10, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['tsf'])
    def tsf(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """时间序列预测 · tsf（趋势）
        ---------
            线性回归外推得到的下一期预测值，兼具趋势线作用。价格在其上方表示上升趋势，
            下方反之。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — tsf

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.tsf(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.tsf(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['tsi'])
    def tsi(self, long_period: int = 26, short_period: int = 12, kernel: str | None = None, **kwargs) -> IndSeries:
        """真实强弱指标 · tsi（动量）
        ---------
            双重平滑的价格动量占比，取值约在正负100之间。零轴穿越判多空，绝对值过大提示超买超卖。

        参数:
        ---------
            >>> long_period (int): 长周期. 默认: 26
            >>> short_period (int): 短周期. 默认: 12
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — tsi

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.tsi(long_period=26, short_period=12, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.tsi(close, long_period=26, short_period=12, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ttm_squeeze_1', 'ttm_squeeze_2'])
    def ttm_squeeze(self, length: int = 14, bb_mult: float = 2.0, kc_mult_high: float = 1.0, kc_mult_mid: float = 1.5, kc_mult_low: float = 2.0, kernel: str | None = None, **kwargs) -> IndFrame:
        """TTM挤压 · ttm_squeeze（波动率）
        ---------
            以布林带收进肯特纳通道判定挤压状态。挤压持续后往往出现放量突破，可提前布局方向。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> bb_mult (float): 宽度 / 倍数系数. 默认: 2.0
            >>> kc_mult_high (float): 宽度 / 倍数系数. 默认: 1.0
            >>> kc_mult_mid (float): 宽度 / 倍数系数. 默认: 1.5
            >>> kc_mult_low (float): 宽度 / 倍数系数. 默认: 2.0
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — ttm_squeeze_1, ttm_squeeze_2

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.ttm_squeeze(length=14, bb_mult=2.0, kc_mult_high=1.0, kc_mult_mid=1.5, kc_mult_low=2.0, kernel=None)    # 副图
            >>> out.columns               # 线名: ttm_squeeze_1, ttm_squeeze_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ttm_squeeze(high, low, close, length=14, bb_mult=2.0, kc_mult_high=1.0, kc_mult_mid=1.5, kc_mult_low=2.0, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ttm_trend'])
    def ttm_trend(self, period: int = 14, kernel=None, **kwargs) -> IndSeries:
        """TTM趋势 · ttm_trend（趋势）
        ---------
            依据价格与短期均线的高低点关系给出趋势值。连续为正表示上升趋势，转负提示下降趋势。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (值): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ttm_trend

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ttm_trend(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ttm_trend(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['twiggs_money_flow_1', 'twiggs_money_flow_2'])
    def twiggs_money_flow(self, length: int = 14, smoothing_length: int = 14, ma_type: str = 'WMA', kernel: str | None = None, **kwargs) -> IndFrame:
        """Twiggs资金流 · twiggs_money_flow（成交量）
        ---------
            以真实波幅加权成交量的资金流指标及信号线。高于信号线表示资金流入，与价格背离提示反转。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> smoothing_length (int): 计算周期（K 线根数）. 默认: 14
            >>> ma_type (str): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 'WMA'
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — twiggs_money_flow_1, twiggs_money_flow_2

        数据:
        ---------
            >>> high, low, close, volume

        使用案例:
        ---------
            >>> out = self.data.twiggs_money_flow(length=14, smoothing_length=14, ma_type='WMA', kernel=None)    # 副图
            >>> out.columns               # 线名: twiggs_money_flow_1, twiggs_money_flow_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.twiggs_money_flow(high, low, close, volume, length=14, smoothing_length=14, ma_type='WMA', kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ui'])
    def ui(self, period: int = 14, scalar: float = 2.0, kernel: str | None = None, **kwargs) -> IndSeries:
        """溃疡指数 · ui（波动率）
        ---------
            衡量回撤深度与持续时间的风险指标。数值越高说明下跌痛苦越大、风险越高，可用于比较品种风险。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> scalar (float): 缩放系数. 默认: 2.0
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ui

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.ui(period=14, scalar=2.0, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ui(close, period=14, scalar=2.0, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['ultosc'])
    def ultosc(self, timeperiod1: str | None = None, timeperiod2: str | None = None, timeperiod3: str | None = None, kernel: str | None = None, **kwargs) -> IndSeries:
        """终极振荡器 · ultosc（动量）
        ---------
            三个不同周期加权组合的动量振荡器。70以上超买、30以下超卖，配合背离可提高信号可靠性。

        参数:
        ---------
            >>> timeperiod1 (str): 计算周期（K 线根数）. 默认: None
            >>> timeperiod2 (str): 计算周期（K 线根数）. 默认: None
            >>> timeperiod3 (str): 计算周期（K 线根数）. 默认: None
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — ultosc

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.ultosc(timeperiod1=None, timeperiod2=None, timeperiod3=None, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.ultosc(high, low, close, timeperiod1=None, timeperiod2=None, timeperiod3=None, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['var'])
    def var(self, period: int = 20, nbdev: float = 1.0, kernel: str | None = None, **kwargs) -> IndSeries:
        """风险价值偏离带 · var（波动率）
        ---------
            按滚动均值与标准差倍数计算的偏离指标。数值触及极端区域表示价格过度偏离，
            可用于风险评估。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20
            >>> nbdev (float): 标准差倍数（通道上下轨宽度）. 默认: 1.0
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — var

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.var(period=20, nbdev=1.0, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.var(close, period=20, nbdev=1.0, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['velocity'])
    def velocity(self, length: int = 14, smooth_length: int = 5, kernel: str | None = None, **kwargs) -> IndSeries:
        """速度指标 · velocity（动量）
        ---------
            衡量价格变化速度的平滑曲线。上穿零轴表示上涨动能增强，下穿表示下跌加速，
            可判断动量转折。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> smooth_length (int): 平滑周期. 默认: 5
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — velocity

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.velocity(length=14, smooth_length=5, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.velocity(close, length=14, smooth_length=5, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['velocity_acceleration_convergence_divergence_indicator_1', 'velocity_acceleration_convergence_divergence_indicator_2'])
    def velocity_acceleration_convergence_divergence_indicator(self, length: int = 14, smooth_length: int = 5, kernel: str | None = None, **kwargs) -> IndFrame:
        """速度加速度背离指标 · velocity_acceleration_convergence_divergence_indicator（动量）
        ---------
            同时给出价格速度与加速度两条线。速度与加速度同向时趋势强劲，两者背离提示动能减弱。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> smooth_length (int): 平滑周期. 默认: 5
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — velocity_acceleration_convergence_divergence_indicator_1, velocity_acceleration_convergence_divergence_indicator_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.velocity_acceleration_convergence_divergence_indicator(length=14, smooth_length=5, kernel=None)    # 副图
            >>> out.columns               # 线名: velocity_acceleration_convergence_divergence_indicator_1, velocity_acceleration_convergence_divergence_indicator_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.velocity_acceleration_convergence_divergence_indicator(close, length=14, smooth_length=5, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['vertical_horizontal_filter'])
    def vertical_horizontal_filter(self, length: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """垂直水平过滤比 · vertical_horizontal_filter（趋势）
        ---------
            比较价格净变动与路径总长度，衡量趋势的垂直程度。数值高表示趋势明确，偏低则为横盘震荡。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — vertical_horizontal_filter

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.vertical_horizontal_filter(length=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.vertical_horizontal_filter(close, length=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['vlma'])
    def vlma(self, min_period: int = 5, max_period: int = 50, matype: str = 'sma', devtype: int = 0, kernel: str | None = None, **kwargs) -> IndSeries:
        """变长移动平均 · vlma（趋势）
        ---------
            按波动幅度自适应调整周期的均线，波动大时缩短、平稳时拉长。兼顾灵敏与平滑，
            用于趋势跟踪。

        参数:
        ---------
            >>> min_period (int): 最小周期. 默认: 5
            >>> max_period (int): 最大周期. 默认: 50
            >>> matype (str): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 'sma'
            >>> devtype (int): 宽度 / 倍数系数. 默认: 0
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — vlma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.vlma(min_period=5, max_period=50, matype='sma', devtype=0, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.vlma(close, min_period=5, max_period=50, matype='sma', devtype=0, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['volatility_quality_index_1', 'volatility_quality_index_2', 'volatility_quality_index_3'])
    def volatility_quality_index(self, fast_length: int = 9, slow_length: int = 200, kernel: str | None = None, **kwargs) -> IndFrame:
        """波动质量指数 · volatility_quality_index（波动率）
        ---------
            以快慢期波动率对比衡量波动的质量与方向。读数变化可判断波动扩张或收缩，辅助确认趋势可靠度。

        参数:
        ---------
            >>> fast_length (int): 快线周期. 默认: 9
            >>> slow_length (int): 慢线周期. 默认: 200
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 3 条线 — volatility_quality_index_1, volatility_quality_index_2, volatility_quality_index_3

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.volatility_quality_index(fast_length=9, slow_length=200, kernel=None)    # 副图
            >>> out.columns               # 线名: volatility_quality_index_1, volatility_quality_index_2, volatility_quality_index_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.volatility_quality_index(open, high, low, close, fast_length=9, slow_length=200, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['volatility_ratio_adaptive_rsx_1', 'volatility_ratio_adaptive_rsx_2'])
    def volatility_ratio_adaptive_rsx(self, period: int = 14, speed: float = 0.5, kernel: str | None = None, **kwargs) -> IndFrame:
        """波动自适应RSX · volatility_ratio_adaptive_rsx（动量）
        ---------
            用波动率比率自适应调整平滑速度的RSX。波动放大时响应更快，可判断超买超卖与动量转向。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> speed (float): 原库参数（默认值见签名）. 默认: 0.5
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — volatility_ratio_adaptive_rsx_1, volatility_ratio_adaptive_rsx_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.volatility_ratio_adaptive_rsx(period=14, speed=0.5, kernel=None)    # 副图
            >>> out.columns               # 线名: volatility_ratio_adaptive_rsx_1, volatility_ratio_adaptive_rsx_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.volatility_ratio_adaptive_rsx(close, period=14, speed=0.5, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['volume_weighted_rsi'])
    def volume_weighted_rsi(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """成交量加权RSI · volume_weighted_rsi（动量）
        ---------
            用成交量加权涨跌幅计算的相对强弱指标。比普通RSI更重视放量时段，可确认量价配合的超买超卖。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — volume_weighted_rsi

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.volume_weighted_rsi(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.volume_weighted_rsi(close, volume, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['k', 'd'])
    def volume_weighted_stochastic_rsi(self, rsi_length: int = 14, stoch_length: int = 14, k_length: int = 3, d_length: int = 3, ma_type: str = 'WSMA', kernel: str | None = None, **kwargs) -> IndFrame:
        """成交量加权随机RSI · volume_weighted_stochastic_rsi（动量）
        ---------
            对成交量加权RSI再做随机化，输出K、D两线。信号更灵敏，用于短线超买超卖与入场择时。

        参数:
        ---------
            >>> rsi_length (int): RSI 计算周期. 默认: 14
            >>> stoch_length (int): 计算周期（K 线根数）. 默认: 14
            >>> k_length (int): 计算周期（K 线根数）. 默认: 3
            >>> d_length (int): 计算周期（K 线根数）. 默认: 3
            >>> ma_type (str): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 'WSMA'
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — k, d

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.volume_weighted_stochastic_rsi(rsi_length=14, stoch_length=14, k_length=3, d_length=3, ma_type='WSMA', kernel=None)    # 副图
            >>> out.columns               # 线名: k, d
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.volume_weighted_stochastic_rsi(close, volume, rsi_length=14, stoch_length=14, k_length=3, d_length=3, ma_type='WSMA', kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['volume_zone_oscillator'])
    def volume_zone_oscillator(self, length: int = 14, intraday_smoothing: bool = True, noise_filter: int = 4, kernel: str | None = None, **kwargs) -> IndSeries:
        """成交量区域振荡器 · volume_zone_oscillator（成交量）
        ---------
            以量价位置衡量资金压力的振荡指标。正值偏多、负值偏空，极端阈值处提示超买超卖与趋势强弱。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> intraday_smoothing (bool): 平滑周期. 默认: True
            >>> noise_filter (int): 原库参数（默认值见签名）. 默认: 4
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — volume_zone_oscillator

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.volume_zone_oscillator(length=14, intraday_smoothing=True, noise_filter=4, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.volume_zone_oscillator(close, volume, length=14, intraday_smoothing=True, noise_filter=4, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['vosc'])
    def vosc(self, short_period: int = 12, long_period: int = 26, kernel: str | None = None, **kwargs) -> IndSeries:
        """成交量振荡器 · vosc（成交量）
        ---------
            成交量短期均线与长期均线之差。正值表示量能扩张、负值表示萎缩，可确认突破或警惕放量滞涨。

        参数:
        ---------
            >>> short_period (int): 短周期. 默认: 12
            >>> long_period (int): 长周期. 默认: 26
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — vosc

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.vosc(short_period=12, long_period=26, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.vosc(close, short_period=12, long_period=26, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['voss_1', 'voss_2'])
    def voss(self, period: int = 14, predict: int = 3, bandwidth: float = 0.25, kernel: str | None = None, **kwargs) -> IndFrame:
        """沃斯预测滤波 · voss（动量）
        ---------
            基于Voss预测滤波的振荡线及预测线。零轴穿越与两线交叉提示短周期动量转折与超买超卖。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> predict (int): 原库参数（默认值见签名）. 默认: 3
            >>> bandwidth (float): 带宽（平滑或通道宽度）. 默认: 0.25
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 副图 · 2 条线 — voss_1, voss_2

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.voss(period=14, predict=3, bandwidth=0.25, kernel=None)    # 副图
            >>> out.columns               # 线名: voss_1, voss_2
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.voss(close, period=14, predict=3, bandwidth=0.25, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['vpt'])
    def vpt(self, kernel: str | None = None, **kwargs) -> IndSeries:
        """量价趋势指标 · vpt（成交量）
        ---------
            按涨跌幅比例累积成交量得到。与价格同步上行确认趋势，出现背离时提示趋势动能不足。

        参数:
        ---------
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — vpt

        数据:
        ---------
            >>> close, volume

        使用案例:
        ---------
            >>> out = self.data.vpt(kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.vpt(close, volume, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['wad'])
    def wad(self, kernel: str | None = None, **kwargs) -> IndSeries:
        """威廉累积派发 · wad（成交量）
        ---------
            依收盘与前期收盘关系累积的量价指标。上升表示资金积累、下降表示派发，背离为反转预警。

        参数:
        ---------
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — wad

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.wad(kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.wad(high, low, close, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['wclprice'])
    def wclprice(self, kernel: str | None = None, **kwargs) -> IndSeries:
        """加权收盘价 · wclprice（其他）
        ---------
            按高、低、收盘加权（高+低+2收）/4计算的价格序列。作为平滑价格用于构造指标与画线。

        参数:
        ---------
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — wclprice

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.wclprice(kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.wclprice(high, low, close, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['wilders'])
    def wilders(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """威尔德平滑均线 · wilders（趋势）
        ---------
            Wilder递推平滑均线，权重随时间指数衰减。常用作ATR、RSI等指标的平滑基础与趋势参考。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — wilders

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.wilders(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.wilders(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['willr'])
    def willr(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """威廉指标 · willr（动量）
        ---------
            收盘价在N周期高低区间中的位置，取值负100至0。负20以上超买、负80以下超卖，
            用于短线反转。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — willr

        数据:
        ---------
            >>> high, low, close

        使用案例:
        ---------
            >>> out = self.data.willr(period=14, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.willr(high, low, close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['wma'])
    def wma(self, period: int = 20, kernel: str | None = None, **kwargs) -> IndSeries:
        """加权移动平均 · wma（趋势）
        ---------
            按时间线性加权、近期权重更大的均线。比SMA灵敏，价格上下穿越可作多空信号与止损参考。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 20
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — wma

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.wma(period=20, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.wma(close, period=20, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['zig_zag_channels_1', 'zig_zag_channels_2', 'zig_zag_channels_3'])
    def zig_zag_channels(self, length: int = 14, extend: bool = True, kernel: str | None = None, **kwargs) -> IndFrame:
        """之字通道 · zig_zag_channels（形态）
        ---------
            连接波段高低点形成的折线通道，直观显示波段结构与关键支撑阻力。用于识别趋势转折与目标位。

        参数:
        ---------
            >>> length (int): 计算周期（K 线根数）. 默认: 14
            >>> extend (bool): 原库参数（默认值见签名）. 默认: True
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndFrame: 主图叠加 · 3 条线 — zig_zag_channels_1, zig_zag_channels_2, zig_zag_channels_3

        数据:
        ---------
            >>> open, high, low, close

        使用案例:
        ---------
            >>> out = self.data.zig_zag_channels(length=14, extend=True, kernel=None)    # 主图叠加
            >>> out.columns               # 线名: zig_zag_channels_1, zig_zag_channels_2, zig_zag_channels_3
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.zig_zag_channels(open, high, low, close, length=14, extend=True, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=True, lines=['zlema'])
    def zlema(self, period: int = 14, kernel: str | None = None, **kwargs) -> IndSeries:
        """零延迟指数均线 · zlema（趋势）
        ---------
            去除延迟处理后的EMA，更贴近价格且拐点更早。适合趋势跟踪与均线交叉择时，震荡市需防假信号。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 主图叠加 · 1 条线 — zlema

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.zlema(period=14, kernel=None)    # 主图叠加
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.zlema(close, period=14, kernel=None)
        """
        ...
    @tobtind(lib="vta", overlap=False, lines=['zscore'])
    def zscore(self, period: int = 14, ma_type: str = 'sma', nbdev: float = 1.0, devtype: int = 0, kernel: str | None = None, **kwargs) -> IndSeries:
        """标准分 · zscore（统计）
        ---------
            价格相对移动均值的标准差倍数。绝对值大于2为极端偏离，适合均值回归交易与异常行情识别。

        参数:
        ---------
            >>> period (int): 计算周期（K 线根数）. 默认: 14
            >>> ma_type (str): 均线类型（0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA …）. 默认: 'sma'
            >>> nbdev (float): 标准差倍数（通道上下轨宽度）. 默认: 1.0
            >>> devtype (int): 宽度 / 倍数系数. 默认: 0
            >>> kernel (str): 计算内核（Rust 后端）：`None` / `'auto'` 自动挑最好的；`'scalar'` 纯标量（任何 CPU 都能跑）；`'avx2'` / `'avx512'` SIMD 内核，结果一致只影响速度. 默认: None

        返回:
        ---------
            >>> IndSeries: 副图 · 1 条线 — zscore

        数据:
        ---------
            >>> close

        使用案例:
        ---------
            >>> out = self.data.zscore(period=14, ma_type='sma', nbdev=1.0, devtype=0, kernel=None)    # 副图
            >>> out.new, out.prev        # 最新一根 / 上一根
            >>> out[-20:]                # 最近 20 根

        原库:
        ---------
            >>> vector_ta.zscore(close, period=14, ma_type='sma', nbdev=1.0, devtype=0, kernel=None)
        """
        ...
    #: 数据不全 / 不是指标 → desk 不显示（方法仍在）
    NON_KLINE_INDICATORS = ['sar', 'ttm_trend']
    #: 建议信号（目录 / 技术分析用；**想改就改这张表** ✓）
    SIGNALS = {
        'adx': {'adx': Threshold(50, 1, label='adx 在 50 上方看多')},
        'adxr': {'adxr': Threshold(50, 1, label='adxr 在 50 上方看多')},
        'aroon': {'aroon_down': Threshold(50, 1, label='aroon_down 在 50 上方看多'), 'aroon_up': Threshold(50, 1, label='aroon_up 在 50 上方看多')},
        'aroonosc': {'aroonosc': Compare(-2, 1, label='aroonosc 高于前一根看多')},
        'atr': {'atr': Compare(-2, 1, label='atr 高于前一根看多')},
        'cci': {'cci': Compare(-2, 1, label='cci 高于前一根看多')},
        'dx': {'dx': Threshold(50, 1, label='dx 在 50 上方看多')},
        'ema': {'ema': Compare(-2, 1, label='ema 高于前一根看多')},
        'mom': {'mom': Compare(-2, 1, label='mom 高于前一根看多')},
        'obv': {'obv': Compare(-2, 1, label='obv 高于前一根看多')},
        'roc': {'roc': Compare(-2, 1, label='roc 高于前一根看多')},
        'rsi': {'rsi': Threshold(50, 1, label='rsi 在 50 上方看多')},
        'sma': {'sma': Compare(-2, 1, label='sma 高于前一根看多')},
        'stoch': {'k': Threshold(50, 1, label='k 在 50 上方看多'), 'd': Threshold(50, 1, label='d 在 50 上方看多')},
        'supertrend': {'supertrend_1': Compare(-2, 1, label='supertrend_1 高于前一根看多')},
        'trix': {'trix': Compare(-2, 1, label='trix 高于前一根看多')},
        'ultosc': {'ultosc': Threshold(50, 1, label='ultosc 在 50 上方看多')},
        'willr': {'willr': Compare(-2, 1, label='willr 高于前一根看多')},
        'wma': {'wma': Compare(-2, 1, label='wma 高于前一根看多')},
    }
