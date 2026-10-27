"""Drawing persistence: drawings must survive a window close and come back for the
same symbol + cycle.

The old code had all the pieces (`ChartDataManager`, `CustomToolBox._save_drawings`)
but never wrote to disk, and keyed everything by symbol only. These tests pin the
new behaviour: `{"symbol|cycle": [...]}` in `chart_data.json`, atomic writes, and
a legacy `{symbol: [...]}` fallback.

    pytest tests/test_miniqt_drawings.py
"""
from __future__ import annotations

import json

from miniqt.app.common.chart_data import ChartDataManager, drawing_key


def frame():
    return [
        {"type": "TrendLine", "points": [
            {"time": 1700000000, "logical": 1, "price": 100},
            {"time": 1700003000, "logical": 2, "price": 110}],
         "options": {"lineColor": "#1E80F0"}},
        {"type": "FibonacciRetracement", "points": [
            {"time": 1700000000, "logical": 1, "price": 100},
            {"time": 1700003000, "logical": 2, "price": 110}],
         "options": {}},
    ]


def test_drawing_key_separates_cycles():
    assert drawing_key("SHFE.rb2610", 60) == "SHFE.rb2610|60"
    assert drawing_key("SHFE.rb2610", 300) == "SHFE.rb2610|300"
    # cycle-less form is the legacy / contract-level key
    assert drawing_key("SHFE.rb2610") == "SHFE.rb2610"
    assert drawing_key("SHFE.rb2610", None) == "SHFE.rb2610"


def test_round_trip_through_disk(tmp_path):
    path = tmp_path / "chart_data.json"
    manager = ChartDataManager(str(path))
    manager.set_drawings("SHFE.rb2610|60", frame())
    manager.set_drawings("SHFE.rb2610|300", [{"type": "HorizontalLine"}])

    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "SHFE.rb2610|60" in payload["drawings"]

    # a fresh manager reads it back
    reloaded = ChartDataManager(str(path))
    assert reloaded.get_drawings("SHFE.rb2610|60") == frame()
    assert reloaded.get_drawings("SHFE.rb2610|300") != frame()


def test_legacy_symbol_only_key_still_loads(tmp_path):
    path = tmp_path / "chart_data.json"
    manager = ChartDataManager(str(path))
    manager.set_drawings("SHFE.rb2610", frame())     # old format: symbol only

    assert manager.get_drawings("SHFE.rb2610|60",
                                legacy_key="SHFE.rb2610") == frame()
    # a different cycle does not inherit the legacy data unless asked via legacy_key
    assert manager.get_drawings("SHFE.rb2610|300") == []


def test_clear(tmp_path):
    manager = ChartDataManager(str(tmp_path / "d.json"))
    manager.set_drawings("A|60", frame())
    manager.set_drawings("B|60", frame())

    manager.clear_drawings("A|60")
    assert manager.get_drawings("A|60") == []
    assert manager.get_drawings("B|60") == frame()

    manager.clear_drawings()
    assert manager.drawings == {}


def test_save_is_atomic_and_leaves_no_temp_files(tmp_path):
    path = tmp_path / "d.json"
    manager = ChartDataManager(str(path))
    for index in range(5):
        manager.set_drawings(f"A|{index}", frame())

    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []
    assert json.loads(path.read_text(encoding="utf-8"))["drawings"]


def test_validate_drops_bad_entries(tmp_path):
    path = tmp_path / "d.json"
    path.write_text(json.dumps({
        "drawings": {"good|60": frame(), "bad|60": "not-a-list", "empty|60": []},
        "price_alerts": {"A|60": {"enabled": True}, "bad": 1},
    }), encoding="utf-8")

    manager = ChartDataManager(str(path))
    assert "good|60" in manager.drawings
    assert "bad|60" not in manager.drawings
    assert "empty|60" not in manager.drawings
    assert manager.get_price_alerts("A|60") == {"enabled": True}


def indicator_spec():
    return [{'group': 'TaLib', 'name': 'MACD',
             'params': {'fastperiod': 12, 'slowperiod': 26},
             'price_line': False, 'price_label': False}]


def test_indicator_round_trip_through_disk(tmp_path):
    """新引擎的指标持久化：按 `合约|周期` 存规格 ✓。"""
    path = tmp_path / "chart_data.json"
    manager = ChartDataManager(str(path))
    manager.set_indicators("SHFE.rb2610|60", indicator_spec())

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "indicators" in payload
    reloaded = ChartDataManager(str(path))
    assert reloaded.get_indicators("SHFE.rb2610|60") == indicator_spec()
    assert reloaded.get_indicators("SHFE.rb2610|300") == []


def test_indicator_clear(tmp_path):
    manager = ChartDataManager(str(tmp_path / "d.json"))
    manager.set_indicators("A|60", indicator_spec())
    manager.clear_indicators("A|60")
    assert manager.get_indicators("A|60") == []


def test_validate_drops_bad_indicators(tmp_path):
    path = tmp_path / "d.json"
    path.write_text(json.dumps({
        "indicators": {"good|60": indicator_spec(), "bad|60": "not-a-list"},
    }), encoding="utf-8")
    manager = ChartDataManager(str(path))
    assert manager.get_indicators("good|60") == indicator_spec()
    assert manager.get_indicators("bad|60") == []


#: 工具箱 13 种画线的存档格式（`{type, points, options}` ✓）
ALL_DRAWING_TYPES = (
    'TrendLine', 'Box', 'HorizontalLine', 'RayLine', 'VerticalLine',
    'FibonacciRetracement', 'FibonacciExtension', 'Measure',
    'ParallelChannel', 'Position', 'AndrewsPitchfork', 'Triangle', 'GannFan',
)


def all_drawings():
    """每种画线一条（点格式与 toolbox 保存的一致：time/logical/price ✓）。"""
    point = {'time': 1700000000, 'logical': 1, 'price': 100.0}
    out = []
    for kind in ALL_DRAWING_TYPES:
        out.append({'type': kind,
                    'points': [dict(point), {**point, 'time': 1700003600,
                                             'logical': 2, 'price': 105.0}],
                    'options': {'lineColor': '#1E80F0'}})
    return out


def test_all_13_drawing_types_round_trip(tmp_path):
    """13 种画线都能按 `合约|周期` 存下并原样读回 ✓。"""
    manager = ChartDataManager(str(tmp_path / "d.json"))
    manager.set_drawings("SHFE.rb2610|60", all_drawings())
    reloaded = ChartDataManager(str(tmp_path / "d.json"))
    saved = reloaded.get_drawings("SHFE.rb2610|60")
    assert [d['type'] for d in saved] == list(ALL_DRAWING_TYPES)
    assert saved[0]['points'][0]['logical'] == 1


def test_bundle_loads_all_13_drawing_types():
    """编译后的 bundle 里 `loadDrawings` 必须认得这 13 种（少一种就静默丢失 ✗）。"""
    import pathlib
    bundle = (pathlib.Path(__file__).resolve().parents[1]
              / 'pylightcharts' / 'js' / 'bundle.js')
    text = bundle.read_text(encoding='utf-8')
    for kind in ALL_DRAWING_TYPES:
        assert f'"{kind}"' in text or f"'{kind}'" in text, kind
    # 恢复后按新周期重算 bar 序号（切周期画线不跑偏 ✓）
    assert 'repositionOnTime' in text
