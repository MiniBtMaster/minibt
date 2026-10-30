/**
 * 扩展功能页：交易工作台 / 策略研究 / 数据平台 / 运维。
 *
 * 这些页面只负责「收集参数 + 显示后端补丁」，不直接下单 / 跑回测：
 * 所有动作都通过 `onCommand(cmd, payload)` 回到 Python。
 */
import type { DeskTheme } from './theme';

function esc(value: unknown): string {
    return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[ch] as string));
}

function num(value: unknown, digits = 2): string {
    if (value === null || value === undefined || value === '') return '—';
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return '—';
    return parsed.toLocaleString(undefined, {
        minimumFractionDigits: 0, maximumFractionDigits: digits,
    });
}

function stabilityScore(summary: Record<string, any>, direction = 1): number | null {
    const mean = Number(summary?.mean);
    if (!Number.isFinite(mean)) return null;
    const std = Number(summary?.std) || 0;
    const rate = Number(summary?.positive_rate) || 0;
    const dir = direction === -1 ? -1 : 1;
    const score = 50 + mean * 100 * dir - std * 80 + (rate - 0.5) * 40;
    return Math.max(0, Math.min(100, score));
}

function when(value: unknown): string {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed <= 0) return '—';
    const date = new Date(parsed * 1000);
    return date.toLocaleString(undefined, { hour12: false });
}

function table(headers: string[], rows: string[][], empty = '暂无数据'): string {
    if (!rows.length) return `<div class="desk-suite-empty">${esc(empty)}</div>`;
    return `<table class="desk-suite-table"><thead><tr>${
        headers.map((item) => `<th>${esc(item)}</th>`).join('')
    }</tr></thead><tbody>${rows.map((row) => `<tr>${
        row.map((cell) => `<td>${cell}</td>`).join('')
    }</tr>`).join('')}</tbody></table>`;
}

const STATUS_TEXT: Record<string, string> = {
    PENDING: '已提交', ALIVE: '挂单中', PARTIAL: '部分成交',
    FINISHED: '已成交', CANCELLED: '已撤单', REJECTED: '已拒绝',
    ARMED: '条件待触发', TRIGGERED: '已触发',
};

function stateBadge(status: unknown): string {
    const key = String(status || '').toUpperCase();
    const cls = key === 'REJECTED' ? 'bad' : (
        key === 'FINISHED' ? 'good' : (
            key === 'CANCELLED' ? 'muted' : 'live'));
    return `<span class="desk-suite-state ${cls}">${
        esc(STATUS_TEXT[key] || key || '—')}</span>`;
}

function shell(kind: string, theme: DeskTheme, title: string,
               subtitle: string, body: string): HTMLDivElement {
    const element = document.createElement('div');
    element.className = `desk-suite-page desk-suite-${kind} theme-${theme}`;
    element.innerHTML = `
        <div class="desk-suite-head">
            <div><h2>${esc(title)}</h2><p class="desk-muted">${esc(subtitle)}</p></div>
            <div class="desk-suite-actions" data-suite-actions></div>
        </div>
        ${body}`;
    return element;
}

interface PageOptions {
    theme: DeskTheme;
    onCommand: (cmd: string, payload?: unknown) => void;
}

// ================================================================ 交易工作台
export class WorkbenchPage {
    public readonly element: HTMLDivElement;
    private readonly options: PageOptions;
    private theme: DeskTheme;

    constructor(options: PageOptions) {
        this.options = options;
        this.theme = options.theme;
        this.element = shell('workbench', this.theme, '交易工作台',
            '订单票 / 条件单 / 风控 / 对账 / 审计。所有下单仍然走 desk 的同一个交易执行器。',
            this.skeleton());
        this.element.addEventListener('click', (event) => {
            this.onClick(event);
        });
        this.element.addEventListener('change', (event) => {
            const target = event.target as HTMLElement;
            if (target.closest('[data-wb="orderType"]')) this.syncType();
        });
    }

    show(): void { this.element.style.display = 'block'; }
    hide(): void { this.element.style.display = 'none'; }
    applyTheme(theme: DeskTheme): void {
        this.theme = theme;
        this.element.className = `desk-suite-page desk-suite-workbench theme-${theme}`;
    }

    private skeleton(): string {
        return `
        <div class="desk-suite-grid">
            <section class="desk-suite-card">
                <h3>订单票</h3>
                <div class="desk-suite-form">
                    <label>合约<input data-wb="symbol" placeholder="SHFE.ag2612"></label>
                    <label>方向<select data-wb="side">
                        <option value="buy">买入 / 开多</option>
                        <option value="sell">卖出 / 开空</option>
                        <option value="close">平仓</option>
                    </select></label>
                    <label>类型<select data-wb="orderType">
                        <option value="market">市价</option>
                        <option value="limit">限价</option>
                        <option value="stop">止损（触发市价）</option>
                        <option value="conditional">条件单</option>
                    </select></label>
                    <label>价格<input data-wb="price" type="number" step="0.01" placeholder="限价 / 触发后限价"></label>
                    <label>触发价<input data-wb="trigger" type="number" step="0.01" placeholder="止损 / 条件单"></label>
                    <label>条件<select data-wb="condition">
                        <option value=">=">价格 ≥ 触发</option>
                        <option value="<=">价格 ≤ 触发</option>
                        <option value="cross_up">上穿</option>
                        <option value="cross_down">下穿</option>
                    </select></label>
                    <label>数量<input data-wb="volume" type="number" min="1" value="1"></label>
                    <label>TIF<select data-wb="tif">
                        <option value="GFD">GFD（当日有效）</option>
                        <option value="IOC">IOC（立即成交否则撤）</option>
                        <option value="FOK">FOK（全部成交否则撤）</option>
                    </select></label>
                    <label class="wide">备注<input data-wb="note" placeholder="可选"></label>
                </div>
                <div class="desk-suite-buttons">
                    <button class="desk-tool primary" data-wb-submit>下单</button>
                    <button class="desk-tool" data-wb-reconcile>对账</button>
                    <button class="desk-tool" data-wb-export-orders>导出委托</button>
                    <button class="desk-tool" data-wb-export-audit>导出审计</button>
                    <button class="desk-tool danger" data-wb-cancel-all>全撤</button>
                </div>
                <div class="desk-suite-hint" id="wb-note"></div>
            </section>
            <section class="desk-suite-card">
                <h3>风控</h3>
                <div class="desk-suite-form">
                    <label class="inline"><input type="checkbox" data-wb="riskEnabled"> 启用风控</label>
                    <label>单笔最多（手/股）<input data-wb="maxVolume" type="number" min="0"></label>
                    <label>单笔最大金额<input data-wb="maxNotional" type="number" min="0"></label>
                    <label>单日最多委托<input data-wb="maxOrders" type="number" min="0"></label>
                    <label>单日最大亏损<input data-wb="maxLoss" type="number" min="0"></label>
                    <label>净持仓上限<input data-wb="maxPosition" type="number" min="0"></label>
                    <label class="inline"><input type="checkbox" data-wb="allowShort" checked> 允许开空</label>
                </div>
                <div class="desk-suite-buttons">
                    <button class="desk-tool primary" data-wb-save-limits>保存风控</button>
                </div>
                <div class="desk-suite-kv" id="wb-stats"></div>
            </section>
        </div>
        <section class="desk-suite-card">
            <h3>委托流水 <span class="desk-muted" id="wb-count"></span></h3>
            <div id="wb-orders"></div>
        </section>
        <div class="desk-suite-grid">
            <section class="desk-suite-card">
                <h3>条件单</h3>
                <div id="wb-conditional"></div>
            </section>
            <section class="desk-suite-card">
                <h3>对账</h3>
                <div id="wb-reconcile"></div>
            </section>
        </div>
        <section class="desk-suite-card">
            <h3>审计日志</h3>
            <div id="wb-audit"></div>
        </section>`;
    }

