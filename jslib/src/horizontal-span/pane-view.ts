import { Coordinate, IPrimitivePaneView } from "lightweight-charts";
import { HorizontalSpan } from "./horizontal-span";
import { HorizontalSpanPaneRenderer } from "./pane-renderer";

export class HorizontalSpanPaneView implements IPrimitivePaneView {
    _source: HorizontalSpan;
    _ys: (Coordinate | null)[] = [];

    constructor(source: HorizontalSpan) {
        this._source = source;
    }

    update() {
        const series = this._source.series;
        this._ys = this._source._prices.map(price => series.priceToCoordinate(price));
    }

    renderer() {
        return new HorizontalSpanPaneRenderer(this._ys, this._source._options);
    }
}
