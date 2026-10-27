import { CanvasRenderingTarget2D } from 'fancy-canvas';
import { ThreePointDrawingPaneRenderer } from '../drawing/three-point-drawing';
import { ViewPoint } from '../drawing/pane-view';
import { setLineStyle } from '../helpers/canvas-rendering';
import { FibonacciExtensionOptions } from './fibonacci-extension';
import { ExtensionLevel } from './pane-view';

export class FibonacciExtensionPaneRenderer extends ThreePointDrawingPaneRenderer {
    declare _options: FibonacciExtensionOptions;
    private readonly _levels: ExtensionLevel[];

    constructor(p1: ViewPoint, p2: ViewPoint, p3: ViewPoint, options: FibonacciExtensionOptions,
                hovered: boolean, levels: ExtensionLevel[]) {
        super(p1, p2, p3, options, hovered);
        this._levels = levels;
    }

    draw(target: CanvasRenderingTarget2D) {
        target.useBitmapCoordinateSpace(scope => {
            const scaled = this._scaled(scope);
            if (!scaled) return;
            const ctx = scope.context;
            const h = scope.horizontalPixelRatio;
            const v = scope.verticalPixelRatio;
            const { x1, y1, x2, y2, x3, y3 } = scaled;

            const span = Math.max(x1, x2, x3) - Math.min(x1, x2, x3);
            const left = Math.min(x1, x2, x3);
            const right = Math.max(x1, x2, x3) + span * (this._options.extension ?? 0.5);

            ctx.lineWidth = this._options.width;
            ctx.strokeStyle = this._options.lineColor;
            setLineStyle(ctx, this._options.lineStyle);
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.lineTo(x3, y3);
            ctx.stroke();

            ctx.font = `${Math.round(this._options.fontSize * v)}px sans-serif`;
            ctx.textBaseline = 'middle';
            ctx.textAlign = 'left';

            for (const level of this._levels) {
                const y = level.ratio === 0 ? y3 : (level.y === null ? null : level.y * v);
                if (y === null) continue;
                ctx.beginPath();
                ctx.moveTo(left, y);
                ctx.lineTo(right, y);
                ctx.stroke();
                if (this._options.showLabels) {
                    ctx.fillStyle = this._options.textColor;
                    ctx.fillText(`${(level.ratio * 100).toFixed(1)}%   ${level.price.toFixed(2)}`,
                        left + 4 * h, y - 8 * v);
                }
            }

            if (!this._hovered) return;
            this._drawEndCircle(scope, x1, y1);
            this._drawEndCircle(scope, x2, y2);
            this._drawEndCircle(scope, x3, y3);
        });
    }
}
