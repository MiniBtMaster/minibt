/** 全局命令面板（Ctrl/⌘ + P）：搜索页面 / 动作，回车执行。 */
import type { DeskTheme } from './theme';

export interface CommandItem {
    label: string;
    hint?: string;
    keywords?: string;
    run: () => void;
}

export class CommandPalette {
    public readonly element: HTMLDivElement;
    private readonly input: HTMLInputElement;
    private readonly list: HTMLDivElement;
    private readonly getCommands: () => CommandItem[];
    private items: CommandItem[] = [];
    private active = 0;
    private theme: DeskTheme;

    constructor(options: { theme: DeskTheme; commands: () => CommandItem[] }) {
        this.theme = options.theme;
        this.getCommands = options.commands;
        this.element = document.createElement('div');
        this.element.className = `desk-palette theme-${this.theme}`;
        this.element.style.display = 'none';
        this.element.innerHTML = `
            <div class="desk-palette-box">
                <input class="desk-palette-input" placeholder="输入页面 / 动作，↑↓ 选择，回车执行，Esc 关闭">
                <div class="desk-palette-list"></div>
                <div class="desk-palette-foot">
                    <span>Ctrl/⌘ + P</span><span>Esc 关闭</span>
                </div>
            </div>`;
        this.input = this.element.querySelector(
            '.desk-palette-input') as HTMLInputElement;
        this.list = this.element.querySelector(
            '.desk-palette-list') as HTMLDivElement;
        this.input.addEventListener('input', () => this.render());
        this.input.addEventListener('keydown', (event) => this.onKey(event));
        this.element.addEventListener('mousedown', (event) => {
            if (event.target === this.element) this.close();
        });
        this.list.addEventListener('click', (event) => {
            const row = (event.target as HTMLElement).closest<HTMLElement>(
                '[data-palette-index]');
            if (!row) return;
            const index = Number(row.dataset.paletteIndex || 0);
            this.run(index);
        });
    }

    applyTheme(theme: DeskTheme): void {
        this.theme = theme;
        this.element.className = `desk-palette theme-${theme}`;
    }

    get open_(): boolean { return this.element.style.display !== 'none'; }

    open(): void {
        this.items = this.getCommands();
        this.element.style.display = 'flex';
        this.input.value = '';
        this.active = 0;
        this.render();
        window.setTimeout(() => this.input.focus(), 0);
    }

    close(): void {
        this.element.style.display = 'none';
        this.input.value = '';
    }

    toggle(): void {
        if (this.open_) this.close();
        else this.open();
    }

    private filtered(): CommandItem[] {
        const text = this.input.value.trim().toLowerCase();
        if (!text) return this.items;
        return this.items.filter((item) => {
            const haystack = `${item.label} ${item.hint || ''} ${item.keywords || ''}`
                .toLowerCase();
            return text.split(/\s+/).every((part) => haystack.includes(part));
        });
    }

    private render(): void {
        const items = this.filtered();
        if (this.active >= items.length) this.active = Math.max(0, items.length - 1);
        this.list.innerHTML = items.length ? items.map((item, index) => `
            <div class="desk-palette-row${index === this.active ? ' on' : ''}" data-palette-index="${index}">
                <span>${this.escape(item.label)}</span>
                <span class="desk-muted">${this.escape(item.hint || '')}</span>
            </div>`).join('') : '<div class="desk-palette-empty">没有匹配的命令</div>';
        const row = this.list.querySelector('.desk-palette-row.on');
        row?.scrollIntoView({ block: 'nearest' });
    }

    private onKey(event: KeyboardEvent): void {
        const items = this.filtered();
        if (event.key === 'Escape') {
            event.preventDefault();
            this.close();
            return;
        }
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            this.active = items.length ? (this.active + 1) % items.length : 0;
            this.render();
            return;
        }
        if (event.key === 'ArrowUp') {
            event.preventDefault();
            this.active = items.length ? (this.active - 1 + items.length) % items.length : 0;
            this.render();
            return;
        }
        if (event.key === 'Enter') {
            event.preventDefault();
            this.run(this.active);
        }
    }

    private run(index: number): void {
        const items = this.filtered();
        const item = items[index];
        if (!item) return;
        this.close();
        item.run();
    }

    private escape(value: string): string {
        return value.replace(/[&<>"']/g, (ch) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[ch] as string));
    }
}
