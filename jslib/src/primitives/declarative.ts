/**
 * Declarative primitives.
 *
 * `ISeriesPrimitive` / `IPanePrimitive` are plain objects whose methods
 * (`paneViews`, `autoscaleInfo`, `hitTest`, …) run synchronously inside the
 * render loop — python cannot be called from them. This module builds such an
 * object from a JSON spec whose extension points reference **registered JS
 * callbacks** (see `general/callbacks.ts`), so python can construct a primitive
 * without shipping a TS class:
 *
 *   Lib.registerCallback('drawLine', ['target','priceConverter','view','prim'],
 *       'const p=prim.series.priceToCoordinate(100); /* draw *​/')
 *   const prim = Lib.createSeriesPrimitive({ paneViews: [{ draw: 'drawLine' }] }, 'myPrim');
 *   series.attachPrimitive(prim)
 *
 * `spec` fields (all optional):
 *   paneViews        : [{ zOrder?, draw? }]          draw/background callbacks
 *   priceAxisViews   : [{ coordinate?, text?, ... }] series primitives only
 *   timeAxisViews    : [{ coordinate?, text?, ... }]
 *   autoscaleInfo    : callback (startTimePoint, endTimePoint, primitive)
 *   hitTest          : callback (x, y, primitive) -> PrimitiveHoveredItem | null
 *   attached         : callback (param, primitive)
 *   detached         : callback (primitive)
 *   updateAllViews   : callback (primitive)
 */
import {
    AutoscaleInfo,
    IPrimitivePaneRenderer,
    IPrimitivePaneView,
    ISeriesPrimitive,
    ISeriesPrimitiveAxisView,
    PrimitiveHoveredItem,
    SeriesAttachedParameter,
    Time,
} from 'lightweight-charts';
import { CanvasRenderingTarget2D } from 'fancy-canvas';
import { lookupCallback } from '../general/callbacks';
import { register } from '../general/rpc';

type AnyCallback = (...args: any[]) => any;

function callback(name?: string): AnyCallback | undefined {
    return name ? lookupCallback(name) : undefined;
}

export interface PaneViewSpec {
    zOrder?: 'bottom' | 'normal' | 'top';
    /** callback(target, priceConverter, view, primitive) */
    draw?: string;
    /** callback(target, priceConverter, view, primitive) — optional background pass */
    drawBackground?: string;
}

export interface AxisViewSpec {
    coordinate?: string;
    text?: string;
    textColor?: string;
    backColor?: string;
    visible?: string;
    tickVisible?: string;
}

export interface PrimitiveSpec {
    paneViews?: PaneViewSpec[];
    priceAxisPaneViews?: PaneViewSpec[];
    timeAxisPaneViews?: PaneViewSpec[];
    priceAxisViews?: AxisViewSpec[];
    timeAxisViews?: AxisViewSpec[];
    autoscaleInfo?: string;
    hitTest?: string;
    attached?: string;
    detached?: string;
    updateAllViews?: string;
}

class CallbackPaneRenderer implements IPrimitivePaneRenderer {
    constructor(private readonly _view: CallbackPaneView) {}

    private _invoke(name: string | undefined, target: CanvasRenderingTarget2D, priceConverter?: unknown): void {
        const fn = callback(name);
        if (fn) fn(target, priceConverter, this._view, this._view._primitive);
    }

    draw(target: CanvasRenderingTarget2D, priceConverter?: unknown): void {
        this._invoke(this._view._spec.draw, target, priceConverter);
    }

    drawBackground(target: CanvasRenderingTarget2D, priceConverter?: unknown): void {
        this._invoke(this._view._spec.drawBackground, target, priceConverter);
    }
}

class CallbackPaneView implements IPrimitivePaneView {
    constructor(public readonly _primitive: CallbackPrimitive, public readonly _spec: PaneViewSpec) {}

    zOrder(): 'bottom' | 'normal' | 'top' {
        return this._spec.zOrder ?? 'normal';
    }

    renderer(): IPrimitivePaneRenderer {
        return new CallbackPaneRenderer(this);
    }
}

class CallbackAxisView implements ISeriesPrimitiveAxisView {
    constructor(private readonly _primitive: CallbackPrimitive, private readonly _spec: AxisViewSpec) {}

    private _call(name: string | undefined, fallback: unknown): any {
        const fn = callback(name);
        return fn ? fn(this._primitive) : fallback;
    }

    coordinate(): number { return this._call(this._spec.coordinate, 0); }
    text(): string { return this._call(this._spec.text, ''); }
    textColor(): string { return this._call(this._spec.textColor, '#000000'); }
    backColor(): string { return this._call(this._spec.backColor, '#FFFFFF'); }
    visible(): boolean { return this._call(this._spec.visible, true); }
    tickVisible(): boolean { return this._call(this._spec.tickVisible, true); }
}

