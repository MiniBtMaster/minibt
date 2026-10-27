import { describe, expect, it } from 'vitest';
import { LineStyle } from 'lightweight-charts';

import { HorizontalLinePaneRenderer } from '../src/horizontal-line/pane-renderer';
import { HorizontalLineAxisView } from '../src/horizontal-line/axis-view';
import { HorizontalLine } from '../src/horizontal-line/horizontal-line';

interface DrawnText { text: string; x: number; y: number; }
interface DrawnBox { x: number; y: number; width: number; height: number; }

function makeTarget(ratio = 1) {
    const boxes: DrawnBox[] = [];
    const texts: DrawnText[] = [];
    const context = {
        fillStyle: '',
        strokeStyle: '',
        lineWidth: 1,
        font: '',
        textAlign: 'left' as CanvasTextAlign,
        textBaseline: 'middle' as CanvasTextBaseline,
        beginPath() { /* noop */ },
        stroke() { /* noop */ },
        setLineDash() { /* noop */ },
        moveTo() { /* noop */ },
        lineTo() { /* noop */ },
        measureText(text: string) { return { width: text.length * 6 }; },
        fillRect(x: number, y: number, width: number, height: number) {
            boxes.push({ x, y, width, height });
        },
        fillText(text: string, x: number, y: number) {
            texts.push({ text, x, y });
        },
    };
    const target = {
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
    return { target, boxes, texts };
}

const options = {
    lineColor: '#ef5350',
    lineStyle: LineStyle.Dashed,
    width: 2,
    text: '多仓1手 亏损-30.00',
};

describe('horizontal line in-pane label', () => {
    it('draws the label pinned to the left edge of the visible range', () => {
        const { target, boxes, texts } = makeTarget();
        const renderer = new HorizontalLinePaneRenderer(
            { x: null, y: 100 }, { ...options, labelVisible: true } as never);
        renderer.draw(target as never);

        expect(texts).toHaveLength(1);
        expect(texts[0].text).toBe(options.text);
        // x = 0 (pane's left border) + 6px padding
        expect(texts[0].x).toBe(6);
        // background box also starts at the very left of the pane
        expect(boxes).toHaveLength(1);
        expect(boxes[0].x).toBe(0);
        expect(boxes[0].width).toBeGreaterThan(texts[0].text.length * 6);
    });

    it('draws nothing in the pane when the label is not enabled', () => {
        const { target, boxes, texts } = makeTarget();
        const renderer = new HorizontalLinePaneRenderer(
            { x: null, y: 100 }, { ...options, labelVisible: false } as never);
        renderer.draw(target as never);

        expect(texts).toHaveLength(0);
        expect(boxes).toHaveLength(0);
    });

    it('hides the price-axis badge when axisLabelVisible is false', () => {
        const hidden = new HorizontalLineAxisView(
            { _options: { axisLabelVisible: false } } as never);
        const shown = new HorizontalLineAxisView(
            { _options: {} } as never);
        expect(hidden.visible()).toBe(false);
        expect(shown.visible()).toBe(true);
    });

    it('contributes no axis view when hidden, so the price scale keeps its width', () => {
        const hidden = new HorizontalLine(
            { price: 100 } as never, { axisLabelVisible: false } as never);
        const shown = new HorizontalLine(
            { price: 100 } as never, { axisLabelVisible: true } as never);
        expect(hidden.priceAxisViews()).toHaveLength(0);
        expect(shown.priceAxisViews()).toHaveLength(1);
    });
});
