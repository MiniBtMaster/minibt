import {
    AreaSeries,
    BarSeries,
    BaselineSeries,
    CandlestickSeries,
    ColorType,
    CrosshairMode,
    DeepPartial,
    HistogramSeries,
    HistogramStyleOptions,
    IChartApi,
    IPriceScaleApi,
    ISeriesApi,
    ISeriesMarkersPluginApi,
    ITextWatermarkPluginApi,
    ITimeScaleApi,
    LineSeries,
    LineStyleOptions,
    LogicalRange,
    LogicalRangeChangeEventHandler,
    MouseEventHandler,
    MouseEventParams,
    SeriesDefinition,
    SeriesMarker,
    SeriesOptionsCommon,
    SeriesType,
    TextWatermarkOptions,
    Time,
    createChart,
    createChartEx,
    createImageWatermark,
    createOptionsChart,
    createSeriesMarkers,
    createTextWatermark,
    createUpDownMarkers,
    createYieldCurveChart
} from "lightweight-charts";

import { register } from "./rpc";
import { resolveFormatter } from "./formatters";
import { lookupHorzScaleBehavior } from "./horz-scale";
import { CustomSeriesPaneView, SpecCustomSeriesPaneView } from "../custom-series/custom-series";
import { GlobalParams, globalParamInit } from "./global-params";
import { Legend } from "./legend";
import { Tooltip, TooltipOptions } from "./tooltip";
import { ToolBox } from "./toolbox";
import { TopBar } from "./topbar";


export interface Scale{
    width: number,
    height: number,
}


globalParamInit();
declare const window: GlobalParams;

export class Handler {
    public id: string;
    public commandFunctions: Function[] = [];

    public wrapper: HTMLDivElement;
    public div: HTMLDivElement;

    public chart: IChartApi;
    public timeScale: ITimeScaleApi<Time>;
    public rightPriceScale: IPriceScaleApi;
    public scale: Scale;
    public precision: number = 2;

    public series!: ISeriesApi<SeriesType>;
    public volumeSeries!: ISeriesApi<SeriesType>;

    public legend: Legend | undefined;
    private _topBar: TopBar | undefined;
    public toolBox: ToolBox | undefined;
    public spinner: HTMLDivElement | undefined;

    public _seriesList: ISeriesApi<SeriesType>[] = [];

    /** Arrow-key navigation; python `Chart(keyboard=False)` clears it. */
    public keyboardNavigation: boolean = true;

    /** Fraction of the visible window one key press moves / zooms (0.1 = 10%);
     *  python `Chart(keyboard_step=...)` sets it. */
    public keyboardStep: number = 0.1;

    /** every chart of the page, so a page-level top bar can re-lay them out */
    private static _instances: Handler[] = [];

    /** Draw the TradingView attribution logo. Set at construction: LWC only reads
     *  the option while creating a chart. */
    private readonly _attributionLogo: boolean;

    // The chart keeps a single slot per event, but several features want it at once:
    // the legend, the drawing toolbox and the host application's own cursor handler.
    // Whoever subscribed last used to win, so a host that re-subscribed after adding
    // an indicator silently killed the drawing tool (clicks and mouse moves stopped
    // reaching it). The handler now owns the slots and fans out to every listener.
    private _clickListeners: MouseEventHandler<Time>[] = [];
    private _crosshairListeners: MouseEventHandler<Time>[] = [];
    private _dblClickListeners: MouseEventHandler<Time>[] = [];

    private _dispatchClick = (param: MouseEventParams<Time>) => {
        for (const listener of [...this._clickListeners]) listener(param)
    };

    private _dispatchCrosshair = (param: MouseEventParams<Time>) => {
        for (const listener of [...this._crosshairListeners]) listener(param)
    };

    private _dispatchDblClick = (param: MouseEventParams<Time>) => {
        for (const listener of [...this._dblClickListeners]) listener(param)
    };

    /** 'time' (default), 'yield-curve' or 'options'. */
    public readonly _kind: string;

    /** Float direction of the row/column layout, as passed to the constructor
     *  (`create_subchart(position=...)`). Restored when a 2D tile layout ends. */
    public readonly floatPosition: string;

    /** When set, the chart is placed **absolutely** as a 2D tile: ``[x, y, w, h]``
     *  in 0..1 fractions (see :func:`setLayoutTiles`). ``null`` = normal float
     *  layout. ``reSize`` applies it, so a window resize moves the tiles too. */
    public tile: number[] | null = null;

    // v5: markers moved from ISeriesApi to a dedicated primitive.
    private static readonly _markerPrimitives = new WeakMap<object, ISeriesMarkersPluginApi<Time>>();
    private _watermark: ITextWatermarkPluginApi<Time> | undefined;