export class CallbackPrimitive implements ISeriesPrimitive<Time> {
    public _spec: PrimitiveSpec;
    private readonly _paneViews: CallbackPaneView[];
    private readonly _priceAxisPaneViews: CallbackPaneView[];
    private readonly _timeAxisPaneViews: CallbackPaneView[];
    private readonly _priceAxisViews: CallbackAxisView[];
    private readonly _timeAxisViews: CallbackAxisView[];
    private _attached?: SeriesAttachedParameter<Time>;

    constructor(spec: PrimitiveSpec = {}) {
        this._spec = spec;
        this._paneViews = (spec.paneViews ?? []).map(view => new CallbackPaneView(this, view));
        this._priceAxisPaneViews = (spec.priceAxisPaneViews ?? []).map(view => new CallbackPaneView(this, view));
        this._timeAxisPaneViews = (spec.timeAxisPaneViews ?? []).map(view => new CallbackPaneView(this, view));
        this._priceAxisViews = (spec.priceAxisViews ?? []).map(view => new CallbackAxisView(this, view));
        this._timeAxisViews = (spec.timeAxisViews ?? []).map(view => new CallbackAxisView(this, view));
    }

    // ---- helpers exposed to the callbacks ----
    public get chart() { return this._attached?.chart; }
    public get series() { return this._attached?.series; }
    public requestUpdate(): void { this._attached?.requestUpdate(); }
    public applyOptions(options: Partial<PrimitiveSpec>): void { this._spec = { ...this._spec, ...options }; }
    public options(): PrimitiveSpec { return this._spec; }

    // ---- ISeriesPrimitive ----
    public updateAllViews(): void { callback(this._spec.updateAllViews)?.(this); }
    public paneViews(): readonly IPrimitivePaneView[] { return this._paneViews; }
    public priceAxisPaneViews(): readonly IPrimitivePaneView[] { return this._priceAxisPaneViews; }
    public timeAxisPaneViews(): readonly IPrimitivePaneView[] { return this._timeAxisPaneViews; }
    public priceAxisViews(): readonly ISeriesPrimitiveAxisView[] { return this._priceAxisViews; }
    public timeAxisViews(): readonly ISeriesPrimitiveAxisView[] { return this._timeAxisViews; }

    public autoscaleInfo(startTimePoint: unknown, endTimePoint: unknown): AutoscaleInfo | null {
        const fn = callback(this._spec.autoscaleInfo);
        return fn ? fn(startTimePoint, endTimePoint, this) : null;
    }

    public hitTest(x: number, y: number): PrimitiveHoveredItem | null {
        const fn = callback(this._spec.hitTest);
        return fn ? fn(x, y, this) : null;
    }

    public attached(param: SeriesAttachedParameter<Time>): void {
        this._attached = param;
        callback(this._spec.attached)?.(param, this);
    }

    public detached(): void {
        callback(this._spec.detached)?.(this);
        this._attached = undefined;
    }
}

/** Pane primitives only expose pane views (no axis views / autoscaleInfo). */
export class CallbackPanePrimitive {
    public _spec: PrimitiveSpec;
    private readonly _paneViews: CallbackPaneView[];
    private _attached?: unknown;

    constructor(spec: PrimitiveSpec = {}) {
        this._spec = spec;
        this._paneViews = (spec.paneViews ?? []).map(view => new CallbackPaneView(this as unknown as CallbackPrimitive, view));
    }

    public get pane() { return this._attached; }
    public requestUpdate(): void { (this._attached as any)?.requestUpdate?.(); }
    public applyOptions(options: Partial<PrimitiveSpec>): void { this._spec = { ...this._spec, ...options }; }
    public options(): PrimitiveSpec { return this._spec; }

    public updateAllViews(): void { callback(this._spec.updateAllViews)?.(this); }
    public paneViews(): readonly IPrimitivePaneView[] { return this._paneViews; }
    public hitTest(x: number, y: number): PrimitiveHoveredItem | null {
        const fn = callback(this._spec.hitTest);
        return fn ? fn(x, y, this) : null;
    }
    public attached(param: unknown): void { this._attached = param; callback(this._spec.attached)?.(param, this); }
    public detached(): void { callback(this._spec.detached)?.(this); this._attached = undefined; }
}

/** Create a series primitive from a spec and register it under `handle`. */
export function createSeriesPrimitive(spec: PrimitiveSpec, handle: string): CallbackPrimitive {
    const primitive = new CallbackPrimitive(spec);
    register(handle, primitive);
    return primitive;
}

/** Create a pane primitive from a spec and register it under `handle`. */
export function createPanePrimitive(spec: PrimitiveSpec, handle: string): CallbackPanePrimitive {
    const primitive = new CallbackPanePrimitive(spec);
    register(handle, primitive);
    return primitive;
}
