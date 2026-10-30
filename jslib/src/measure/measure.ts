import { Point } from '../drawing/data-source';
import { SimpleTwoPointDrawing } from '../drawing/simple-two-point';
import { MeasurePaneView } from './pane-view';
import { DrawingOptions } from '../drawing/options';

export interface MeasureOptions extends DrawingOptions {
    fillColor: string;
    textColor: string;
    backgroundColor: string;
    fontSize: number;
    showTimeRange: boolean;
}

export class Measure extends SimpleTwoPointDrawing {
    _type = 'Measure';
    declare _options: MeasureOptions;

    constructor(p1: Point, p2: Point, options?: Partial<MeasureOptions>) {
        super(p1, p2, options);
        this._options = {
            ...this._options,
            fillColor: 'rgba(41, 98, 255, 0.18)',
            textColor: '#FFFFFF',
            backgroundColor: 'rgba(41, 98, 255, 0.85)',
            fontSize: 12,
            showTimeRange: true,
            ...options,
        } as MeasureOptions;
        this._paneViews = [new MeasurePaneView(this)];
    }
}
