import { describe, expect, it } from 'vitest';

import { LineFillPaneRenderer } from '../src/line-fill/pane-renderer';

/** Records fill()/stroke()/path calls so we can assert on the segments drawn. */
function makeTarget() {
    const fills: number[] = [];
    let pathPoints = 0;
    const context = {
        globalAlpha: 1,
        fillStyle: '',
        strokeStyle: '',
        lineWidth: 1,
        beginPath() { pathPoints = 0; },
        moveTo() { pathPoints++; },
        lineTo() { pathPoints++; },
        closePath() { /* noop */ },
        fill() { fills.push(pathPoints); },
        stroke() { /* noop */ },
        setLineDash() { /* noop */ },
    };
    return {
        fills,
        useBitmapCoordinateSpace(callback: (scope: unknown) => void): void {
            callback({
                context,
                horizontalPixelRatio: 1,
                verticalPixelRatio: 1,
                mediaSize: { width: 800, height: 600 },
                bitmapSize: { width: 800, height: 600 },
            });
        },
    };
}

const OPTIONS = { fillColor: '#2962FF', opacity: 0.2, lineColor: null, lineWidth: 1, lineStyle: 0 };

function point(x: number, y1: number, y2: number) {
    return { x, y1, y2 };
}

describe('line-fill NaN gaps', () => {
    it('fills one segment when every point is valid', () => {
        const target = makeTarget();
        new LineFillPaneRenderer(
            [point(0, 1, 3), point(1, 2, 3), point(2, 1, 4)], OPTIONS as never,
        ).draw(target as never);
        expect(target.fills).toHaveLength(1);          // 一条闭合路径
        expect(target.fills[0]).toBe(6);               // 3 上边界 + 3 下边界
    });

    it('breaks the band where a channel line has no value', () => {
        const target = makeTarget();
        new LineFillPaneRenderer([
            point(0, 1, 3), point(1, 2, 3),
            point(2, Number.NaN, 3),                   // <- 上通道线缺值
            point(3, 2, 4), point(4, 1, 3),
        ], OPTIONS as never).draw(target as never);
        expect(target.fills).toHaveLength(2);          // 缺口两侧各一段
        expect(target.fills).toEqual([4, 4]);
    });

    it('skips leading/trailing gaps and single-point runs', () => {
        const target = makeTarget();
        new LineFillPaneRenderer([
            point(0, Number.NaN, 1), point(1, 1, 2),   // 开头缺
            point(2, 2, 2),                            // [1,2] -> 2 点，够一段
            point(3, Number.NaN, 3), point(4, 3, 4),   // 中间缺
            point(5, Number.NaN, 5),                   // 结尾缺
        ], OPTIONS as never).draw(target as never);
        // 只有 [1,2] 这一段够画（末尾单点不成段）
        expect(target.fills).toEqual([4]);
    });

    it('draws nothing when fewer than two valid points exist', () => {
        const target = makeTarget();
        new LineFillPaneRenderer(
            [point(0, 1, 2), point(1, Number.NaN, 2)], OPTIONS as never,
        ).draw(target as never);
        expect(target.fills).toHaveLength(0);
    });
});
