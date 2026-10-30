/**
 * Minimal DOM stub for the legend / legend-menu vitest cases.
 *
 * The project uses vitest's default `node` environment (no jsdom), and the
 * legend code builds real DOM nodes. This stub implements just the surface the
 * code touches (`createElement`, `appendChild`, `classList`, listeners,
 * `getBoundingClientRect`, …) plus `window.callbackFunction` capture.
 */

export type Listener = (event: any) => void;

export class StubElement {
    tagName: string;
    children: StubElement[] = [];
    style: Record<string, string> & {
        setProperty?: (name: string, value: string) => void } = {
        setProperty(this: Record<string, string>, name: string, value: string) {
            this[name] = value;
        },
    };
    className = '';
    private _innerHTML = '';
    private _text = '';
    title = '';
    type = '';
    value = '';
    readOnly = false;
    disabled = false;
    dataset: Record<string, string> = {};
    parentNode: StubElement | null = null;

    private _classes = new Set<string>();
    private _listeners: Record<string, Listener[]> = {};

    constructor(tag = 'div') {
        this.tagName = tag;
    }

    /** Assigning `innerHTML` clears children, like the real DOM does. */
    get innerHTML(): string { return this._innerHTML; }
    set innerHTML(value: string) {
        this._innerHTML = value;
        if (value === '') this.children = [];
    }

    /** Own text when set, otherwise concatenated children (like the DOM). */
    get textContent(): string {
        if (this._text) return this._text;
        return this.children.map((child) => child.textContent).join('');
    }
    set textContent(value: string) {
        this._text = value;
        if (value !== '') this.children = [];
    }

    classList = {
        add: (...names: string[]) => {
            for (const name of names) this._classes.add(name);
        },
        remove: (...names: string[]) => {
            for (const name of names) this._classes.delete(name);
        },
        contains: (name: string) => this._classes.has(name),
        toggle: (name: string, on?: boolean) => {
            const next = on === undefined ? !this._classes.has(name) : on;
            if (next) this._classes.add(name); else this._classes.delete(name);
            return next;
        },
    };

    /** `element.append(a, b, …)`（设置卡片里用的是 append ✓） */
    append(...nodes: StubElement[]): void {
        for (const node of nodes) this.appendChild(node);
    }

    appendChild(child: StubElement): StubElement {
        this.children.push(child);
        child.parentNode = this;
        return child;
    }

    /** `element.remove()`（设置卡片关掉时用 ✓） */
    remove(): void {
        this.parentNode?.removeChild(this);
    }

    removeChild(child: StubElement): StubElement {
        const index = this.children.indexOf(child);
        if (index >= 0) this.children.splice(index, 1);
        child.parentNode = null;
        return child;
    }

    addEventListener(name: string, fn: Listener): void {
        (this._listeners[name] ||= []).push(fn);
    }

    dispatch(name: string, event: any = {}): void {
        const event_ = { stopPropagation() {}, preventDefault() {}, ...event };
        for (const fn of this._listeners[name] || []) fn(event_);
    }

    click(): void { this.dispatch('click', {}); }

    getBoundingClientRect() {
        const left = Number(this.style.left?.replace('px', '')) || 0;
        const top = Number(this.style.top?.replace('px', '')) || 0;
        return { left, top, right: left + 100, bottom: top + 20,
                 width: 100, height: 20, x: left, y: top };
    }

    contains(node: any): boolean {
        if (node === this) return true;
        return this.children.some((child) => child.contains(node));
    }

    setAttribute(): void { /* no-op */ }
    querySelector(selector: string): StubElement | null {
        const name = String(selector || '').replace(/^\./, '');
        if (!name) return null;
        const walk = (node: StubElement): StubElement | null => {
            if ((node.className || '').split(/\s+/).includes(name)) return node;
            for (const child of node.children || []) {
                const hit = walk(child);
                if (hit) return hit;
            }
            return null;
        };
        for (const child of this.children || []) {
            const hit = walk(child);
            if (hit) return hit;
        }
        return null;
    }

    /** 按 class 找子节点（设置卡片的色块 / 按钮用例要用 ✓） */
    querySelectorAll(selector: string): StubElement[] {
        const name = selector.replace(/^\./, '');
        const out: StubElement[] = [];
        const walk = (node: StubElement) => {
            if (name && (node.className || '').split(/\s+/).includes(name)) {
                out.push(node);
            }
            for (const child of node.children || []) walk(child);
        };
        for (const child of this.children || []) walk(child);
        return out as never;
    }

    get offsetWidth(): number { return 120; }
    get offsetHeight(): number { return 200; }
    get clientWidth(): number { return 400; }
    get clientHeight(): number { return 400; }
}

export interface DomStub {
    body: StubElement;
    messages: string[];
    documentElement: { clientWidth: number; clientHeight: number };
}

/** Install the stub on `globalThis`; returns capture handles. */
export function installDom(): DomStub {
    const body = new StubElement('body');
    const messages: string[] = [];
    const documentElement = { clientWidth: 800, clientHeight: 600 };
    const doc = {
        createElement: (tag: string) => new StubElement(tag),
        createElementNS: (_ns: string, tag: string) => new StubElement(tag),
        getElementById: (_id: string) => null,
        head: new StubElement('head'),
        body,
        documentElement,
        addEventListener: () => { /* no-op */ },
    };
    (globalThis as any).document = doc;
    (globalThis as any).window = {
        callbackFunction: (message: string) => { messages.push(message); },
        innerWidth: 800,
        innerHeight: 600,
    };
    (globalThis as any).MutationObserver = class {
        observe() { /* no-op */ }
        disconnect() { /* no-op */ }
    };
    return { body, messages, documentElement };
}
