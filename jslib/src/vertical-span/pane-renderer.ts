import { Coordinate, IPrimitivePaneRenderer } from "lightweight-charts";
import { CanvasRenderingTarget2D } from "fancy-canvas";
import { VerticalSpanOptions } from "./vertical-span";
import { setLineStyle } from "../helpers/canvas-rendering";

export class VerticalSpanPaneRenderer implements IPrimitivePaneRenderer {
    _xs: (Coordinate | null)[];
    _options: VerticalSpanOptions;

    constructor(xs: (Coordinate | null)[], options: VerticalSpanOptions) {
        this._xs = xs;
        this._options = options;
    }

    draw(target: CanvasRenderingTarget2D) {
        target.useBitmapCoordinateSpace(scope => {
            const xs = this._xs
                .filter((x): x is Coordinate => x !== null)
                .map(x => Math.round(x * scope.horizontalPixelRatio));
            if (xs.length === 0) return;
            const ctx = scope.context;
            const height = scope.bitmapSize.height;
            ctx.lineWidth = Math.max(1, this._options.width * scope.horizontalPixelRatio);
            ctx.strokeStyle = this._options.lineColor;
            setLineStyle(ctx, this._options.lineStyle as any);

            if (this._options.filled && xs.length >= 2) {
                const x1 = Math.min(xs[0], xs[1]);
                const x2 = Math.max(xs[0], xs[1]);
                const previousAlpha = ctx.globalAlpha;
                if (this._options.opacity !== null && this._options.opacity !== undefined) {
                    ctx.globalAlpha = this._options.opacity;
                }
                ctx.fillStyle = this._options.fillColor;
                ctx.fillRect(x1, 0, Math.max(1, x2 - x1), height);
                ctx.globalAlpha = previousAlpha;
                ctx.beginPath();
                ctx.moveTo(x1, 0);
                ctx.lineTo(x1, height);
                ctx.moveTo(x2, 0);
                ctx.lineTo(x2, height);
                ctx.stroke();
                return;
            }

            ctx.beginPath();
            for (const x of xs) {
                ctx.moveTo(x, 0);
                ctx.lineTo(x, height);
            }
            ctx.stroke();
        });
    }
}