    private input(name: string): HTMLInputElement | HTMLSelectElement | null {
        return this.element.querySelector(
            `[data-wb="${name}"]`) as HTMLInputElement | HTMLSelectElement | null;
    }

    private value(name: string): string {
        return String(this.input(name)?.value ?? '').trim();
    }

    private checked(name: string): boolean {
        return !!(this.input(name) as HTMLInputElement | null)?.checked;
    }

    private syncType(): void {
        const type = this.value('orderType');
        const price = this.input('price');
        const trigger = this.input('trigger');
        if (price) price.disabled = type === 'market';
        if (trigger) trigger.disabled = !(type === 'stop' || type === 'conditional');
    }

    private onClick(event: MouseEvent): void {
        const target = event.target as HTMLElement;
        const click = (selector: string) => !!target.closest(selector);
        if (click('[data-wb-reconcile]')) {
            this.options.onCommand('workbench_reconcile', {});
            return;
        }
        if (click('[data-wb-export-orders]')) {
            this.options.onCommand('workbench_export', { table: 'orders' });
            return;
        }
        if (click('[data-wb-export-audit]')) {
            this.options.onCommand('workbench_export', { table: 'audit' });
            return;
        }
        if (click('[data-wb-cancel-all]')) {
            if (!window.confirm('确定撤销全部未成交委托？')) return;
            this.options.onCommand('workbench_cancel',
                { all: true, symbol: this.value('symbol') });
            return;
        }
        if (click('[data-wb-save-limits]')) {
            this.options.onCommand('workbench_limits', {
                enabled: this.checked('riskEnabled'),
                max_volume: Number(this.value('maxVolume') || 0),
                max_notional: Number(this.value('maxNotional') || 0),
                max_orders_per_day: Number(this.value('maxOrders') || 0),
                max_daily_loss: Number(this.value('maxLoss') || 0),
                max_position: Number(this.value('maxPosition') || 0),
                allow_short: this.checked('allowShort'),
            });
            return;
        }
        if (click('[data-wb-submit]')) {
            const type = this.value('orderType');
            const payload: Record<string, unknown> = {
                symbol: this.value('symbol'), side: this.value('side'),
                volume: Number(this.value('volume') || 1),
                order_type: type, tif: this.value('tif'),
                note: this.value('note'),
            };
            if (type !== 'market') payload.price = Number(this.value('price') || 0) || null;
            if (type === 'stop' || type === 'conditional') {
                payload.trigger_price = Number(this.value('trigger') || 0) || null;
                payload.condition = this.value('condition');
            }
            if (!String(payload.symbol || '')) {
                window.alert('请先填合约');
                return;
            }
            this.options.onCommand('workbench_submit', payload);
            return;
        }
        const cancel = target.closest<HTMLElement>('[data-wb-cancel]');
        if (cancel) {
            this.options.onCommand('workbench_cancel', {
                order_id: cancel.dataset.orderId || '',
                symbol: cancel.dataset.symbol || '',
                id: Number(cancel.dataset.localId || 0),
            });
            return;
        }
        const modify = target.closest<HTMLElement>('[data-wb-modify]');
        if (modify) {
            const price = window.prompt('新的限价', modify.dataset.price || '');
            if (!price) return;
            this.options.onCommand('workbench_modify', {
                order_id: modify.dataset.orderId || '',
                symbol: modify.dataset.symbol || '',
                id: Number(modify.dataset.localId || 0),
                side: modify.dataset.side || 'buy',
                volume: Number(modify.dataset.volume || 1),
                price: Number(price),
            });
            return;
        }
        const cond = target.closest<HTMLElement>('[data-wb-cond-cancel]');
        if (cond) {
            this.options.onCommand('workbench_conditional_cancel',
                { id: cond.dataset.id || '' });
        }
    }

