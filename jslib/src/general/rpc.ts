/**
 * Generic RPC bridge between Python and the live chart objects.
 *
 * Python keeps string "handles" that point at live JS objects.  Chart handles
 * look like `window.abcdefgh` (see `IDGen.generate`), series handles are
 * registered explicitly.  A handle is either
 *
 *   - a registered key (see `register`), or
 *   - a dotted path resolved from the global scope, where a leading `window.`
 *     is optional and numeric segments index into arrays.
 *
 * `invoke` then calls any method on the resolved object.  This lets Python
 * drive arbitrary parts of the Lightweight Charts API without adding a single
 * line of TypeScript here.
 */

const registry = new Map<string, unknown>();

/** Look up a registered handle, falling back to a global dotted path. */
export function lookup(handle: string): unknown {
    if (registry.has(handle)) {
        return registry.get(handle);
    }
    const parts = handle.split('.');
    let current: any;
    let rest: string[];
    // a path may start at a registered handle, e.g. `mySeries.priceScale`
    if (registry.has(parts[0])) {
        current = registry.get(parts[0]);
        rest = parts.slice(1);
    } else {
        current = globalThis;
        rest = parts.filter(part => part.length > 0 && part !== 'window');
    }
    for (const part of rest) {
        if (current === null || current === undefined) {
            throw new Error(`pylightcharts: cannot resolve '${handle}' (stuck at '${part}')`);
        }
        current = current[part];
    }
    if (current === undefined) {
        throw new Error(`pylightcharts: cannot resolve '${handle}'`);
    }
    return current;
}

/** Register an object under a handle so Python can reference it later. */
export function register(handle: string, value: unknown): void {
    registry.set(handle, value);
}

/** Drop a previously registered handle. */
export function unregister(handle: string): void {
    registry.delete(handle);
}

/**
 * Resolve `{"$ref": "handle"}` placeholders (recursively) into the live objects
 * they point at. This lets Python pass JS objects as arguments, e.g.
 * `series.attachPrimitive({"$ref": "myPrimitive"})`.
 */
function resolveRefs(value: unknown): unknown {
    if (Array.isArray(value)) {
        return value.map(resolveRefs);
    }
    if (value !== null && typeof value === 'object') {
        const record = value as Record<string, unknown>;
        if (typeof record.$ref === 'string') {
            return lookup(record.$ref);
        }
        const out: Record<string, unknown> = {};
        for (const key of Object.keys(record)) {
            out[key] = resolveRefs(record[key]);
        }
        return out;
    }
    return value;
}

/**
 * Call `method` on the object referenced by `handle`.
 * When `storeAs` is given, the return value is registered under that handle.
 */
export function invoke(handle: string, method: string, args: unknown[] = [], storeAs?: string): unknown {
    const target = lookup(handle) as any;
    const fn = target === null || target === undefined ? undefined : target[method];
    if (typeof fn !== 'function') {
        throw new Error(`pylightcharts: '${handle}.${method}' is not a function`);
    }
    const result = fn.apply(target, resolveRefs(args));
    if (storeAs) {
        register(storeAs, result);
    }
    return result;
}

/** Convenience wrapper for `applyOptions`. */
export function applyOptions(handle: string, options: unknown): void {
    invoke(handle, 'applyOptions', [options]);
}

/** Merge options recursively, used by the Python `apply_options` helper. */
export function deepMerge(target: any, source: any): any {
    if (Array.isArray(target) || Array.isArray(source)) {
        return source;
    }
    if (typeof target === 'object' && target !== null && typeof source === 'object' && source !== null) {
        const out: any = { ...target };
        for (const key of Object.keys(source)) {
            out[key] = key in out ? deepMerge(out[key], source[key]) : source[key];
        }
        return out;
    }
    return source;
}
