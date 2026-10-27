/**
 * Transport abstraction for the minibt desk app.
 *
 * The desk UI is *transport agnostic*: every user action is sent as one JSON
 * command (`{cmd, payload}`), and every server push is one JS statement calling
 * `window.__desk.applyPatch(...)`.
 *
 * That means the exact same bundle runs in:
 *
 *   - **Qt** desktop window  → `QtTransport`   (QWebChannel → `callbackFunction`)
 *   - **browser / live**     → `SseTransport`  (POST `/callback` + SSE `/events`)
 *   - **minibt-charts**      → `RestTransport` / custom (bring your own backend)
 *   - **unit tests / static** → `MockTransport`
 */

export interface DeskCommand {
    cmd: string;
    payload?: unknown;
}

export interface DeskTransport {
    /** stable name, shown in the status bar (`qt` / `sse` / `rest` / `mock`) */
    readonly kind: string;
    /** JS → backend */
    send(command: DeskCommand): void;
    /** true when a backend is actually attached */
    readonly connected: boolean;
}

/**
 * Qt / QWebEngine: pylightcharts rebinds `window.callbackFunction` per backend.
 *
 * ⚠ 页面刚加载时 `window.pythonObject`（QWebChannel 桥）可能还没建立，
 * 此时调用 `callbackFunction` 会抛
 * ``Cannot read properties of undefined (reading 'callback')``。
 * 所以这里**先排队**，每 50ms 轮询桥，就绪后一次性把命令发出去 ✓
 */
export class QtTransport implements DeskTransport {
    readonly kind = 'qt';

    private queue: DeskCommand[] = [];
    private timer: number | undefined;
    private waited = 0;
    private warned = false;

    get connected(): boolean {
        return !!this._bridge();
    }

    private _bridge(): boolean {
        const host = window as unknown as {
            pythonObject?: { callback?: Function };
            callbackFunction?: Function;
        };
        return !!(host.pythonObject && typeof host.callbackFunction === 'function');
    }

    send(command: DeskCommand): void {
        if (this._bridge()) {
            this._invoke(command);
            return;
        }
        this.queue.push(command);
        this._waitForBridge();
    }

    private _invoke(command: DeskCommand): void {
        const fn = (window as unknown as {
            callbackFunction?: (message: string) => void }).callbackFunction;
        if (typeof fn !== 'function') return;
        // pylightcharts wire format:  "<name>_~_<arg0>;;;<arg1>"
        fn(`desk_~_${JSON.stringify(command)}`);
    }

    /** 桥没就绪 → 轮询（最多 15 秒），就绪后 flush 队列 ✓ */
    private _waitForBridge(): void {
        if (this.timer !== undefined) return;
        this.timer = window.setInterval(() => {
            this.waited += 50;
            if (this._bridge()) {
                window.clearInterval(this.timer);
                this.timer = undefined;
                const pending = this.queue;
                this.queue = [];
                for (const command of pending) this._invoke(command);
                return;
            }
            if (this.waited >= 15000 && !this.warned) {
                this.warned = true;
                window.clearInterval(this.timer);
                this.timer = undefined;
                // eslint-disable-next-line no-console
                console.error('[desk] 桥接 15 秒内未就绪：检查 '
                    + 'qwebchannel.js 是否与 desk.html 同目录');
            }
        }, 50);
    }
}

/** Browser shell: `LiveServer` in pylightcharts exposes POST /callback + SSE. */
export class SseTransport implements DeskTransport {
    readonly kind = 'sse';

    private source: EventSource | null = null;
    private ready = false;
    /** 命令先排队，等 SSE 建好再发 —— 否则 `ready` 可能早于 /events 注册，
     *  后端的 boot / chips / rows 补丁会全部丢掉（页面一直停在加载中 ✗）。 */
    private queue: DeskCommand[] = [];

    constructor(private readonly endpoint: string = '/callback',
                private readonly events: string = '/events',
                private readonly token: string = '') {
        this._connect();
    }

    get connected(): boolean {
        return this.ready;
    }

    send(command: DeskCommand): void {
        if (!this.ready) {
            this.queue.push(command);
            return;
        }
        this._post(command);
    }

    close(): void {
        if (this.source) {
            this.source.close();
            this.source = null;
        }
        this.ready = false;
    }