    apply(patch: Record<string, any>): void {
        if (patch.type !== 'workbench') return;
        const stats = patch.stats || {};
        const account = String(patch.account || '—');
        const statsBox = this.element.querySelector('#wb-stats');
        if (statsBox) {
            statsBox.innerHTML = `
                <span>账户 <b>${esc(account)}</b></span>
                <span>委托 <b>${esc(stats.orders ?? 0)}</b></span>
                <span>未完成 <b>${esc(stats.open ?? 0)}</b></span>
                <span>失败 <b>${esc(stats.failed ?? 0)}</b></span>
                <span>当日盈亏 <b>${num(stats.daily_pnl, 2)}</b></span>
                <span>交易 <b>${patch.enabled ? '已启用' : '未启用'}</b>${
                    patch.real ? ' · <b class="warn">实盘</b>' : ''}</span>`;
        }
        const limits = patch.limits || {};
        const setValue = (name: string, value: unknown) => {
            const input = this.input(name);
            if (input) input.value = value === null || value === undefined
                ? '' : String(value);
        };
        const enabled = this.input('riskEnabled') as HTMLInputElement | null;
        if (enabled) enabled.checked = !!limits.enabled;
        const allowShort = this.input('allowShort') as HTMLInputElement | null;
        if (allowShort) allowShort.checked = limits.allow_short !== false;
        setValue('maxVolume', limits.max_volume ?? '');
        setValue('maxNotional', limits.max_notional ?? '');
        setValue('maxOrders', limits.max_orders_per_day ?? '');
        setValue('maxLoss', limits.max_daily_loss ?? '');
        setValue('maxPosition', limits.max_position ?? '');
        this.syncType();

        const orders = (patch.orders || []) as Array<Record<string, any>>;
        const orderRows = orders.map((row) => {
            const open = ['PENDING', 'ALIVE', 'PARTIAL'].includes(
                String(row.status || ''));
            const actions = open ? `
                <button class="desk-suite-link" data-wb-cancel data-order-id="${esc(row.order_id || '')}" data-symbol="${esc(row.symbol || '')}" data-local-id="${esc(row.id || '')}">撤</button>
                <button class="desk-suite-link" data-wb-modify data-order-id="${esc(row.order_id || '')}" data-symbol="${esc(row.symbol || '')}" data-side="${esc(row.side || 'buy')}" data-volume="${esc(row.volume || 1)}" data-local-id="${esc(row.id || '')}" data-price="${esc(row.price || '')}">改</button>`
                : '';
            return [
                `<span class="desk-muted">${when(row.ts)}</span>`,
                esc(row.symbol || ''), esc(row.side || ''),
                esc(row.volume ?? ''), row.price ? num(row.price, 4) : '市价',
                esc(row.order_type || ''), stateBadge(row.status),
                `<span class="desk-suite-cell">${esc(row.text || '')}</span>`,
                actions,
            ];
        });
        const ordersBox = this.element.querySelector('#wb-orders');
        if (ordersBox) {
            ordersBox.innerHTML = table(
                ['时间', '合约', '方向', '数量', '价格', '类型', '状态', '说明', '操作'],
                orderRows, '还没有委托');
        }
        const count = this.element.querySelector('#wb-count');
        if (count) count.textContent = orders.length ? `（${orders.length}）` : '';

        const conditional = (patch.conditional || []) as Array<Record<string, any>>;
        const condBox = this.element.querySelector('#wb-conditional');
        if (condBox) {
            condBox.innerHTML = table(['合约', '方向', '数量', '条件', '触发价', '状态', ''],
                conditional.map((row) => [
                    esc(row.symbol || ''), esc(row.side || ''),
                    esc(row.volume ?? ''), esc(row.condition || ''),
                    num(row.trigger_price, 4), stateBadge(row.status || 'ARMED'),
                    `<button class="desk-suite-link" data-wb-cond-cancel data-id="${esc(row.id || '')}">撤销</button>`,
                ]), '没有条件单');
        }

        const recon = patch.reconcile || {};
        const reconBox = this.element.querySelector('#wb-reconcile');
        if (reconBox) {
            const missing = (recon.missing || []) as Array<Record<string, any>>;
            const extra = (recon.extra || []) as Array<Record<string, any>>;
            reconBox.innerHTML = recon.at ? `
                <div class="desk-suite-kv">
                    <span>本地未完成 <b>${esc(recon.local_open ?? 0)}</b></span>
                    <span>券商未成交 <b>${esc(recon.broker_open ?? 0)}</b></span>
                    <span>差异 <b>${missing.length + extra.length}</b></span>
                </div>
                ${table(['差异', '合约', '委托号'], [
                    ...missing.map((row) => ['本地有 / 券商无',
                        esc(row.symbol || ''), esc(row.order_id || '')]),
                    ...extra.map((row) => ['券商有 / 本地无',
                        esc(row.symbol || ''), esc(row.order_id || '')]),
                ], '本地与券商一致')}
                ${(recon.errors || []).length
                    ? `<div class="desk-suite-hint warn">${esc((recon.errors || []).join('；'))}</div>` : ''}`
                : '<div class="desk-suite-empty">还没有对账。点「对账」比较本地流水与券商未成交委托。</div>';
        }

        const audit = (patch.audit || []) as Array<Record<string, any>>;
        const auditBox = this.element.querySelector('#wb-audit');
        if (auditBox) {
            auditBox.innerHTML = table(['时间', '类型', '合约', '方向', '数量', '价格', '状态', '说明'],
                audit.map((row) => [
                    `<span class="desk-muted">${when(row.ts)}</span>`,
                    esc(row.kind || ''), esc(row.symbol || ''),
                    esc(row.side || ''), esc(row.volume ?? ''),
                    row.price === null || row.price === undefined ? '' : num(row.price, 4),
                    stateBadge(row.status || ''), esc(row.text || ''),
                ]), '还没有审计记录');
        }
    }
}

// ================================================================ 研究平台
export class ResearchPage {
    public readonly element: HTMLDivElement;
    private readonly options: PageOptions;
    private theme: DeskTheme;
    private data: Record<string, any> = {};
    private selected = 0;

    constructor(options: PageOptions) {
        this.options = options;
        this.theme = options.theme;
        this.element = shell('research', this.theme, '策略研究平台',
            'Walk-forward / 批量回测 / 参数网格；结果自动写进实验库，可导出 Markdown + CSV。',
            this.skeleton());
        this.element.addEventListener('click', (event) => {
            this.onClick(event);
        });
        this.element.addEventListener('change', (event) => {
            const target = event.target as HTMLElement;
            if (target.closest('[data-rs="heatMetric"]')) this.renderHeatmap();
        });
    }

    show(): void { this.element.style.display = 'block'; }
    hide(): void { this.element.style.display = 'none'; }
    applyTheme(theme: DeskTheme): void {
        this.theme = theme;
        this.element.className = `desk-suite-page desk-suite-research theme-${theme}`;
    }

    private skeleton(): string {
        return `
        <section class="desk-suite-card">
            <h3>新实验</h3>
            <div class="desk-suite-form">
                <label>模式<select data-rs="mode">
                    <option value="walk_forward">Walk-forward（滚动训练/测试）</option>
                    <option value="batch">批量回测（多数据文件）</option>
                    <option value="grid">参数网格</option>
                </select></label>
                <label>策略文件<input data-rs="file" placeholder="C:/.../my_strategy.py"></label>
                <label class="wide">数据文件（LocalDatas 名 / CSV 路径）
                    <input data-rs="data" list="rs-data-names"
                           placeholder="留空 = 按策略里的 LocalDatas 自动识别；如 test / l2609_60">
                    <datalist id="rs-data-names"></datalist>
                </label>
                <label>训练根数<input data-rs="train" type="number" value="240"></label>
                <label>测试根数<input data-rs="test" type="number" value="60"></label>
                <label>步长<input data-rs="step" type="number" value="60"></label>
                <label>实验名<input data-rs="name" placeholder="可选"></label>
                <label>指标 1<select data-rs="metric0"></select></label>
                <label>指标 2<select data-rs="metric1"><option value="">（不使用）</option></select></label>
                <label>指标 3<select data-rs="metric2"><option value="">（不使用）</option></select></label>
                <label class="wide">参数（JSON）<textarea data-rs="params" rows="3" placeholder='{"length":[10,20],"std":[1,2]}'></textarea></label>
            </div>
            <div class="desk-suite-buttons">
                <button class="desk-tool primary" data-rs-run>开始</button>
                <button class="desk-tool" data-rs-cancel>取消</button>
                <button class="desk-tool" data-rs-refresh>刷新实验库</button>
            </div>
            <div class="desk-suite-hint" id="rs-status"></div>
        </section>
        <div class="desk-suite-grid">
            <section class="desk-suite-card">
                <h3>稳定性摘要</h3>
                <div id="rs-summary"></div>
            </section>
            <section class="desk-suite-card">
                <h3>Pareto 前沿</h3>
                <div id="rs-pareto"></div>
            </section>
        </div>
        <section class="desk-suite-card">
            <h3>参数热力图
                <select data-rs="heatMetric" class="desk-suite-inline-select"></select>
                <span class="desk-muted" id="rs-heat-title"></span></h3>
            <div id="rs-heatmap"></div>
        </section>
        <section class="desk-suite-card">
            <h3>窗口 / Trial</h3>
            <div id="rs-windows"></div>
        </section>
        <section class="desk-suite-card">
            <h3>实验库</h3>
            <div id="rs-experiments"></div>
        </section>`;
    }