    // TODO find a better solution rather than the 'position' parameter
    constructor(
        chartId: string,
        innerWidth: number,
        innerHeight: number,
        position: string,
        autoSize: boolean,
        kind: string = 'time',
        attributionLogo: boolean = false
    ) {
        this.reSize = this.reSize.bind(this)
        // creation-time only: Lightweight Charts reads `layout.attributionLogo`
        // when the chart is built and never re-renders it on applyOptions
        this._attributionLogo = attributionLogo

        this.id = chartId
        this._kind = kind
        this.floatPosition = position
        Handler._instances.push(this)
        this.scale = {
            width: innerWidth,
            height: innerHeight,
        }

        this.wrapper = document.createElement('div')
        this.wrapper.classList.add("handler");
        this.wrapper.style.float = position

        this.div = document.createElement('div')
        this.div.style.position = 'relative'

        this.wrapper.appendChild(this.div);
        window.containerDiv.append(this.wrapper)

        // every chart gets a (hidden) spinner: `chart.spinner(...)` used to fail
        // with "Cannot read properties of undefined" because the element was only
        // created for polygon charts (see Events.search)
        Handler.makeSpinner(this)
        
        this.chart = this._createChart(kind);
        this.timeScale = this.chart.timeScale();
        this.rightPriceScale = this.chart.priceScale('right');
        this.chart.subscribeClick(this._dispatchClick);
        this.chart.subscribeCrosshairMove(this._dispatchCrosshair);
        this.chart.subscribeDblClick(this._dispatchDblClick);

        // numeric-horizontal-axis charts (yield curve / options) have no
        // candlestick or volume series, and no legend
        if (kind === 'time') {
            this.series = this.createCandlestickSeries();
            this.volumeSeries = this.createVolumeSeries();
            this.legend = new Legend(this);
        }

        document.addEventListener('keydown', (event) => {
            // `hotkey()` handlers are unshifted, so a user binding always wins
            // over the built-in arrow-key navigation below
            for (let i = 0; i < this.commandFunctions.length; i++) {
                if (this.commandFunctions[i](event)) return
            }
            this._handleArrowKey(event)
        })
        // The first chart of the page keeps the keyboard focus (arrow keys, the
        // toolbox, the in-chart search) until the pointer moves over another one.
        // A subchart created later used to steal it, so the arrows suddenly drove
        // a small floating chart instead of the main one.
        if (!window.handlerInFocus) {
            window.handlerInFocus = this.id;
        }
        this.wrapper.addEventListener('mouseover', () => window.handlerInFocus = this.id)

        this.reSize()
        if (!autoSize) return
        window.addEventListener('resize', () => this.reSize())
        // the legend is anchored to the pane, see `Legend.updatePosition`
    }


