/**
 * KeyboardSprite — 键盘精灵（空格键）✓
 *
 * 复刻 miniqt 的键盘精灵：按**空格**弹出一个输入框，一个框里搜
 * **指标 / 策略 / 合约 / 股票**（后端 `sprite_search` 一起返回 ✓）。
 *
 * * `↑` / `↓` 选行，`Enter` 选中当前行（默认就是第一行 ✓），`Esc` 关掉；
 * * 双击某一行也等于选中它；
 * * 选中「指标 / 策略」→ **加到鼠标最后点击的那张图**；
 *   选中「合约 / 股票」→ **把那张图切到它**（＝切换 ✓）。
 */

export type SpriteKind = 'indicator' | 'strategy' | 'symbol';

export interface SpriteItem {
    kind: SpriteKind;
    key: string;
    label: string;
    name?: string;
    symbol?: string;
    group?: string;
}

const STYLE_ID = 'desk-sprite-style';

const CSS = `
.desk-sprite-mask {
    position: fixed;
    inset: 0;
    z-index: 900;
    background: rgba(0, 0, 0, .28);
}
.desk-sprite {
    position: fixed;
    z-index: 901;
    left: 50%;
    top: 16%;
    transform: translateX(-50%);
    width: 520px;
    max-width: 92vw;
    border-radius: 8px;
    border: 1px solid var(--desk-border, #2a3038);
    background: var(--desk-bg, #161a20);
    color: var(--desk-text, #d8d9db);
    box-shadow: 0 18px 48px rgba(0, 0, 0, .45);
    overflow: hidden;
    font-size: 12.5px;
}
.desk-sprite-input {
    width: 100%;
    box-sizing: border-box;
    border: 0;
    border-bottom: 1px solid var(--desk-border, #2a3038);
    background: transparent;
    color: inherit;
    padding: 10px 12px;
    font-size: 13.5px;
    outline: none;
}
.desk-sprite-list {
    max-height: 340px;
    overflow-y: auto;
    padding: 4px 0;
}
.desk-sprite-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 12px;
    cursor: pointer;
    user-select: none;
}
.desk-sprite-row.on { background: rgba(76, 141, 255, .22); }
.desk-sprite-badge {
    flex: 0 0 auto;
    min-width: 34px;
    text-align: center;
    padding: 0 4px;
    border-radius: 3px;
    font-size: 10px;
    line-height: 16px;
    color: #fff;
    opacity: .92;
}
.desk-sprite-badge.indicator { background: #4c8dff; }
.desk-sprite-badge.strategy { background: #9c27b0; }
.desk-sprite-badge.symbol { background: #26a69a; }
.desk-sprite-label { flex: 1 1 auto; overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap; }
.desk-sprite-group { flex: 0 0 auto; color: var(--desk-muted, #8b929c);
    font-size: 10.5px; }
.desk-sprite-empty { padding: 12px; color: var(--desk-muted, #8b929c); }
.desk-sprite-foot {
    padding: 4px 12px 6px;
    color: var(--desk-muted, #8b929c);
    font-size: 10.5px;
    border-top: 1px solid var(--desk-border, #2a3038);
}
`;

const BADGE: Record<SpriteKind, string> = {
    indicator: '指标',
    strategy: '策略',
    symbol: '合约',
};

export interface KeyboardSpriteOptions {
    theme?: 'dark' | 'light';
    /** 输入变化 → 发给后端搜（`sprite_search`）✓ */
    onQuery?: (text: string) => void;
    /** 选中一行（指标/策略 → 加；合约 → 切 ✓） */
    onPick: (item: SpriteItem) => void;
}

export class KeyboardSprite {
    private mask: HTMLDivElement | null = null;
    private box: HTMLDivElement | null = null;
    private input: HTMLInputElement | null = null;
    private list: HTMLDivElement | null = null;
    private foot: HTMLDivElement | null = null;
    private items: SpriteItem[] = [];
    private active = 0;
    private options: KeyboardSpriteOptions;

    constructor(options: KeyboardSpriteOptions) {
        this.options = options;
    }

    get opened(): boolean {
        return this.box !== null;
    }