    private input(name: string): HTMLInputElement | HTMLSelectElement
        | HTMLTextAreaElement | null {
        return this.element.querySelector(
            `[data-rs="${name}"]`) as HTMLInputElement | HTMLSelectElement
            | HTMLTextAreaElement | null;
    }

    private value(name: string): string {
        return String(this.input(name)?.value ?? '').trim();
    }

    private onClick(event: MouseEvent): void {
        const target = event.target as HTMLElement;
        if (target.closest('[data-rs-run]')) {
            let params: Record<string, unknown> = {};
            const raw = this.value('params');
            if (raw) {
                try {
                    params = JSON.parse(raw);
                } catch {
                    window.alert('参数不是合法 JSON');
                    return;
                }
            }
            const metrics = ['metric0', 'metric1', 'metric2']
                .map((name) => this.value(name))
                .filter((name, index, all) => !!name && all.indexOf(name) === index)
                .slice(0, 3);
            this.options.onCommand('research_start', {
                mode: this.value('mode'), file: this.value('file'),
                data: this.value('data'), train: Number(this.value('train') || 240),
                test: Number(this.value('test') || 60),
                step: Number(this.value('step') || 0),
                metrics, metric: metrics[0] || 'profit_ratio',
                name: this.value('name'), params,
            });
            return;
        }
        if (target.closest('[data-rs-cancel]')) {
            this.options.onCommand('research_cancel', {});
            return;
        }
        if (target.closest('[data-rs-refresh]')) {
            this.options.onCommand('research', {});
            return;
        }
        const report = target.closest<HTMLElement>('[data-rs-report]');
        if (report) {
            this.options.onCommand('research_report', {
                experiment: Number(report.dataset.rsReport || 0),
            });
            return;
        }
        const drop = target.closest<HTMLElement>('[data-rs-delete]');
        if (drop) {
            if (!window.confirm('删除这个实验（含 trials）？')) return;
            this.options.onCommand('research_delete', {
                experiment: Number(drop.dataset.rsDelete || 0),
            });
            return;
        }
        const row = target.closest<HTMLElement>('[data-rs-select]');
        if (row) {
            this.selected = Number(row.dataset.rsSelect || 0);
            this.renderExperiments();
        }
    }

    apply(patch: Record<string, any>): void {
        if (patch.type === 'research_state' || patch.type === 'research') {
            const status = String(patch.status || this.data.status || 'idle');
            const statusBox = this.element.querySelector('#rs-status');
            if (statusBox) {
                const error = String(patch.error || this.data.error || '');
                statusBox.innerHTML = status === 'running'
                    ? `运行中… ${esc(this.data.progress_text || '')}`
                    : (error ? `<span class="warn">${esc(error)}</span>`
                        : `状态：${esc(status)}`);
            }
            if (patch.result) this.data.result = patch.result;
            if (patch.experiments) this.data.experiments = patch.experiments;
            if (patch.metrics) this.data.metricOptions = patch.metrics;
            if (patch.metric_directions) {
                this.data.metricDirections = patch.metric_directions;
            }
            if (patch.data_names) this.data.dataNames = patch.data_names;
            if (patch.status) this.data.status = patch.status;
            if (patch.error !== undefined) this.data.error = patch.error;
            this.fillSelectors();
            this.renderAll();
            return;
        }
        if (patch.type === 'research_progress') {
            this.data.progress_text = `${patch.current}/${patch.total} ${patch.text || ''}`;
            const statusBox = this.element.querySelector('#rs-status');
            if (statusBox) {
                statusBox.textContent = `运行中… ${this.data.progress_text}`;
            }
            return;
        }
        if (patch.type === 'research_error') {
            this.data.error = patch.message;
            const statusBox = this.element.querySelector('#rs-status');
            if (statusBox) {
                statusBox.innerHTML = `<span class="warn">${esc(patch.message)}</span>`;
            }
            return;
        }
        if (patch.type === 'research_result') {
            this.data.result = patch;
            this.data.status = 'ready';
            this.fillSelectors();
            this.renderAll();
        }
    }

    private fillSelectors(): void {
        const options = (this.data.metricOptions || []) as string[];
        if (options.length) {
            const previous = ['metric0', 'metric1', 'metric2'].map(
                (name) => this.value(name));
            ['metric0', 'metric1', 'metric2'].forEach((name, index) => {
                const select = this.input(name) as HTMLSelectElement | null;
                if (!select) return;
                const blank = index === 0 ? '' : '<option value="">（不使用）</option>';
                const chosen = previous[index] || (index === 0 ? 'profit_ratio' : '');
                select.innerHTML = blank + options.map((item) =>
                    `<option value="${esc(item)}">${esc(item)}</option>`).join('');
                select.value = options.includes(chosen) ? chosen
                    : (index === 0 ? (options.includes('profit_ratio')
                        ? 'profit_ratio' : options[0]) : '');
            });
        }
        const names = (this.data.dataNames || []) as string[];
        const list = this.element.querySelector('#rs-data-names');
        if (list) {
            list.innerHTML = names.map((name) =>
                `<option value="${esc(name)}"></option>`).join('');
        }
        const result = this.data.result || {};
        const heatOptions = (result.metrics || options) as string[];
        const heatSelect = this.input('heatMetric') as HTMLSelectElement | null;
        if (heatSelect && heatOptions.length) {
            const chosen = heatSelect.value || result.metric || heatOptions[0];
            heatSelect.innerHTML = heatOptions.map((item) =>
                `<option value="${esc(item)}">${esc(item)}</option>`).join('');
            heatSelect.value = heatOptions.includes(chosen) ? chosen : heatOptions[0];
        }
    }