    /** Arrow keys pan/zoom the chart under the pointer (pylightcharts
     *  extension, on by default - `Chart(keyboard=False)` turns it off).
     *
     *  - Left/Right move the *visible window* by `keyboardStep` of its width
     *    (default 10%), so 100..200 becomes ~90..190 for ArrowLeft;
     *  - Up/Down zoom by the same fraction around the middle of the window.
     *    Zooming *out* (Down) never grows to the right once the newest bar is
     *    on screen: the extra width goes to the older side instead, so the live
     *    edge stays where it was (`_rightmostBarX`);
     *  - Shift = a near-full page (90%) / 2.5x zoom step;
     *  - Ctrl (or PageUp / PageDown) = a full page;
     *  - Home = the first bar, End = the latest one, Ctrl+0 = fit the series.
     *
     *  Held keys repeat, because the browser fires `keydown` continuously. The
     *  handler runs only after every `hotkey()` handler had its chance, only for
     *  the focused chart, and never while the user is typing (topbar textbox,
     *  chart search box). */
    private _handleArrowKey(event: KeyboardEvent) {
        if (!this.keyboardNavigation) return;
        const key = event.key;
        const reset = key === '0' && (event.ctrlKey || event.metaKey);
        const pan = key === 'ArrowLeft' || key === 'ArrowRight';
        const zoom = key === 'ArrowUp' || key === 'ArrowDown';
        const page = key === 'PageUp' || key === 'PageDown'
            || ((key === 'ArrowLeft' || key === 'ArrowRight')
                && (event.ctrlKey || event.metaKey));
        const home = key === 'Home';
        const end = key === 'End';
        if (!reset && !pan && !zoom && !page && !home && !end) return;
        if (window.handlerInFocus !== this.id || window.textBoxFocused) return;
        const active = document.activeElement as HTMLElement | null;
        const tag = active ? active.tagName : '';
        if (tag === 'INPUT' || tag === 'TEXTAREA' || (active && active.isContentEditable)) {
            return;
        }

        const timeScale = this.chart.timeScale();
        if (reset) {
            timeScale.fitContent();
            event.preventDefault();
            return;
        }
        const range = timeScale.getVisibleLogicalRange();
        if (!range) return;
        const visible = range.to - range.from;
        const step = this.keyboardStep > 0 ? this.keyboardStep : 0.1;

        if (end) {
            timeScale.scrollToRealTime();
        } else if (home) {
            // keep the width, put the first bar at the left edge
            timeScale.setVisibleLogicalRange({ from: 0, to: visible });
        } else if (pan || page) {
            // move the window itself: left = older bars, right = newer ones
            const fraction = page ? 1 : (event.shiftKey ? 0.9 : step);
            const move = Math.max(1, Math.round(visible * fraction));
            const back = key === 'ArrowLeft' || page && key === 'PageUp';
            const delta = back ? -move : move;
            timeScale.setVisibleLogicalRange({
                from: range.from + delta,
                to: range.to + delta,
            });
        } else {
            // zoom by moving the logical range, not by `applyOptions({barSpacing})`:
            // the engine reports `maxBarSpacing = 0` when it is unlimited, and in
            // that state applyOptions clamps the spacing away (it looks like a
            // no-op). The width / minBarSpacing pair bounds how far we can go out.
            const options = timeScale.options();
            const minSpacing = options.minBarSpacing > 0
                ? options.minBarSpacing : 0.5;
            const width = typeof timeScale.width === 'function'
                ? timeScale.width() : this.div.clientWidth;
            const factor = event.shiftKey ? 1 + step * 2.5 : 1 + step;
            const wanted = key === 'ArrowUp' ? visible / factor : visible * factor;
            const bars = Math.min(Math.max(wanted, 10), width / minSpacing);
            // zoom around the *middle* of the window: zooming in moves the left
            // edge right and the right edge left (like the mouse wheel), instead
            // of only pulling one edge inwards
            const centre = (range.from + range.to) / 2;
            let from = centre - bars / 2;
            let to = centre + bars / 2;
            if (key !== 'ArrowUp') {
                // the newest bar is already inside the window: do not stretch
                // past it, grow towards the older bars only
                const newest = this._rightmostBarX();
                if (newest !== null && newest >= 0 && newest <= width) {
                    to = range.to;
                    from = range.to - bars;
                }
            }
            timeScale.setVisibleLogicalRange({ from, to });
        }
        event.preventDefault();
    }

    /**
     * The x coordinate of the newest bar of any series, or null when empty.
     *
     * `dataByIndex(MAX, NearestLeft)` returns the last point without copying the
     * series' data, and `timeToCoordinate` maps it into the pane - so this is
     * "is the live edge inside the viewport?" in an engine-provided way, without
     * comparing time values (they can be numbers, strings or business days).
     */
    private _rightmostBarX(): number | null {
        const timeScale = this.chart.timeScale();
        let rightmost: number | null = null;
        const seriesList = [this.series, ...this._seriesList];
        for (const series of seriesList) {
            const point = series.dataByIndex(Number.MAX_SAFE_INTEGER, -1) as
                { time?: Time } | null;
            if (!point || point.time === undefined) continue;
            const coordinate = timeScale.timeToCoordinate(point.time);
            if (coordinate === null) continue;
            rightmost = rightmost === null
                ? coordinate : Math.max(rightmost, coordinate);
        }
        return rightmost;
    }

    reSize() {
        let topBarOffset = this.scale.height !== 0 ? this._topBar?._div.offsetHeight || 0 : 0
        const width = window.innerWidth
        // page-level top bars sit above every chart, so they are not part of the
        // area the charts may use
        const height = window.innerHeight - Handler.pageHeight()
        this.chart.resize(width * this.scale.width, (height * this.scale.height) - topBarOffset)
        this.wrapper.style.width = `${100 * this.scale.width}%`
        // in px, not %: the percentages would be of the window and would push the
        // last chart under the page-level bars
        this.wrapper.style.height = `${height * this.scale.height}px`
        this._applyTile(height)
        
        // a resize moves the left price scale too, and a crosshair event (which
        // also re-anchors the legend) does not necessarily follow one
        this.legend?.updatePosition()

        // TODO definitely a better way to do this
        if (this.scale.height === 0 || this.scale.width === 0) {
            // if (this.legend.div.style.display == 'flex') this.legend.div.style.display = 'none'
            if (this.toolBox) {
                this.toolBox.div.style.display = 'none'
            }
        }
        else {
            // this.legend.div.style.display = 'flex'
            if (this.toolBox) {
                this.toolBox.div.style.display = 'flex'
            }
        }
    }

