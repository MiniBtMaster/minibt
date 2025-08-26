from ..utils import get_stats, pd


class Stats(pd.Series):

    def __init__(self, data=None, index=None, dtype=None, name=None, copy=False, fastpath=False, available=None) -> None:
        super().__init__(data, index, dtype, name, copy, fastpath)
        self.profit_array = data
        self.available = available

    @property
    def last_result(self):
        return self.profit_array[-1]

    def result(self) -> float:
        return self.last_result

    def profit(self) -> float:
        return self.last_result-self.available

    def profit_rate(self) -> float:
        return self.profit()/self.available

    @get_stats
    def pct_rank(self, window=60):
        """Rank prices by window"""
        ...

    @get_stats
    def compsum(self):
        """Calculates rolling compounded returns"""
        ...

    @get_stats
    def comp(self):
        """Calculates total compounded returns"""
        ...

    @get_stats
    def distribution(self, compounded=True, prepare_returns=True):
        ...

    @get_stats
    def expected_return(self, aggregate=None, compounded=True,
                        prepare_returns=True):
        """
        Returns the expected return for a given period
        by calculating the geometric holding period return
        """
        ...

    @get_stats
    def geometric_mean(self, aggregate=None, compounded=True):
        """Shorthand for expected_return()"""
        ...

    @get_stats
    def ghpr(self, aggregate=None, compounded=True):
        """Shorthand for expected_return()"""
        ...

    @get_stats
    def outliers(self, quantile=.95):
        """Returns series of outliers"""
        ...

    @get_stats
    def remove_outliers(self, quantile=.95):
        """Returns series of returns without the outliers"""
        ...

    @get_stats
    def best(self, aggregate=None, compounded=True, prepare_returns=True):
        """Returns the best day/month/week/quarter/year's return"""
        ...

    @get_stats
    def worst(self, aggregate=None, compounded=True, prepare_returns=True):
        """Returns the worst day/month/week/quarter/year's return"""
        ...

    @get_stats
    def consecutive_wins(self, aggregate=None, compounded=True,
                         prepare_returns=True):
        """Returns the maximum consecutive wins by day/month/week/quarter/year"""
        ...

    @get_stats
    def consecutive_losses(self, aggregate=None, compounded=True,
                           prepare_returns=True):
        """
        Returns the maximum consecutive losses by
        day/month/week/quarter/year
        """
        ...

    @get_stats
    def exposure(self, prepare_returns=True):
        """Returns the market exposure time (self != 0)"""
        ...

    @get_stats
    def win_rate(self, aggregate=None, compounded=True, prepare_returns=True):
        """Calculates the win ratio for a period"""
        ...

    @get_stats
    def avg_return(self, aggregate=None, compounded=True, prepare_returns=True):
        """Calculates the average return/trade return for a period"""
        ...

    @get_stats
    def avg_win(self, aggregate=None, compounded=True, prepare_returns=True):
        """
        Calculates the average winning
        return/trade return for a period
        """
        ...

    @get_stats
    def avg_loss(self, aggregate=None, compounded=True, prepare_returns=True):
        """
        Calculates the average low if
        return/trade return for a period
        """
        ...

    @get_stats
    def volatility(self, periods=252, annualize=True, prepare_returns=True):
        """Calculates the volatility of returns for a period"""
        ...

    @get_stats
    def rolling_volatility(self, rolling_period=126, periods_per_year=252,
                           prepare_returns=True):
        ...

    @get_stats
    def implied_volatility(self, periods=252, annualize=True):
        """Calculates the implied volatility of returns for a period"""
        ...

    @get_stats
    def autocorr_penalty(self, prepare_returns=False):
        """Metric to account for auto correlation"""
        ...

    # ======= METRICS =======

    @get_stats
    def sharpe(self, rf=0., periods=252, annualize=True, smart=False):
        """
        Calculates the sharpe ratio of access returns

        If rf is non-zero, you must specify periods.
        In this case, rf is assumed to be expressed in yearly (annualized) terms

        Args:
            * returns (Series, DataFrame): Input return series
            * rf (float): Risk-free rate expressed as a yearly (annualized) return
            * periods (int): Freq. of returns (252/365 for daily, 12 for monthly)
            * annualize: return annualize sharpe?
            * smart: return smart sharpe ratio
        """
        ...

    @get_stats
    def smart_sharpe(self, rf=0., periods=252, annualize=True):
        ...

    @get_stats
    def rolling_sharpe(self, rf=0., rolling_period=126,
                       annualize=True, periods_per_year=252,
                       prepare_returns=True):
        ...

    @get_stats
    def sortino(self, rf=0, periods=252, annualize=True, smart=False):
        """
        Calculates the sortino ratio of access returns

        If rf is non-zero, you must specify periods.
        In this case, rf is assumed to be expressed in yearly (annualized) terms

        Calculation is based on this paper by Red Rock Capital
        http://www.redrockcapital.com/Sortino__A__Sharper__Ratio_Red_Rock_Capital.pdf
        """
        ...

    @get_stats
    def smart_sortino(self, rf=0, periods=252, annualize=True):
        ...

    @get_stats
    def rolling_sortino(self, rf=0, rolling_period=126, annualize=True,
                        periods_per_year=252, **kwargs):
        ...

    @get_stats
    def adjusted_sortino(self, rf=0, periods=252, annualize=True, smart=False):
        """
        Jack Schwager's version of the Sortino ratio allows for
        direct comparisons to the Sharpe. See here for more info:
        https://archive.is/wip/2rwFW
        """
        ...

    @get_stats
    def probabilistic_ratio(self, rf=0., base="sharpe", periods=252, annualize=False, smart=False):
        ...

    @get_stats
    def probabilistic_sharpe_ratio(self, rf=0., periods=252, annualize=False, smart=False):
        ...

    @get_stats
    def probabilistic_sortino_ratio(self, rf=0., periods=252, annualize=False, smart=False):
        ...

    @get_stats
    def probabilistic_adjusted_sortino_ratio(self, rf=0., periods=252, annualize=False, smart=False):
        ...

    @get_stats
    def treynor_ratio(self, benchmark, periods=252., rf=0.):
        """
        Calculates the Treynor ratio

        Args:
            * returns (Series, DataFrame): Input return series
            * benchmatk (String, Series, DataFrame): Benchmark to compare beta to
            * periods (int): Freq. of returns (252/365 for daily, 12 for monthly)
        """
        ...

    @get_stats
    def omega(self, rf=0.0, required_return=0.0, periods=252):
        """
        Determines the Omega ratio of a strategy.
        See https://en.wikipedia.org/wiki/Omega_ratio for more details.
        """
        ...

    @get_stats
    def gain_to_pain_ratio(self, rf=0, resolution="D"):
        """
        Jack Schwager's GPR. See here for more info:
        https://archive.is/wip/2rwFW
        """
        ...

    @get_stats
    def cagr(self, rf=0., compounded=True):
        """
        Calculates the communicative annualized growth return
        (CAGR%) of access returns

        If rf is non-zero, you must specify periods.
        In this case, rf is assumed to be expressed in yearly (annualized) terms
        """
        ...

    @get_stats
    def rar(self, rf=0.):
        """
        Calculates the risk-adjusted return of access returns
        (CAGR / exposure. takes time into account.)

        If rf is non-zero, you must specify periods.
        In this case, rf is assumed to be expressed in yearly (annualized) terms
        """
        ...

    @get_stats
    def skew(self, prepare_returns=True):
        """
        Calculates returns' skewness
        (the degree of asymmetry of a distribution around its mean)
        """
        ...

    @get_stats
    def kurtosis(self, prepare_returns=True):
        """
        Calculates returns' kurtosis
        (the degree to which a distribution peak compared to a normal distribution)
        """
        ...

    @get_stats
    def calmar(self, prepare_returns=True):
        """Calculates the calmar ratio (CAGR% / MaxDD%)"""
        ...

    @get_stats
    def ulcer_index(self):
        """Calculates the ulcer index score (downside risk measurment)"""
        ...

    @get_stats
    def ulcer_performance_index(self, rf=0):
        """
        Calculates the ulcer index score
        (downside risk measurment)
        """
        ...

    @get_stats
    def upi(self, rf=0):
        """Shorthand for ulcer_performance_index()"""
        ...

    @get_stats
    def serenity_index(self, rf=0):
        """
        Calculates the serenity index score
        (https://www.keyquant.com/Download/GetFile?Filename=%5CPublications%5CKeyQuant_WhitePaper_APT_Part1.pdf)
        """
        ...

    @get_stats
    def risk_of_ruin(self, prepare_returns=True):
        """
        Calculates the risk of ruin
        (the likelihood of losing all one's investment capital)
        """
        ...

    @get_stats
    def ror(self):
        """Shorthand for risk_of_ruin()"""
        ...

    @get_stats
    def value_at_risk(self, sigma=1, confidence=0.95, prepare_returns=True):
        """
        Calculats the daily value-at-risk
        (variance-covariance calculation with confidence n)
        """
        ...

    @get_stats
    def var(self, sigma=1, confidence=0.95, prepare_returns=True):
        """Shorthand for value_at_risk()"""
        ...

    @get_stats
    def conditional_value_at_risk(self, sigma=1, confidence=0.95,
                                  prepare_returns=True):
        """
        Calculats the conditional daily value-at-risk (aka expected shortfall)
        quantifies the amount of tail risk an investment
        """
        ...

    @get_stats
    def cvar(self, sigma=1, confidence=0.95, prepare_returns=True):
        """Shorthand for conditional_value_at_risk()"""
        ...

    @get_stats
    def expected_shortfall(self, sigma=1, confidence=0.95):
        """Shorthand for conditional_value_at_risk()"""
        ...

    @get_stats
    def tail_ratio(self, cutoff=0.95, prepare_returns=True):
        """
        Measures the ratio between the right
        (95%) and left tail (5%).
        """
        ...

    @get_stats
    def payoff_ratio(self, prepare_returns=True):
        """Measures the payoff ratio (average win/average loss)"""
        ...

    @get_stats
    def win_loss_ratio(self, prepare_returns=True):
        """Shorthand for payoff_ratio()"""
        ...

    @get_stats
    def profit_ratio(self, prepare_returns=True):
        """Measures the profit ratio (win ratio / loss ratio)"""
        ...

    @get_stats
    def profit_factor(self, prepare_returns=True):
        """Measures the profit ratio (wins/loss)"""
        ...

    @get_stats
    def cpc_index(self, prepare_returns=True):
        """
        Measures the cpc ratio
        (profit factor * win % * win loss ratio)
        """
        ...

    @get_stats
    def common_sense_ratio(self, prepare_returns=True):
        """Measures the common sense ratio (profit factor * tail ratio)"""
        ...

    @get_stats
    def outlier_win_ratio(self, quantile=.99, prepare_returns=True):
        """
        Calculates the outlier winners ratio
        99th percentile of returns / mean positive return
        """
        ...

    @get_stats
    def outlier_loss_ratio(self, quantile=.01, prepare_returns=True):
        """
        Calculates the outlier losers ratio
        1st percentile of returns / mean negative return
        """
        ...

    @get_stats
    def recovery_factor(self, prepare_returns=True):
        """Measures how fast the strategy recovers from drawdowns"""
        ...

    @get_stats
    def risk_return_ratio(self, prepare_returns=True):
        """
        Calculates the return / risk ratio
        (sharpe ratio without factoring in the risk-free rate)
        """
        ...

    @get_stats
    def max_drawdown(self):
        """Calculates the maximum drawdown"""
        ...

    @get_stats
    def to_drawdown_series(self):
        """Convert returns series to drawdown series"""
        ...

    @staticmethod
    @get_stats
    def drawdown_details(drawdown):
        """
        Calculates drawdown details, including start/end/valley dates,
        duration, max drawdown and max dd for 99% of the dd period
        for every drawdown period
        """
        ...

    @get_stats
    def kelly_criterion(self, prepare_returns=True):
        """
        Calculates the recommended maximum amount of capital that
        should be allocated to the given strategy, based on the
        Kelly Criterion (http://en.wikipedia.org/wiki/Kelly_criterion)
        """
        ...

    # ==== VS. BENCHMARK ====

    @get_stats
    def r_squared(self, benchmark, prepare_returns=True):
        """Measures the straight line fit of the equity curve"""
        # slope, intercept, r_val, p_val, std_err = _linregress(
        ...

    @get_stats
    def r2(self, benchmark):
        """Shorthand for r_squared()"""
        ...

    @get_stats
    def information_ratio(self, benchmark, prepare_returns=True):
        """
        Calculates the information ratio
        (basically the risk return ratio of the net profits)
        """
        ...

    @get_stats
    def greeks(self, benchmark, periods=252., prepare_returns=True):
        """Calculates alpha and beta of the portfolio"""
        # ----------------------------
        # data cleanup
        ...

    @get_stats
    def rolling_greeks(self, benchmark, periods=252, prepare_returns=True):
        """Calculates rolling alpha and beta of the portfolio"""
        ...

    @get_stats
    def compare(self, benchmark, aggregate=None, compounded=True,
                round_vals=None, prepare_returns=True):
        """
        Compare returns to benchmark on a
        day/week/month/quarter/year basis
        """
        ...

    @get_stats
    def monthly_returns(self, eoy=True, compounded=True, prepare_returns=True):
        """Calculates monthly returns"""
        ...
