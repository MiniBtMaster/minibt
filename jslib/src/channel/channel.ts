import { Point } from '../drawing/data-source';
import { DrawingOptions } from '../drawing/options';
import { SimpleTwoPointDrawing } from '../drawing/simple-two-point';
import { ChannelPaneView } from './pane-view';

export interface ChannelOptions extends DrawingOptions {
    /** Vertical price offset between the main line and the parallel line. */
    channelOffset: number;
    fillColor: string;
    fillEnabled: boolean;
}

export class ParallelChannel extends SimpleTwoPointDrawing {
    _type = 'ParallelChannel';
    declare _options: ChannelOptions;

    constructor(p1: Point, p2: Point, options?: Partial<ChannelOptions>) {
        super(p1, p2, options);
        this._options = {
            ...this._options,
            channelOffset: 0,
            fillColor: 'rgba(41, 98, 255, 0.12)',
            fillEnabled: true,
            ...options,
        } as ChannelOptions;
        this._paneViews = [new ChannelPaneView(this)];
    }
}