    /**
     * Remove this chart's wrapper from the DOM.
     *
     * `chart.remove()` only destroys the Lightweight Charts instance; the
     * `.handler` wrapper stayed behind - floated (or absolutely positioned, in a
     * 2D layout) at its old size. Closing a panel therefore left an invisible
     * box that occupied space and could cover the charts created next. This is
     * terminal: call it right after ``chart.remove()``.
     */
    destroy() {
        this.wrapper.remove()
        const index = Handler._instances.indexOf(this)
        if (index >= 0) Handler._instances.splice(index, 1)
    }

    /**
     * Apply (or clear) the absolute geometry of a 2D tile layout.
     *
     * The row/column layout floats the wrappers and sizes them in pixels, which
     * is enough. A 2D layout needs ``left``/``top`` as well - and doing that with
     * percentages collapsed to 0, because ``#container`` has no definite height
     * (every child is absolute), so all the tiles landed at the top-left and the
     * page looked like a single chart. Positioning in pixels, inside ``reSize``,
     * also means a window resize (which calls ``reSize``) moves the tiles. The
     * page top-bar height is added so the first row does not sit under it.
     */
    private _applyTile(area: number) {
        const wrapper = this.wrapper
        if (this.tile) {
            const [x, y, w, h] = this.tile
            // Use the viewport width, the same basis `reSize` sizes the canvas
            // with - `containerDiv.getBoundingClientRect()` can be narrower (a
            // page-level bar, a scrollbar) and the wrapper would then clip the
            // chart to a fraction of the window.
            const width = window.innerWidth
            const topOffset = window.innerHeight - area
            wrapper.style.position = 'absolute'
            wrapper.style.float = 'none'
            wrapper.style.left = `${width * x}px`
            wrapper.style.top = `${topOffset + area * y}px`
            wrapper.style.width = `${width * w}px`
            wrapper.style.height = `${area * h}px`
        } else if (wrapper.style.position === 'absolute') {
            // leaving a 2D layout: hand the wrapper back to the float layout
            wrapper.style.position = ''
            wrapper.style.float = this.floatPosition
            wrapper.style.left = ''
            wrapper.style.top = ''
        }
    }

    private _createChart(kind: string) {
        const base = {
            width: window.innerWidth * this.scale.width,
            height: (window.innerHeight - Handler.pageHeight()) * this.scale.height,
            layout: {
                textColor: window.pane.color,
                background: {
                    color: '#000000',
                    type: ColorType.Solid,
                },
                fontSize: 12,
                // Hidden unless the host asked for it (see python
                // `pylightcharts.set_attribution_logo`). The Apache-2.0 notice asks
                // for attribution, so a published app that hides this should credit
                // TradingView and link to https://www.tradingview.com/ somewhere
                // its users can see.
                attributionLogo: this._attributionLogo,
            },
            grid: {
                vertLines: {color: 'rgba(29, 30, 38, 5)'},
                horzLines: {color: 'rgba(29, 30, 58, 5)'},
            },
        };

        // horizontal scale is a plain number (months / price) instead of time
        if (kind === 'yield-curve') {
            return createYieldCurveChart(this.div, base as any) as unknown as IChartApi;
        }
        if (kind === 'options') {
            return createOptionsChart(this.div, base as any) as unknown as IChartApi;
        }
        if (kind.startsWith('custom:')) {
            const behavior = lookupHorzScaleBehavior(kind.slice('custom:'.length));
            if (!behavior) {
                throw new Error(`pylightcharts: no horizontal scale behavior registered as '${kind.slice(7)}'`);
            }
            return createChartEx(this.div, behavior as any, base as any) as unknown as IChartApi;
        }

        return createChart(this.div, {
            ...base,
            rightPriceScale: {
                scaleMargins: {top: 0.3, bottom: 0.25},
            },
            timeScale: {timeVisible: true, secondsVisible: false},
            crosshair: {
                mode: CrosshairMode.Normal,
                vertLine: {
                    labelBackgroundColor: 'rgb(46, 46, 46)'
                },
                horzLine: {
                    labelBackgroundColor: 'rgb(55, 55, 55)'
                }
            },
            handleScroll: {vertTouchDrag: true},
        })
    }

