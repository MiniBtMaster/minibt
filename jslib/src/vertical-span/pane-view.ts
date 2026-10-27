import { Coordinate, IPrimitivePaneView } from "lightweight-charts";
import { VerticalSpan } from "./vertical-span";
import { VerticalSpanPaneRenderer } from "./pane-renderer";

export class VerticalSpanPaneView implements IPrimitivePaneView {
    _source: VerticalSpan;
    _xs: (Coordinate | null)[] = [];

    constructor(source: VerticalSpan) {
        this._source = source;
    }

    update() {
        const timeScale = this._source.chart.timeScale();
        this._xs = this._source._points.map(p => (
            p.time ? timeScale.timeToCoordinate(p.time) : timeScale.logicalToCoordinate(p.logical)
        ));
    }

    renderer() {
        return new VerticalSpanPaneRenderer(this._xs, this._source._options);
    }
}
