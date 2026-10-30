import { GannFan } from './gann-fan';
import { GannFanPaneRenderer } from './pane-renderer';
import { TwoPointDrawingPaneView } from '../drawing/pane-view';

export class GannFanPaneView extends TwoPointDrawingPaneView {
    declare _source: GannFan;

    constructor(source: GannFan) {
        super(source);
    }

    renderer() {
        return new GannFanPaneRenderer(
            this._p1,
            this._p2,
            this._source._options,
            this._source.hovered,
        );
    }
}
