import { CanvasRenderingTarget2D } from 'fancy-canvas';
import { ThreePointDrawingPaneRenderer } from '../drawing/three-point-drawing';
import { ViewPoint } from '../drawing/pane-view';
import { setLineStyle } from '../helpers/canvas-rendering';
import { PitchforkOptions } from './pitchfork';

export class PitchforkPaneRenderer extends ThreePointDrawingPaneRenderer {
    declare _options: PitchforkOptions;

    constructor(p1: ViewPoint, p2: ViewPoint, p3: ViewPoint, options: PitchforkOptions, hovered: boolean) {
        super(p1, p2, p3, options, hovered);
    }

    draw(target: CanvasRenderingTarget2D) {
        target.useBitmapCoordinateSpace(scope => {
            const scaled = this._scaled(scope);
            if (!scaled) return;
            const ctx = scope.context;
            const { x1, y1, x2, y2, x3, y3 } = scaled;

            // median runs from p1 through the midpoint of p2/p3
            const midX = (x2 + x3) / 2;
            const midY = (y2 + y3) / 2;
            const dx = midX - x1;
            const dy = midY - y1;
            const t = this._options.extension ?? 4;

            const endX = x1 + dx * t;
            const endY = y1 + dy * t;

            if (this._options.fillEnabled) {
                ctx.fillStyle = this._options.fillColor;
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x1 + dx * t, y1 + dy * t);
                ctx.lineTo(x2 + dx * t, y2 + dy * t);
                ctx.lineTo(x2, y2);
                ctx.lineTo(x3, y3);
                ctx.lineTo(x3 + dx * t, y3 + dy * t);
                ctx.closePath();
                ctx.fill();
            }

            ctx.lineWidth = this._options.width;
            ctx.strokeStyle = this._options.lineColor;
            setLineStyle(ctx, this._options.lineStyle);

            const lines: Array<[number, number]> = [[x1, y1], [x2, y2], [x3, y3]];
            for (const [sx, sy] of lines) {
                ctx.beginPath();
                ctx.moveTo(sx, sy);
                ctx.lineTo(sx + dx * t, sy + dy * t);
                ctx.stroke();
            }

            // the base p2 -> p3
            ctx.setLineDash([]);
            ctx.beginPath();
            ctx.moveTo(x2, y2);
            ctx.lineTo(x3, y3);
            ctx.stroke();

            if (!this._hovered) return;
            this._drawEndCircle(scope, x1, y1);
            this._drawEndCircle(scope, x2, y2);
            this._drawEndCircle(scope, x3, y3);
            void endX;
            void endY;
        });
    }
}
