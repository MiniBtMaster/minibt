/**
 * AlertDialog — 「创建预警」对话框（复刻 miniqt / TradingView 样式）。
 *
 * 由 Python 驱动（`Lib.AlertDialog`，见 `pylightcharts/panels/alert_dialog.py`）：
 *
 *     window.<id> = new Lib.AlertDialog({symbol, price, items: [...]})
 *     window.<id>.setItems(items)          // 已有预警列表（可删除）
 *     window.<id>.open() / close()
 *
 * 事件通过 `callbackName` 回报，载荷用 `;;;` 分隔：
 *
 *     'create;;;<json>'          创建（json: price/cross/expire/message/action/qty）
 *     'delete;;;<id>'            删除某条
 */
import { emitCallback, ensureStyle } from './emit';

export interface AlertItem {
    id: number | string;
    symbol?: string;
    price?: number | null;
    action?: string;
    qty?: number | null;
    message?: string;
    /** 是否在图表上画预警线（默认 true ✓） */
    line?: boolean;
    fired?: boolean;
    expires_at?: number | null;
}

export interface AlertDialogOptions {
    symbol?: string;
    price?: number | null;
    /** 合约小数位（后端由 `price_tick` 推 ✓） */
    decimals?: number | null;
    /** 穿越方向：穿过 / 上穿 / 下穿 */
    crosses?: string[];
    /** 到期时间：``[标签, 秒数]`` */
    expires?: Array<[string, number]>;
    /** 触发动作：无操作 / 买 / 卖 / 平 */
    actions?: string[];
    items?: AlertItem[];
    callbackName?: string | null;
    theme?: 'light' | 'dark';
}

const STYLE_ID = 'pylightcharts-alertdialog-style';

const CSS = `
.pylc-al-mask{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:12000;
  display:flex;align-items:center;justify-content:center}
.pylc-al{width:560px;max-height:86vh;overflow:auto;border-radius:10px;
  background:var(--al-bg);color:var(--al-text);border:1px solid var(--al-border);
  box-shadow:0 18px 48px rgba(0,0,0,.45);font-size:12.5px}
.pylc-al-head{display:flex;align-items:center;justify-content:space-between;
  padding:10px 14px;border-bottom:1px solid var(--al-border);font-size:14px;
  font-weight:600}
.pylc-al-close{border:none;background:transparent;color:var(--al-text);
  cursor:pointer;font-size:16px;line-height:1}
.pylc-al-body{padding:12px 14px;display:flex;flex-direction:column;gap:8px}
.pylc-al-row{display:flex;align-items:center;gap:8px}
.pylc-al-row > .k{flex:0 0 68px;color:var(--al-muted)}
.pylc-al-chip{height:26px;padding:0 10px;border-radius:6px;cursor:pointer;
  border:1px solid var(--al-border);background:transparent;color:var(--al-text);
  font-size:12px}
.pylc-al-chip.on{background:var(--al-accent);border-color:var(--al-accent);
  color:#fff}
.pylc-al-input{flex:1 1 auto;min-width:0;height:26px;padding:0 8px;border-radius:6px;
  border:1px solid var(--al-border);background:var(--al-input);color:var(--al-text);
  outline:none;font-size:12.5px}
.pylc-al-input:focus{border-color:var(--al-accent)}
.pylc-al-check{display:inline-flex;align-items:center;gap:6px;height:26px;
  padding:0 9px;border:1px solid var(--al-border);border-radius:6px;
  color:var(--al-text);cursor:pointer;font-size:12px;user-select:none}
.pylc-al-check input{accent-color:var(--al-accent);margin:0}
.pylc-al-hint{color:var(--al-muted);font-size:10.5px}
.pylc-al-list{border-top:1px solid var(--al-border);margin-top:4px;
  max-height:150px;overflow:auto}
.pylc-al-item{display:grid;grid-template-columns:1fr auto auto;gap:8px;
  align-items:center;padding:5px 2px;border-bottom:1px solid var(--al-border);
  font-size:12px}
.pylc-al-item .meta{color:var(--al-muted)}
.pylc-al-item.fired .meta{color:var(--al-accent)}
.pylc-al-foot{display:flex;justify-content:flex-end;gap:8px;
  padding:10px 14px;border-top:1px solid var(--al-border)}
.pylc-al-btn{height:28px;padding:0 14px;border-radius:6px;cursor:pointer;
  border:1px solid var(--al-border);background:transparent;color:var(--al-text);
  font-size:12.5px}
.pylc-al-btn.primary{background:var(--al-accent);border-color:var(--al-accent);
  color:#fff}
.pylc-al-empty{color:var(--al-muted);padding:8px 2px}
`;

