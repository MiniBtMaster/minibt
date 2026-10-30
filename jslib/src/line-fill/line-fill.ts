import { DeepPartial, ISeriesApi, SeriesOptionsMap } from "lightweight-charts";
import { PluginBase } from "../plugin-base";
import { lookup } from "../general/rpc";
import { LineFillPaneView } from "./pane-view";

export interface LineFillOptions {
    fillColor: string;
    /** optional stroke around the filled area (null / omitted → fill only) */
    lineColor: string | null;
    width: number;
    lineStyle: number;
    /** Alpha for the fill (0..1); null → use the colour's own alpha. */
    opacity: number | null;
}

export const defaultLineFillOptions: LineFillOptions = {
    fillColor: '#2962FF',
    lineColor: null,
    width: 1,
    lineStyle: 0,
    opacity: 0.15,
};

export interface FillPoint {
    x: number;
    y1: number;
    y2: number;
}

/**
 * Fills the area between two series lines (an indicator band: Bollinger,
 * Keltner, ...). Attach it to one of the two series; the other one is resolved
 * from its bridge handle.
 *
 * Both series have to share the pane's price scale, otherwise the two
 * `priceToCoordinate` calls describe different scales and the band is wrong.
 */
export class LineFill extends PluginBase {
    _type = 'LineFill';
    _options: LineFillOptions;
    _other: ISeriesApi<keyof SeriesOptionsMap>;
    private _paneViews: LineFillPaneView[];
    private _otherDataChanged?: () => void;

    constructor(
        other: string | ISeriesApi<keyof SeriesOptionsMap>,
        options: DeepPartial<LineFillOptions> = {}
    ) {
        super();
        this._other = (typeof other === 'string'
            ? lookup(other)
            : other) as ISeriesApi<keyof SeriesOptionsMap>;
        if (!this._other || typeof this._other.priceToCoordinate !== 'function') {
            throw new Error('pylightcharts: LineFill needs another series handle');
        }
        this._options = { ...defaultLineFillOptions, ...options } as LineFillOptions;
        this._paneViews = [new LineFillPaneView(this)];
    }

    public attached(param: Parameters<PluginBase['attached']>[0]) {
        super.attached(param);
        // a data change on the other line must repaint the band as well
        this._otherDataChanged = () => this.requestUpdate();
        this._other.subscribeDataChanged(this._otherDataChanged);
    }

    public detached() {
        if (this._otherDataChanged) {
            this._other.unsubscribeDataChanged(this._otherDataChanged);
            this._otherDataChanged = undefined;
        }
        super.detached();
    }

    updateAllViews() {
        this._paneViews.forEach(view => view.update());
    }

    paneViews() {
        return this._paneViews;
    }

    public applyOptions(options: DeepPartial<LineFillOptions>) {
        this._options = { ...this._options, ...options } as LineFillOptions;
        this.requestUpdate();
    }
}
