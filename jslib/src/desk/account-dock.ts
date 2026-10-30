/**
 * AccountDock — the bottom panel of a chart tab (miniqt `sim_account_panel.py`).
 *
 *   ┌ 交易账户 × │ 运行日志 × │ ＋                 [账户 ▾] ┐
 * ├ 静态权益 账户权益 持仓盈亏 … 资金使用率（11 张卡） ────┤
 * │ 持仓 | 委托 | 成交记录 | 未成委托       [平][反][全]    │
 * │ 表格（columns / rows，由后端预格式化）                  │
 * └──────────────────────────────────────────────────────┘
 *
 * 数据全由后端算好（`{type:'account', values, fields, tables, labels}`），
 * 这里只负责排版、子表切换、账户切换、日志。
 */
import { showMenu, type MenuItem } from './menu';

export interface AccountField {
    key: string;
    title: string;
    percent?: boolean;
}

export interface AccountTable {
    columns?: string[];
    rows?: unknown[][];
    total?: number;
    limit?: number;
}

export interface AccountPayload {
    type: 'account';
    empty?: boolean;
    kind?: string;
    index?: number;
    labels?: string[];
    values?: Record<string, number | null>;
    fields?: AccountField[];
    tables?: Record<string, AccountTable>;
}

export type DockTab = 'account' | 'log' | 'code';

const TABLE_ORDER: Array<[string, string]> = [
    ['positions', '持仓'], ['orders', '委托'],
    ['trades', '成交记录'], ['unfilled', '未成委托'],
];

const LOG_LIMIT = 500;

function money(value: unknown, digits = 2): string {
    const number = Number(value);
    if (value === null || value === undefined || !Number.isFinite(number)) {
        return '--';
    }
    return number.toLocaleString('en-US', {
        minimumFractionDigits: digits, maximumFractionDigits: digits,
    });
}

export class AccountDock {
    public readonly element: HTMLDivElement;
    /** 「最大化 / 恢复」按钮（最右 ✓） */
    private maximizeButton: HTMLButtonElement | null = null;
    /** 宿主想知道点了最大化（ChartPage 负责隐藏图表区 ✓） */
    public onToggleMaximize: (() => void) | null = null;
    /** 切到「代码」页签（第一次才建编辑器 ✓） */
    public onEditorOpen: (() => void) | null = null;
    /** 页签切换（宿主按需 show/hide 编辑器 ✓） */
    public onTabChange: ((tab: DockTab) => void) | null = null;
    /** CSV 导出交给宿主（Qt 里落盘到 `~/.minibt/exports/` ✓） */
    public onExport: ((filename: string, text: string) => boolean | void)
        | null = null;

    private readonly tabs: HTMLDivElement;
    private readonly accountPane: HTMLDivElement;
    private readonly logPane: HTMLDivElement;
    private readonly cards: HTMLDivElement;
    private readonly subTabs: HTMLDivElement;
    private readonly tableHost: HTMLDivElement;
    /** 本地图表：交易控件放这里（持仓/委托列表右侧 ✓） */
    private readonly ticketHost: HTMLDivElement;
    private readonly actions: HTMLDivElement;
    private readonly accountSelect: HTMLSelectElement;
    private readonly logList: HTMLDivElement;
    /** 「代码」页签容器（`EditorPanel` 挂进来 ✓） */
    public readonly editorPane: HTMLDivElement;

    private payload: AccountPayload = { type: 'account' };
    private activeTable = 'positions';
    private activeTab: DockTab = 'account';

    /** 当前页签（宿主判断要不要显示编辑器 ✓） */
    get currentTab(): DockTab {
        return this.activeTab;
    }
    private readonly buttons = new Map<string, HTMLButtonElement>();