    createCandlestickSeries() {
        const up = 'rgba(39, 157, 130, 100)'
        const down = 'rgba(200, 97, 100, 100)'
        const candleSeries = this.chart.addSeries(CandlestickSeries, {
            upColor: up, borderUpColor: up, wickUpColor: up,
            downColor: down, borderDownColor: down, wickDownColor: down
        });
        candleSeries.priceScale().applyOptions({
            scaleMargins: {top: 0.2, bottom: 0.2},
        });
        return candleSeries;
    }

    createVolumeSeries() {
        const volumeSeries = this.chart.addSeries(HistogramSeries, {
            color: '#26a69a',
            priceFormat: {type: 'volume'},
            priceScaleId: 'volume_scale',
        })
        volumeSeries.priceScale().applyOptions({
            scaleMargins: {top: 0.8, bottom: 0},
        });
        return volumeSeries;
    }

    createLineSeries(name: string, options: DeepPartial<LineStyleOptions & SeriesOptionsCommon>, showLegendToggle: boolean = true) {
        const line = this.chart.addSeries(LineSeries, {...options});
        this._seriesList.push(line);
        this.legend?.makeSeriesRow(name, line, showLegendToggle)
        return {
            name: name,
            series: line,
            priceScale: line.priceScale(),
        }
    }

    createHistogramSeries(name: string, options: DeepPartial<HistogramStyleOptions & SeriesOptionsCommon>, showLegendToggle: boolean = true) {
        const line = this.chart.addSeries(HistogramSeries, {...options});
        this._seriesList.push(line);
        this.legend?.makeSeriesRow(name, line, showLegendToggle)
        return {
            name: name,
            series: line,
            priceScale: line.priceScale(),
        }
    }

    private static readonly _seriesDefinitions: Record<string, SeriesDefinition<SeriesType>> = {
        Area: AreaSeries,
        Bar: BarSeries,
        Baseline: BaselineSeries,
        Candlestick: CandlestickSeries,
        Histogram: HistogramSeries,
        Line: LineSeries,
    };

    /**
     * Generic series creation (the whole point of the bridge): lets Python create
     * any series type without a matching hand-written method here. `handle` is the
     * JS handle the created wrapper is registered under, so Python can address it.
     */
    public addSeries(kind: string, name: string, options: unknown, handle?: string, paneIndex?: number, showLegendToggle: boolean = true) {
        const definition = Handler._seriesDefinitions[kind];
        if (!definition) {
            throw new Error(`pylightcharts: unknown series kind '${kind}'`);
        }
        const series = (this.chart.addSeries as (d: SeriesDefinition<SeriesType>, o?: unknown, p?: number) => ISeriesApi<SeriesType>)(definition, options, paneIndex);
        this._seriesList.push(series);
        if (name) {
            this.legend?.makeSeriesRow(name, series, showLegendToggle);
        }
        const wrapper = { name, series, priceScale: series.priceScale() };
        if (handle) {
            register(handle, wrapper);
        }
        return wrapper;
    }

    /** Apply a declarative number formatter to the price scale labels. */
    public setPriceFormatter(spec: unknown) {
        const formatter = resolveFormatter(spec as any, 'price');
        (this.chart.applyOptions as any)({ localization: { priceFormatter: formatter } });
    }

    /** Apply a declarative time formatter to the time scale labels. */
    public setTimeFormatter(spec: unknown) {
        const formatter = resolveFormatter(spec as any, 'time');
        (this.chart.applyOptions as any)({ localization: { timeFormatter: formatter } });
    }

    /** Create a declarative custom series (see custom-series/custom-series.ts). */
    public createCustomSeries(name: string, options: unknown, handle?: string, paneIndex?: number, spec?: unknown, showLegendToggle: boolean = true) {
        const paneView = spec ? new SpecCustomSeriesPaneView(spec as any) : new CustomSeriesPaneView();
        const series = (this.chart.addCustomSeries as any)(paneView, options, paneIndex) as ISeriesApi<SeriesType>;
        this._seriesList.push(series);
        if (name) {
            this.legend?.makeSeriesRow(name, series, showLegendToggle);
        }
        const wrapper = { name, series, priceScale: series.priceScale(), paneView };
        if (handle) {
            register(handle, wrapper);
        }
        return wrapper;
    }

