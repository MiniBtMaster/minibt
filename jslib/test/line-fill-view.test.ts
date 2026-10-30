import { describe, expect, it } from 'vitest';

import { LineFillPaneView } from '../src/line-fill/pane-view';

/** 最小可用的 LineFill 替身：pane-view 只用到这几个成员。 */
function fakeSource(points: Array<[unknown, number | undefined]>) {
    const times = points.map(([time]) => time);
    return {
        chart: {
            timeScale: () => ({
                timeToCoordinate: (t: unknown) => t as number,
                // 索引连续（不制造额外断点）——缺口由 value===undefined 触发
                timeToIndex: (t: unknown) => t as number,
            }),
        },
        series: {
            data: () => points.map(([time, value]) => ({ time, value })),
            priceToCoordinate: (v: number) => v,
        },
        _other: {
            // 另一条通道线：第 3 个点没有值
            data: () => points.map(([time], i) => (i === 2 ? { time } : { time, value: 5 })),
            priceToCoordinate: (v: number) => v,
        },
        _options: {},
    };
}

describe('line-fill pane view keeps the gaps', () => {
    it('turns a missing value into an explicit NaN break point', () => {
        const view = new LineFillPaneView(fakeSource([
            [0, 1], [1, 2], [2, undefined], [3, 3],
        ]) as never);
        view.update();
        const points = view._points as Array<{ x: number; y1: number; y2: number }>;
        expect(points).toHaveLength(4);                       // 缺值那根**保留**
        expect(points.map(p => p.x)).toEqual([0, 1, 2, 3]);
        expect(Number.isFinite(points[2].y1)).toBe(false);    // 断点：y 是 NaN
        expect(Number.isFinite(points[2].y2)).toBe(false);
        expect(points[0].y1).toBe(1);
        expect(points[3].y2).toBe(5);
    });

    it('treats a transparent per-point colour as a gap', () => {
        // pylightcharts 的"单序列 + 透明缺口"路径：缺口点有值但颜色透明
        const source = {
            chart: {
                timeScale: () => ({
                    timeToCoordinate: (t: unknown) => t as number,
                    timeToIndex: (t: unknown) => t as number,
                }),
            },
            series: {
                data: () => [
                    { time: 0, value: 1, color: '#26a69a' },
                    { time: 1, value: 2, color: 'rgba(0, 0, 0, 0)' },
                    { time: 2, value: 3, color: '#26a69a' },
                ],
                priceToCoordinate: (v: number) => v,
            },
            _other: {
                data: () => [{ time: 0, value: 5 }, { time: 1, value: 5 },
                             { time: 2, value: 5 }],
                priceToCoordinate: (v: number) => v,
            },
            _options: {},
        } as never;
        const view = new LineFillPaneView(source);
        view.update();
        const points = view._points as Array<{ y1: number; y2: number }>;
        expect(points).toHaveLength(3);
        expect(Number.isFinite(points[0].y1)).toBe(true);
        expect(Number.isFinite(points[1].y1)).toBe(false);    // 透明 -> 断点
        expect(Number.isFinite(points[1].y2)).toBe(false);
        expect(Number.isFinite(points[2].y1)).toBe(true);
    });

    it('breaks when the *other* line is the one missing a value', () => {
        const source = fakeSource([[0, 1], [1, 2], [2, 3]]) as never;
        const view = new LineFillPaneView(source);
        // 让"另一条线"在第 1 个点上缺值
        (source as { _other: { data: () => unknown[] } })._other.data = () =>
            [{ time: 0, value: 5 }, { time: 1 }, { time: 2, value: 5 }];
        view.update();
        const points = view._points as Array<{ y1: number; y2: number }>;
        expect(points).toHaveLength(3);
        expect(Number.isFinite(points[1].y1)).toBe(false);
        expect(Number.isFinite(points[1].y2)).toBe(false);
        expect(Number.isFinite(points[0].y1)).toBe(true);
    });
});
