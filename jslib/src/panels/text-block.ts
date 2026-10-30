/**
 * TextBlock — a styled, scrollable block of text/HTML.
 *
 * Used by the P3 shells (company profile description, notes, disclaimers). `text`
 * is set with `textContent` (safe); `html` is injected raw, so the host owns it.
 */

import { ensureStyle } from './emit';

export interface TextBlockTheme {
    background?: string;
    text?: string;
    muted?: string;
    border?: string;
    accent?: string;
}

export interface TextBlockOptions {
    text?: string;
    html?: string;
    title?: string;
    theme?: TextBlockTheme;
}

interface ResolvedTheme {
    background: string;
    text: string;
    muted: string;
    border: string;
    accent: string;
}

const STYLE_ID = 'pylightcharts-textblock-style';
const CSS = `
.pylc-text{width:100%;height:100%;overflow:auto;box-sizing:border-box;padding:10px 14px;
  background:var(--tx-bg);color:var(--tx-text);
  font:12.5px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,Arial,sans-serif}
.pylc-text h1,.pylc-text h2,.pylc-text h3{margin:.6em 0 .3em;color:var(--tx-text)}
.pylc-text p{margin:.4em 0}
.pylc-text a{color:var(--tx-accent);text-decoration:none}
.pylc-text a:hover{text-decoration:underline}
.pylc-text-title{font-size:14px;font-weight:700;margin-bottom:6px}
.pylc-text-muted{color:var(--tx-muted)}
.pylc-stack>.pylc-text{height:auto;flex:1 1 auto;min-height:0}
`;

function defaultContainer(): HTMLElement {
    const host = window as unknown as { containerDiv?: HTMLElement };
    return host.containerDiv ?? document.body;
}

export class TextBlock {
    public readonly element: HTMLDivElement;

    private _theme: ResolvedTheme;

    constructor(options: TextBlockOptions = {}, parent?: HTMLElement | null) {
        ensureStyle(STYLE_ID, CSS);
        this._theme = this._resolveTheme(options.theme ?? {});
        this.element = document.createElement('div');
        this.element.className = 'pylc-text';
        this._applyThemeVars();
        (parent ?? defaultContainer()).appendChild(this.element);
        if (options.title) {
            const title = document.createElement('div');
            title.className = 'pylc-text-title';
            title.textContent = options.title;
            this.element.appendChild(title);
        }
        if (options.html !== undefined) {
            this.setHtml(options.html);
        } else {
            this.setText(options.text ?? '');
        }
    }

    setText(text: string): void {
        this.element.textContent = text ?? '';
    }

    setHtml(html: string): void {
        this.element.innerHTML = html ?? '';
    }

    setOptions(options: Partial<TextBlockOptions>): void {
        if (options.theme) {
            this._theme = this._resolveTheme(options.theme);
            this._applyThemeVars();
        }
        if (options.html !== undefined) {
            this.setHtml(options.html);
        } else if (options.text !== undefined) {
            this.setText(options.text);
        }
    }

    destroy(): void {
        this.element.remove();
    }

    private _resolveTheme(theme: TextBlockTheme): ResolvedTheme {
        return {
            background: theme.background ?? '#131722',
            text: theme.text ?? '#d1d4dc',
            muted: theme.muted ?? '#787b86',
            border: theme.border ?? '#2a2e39',
            accent: theme.accent ?? '#2962ff',
        };
    }

    private _applyThemeVars(): void {
        const style = this.element.style;
        style.setProperty('--tx-bg', this._theme.background);
        style.setProperty('--tx-text', this._theme.text);
        style.setProperty('--tx-muted', this._theme.muted);
        style.setProperty('--tx-border', this._theme.border);
        style.setProperty('--tx-accent', this._theme.accent);
    }
}
