from __future__ import annotations
from ._base import tobtind

from ..utils import TYPE_CHECKING

if TYPE_CHECKING:
    from ._core import IndSeries,IndFrame


class Pair:
    """
    ## 配对交易策略类

    - 配对交易是一种统计套利策略，通过识别具有长期均衡关系的两只或多只资产，
    - 当它们之间的价差偏离历史均值时，分别做多和做空，等待价差回归时平仓获利。

    ## 策略方法分类：

    ### 基础方法：
    - `bollinger_bands_strategy`: 布林带策略 - 使用布林带识别价差偏离
    - `percentage_deviation_strategy`: 百分比偏差策略 - 基于百分比偏离识别交易机会
    - `rolling_quantile_strategy`: 移动窗口分位数策略 - 使用分位数识别极端偏离
    - `z_score_strategy`: Z-score策略 - 基于标准分数识别统计套利机会

    ### 高级方法：
    - `hurst_filter_strategy`: Hurst指数过滤策略 - 使用Hurst指数过滤趋势性价差
    - `kalman_filter_strategy`: 卡尔曼滤波策略 - 动态估计对冲比率和价差
    - `garch_volatility_adjusted_signals`: GARCH模型波动率调整策略 - 考虑时变波动率
    - `vecm_based_signals`: VECM模型策略 - 基于向量误差修正模型识别长期均衡关系
    """

    _perfixes: str = "pair_"
    _df: IndSeries

    def __init__(self, data):
        self._df = data

    @tobtind(lines=["spread", "upper_band", "lower_band", "signals"], lib="pair")
    def bollinger_bands(self, window: int = 60, num_std: float = 2.0, **kwargs) -> IndFrame:
        """
        ## 布林带配对交易策略

        - 布林带是一种基于移动平均线和标准差的技术指标，用于识别价差的波动范围。
        - 当价差突破布林带上轨时，表示价差过高，应做空价差（做多被低估资产，做空被高估资产）。
        - 当价差跌破布林带下轨时，表示价差过低，应做多价差（做空被高估资产，做多被低估资产）。

        底层逻辑：
        ```
        spread_mean = spread_series.rolling(window=window).mean()
        spread_std = spread_series.rolling(window=window).std()
        upper_band = num_std * spread_std
        lower_band = -upper_band
        normalized_spread = spread_series - spread_mean
        signals = np.where(normalized_spread > upper_band, -1.,  # 做空价差
                           np.where(normalized_spread < lower_band, 1., 0.))  # 做多价差
        ```

        Parameters
        ----------
        window : int, default=60
            计算移动平均线和标准差的窗口大小（交易日数）

        num_std : float, default=2.0
            标准差倍数，用于确定布林带的宽度。常用值：1.5、2.0、2.5
            值越大，交易信号越保守（较少触发）

        **kwargs : dict
            其他关键字参数，传递给底层实现

        Returns
        -------
        IndFrame
            包含以下列的数据框：
            - `spread` : 归一化后的价差序列（原始价差减去移动平均）
            - `upper_band` : 布林带上轨
            - `lower_band` : 布林带下轨
            - `signals` : 交易信号
              - 1 : 做多价差（价差过低，预期回归）
              - -1 : 做空价差（价差过高，预期回归）
              - 0 : 无信号

        Notes
        -----
        1. 布林带策略适用于均值回复性强的价差序列
        2. 窗口大小选择应考虑到价差的波动周期（一般为20-120个交易日）
        3. 标准差倍数决定交易信号的敏感度，值越大信号越少但更可靠
        4. 信号在价差突破布林带边界时生成，回归到移动平均线时平仓

        Examples
        --------
        ```python
        # 两个资产的基差序列，类型IndSeries
        spread_series

        # 使用自定义参数
        signals_custom = spread_series.bollinger_bands(window=20, num_std=1.5)

        # 访问结果列（使用属性访问）
        spread = signals.spread
        upper_band = signals.upper_band
        lower_band = signals.lower_band
        trade_signals = signals.signals

        # 查找做多信号
        long_signals = signals[signals.signals == 1]

        # 查找做空信号
        short_signals = signals[signals.signals == -1]
        ```
        """
        ...

    @tobtind(lines=["pct_deviation", "signals"], lib="pair")
    def percentage_deviation(self, window: int = 60, threshold: float = 0.1, **kwargs) -> IndFrame:
        """
        ## 百分比偏差配对交易策略

        - 计算价差相对于移动平均的百分比偏离程度，当百分比偏差超过预设阈值时生成交易信号。
        - 适用于价差波动相对稳定的配对。

        底层逻辑：
        ```
        spread_mean = spread_series.rolling(window=window).mean()
        spread_mean = spread_mean.replace(0, 1e-10)  # 避免除以零
        pct_deviation = (spread_series - spread_mean) / spread_mean * 100.  # 百分比偏差
        signals = np.where(pct_deviation > threshold, -1.,  # 做空价差
                           np.where(pct_deviation < -threshold, 1., 0))  # 做多价差
        ```

        Parameters
        ----------
        window : int, default=60
            计算移动平均的窗口大小（交易日数）

        threshold : float, default=0.1
            百分比偏差阈值（单位：%），例如0.1表示10%
            当|百分比偏差| > threshold时生成交易信号

        **kwargs : dict
            其他关键字参数，传递给底层实现

        Returns
        -------
        IndFrame
            包含以下列的数据框：
            - `pct_deviation` : 百分比偏差序列（单位：%）
            - `signals` : 交易信号
              - 1 : 做多价差（百分比偏差低于负阈值）
              - -1 : 做空价差（百分比偏差高于正阈值）
              - 0 : 无信号

        Notes
        -----
        1. 百分比偏差策略直观易懂，适用于具有稳定波动范围的价差
        2. 阈值选择需要根据历史数据进行回测优化（一般为5%-20%）
        3. 百分比偏差可能受极端值影响较大，建议结合其他指标使用
        4. 当移动平均接近零时，使用1e-10替代以避免除以零错误

        Examples
        --------
        ```python
        # 两个资产的基差序列，类型IndSeries
        spread_series

        # 使用自定义阈值
        signals_custom = spread_series.percentage_deviation(window=30, threshold=15.0)

        # 访问结果
        pct_dev = signals.pct_deviation
        trade_signals = signals.signals

        # 计算信号统计
        signal_counts = signals.signals.tqfunc.count(length=10)
        #10周期出现做多价差信号的次数
        long_signal = (signals.signals==1).tqfunc.count(length=10)
        #10周期出现做空价差信号的次数
        long_signal = (signals.signals==-1).tqfunc.count(length=10)
        ```
        """
        ...

    @tobtind(lines=["spread", "upper_threshold", "lower_threshold", "signals"], lib="pair")
    def rolling_quantile(self, window: int = 60, upper_quantile: float = 0.95,
                         lower_quantile: float = 0.05, **kwargs) -> IndFrame:
        """
        ## 移动窗口分位数配对交易策略

        - 使用移动窗口的分位数作为动态阈值，识别价差的极端偏离情况。
        - 相比固定阈值，分位数阈值能更好地适应价差分布的变化。

        底层逻辑：
        ```
        spread_mean = spread_series.rolling(window=window).mean()
        # 计算滚动分位数
        upper_threshold = spread_series.rolling(window=window).quantile(upper_quantile) - spread_mean
        lower_threshold = spread_series.rolling(window=window).quantile(lower_quantile) - spread_mean
        normalized_spread = spread_series - spread_mean
        signals = np.where(normalized_spread > upper_threshold, -1.,  # 做空价差
                           np.where(normalized_spread < lower_threshold, 1., 0.))  # 做多价差
        ```

        Parameters
        ----------
        window : int, default=60
            计算分位数的滚动窗口大小（交易日数）

        upper_quantile : float, default=0.95
            上分位数阈值，范围(0,1)。常用值：0.90、0.95、0.975
            表示当价差超过历史窗口95%分位数时触发做空信号

        lower_quantile : float, default=0.05
            下分位数阈值，范围(0,1)。常用值：0.05、0.10、0.025
            表示当价差低于历史窗口5%分位数时触发做多信号

        **kwargs : dict
            其他关键字参数，传递给底层实现

        Returns
        -------
        IndFrame
            包含以下列的数据框：
            - `spread` : 归一化后的价差序列
            - `upper_threshold` : 上分位数阈值
            - `lower_threshold` : 下分位数阈值
            - `signals` : 交易信号
              - 1 : 做多价差（价差低于下分位数阈值）
              - -1 : 做空价差（价差高于上分位数阈值）
              - 0 : 无信号

        Notes
        -----
        1. 分位数策略能自适应价差分布的变化，对异常值不敏感
        2. 上分位数和下分位数通常对称设置（如0.95和0.05）
        3. 较小的分位数阈值（如0.90/0.10）产生更多交易信号
        4. 较大的分位数阈值（如0.975/0.025）产生更可靠的信号但机会较少

        Examples
        --------
        ```python
        # 两个资产的基差序列，类型IndSeries
        spread_series

        # 使用对称分位数（90%和10%）
        signals_symmetric = spread_series.rolling_quantile(upper_quantile=0.90, lower_quantile=0.10)

        # 使用不对称分位数（针对偏态分布）
        signals_asymmetric = spread_series.rolling_quantile(upper_quantile=0.97, lower_quantile=0.03)

        # 访问结果
        normalized_spread = signals.spread
        upper_thresh = signals.upper_threshold
        lower_thresh = signals.lower_threshold
        ```
        """
        ...

    @tobtind(lines=["z_score", "signals"], lib="pair")
    def z_score(self, window: int = 60, z_threshold: float = 2.0, **kwargs) -> IndFrame:
        """
        ## Z-score配对交易策略

        - 计算价差的Z-score（标准分数），基于统计学原理识别价差的极端偏离。
        - Z-score表示价差偏离其均值的标准差倍数，是配对交易最常用的指标之一。

        底层逻辑：
        ```
        spread_mean = spread_series.rolling(window=window).mean()
        spread_std = spread_series.rolling(window=window).std()
        spread_std = spread_std.replace(0, 1e-10)  # 避免除以零
        z_score = (spread_series - spread_mean) / spread_std  # 计算Z-score
        signals = np.where(z_score > z_threshold, -1,  # 做空价差
                           np.where(z_score < -z_threshold, 1, 0))  # 做多价差
        ```

        Parameters
        ----------
        window : int, default=60
            计算均值和标准差的滚动窗口大小（交易日数）

        z_threshold : float, default=2.0
            Z-score阈值，常用值：1.5、2.0、2.5、3.0
            当|Z-score| > z_threshold时生成交易信号

        **kwargs : dict
            其他关键字参数，传递给底层实现

        Returns
        -------
        IndFrame
            包含以下列的数据框：
            - `z_score` : Z-score序列
            - `signals` : 交易信号
              - 1 : 做多价差（Z-score < -z_threshold）
              - -1 : 做空价差（Z-score > z_threshold）
              - 0 : 无信号

        Notes
        -----
        1. Z-score策略基于正态分布假设，适用于近似正态分布的价差
        2. Z-score阈值决定交易频率和风险：
           - 阈值=1.5：频繁交易，风险较高
           - 阈值=2.0：平衡型，常用设置
           - 阈值=2.5：较少交易，风险较低
        3. 当标准差接近零时，使用1e-10替代以避免除以零错误
        4. Z-score可以直接比较不同配对间的偏离程度

        Examples
        --------
        ```python
        # 两个资产的基差序列，类型IndSeries
        spread_series

        # 使用不同阈值
        signals_conservative = spread_series.z_score(z_threshold=2.5)  # 保守策略
        signals_aggressive = spread_series.z_score(z_threshold=1.5)    # 激进策略

        # 访问Z-score和信号
        z_scores = signals.z_score
        trade_signals = signals.signals

        # 计算Z-score的统计特性
        z_stats = {
            'mean': z_scores.mean(),
            'std': z_scores.std(),
            'min': z_scores.min(),
            'max': z_scores.max(),
            'skewness': z_scores.skew(),
            'kurtosis': z_scores.kurtosis()
        }

        # 检查Z-score是否服从标准正态分布
        from scipy import stats
        _, p_value = stats.kstest(z_scores.dropna(), 'norm')
        print(f"Kolmogorov-Smirnov检验p值: {p_value:.4f}")
        ```
        """
        ...

    @tobtind(lines=["z_score", "signals"], lib="pair")
    def hurst_filter(self, hurst_threshold: float = 0.5, z_threshold: float = 2.0, **kwargs) -> IndFrame:
        """
        ## Hurst指数过滤策略

        - 使用Hurst指数判断价差序列的均值回复特性，过滤掉趋势性强的价差。
        - 只对具有均值回复特性（Hurst指数<阈值）的价差应用Z-score策略。

        底层逻辑：
        ```
        # 1. 计算Hurst指数
        def calculate_hurst_exponent(series, max_lag=20):
            lags = range(2, max_lag + 1)
            tau = []
            for lag in lags:
                diff = np.subtract(series[lag:], series[:-lag])
                std = np.std(diff)
                tau.append(std if std != 0 else 1e-10)
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            return poly[0]  # Hurst指数

        # 2. 判断均值回复性
        hurst = calculate_hurst_exponent(spread_series)

        # 3. 应用过滤
        if hurst >= hurst_threshold:  # 趋势性强，不交易
            signals = np.zeros_like(z_signals)
        else:  # 均值回复性强，使用Z-score策略
            zscore_result = z_score_strategy(spread_series, z_threshold=z_threshold)
            signals = zscore_result.signals
        ```

        Parameters
        ----------
        hurst_threshold : float, default=0.5
            Hurst指数阈值，常用值：0.5
            - Hurst指数 < 0.5：均值回复过程
            - Hurst指数 = 0.5：随机游走
            - Hurst指数 > 0.5：趋势过程
            只对Hurst指数 < hurst_threshold的价差生成交易信号

        z_threshold : float, default=2.0
            应用于Z-score策略的阈值

        **kwargs : dict
            其他关键字参数，传递给底层实现

        Returns
        -------
        IndFrame
            包含以下列的数据框：
            - `z_score` : Z-score序列（即使被过滤也计算）
            - `signals` : 过滤后的交易信号
              - 1 : 做多价差（均值回复性强且Z-score < -z_threshold）
              - -1 : 做空价差（均值回复性强且Z-score > z_threshold）
              - 0 : 无信号（包括趋势性强的情况）

        Notes
        -----
        1. Hurst指数用于量化时间序列的长期记忆性
        2. 配对交易要求价差具有均值回复性（Hurst指数<0.5）
        3. 趋势性强的价差（Hurst指数>0.5）不适合配对交易
        4. 该方法能有效过滤掉不合适的交易机会，提高策略胜率
        5. Hurst指数的计算基于重标极差分析（R/S分析）的简化版本

        Examples
        --------
        ```python
        # 两个资产的基差序列，类型IndSeries
        spread_series

        # 获取Hurst指数（需要从底层获取，这里假设可以通过kwargs传递）
        # 在实际使用中，可能需要查看日志或修改代码来获取Hurst指数值

        # 比较有过滤和无过滤的信号
        signals_with_filter = spread_series.hurst_filter(hurst_threshold=0.5)
        signals_no_filter = spread_series.z_score(z_threshold=2.0)

        # 统计过滤效果
        total_signals_no_filter = (signals_no_filter.signals != 0).tqfunc.count(length=10)
        total_signals_with_filter = (signals_with_filter.signals != 0).tqfunc.count(length=10)
        filtered_out = total_signals_no_filter - total_signals_with_filter

        print(f"无过滤信号数: {total_signals_no_filter.new}")
        print(f"有过滤信号数: {total_signals_with_filter.new}")
        print(f"过滤掉的信号: {filtered_out.new} ({filtered_out.new/total_signals_no_filter.new:.1%})")
        ```
        """
        ...

    @tobtind(lines=["dynamic_spread", "hedge_ratios", "z_score", "signals"], lib="pair")
    def kalman_filter(self, y_series=None, z_threshold: float = 2.0, **kwargs) -> IndFrame:
        """
        ## 卡尔曼滤波配对交易策略

        - 使用卡尔曼滤波动态估计对冲比率，计算动态价差，然后应用Z-score策略。
        - 适用于对冲比率随时间变化的情况。

        底层逻辑：
        ```
        # 1. 初始化卡尔曼滤波器
        kf = KalmanFilter(
            transition_matrices=[[1, 0], [0, 1]],
            observation_matrices=[[x_series.values[0], 1]],
            initial_state_mean=[0, 0],
            initial_state_covariance=np.eye(2),
            observation_covariance=1.0,
            transition_covariance=np.eye(2) * 0.01
        )

        # 2. 滤波估计状态（对冲比率和截距）
        state_means, _ = kf.filter(y_series.values)
        hedge_ratios = state_means[:, 0]  # 动态对冲比率
        intercepts = state_means[:, 1]    # 动态截距

        # 3. 计算动态价差
        dynamic_spread = y_series.values - hedge_ratios * x_series.values - intercepts

        # 4. 对动态价差应用Z-score策略
        zscore_result = z_score_strategy(dynamic_spread, z_threshold=z_threshold)
        ```

        Parameters
        ----------
        self : IndSeries 
            资产价格序列

        y_series : IndSeries
            与之配对的另外一个资产价格序列

        z_threshold : float, default=2.0
            应用于动态价差的Z-score阈值

        **kwargs : dict
            其他关键字参数，传递给卡尔曼滤波器和底层实现
            - transition_covariance: 状态转移协方差（默认0.01）
            - observation_covariance: 观测协方差（默认1.0）

        Returns
        -------
        IndFrame
            包含以下列的数据框：
            - `dynamic_spread` : 基于动态对冲比率计算的价差
            - `hedge_ratios` : 卡尔曼滤波估计的动态对冲比率
            - `z_score` : 动态价差的Z-score
            - `signals` : 交易信号
              - 1 : 做多价差（Z-score < -z_threshold）
              - -1 : 做空价差（Z-score > z_threshold）
              - 0 : 无信号

        Notes
        -----
        1. 卡尔曼滤波能实时更新对冲比率，适应市场结构变化
        2. 动态对冲比率比静态OLS估计更灵活
        3. 状态转移协方差控制对冲比率的平滑程度：
           - 较小值：对冲比率变化缓慢
           - 较大值：对冲比率变化迅速
        4. 观测协方差控制滤波器对观测值的信任程度
        5. 卡尔曼滤波需要足够的初始数据来收敛

        Examples
        --------
        ```python
        # 两个资产的价格序列，类型IndSeries
        x_series # 实例自身
        y_series
        signals = x_series.kalman_filter(y_series)

        # 访问动态对冲比率和价差
        hedge_ratios = signals.hedge_ratios
        dynamic_spread = signals.dynamic_spread
        ```
        """
        ...

    @tobtind(lines=["volatility", "garch_z_score", "signals"], lib="pair")
    def garch_volatility_adjusted(self, z_threshold: float = 2.0, **kwargs) -> IndFrame:
        """
        ## GARCH波动率调整策略

        - 使用GARCH(1,1)模型估计时变波动率，计算波动率调整的Z-score。
        - 考虑波动率的聚类效应（volatility clustering），在波动率高时放宽交易阈值。

        底层逻辑：
        ```
        # 1. 数据预处理和缩放
        spread_series = pd.to_numeric(spread_series, errors='coerce').dropna()
        spread_scaled = spread_series * 100  # 缩放提高数值稳定性

        # 2. 拟合GARCH(1,1)模型
        model = arch_model(spread_scaled.values, vol='GARCH', p=1, q=1)
        garch_results = model.fit(disp='off')

        # 3. 获取条件波动率并还原缩放
        volatility = pd.Series(garch_results.conditional_volatility) / 100

        # 4. 计算GARCH调整的Z-score
        spread_mean = spread_series.rolling(window=60).mean()
        volatility = volatility.replace(0, 1e-10)  # 避免除以零
        garch_z_score = (spread_series - spread_mean) / volatility

        # 5. 生成信号
        signals = np.where(garch_z_score > z_threshold, -1,
                           np.where(garch_z_score < -z_threshold, 1, 0))
        ```

        Parameters
        ----------
        z_threshold : float, default=2.0
            应用于GARCH调整Z-score的阈值

        **kwargs : dict
            其他关键字参数，传递给GARCH模型
            - p: GARCH模型的自回归阶数（默认1）
            - q: GARCH模型的移动平均阶数（默认1）
            - vol: 波动率模型类型（默认'GARCH'）

        Returns
        -------
        IndFrame
            包含以下列的数据框：
            - `volatility` : GARCH估计的条件波动率序列
            - `garch_z_score` : 波动率调整的Z-score
            - `signals` : 交易信号
              - 1 : 做多价差（garch_z_score < -z_threshold）
              - -1 : 做空价差（garch_z_score > z_threshold）
              - 0 : 无信号

        Notes
        -----
        1. GARCH模型能捕捉波动率的时变性和聚类效应
        2. 波动率调整的Z-score在波动率高时更保守（不易触发信号）
        3. GARCH(1,1)是金融时间序列最常用的波动率模型
        4. 数据缩放（×100）提高GARCH模型估计的数值稳定性
        5. 需要足够的历史数据（建议>100个观测值）来可靠估计GARCH参数

        Examples
        --------
        ```python
        # 两个资产的基差序列，类型IndSeries
        spread_series

        # 使用GARCH波动率调整策略
        signals = spread_series.garch_volatility_adjusted()

        # 访问GARCH估计的波动率和调整后的Z-score
        conditional_vol = signals.volatility
        garch_z = signals.garch_z_score

        # 比较传统Z-score和GARCH调整Z-score
        traditional_z = spread_series.z_score()
        garch_z = signals.garch_z_score
        ```
        """
        ...

    @tobtind(lines=["ect", "signals"], lib="pair")
    def vecm_based(self, y_series=None, window: int = 60, lag: int = 2, **kwargs) -> IndFrame:
        """
        ## 向量误差修正模型（VECM）策略

        基于向量误差修正模型识别资产间的长期均衡关系，使用误差修正项（ECT）作为交易信号。
        VECM适用于具有协整关系的多变量时间序列。

        底层逻辑：
        ```
        # 1. 数据预处理和对齐
        x_series = pd.to_numeric(x_series, errors='coerce').dropna()
        y_series = pd.to_numeric(y_series, errors='coerce').dropna()
        combined = pd.DataFrame({'x': x_series, 'y': y_series}).dropna()

        # 2. 手动Johansen协整检验
        series = combined[['x', 'y']].values
        coint_vector = johansen_test_manual(series, lags=lag)

        # 3. 计算误差修正项（ECT）
        ect = np.dot(series, coint_vector)  # 线性组合
        ect = pd.Series(ect, index=combined.index)
        ect -= ect.mean()  # 中心化处理

        # 4. 使用滚动分位数生成信号
        upper_threshold = ect.rolling(window=window).quantile(0.90)
        lower_threshold = ect.rolling(window=window).quantile(0.10)
        signals = np.where(ect > upper_threshold, -1.,  # 做空价差
                           np.where(ect < lower_threshold, 1., 0.))  # 做多价差
        ```

        Parameters
        ----------
        self : IndSeries 
            资产价格序列

        y_series : IndSeries
            与之配对的另外一个资产价格序列

        window : int, default=60
            计算分位数阈值的滚动窗口大小

        lag : int, default=2
            VECM模型的滞后阶数，常用值：1、2、3
            通过信息准则（AIC/BIC）选择最优滞后阶数

        **kwargs : dict
            其他关键字参数，传递给协整检验和VECM模型

        Returns
        -------
        IndFrame
            包含以下列的数据框：
            - `ect` : 误差修正项序列（中心化后的线性组合）
            - `signals` : 交易信号
              - 1 : 做多价差（ECT低于下分位数阈值）
              - -1 : 做空价差（ECT高于上分位数阈值）
              - 0 : 无信号

        Notes
        -----
        1. VECM模型同时考虑短期动态调整和长期均衡关系
        2. 误差修正项（ECT）度量系统偏离长期均衡的程度
        3. Johansen协整检验比Engle-Granger两步法更适合多变量情形
        4. 滞后阶数选择影响模型性能，可通过AIC/BIC准则确定
        5. 需要足够的数据量（建议>100个观测值）进行可靠的协整检验

        Examples
        --------
        ```python
        # 两个资产的价格序列，类型IndSeries
        x_series # 实例自身
        y_series
        signals = x_series.vecm_based(y_series)

        # 访问误差修正项和信号
        ect_series = signals.ect
        trade_signals = signals.signals

        # 检查ECT的平稳性（应该平稳）
        from statsmodels.tsa.stattools import adfuller
        adf_result = adfuller(ect_series.dropna())
        print(f"ADF统计量: {adf_result[0]:.4f}")
        print(f"p值: {adf_result[1]:.4f}")
        print(f"临界值: {adf_result[4]}")

        # 标记交易信号
        long_signals = signals[signals.signals == 1]
        short_signals = signals[signals.signals == -1]
        ```
        """
        ...
