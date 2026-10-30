"""Declarative formatters and the preload escape hatch."""
import pandas as pd
import pytest

from pylightcharts.abstract import AbstractChart, Window


@pytest.fixture()
def chart():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)
    chart.captured = captured
    chart.set(pd.DataFrame({
        'time': pd.date_range('2020-01-01', periods=5),
        'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5,
    }))
    captured.clear()
    return chart


def test_price_formatter_spec(chart):
    chart.set_price_formatter(decimals=2, thousands=True, prefix='$')
    script = chart.captured[-1]
    assert '"setPriceFormatter"' in script
    assert '"decimals":2' in script
    assert '"thousands":true' in script
    assert '"prefix":"$"' in script


def test_price_formatter_omits_none_decimals(chart):
    chart.set_price_formatter(thousands=True)
    assert '"decimals"' not in chart.captured[-1]


def test_time_formatter_spec(chart):
    chart.set_time_formatter('YYYY-MM-DD HH:mm')
    script = chart.captured[-1]
    assert '"setTimeFormatter"' in script
    assert '"template":"YYYY-MM-DD HH:mm"' in script
    assert '"utc":true' in script


def test_formatter_by_registered_name(chart):
    chart.set_price_formatter(name='eur')
    assert '"setPriceFormatter"' in chart.captured[-1]
    assert '"eur"' in chart.captured[-1]
    chart.captured.clear()
    chart.set_time_formatter(name='friendly')
    assert '"friendly"' in chart.captured[-1]


def test_named_formatter_rejects_declarative_options(chart):
    """`name=` replaces the declarative options, it does not merge them.

    Passing both used to silently ignore `prefix`/`thousands`/... - which reads
    exactly like "the option does nothing" on the axis.
    """
    with pytest.raises(ValueError, match='replaces the declarative options'):
        chart.set_price_formatter(name='eur', prefix='$')
    with pytest.raises(ValueError, match='thousands'):
        chart.set_price_formatter(name='eur', thousands=True)
    with pytest.raises(ValueError, match='replaces the declarative options'):
        chart.set_time_formatter(name='friendly', template='YYYY')

    # the defaults of the *other* arguments are not a conflict
    chart.set_price_formatter(name='eur')
    assert '"eur"' in chart.captured[-1]
    chart.set_time_formatter(name='friendly')
    assert '"friendly"' in chart.captured[-1]


def test_register_js_formatter(chart):
    chart.register_js_formatter('eur', "value => '\u20ac' + value.toFixed(2)")
    script = chart.captured[-1]
    assert 'Lib.registerFormatter("eur"' in script
    assert "value.toFixed(2)" in script


# --------------------------------------------------------------------------
# preload
# --------------------------------------------------------------------------

def test_preload_runs_before_the_handler():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)          # emits the handler statement first
    # simulate the queued-script path instead: a fresh, unloaded window
    window2 = Window(script_func=captured.append)
    window2.preload('Lib.registerHorzScaleBehavior("x", new X())')
    assert window2.scripts[0].startswith('Lib.registerHorzScaleBehavior')
    assert chart is not None


def test_preload_order_is_preserved():
    window = Window(script_func=lambda script: None)
    window.preload('first')
    window.preload('second')
    window.run_script('handler')
    assert window.scripts[:3] == ['first', 'second', 'handler']


def test_preload_after_load_raises():
    window = Window(script_func=lambda script: None)
    window.loaded = True
    with pytest.raises(RuntimeError):
        window.preload('too late')


def test_custom_kind_is_accepted():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True

    class CustomScaleChart(AbstractChart):
        _chart_kind = 'custom:myScale'

    CustomScaleChart(window)
    assert any('"custom:myScale"' in script for script in captured)
