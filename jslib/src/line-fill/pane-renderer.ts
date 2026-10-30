import { IPrimitivePaneRenderer } from "lightweight-charts";
import { CanvasRenderingTarget2D } from "fancy-canvas";
import { FillPoint, LineFillOptions } from "./line-fill";
import { setLineStyle } from "../helpers/canvas-rendering";

/** A point is drawable only when both lines (and x) have a real value. */
function isValidPoint(point: FillPoint): boolean {
    return Number.isFinite(point.x) && Number.isFinite(point.y1) && Number.isFinite(point.y2);
}

/**
 * Fill one run of consecutive valid points: upper line left → right, lower line
 * right → left, then close the path.
 */
function fillSegment(
    ctx: CanvasRenderingContext2D,
    points: FillPoint[],
    h: number,
    v: number,
    stroke: boolean,
): void {
    ctx.beginPath();
    points.forEach((point, index) => {
        const x = point.x * h;
        const y = point.y1 * v;
        if (index === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });
    for (let index = points.length - 1; index >= 0; index--) {
        ctx.lineTo(points[index].x * h, points[index].y2 * v);
    }
    ctx.closePath();
    ctx.fill();
    if (stroke) {
        ctx.stroke();
    }
}

export class LineFillPaneRenderer implements IPrimitivePaneRenderer {
    _points: FillPoint[];
    _options: LineFillOptions;

    constructor(points: FillPoint[], options: LineFillOptions) {
        this._points = points;
        this._options = options;
    }

    draw(target: CanvasRenderingTarget2D) {
        if (this._points.length < 2) return;
        target.useBitmapCoordinateSpace(scope => {
            const h = scope.horizontalPixelRatio;
            const v = scope.verticalPixelRatio;
            const ctx = scope.context;

            const previousAlpha = ctx.globalAlpha;
            if (this._options.opacity !== null && this._options.opacity !== undefined) {
                ctx.globalAlpha = this._options.opacity;
            }
            ctx.fillStyle = this._options.fillColor;
            const stroke = Boolean(this._options.lineColor);
            if (stroke) {
                ctx.lineWidth = Math.max(1, this._options.width * v);
                ctx.strokeStyle = this._options.lineColor as string;
                setLineStyle(ctx, this._options.lineStyle as never);
            }

            // NaN 断开：只把**连续有效**的点连成一段（否则缺口处会把两条通道线
            // 直接连起来，色带变成一大块三角形）。
            let start = 0;
            while (start < this._points.length) {
                while (start < this._points.length && !isValidPoint(this._points[start])) {
                    start++;
                }
                let end = start;
                while (end < this._points.length && isValidPoint(this._points[end])) {
                    end++;
                }
                if (end - start >= 2) {
                    fillSegment(ctx, this._points.slice(start, end), h, v, stroke);
                }
                start = end;
            }
            ctx.globalAlpha = previousAlpha;
        });
    }
}
