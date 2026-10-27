/**
 * Upstream-value re-exports.
 *
 * The generic RPC (`rpc.ts`) can only *call methods* on objects that are
 * reachable from `globalThis` (or the registry). Module-scope symbols such as
 * enums, `version()` and the type guards are therefore invisible to Python
 * even though the chart engine uses them everywhere.
 *
 * This module surfaces the value-level parts of the public Lightweight Charts
 * API on the `Lib` global so the Python layer can expose real constants instead
 * of guessing integer values.
 *
 * NOTE: `MarkerSign` is a `const enum` (erased at compile time) and therefore
 * cannot be re-exported as a runtime value; its members are trivial
 * (-1 / 0 / 1) and live in `pylightcharts/constants.py` instead.
 */
export {
    ColorType,
    CrosshairMode,
    LastPriceAnimationMode,
    LineStyle,
    LineType,
    MismatchDirection,
    PriceLineSource,
    PriceScaleMode,
    TickMarkType,
    TrackingModeExitMode,
    version,
    isBusinessDay,
    isUTCTimestamp,
    defaultHorzScaleBehavior,
    customSeriesDefaultOptions,
    // factory functions: escape hatch for advanced hosts that build their own
    // chart/plugin outside the Handler helpers
    createChart,
    createChartEx,
    createOptionsChart,
    createYieldCurveChart,
    createSeriesMarkers,
    createUpDownMarkers,
    createTextWatermark,
    createImageWatermark,
} from 'lightweight-charts';
