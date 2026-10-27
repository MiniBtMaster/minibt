/**
 * Tabs — a horizontal group switcher for the composite panels (MarketData,
 * Watchlist, SymbolOverview). It is a plain DOM bar; the active key is reported
 * to Python through the bridge so the caller can swap the underlying data.
 */

import { emitCallback, ensureStyle } from './emit';

export interface TabItem {
    key: string;
    title: string;
}

export interface TabsTheme {
    background?: string;
    text?: string;
    muted?: string;
    activeText?: string;
    activeBackground?: string;
    hover?: string;
    border?: string;
    accent?: string;
}

export interface TabsOptions {
    items?: TabItem[];
    active?: string;
    theme?: TabsTheme;
    onChange?: (key: string) => void;
}

interface ResolvedTheme {
    background: string;
    text: string;
    muted: string;
    activeText: string;
    activeBackground: string;
    hover: string;
    border: string;
    accent: string;
}

const STYLE_ID = 'pylightcharts-tabs-style';
const CSS = `
.pylc-tabs{display:flex;align-items:center;gap:4px;padding:6px 8px;overflow-x:auto;
  background:var(--tb-bg);border-bottom:1px solid var(--tb-border);flex:0 0 auto;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,Arial,sans-serif}
.pylc-tabs::-webkit-scrollbar{height:0}
.pylc-tab{border:0;background:transparent;color:var(--tb-muted);font-size:12px;font-weight:500;
  padding:4px 10px;border-radius:4px;cursor:pointer;white-space:nowrap;font-family:inherit}
.pylc-tab:hover{background:var(--tb-hover);color:var(--tb-text)}
.pylc-tab.active{background:var(--tb-active-bg);color:var(--tb-active-text)}
`;

function defaultContainer(): HTMLElement {
    const host = window as unknown as { containerDiv?: HTMLElement };
    return host.containerDiv ?? document.body;
}

export class Tabs {
    public callbackName: string | null = null;
    public readonly element: HTMLDivElement;

    private _items: TabItem[] = [];
    private _active = '';
    private _theme: ResolvedTheme;
    private _onChange?: (key: string) => void;

    constructor(options: TabsOptions = {}, parent?: HTMLElement | null) {
        ensureStyle(STYLE_ID, CSS);
        this._theme = this._resolveTheme(options.theme ?? {});
        this.element = document.createElement('div');
        this.element.className = 'pylc-tabs';
        this._applyThemeVars();
        if (options.onChange) {
            this._onChange = options.onChange;
        }
        (parent ?? defaultContainer()).appendChild(this.element);
        if (options.items) {
            this.setTabs(options.items, options.active);
        }
    }

    setTabs(items: TabItem[], active?: string): void {
        this._items = items ?? [];
        if (active !== undefined) {
            this._active = active;
        } else if (!this._items.some((item) => item.key === this._active)) {
            this._active = this._items.length ? this._items[0].key : '';
        }
        this._render();
    }

    setActive(key: string): void {
        if (this._active === key) {
            return;
        }
        this._active = key;
        this._render();
    }

    getActive(): string {
        return this._active;
    }

    setTheme(theme: TabsTheme): void {
        this._theme = this._resolveTheme(theme);
        this._applyThemeVars();
    }

    reSize(): void {
        /* the bar is auto-sized; kept for API symmetry */
    }

    destroy(): void {
        this.element.remove();
    }

    private _resolveTheme(theme: TabsTheme): ResolvedTheme {
        return {
            background: theme.background ?? '#1e222d',
            text: theme.text ?? '#d1d4dc',
            muted: theme.muted ?? '#9aa0aa',
            activeText: theme.activeText ?? '#ffffff',
            activeBackground: theme.activeBackground ?? '#363a45',
            hover: theme.hover ?? '#2a2e39',
            border: theme.border ?? '#2a2e39',
            accent: theme.accent ?? '#2962ff',
        };
    }

    private _applyThemeVars(): void {
        const style = this.element.style;
        style.setProperty('--tb-bg', this._theme.background);
        style.setProperty('--tb-text', this._theme.text);
        style.setProperty('--tb-muted', this._theme.muted);
        style.setProperty('--tb-active-text', this._theme.activeText);
        style.setProperty('--tb-active-bg', this._theme.activeBackground);
        style.setProperty('--tb-hover', this._theme.hover);
        style.setProperty('--tb-border', this._theme.border);
    }

    private _render(): void {
        this.element.textContent = '';
        for (const item of this._items) {
            const button = document.createElement('button');
            button.className = 'pylc-tab' + (item.key === this._active ? ' active' : '');
            button.textContent = item.title;
            button.addEventListener('click', () => this._select(item.key));
            this.element.appendChild(button);
        }
    }

    private _select(key: string): void {
        if (key === this._active) {
            return;
        }
        this._active = key;
        this._render();
        if (this.callbackName) {
            emitCallback(this.callbackName, key);
        } else if (this._onChange) {
            this._onChange(key);
        }
    }
}