    private renderHeatmap(): void {
        const result = this.data.result || {};
        const select = this.input('heatMetric') as HTMLSelectElement | null;
        const metric = select?.value || result.metric || 'profit_ratio';
        const heat = ((result.heatmaps || {}) as Record<string, any>)[metric]
            || result.heatmap || {};
        const title = this.element.querySelector('#rs-heat-title');
        if (title) {
            title.textContent = heat.x ? `${heat.x} × ${heat.y}` : '';
        }
        const heatBox = this.element.querySelector('#rs-heatmap');
        if (!heatBox) return;
        const xs = (heat.x_values || []) as string[];
        const ys = (heat.y_values || []) as string[];
        const grid = (heat.grid || []) as Array<Array<number | null>>;
        heatBox.innerHTML = xs.length && ys.length ? `
            <table class="desk-suite-table heatmap">
                <thead><tr><th>${esc(heat.y || '')} | ${esc(heat.x || '')}</th>${
                    xs.map((x) => `<th>${esc(x)}</th>`).join('')}</tr></thead>
                <tbody>${ys.map((y, yi) => `<tr><th>${esc(y)}</th>${
                    xs.map((_x, xi) => {
                        const value = grid[yi]?.[xi];
                        if (value === null || value === undefined) {
                            return '<td class="muted">—</td>';
                        }
                        const ratio = Math.max(-1, Math.min(1, value * 5));
                        const color = ratio >= 0
                            ? `rgba(38,166,154,${0.15 + ratio * 0.55})`
                            : `rgba(239,83,80,${0.15 + (-ratio) * 0.55})`;
                        return `<td style="background:${color}">${num(value, 4)}</td>`;
                    }).join('')}</tr>`).join('')}</tbody>
            </table>` : '<div class="desk-suite-empty">参数网格 / Walk-forward 结果会显示在这里。</div>';
    }

    private renderAll(): void {
        const result = this.data.result || {};
        const summaries = (result.summaries || (
            result.summary ? { [result.metric || 'profit_ratio']: result.summary } : {}
        )) as Record<string, Record<string, any>>;
        const directions = (this.data.metricDirections || {}) as Record<string, number>;
        const summaryBox = this.element.querySelector('#rs-summary');
        if (summaryBox) {
            const rows = Object.keys(summaries).map((name) => {
                const item = summaries[name] || {};
                const dir = directions[name] === -1 ? '越小越好' : '越大越好';
                return [
                    esc(name), `<span class="desk-muted">${dir}</span>`,
                    esc(item.count ?? 0), num(item.mean, 4), num(item.std, 4),
                    `${num((item.positive_rate || 0) * 100, 1)}%`,
                    num(item.worst, 4), num(item.best, 4),
                    num(stabilityScore(item, directions[name]), 1),
                ];
            });
            summaryBox.innerHTML = rows.length ? `
                <div class="desk-suite-kv">
                    <span>总稳定性 <b>${num(result.score, 1)}</b></span>
                    <span>指标 <b>${esc((result.metrics || []).join(' / '))}</b></span>
                </div>
                ${table(['指标', '方向', '样本', '均值', '标准差', '胜率', '最差', '最好', '稳定性'],
                    rows, '还没有结果')}`
                : '<div class="desk-suite-empty">跑一次 walk-forward / 网格就会出现。</div>';
        }
        const paretoBox = this.element.querySelector('#rs-pareto');
        if (paretoBox) {
            const rows = (result.pareto || []) as Array<Record<string, any>>;
            paretoBox.innerHTML = table(['#', '参数 / 窗口', '目标'],
                rows.map((row, index) => [
                    String(index + 1),
                    esc(JSON.stringify(row.params || row.name || row.window || {})),
                    esc(JSON.stringify(row._objectives || row.metrics || {})),
                ]), '没有可比较的结果');
        }
        this.renderHeatmap();
        const windows = (result.windows || result.grid_rows
            || result.batch_rows || []) as Array<Record<string, any>>;
        const winBox = this.element.querySelector('#rs-windows');
        if (winBox) {
            winBox.innerHTML = table(['#', '训练 / 数据', '测试 / 参数', '指标'],
                windows.map((row, index) => [
                    String(index + 1), esc(row.train || row.name || ''),
                    esc(row.test || JSON.stringify(row.params || {})),
                    esc(JSON.stringify(row.metrics || {})),
                ]), '还没有窗口结果');
        }
        this.renderExperiments();
    }

    private renderExperiments(): void {
        const experiments = (this.data.experiments || []) as Array<Record<string, any>>;
        const box = this.element.querySelector('#rs-experiments');
        if (!box) return;
        box.innerHTML = table(['ID', '名称', '模式', '分数', '创建', '操作'],
            experiments.map((row) => {
                const id = Number(row.id || 0);
                return [
                    `<button class="desk-suite-link" data-rs-select="${id}">#${id}</button>`,
                    esc(row.name || ''), esc(row.mode || ''),
                    num(row.score, 1), `<span class="desk-muted">${when(row.created)}</span>`,
                    `<button class="desk-suite-link" data-rs-report="${id}">报告</button>
                     <button class="desk-suite-link" data-rs-delete="${id}">删除</button>`,
                ];
            }), '实验库还是空的');
        if (this.selected) {
            const hit = experiments.find((row) => Number(row.id) === this.selected);
            if (hit && hit.windows) {
                const winBox = this.element.querySelector('#rs-windows');
                if (winBox) {
                    winBox.innerHTML = table(['#', '训练 / 数据', '测试 / 参数', '指标'],
                        (hit.windows as Array<Record<string, any>>).map((row, index) => [
                            String(index + 1), esc(row.train || row.name || ''),
                            esc(row.test || JSON.stringify(row.params || {})),
                            esc(JSON.stringify(row.metrics || {})),
                        ]), '这个实验没有窗口明细');
                }
            }
        }
    }
}

// ================================================================ 数据平台
export class DataPage {
    public readonly element: HTMLDivElement;
    private readonly options: PageOptions;
    private theme: DeskTheme;

    constructor(options: PageOptions) {
        this.options = options;
        this.theme = options.theme;
        this.element = shell('data', this.theme, '本地数据平台',
            'CSV / Parquet 行情库：质检、重采样、主力换月复权、Tick 聚合、只读 SQL。',
            this.skeleton());
        this.element.addEventListener('click', (event) => {
            this.onClick(event);
        });
    }

    show(): void { this.element.style.display = 'block'; }
    hide(): void { this.element.style.display = 'none'; }
    applyTheme(theme: DeskTheme): void {
        this.theme = theme;
        this.element.className = `desk-suite-page desk-suite-data theme-${theme}`;
    }

