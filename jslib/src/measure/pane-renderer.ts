import { CanvasRenderingTarget2D, BitmapCoordinatesRenderingScope } from 'fancy-canvas';
import { TwoPointDrawingPaneRenderer } from '../drawing/pane-renderer';
import { ViewPoint } from '../drawing/pane-view';
import { MeasureOptions } from './measure';

export class MeasurePaneRenderer extends TwoPointDrawingPaneRenderer {
    declare _options: MeasureOptions;
    private readonly _price1: number;
    private readonly _price2: number;
    private readonly _logical1: number;
    private readonly _logical2: number;

    constructor(p1: ViewPoint, p2: ViewPoint, options: MeasureOptions, hovered: boolean,
                price1: number, price2: number, logical1: number, logical2: number) {
        super(p1, p2, options, hovered);
        this._price1 = price1;
        this._price2 = price2;
        this._logical1 = logical1;
        this._logical2 = logical2;
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
            const top = Math.min(y1, y2);
            const bottom = Math.max(y1, y2);

            ctx.fillStyle = this._options.fillColor;
            ctx.fillRect(left, top, right - left, bottom - top);

            ctx.setLineDash([]);
            ctx.lineWidth = this._options.width;
            ctx.strokeStyle = this._options.lineColor;
            ctx.strokeRect(left, top, right - left, bottom - top);

            // horizontal guides at both anchors
            ctx.beginPath();
            ctx.moveTo(left, y1);
            ctx.lineTo(right, y1);
            ctx.moveTo(left, y2);
            ctx.lineTo(right, y2);
            ctx.stroke();

            const delta = this._price2 - this._price1;
            const percent = this._price1 !== 0 ? (delta / this._price1) * 100 : 0;
            const bars = Math.round(Math.abs(this._logical2 - this._logical1)) + 1;
            const sign = delta >= 0 ? '+' : '';
            const label = `${sign}${delta.toFixed(2)}  ${sign}${percent.toFixed(2)}%`;
            const timeLabel = this._options.showTimeRange ? `${bars} bars` : '';

            this._drawLabel(scope, label, x2, y2, true);
            if (timeLabel) {
                this._drawLabel(scope, timeLabel, x2, Math.round((y1 + y2) / 2), false);
            }

            if (!this._hovered) return;
            this._drawEndCircle(scope, x1, y1);
            this._drawEndCircle(scope, x2, y2);
        });
    }

    private _drawLabel(scope: BitmapCoordinatesRenderingScope, text: string, x: number, y: number, above: boolean) {
        const ctx = scope.context;
        const h = scope.horizontalPixelRatio;
        const v = scope.verticalPixelRatio;
        const padding = 4 * h;
        const fontSize = Math.round(this._options.fontSize * v);
        ctx.font = `${fontSize}px sans-serif`;
        ctx.textBaseline = 'middle';
        ctx.textAlign = 'left';
        const width = ctx.measureText(text).width;
        const boxHeight = fontSize + 6 * v;
        const boxY = above ? y - boxHeight - 2 * v : y + 2 * v;

        ctx.fillStyle = this._options.backgroundColor;
        ctx.fillRect(x + 6 * h - padding, boxY, width + padding * 2, boxHeight);
        ctx.fillStyle = this._options.textColor;
        ctx.fillText(text, x + 6 * h, boxY + boxHeight / 2);
    }
}