    constructor(private readonly send: (cmd: string, payload?: unknown) => void) {
        this.element = document.createElement('div');
        this.element.className = 'desk-dock';

        // ---- tab strip -----------------------------------------------------
        this.tabs = document.createElement('div');
        this.tabs.className = 'desk-dock-tabs';
        // 顺序按用户要求：交易账户 / 编辑器 / 运行日志 ✓
        for (const [key, label] of [['account', '交易账户'],
                                    ['code', '编辑器'],
                                    ['log', '运行日志']] as const) {
            const tab = document.createElement('button');
            tab.className = 'desk-dock-tab';
            tab.textContent = label;
            tab.dataset.tab = key;
            tab.addEventListener('click', () => this.setTab(key));
            this.tabs.appendChild(tab);
            this.buttons.set(key, tab);
        }
        this.accountSelect = document.createElement('select');
        this.accountSelect.className = 'desk-dock-account';
        this.accountSelect.title = '切换交易账户（快期模拟 / 实盘）';
        this.accountSelect.addEventListener('change', () => {
            this.send('switch_account',
                      { index: Number(this.accountSelect.value) || 0 });
        });
        this.tabs.appendChild(this.accountSelect);
        // ★ 最右：最大化 / 恢复（初始「最大化」，点一下隐藏图表区 ✓）
        const spacer = document.createElement('span');
        spacer.style.flex = '1 1 auto';
        this.tabs.appendChild(spacer);
        const maximize = document.createElement('button');
        maximize.className = 'desk-dock-action desk-dock-maximize';
        maximize.textContent = '⤢';
        maximize.title = '最大化（隐藏图表，只看交易 / 编辑器）';
        maximize.addEventListener('click', () => this.onToggleMaximize?.());
        this.tabs.appendChild(maximize);
        this.maximizeButton = maximize;

        // ---- cards ---------------------------------------------------------
        this.cards = document.createElement('div');
        this.cards.className = 'desk-dock-cards';

        // ---- sub tabs + table ---------------------------------------------
        this.subTabs = document.createElement('div');
        this.subTabs.className = 'desk-dock-subtabs';
        for (const [key, label] of TABLE_ORDER) {
            const tab = document.createElement('button');
            tab.className = 'desk-dock-subtab';
            tab.textContent = label;
            tab.dataset.table = key;
            tab.addEventListener('click', () => this.setTable(key));
            this.subTabs.appendChild(tab);
        }
        // ★ 平 / 反 / 全 / 撤 已统一到右侧「交易」面板（用户要求 ✓）
        this.actions = document.createElement('div');
        this.actions.className = 'desk-dock-actions';
        this.subTabs.appendChild(this.actions);

        const exportButton = document.createElement('button');
        exportButton.className = 'desk-dock-action';
        exportButton.textContent = '导出 CSV';
        exportButton.addEventListener('click', () => this.exportCsv());
        this.actions.appendChild(exportButton);

        // ★ 面板默认右键菜单禁用（行内右键 → 我们自己的菜单 ✓）
        this.element.addEventListener('contextmenu', (event) => {
            event.preventDefault();
        });

        this.tableHost = document.createElement('div');
        this.tableHost.className = 'desk-dock-table';

        this.ticketHost = document.createElement('div');
        this.ticketHost.className = 'desk-dock-ticket';
        this.ticketHost.style.display = 'none';
        const tableRow = document.createElement('div');
        tableRow.className = 'desk-dock-tablerow';
        tableRow.append(this.tableHost, this.ticketHost);

        this.accountPane = document.createElement('div');
        this.accountPane.className = 'desk-dock-pane';
        this.accountPane.append(this.cards, this.subTabs, tableRow);

        // ---- log -----------------------------------------------------------
        const logBar = document.createElement('div');
        logBar.className = 'desk-dock-logbar';
        const filter = document.createElement('input');
        filter.className = 'desk-input desk-dock-logfilter';
        filter.placeholder = '过滤日志…';
        filter.addEventListener('input', () => this._filterLog(filter.value));
        const copy = document.createElement('button');
        copy.className = 'desk-dock-action';
        copy.textContent = '复制';
        copy.addEventListener('click', () => {
            void navigator.clipboard?.writeText(this.logList.innerText);
        });
        const clear = document.createElement('button');
        clear.className = 'desk-dock-action';
        clear.textContent = '清空';
        clear.addEventListener('click', () => { this.logList.textContent = ''; });
        logBar.append(filter, copy, clear);
        this.logList = document.createElement('div');
        this.logList.className = 'desk-dock-log';
        this.logPane = document.createElement('div');
        this.logPane.className = 'desk-dock-pane';
        this.logPane.append(logBar, this.logList);

        this.editorPane = document.createElement('div');
        this.editorPane.className = 'desk-dock-pane desk-dock-editor';
        this.editorPane.style.display = 'none';
        this.editorPane.style.padding = '0';
        this.element.append(this.tabs, this.accountPane, this.logPane,
                            this.editorPane);
        this.setTab('account');
        this.setTable('positions');
    }

