import { Measure } from './measure';
import { MeasurePaneRenderer } from './pane-renderer';
import { TwoPointDrawingPaneView } from '../drawing/pane-view';

export class MeasurePaneView extends TwoPointDrawingPaneView {
    declare _source: Measure;

    constructor(source: Measure) {
        super(source);
    }

    renderer() {
        return new MeasurePaneRenderer(
            this._p1,
            this._p2,
            this._source._options,
            this._source.hovered,
            this._source.p1!.price,
            this._source.p2!.price,
            this._source.p1!.logical as number,
            this._source.p2!.logical as number,
        );
    }
}