    private skeleton(): string {
        return `
        <section class="desk-suite-card">
            <div class="desk-suite-buttons">
                <button class="desk-tool primary" data-dh-refresh>扫描数据目录</button>
                <input data-dh="folder" class="desk-suite-input" placeholder="额外目录（可选）">
                <span class="desk-muted" id="dh-engine"></span>
            </div>
            <div id="dh-items"></div>
        </section>
        <div class="desk-suite-grid">
            <section class="desk-suite-card">
                <h3>质检 / 重采样 / Tick</h3>
                <div class="desk-suite-form">
                    <label>数据 name<input data-dh="name" placeholder="从上面选一个 name"></label>
                    <label>周期 rule<input data-dh="rule" value="5min"></label>
                    <label>Tick 秒数<input data-dh="seconds" type="number" value="60"></label>
                </div>
                <div class="desk-suite-buttons">
                    <button class="desk-tool" data-dh-quality>数据质检</button>
                    <button class="desk-tool" data-dh-resample>重采样</button>
                    <button class="desk-tool" data-dh-ticks>Tick → K 线</button>
                    <button class="desk-tool" data-dh-export>导出 Parquet</button>
                </div>
                <div id="dh-quality"></div>
                <div id="dh-result"></div>
            </section>
            <section class="desk-suite-card">
                <h3>主力换月 / 复权</h3>
                <div class="desk-suite-form">
                    <label class="wide">合约 names<input data-dh="names" placeholder="rb2610, rb2701（按时间拼接）"></label>
                    <label>复权<select data-dh="mode">
                        <option value="ratio">比例</option>
                        <option value="difference">价差</option>
                        <option value="none">不复权</option>
                    </select></label>
                </div>
                <div class="desk-suite-buttons">
                    <button class="desk-tool primary" data-dh-roll>拼接连续合约</button>
                </div>
                <div id="dh-roll-result"></div>
            </section>
        </div>
        <section class="desk-suite-card">
            <h3>只读 SQL（DuckDB）</h3>
            <textarea data-dh="sql" rows="4" class="desk-suite-sql">SELECT * FROM ag2612_60 LIMIT 20</textarea>
            <div class="desk-suite-buttons">
                <button class="desk-tool primary" data-dh-query>执行 SELECT</button>
                <span class="desk-muted">只允许 SELECT / WITH；直接查文件名（非字母数字换成 _）</span>
            </div>
            <div id="dh-query"></div>
        </section>`;
    }

    private input(name: string): HTMLInputElement | HTMLSelectElement
        | HTMLTextAreaElement | null {
        return this.element.querySelector(
            `[data-dh="${name}"]`) as HTMLInputElement | HTMLSelectElement
            | HTMLTextAreaElement | null;
    }

    private value(name: string): string {
        return String(this.input(name)?.value ?? '').trim();
    }

    private onClick(event: MouseEvent): void {
        const target = event.target as HTMLElement;
        if (target.closest('[data-dh-refresh]')) {
            this.options.onCommand('datahub_refresh',
                { folder: this.value('folder') });
            return;
        }
        if (target.closest('[data-dh-quality]')) {
            this.options.onCommand('datahub_quality', { name: this.value('name') });
            return;
        }
        if (target.closest('[data-dh-resample]')) {
            this.options.onCommand('datahub_resample',
                { name: this.value('name'), rule: this.value('rule') });
            return;
        }
        if (target.closest('[data-dh-ticks]')) {
            this.options.onCommand('datahub_ticks', {
                name: this.value('name'),
                seconds: Number(this.value('seconds') || 60),
            });
            return;
        }
        if (target.closest('[data-dh-roll]')) {
            this.options.onCommand('datahub_roll', {
                names: this.value('names'), mode: this.value('mode'),
            });
            return;
        }
        if (target.closest('[data-dh-export]')) {
            this.options.onCommand('datahub_export', { name: this.value('name') });
            return;
        }
        if (target.closest('[data-dh-query]')) {
            this.options.onCommand('datahub_query', { sql: this.value('sql') });
            return;
        }
        const pick = target.closest<HTMLElement>('[data-dh-pick]');
        if (pick) {
            const name = pick.dataset.dhPick || '';
            const input = this.input('name') as HTMLInputElement | null;
            if (input) input.value = name;
            this.options.onCommand('datahub_quality', { name });
            return;
        }
    }

    apply(patch: Record<string, any>): void {
        const type = String(patch.type || '');
        if (type === 'datahub') {
            const engine = this.element.querySelector('#dh-engine');
            if (engine) {
                engine.textContent = patch.duckdb
                    ? `DuckDB 已启用 · ${(patch.items || []).length} 个文件`
                    : `未安装 DuckDB（CSV/Parquet 仍可用）· ${(patch.items || []).length} 个文件`;
            }
            const items = (patch.items || []) as Array<Record<string, any>>;
            const box = this.element.querySelector('#dh-items');
            if (box) {
                box.innerHTML = table(['名称', '格式', '行数', '区间', '大小', ''],
                    items.map((row) => [
                        `<button class="desk-suite-link" data-dh-pick="${esc(row.name)}">${esc(row.name)}</button>`,
                        esc(row.format || ''),
                        row.error ? `<span class="warn">${esc(row.error)}</span>`
                            : num(row.rows, 0),
                        `<span class="desk-muted">${esc(row.from || '')}${
                            row.to ? ' → ' + esc(row.to) : ''}</span>`,
                        row.size ? `${(Number(row.size) / 1024).toFixed(0)} KB` : '',
                        esc(row.path || ''),
                    ]), '没有扫描到数据文件');
            }
            return;
        }
        if (type === 'datahub_quality') {
            const report = patch.report || {};
            const box = this.element.querySelector('#dh-quality');
            if (box) {
                box.innerHTML = `
                    <div class="desk-suite-kv">
                        <span>文件 <b>${esc(patch.name || '')}</b></span>
                        <span>分数 <b>${num(report.score, 1)}</b></span>
                        <span>行数 <b>${num(report.rows, 0)}</b></span>
                        <span>状态 <b>${report.ok ? '通过' : '有错误'}</b></span>
                    </div>
                    ${table(['级别', '问题', '数量', '说明'],
                        (report.issues || []).map((row: any) => [
                            esc(row.level || ''), esc(row.kind || ''),
                            esc(row.count ?? ''), esc(row.detail || ''),
                        ]), '没有发现问题')}`;
            }
            return;
        }
        if (type === 'datahub_result') {
            const bars = (patch.bars || []) as Array<Record<string, any>>;
            const first = bars[0] || {};
            const last = bars[bars.length - 1] || {};
            const box = this.element.querySelector(
                patch.action === 'roll' ? '#dh-roll-result' : '#dh-result');
            if (box) {
                box.innerHTML = `
                    <div class="desk-suite-kv">
                        <span>${esc(patch.action || '')}</span>
                        <span>根数 <b>${esc(patch.rows ?? bars.length)}</b></span>
                        <span>首根 <b>${esc(first.time || '')}</b></span>
                        <span>末根 <b>${esc(last.time || '')}</b></span>
                        <span>末收 <b>${num(last.close, 4)}</b></span>
                        ${patch.rule ? `<span>周期 <b>${esc(patch.rule)}</b></span>` : ''}
                        ${patch.seconds ? `<span>秒数 <b>${esc(patch.seconds)}</b></span>` : ''}
                    </div>`;
            }
            return;
        }
        if (type === 'datahub_query') {
            const box = this.element.querySelector('#dh-query');
            if (!box) return;
            if (!patch.ok) {
                box.innerHTML = `<div class="desk-suite-hint warn">${esc(patch.message || '查询失败')}</div>`;
                return;
            }
            const rows = (patch.rows || []) as Array<Record<string, any>>;
            const keys = rows.length ? Object.keys(rows[0]) : [];
            box.innerHTML = `${table(keys, rows.slice(0, 200).map(
                (row) => keys.map((key) => esc(row[key]))),
                '查询没有结果')}
                <div class="desk-suite-hint">${esc(patch.message || '')}（最多显示 200 行）</div>`;
        }
    }
}

