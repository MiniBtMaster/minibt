import { IPrimitivePaneView } from "lightweight-charts";
import { FillPoint, LineFill } from "./line-fill";
import { LineFillPaneRenderer } from "./pane-renderer";

interface PointLike {
    time: unknown;
    value?: number;
    color?: string;
}

/**
 * A fully transparent per-point colour marks a **gap**.
 *
 * `pylightcharts` draws fragmented lines with one series (gap points are filled
 * with the previous value and coloured transparent) instead of one series per
 * segment; the band must treat those points as breaks, or it fills straight
 * across the gap.
 */
function isTransparentColour(colour: unknown): boolean {
    if (typeof colour !== 'string') return false;
    const value = colour.trim().toLowerCase();
    if (value === 'transparent') return true;
    const rgba = value.match(
        /^rgba\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+\s*,\s*([\d.]+)\s*\)$/);
    if (rgba) return parseFloat(rgba[1]) === 0;
    const hex = value.match(/^#([0-9a-f]{8})$/);
    if (hex) return hex[1].slice(6) === '00';
    return false;
}

export class LineFillPaneView implements IPrimitivePaneView {
    _source: LineFill;
    _points: FillPoint[] = [];

    constructor(source: LineFill) {
        this._source = source;
    }

    zOrder(): 'bottom' | 'normal' | 'top' {
        return 'bottom';
    }

    update() {
        const source = this._source;
        const timeScale = source.chart.timeScale();

        // the other line is looked up by time: only the shared stamps are filled
        const others = new Map<unknown, number>();
        for (const point of source._other.data() as PointLike[]) {
            if (point.value !== undefined && !isTransparentColour(point.color)) {
                others.set(point.time, point.value);
            }
        }

        const points: FillPoint[] = [];
        // 缺值的 bar 必须**保留成断点**（y1/y2 = NaN），渲染端据此把色带切成几段。
        // 两个来源都要处理：
        //   1) 这根 bar 本身缺值（`value === undefined`，数据里下发了空白点）；
        //   2) LWC 的 `series.data()` **不会返回空白点**（实测），所以序列看似
        //      "连续"，但两根 bar 的**逻辑索引跳了**（中间有别的序列的 bar）——
        //      用 `timeToIndex` 检测这种跳跃，补一个断点。
        const gap = (x: number): FillPoint => ({ x, y1: Number.NaN, y2: Number.NaN });
        let previousIndex: number | null = null;
        for (const point of source.series.data() as PointLike[]) {
            const x = timeScale.timeToCoordinate(point.time as never);
            if (x === null) continue;                    // 不在时间轴上：整根跳过
            const logical = timeScale.timeToIndex(point.time as never, false);
            if (previousIndex !== null && logical !== null && logical - previousIndex > 1) {
                points.push(gap(x as number));           // 中间空了 bar -> 断开
            }
            previousIndex = logical === null ? previousIndex : logical;
            const otherValue = others.get(point.time);
            if (point.value === undefined || otherValue === undefined
                || isTransparentColour(point.color)) {   // 透明点 = 缺口
                points.push(gap(x as number));
                continue;
            }
            const y1 = source.series.priceToCoordinate(point.value);
            const y2 = source._other.priceToCoordinate(otherValue);
            if (y1 === null || y2 === null) {
                points.push(gap(x as number));
                continue;
            }
            points.push({ x: x as number, y1: y1 as number, y2: y2 as number });
        }
        this._points = points;
    }

    renderer() {
        return new LineFillPaneRenderer(this._points, this._source._options);
    }
}