    /** Remove a series created through `addSeries`, including its legend row. */
    public removeSeries(wrapper: { series: ISeriesApi<SeriesType>; name?: string } | undefined) {
        const series = wrapper && wrapper.series;
        if (!series) {
            return;
        }
        const name = wrapper && wrapper.name;
        const index = this._seriesList.indexOf(series);
        if (index >= 0) {
            this._seriesList.splice(index, 1);
        }
        // 先按对象身份找；找不到再按名字兜底。自定义序列（信号箭头等）在 legend
        // 里登记的 series 对象与这里收到的 wrapper.series 未必是同一个引用，
        // 只比身份的话图例行会留下来，切页面时一组一组地累加。
        const legendRow = this.legend?._lines.find(
            (row: { series: ISeriesApi<SeriesType>; name?: string }) =>
                row.series === series || (!!name && row.name === name));
        if (legendRow && this.legend) {
            this.legend._lines = this.legend._lines.filter((row: { series: ISeriesApi<SeriesType> }) => row !== legendRow);
            const rowEl = (legendRow as { row: HTMLDivElement }).row;
            if (rowEl.parentNode) {
                rowEl.parentNode.removeChild(rowEl);
            }
        }
        this.chart.removeSeries(series);
    }

    /** Subscribe to chart clicks. Unlike ``chart.subscribeClick`` this is additive. */
    addClickListener(listener: MouseEventHandler<Time>) {
        if (!this._clickListeners.includes(listener)) this._clickListeners.push(listener)
    }

    removeClickListener(listener: MouseEventHandler<Time>) {
        this._clickListeners = this._clickListeners.filter(l => l !== listener)
    }

    /** Subscribe to crosshair moves. Unlike ``chart.subscribeCrosshairMove`` this is additive. */
    addCrosshairListener(listener: MouseEventHandler<Time>) {
        if (!this._crosshairListeners.includes(listener)) this._crosshairListeners.push(listener)
    }

    removeCrosshairListener(listener: MouseEventHandler<Time>) {
        this._crosshairListeners = this._crosshairListeners.filter(l => l !== listener)
    }

    /** Subscribe to chart double-clicks. Additive, like `addClickListener`. */
    addDblClickListener(listener: MouseEventHandler<Time>) {
        if (!this._dblClickListeners.includes(listener)) this._dblClickListeners.push(listener)
    }

    removeDblClickListener(listener: MouseEventHandler<Time>) {
        this._dblClickListeners = this._dblClickListeners.filter(l => l !== listener)
    }

    createToolBox() {
        this.toolBox = new ToolBox(this.id, this, this.series, this.commandFunctions);
        this.div.appendChild(this.toolBox.div);
    }

    createTopBar() {
        this._topBar = new TopBar(this);
        this.wrapper.prepend(this._topBar._div)
        return this._topBar;
    }

    /** Height left for the charts once the page-level bars are accounted for. */
    static pageHeight(): number {
        return TopBar.pageHeight();
    }

    /** Re-size every chart: a page-level bar changed height. */
    static reLayoutAll() {
        for (const handler of Handler._instances) {
            handler.reSize();
        }
    }

    /** Create the bar that spans the window, above every chart. */
    static createPageTopBar(): TopBar {
        const bar = new TopBar(undefined, true);
        // first child: the charts are floated and would otherwise start at the top
        window.containerDiv.insertBefore(bar._div, window.containerDiv.firstChild)
        TopBar.registerPageBar(bar)
        Handler.reLayoutAll()
        return bar;
    }

    public setWatermark(text: string, fontSize: number, color: string, handle?: string) {
        // v5: watermark moved from a chart option to a pane primitive.
        const options: DeepPartial<TextWatermarkOptions> = {
            horzAlign: 'center',
            vertAlign: 'center',
            lines: [{ text, color, fontSize }],
        };
        if (this._watermark) {
            this._watermark.applyOptions(options);
        } else {
            this._watermark = createTextWatermark(this.chart.panes()[0], options);
        }
        if (handle) {
            register(handle, this._watermark);
        }
        return this._watermark;
    }

    /**
     * v5 replacement for `series.setMarkers()`.
     * Keeps one marker primitive per series, cached across calls.
     */
    public static setMarkers(series: ISeriesApi<SeriesType>, markers: SeriesMarker<Time>[], handle?: string) {
        let primitive = Handler._markerPrimitives.get(series);
        if (primitive) {
            primitive.setMarkers(markers);
        } else {
            primitive = createSeriesMarkers(series, markers);
            Handler._markerPrimitives.set(series, primitive);
        }
        if (handle) {
            register(handle, primitive);
        }
        return primitive;
    }

    /**
     * A crosshair tooltip (tracking or magnifier) for one series.
     *
     * Lightweight Charts has no tooltip of its own - the official tutorial
     * builds one from an `html` element plus `subscribeCrosshairMove`; this is
     * the same thing inside the bundle, so it updates at pointer speed.
     */
    public createTooltip(series: ISeriesApi<SeriesType>, options: TooltipOptions,
                         handle?: string) {
        const tooltip = new Tooltip(this, series, options);
        if (handle) {
            tooltip.setHandle(handle);
            register(handle, tooltip);
        }
        return tooltip;
    }