    /** 打开（`text` = 输入的初始内容 ✓） */
    open(text = ''): void {
        this._ensureStyle();
        this.close();
        const mask = document.createElement('div');
        mask.className = 'desk-sprite-mask';
        const box = document.createElement('div');
        box.className = 'desk-sprite';
        if (this.options.theme === 'light') box.classList.add('light');
        const input = document.createElement('input');
        input.className = 'desk-sprite-input';
        input.placeholder = '指标 / 策略 / 合约 / 股票（回车选中第一行）';
        input.value = text;
        const list = document.createElement('div');
        list.className = 'desk-sprite-list';
        const foot = document.createElement('div');
        foot.className = 'desk-sprite-foot';
        foot.textContent = '↑↓ 选择 · Enter 确认 · Esc 关闭';
        box.append(input, list, foot);
        document.body.append(mask, box);
        this.mask = mask;
        this.box = box;
        this.input = input;
        this.list = list;
        this.foot = foot;
        this.items = [];
        this.active = 0;

        mask.addEventListener('mousedown', () => this.close());
        input.addEventListener('input', () => {
            this.options.onQuery?.(input.value.trim());
        });
        input.addEventListener('keydown', (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                event.preventDefault();
                this.close();
            } else if (event.key === 'ArrowDown') {
                event.preventDefault();
                this._move(1);
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                this._move(-1);
            } else if (event.key === 'Enter') {
                event.preventDefault();
                this._pick(this.active);
            }
        });
        input.focus();
        void this.input;                  // 保留引用（外部能取到输入框 ✓）
        this.options.onQuery?.(text.trim());
        this._render();
    }

    close(): void {
        this.mask?.remove();
        this.box?.remove();
        this.mask = null;
        this.box = null;
        this.input = null;
        this.list = null;
        this.foot = null;
        this.items = [];
    }

    /** 后端返回的搜索结果（`{type:'sprite'}` 补丁 ✓） */
    setResults(items: SpriteItem[], hint = ''): void {
        this.items = Array.isArray(items) ? items : [];
        this.active = 0;
        if (this.foot) {
            this.foot.textContent = hint
                || '↑↓ 选择 · Enter 确认 · Esc 关闭';
        }
        this._render();
    }

    private _move(step: number): void {
        if (!this.items.length) return;
        this.active = (this.active + step + this.items.length)
            % this.items.length;
        this._render();
    }

    private _pick(index: number): void {
        const item = this.items[index];
        if (!item) return;
        this.close();
        this.options.onPick(item);
    }

    private _render(): void {
        const list = this.list;
        if (!list) return;
        list.textContent = '';
        if (!this.items.length) {
            const empty = document.createElement('div');
            empty.className = 'desk-sprite-empty';
            empty.textContent = '没有匹配项';
            list.appendChild(empty);
            return;
        }
        this.items.forEach((item, index) => {
            const row = document.createElement('div');
            row.className = 'desk-sprite-row' + (index === this.active ? ' on' : '');
            const badge = document.createElement('span');
            badge.className = `desk-sprite-badge ${item.kind}`;
            badge.textContent = BADGE[item.kind] || item.kind;
            const label = document.createElement('span');
            label.className = 'desk-sprite-label';
            label.textContent = item.kind === 'symbol' && item.name
                ? `${item.label}  ${item.name}` : item.label;
            const group = document.createElement('span');
            group.className = 'desk-sprite-group';
            group.textContent = item.group || '';
            row.append(badge, label, group);
            row.addEventListener('mousedown', (event) => {
                event.preventDefault();
                this.active = index;
                this._pick(index);
            });
            row.addEventListener('dblclick', (event) => {
                event.preventDefault();
                this._pick(index);
            });
            list.appendChild(row);
        });
        const current = list.children[this.active] as HTMLElement | undefined;
        current?.scrollIntoView({ block: 'nearest' });
    }

    private _ensureStyle(): void {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = CSS;
        document.head.appendChild(style);
    }
}

/** 判断当前焦点是不是在输入框里（那样空格应该正常输入 ✓） */
export function isTypingTarget(target: EventTarget | null): boolean {
    const node = target as HTMLElement | null;
    if (!node) return false;
    const tag = String(node.tagName || '').toUpperCase();
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
    return !!node.isContentEditable;
}