// ================================================================ 运维
export class OpsPage {
    public readonly element: HTMLDivElement;
    private readonly options: PageOptions;
    private theme: DeskTheme;
    private data: Record<string, any> = {};

    constructor(options: PageOptions) {
        this.options = options;
        this.theme = options.theme;
        this.element = shell('ops', this.theme, '平台 / 运维',
            'API Token、定时任务、企业微信/邮件告警、策略版本回滚。headless 服务用同一套 token。',
            this.skeleton());
        this.element.addEventListener('click', (event) => {
            this.onClick(event);
        });
    }

    show(): void { this.element.style.display = 'block'; }
    hide(): void { this.element.style.display = 'none'; }
    applyTheme(theme: DeskTheme): void {
        this.theme = theme;
        this.element.className = `desk-suite-page desk-suite-ops theme-${theme}`;
    }

    private skeleton(): string {
        return `
        <div class="desk-suite-grid">
            <section class="desk-suite-card">
                <h3>API Token</h3>
                <div class="desk-suite-form">
                    <label>名称<input data-op="tokenName" placeholder="ci / mobile"></label>
                    <label>scope<input data-op="tokenScopes" value="read" placeholder="read,trade,research,data,ops"></label>
                    <label>有效期（秒）<input data-op="tokenTtl" type="number" value="604800"></label>
                    <label class="inline">永久（0）<input data-op="tokenTtl0" type="checkbox"></label>
                </div>
                <div class="desk-suite-buttons">
                    <button class="desk-tool primary" data-op-token>生成 Token</button>
                    <button class="desk-tool danger" data-op-token-all>全部撤销</button>
                </div>
                <div id="op-token-out"></div>
                <div id="op-tokens"></div>
            </section>
            <section class="desk-suite-card">
                <h3>定时任务</h3>
                <div class="desk-suite-form">
                    <label>名称<input data-op="taskName" placeholder="reconcile"></label>
                    <label>动作<select data-op="taskAction">
                        <option value="heartbeat">heartbeat</option>
                        <option value="snapshot_quotes">snapshot_quotes</option>
                        <option value="reconcile">reconcile</option>
                        <option value="prune">prune</option>
                    </select></label>
                    <label>间隔（秒）<input data-op="taskInterval" type="number" value="300"></label>
                </div>
                <div class="desk-suite-buttons">
                    <button class="desk-tool primary" data-op-task-add>添加</button>
                    <button class="desk-tool" data-op-task-run>立即跑到期任务</button>
                </div>
                <div id="op-tasks"></div>
            </section>
        </div>
        <div class="desk-suite-grid">
            <section class="desk-suite-card">
                <h3>告警通道</h3>
                <div class="desk-suite-form">
                    <label class="inline"><input type="checkbox" data-op="wecomEnabled"> 企业微信</label>
                    <label class="wide">Webhook<input data-op="wecomWebhook" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="></label>
                    <label class="inline"><input type="checkbox" data-op="emailEnabled"> 邮件</label>
                    <label>SMTP<input data-op="emailHost" placeholder="smtp.qq.com"></label>
                    <label>端口<input data-op="emailPort" type="number" value="465"></label>
                    <label>账号<input data-op="emailUser"></label>
                    <label>密码 / 授权码<input data-op="emailPassword" type="password"></label>
                    <label>收件人<input data-op="emailTo"></label>
                    <label>发件人<input data-op="emailFrom"></label>
                </div>
                <div class="desk-suite-buttons">
                    <button class="desk-tool primary" data-op-notify-save>保存通道</button>
                    <button class="desk-tool" data-op-notify-test>发送测试</button>
                </div>
                <div id="op-notify"></div>
            </section>
            <section class="desk-suite-card">
                <h3>策略版本</h3>
                <div class="desk-suite-form">
                    <label class="wide">策略文件<input data-op="versionPath" placeholder="C:/.../my_strategy.py"></label>
                </div>
                <div class="desk-suite-buttons">
                    <button class="desk-tool primary" data-op-version-snapshot>保存快照</button>
                    <button class="desk-tool" data-op-version-list>列出</button>
                </div>
                <div id="op-versions"></div>
            </section>
        </div>
        <section class="desk-suite-card">
            <h3>服务状态</h3>
            <div id="op-status"></div>
        </section>`;
    }

    private input(name: string): HTMLInputElement | HTMLSelectElement | null {
        return this.element.querySelector(
            `[data-op="${name}"]`) as HTMLInputElement | HTMLSelectElement | null;
    }

    private value(name: string): string {
        return String(this.input(name)?.value ?? '').trim();
    }

    private checked(name: string): boolean {
        return !!(this.input(name) as HTMLInputElement | null)?.checked;
    }

    private onClick(event: MouseEvent): void {
        const target = event.target as HTMLElement;
        if (target.closest('[data-op-token]')) {
            const ttl = this.checked('tokenTtl0') ? 0 : Number(this.value('tokenTtl') || 604800);
            this.options.onCommand('ops_token_issue', {
                name: this.value('tokenName') || 'api',
                scopes: this.value('tokenScopes') || 'read', ttl,
            });
            return;
        }
        if (target.closest('[data-op-token-all]')) {
            if (window.confirm('撤销全部 API Token？')) {
                this.options.onCommand('ops_token_revoke_all', {});
            }
            return;
        }
        const revoke = target.closest<HTMLElement>('[data-op-token-revoke]');
        if (revoke) {
            this.options.onCommand('ops_token_revoke',
                { id: revoke.dataset.opTokenRevoke || '' });
            return;
        }
        if (target.closest('[data-op-task-add]')) {
            this.options.onCommand('ops_task_add', {
                name: this.value('taskName') || this.value('taskAction'),
                action: this.value('taskAction'),
                interval: Number(this.value('taskInterval') || 300),
            });
            return;
        }
        if (target.closest('[data-op-task-run]')) {
            this.options.onCommand('ops_task_run', {});
            return;
        }
        const toggle = target.closest<HTMLElement>('[data-op-task-toggle]');
        if (toggle) {
            this.options.onCommand('ops_task_toggle', {
                name: toggle.dataset.opTaskToggle || '',
                enabled: toggle.dataset.enabled !== '1',
            });
            return;
        }
        const drop = target.closest<HTMLElement>('[data-op-task-remove]');
        if (drop) {
            this.options.onCommand('ops_task_remove',
                { name: drop.dataset.opTaskRemove || '' });
            return;
        }
        if (target.closest('[data-op-notify-save]')) {
            this.options.onCommand('ops_notify_config', {
                kind: this.checked('emailEnabled') ? 'email' : 'wecom',
                values: {
                    enabled: this.checked('emailEnabled') ? true : this.checked('wecomEnabled'),
                    webhook: this.value('wecomWebhook'),
                    host: this.value('emailHost'),
                    port: Number(this.value('emailPort') || 465), ssl: true,
                    user: this.value('emailUser'),
                    password: this.value('emailPassword'),
                    to: this.value('emailTo'), from: this.value('emailFrom'),
                },
            });
            // 两个通道都保存一次（简单可靠）
            this.options.onCommand('ops_notify_config', {
                kind: 'wecom', values: {
                    enabled: this.checked('wecomEnabled'),
                    webhook: this.value('wecomWebhook'),
                },
            });
            return;
        }
        if (target.closest('[data-op-notify-test]')) {
            this.options.onCommand('ops_notify_test', {});
            return;
        }
        if (target.closest('[data-op-version-snapshot]')) {
            this.options.onCommand('ops_version_snapshot',
                { path: this.value('versionPath') });
            return;
        }
        if (target.closest('[data-op-version-list]')) {
            this.options.onCommand('ops_versions',
                { path: this.value('versionPath') });
            return;
        }
        const rollback = target.closest<HTMLElement>('[data-op-version-rollback]');
        if (rollback) {
            if (!window.confirm('回滚这个版本？当前文件会先自动备份。')) return;
            this.options.onCommand('ops_version_rollback', {
                path: this.value('versionPath'),
                version: rollback.dataset.opVersionRollback || '',
            });
        }
    }

