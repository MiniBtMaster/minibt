import { Point } from '../drawing/data-source';
import { DrawingOptions } from '../drawing/options';
import { ThreePointDrawing } from '../drawing/three-point-drawing';
import { PitchforkPaneView } from './pane-view';

export interface PitchforkOptions extends DrawingOptions {
    /** shade the area between the upper and lower parallels */
    fillEnabled: boolean;
    fillColor: string;
    /** how far the three lines run past the third point (multiples of A->M) */
    extension: number;
}

/**
 * Andrew's pitchfork: a median line from `p1` through the midpoint of `p2`/`p3`,
 * plus two parallels through `p2` and `p3`.
 */
export class AndrewsPitchfork extends ThreePointDrawing {
    _type = 'AndrewsPitchfork';
    declare _options: PitchforkOptions;

    constructor(p1: Point, p2: Point, p3: Point, options?: Partial<PitchforkOptions>) {
        super(p1, p2, p3, options);
        this._options = {
            ...this._options,
            fillEnabled: true,
            fillColor: 'rgba(41, 98, 255, 0.08)',
            extension: 4,
            ...options,
        } as PitchforkOptions;
        this._paneViews = [new PitchforkPaneView(this)];
    }
}
