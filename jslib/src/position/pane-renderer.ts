import { BitmapCoordinatesRenderingScope, CanvasRenderingTarget2D } from 'fancy-canvas';
import { TwoPointDrawingPaneRenderer } from '../drawing/pane-renderer';
import { ViewPoint } from '../drawing/pane-view';
import { PositionOptions } from './position';

export class PositionPaneRenderer extends TwoPointDrawingPaneRenderer {
    declare _options: PositionOptions;
    private readonly _entry: number;
    private readonly _target: number;
    private readonly _stop: number;
    private readonly _stopY: number | null;

    constructor(p1: ViewPoint, p2: ViewPoint, options: PositionOptions, hovered: boolean,
                entry: number, target: number, stop: number, stopY: number | null) {
        super(p1, p2, options, hovered);
        this._entry = entry;
        this._target = target;
        this._stop = stop;
        this._stopY = stopY;
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
            const x2 = Math.round(this._p2.x * h);
            const left = Math.min(x1, x2);
            const right = Math.max(x1, x2);
            const entryY = Math.round(this._p1.y * v);
            const targetY = Math.round(this._p2.y * v);
            const stopY = this._stopY === null ? null : Math.round(this._stopY * v);
            const width = Math.max(right - left, 2);

            // profit zone
            ctx.fillStyle = this._options.profitFillColor;
            ctx.fillRect(left, Math.min(entryY, targetY), width, Math.abs(targetY - entryY));
            // loss zone
            if (stopY !== null) {
                ctx.fillStyle = this._options.lossFillColor;
                ctx.fillRect(left, Math.min(entryY, stopY), width, Math.abs(stopY - entryY));
            }

            ctx.setLineDash([]);
            ctx.lineWidth = this._options.width;
            ctx.strokeStyle = this._options.lineColor;
            ctx.strokeRect(left, Math.min(entryY, targetY, stopY ?? entryY), width,
                Math.max(targetY, stopY ?? entryY) - Math.min(targetY, stopY ?? entryY));

            const lines: Array<[number, string, string]> = [
                [entryY, this._options.lineColor, `entry ${this._entry.toFixed(2)}`],
                [targetY, this._options.profitLineColor,
                    `target ${this._target.toFixed(2)}  ${this._percent(this._entry, this._target)}`],
            ];
            if (stopY !== null) {
                lines.push([stopY, this._options.lossLineColor,
                    `stop ${this._stop.toFixed(2)}  ${this._percent(this._entry, this._stop)}`]);
            }
            for (const [y, colour, label] of lines) {
                ctx.strokeStyle = colour;
                ctx.beginPath();
                ctx.moveTo(left, y);
                ctx.lineTo(right, y);
                ctx.stroke();
                if (this._options.showLabels) {
                    this._drawLabel(scope, label, right, y, colour);
                }
            }

            if (!this._hovered) return;
            this._drawEndCircle(scope, x1, entryY);
            this._drawEndCircle(scope, x2, targetY);
        });
    }

    private _percent(from: number, to: number): string {
        if (!from) return '';
        const value = (to / from - 1) * 100;
        return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
    }

    private _drawLabel(scope: BitmapCoordinatesRenderingScope, text: string, x: number, y: number,
                       background: string): void {
        const ctx = scope.context;
        const h = scope.horizontalPixelRatio;
        const v = scope.verticalPixelRatio;
        const fontSize = Math.round(this._options.fontSize * v);
        const padding = 4 * h;
        ctx.font = `${fontSize}px sans-serif`;
        ctx.textBaseline = 'middle';
        ctx.textAlign = 'left';
        const width = ctx.measureText(text).width;
        const boxHeight = fontSize + 6 * v;
        const boxX = x + 8 * h;
        const boxY = y - boxHeight / 2;

        ctx.fillStyle = background;
        ctx.fillRect(boxX - padding, boxY, width + padding * 2, boxHeight);
        ctx.fillStyle = this._options.textColor;
        ctx.fillText(text, boxX, y);
    }
}