    apply(patch: Record<string, any>): void {
        const type = String(patch.type || '');
        if (type === 'ops_token' && patch.token) {
            const box = this.element.querySelector('#op-token-out');
            if (box) {
                box.innerHTML = `<div class="desk-suite-token">
                    <span class="desk-muted">只显示一次：</span>
                    <code>${esc(patch.token.token || '')}</code></div>`;
            }
            return;
        }
        if (type === 'ops') {
            this.data = patch;
            this.render(patch);
            return;
        }
        if (type === 'ops_tasks') {
            this.data.tasks = patch.tasks;
            this.renderTasks();
            const results = (patch.results || []) as Array<Record<string, any>>;
            const box = this.element.querySelector('#op-tasks');
            if (box && results.length) {
                box.insertAdjacentHTML('afterbegin', `<div class="desk-suite-hint">${
                    results.map((row) => `${esc(row.name)}: ${
                        row.ok ? 'OK' : '失败 ' + esc(row.error)}`).join('；')
                }</div>`);
            }
            return;
        }
        if (type === 'ops_notify') {
            if (patch.notify) {
                this.data.notify = patch.notify;
                this.renderNotify();
            }
            return;
        }
        if (type === 'ops_versions') {
            this.data.versions = patch.items || [];
            this.renderVersions();
        }
    }

    private render(patch: Record<string, any>): void {
        const status = patch.status || {};
        const statusBox = this.element.querySelector('#op-status');
        if (statusBox) {
            statusBox.innerHTML = table(['项', '值'], Object.keys(status).map(
                (key) => [esc(key), esc(JSON.stringify(status[key]))]),
                '还没有状态');
        }
        const tokens = (patch.tokens || []) as Array<Record<string, any>>;
        const tokenBox = this.element.querySelector('#op-tokens');
        if (tokenBox) {
            tokenBox.innerHTML = table(['名称', 'Scope', '创建', '过期', '最近使用', ''],
                tokens.map((row) => [
                    esc(row.name || ''),
                    esc((row.scopes || []).join(',')), when(row.created),
                    row.expires ? when(row.expires) : '永久',
                    row.last_used ? when(row.last_used) : '—',
                    row.revoked ? '<span class="muted">已撤销</span>'
                        : `<button class="desk-suite-link" data-op-token-revoke="${esc(row.id || '')}">撤销</button>`,
                ]), '还没有 token');
        }
        this.renderTasks();
        this.renderNotify();
        this.renderVersions();
    }

    private renderTasks(): void {
        const tasks = ((this.data.tasks || {}).tasks || []) as Array<Record<string, any>>;
        const box = this.element.querySelector('#op-tasks');
        if (!box) return;
        box.innerHTML = table(['名称', '动作', '间隔', '下次', '上次', '状态', '操作'],
            tasks.map((row) => [
                esc(row.name || ''), esc(row.action || ''),
                `${esc(row.interval)}s`, when(row.next_run), when(row.last_run),
                row.enabled ? `<span class="desk-suite-state live">${
                    esc(row.last_status || '待运行')}</span>`
                    : '<span class="muted">已停用</span>',
                `<button class="desk-suite-link" data-op-task-toggle="${esc(row.name)}" data-enabled="${row.enabled ? '1' : '0'}">${row.enabled ? '停用' : '启用'}</button>
                 <button class="desk-suite-link" data-op-task-remove="${esc(row.name)}">删除</button>`,
            ]), '还没有任务');
    }

    private renderNotify(): void {
        const notify = this.data.notify || {};
        const config = notify.config || {};
        const wecom = config.wecom || {};
        const email = config.email || {};
        const setInput = (name: string, value: unknown) => {
            const input = this.input(name);
            if (input && input.type !== 'checkbox') input.value = value === null
                || value === undefined ? '' : String(value);
        };
        const wecomOn = this.input('wecomEnabled') as HTMLInputElement | null;
        if (wecomOn) wecomOn.checked = !!wecom.enabled;
        const emailOn = this.input('emailEnabled') as HTMLInputElement | null;
        if (emailOn) emailOn.checked = !!email.enabled;
        setInput('wecomWebhook', wecom.webhook);
        setInput('emailHost', email.host);
        setInput('emailPort', email.port);
        setInput('emailUser', email.user);
        setInput('emailTo', email.to);
        setInput('emailFrom', email.from);
        const box = this.element.querySelector('#op-notify');
        if (!box) return;
        const history = (notify.history || []) as Array<Record<string, any>>;
        box.innerHTML = table(['时间', '标题', '结果'], history.map((row) => [
            when(row.at), esc(row.title || ''),
            esc((row.results || []).map((item: any) =>
                `${item.channel}:${item.ok ? 'ok' : 'fail'}`).join('；')),
        ]), '还没有发送记录');
    }

    private renderVersions(): void {
        const items = (this.data.versions || []) as Array<Record<string, any>>;
        const box = this.element.querySelector('#op-versions');
        if (!box) return;
        box.innerHTML = table(['版本', '说明', '时间', '大小', ''],
            items.map((row) => [
                esc(row.version || ''), esc(row.note || ''), when(row.at),
                `${num(Number(row.size || 0) / 1024, 1)} KB`,
                `<button class="desk-suite-link" data-op-version-rollback="${esc(row.version || '')}">回滚</button>`,
            ]), '还没有版本快照');
    }
}
