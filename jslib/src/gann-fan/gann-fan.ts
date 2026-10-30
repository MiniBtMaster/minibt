import { Point } from '../drawing/data-source';
import { DrawingOptions } from '../drawing/options';
import { SimpleTwoPointDrawing } from '../drawing/simple-two-point';
import { GannFanPaneView } from './pane-view';

export interface GannFanOptions extends DrawingOptions {
    /** slope multipliers relative to the 1x1 line (p1 -> p2) */
    ratios: number[];
    /** how far the fan runs, as multiples of the p1 -> p2 span */
    extension: number;
    highlightColor: string;
    showLabels: boolean;
    textColor: string;
    fontSize: number;
}

export const defaultGannRatios: number[] = [1 / 8, 1 / 4, 1 / 3, 1 / 2, 1, 2, 3, 4, 8];

/** Gann fan: the p1 -> p2 line is the 1x1, plus steeper / shallower rays. */
export class GannFan extends SimpleTwoPointDrawing {
    _type = 'GannFan';
    declare _options: GannFanOptions;

    constructor(p1: Point, p2: Point, options?: Partial<GannFanOptions>) {
        super(p1, p2, options);
        this._options = {
            ...this._options,
            ratios: defaultGannRatios,
            extension: 3,
            highlightColor: '#FF9800',
            showLabels: false,
            textColor: '#9598A1',
            fontSize: 10,
            ...options,
        } as GannFanOptions;
        this._paneViews = [new GannFanPaneView(this)];
    }
}

/** '1x1', '2x1', '1x2', ... for a slope multiplier. */
export function gannLabel(ratio: number): string {
    if (Math.abs(ratio - 1) < 1e-9) return '1x1';
    if (ratio > 1) return `${Number(ratio.toFixed(3))}x1`;
    return `1x${Math.round(1 / ratio)}`;
}
