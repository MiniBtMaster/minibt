import { Position } from './position';
import { PositionPaneRenderer } from './pane-renderer';
import { TwoPointDrawingPaneView } from '../drawing/pane-view';

export class PositionPaneView extends TwoPointDrawingPaneView {
    declare _source: Position;
    _stopY: number | null = null;

    constructor(source: Position) {
        super(source);
    }

    update() {
        super.update();
        const converted = this._source.series.priceToCoordinate(this._source.stopPrice);
        this._stopY = converted === null ? null : (converted as number);
    }

    renderer() {
        return new PositionPaneRenderer(
            this._p1,
            this._p2,
            this._source._options,
            this._source.hovered,
            this._source.p1!.price,
            this._source.p2!.price,
            this._source.stopPrice,
            this._stopY,
        );
    }
}