    /** 最大化状态 → 图标在「最大化 ⤢ / 恢复 ⤡」之间切换 ✓ */
    setMaximized(maximized: boolean): void {
        const button = this.maximizeButton;
        if (!button) return;
        button.textContent = maximized ? '⤡' : '⤢';
        button.title = maximized
            ? '恢复（回到上次图表 / 面板的比例）'
            : '最大化（隐藏图表，只看交易 / 编辑器）';
        button.classList.toggle('on', maximized);
    }

    // ------------------------------------------------------------ tabs
    setTab(tab: DockTab): void {
        this.activeTab = tab;
        for (const [key, button] of this.buttons) {
            button.classList.toggle('on', key === tab);
        }
        this.accountPane.style.display = tab === 'account' ? '' : 'none';
        this.logPane.style.display = tab === 'log' ? '' : 'none';
        this.editorPane.style.display = tab === 'code' ? '' : 'none';
        this.accountSelect.style.display = tab === 'account' ? '' : 'none';
        if (tab === 'account') this.send('account', {});
        if (tab === 'code') this.onEditorOpen?.();
        this.onTabChange?.(tab);
    }

    setTable(table: string): void {
        this.activeTable = table;
        this.subTabs.querySelectorAll<HTMLElement>('.desk-dock-subtab')
            .forEach((node) => {
                node.classList.toggle('on', node.dataset.table === table);
            });
        // 动作按钮已搬到右侧「交易」面板 → 这里只切表 ✓
        this._renderTable();
    }

    // ------------------------------------------------------------ data
    setAccount(payload: AccountPayload): void {
        this.payload = payload || { type: 'account' };
        this._renderCards();
        this._renderAccounts();
        this._renderTable();
    }

    /** 把自定义交易控件放进「交易账户」页（列表右侧；不传 = 移除）✓ */
    setTicket(element: HTMLElement | null): void {
        this.ticketHost.textContent = '';
        if (element) {
            this.ticketHost.appendChild(element);
            this.ticketHost.style.display = '';
        } else {
            this.ticketHost.style.display = 'none';
        }
    }

    appendLog(text: string, level = 'info', ts = ''): void {
        const line = document.createElement('div');
        line.className = `desk-log-line ${level}`;
        line.textContent = `${ts ? `[${ts}] ` : ''}${text}`;
        this.logList.appendChild(line);
        while (this.logList.childElementCount > LOG_LIMIT) {
            this.logList.firstElementChild?.remove();
        }
        this.logList.scrollTop = this.logList.scrollHeight;
    }

