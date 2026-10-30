import { BitmapCoordinatesRenderingScope, CanvasRenderingTarget2D } from "fancy-canvas";
import { DrawingOptions } from "../drawing/options";
import { DrawingPaneRenderer } from "../drawing/pane-renderer";
import { ViewPoint } from "../drawing/pane-view";
import { setLineStyle } from "../helpers/canvas-rendering";

export class HorizontalLinePaneRenderer extends DrawingPaneRenderer {
    _point: ViewPoint = {x: null, y: null};

    constructor(point: ViewPoint, options: DrawingOptions) {
        super(options);
        this._point = point;
    }

    draw(target: CanvasRenderingTarget2D) {
        target.useBitmapCoordinateSpace(scope => {
            if (this._point.y == null) return;
            const ctx = scope.context;

            const scaledY = Math.round(this._point.y * scope.verticalPixelRatio);
            const scaledX = this._point.x ? this._point.x * scope.horizontalPixelRatio : 0;

            ctx.lineWidth = this._options.width;
            ctx.strokeStyle = this._options.lineColor;
            setLineStyle(ctx, this._options.lineStyle);
            ctx.beginPath();

            ctx.moveTo(scaledX, scaledY);
            ctx.lineTo(scope.bitmapSize.width, scaledY);

            ctx.stroke();

            this._drawInPaneLabel(scope, scaledY);
        });
    }

    /**
     * Draw the optional `text` **inside** the pane, pinned to the left edge of the
     * visible range (canvas x = 0 is the pane's left border). This mirrors the
     * price-axis badge, but keeps the label over the chart instead of on the axis.
     */
    private _drawInPaneLabel(scope: BitmapCoordinatesRenderingScope, scaledY: number) {
        const text = this._options.text;
        if (!this._options.labelVisible || !text) return;

        const ctx = scope.context;
        const h = scope.horizontalPixelRatio;
        const v = scope.verticalPixelRatio;
        const fontSize = Math.round(12 * v);
        ctx.font = this._options.labelFont || `${fontSize}px sans-serif`;
        ctx.textBaseline = 'middle';
        ctx.textAlign = 'left';

        const paddingX = 6 * h;
        const paddingY = 3 * v;
        const textWidth = ctx.measureText(text).width;
        const boxHeight = fontSize + paddingY * 2;
        const boxX = 0;                              // pane 左沿 = 图表可视范围左边
        const boxY = scaledY - boxHeight / 2;

        ctx.fillStyle = this._options.labelBackgroundColor || this._options.lineColor;
        ctx.fillRect(boxX, boxY, textWidth + paddingX * 2, boxHeight);
        ctx.fillStyle = this._options.labelTextColor || 'white';
        ctx.fillText(text, boxX + paddingX, scaledY);
    }
}
