/**
 * Shared helper for panel → Python callbacks.
 *
 * The bridge installs `window.callbackFunction` (see `Window.__init__`). A panel
 * reports an event as `"<callbackName>_~_<payload>"`, which Python's
 * `parse_event_message` splits back into `(name, args)`. In a static page
 * without Python, `callbackFunction` is the shim from `export.py`, so this is
 * always safe to call.
 */
export function emitCallback(name: string | null, payload: string): boolean {
    if (!name) {
        return false;
    }
    const host = window as unknown as {
        callbackFunction?: (message: string) => void;
    };
    if (typeof host.callbackFunction === 'function') {
        host.callbackFunction(`${name}_~_${payload}`);
        return true;
    }
    return false;
}

/** Append a `<style>` block once (keyed by `id`). */
export function ensureStyle(id: string, css: string): void {
    if (document.getElementById(id)) {
        return;
    }
    const style = document.createElement('style');
    style.id = id;
    style.textContent = css;
    document.head.appendChild(style);
}

/** Wrap a value so it can be emitted as a single callback argument. */
export function asMessage(...parts: Array<string | number>): string {
    return parts.map((part) => String(part)).join(';;;');
}
