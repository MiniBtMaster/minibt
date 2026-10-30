import { Point } from '../drawing/data-source';
import { DrawingOptions } from '../drawing/options';
import { SimpleTwoPointDrawing } from '../drawing/simple-two-point';
import { PositionPaneView } from './pane-view';

export interface PositionOptions extends DrawingOptions {
    profitFillColor: string;
    lossFillColor: string;
    profitLineColor: string;
    lossLineColor: string;
    /** Stop-loss distance as a multiple of the entry->target distance. */
    riskRatio: number;
    showLabels: boolean;
    textColor: string;
    fontSize: number;
}

/**
 * Risk / reward position tool: `p1` is the entry, `p2` the target. The
 * stop-loss sits on the opposite side, `riskRatio` times the target distance.
 */
export class Position extends SimpleTwoPointDrawing {
    _type = 'Position';
    declare _options: PositionOptions;

    constructor(p1: Point, p2: Point, options?: Partial<PositionOptions>) {
        super(p1, p2, options);
        this._options = {
            ...this._options,
            profitFillColor: 'rgba(38, 166, 154, 0.25)',
            lossFillColor: 'rgba(239, 83, 80, 0.25)',
            profitLineColor: '#26A69A',
            lossLineColor: '#EF5350',
            riskRatio: 1,
            showLabels: true,
            textColor: '#FFFFFF',
            fontSize: 12,
            ...options,
        } as PositionOptions;
        this._paneViews = [new PositionPaneView(this)];
    }

    /** The stop-loss price implied by the current points and options. */
    get stopPrice(): number {
        const entry = this.p1?.price ?? 0;
        const target = this.p2?.price ?? 0;
        const direction = target >= entry ? 1 : -1;
        return entry - direction * Math.abs(target - entry) * this._options.riskRatio;
    }
}
