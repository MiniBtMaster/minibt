import { DeepPartial } from "lightweight-charts";
import { Point } from "../drawing/data-source";
import { PluginBase } from "../plugin-base";
import { VerticalSpanPaneView } from "./pane-view";

export interface VerticalSpanOptions {
    fillColor: string;
    lineColor: string;
    width: number;
    lineStyle: number;
    /** true → 在两点之间填充；false → 在每个点画一条竖线。 */
    filled: boolean;
    /** 填充的透明度（0..1）；null → 用颜色自带的 alpha。 */
    opacity: number | null;
}

export const defaultVerticalSpanOptions: VerticalSpanOptions = {
    fillColor: 'rgba(252, 219, 3, 0.2)',
    lineColor: 'rgba(252, 219, 3, 0.9)',
    width: 1,
    lineStyle: 0,
    filled: true,
    opacity: null,
};

/**
 * v5 replacement for the removed histogram-based vertical span.
 *
 * Draws either a shaded band between two times (`filled: true`) or one vertical
 * line per anchor (`filled: false`). Attach it with
 * `series.attachPrimitive(new Lib.VerticalSpan(points, options))`.
 */
export class VerticalSpan extends PluginBase {
    _type = 'VerticalSpan';
    _options: VerticalSpanOptions;
    _points: Point[] = [];
    private _paneViews: VerticalSpanPaneView[];

    constructor(points: (Point | null)[], options: DeepPartial<VerticalSpanOptions> = {}) {
        super();
        this._options = { ...defaultVerticalSpanOptions, ...options } as VerticalSpanOptions;
        this._points = points.filter((p): p is Point => !!p);
        this._paneViews = [new VerticalSpanPaneView(this)];
    }

    updateAllViews() {
        this._paneViews.forEach(v => v.update());
    }

    paneViews() {
        return this._paneViews;
    }

    public setPoints(points: (Point | null)[]) {
        this._points = points.filter((p): p is Point => !!p);
        this.requestUpdate();
    }

    public applyOptions(options: DeepPartial<VerticalSpanOptions>) {
        this._options = { ...this._options, ...options } as VerticalSpanOptions;
        this.requestUpdate();
    }
}
