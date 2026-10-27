import { describe, expect, it } from 'vitest';

import { CustomSeriesPaneView, textLineOffsets } from '../src/custom-series/custom-series';

/**
 * Regression tests for the "off-screen shapes pile up while zooming" bug.
 *
 * The library only writes coordinates for the bars inside `visibleRange`
 * (`TimeScale.indexesToCoordinates`). Bars outside it keep a stale - and still
 * finite - `x` from the previous viewport, so a renderer that iterates `_bars`
 * re-draws them on top of the visible data.
 */

interface Rect {
    x: number;
    y: number;
    width: number;
    height: number;
}

/** A CanvasRenderingTarget2D stand-in that records fillRect calls. */
interface DrawnText {
    text: string;
    x: number;
    y: number;
    font?: string;
}

interface DrawnBox {
    x: number;
    y: number;
    width: number;
    height: number;
}

function makeTarget(recorded: Rect[], texts: DrawnText[] = [],
                    boxes: DrawnBox[] = [], ratio = 1) {
    const context = {
        fillStyle: '',
        strokeStyle: '',
        lineWidth: 1,
        font: '',
        textAlign: 'center' as CanvasTextAlign,
        textBaseline: 'middle' as CanvasTextBaseline,
        save() { /* noop */ },
        restore() { /* noop */ },
        beginPath() { /* noop */ },
        fill() { /* noop */ },
        stroke() { /* noop */ },
        setLineDash() { /* noop */ },
        moveTo() { /* noop */ },
        lineTo() { /* noop */ },
        arc() { /* noop */ },
        globalAlpha: 1,
        fillText(text: string, x: number, y: number) {
            texts.push({ text, x, y, font: this.font });
        },
        measureText(text: string) { return { width: text.length * 6 }; },
        roundRect(x: number, y: number, width: number, height: number) {
            boxes.push({ x, y, width, height });
        },
        strokeRect() { /* noop */ },
        fillRect(x: number, y: number, width: number, height: number) {
            recorded.push({ x, y, width, height });
        },
    };
    return {
        useBitmapCoordinateSpace(callback: (scope: unknown) => void): void {
            callback({
                context,
                horizontalPixelRatio: ratio,
                verticalPixelRatio: ratio,
                mediaSize: { width: 800, height: 600 },
                bitmapSize: { width: 800, height: 600 },
            });
        },
    };
}

/** One bar whose rect spans the price range [index, index + 1]. */
function bar(index: number, x: number) {
    return {
        x,
        originalData: {
            time: index,
            value: 100,
            shapes: [
                {
                    type: 'rect',
                    from: index,
                    to: index + 1,
                    left: -0.1,
                    right: 0.1,
                    fillColor: '#00ff00',
                },
            ],
        },
    };
}

const CONVERTER = (price: number): number => price;

describe('custom series visible range', () => {
    it('draws only the bars inside visibleRange', () => {
        const view = new CustomSeriesPaneView();
        // All ten bars carry a coordinate from a previous, wider viewport; the
        // current visible slice is 4..7, the rest are stale.
        const bars = Array.from({ length: 10 }, (_, index) => bar(index, index * 10));
        view.update(
            { bars, barSpacing: 10, visibleRange: { from: 4, to: 7 }, conflationFactor: 1 } as never,
            {} as never,
        );

        const drawn: Rect[] = [];
        view.renderer().draw(makeTarget(drawn) as never, CONVERTER as never);

        // The y coordinate is the bar's price, so it identifies the bar.
        expect(drawn.map(rect => rect.y)).toEqual([4, 5, 6]);
    });

    it('skips bars without a finite coordinate', () => {
        const view = new CustomSeriesPaneView();
        const bars = [bar(0, 0), { x: NaN, originalData: bar(1, 0).originalData }, bar(2, 20)];
        view.update(
            { bars, barSpacing: 10, visibleRange: { from: 0, to: 3 }, conflationFactor: 1 } as never,
            {} as never,
        );

        const drawn: Rect[] = [];
        view.renderer().draw(makeTarget(drawn) as never, CONVERTER as never);

        expect(drawn.map(rect => rect.y)).toEqual([0, 2]);
    });

    it('exposes the visible slice to rendererDraw callbacks', () => {
        const view = new CustomSeriesPaneView();
        const bars = Array.from({ length: 10 }, (_, index) => bar(index, index * 10));
        view.update(
            { bars, barSpacing: 10, visibleRange: { from: 4, to: 7 }, conflationFactor: 1 } as never,
            {} as never,
        );

        expect(view.visibleBars()).toEqual(bars.slice(4, 7));
    });

    it('falls back to every bar when no visible range is known', () => {
        const view = new CustomSeriesPaneView();
        const bars = [bar(0, 0), bar(1, 10)];
        view.update(
            { bars, barSpacing: 10, visibleRange: null, conflationFactor: 1 } as never,
            {} as never,
        );

        expect(view.visibleBars()).toEqual(bars);
    });
});

