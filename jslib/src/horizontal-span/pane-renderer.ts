import { Coordinate, IPrimitivePaneRenderer } from "lightweight-charts";
import { CanvasRenderingTarget2D } from "fancy-canvas";
import { HorizontalSpanOptions } from "./horizontal-span";
import { setLineStyle } from "../helpers/canvas-rendering";

export class HorizontalSpanPaneRenderer implements IPrimitivePaneRenderer {
    _ys: (Coordinate | null)[];
    _options: HorizontalSpanOptions;

    constructor(ys: (Coordinate | null)[], options: HorizontalSpanOptions) {
        this._ys = ys;
        this._options = options;
    }

    draw(target: CanvasRenderingTarget2D) {
        target.useBitmapCoordinateSpace(scope => {
            const ys = this._ys
                .filter((y): y is Coordinate => y !== null && y !== undefined)
                .map(y => Math.round(y * scope.verticalPixelRatio));
            if (ys.length === 0) return;
            const ctx = scope.context;
            const width = scope.bitmapSize.width;
            ctx.lineWidth = Math.max(1, this._options.width * scope.verticalPixelRatio);
            ctx.strokeStyle = this._options.lineColor;
            setLineStyle(ctx, this._options.lineStyle as any);

            if (this._options.filled && ys.length >= 2) {
                // a band always spans the outermost prices (a list may hold more
                // than two)
                const y1 = Math.min(...ys);
                const y2 = Math.max(...ys);
                const previousAlpha = ctx.globalAlpha;
                if (this._options.opacity !== null && this._options.opacity !== undefined) {
                    ctx.globalAlpha = this._options.opacity;
                }
                ctx.fillStyle = this._options.fillColor;
                ctx.fillRect(0, y1, width, Math.max(1, y2 - y1));
                ctx.globalAlpha = previousAlpha;
                ctx.beginPath();
                ctx.moveTo(0, y1);
                ctx.lineTo(width, y1);
                ctx.moveTo(0, y2);
                ctx.lineTo(width, y2);
                ctx.stroke();
                return;
            }

            ctx.beginPath();
            for (const y of ys) {
                ctx.moveTo(0, y);
                ctx.lineTo(width, y);
            }
            ctx.stroke();
        });
    }
}
