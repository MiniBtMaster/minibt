/**
 * minibt desk app entry point (quote window + chart window, all TS).
 *
 * Bundled to `desk.js` (IIFE, global `Desk`) and loaded by `desk.html`:
 *
 *     <script src="./lightweight-charts.js"></script>
 *     <script src="./desk.js"></script>
 *
 * Hosts:
 *   - Qt        `minibt.desk.app.DeskWindow`  (QWebChannel)
 *   - browser   `minibt.desk.web`             (SSE + POST /callback)
 *   - minibt-charts / tests                   (bring your own DeskTransport)
 */
import { DeskApp, registerDesk } from './app';
import { mountDesk } from './sdk';
import { detectTransport, MockTransport, RestTransport, SseTransport, QtTransport } from './transport';

declare global {
    interface Window {
        __desk?: DeskApp;
        __deskConfig?: Record<string, unknown>;
    }
}

const config = (window.__deskConfig || {}) as Record<string, any>;

const app = new DeskApp({
    theme: config.theme === 'light' ? 'light' : 'dark',
    title: config.title,
    transport: detectTransport(config as never),
});

registerDesk(app);

function start(): void {
    const host = document.getElementById('desk') || document.body;
    app.mount(host as HTMLElement);
    app.boot();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
} else {
    start();
}

export {
    DeskApp, registerDesk, detectTransport, mountDesk,
    MockTransport, RestTransport, SseTransport, QtTransport,
};