const PALS = {
    dark: {
        bg: '#161a20', text: '#d8d9db', muted: '#8b93a1',
        border: '#262c36', input: '#0f1115', accent: '#2962ff',
    },
    light: {
        bg: '#ffffff', text: '#1f2329', muted: '#6b7280',
        border: '#e3e6ea', input: '#f6f7f9', accent: '#1a73e8',
    },
};

function esc(value: unknown): string {
    return String(value ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export class AlertDialog {
    public readonly element: HTMLDivElement;
    public callbackName: string | null = null;
    /** 直接回调（不经过 bridge —— desk 这类同页应用用 ✓） */
    public onCreateCallback: ((payload: Record<string, unknown>) => void) | null
        = null;
    public onDeleteCallback: ((id: unknown) => void) | null = null;

    private readonly body: HTMLDivElement;
    private readonly list: HTMLDivElement;
    private readonly priceInput: HTMLInputElement;
    private readonly messageInput: HTMLInputElement;
    private readonly qtyInput: HTMLInputElement;
    private cross = '穿过';
    private action = '无操作';
    private expire = 86400;
    /** 「预警线」默认开启（用户要求 ✓） */
    private lineEnabled = true;
    private items: AlertItem[] = [];
    private theme: 'light' | 'dark' = 'dark';

    constructor(private readonly options: AlertDialogOptions = {}) {
        ensureStyle(STYLE_ID, CSS);
        this.callbackName = options.callbackName || null;
        this.theme = options.theme === 'light' ? 'light' : 'dark';
        this.items = options.items || [];

        this.element = document.createElement('div');
        this.element.className = 'pylc-al-mask';
        this.element.style.display = 'none';

        const dialog = document.createElement('div');
        dialog.className = 'pylc-al';

        const head = document.createElement('div');
        head.className = 'pylc-al-head';
        head.innerHTML = `<span>预警 · ${esc(options.symbol || '')}</span>`;
        const close = document.createElement('button');
        close.className = 'pylc-al-close';
        close.textContent = '✕';
        close.title = '关闭';
        close.addEventListener('click', () => this.close());
        head.appendChild(close);

        this.body = document.createElement('div');
        this.body.className = 'pylc-al-body';

        // 价格 + 方向 + 数值
        const condRow = document.createElement('div');
        condRow.className = 'pylc-al-row';
        condRow.innerHTML = '<span class="k">条件</span>';
        this.priceInput = document.createElement('input');
        this.priceInput.className = 'pylc-al-input';
        this.priceInput.type = 'number';
        this.priceInput.step = 'any';
        this.priceInput.value = options.price == null ? ''
            : this._fmt(options.price);
        this.priceInput.title = '触发价格';
        condRow.append(this.priceInput);
        const crosses = options.crosses || ['穿过', '上穿', '下穿'];
        for (const cross of crosses) {
            const chip = document.createElement('button');
            chip.className = 'pylc-al-chip';
            chip.textContent = cross;
            if (cross === this.cross) chip.classList.add('on');
            chip.addEventListener('click', () => {
                this.cross = cross;
                condRow.querySelectorAll('.pylc-al-chip')
                    .forEach((n) => n.classList.remove('on'));
                chip.classList.add('on');
                this._syncMessage();
            });
            condRow.appendChild(chip);
        }

        // 到期 + 消息
        const expireRow = document.createElement('div');
        expireRow.className = 'pylc-al-row';
        expireRow.innerHTML = '<span class="k">到期时间</span>';
        const expireSelect = document.createElement('select');
        expireSelect.className = 'pylc-al-input';
        expireSelect.title = '到期时间（到时自动失效）';
        for (const [label, seconds] of (options.expires
            || [['1 小时后', 3600], ['1 天后', 86400],
                ['1 周后', 604800], ['无到期', 0]])) {
            const option = document.createElement('option');
            option.value = String(seconds);
            option.textContent = label;
            if (Number(seconds) === this.expire) option.selected = true;
            expireSelect.appendChild(option);
        }
        expireSelect.addEventListener('change', () => {
            this.expire = Number(expireSelect.value) || 0;
        });
        expireRow.appendChild(expireSelect);

        const messageRow = document.createElement('div');
        messageRow.className = 'pylc-al-row';
        messageRow.innerHTML = '<span class="k">消息</span>';
        this.messageInput = document.createElement('input');
        this.messageInput.className = 'pylc-al-input';
        this.messageInput.placeholder = '到价提醒内容（可留空）';
        this.messageInput.title = '触发时显示的提醒文字';
        messageRow.appendChild(this.messageInput);

        // 动作 + 手数
        const actionRow = document.createElement('div');
        actionRow.className = 'pylc-al-row';
        actionRow.innerHTML = '<span class="k">触发动作</span>';
        const actions = options.actions || ['无操作', '买', '卖', '平'];
        for (const action of actions) {
            const chip = document.createElement('button');
            chip.className = 'pylc-al-chip';
            chip.textContent = action;
            if (action === this.action) chip.classList.add('on');
            chip.title = action === '无操作' ? '只提醒，不下单'
                : `到价后询问是否「${action}」`;
            chip.addEventListener('click', () => {
                this.action = action;
                actionRow.querySelectorAll('.pylc-al-chip')
                    .forEach((n) => n.classList.remove('on'));
                chip.classList.add('on');
            });
            actionRow.appendChild(chip);
        }
        this.qtyInput = document.createElement('input');
        this.qtyInput.className = 'pylc-al-input';
        this.qtyInput.type = 'number';
        this.qtyInput.min = '1';
        this.qtyInput.value = '1';
        this.qtyInput.title = '触发后下单的手数';
        this.qtyInput.style.maxWidth = '70px';
        actionRow.appendChild(this.qtyInput);

        // 「预警线」：默认开启，开启时在对应图表左侧画一条价格线 ✓
        const lineRow = document.createElement('div');
        lineRow.className = 'pylc-al-row';
        lineRow.innerHTML = '<span class="k"></span>';
        const lineLabel = document.createElement('label');
        lineLabel.className = 'pylc-al-check';
        lineLabel.title = '在图表上画一条预警价格线（文字显示在左侧）';
        const lineCheck = document.createElement('input');
        lineCheck.type = 'checkbox';
        lineCheck.checked = this.lineEnabled;
        lineCheck.addEventListener('change', () => {
            this.lineEnabled = !!lineCheck.checked;
        });
        lineLabel.append(lineCheck, document.createTextNode('预警线'));
        const lineHint = document.createElement('span');
        lineHint.className = 'pylc-al-hint';
        lineHint.textContent = '在图表左侧显示价格线';
        lineRow.append(lineLabel, lineHint);

        const listTitle = document.createElement('div');
        listTitle.className = 'pylc-al-row';
        listTitle.innerHTML = '<span class="k">已有预警</span>';
        this.list = document.createElement('div');
        this.list.className = 'pylc-al-list';

        this.body.append(condRow, expireRow, messageRow, actionRow, lineRow,
                         listTitle, this.list);

        const foot = document.createElement('div');
        foot.className = 'pylc-al-foot';
        const cancel = document.createElement('button');
        cancel.className = 'pylc-al-btn';
        cancel.textContent = '取消';
        cancel.title = '关闭（不创建）';
        cancel.addEventListener('click', () => this.close());
        const create = document.createElement('button');
        create.className = 'pylc-al-btn primary';
        create.textContent = '创建';
        create.title = '创建这条价格预警';
        create.addEventListener('click', () => this._create());
        foot.append(cancel, create);

        dialog.append(head, this.body, foot);
        this.element.appendChild(dialog);
        this.element.addEventListener('mousedown', (event) => {
            if (event.target === this.element) this.close();
        });
        (document.body).appendChild(this.element);
        this.setTheme(this.theme);
        this.setItems(this.items);
        this._syncMessage();
    }

    // ------------------------------------------------------------- 显示
    open(): void {
        this.element.style.display = '';
        this.priceInput.focus();
        this.priceInput.select();
    }

    close(): void {
        this.element.style.display = 'none';
    }

    get visible(): boolean {
        return this.element.style.display !== 'none';
    }

    /** 换商品（Python 的 `open(symbol=…)` 用 ✓） */
    setSymbol(symbol: string): void {
        this.options.symbol = String(symbol || '');
        const title = this.element.querySelector('.pylc-al-head span');
        if (title) title.textContent = `预警 · ${this.options.symbol}`;
    }

    /** 换触发价 */
    /** 合约小数位（输入框 / 列表里的价格都按它显示 ✓） */
    setDecimals(decimals: number | null | undefined): void {
        const value = Number(decimals);
        if (!Number.isFinite(value) || value < 0) return;
        this.options.decimals = Math.min(6, Math.round(value));
    }

    private _fmt(price: number | null | undefined): string {
        const number = Number(price);
        if (price === null || price === undefined || !Number.isFinite(number)) {
            return '-';
        }
        const value = Number(this.options.decimals);
        const digits = Number.isFinite(value)
            ? Math.min(6, Math.max(0, value)) : 2;
        return number.toFixed(digits);
    }

    setPrice(price: number | null): void {
        if (price === null || price === undefined) return;
        this.options.price = Number(price);
        this.priceInput.value = this._fmt(price);
    }

    setItems(items: AlertItem[]): void {
        this.items = items || [];
        this.list.textContent = '';
        if (!this.items.length) {
            const empty = document.createElement('div');
            empty.className = 'pylc-al-empty';
            empty.textContent = '（还没有预警）';
            this.list.appendChild(empty);
            return;
        }
        for (const item of this.items) {
            const row = document.createElement('div');
            row.className = 'pylc-al-item' + (item.fired ? ' fired' : '');
            const meta = document.createElement('span');
            meta.className = 'meta';
            meta.textContent = `${item.fired ? '已触发' : '等待'} · `
                + `${this._fmt(item.price)} · ${item.action || '无操作'}`
                + (item.qty ? ` ${item.qty} 手` : '')
                + (item.message ? ` · ${item.message}` : '');
            const del = document.createElement('button');
            del.className = 'pylc-al-btn';
            del.textContent = '删除';
            del.title = '删除这条预警';
            del.addEventListener('click', () => {
                emitCallback(this.callbackName, `delete;;;${item.id}`);
                this.onDeleteCallback?.(item.id);
                this.setItems(this.items.filter((it) => it.id !== item.id));
            });
            row.append(meta, del, document.createElement('span'));
            this.list.appendChild(row);
        }
    }

    setTheme(theme: 'light' | 'dark'): void {
        this.theme = theme === 'light' ? 'light' : 'dark';
        const pal = PALS[this.theme];
        for (const [key, value] of Object.entries(pal)) {
            this.element.style.setProperty(`--al-${key}`, value);
        }
    }

    // ------------------------------------------------------------- 内部
    private _syncMessage(): void {
        if (!this.messageInput || this.messageInput.value) return;
        this.messageInput.placeholder =
            `${this.options.symbol || '商品'} ${this.cross} `
            + `${this.priceInput?.value || ''}`;
    }

    private _create(): void {
        const price = Number(this.priceInput.value);
        if (!Number.isFinite(price) || price <= 0) {
            this.priceInput.focus();
            return;
        }
        const payload = {
            price,
            cross: this.cross,
            expire: this.expire,
            message: this.messageInput.value.trim(),
            action: this.action,
            qty: Math.max(1, Number(this.qtyInput.value) || 1),
            line: !!this.lineEnabled,
        };
        emitCallback(this.callbackName, `create;;;${JSON.stringify(payload)}`);
        this.onCreateCallback?.(payload);
        this.close();
    }
}
