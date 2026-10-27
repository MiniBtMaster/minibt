import { ParallelChannel } from './channel';
import { ChannelPaneRenderer } from './pane-renderer';
import { TwoPointDrawingPaneView } from '../drawing/pane-view';

export class ChannelPaneView extends TwoPointDrawingPaneView {
    declare _source: ParallelChannel;
    _offsetY = 0;

    constructor(source: ParallelChannel) {
        super(source);
    }

    update() {
        super.update();
        const series = this._source.series;
        const offset = this._source._options.channelOffset;
        if (!offset) {
            this._offsetY = 0;
            return;
        }
        const base = series.priceToCoordinate(this._source.p1!.price);
        const shifted = series.priceToCoordinate(this._source.p1!.price + offset);
        this._offsetY = (base === null || shifted === null) ? 0 : shifted - base;
    }

    renderer() {
        return new ChannelPaneRenderer(
            this._p1,
            this._p2,
            this._source._options,
            this._source.hovered,
            this._offsetY,
        );
    }
}
