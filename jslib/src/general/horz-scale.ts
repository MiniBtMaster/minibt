/**
 * Custom horizontal scale behaviors.
 *
 * `createChartEx(container, horzScaleBehavior, options)` accepts any
 * `IHorzScaleBehavior` instance. Python cannot build one, so a JS instance is
 * registered by name and requested when the chart is created:
 *
 *   Lib.registerHorzScaleBehavior('myScale', new MyBehavior());
 *   new Lib.Handler(id, w, h, position, autoSize, 'custom:myScale');
 *
 * From python, inject the registration with `Window.preload(...)` before the
 * chart is created (see docs/advanced/custom-scale.md).
 */
import { lookupCallback } from './callbacks';

export interface HorzScaleBehaviorLike {
    options(): unknown;
    setOptions(options: unknown): void;
    preprocessData?(data: unknown[]): unknown[];
    update?(...args: unknown[]): void;
    [key: string]: unknown;
}

const registry = new Map<string, HorzScaleBehaviorLike>();

export function registerHorzScaleBehavior(name: string, behavior: HorzScaleBehaviorLike): void {
    registry.set(name, behavior);
}

export function lookupHorzScaleBehavior(name: string): HorzScaleBehaviorLike | undefined {
    return registry.get(name);
}

/** A behavior spec: every `IHorzScaleBehavior` method is a registered callback name. */
export interface HorzScaleBehaviorSpec {
    options?: string;
    setOptions?: string;
    preprocessData?: string;
    convertHorzItemToInternal?: string;
    createConverterToInternalObj?: string;
    key?: string;
    cacheKey?: string;
    updateFormatter?: string;
    formatHorzItem?: string;
    formatTickmark?: string;
    maxTickMarkWeight?: string;
    fillWeightsForPoints?: string;
    shouldResetTickmarkLabels?: string;
}

/**
 * Build an `IHorzScaleBehavior` from registered callbacks and register it.
 * Missing methods fall back to sensible identity/string implementations so a
 * caller only has to provide the parts it actually needs.
 */
export function registerHorzScaleBehaviorSpec(name: string, spec: HorzScaleBehaviorSpec): void {
    const fn = (key: keyof HorzScaleBehaviorSpec) => {
        const callbackName = spec[key];
        return callbackName ? lookupCallback(callbackName) : undefined;
    };
    const behavior: HorzScaleBehaviorLike = {
        options: () => fn('options')?.() ?? {},
        setOptions: (options: unknown) => fn('setOptions')?.(options),
        preprocessData: (data: unknown) => fn('preprocessData')?.(data) ?? data,
        convertHorzItemToInternal: (item: unknown) => fn('convertHorzItemToInternal')?.(item) ?? item,
        createConverterToInternalObj: (data: unknown) =>
            fn('createConverterToInternalObj')?.(data) ?? ((item: unknown) => item),
        key: (item: unknown) => fn('key')?.(item) ?? item,
        cacheKey: (item: unknown) => fn('cacheKey')?.(item) ?? 0,
        updateFormatter: (options: unknown) => fn('updateFormatter')?.(options),
        formatHorzItem: (item: unknown) => fn('formatHorzItem')?.(item) ?? String(item),
        formatTickmark: (tickMark: unknown, localization: unknown) =>
            fn('formatTickmark')?.(tickMark, localization) ?? String(tickMark),
        maxTickMarkWeight: (marks: unknown) => fn('maxTickMarkWeight')?.(marks) ?? 0,
        fillWeightsForPoints: (points: unknown, startIndex: unknown) =>
            fn('fillWeightsForPoints')?.(points, startIndex),
        shouldResetTickmarkLabels: (tickMarks: unknown) =>
            fn('shouldResetTickmarkLabels')?.(tickMarks) ?? false,
    };
    registerHorzScaleBehavior(name, behavior);
}
