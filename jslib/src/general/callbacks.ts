/**
 * Function-valued options.
 *
 * Several Lightweight Charts options are synchronous JS callbacks
 * (`timeScale.tickMarkFormatter`, `series.priceFormat.formatter`,
 * `series.autoscaleInfoProvider`, `localization.*`). JSON cannot carry a
 * function, so python registers a callback **by name** here (compiled with
 * `new Function`) and then asks the bridge to install it at the right option
 * path. The callbacks run entirely inside the page; they never call back into
 * python (which would be fatal on a render frame).
 *
 *   Lib.registerCallback('vol', ['price'], 'return (price/1e6).toFixed(1)+"M"')
 *   Lib.setOptionCallback('window.abc.series', 'applyOptions',
 *                         'priceFormat.formatter', 'vol')
 *
 * NOTE: `new Function` requires a CSP that allows `unsafe-eval` (the default in
 * the desktop/Jupyter webviews). Hosts that lock CSP down can register the
 * function with plain JS through `Window.preload()` and call only
 * `setOptionCallback` from python.
 */
import { lookup } from './rpc';

type AnyFunction = (...args: any[]) => any;

const callbacks = new Map<string, AnyFunction>();

/** Register a callback from its parameter names and a JS statement body. */
export function registerCallback(name: string, params: string[], body: string): void {
    // eslint-disable-next-line no-new-func
    callbacks.set(name, new Function(...params, body) as AnyFunction);
}

export function lookupCallback(name: string): AnyFunction | undefined {
    return callbacks.get(name);
}

export function listCallbacks(): string[] {
    return [...callbacks.keys()];
}

export function unregisterCallback(name: string): void {
    callbacks.delete(name);
}

/**
 * Install a registered callback at `handle.<method>({ <optionPath>: fn })`.
 * `optionPath` may be dotted (`localization.priceFormatter`).
 */
export function setOptionCallback(handle: string, method: string, optionPath: string,
                                  callbackName: string): void {
    const target = lookup(handle) as any;
    if (!target || typeof target[method] !== 'function') {
        throw new Error(`pylightcharts: '${handle}.${method}' is not a function`);
    }
    const fn = callbacks.get(callbackName);
    if (!fn) {
        throw new Error(`pylightcharts: no callback registered as '${callbackName}'`);
    }
    const options: Record<string, any> = {};
    const parts = optionPath.split('.');
    let cursor = options;
    for (let i = 0; i < parts.length - 1; i++) {
        cursor = cursor[parts[i]] = {};
    }
    cursor[parts[parts.length - 1]] = fn;
    target[method](options);
}

/**
 * Merge-safe variant for a series' `priceFormat.formatter`.
 *
 * `priceFormat` is a union type; a plain `applyOptions({priceFormat:{formatter}})`
 * can drop its `type`. This reads the current options first and merges.
 */
export function setPriceFormatFormatter(handle: string, callbackName: string): void {
    const target = lookup(handle) as any;
    if (!target || typeof target.applyOptions !== 'function') {
        throw new Error(`pylightcharts: '${handle}' is not a series`);
    }
    const fn = callbacks.get(callbackName);
    if (!fn) {
        throw new Error(`pylightcharts: no callback registered as '${callbackName}'`);
    }
    const current = typeof target.options === 'function' ? target.options() : {};
    target.applyOptions({ priceFormat: { ...(current.priceFormat || {}), formatter: fn } });
}
