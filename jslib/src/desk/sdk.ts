/**
 * minibt-charts SDK：把 desk 应用**嵌进任意页面**（一个函数搞定）。
 *
 * ```ts
 * import { mountDesk } from 'desk';       // 或 window.Desk.mount
 *
 * const desk = mountDesk({
 *     container: '#desk-host',            // 不传 → document.body
 *     transport: { kind: 'rest', endpoint: '/api/desk' },
 *     theme: 'dark',
 *     title: 'minibt桌面端',
 * });
 *
 * // 之后后端把补丁推给页面即可：
 * //   window.__desk.applyPatch({ type: 'rows', rows: [...] })
 *
 * desk.destroy();                          // 卸载
 * ```
 *
 * transport 三种写法：
 *  - `{ kind: 'rest', endpoint }`：自己后端（minibt-charts ✓）
 *  - `{ kind: 'sse', endpoint }`：pylightcharts `LiveServer`
 *  - 直接给一个 `DeskTransport` 实例（自定义）
 */
import { DeskApp, registerDesk } from './app';
import {
    RestTransport, SseTransport, type DeskBootstrap, type DeskTransport,
} from './transport';

export type TransportSpec =
    | DeskTransport
    | { kind: 'rest' | 'sse' | 'qt' | 'mock'; endpoint?: string };

export interface MountDeskOptions {
    /** CSS 选择器或元素（默认 `#desk` → 再退到 `document.body`） */
    container?: HTMLElement | string;
    /** 传输层（默认按页面协议自动选 ✓） */
    transport?: TransportSpec;
    theme?: 'light' | 'dark';
    title?: string;
    /** 额外的 `window.__deskConfig`（会合并进去 ✓） */
    config?: DeskBootstrap & Record<string, unknown>;
    /** 挂载后立刻发 `ready`（默认 true） */
    boot?: boolean;
}

export interface DeskHandle {
    app: DeskApp;
    destroy: () => void;
}

function resolveTransport(spec?: TransportSpec): DeskTransport | undefined {
    if (!spec) return undefined;
    if (typeof (spec as DeskTransport).send === 'function') {
        return spec as DeskTransport;
    }
    const value = spec as { kind: string; endpoint?: string };
    if (value.kind === 'rest' && value.endpoint) {
        return new RestTransport(value.endpoint);
    }
    if (value.kind === 'sse') {
        return new SseTransport(value.endpoint || '/callback');
    }
    return undefined;               // qt / mock：交给 auto-detect
}

function resolveContainer(target?: HTMLElement | string): HTMLElement {
    if (target && typeof target !== 'string') return target;
    if (typeof target === 'string') {
        const node = document.querySelector(target);
        if (node) return node as HTMLElement;
    }
    return document.getElementById('desk') || document.body;
}

/** 把一个 desk 应用挂到页面上（minibt-charts 用 ✓） */
export function mountDesk(options: MountDeskOptions = {}): DeskHandle {
    const config = {
        transport: 'rest',
        ...(options.config || {}),
        theme: options.theme || options.config?.theme || 'dark',
        title: options.title || options.config?.title || 'minibt桌面端',
    } as DeskBootstrap & Record<string, unknown>;
    (window as unknown as { __deskConfig?: unknown }).__deskConfig = config;

    const app = new DeskApp({
        theme: config.theme === 'light' ? 'light' : 'dark',
        title: String(config.title || 'minibt桌面端'),
        transport: resolveTransport(options.transport),
    });
    registerDesk(app);
    app.mount(resolveContainer(options.container));
    if (options.boot !== false) app.boot();

    return {
        app,
        destroy: () => {
            app.root.remove();
            if ((window as unknown as { __desk?: DeskApp }).__desk === app) {
                delete (window as unknown as { __desk?: DeskApp }).__desk;
            }
        },
    };
}