/** One bar carrying a single text shape. */
function textBar(index: number, x: number, text: string, baseline: string) {
    return {
        x,
        originalData: {
            time: index,
            value: 100,
            shapes: [
                { type: 'text', price: 100, text, offset: 0, fontSize: 12, baseline },
            ],
        },
    };
}

describe('custom series multi-line text', () => {
    it('lays out newline separated lines around the anchor', () => {
        expect(textLineOffsets('A', 12, 'middle')).toEqual([0]);
        expect(textLineOffsets('A\nB\nC', 12, 'top')).toEqual([0, 12, 24]);
        expect(textLineOffsets('A\nB\nC', 12, 'bottom')).toEqual([-24, -12, 0]);
        expect(textLineOffsets('A\nB\nC', 12, 'middle')).toEqual([-12, 0, 12]);
        expect(textLineOffsets(undefined, 12, 'middle')).toEqual([0]);
    });

    it('draws every line of a multi-line label', () => {
        const view = new CustomSeriesPaneView();
        const bars = [textBar(0, 0, 'BUY\nCCI\nRSI', 'middle')];
        view.update(
            { bars, barSpacing: 10, visibleRange: { from: 0, to: 1 }, conflationFactor: 1 } as never,
            {} as never,
        );

        const drawn: Rect[] = [];
        const texts: DrawnText[] = [];
        view.renderer().draw(makeTarget(drawn, texts) as never, CONVERTER as never);

        expect(texts.map(item => item.text)).toEqual(['BUY', 'CCI', 'RSI']);
        expect(texts[0].y).toBeCloseTo(85.6, 4);    // 100 - (3-1)/2 * 1.2 * 12
        expect(texts[1].y).toBeCloseTo(100, 4);
        expect(texts[2].y).toBeCloseTo(114.4, 4);
    });
});


/** One bar carrying a single, fully styled text shape. */
function styledTextBar(index: number, x: number, shape: Record<string, unknown>) {
    return {
        x,
        originalData: {
            time: index,
            value: 100,
            shapes: [{ type: 'text', price: 100, ...shape }],
        },
    };
}

describe('custom series text style', () => {
    function draw(shape: Record<string, unknown>, ratio = 1) {
        const view = new CustomSeriesPaneView();
        const bars = [styledTextBar(0, 0, shape)];
        view.update(
            { bars, barSpacing: 10, visibleRange: { from: 0, to: 1 }, conflationFactor: 1 } as never,
            {} as never,
        );
        const drawn: Rect[] = [];
        const texts: DrawnText[] = [];
        const boxes: DrawnBox[] = [];
        view.renderer().draw(makeTarget(drawn, texts, boxes, ratio) as never,
                             CONVERTER as never);
        return { texts, boxes };
    }

    it('applies pixel offsets (scaled by the pixel ratio)', () => {
        const one = draw({ text: 'X', offsetX: 5, offsetY: -7 });
        expect(one.texts[0].x).toBe(5);
        expect(one.texts[0].y).toBe(93);

        // ratio=2：锚点(100)与偏移(-7)都按 v 放大 -> 200 - 14 = 186
        const two = draw({ text: 'X', offsetX: 5, offsetY: -7 }, 2);
        expect(two.texts[0].x).toBe(10);
        expect(two.texts[0].y).toBe(186);
    });

    it('builds the canvas font from weight / style / family', () => {
        const { texts } = draw({
            text: 'X', fontFamily: 'serif', fontWeight: 'bold', fontStyle: 'italic',
            fontSize: 14,
        });
        expect(texts[0].font).toBe('italic bold 14px serif');
    });

    it('draws a background box behind a multi-line label', () => {
        const { texts, boxes } = draw({
            text: 'BUY\nCCI', backgroundColor: '#222', padding: 4, fontSize: 12,
        });
        expect(texts.map(item => item.text)).toEqual(['BUY', 'CCI']);
        expect(boxes).toHaveLength(1);
        // 两行 3 个字符（18px 宽）+ 左右各 4px padding
        expect(boxes[0].width).toBeCloseTo(3 * 6 + 8, 3);
        expect(boxes[0].height).toBeGreaterThan(0);
    });
});
