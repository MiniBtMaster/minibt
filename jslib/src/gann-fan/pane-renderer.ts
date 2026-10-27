import { CanvasRenderingTarget2D } from 'fancy-canvas';
import { TwoPointDrawingPaneRenderer } from '../drawing/pane-renderer';
import { ViewPoint } from '../drawing/pane-view';
import { setLineStyle } from '../helpers/canvas-rendering';
import { defaultGannRatios, GannFanOptions, gannLabel } from './gann-fan';

export class GannFanPaneRenderer extends TwoPointDrawingPaneRenderer {
    declare _options: GannFanOptions;

    constructor(p1: ViewPoint, p2: ViewPoint, options: GannFanOptions, hovered: boolean) {
        super(p1, p2, options, hovered);
    }

    draw(target: CanvasRenderingTarget2D) {
        target.useBitmapCoordinateSpace(scope => {
            const scaled = this._getScaledCoordinates(scope);
            if (!scaled) return;
            const ctx = scope.context;
            const h = scope.horizontalPixelRatio;
            const v = scope.verticalPixelRatio;
            const { x1, y1, x2, y2 } = scaled;

            const dx = x2 - x1;
            const dy = y2 - y1;
            const extension = this._options.extension ?? 3;
            const ratios = this._options.ratios?.length ? this._options.ratios : defaultGannRatios;

            ctx.font = `${Math.round(this._options.fontSize * v)}px sans-serif`;
            ctx.textBaseline = 'middle';
            ctx.textAlign = 'left';

            for (const ratio of ratios) {
                const isOneToOne = Math.abs(ratio - 1) < 1e-9;
                ctx.lineWidth = isOneToOne ? this._options.width + 1 : this._options.width;
                ctx.strokeStyle = isOneToOne ? this._options.highlightColor : this._options.lineColor;
                setLineStyle(ctx, this._options.lineStyle);

                const endX = x1 + dx * extension;
                const endY = y1 + dy * ratio * extension;
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(endX, endY);
                ctx.stroke();

                if (this._options.showLabels) {
                    ctx.fillStyle = this._options.textColor;
                    ctx.fillText(gannLabel(ratio), endX + 4 * h, endY);
                }
            }

            if (!this._hovered) return;
            this._drawEndCircle(scope, x1, y1);
            this._drawEndCircle(scope, x2, y2);
        });
    }
}
