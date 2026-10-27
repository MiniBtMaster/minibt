#!/usr/bin/env python3
"""Lightweight Charts API 覆盖率检查器。

解析上游 ``typings.d.ts`` 中关键接口的成员，与 :data:`MANIFEST` 里登记的
“Python 侧实现符号”（``None`` 表示尚未封装）对照，输出覆盖率，并可用
``--check`` 在 CI 中防止覆盖率回退。

用法::

    python scripts/check_api_coverage.py                 # 打印报告
    python scripts/check_api_coverage.py --check         # 覆盖率低于基线则退出码 1
    python scripts/check_api_coverage.py --write-baseline
    python scripts/check_api_coverage.py --markdown docs/_generated/api_coverage.md

上游文件默认取自 ``jslib/node_modules/lightweight-charts/dist/typings.d.ts``。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TYPINGS = ROOT / "jslib" / "node_modules" / "lightweight-charts" / "dist" / "typings.d.ts"
BASELINE = ROOT / "scripts" / "api_coverage_baseline.json"

#: 接口 → 成员 → Python 侧实现符号（``None`` = 尚未封装）。
#: 成员名与上游 ``typings.d.ts`` 完全一致（camelCase）。
MANIFEST: dict[str, dict[str, str | None]] = {
    "IChartApiBase": {
        "remove": "AbstractChart.remove",
        "resize": "AbstractChart.resize",
        "addCustomSeries": "AbstractChart.add_custom_series",
        "addSeries": "AbstractChart.add_series",
        "removeSeries": "*.delete",
        "subscribeClick": "Events.click",
        "unsubscribeClick": "JSEmitter.unsubscribe",
        "subscribeDblClick": "Events.dblclick",
        "unsubscribeDblClick": "JSEmitter.unsubscribe",
        "subscribeCrosshairMove": "Events.crosshair_move",
        "unsubscribeCrosshairMove": "JSEmitter.unsubscribe",
        "priceScale": "AbstractChart.get_price_scale",
        "timeScale": "AbstractChart.time_scale*",
        "applyOptions": "AbstractChart.apply_options",
        "options": "AbstractChart.chart_options",
        "takeScreenshot": "AbstractChart.screenshot",
        "addPane": "AbstractChart.add_pane",
        "panes": "AbstractChart.pane_*",
        "removePane": "AbstractChart.remove_pane",
        "swapPanes": "AbstractChart.swap_panes",
        "autoSizeActive": "AbstractChart.auto_size_active",
        "chartElement": "AbstractChart.chart_element",
        "setCrosshairPosition": "AbstractChart.set_crosshair_position",
        "clearCrosshairPosition": "AbstractChart.clear_crosshair_position",
        "paneSize": "AbstractChart.pane_size",
        "horzBehaviour": "AbstractChart.horz_behavior",
    },
    "ISeriesApi": {
        "priceFormatter": "SeriesCommon.price_formatter",
        "priceToCoordinate": "SeriesCommon.price_to_coordinate",
        "coordinateToPrice": "SeriesCommon.coordinate_to_price",
        "barsInLogicalRange": "SeriesCommon.bars_in_logical_range",
        "applyOptions": "SeriesCommon.apply_options",
        "options": "SeriesCommon.options",
        "priceScale": "SeriesCommon.price_scale_options",
        "setData": "SeriesCommon.set",
        "update": "SeriesCommon.update",
        "pop": "SeriesCommon.pop",
        "dataByIndex": "SeriesCommon.data_by_index",
        "data": "SeriesCommon.data_points",
        "subscribeDataChanged": "SeriesCommon.subscribe_data_changed",
        "unsubscribeDataChanged": "SeriesCommon.unsubscribe_data_changed",
        "createPriceLine": "SeriesCommon.create_price_line",
        "removePriceLine": "PriceLine.remove",
        "priceLines": "SeriesCommon.js_price_lines",
        "seriesType": "SeriesCommon.series_type",
        "lastValueData": "SeriesCommon.last_value_data",
        "attachPrimitive": "SeriesCommon.attach_primitive",
        "detachPrimitive": "SeriesCommon.detach_primitive",
        "moveToPane": "SeriesCommon.move_to_pane",
        "seriesOrder": "SeriesCommon.series_order",
        "setSeriesOrder": "SeriesCommon.set_series_order",
        "getPane": "SeriesCommon.get_pane_index",
    },
    "ITimeScaleApi": {
        "scrollPosition": "AbstractChart.scroll_position",
        "scrollToPosition": "AbstractChart.scroll_to_position",
        "scrollToRealTime": "AbstractChart.scroll_to_real_time",
        "getVisibleRange": "AbstractChart.get_visible_range",
        "setVisibleRange": "AbstractChart.set_visible_range",
        "getVisibleLogicalRange": "AbstractChart.get_visible_logical_range",
        "setVisibleLogicalRange": "AbstractChart.set_visible_logical_range",
        "resetTimeScale": "AbstractChart.reset_time_scale",
        "fitContent": "AbstractChart.fit",
        "logicalToCoordinate": "AbstractChart.logical_to_coordinate",
        "coordinateToLogical": "AbstractChart.coordinate_to_logical",
        "timeToIndex": "AbstractChart.time_to_index",
        "timeToCoordinate": "AbstractChart.time_to_coordinate",
        "coordinateToTime": "AbstractChart.coordinate_to_time",
        "width": "AbstractChart.time_scale_width",
        "height": "AbstractChart.time_scale_height",
        "subscribeVisibleTimeRangeChange": "Events.visible_time_range_change",
        "unsubscribeVisibleTimeRangeChange": "JSEmitter.unsubscribe",
        "subscribeVisibleLogicalRangeChange": "Events.range_change",
        "unsubscribeVisibleLogicalRangeChange": "JSEmitter.unsubscribe",
        "subscribeSizeChange": "Events.size_change",
        "unsubscribeSizeChange": "JSEmitter.unsubscribe",
        "applyOptions": "AbstractChart.time_scale_options",
        "options": "AbstractChart.time_scale_settings",
    },
    "IPriceScaleApi": {
        "applyOptions": "PriceScale.apply_options",
        "options": "PriceScale.options",
        "width": "PriceScale.width",
        "setVisibleRange": "PriceScale.set_visible_range",
        "getVisibleRange": "PriceScale.get_visible_range",
        "setAutoScale": "PriceScale.set_auto_scale",
    },
    "IPaneApi": {
        "getHeight": "AbstractChart.pane_height",
        "setHeight": "AbstractChart.set_pane_height",
        "moveTo": "AbstractChart.pane_move_to",
        "paneIndex": "AbstractChart.pane_*",
        "getSeries": "AbstractChart.pane_series_handle",
        "getHTMLElement": "AbstractChart.pane_get_htmlelement",
        "attachPrimitive": "AbstractChart.attach_pane_primitive",
        "detachPrimitive": "AbstractChart.detach_pane_primitive",
        "priceScale": "AbstractChart.pane_price_scale",
        "setPreserveEmptyPane": "AbstractChart.set_pane_preserve_empty",
        "preserveEmptyPane": "AbstractChart.pane_preserve_empty",
        "getStretchFactor": "AbstractChart.pane_stretch_factor",
        "setStretchFactor": "AbstractChart.set_pane_stretch",
        "addCustomSeries": "AbstractChart.pane_add_custom_series",
        "addSeries": "AbstractChart.pane_add_series",
    },
    "IPriceLine": {
        "applyOptions": "PriceLine.apply_options",
        "options": "PriceLine.options",
    },
    "ISeriesMarkersPluginApi": {
        "setMarkers": "SeriesMarkersPlugin.set_markers",
        "markers": "SeriesMarkersPlugin.markers",
        "detach": "SeriesMarkersPlugin.detach",
        "getSeries": "SeriesMarkersPlugin.get_series",
        "applyOptions": "SeriesMarkersPlugin.apply_options",
    },
    "ISeriesUpDownMarkerPluginApi": {
        "applyOptions": "UpDownMarkersPlugin.apply_options",
        "setData": "UpDownMarkersPlugin.set_data",
        "update": "UpDownMarkersPlugin.update",
        "markers": "UpDownMarkersPlugin.markers",
        "setMarkers": "UpDownMarkersPlugin.set_markers",
        "clearMarkers": "UpDownMarkersPlugin.clear_markers",
        "detach": "UpDownMarkersPlugin.detach",
        "getSeries": "UpDownMarkersPlugin.get_series",
    },
    "ITextWatermarkPluginApi": {
        "applyOptions": "TextWatermarkPlugin.apply_options",
        "detach": "TextWatermarkPlugin.detach",
        "getPane": "TextWatermarkPlugin.get_pane",
    },
    "IImageWatermarkPluginApi": {
        "applyOptions": "ImageWatermarkPlugin.apply_options",
        "detach": "ImageWatermarkPlugin.detach",
        "getPane": "ImageWatermarkPlugin.get_pane",
    },
    "ISeriesPrimitiveBase": {
        "updateAllViews": "CallbackPrimitive.updateAllViews",
        "priceAxisViews": "CallbackPrimitive.priceAxisViews",
        "timeAxisViews": "CallbackPrimitive.timeAxisViews",
        "paneViews": "CallbackPrimitive.paneViews",
        "priceAxisPaneViews": "CallbackPrimitive.priceAxisPaneViews",
        "timeAxisPaneViews": "CallbackPrimitive.timeAxisPaneViews",
        "autoscaleInfo": "CallbackPrimitive.autoscaleInfo",
        "attached": "CallbackPrimitive.attached",
        "detached": "CallbackPrimitive.detached",
        "hitTest": "CallbackPrimitive.hitTest",
    },
    "IPanePrimitiveBase": {
        "updateAllViews": "CallbackPanePrimitive.updateAllViews",
        "paneViews": "CallbackPanePrimitive.paneViews",
        "attached": "CallbackPanePrimitive.attached",
        "detached": "CallbackPanePrimitive.detached",
        "hitTest": "CallbackPanePrimitive.hitTest",
    },
    "ICustomSeriesPaneView": {
        "renderer": "CustomSeriesPaneView",
        "update": "CustomSeriesPaneView",
        "priceValueBuilder": "SpecCustomSeriesPaneView.priceValueBuilder",
        "isWhitespace": "SpecCustomSeriesPaneView.isWhitespace",
        "defaultOptions": "SpecCustomSeriesPaneView.defaultOptions",
        "destroy": "SpecCustomSeriesPaneView.destroy",
        "conflationReducer": "SpecCustomSeriesPaneView.conflationReducer",
    },
    "ICustomSeriesPaneRenderer": {
        "draw": "CustomSeriesRenderer",
        "hitTest": "CallbackCustomSeriesRenderer.hitTest",
    },
    "IHorzScaleBehavior": {
        "options": "registerHorzScaleBehaviorSpec.options",
        "setOptions": "registerHorzScaleBehaviorSpec.setOptions",
        "preprocessData": "registerHorzScaleBehaviorSpec.preprocessData",
        "convertHorzItemToInternal": "registerHorzScaleBehaviorSpec.convertHorzItemToInternal",
        "createConverterToInternalObj": "registerHorzScaleBehaviorSpec.createConverterToInternalObj",
        "key": "registerHorzScaleBehaviorSpec.key",
        "cacheKey": "registerHorzScaleBehaviorSpec.cacheKey",
        "updateFormatter": "registerHorzScaleBehaviorSpec.updateFormatter",
        "formatHorzItem": "registerHorzScaleBehaviorSpec.formatHorzItem",
        "formatTickmark": "registerHorzScaleBehaviorSpec.formatTickmark",
        "maxTickMarkWeight": "registerHorzScaleBehaviorSpec.maxTickMarkWeight",
        "fillWeightsForPoints": "registerHorzScaleBehaviorSpec.fillWeightsForPoints",
        "shouldResetTickmarkLabels": "registerHorzScaleBehaviorSpec.shouldResetTickmarkLabels",
    },
}

_MEMBER_RE = re.compile(r"^\s+([A-Za-z_]\w*)\s*\??\s*[:(<]")


def parse_interface_members(path: Path, interface: str) -> list[str]:
    """Return the member names declared inside ``interface <name> {...}``."""
    text = path.read_text(encoding="utf-8")
    # match `export interface <name>` or `interface <name>` (possibly with generics)
    pattern = re.compile(rf"^(?:export\s+)?interface\s+{interface}\b[^{{]*\{{", re.M)
    m = pattern.search(text)
    if not m:
        return []
    i = m.end()
    depth = 1
    members: list[str] = []
    line_start = m.start()
    for line in text[i:].splitlines():
        stripped = line.strip()
        if depth == 1:
            mm = _MEMBER_RE.match(line)
            if mm:
                members.append(mm.group(1))
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            break
    # de-duplicate, preserving order
    seen: set[str] = set()
    out = []
    for name in members:
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def build_report(typings: Path) -> list[dict]:
    report = []
    for interface, mapping in MANIFEST.items():
        members = parse_interface_members(typings, interface)
        if not members:
            # 类型别名（如 ITextWatermarkPluginApi）无法按 interface 解析，
            # 回退到 manifest 登记成员。
            members = list(mapping.keys())
        missing_upstream = [m for m in members if m not in mapping]
        implemented = [m for m in members if mapping.get(m)]
        gaps = [m for m in members if m in mapping and not mapping.get(m)]
        report.append({
            "interface": interface,
            "upstream": len(members),
            "implemented": len(implemented),
            "gaps": len(gaps),
            "coverage": (len(implemented) / len(members)) if members else 0.0,
            "gap_members": gaps,
            "unmapped_members": missing_upstream,
        })
    return report


def print_report(report: list[dict]) -> int:
    total = impl = 0
    print(f"{'interface':<34}{'upstream':>9}{'impl':>6}{'gap':>6}{'cover':>8}")
    print("-" * 63)
    for row in report:
        total += row["upstream"]
        impl += row["implemented"]
        print(f"{row['interface']:<34}{row['upstream']:>9}{row['implemented']:>6}"
              f"{row['gaps']:>6}{row['coverage'] * 100:>7.0f}%")
        if row["gap_members"]:
            print(f"    gaps : {', '.join(row['gap_members'])}")
        if row["unmapped_members"]:
            print(f"    NEW  : {', '.join(row['unmapped_members'])}  (not in manifest)")
    print("-" * 63)
    pct = (impl / total * 100) if total else 0.0
    print(f"{'TOTAL':<34}{total:>9}{impl:>6}{total - impl:>6}{pct:>7.1f}%")
    return impl


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--typings", type=Path, default=TYPINGS)
    ap.add_argument("--check", action="store_true", help="fail if below baseline")
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--markdown", type=Path, default=None)
    args = ap.parse_args()

    if not args.typings.exists():
        print(f"typings.d.ts not found: {args.typings}", file=sys.stderr)
        print("run `cd jslib && npm install` first.", file=sys.stderr)
        return 2

    report = build_report(args.typings)
    implemented = print_report(report)

    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Lightweight Charts API 覆盖率", "",
                 "| 接口 | 上游成员 | 已实现 | 缺口 | 覆盖率 |",
                 "|---|---|---|---|---|"]
        for row in report:
            lines.append(f"| `{row['interface']}` | {row['upstream']} | "
                         f"{row['implemented']} | {row['gaps']} | "
                         f"{row['coverage'] * 100:.0f}% |")
        args.markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"markdown written -> {args.markdown}")

    if args.write_baseline:
        BASELINE.write_text(json.dumps({"implemented": implemented, "total": sum(
            r['upstream'] for r in report)}, indent=2), encoding="utf-8")
        print(f"baseline written -> {BASELINE}")

    if args.check and BASELINE.exists():
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        if implemented < baseline["implemented"]:
            print(f"coverage regressed: {implemented} < {baseline['implemented']}",
                  file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
