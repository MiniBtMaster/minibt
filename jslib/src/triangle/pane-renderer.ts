import { CanvasRenderingTarget2D } from 'fancy-canvas';
import { ThreePointDrawingPaneRenderer } from '../drawing/three-point-drawing';
import { ViewPoint } from '../drawing/pane-view';
import { setLineStyle } from '../helpers/canvas-rendering';
import { TriangleOptions } from './triangle';

export class TrianglePaneRenderer extends ThreePointDrawingPaneRenderer {
    declare _options: TriangleOptions;

    constructor(p1: ViewPoint, p2: ViewPoint, p3: ViewPoint, options: TriangleOptions, hovered: boolean) {
        super(p1, p2, p3, options, hovered);
    }

    draw(target: CanvasRenderingTarget2D) {
        target.useBitmapCoordinateSpace(scope => {
            const scaled = this._scaled(scope);
            if (!scaled) return;
            const ctx = scope.context;
            const { x1, y1, x2, y2, x3, y3 } = scaled;

            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.lineTo(x3, y3);
            ctx.closePath();

            if (this._options.fillEnabled) {
                ctx.fillStyle = this._options.fillColor;
                ctx.fill();
            }
            ctx.lineWidth = this._options.width;
            ctx.strokeStyle = this._options.lineColor;
            setLineStyle(ctx, this._options.lineStyle);
            ctx.stroke();

            if (!this._hovered) return;
            this._drawEndCircle(scope, x1, y1);
            this._drawEndCircle(scope, x2, y2);
            this._drawEndCircle(scope, x3, y3);
        });
    }
}
