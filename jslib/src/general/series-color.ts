import { ISeriesApi, SeriesType } from "lightweight-charts";

/**
 * The colour a series draws itself with.
 *
 * Series types disagree on the option that carries their colour: line / bar /
 * candlestick use `color`, an area uses `lineColor` / `topColor`, and a custom
 * series has none unless the caller passed one. The legend and both tooltips
 * need the same answer, so it lives here (the legend used to compute it
 * inline).
 *
 * `color` is what the series was given, `solid` the same colour with an `rgba`
 * alpha forced to 1 so text drawn in it stays readable.
 */
export function seriesColor(series: ISeriesApi<SeriesType>): { color: string, solid: string } {
    const options = series.options() as {
        color?: string, lineColor?: string, topColor?: string, bottomColor?: string
    };
    const color = options.color ?? options.lineColor ?? options.topColor
        ?? options.bottomColor ?? '#2196f3';
    const solid = color.startsWith('rgba') ? color.replace(/[^,]+(?=\))/, '1') : color;
    return { color, solid };
}
