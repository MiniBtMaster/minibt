import { CanvasRenderingTarget2D } from 'fancy-canvas';
import { TwoPointDrawingPaneRenderer } from '../drawing/pane-renderer';
import { ViewPoint } from '../drawing/pane-view';
import { setLineStyle } from '../helpers/canvas-rendering';
import { ChannelOptions } from './channel';

export class ChannelPaneRenderer extends TwoPointDrawingPaneRenderer {
    declare _options: ChannelOptions;
    private readonly _offsetY: number;

    constructor(p1: ViewPoint, p2: ViewPoint, options: ChannelOptions, hovered: boolean, offsetY: number) {
        super(p1, p2, options, hovered);
        this._offsetY = offsetY;
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
            const offset = Math.round(this._offsetY * v);

            if (this._options.fillEnabled && offset !== 0) {
                ctx.fillStyle = this._options.fillColor;
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.lineTo(x2, y2 + offset);
                ctx.lineTo(x1, y1 + offset);
                ctx.closePath();
                ctx.fill();
            }

            ctx.lineWidth = this._options.width;
            ctx.strokeStyle = this._options.lineColor;
            setLineStyle(ctx, this._options.lineStyle);
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.moveTo(x1, y1 + offset);
            ctx.lineTo(x2, y2 + offset);
            ctx.stroke();

            // dashed guide at the second anchor
            ctx.setLineDash([4 * h, 4 * h]);
            ctx.beginPath();
            ctx.moveTo(x2, y2);
            ctx.lineTo(x2, y2 + offset);
            ctx.stroke();

            if (!this._hovered) return;
            this._drawEndCircle(scope, x1, y1);
            this._drawEndCircle(scope, x2, y2);
            this._drawEndCircle(scope, x1, y1 + offset);
            this._drawEndCircle(scope, x2, y2 + offset);
        });
    }
}
