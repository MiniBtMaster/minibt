import { FibonacciRetracement } from './fibonacci';
import { FibonacciPaneRenderer } from './pane-renderer';
import { TwoPointDrawingPaneView } from '../drawing/pane-view';

export class FibonacciPaneView extends TwoPointDrawingPaneView {
    declare _source: FibonacciRetracement;

    constructor(source: FibonacciRetracement) {
        super(source);
    }

    renderer() {
        return new FibonacciPaneRenderer(
            this._p1,
            this._p2,
            this._source._options,
            this._source.hovered,
            this._source.p1!.price,
            this._source.p2!.price,
        );
    }
}