    private _post(command: DeskCommand): void {
        // keep-alive friendly, never blocks the UI
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        };
        if (this.token) headers['X-Desk-Token'] = this.token;
        void fetch(this.endpoint, {
            method: 'POST',
            headers,
            body: JSON.stringify(command),
        }).catch(() => undefined);
    }

    private _connect(): void {
        if (typeof EventSource === 'undefined') {
            // 老浏览器 / 非浏览器宿主：退化成“只发不收”，至少命令还能到后端
            this.ready = true;
            return;
        }
        let events = this.events;
        if (this.token) {
            const join = events.includes('?') ? '&' : '?';
            events += `${join}token=${encodeURIComponent(this.token)}`;
        }
        const source = new EventSource(events);
        this.source = source;
        source.onopen = () => {
            this.ready = true;
            const pending = this.queue;
            this.queue = [];
            for (const command of pending) this._post(command);
        };
        source.onmessage = (event) => this._apply(event.data);
        source.onerror = () => {
            // EventSource 会自动重连；重连期间先把命令攒着 ✓
            this.ready = false;
        };
    }

    /** 后端下发的是完整 JS 语句：`window.__desk.applyPatch({...});` */
    private _apply(script: string): void {
        try {
            // eslint-disable-next-line no-eval
            (0, eval)(String(script));
        } catch (error) {
            // eslint-disable-next-line no-console
            console.error('[desk] 补丁执行失败', error);
        }
    }
}

/** minibt-charts / any REST backend: override `send` or pass a URL. */
export class RestTransport implements DeskTransport {
    readonly kind = 'rest';
    readonly connected = true;

    constructor(private readonly endpoint: string,
                private readonly headers: Record<string, string> = {}) {}

    send(command: DeskCommand): void {
        void fetch(this.endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...this.headers },
            body: JSON.stringify(command),
        }).catch(() => undefined);
    }
}

/** No backend: records commands so tests / demos can assert on them. */
export class MockTransport implements DeskTransport {
    readonly kind = 'mock';
    readonly connected = false;
    readonly sent: DeskCommand[] = [];

    send(command: DeskCommand): void {
        this.sent.push(command);
    }

    /** test helper: get the payload of the last command with that name */
    last(cmd: string): DeskCommand | undefined {
        for (let i = this.sent.length - 1; i >= 0; i -= 1) {
            if (this.sent[i].cmd === cmd) return this.sent[i];
        }
        return undefined;
    }
}

export interface DeskBootstrap {
    /** `'qt' | 'sse' | 'rest' | 'mock'`; absent → auto-detect */
    transport?: string;
    /** REST endpoint (only used when transport === 'rest') */
    endpoint?: string;
    theme?: 'light' | 'dark';
    title?: string;
    /** browser shell：POST /events 的本地令牌（Qt 不用 ✓） */
    token?: string;
}

/**
 * Pick a transport from the host page.
 *
 *  - `window.__deskConfig` (written by the Python shell) wins;
 *  - QWebChannel ready (`window.pythonObject`) → Qt;
 *  - served over http(s) with a live server → Sse;
 *  - otherwise Mock (static preview / tests).
 */
export function detectTransport(config: DeskBootstrap = {}): DeskTransport {
    const wanted = (config.transport || '').toLowerCase();
    if (wanted === 'rest' && config.endpoint) {
        return new RestTransport(config.endpoint);
    }
    if (wanted === 'sse') return new SseTransport(config.endpoint || '/callback', '/events', config.token || '');
    if (wanted === 'mock') return new MockTransport();
    if (wanted === 'qt') return new QtTransport();
    if (typeof (window as any).pythonObject !== 'undefined') return new QtTransport();
    if (/^https?:$/.test(window.location.protocol)) return new SseTransport('/callback', '/events', config.token || '');
    // ★ file:// 只可能是 Qt 壳（desk.html）：QWebChannel 是**页面加载后**才注入的，
    //   这时 `pythonObject` 还不存在 —— 不能因此退回 Mock（那就永远发不出 ready ✗）。
    //   `QtTransport` 会排队等桥就绪，正好用在这里 ✓
    if (window.location.protocol === 'file:') return new QtTransport();
    return new MockTransport();
}