    // ------------------------------------------------------------ render
    private _renderCards(): void {
        const values = this.payload.values || {};
        const fields = this.payload.fields || [];
        this.cards.textContent = '';
        for (const field of fields) {
            const raw = values[field.key];
            const card = document.createElement('div');
            card.className = 'desk-dock-card';
            const number = Number(raw);
            const colored = ['position_profit', 'close_profit', 'float_profit']
                .includes(field.key) && Number.isFinite(number) && number !== 0;
            const cls = colored ? (number > 0 ? 'up' : 'down') : '';
            const text = raw === null || raw === undefined
                ? '--'
                : (field.percent
                    ? `${(number * 100).toFixed(2)}%`
                    : money(number));
            card.innerHTML = `<span class="k">${field.title}</span>`
                + `<b class="${cls}">${text}</b>`;
            this.cards.appendChild(card);
        }
    }

    private _renderAccounts(): void {
        const labels = this.payload.labels || [];
        this.accountSelect.textContent = '';
        labels.forEach((label, index) => {
            const option = document.createElement('option');
            option.value = String(index);
            option.textContent = label;
            this.accountSelect.appendChild(option);
        });
        this.accountSelect.selectedIndex = Number(this.payload.index || 0);
        // 只有一个账户就淡化（miniqt 里是隐藏 ✓）
        this.accountSelect.style.display = labels.length > 1 ? '' : 'none';
    }

    private _renderTable(): void {
        const table = (this.payload.tables || {})[this.activeTable] || {};
        const columns = table.columns || [];
        const rows = table.rows || [];
        this.tableHost.textContent = '';
        if (!columns.length) {
            const empty = document.createElement('div');
            empty.className = 'desk-dock-empty';
            empty.textContent = '（暂无数据）';
            this.tableHost.appendChild(empty);
            return;
        }
        const head = document.createElement('div');
        head.className = 'desk-dock-tr head';
        head.style.gridTemplateColumns = `repeat(${columns.length}, minmax(0, 1fr))`;
        head.innerHTML = columns.map((column) => `<span>${column}</span>`).join('');
        const body = document.createElement('div');
        body.className = 'desk-dock-tbody';
        if (!rows.length) {
            // ★ 有列但 0 行：显示“暂无数据”，不要只留表头 ✗
            const empty = document.createElement('div');
            empty.className = 'desk-dock-empty';
            empty.textContent = '（暂无数据）';
            body.appendChild(empty);
            this.tableHost.append(head, body);
            return;
        }
        const raw = (table as unknown as { raw?: Array<Record<string, unknown>> })
            .raw || [];
        rows.forEach((row, index) => {
            const line = document.createElement('div');
            line.className = 'desk-dock-tr';
            line.dataset.index = String(index);
            if (index === this.selectedRow) line.classList.add('on');
            line.style.gridTemplateColumns =
                `repeat(${columns.length}, minmax(0, 1fr))`;
            line.innerHTML = row.map((cell) => {
                const text = String(cell ?? '');
                const cls = text.startsWith('+') ? 'up'
                    : (text.startsWith('-') ? 'down' : '');
                return `<span class="${cls}">${text}</span>`;
            }).join('');
            // ★ 行可选中（左键）/ 右键菜单（持仓：平反全；委托：撤全 ✓）
            line.addEventListener('click', () => {
                this.selectedRow = index;
                body.querySelectorAll('.desk-dock-tr').forEach((node) => {
                    node.classList.remove('on');
                });
                line.classList.add('on');
            });
            line.addEventListener('contextmenu', (event) => {
                event.preventDefault();
                this.selectedRow = index;
                body.querySelectorAll('.desk-dock-tr').forEach((node) => {
                    node.classList.remove('on');
                });
                line.classList.add('on');
                this._openRowMenu(event, raw[index] || {}, index);
            });
            body.appendChild(line);
        });
        this.tableHost.append(head, body);
    }

    /** 当前选中的行（切表重置 ✓） */
    private selectedRow = -1;

