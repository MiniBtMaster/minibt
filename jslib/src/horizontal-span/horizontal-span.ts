import { DeepPartial } from "lightweight-charts";
import { PluginBase } from "../plugin-base";
import { HorizontalSpanPaneView } from "./pane-view";

export interface HorizontalSpanOptions {
    fillColor: string;
    lineColor: string;
    width: number;
    lineStyle: number;
    /** true → fill between the two prices; false → one line per price. */
    filled: boolean;
    /** Let the prices take part in the pane's auto-scaling (off by default). */
    autoscale: boolean;
    /** Alpha for the fill (0..1); null → use the colour's own alpha. */
    opacity: number | null;
}

export const defaultHorizontalSpanOptions: HorizontalSpanOptions = {
    fillColor: '#7E57C2',
    lineColor: 'rgba(126, 87, 194, 0.90)',
    width: 1,
    lineStyle: 0,
    filled: true,
    autoscale: false,
    opacity: 0.2,
};

/** A price anchor: a plain number or `{price}` (like `VerticalSpan`'s points). */
export type PricePoint = number | { price: number } | null;

function toPrices(points: PricePoint[]): number[] {
    return (points || [])
        .map(point => (typeof point === 'number' ? point : point ? point.price : null))
        .filter((price): price is number => price !== null && price !== undefined && !Number.isNaN(price));
}

/**
 * A horizontal price band (support / resistance zone): fills the area between two
 * prices across the whole pane, or draws one full-width line per price.
 *
 * `series.attachPrimitive(new Lib.HorizontalSpan([{price: 98}, {price: 102}],
 * { fillColor: 'rgba(126, 87, 194, 0.2)' }))`
 */
export class HorizontalSpan extends PluginBase {
    _type = 'HorizontalSpan';
    _options: HorizontalSpanOptions;
    _prices: number[] = [];
    private _paneViews: HorizontalSpanPaneView[];

    constructor(prices: PricePoint[], options: DeepPartial<HorizontalSpanOptions> = {}) {
        super();
        this._options = { ...defaultHorizontalSpanOptions, ...options } as HorizontalSpanOptions;
        this._prices = toPrices(prices);
        this._paneViews = [new HorizontalSpanPaneView(this)];
    }

    updateAllViews() {
        this._paneViews.forEach(view => view.update());
    }

    paneViews() {
        return this._paneViews;
    }

    /** Optional autoscale so the band is never scrolled out of the visible range. */
    autoscaleInfo() {
        if (!this._options.autoscale || this._prices.length === 0) {
            return null;
        }
        return {
            priceRange: {
                minValue: Math.min(...this._prices),
                maxValue: Math.max(...this._prices),
            },
        };
    }

    public setPrices(prices: PricePoint[]) {
        this._prices = toPrices(prices);
        this.requestUpdate();
    }

    public applyOptions(options: DeepPartial<HorizontalSpanOptions>) {
        this._options = { ...this._options, ...options } as HorizontalSpanOptions;
        this.requestUpdate();
    }
}