    /** v5 up-down markers plugin, attached to a series. */
    public createUpDownMarkers(series: ISeriesApi<SeriesType>, options: unknown, handle?: string) {
        const markers = createUpDownMarkers(series, options as any);
        if (handle) {
            register(handle, markers);
        }
        return markers;
    }

    /** v5 image watermark plugin, attached to a pane. */
    public createImageWatermark(paneIndex: number, imageUrl: string, options: unknown, handle?: string) {
        const pane = this.chart.panes()[paneIndex];
        const watermark = createImageWatermark(pane, imageUrl, options as any);
        if (handle) {
            register(handle, watermark);
        }
        return watermark;
    }

    toJSON() {
        // Exclude the chart attribute from serialization
        const {chart, ...serialized} = this;
        return serialized;
    }

    /** Everything `syncCharts` attached to a pair, so it can be undone. */
    private static _syncTeardown =
        new Map<Handler, { parent: Handler, detach: Array<() => void> }>();

    /** Unlink two charts (no-op when they were not linked).
     *
     * `syncCharts` used to leave its listeners behind, so a second call stacked
     * handlers (each pan moved the other chart twice) and there was no way back
     * to independent charts. Every link now keeps its own teardown. */
    public static unsyncCharts(childChart: Handler, parentChart: Handler) {
        const link = Handler._syncTeardown.get(childChart);
        if (!link || link.parent !== parentChart) return;
        for (const detach of link.detach) detach();
        Handler._syncTeardown.delete(childChart);
    }

    /** Link two charts: crosshair, and - unless `crosshairOnly` - pan/zoom.
     *
     * The link follows the chart under the mouse; calling this again replaces
     * the previous link instead of stacking listeners. */
    public static syncCharts(childChart:Handler, parentChart: Handler, crosshairOnly = false) {
        Handler.unsyncCharts(childChart, parentChart);

        function crosshairHandler(chart: Handler, point: any) {//point: BarData | LineData) {
            if (!point) {
                chart.chart.clearCrosshairPosition()
                return
            }
            // TODO fix any point ?
            chart.chart.setCrosshairPosition(point.value || point!.close, point.time, chart.series);
            chart.legend?.legendHandler(point, true)
        }

        function getPoint(series: ISeriesApi<SeriesType>, param: MouseEventParams) {
            if (!param.time) return null;
            return param.seriesData.get(series) || null;
        }

        const childTimeScale = childChart.chart.timeScale();
        const parentTimeScale = parentChart.chart.timeScale();

        const setChildRange = (timeRange: LogicalRange | null) => {
            if(timeRange) childTimeScale.setVisibleLogicalRange(timeRange);
        }
        const setParentRange = (timeRange: LogicalRange | null) => {
            if(timeRange) parentTimeScale.setVisibleLogicalRange(timeRange);
        }

        const setParentCrosshair = (param: MouseEventParams) => {
            crosshairHandler(parentChart, getPoint(childChart.series, param))
        }
        const setChildCrosshair = (param: MouseEventParams) => {
            crosshairHandler(childChart, getPoint(parentChart.series, param))
        }

        let selected = parentChart
        function addMouseOverListener(
            thisChart: Handler,
            otherChart: Handler,
            thisCrosshair: MouseEventHandler<Time>,
            otherCrosshair: MouseEventHandler<Time>,
            thisRange: LogicalRangeChangeEventHandler,
            otherRange: LogicalRangeChangeEventHandler)
        {
            const onMouseOver = () => {
                if (selected === thisChart) return
                selected = thisChart
                otherChart.removeCrosshairListener(thisCrosshair)
                thisChart.addCrosshairListener(otherCrosshair)
                if (crosshairOnly) return;
                otherChart.chart.timeScale().unsubscribeVisibleLogicalRangeChange(thisRange)
                thisChart.chart.timeScale().subscribeVisibleLogicalRangeChange(otherRange)
            }
            thisChart.wrapper.addEventListener('mouseover', onMouseOver)
            return () => thisChart.wrapper.removeEventListener('mouseover', onMouseOver)
        }

        const teardown: Array<() => void> = [
            addMouseOverListener(
                parentChart,
                childChart,
                setParentCrosshair,
                setChildCrosshair,
                setParentRange,
                setChildRange
            ),
            addMouseOverListener(
                childChart,
                parentChart,
                setChildCrosshair,
                setParentCrosshair,
                setChildRange,
                setParentRange
            ),
            () => {
                // the mouseover handlers above subscribe/unsubscribe while
                // moving between charts, so clear every possible registration
                for (const scale of [childTimeScale, parentTimeScale]) {
                    scale.unsubscribeVisibleLogicalRangeChange(setChildRange)
                    scale.unsubscribeVisibleLogicalRangeChange(setParentRange)
                }
                for (const chart of [childChart, parentChart]) {
                    chart.removeCrosshairListener(setChildCrosshair)
                    chart.removeCrosshairListener(setParentCrosshair)
                }
            },
        ];

        parentChart.addCrosshairListener(setChildCrosshair)

        // crosshair-only must not touch the time scales at all: the charts are
        // usually different periods, and snapping one to the other on linking
        // would move what the user is looking at
        const parentRange = parentTimeScale.getVisibleLogicalRange()
        if (parentRange && !crosshairOnly) {
            childTimeScale.setVisibleLogicalRange(parentRange)
        }

        if (!crosshairOnly) {
            parentTimeScale.subscribeVisibleLogicalRangeChange(setChildRange)
        }

        Handler._syncTeardown.set(childChart, { parent: parentChart, detach: teardown })
    }

