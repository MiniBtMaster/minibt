import { CanvasRenderingTarget2D } from 'fancy-canvas';
import { TwoPointDrawingPaneRenderer } from '../drawing/pane-renderer';
import { ViewPoint } from '../drawing/pane-view';
import { setLineStyle } from '../helpers/canvas-rendering';
import { defaultFibonacciLevels, FibonacciOptions } from './fibonacci';

export class FibonacciPaneRenderer extends TwoPointDrawingPaneRenderer {
    declare _options: FibonacciOptions;
    private readonly _price1: number;
    private readonly _price2: number;

    constructor(p1: ViewPoint, p2: ViewPoint, options: FibonacciOptions, hovered: boolean,
                price1: number, price2: number) {
        super(p1, p2, options, hovered);
        this._price1 = price1;
        this._price2 = price2;
    }

    draw(target: CanvasRenderingTarget2D) {
        target.useBitmapCoordinateSpace(scope => {
            if (this._p1.x === null || this._p1.y === null || this._p2.x === null || this._p2.y === null) {
                return;
            }
            const ctx = scope.context;
            const h = scope.horizontalPixelRatio;
            const v = scope.verticalPixelRatio;

            const x1 = Math.round(this._p1.x * h);
            const y1 = Math.round(this._p1.y * v);
            const x2 = Math.round(this._p2.x * h);
            const y2 = Math.round(this._p2.y * v);
            const left = Math.min(x1, x2);
            const right = Math.max(x1, x2);

            const options = this._options;
            const levels = options.levels && options.levels.length ? options.levels : defaultFibonacciLevels;
            const sorted = [...levels].sort((a, b) => a - b);

            if (options.fillBackground) {
                for (let i = 0; i < sorted.length - 1; i++) {
                    const top = Math.round(y1 + (y2 - y1) * sorted[i + 1]);
                    const bottom = Math.round(y1 + (y2 - y1) * sorted[i]);
                    ctx.fillStyle = options.backgroundColor;
                    ctx.fillRect(left, top, right - left, Math.max(bottom - top, 0));
                }
            }

            ctx.lineWidth = options.width;
            ctx.strokeStyle = options.lineColor;
            setLineStyle(ctx, options.lineStyle);
            ctx.font = `${Math.round(options.fontSize * v)}px sans-serif`;
            ctx.textBaseline = 'middle';
            ctx.textAlign = 'left';

            for (const ratio of sorted) {
                const y = Math.round(y1 + (y2 - y1) * ratio);
                ctx.beginPath();
                ctx.moveTo(left, y);
                ctx.lineTo(right, y);
                ctx.stroke();
                if (options.showLabels) {
                    const price = this._price1 + (this._price2 - this._price1) * ratio;
                    ctx.fillStyle = options.textColor;
                    ctx.fillText(`${(ratio * 100).toFixed(1)}%   ${price.toFixed(2)}`, left + 4 * h, y - 8 * v);
                }
            }

            // diagonal between the two anchors
            setLineStyle(ctx, options.lineStyle);
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.stroke();

            if (!this._hovered) return;
            this._drawEndCircle(scope, x1, y1);
            this._drawEndCircle(scope, x2, y2);
        });
    }
}