    /** 行右键菜单（持仓 → 平 / 反 / 全；委托 → 撤 / 全 ✓） */
    private _openRowMenu(event: MouseEvent, raw: Record<string, unknown>,
                         index: number): void {
        const table = this.activeTable;
        const symbol = String(raw.symbol || '');
        const volume = Number(raw.volume) || 0;
        const items: MenuItem[] = [];
        if (table === 'positions') {
            items.push({
                label: `平（市价平 ${symbol || '该合约'}）`,
                run: () => this.send('position_action', {
                    action: 'close', symbol, volume,
                }),
            }, {
                label: `反（市价平 ${volume || ''} 手后反向开）`,
                run: () => this.send('position_action', {
                    action: 'reverse', symbol, volume,
                }),
            }, {
                label: '全（市价平掉全部持仓）',
                separator: true,
                run: () => this.send('position_action', { action: 'all' }),
            });
        } else {
            const alive = raw.alive !== false;
            const orderId = String(raw.order_id || '');
            items.push({
                label: '撤（撤掉这笔委托）',
                disabled: !alive || !orderId,
                run: () => this.send('order_action', {
                    action: 'cancel', symbol, order_id: orderId,
                }),
            }, {
                label: '全（撤掉所有未成交委托）',
                separator: true,
                run: () => this.send('order_action', {
                    action: 'cancel_all', symbol,
                }),
            });
        }
        void index;
        showMenu(Math.round(event.clientX), Math.round(event.clientY), items);
    }

    /**
     * 当前子表 → CSV（浏览器直接下载；Qt 里同样可用 ✓）
     *
     * 价格列已经是**按合约小数位**预格式化的字符串（后端 `_money(x, decimals)`），
     * 这里再兜一层：万一某格是**数字**，按表格的 `decimals`（若有）格式化，
     * 保证导出的 CSV 和界面上看到的位数一致 ✓
     */
    exportCsv(): void {
        const table = (this.payload.tables || {})[this.activeTable] || {};
        const columns = table.columns || [];
        const rows = table.rows || [];
        if (!columns.length) {
            this.send('toast_local', { text: '当前表没有数据' });
            return;
        }
        const digits = Number((table as unknown as { decimals?: number })
            .decimals);
        const places = Number.isFinite(digits)
            ? Math.max(0, Math.min(6, Math.round(digits))) : 2;
        // 数字 → 固定小数位；"3,600" 这种**带千分位的字符串**去掉逗号
        // （Excel 会把 `"3,600"` 当文本，二次计算就废了 ✗）
        const cellText = (cell: unknown): string => {
            if (typeof cell === 'number' && Number.isFinite(cell)) {
                return cell.toFixed(places);
            }
            const text = String(cell ?? '');
            return /^-?\d{1,3}(,\d{3})+(\.\d+)?$/.test(text)
                ? text.replace(/,/g, '') : text;
        };
        const escape = (value: unknown) => {
            const text = cellText(value);
            const needs = text.includes('"') || text.includes(',')
                || text.includes('\n');
            return needs ? `"${text.replace(/"/g, '""')}"` : text;
        };
        const lines = [columns.map(escape).join(',')];
        for (const row of rows) lines.push(row.map(escape).join(','));
        const stamp = new Date().toISOString().replace(/[:T]/g, '-').slice(0, 19);
        const name = `${this.activeTable}_${stamp}.csv`;
        if (this.onExport && this.onExport(name, lines.join('\n'))) return;
        const blob = new Blob(['\ufeff' + lines.join('\n')],
            { type: 'text/csv;charset=utf-8' });
        const link = document.createElement('a');
        link.download = name;
        link.href = URL.createObjectURL(blob);
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    }

    private _filterLog(text: string): void {
        const needle = text.trim().toLowerCase();
        this.logList.querySelectorAll<HTMLElement>('.desk-log-line')
            .forEach((line) => {
                line.style.display = !needle
                    || line.textContent!.toLowerCase().includes(needle)
                    ? '' : 'none';
            });
    }

    get tab(): DockTab {
        return this.activeTab;
    }
}