    public static makeSearchBox(chart: Handler) {
        const searchWindow = document.createElement('div')
        searchWindow.classList.add('searchbox');
        searchWindow.style.display = 'none';

        const magnifyingGlass = document.createElement('div');
        magnifyingGlass.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="24px" height="24px" viewBox="0 0 24 24" version="1.1"><path style="fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;stroke:lightgray;stroke-opacity:1;stroke-miterlimit:4;" d="M 15 15 L 21 21 M 10 17 C 6.132812 17 3 13.867188 3 10 C 3 6.132812 6.132812 3 10 3 C 13.867188 3 17 6.132812 17 10 C 17 13.867188 13.867188 17 10 17 Z M 10 17 "/></svg>`

        const sBox = document.createElement('input');
        sBox.type = 'text';

        searchWindow.appendChild(magnifyingGlass)
        searchWindow.appendChild(sBox)
        chart.div.appendChild(searchWindow);

        chart.commandFunctions.push((event: KeyboardEvent) => {
            if (window.handlerInFocus !== chart.id || window.textBoxFocused) return false
            if (searchWindow.style.display === 'none') {
                if (/^[a-zA-Z0-9]$/.test(event.key)) {
                    searchWindow.style.display = 'flex';
                    sBox.focus();
                    return true
                }
                else return false
            }
            else if (event.key === 'Enter' || event.key === 'Escape') {
                if (event.key === 'Enter') window.callbackFunction(`search${chart.id}_~_${sBox.value}`)
                searchWindow.style.display = 'none'
                sBox.value = ''
                return true
            }
            else return false
        })
        sBox.addEventListener('input', () => sBox.value = sBox.value.toUpperCase())
        return {
            window: searchWindow,
            box: sBox,
        }
    }

    public static makeSpinner(chart: Handler) {
        // idempotent: the polygon chart asks for a spinner too (Events.search)
        if (chart.spinner) return;

        chart.spinner = document.createElement('div');
        chart.spinner.classList.add('spinner');
        chart.wrapper.appendChild(chart.spinner)

        // TODO below can be css (animate)
        let rotation = 0;
        const speed = 10;
        function animateSpinner() {
            // only spin while visible, the element exists on every chart
            if (chart.spinner && chart.spinner.style.display === 'block') {
                rotation += speed
                chart.spinner.style.transform = `translate(-50%, -50%) rotate(${rotation}deg)`
            }
            requestAnimationFrame(animateSpinner)
        }
        animateSpinner();
    }

    /** Show or hide the loading spinner (created for every handler). */
    public setSpinner(visible: boolean) {
        Handler.makeSpinner(this);
        const spinner = this.spinner;
        if (spinner) spinner.style.display = visible ? 'block' : 'none';
    }

    private static readonly _styleMap = {
        '--bg-color': 'backgroundColor',
        '--hover-bg-color': 'hoverBackgroundColor',
        '--click-bg-color': 'clickBackgroundColor',
        '--active-bg-color': 'activeBackgroundColor',
        '--muted-bg-color': 'mutedBackgroundColor',
        '--border-color': 'borderColor',
        '--color': 'color',
        '--active-color': 'activeColor',
    }
    public static setRootStyles(styles: any) {
        const rootStyle = document.documentElement.style;
        for (const [property, valueKey] of Object.entries(this._styleMap)) {
            rootStyle.setProperty(property, styles[valueKey]);
        }
    }
}
