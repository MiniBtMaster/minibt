/**
 * DeskApp — the top-level shell: tab strip + page stack + patch dispatcher.
 *
 * Python (or any backend) drives the UI by evaluating one JS statement:
 *
 *     window.__desk.applyPatch({type: 'rows', market: 'FUT', rows: [...]})
 *
 * and receives commands through the transport (`desk_~_{cmd,payload}`).
 */
import { ChartPage } from './chart-page';
import { HomePage, type HomeMarkets } from './home-page';
import { LocalChartPage } from './local-chart-page';
import { StrategyLabPage } from './strategy-lab-page';
import { CommandPalette, type CommandItem } from './command-palette';
import { DataPage, OpsPage, ResearchPage, WorkbenchPage } from './suite-pages';
import { deskLogo } from './logo';
import { StrategyManager, type StrategyRow } from './layout-dialogs';
import { ensureDeskDialogStyle, LoginDialog,
    type LoginKind } from './login-dialog';
import { LogPage, type LogItem } from './log-page';
import {
    addToGroup, applyState as applyWatchState,
    favorites as watchFavorites, groupSymbols, isFavorite,
    setPersistHook, snapshot as watchSnapshot,
    toggleFavorite as toggleWatchFavorite, writableGroups,
} from './watch-store';
import { openIndicatorMenu, showPersonalManager } from './indicator-menu';
import { closeMenu, showMenu, showMenuBelow, type MenuItem } from './menu';
import { QuotePage } from './quote-page';
// 「设置」页（复刻 miniqt 设置界面 ✓）
import { SettingsPage, type SettingsValues } from './settings-page';
import { AlertCenterPage, ReplayLabPage, WorkspacePage } from './workspace-pages';
import { SymbolPreview } from './symbol-preview';
import { detectTransport, MockTransport, type DeskBootstrap, type DeskTransport } from './transport';

export interface DeskAppOptions extends Omit<DeskBootstrap, 'transport'> {
    /** already-built transport (wins over auto-detection) */
    transport?: DeskTransport;
}

interface TabItem {
    id: string;
    label: string;
    kind: 'home' | 'quote' | 'chart' | 'local' | 'strategy' | 'settings'
        | 'log' | 'web' | 'workspace' | 'replay-lab' | 'alerts'
        | 'workbench' | 'research' | 'datahub' | 'ops';
    symbol?: string;
}

const HOME_TAB_ID = '__home';
const QUOTE_TAB_ID = '__quote';
/** 「设置」页签（顶栏可关闭 ✓） */
const SETTINGS_TAB_ID = '__settings';
/** 「运行日志」页签（从「＋ 新建 ▾」打开 ✓） */
const LOG_TAB_ID = '__log';
const WORKSPACE_TAB_ID = '__workspace';
const REPLAY_LAB_TAB_ID = '__replay_lab';
const ALERT_CENTER_TAB_ID = '__alerts';
const WORKBENCH_TAB_ID = '__workbench';
const RESEARCH_TAB_ID = '__research';
const DATAHUB_TAB_ID = '__datahub';
const OPS_TAB_ID = '__ops';
/** 日志环形缓冲（页面打开前的日志也保留，最多 800 条 ✓） */
const LOG_BUFFER = 800;

/** toast 上的按钮（导出的「打开文件 / 打开文件夹」✓） */
export interface ToastAction {
    label: string;
    cmd: string;
    payload?: Record<string, unknown>;
}

export interface ExportItem {
    path: string;
    name?: string;
    rows?: number;
    at?: string;
}
/** 同时打开的看盘 tab 上限（多了就提示，避免一堆图吃内存 ✓） */
export const MAX_CHART_TABS = 12;
/** 主题记忆（localStorage，浏览器壳刷新也保持 ✓） */
const THEME_KEY = 'minibt.desk.theme';

function escapeHtml(value: unknown): string {
    return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[ch] as string));
}

export class DeskApp {
    public readonly root: HTMLDivElement;
    public readonly transport: DeskTransport;

    private readonly tabStrip: HTMLDivElement;
    private readonly stack: HTMLDivElement;
    private readonly status: HTMLSpanElement;
    private settingsButton: HTMLButtonElement | null = null;
    private addButton: HTMLButtonElement | null = null;
    private home: HomePage | null = null;
    private markets: HomeMarkets = {
        futures: false, stocks: false, offline: true, no_service: true,
    };
    /** 首页是否可见（不可见时后端不刷新 home） */
    private homeActive = false;
    /** 是否已经根据 boot 的连接状态决定初始页 */
    private initialRouted = false;
    /** 报价页是否已经请求过（按需创建 / 拉数 ✓） */
    private quoteRequested = false;
    /** 报价页没打开时先攒着补丁，打开后回放 ✓ */
    private quoteQueue: Array<Record<string, any>> = [];
    /** 离线启动：本地图表拿到 local_data 后自动加载第一个 CSV ✓ */
    private pendingLocalAutoLoad = false;
    /** 策略回测 / 参数优化 Tab（独立于本地图表 ✓） */
    private readonly strategyPages = new Map<string, StrategyLabPage>();
    private readonly strategySources = new Map<string, string>();
    private strategySeq = 0;
    /** 「实时图表」正在等后端默认合约（未连接 → 空白图表 ✓） */
    private pendingRealtime = false;

    private readonly tabs = new Map<string, TabItem>();
    private readonly pages = new Map<string,
        HomePage | QuotePage | ChartPage | LocalChartPage | StrategyLabPage
        | SettingsPage | LogPage>();
    /** 设置页（一个实例，关掉就销毁 ✓） */
    private settingsPage: SettingsPage | null = null;
    /** 后端推来的偏好设置（设置页读它 ✓） */
    private settingsValues: SettingsValues = {};
    /** 本地 LSP（jedi）地址；`null` = 还没起来 / 不可用 ✓ */
    private lspInfo: { url: string; root: string } | null = null;
    private lspStatus = '';
    private lspError = '';
    /** 编辑器「帮助」对话框（同一时刻只留一个 ✓） */
    private helpDialog: HTMLDivElement | null = null;
    private alertDialog: HTMLDivElement | null = null;
    private strategyManager: StrategyManager | null = null;
    private version = '';
    private readonly buttons = new Map<string, HTMLButtonElement>();

    private activeId = HOME_TAB_ID;
    /** 后端下发的状态栏文本（`{type:'status'}`），优先于 transport 名 ✓ */
    private serverStatus = '';
    /** ★ 收藏的指标 / 策略（后端 `favorites` 补丁 → 工具栏下拉 ✓） */
    private favorites: Array<Record<string, unknown>> = [];
    private strategyFavorites: Array<Record<string, unknown>> = [];
    private theme: 'light' | 'dark';
    private readonly logo: HTMLDivElement;
    private quotePage: QuotePage | null = null;
    private preview: SymbolPreview | null = null;
    /** 最近导出的文件（后端 `exports` 补丁 ✓） */
    private exportHistory: ExportItem[] = [];
    /** 个人指标（编辑器保存后推过来；下次打开菜单时合并 ✓） */
    private personalIndicators: Array<Record<string, unknown>> = [];
    /** 登录框（期货 / 股票；离线也能打开 ✓） */
    private login: LoginDialog | null = null;
    /** 独立「运行日志」页（`＋ 新建 ▾ → 运行日志` ✓） */
    private logPage: LogPage | null = null;
    private workspacePage: WorkspacePage | null = null;
    private replayLabPage: ReplayLabPage | null = null;
    private alertCenter: AlertCenterPage | null = null;
    private workbenchPage: WorkbenchPage | null = null;
    private researchPage: ResearchPage | null = null;
    private datahubPage: DataPage | null = null;
    private opsPage: OpsPage | null = null;
    private palette: CommandPalette | null = null;
    /** 所有日志的环形缓冲（后开的日志页也能看到之前的 ✓） */
    private logBuffer: LogItem[] = [];
    constructor(options: DeskAppOptions = {}) {
        this.theme = options.theme || 'dark';
        this.transport = options.transport || detectTransport(options as DeskBootstrap);

        this.root = document.createElement('div');
        this.root.className = 'desk-root';

        // ---- tab strip -----------------------------------------------------
        const topbar = document.createElement('div');
        topbar.className = 'desk-topbar';
        // 顶栏 LOGO（深色 / 浅色两套 SVG，切主题时换 ✓）
        this.logo = document.createElement('div');
        this.logo.className = 'desk-logo';
        this.logo.title = 'MiniBT Desk';
        this.logo.innerHTML = deskLogo(this.theme);
        this.logo.addEventListener('click', () => this._goHome());
        this.tabStrip = document.createElement('div');
        this.tabStrip.className = 'desk-tabstrip';
        const add = document.createElement('button');
        add.className = 'desk-tab-add desk-tab-new';
        // ★ 只留图标（用户要求：去掉「新建」二字 ✓）
        add.innerHTML = '<span class="desk-tab-new-plus">+</span>'
            + '<span class="desk-tab-new-chev">▾</span>';
        add.title = '新建页面（行情报价 / 本地图表）';
        add.addEventListener('click', () => this._showNewMenu(add));
        this.addButton = add;
        this.status = document.createElement('span');
        this.status.className = 'desk-muted desk-status';
        const themeButton = document.createElement('button');
        themeButton.className = 'desk-tab-add';
        themeButton.title = '切换主题（浅色 / 深色）';
        themeButton.textContent = '◐';
        themeButton.addEventListener('click', () => {
            this.toggleTheme();
        });
        // ---- 右侧：minibt 官网 / 设置（对应 miniqt 左侧导航最底下两项 ✓）
        const site = document.createElement('button');
        site.className = 'desk-tab-add desk-topbar-btn';
        site.title = '打开 minibt 官网（顶栏新 tab；可关闭 ✓）';
        site.textContent = '🌐';
        site.addEventListener('click', () => this.openWebPage(
            'https://www.minibt.cn'));
        const gear = document.createElement('button');
        gear.className = 'desk-tab-add desk-topbar-btn';
        gear.title = '设置（本地文件 / 个性化 / 关于 / 图表配置 / 图表颜色）';
        gear.textContent = '⚙';
        gear.addEventListener('click', () => this.openSettings());
        this.settingsButton = gear;
        // ★ 顶栏全局搜索 / 运行日志（文档 13.3 / 13.13 的入口 ✓）
        const search = document.createElement('button');
        search.className = 'desk-tab-add desk-topbar-btn';
        search.title = '全局搜索（打开报价页并聚焦搜索框）';
        search.textContent = '🔍';
        search.addEventListener('click', () => {
            this.openQuote();
            window.setTimeout(() => this.quotePage?.focusSearch(), 0);
        });
        const logButton = document.createElement('button');
        logButton.className = 'desk-tab-add desk-topbar-btn';
        logButton.title = '打开运行日志';
        logButton.textContent = '🗒';
        logButton.addEventListener('click', () => this.openLog());
        const paletteButton = document.createElement('button');
        paletteButton.className = 'desk-tab-add desk-topbar-btn';
        paletteButton.title = '全局命令面板（Ctrl/⌘ + K）';
        paletteButton.textContent = '⌘';
        paletteButton.addEventListener('click', () => this.openPalette());
        topbar.append(this.logo, this.tabStrip, add, this.status,
                      search, paletteButton, logButton, site, gear, themeButton);

        this.stack = document.createElement('div');
        this.stack.className = 'desk-stack';

        this.root.append(topbar, this.stack);
        // ★ 收藏 / 自选分组改动 → 落盘（重启还在 ✓）
        setPersistHook((state) => this.send('watch_set', state));
        this.send('watch_get', {});
        const saved = this._readTheme();
        this.applyTheme(saved || this.theme);

        this._installShortcuts();
        this._installLinkGuard();
        this._installWebNav();
    }

    // ------------------------------------------------------------- lifecycle
    mount(parent: HTMLElement): void {
        parent.appendChild(this.root);
        this.activate(HOME_TAB_ID);
        this._setStatus();
    }

    /** Tell the backend we are ready (it answers with a `boot` patch). */
    boot(): void {
        this.send('ready', {
            transport: this.transport.kind,
            width: window.innerWidth,
            height: window.innerHeight,
        });
    }

    send(cmd: string, payload?: unknown): void {
        this.transport.send({ cmd, payload });
    }

    // ------------------------------------------------------------- home / lazy quote
    private _createHomePage(): void {
        const page = new HomePage({
            theme: this.theme,
            markets: this.markets,
            onCommand: (cmd, payload) => this.send(cmd, payload),
            onOpenQuote: () => this.openQuote(),
            onOpenLocal: (name) => this.openLocalChart(name || ''),
            onOpenChart: (symbol, name) => this.openChart(symbol, { name }),
            // 左键选中自选行 → 下面画 K 线（替代原来的折线 ✓）
            onPreviewBars: (symbol, cycle) => this.send('home_preview', {
                symbol, cycle,
            }),
            // 点「主力行情」某交易所 → 后端取该所主力合约 ✓
            onMainRows: (exchange) => this.send('home_main', { exchange }),
            onNew: () => {
                if (this.addButton) this._showNewMenu(this.addButton);
            },
            // 左下角「数据源」两行：点一下就打开对应登录框 ✓
            onLogin: (kind) => this.openLogin(kind as LoginKind),
            onToast: (level, text) => this.toast(level, text),
            defaultGroup: String(
                this.settingsValues.watch_default_group || 'recent'),
            onOpenWorkspace: () => this.openWorkspace(),
            onOpenReplayLab: () => this.openReplayLab(),
            onOpenAlerts: () => this.openAlertCenter(),
        });
        page.hide();
        this.home = page;
        this.pages.set(HOME_TAB_ID, page);
        this.stack.appendChild(page.element);
    }

    /**
     * 实时图表（看盘窗口）→ **空白图表** + 自动弹「商品搜索」（P208 ✓）
     *
     * 没有合约的看盘页：图表区提示"按空格搜索合约 / 点商品搜索"，
     * 选到合约后自动 `switch_symbol` 到该合约 ✓
     */
    openBlankChart(): string {
        // 天勤已连接 → 后端给「主力 + 上期所第一个合约」；
        // 未连接 / 没有合约 → 仍然打开空白图表 + 商品搜索。
        if (this.pendingRealtime) return '';
        this.pendingRealtime = true;
        this.send('default_realtime', {});
        window.setTimeout(() => {
            if (!this.pendingRealtime) return;
            this.pendingRealtime = false;
            this._openBlankChartFallback();
        }, 2500);
        return '';
    }

    private _openBlankChartFallback(): void {
        const placeholder = `blank:${Date.now()}`;
        const id = this.openChart(placeholder, {
            name: '实时图表', blank: true, label: '实时图表',
        });
        const page = this.pages.get(id) as unknown as {
            openSymbolSearch?: () => void;
            setBlankHint?: (text: string) => void;
        } | null;
        window.setTimeout(() => {
            page?.setBlankHint?.('按 空格 搜索合约，或点「商品搜索」');
            page?.openSymbolSearch?.();
        }, 350);
    }

    private _showNewMenu(anchor: HTMLElement): void {
        const futuresOn = !!this.markets.futures;
        const stocksOn = !!this.markets.stocks;
        showMenuBelow(anchor, [
            {
                // ★ 首页恢复可用（P105）：点它才打开，启动不再自动出现 ✓
                label: '首页',
                run: () => this.openHome(),
            },
            {
                // ★ 离线也能打开：只显示本地缓存的合约，连上行情才更新 ✓
                label: '行情报价',
                run: () => this.openQuote(),
            },
            {
                // ★ 实时图表（看盘窗口）：打开**空白图表**，再用商品搜索 /
                //   键盘精灵选合约（用户要求 ✓）
                label: '实时图表（看盘窗口）',
                separator: true,
                run: () => this.openBlankChart(),
            },
            {
                label: '本地图表（minibt 内置数据 / CSV）',
                run: () => this.openLocalChart(),
            },
            {
                // ★ 独立日志页：不打开图表也能看日志（用户要求 ✓）
                label: '运行日志',
                run: () => this.openLog(),
            },
            /* 扩展功能入口暂时关闭：需要时再打开 ✓
            {
                label: '交易工作台（订单票 / 风控 / 审计）',
                separator: true,
                run: () => this.openWorkbench(),
            },
            {
                label: '策略研究（walk-forward / 实验库）',
                run: () => this.openResearch(),
            },
            {
                label: '本地数据平台（质检 / 换月 / SQL）',
                run: () => this.openDataHub(),
            },
            {
                label: '平台 / 运维（Token / 任务 / 告警）',
                run: () => this.openOps(),
            },
            */
            {
                label: futuresOn ? '期货已连接（重新登录…）' : '登录期货账户（天勤）…',
                separator: true,
                // ⚠ 首页暂停用 → 登录不再打开首页（只弹登录框 ✓）
                run: () => this.openLogin('futures'),
            },
            {
                label: stocksOn ? '股票已连接（重新连接…）'
                    : '连接股票（富途 OpenD）…',
                run: () => this.openLogin('stocks'),
            },
            {
                // 本地模拟账户（离线也能设置初始资金 / 手续费）
                label: '本地模拟账户…',
                run: () => this.openSettings('sim'),
            },
        ]);
    }

    /** 打开登录框（离线状态下的接入口 ✓） */
    openLogin(kind: LoginKind = 'futures',
              saved: Record<string, any> | null = null): LoginDialog {
        if (!this.login) {
            this.login = new LoginDialog({
                theme: this.theme,
                onSubmit: (target, values) => {
                    this.send(target === 'stocks'
                        ? 'connect_stocks' : 'connect_futures', values);
                },
                onTest: (values) => this.send('test_futu', values),
                // ★ 股票「帮助」在弹窗里点「打开下载页面」才开外链（复刻 miniqt ✓）
                onOpenUrl: (url) => this.send('open_url', { url }),
                onHelp: (which) => {
                    const urls: Record<string, string> = {
                        futu: 'https://openapi.futunn.com/futu-api-doc/quick/'
                            + 'opend-base.html',
                        real: 'https://www.minibt.cn',
                        tqsdk: 'https://www.shinnytech.com/tqsdk',
                    };
                    this.send('open_url', { url: urls[which] || urls.futu });
                },
                onCommand: (target) => this.send('login_info', { kind: target }),
            });
        }
        this.login.setTheme(this.theme);
        this.login.open(kind, saved);
        if (!saved) this.send('login_info', { kind });
        return this.login;
    }

    /** 对所有已打开的本地图表页的编辑器跑一个回调 ✓ */
    /** 每个页面里的编辑器都刷一遍（策略按钮 / 大纲 等 ✓） */
    private _refreshEditors(): void {
        const list: Array<{ refreshStrategyButtons?: () => void }> = [];
        for (const page of this.pages.values()) {
            const panel = (page as unknown as {
                editorPanel?: { refreshStrategyButtons?: () => void } })
                .editorPanel;
            if (panel) list.push(panel);
        }
        for (const panel of list) panel.refreshStrategyButtons?.();
    }

    private _forEditors(run: (page: LocalChartPage) => void): void {
        for (const page of this.pages.values()) {
            if (!(page instanceof LocalChartPage)) continue;
            const editor = page.editorPanel;
            if (editor) run(page);
        }
    }

    /** 编辑器「帮助」：复刻 MiniQT 的 Pi Agent Web 环境配置指引 ✓ */
    private _showEditorHelp(text: string): void {
        if (!text) return;
        ensureDeskDialogStyle();      // 没登录过也要有弹窗样式 ✓
        if (this.helpDialog) this.helpDialog.remove();
        const mask = document.createElement('div');
        mask.className = 'desk-help-mask';
        const box = document.createElement('div');
        box.className = 'desk-help-box desk-help-wide';
        const head = document.createElement('div');
        head.className = 'desk-help-head';
        head.innerHTML = '<span>帮助</span>';
        const close = document.createElement('button');
        close.className = 'desk-help-close';
        close.textContent = '✕';
        close.title = '关闭';
        head.appendChild(close);
        const body = document.createElement('div');
        body.className = 'desk-help-body';
        const pre = document.createElement('pre');
        pre.className = 'desk-help-pre';
        pre.textContent = text;
        body.appendChild(pre);
        const foot = document.createElement('div');
        foot.className = 'desk-help-foot';
        const ok = document.createElement('button');
        ok.className = 'desk-help-btn primary';
        ok.textContent = '确定';
        foot.appendChild(ok);
        box.append(head, body, foot);
        mask.appendChild(box);
        const dismiss = () => {
            mask.remove();
            this.helpDialog = null;
        };
        close.addEventListener('click', dismiss);
        ok.addEventListener('click', dismiss);
        mask.addEventListener('mousedown', (event) => {
            if (event.target === mask) dismiss();
        });
        document.body.appendChild(mask);
        this.helpDialog = mask;
    }

    /** 模态提醒弹窗（体检没通过 / 加到图表失败 ✓） */
    showAlert(info: { title?: string; message?: string; detail?: string;
                      level?: string }): void {
        ensureDeskDialogStyle();      // 同上 ✓
        const level = String(info.level || 'warning');
        if (this.alertDialog) this.alertDialog.remove();
        const mask = document.createElement('div');
        mask.className = 'desk-help-mask';
        const box = document.createElement('div');
        box.className = 'desk-help-box desk-alert-box';
        const head = document.createElement('div');
        head.className = 'desk-help-head';
        head.innerHTML = `<span>${
            level === 'error' ? '错误' : (level === 'info' ? '提示' : '提醒')
        }</span>`;
        const close = document.createElement('button');
        close.className = 'desk-help-close';
        close.textContent = '✕';
        close.title = '关闭';
        head.appendChild(close);
        const body = document.createElement('div');
        body.className = 'desk-help-body desk-alert-body';
        const title = document.createElement('div');
        title.className = `desk-alert-title is-${level}`;
        title.textContent = String(info.title || '提示');
        const message = document.createElement('div');
        message.className = 'desk-alert-message';
        message.textContent = String(info.message || '');
        body.append(title, message);
        const detail = String(info.detail || '');
        if (detail) {
            const tag = document.createElement('div');
            tag.className = 'desk-alert-detail';
            tag.textContent = detail;
            body.appendChild(tag);
        }
        const foot = document.createElement('div');
        foot.className = 'desk-help-foot';
        const ok = document.createElement('button');
        ok.className = 'desk-help-btn primary';
        ok.textContent = '知道了';
        foot.appendChild(ok);
        box.append(head, body, foot);
        mask.appendChild(box);
        const dismiss = (): void => {
            mask.remove();
            this.alertDialog = null;
        };
        close.addEventListener('click', dismiss);
        ok.addEventListener('click', dismiss);
        mask.addEventListener('mousedown', (event) => {
            if (event.target === mask) dismiss();
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') dismiss();
        }, { once: true });
        document.body.appendChild(mask);
        this.alertDialog = mask;
        ok.focus();
    }

    /** 策略管理（看盘窗口「指标 → 策略管理…」✓ 界面复用「布局管理」） */
    showStrategyManage(patch: Record<string, any>): void {
        if (!this.strategyManager) {
            const manager = new StrategyManager();
            manager.onToggleCallback = (row, key, value) => {
                this.send('strategy_manage_update', {
                    action: 'toggle', symbol: row.symbol,
                    cell: row.cell || 0, key, value,
                });
            };
            manager.onDeleteCallback = (row) => {
                this.send('strategy_manage_update', {
                    action: 'delete', symbol: row.symbol,
                    cell: row.cell || 0, local: !!row.local,
                });
            };
            document.body.appendChild(manager.element);
            this.strategyManager = manager;
        }
        this.strategyManager.open((patch.rows || []) as StrategyRow[]);
    }

    private _goHome(): void {
        this.openHome();
    }

    /** 收起首页（离线启动时默认不显示，用户点「首页」再打开 ✓） */
    private _dropHome(): void {
        if (!this.tabs.has(HOME_TAB_ID)) return;
        this.pages.delete(HOME_TAB_ID);
        this.tabs.delete(HOME_TAB_ID);
        this.buttons.get(HOME_TAB_ID)?.remove();
        this.buttons.delete(HOME_TAB_ID);
        this.home?.element.remove();
        this.home = null;
        this.homeActive = false;
    }

/** 启动时是否自动打开首页（`boot.home`；**只有命令行带账号**才为真 ✓） */
    private autoHome = false;

    /** 打开（必要时重建）首页 ✓ */
    openHome(): void {
        if (!this.tabs.has(HOME_TAB_ID)) {
            this._createHomePage();
            this._addTab({ id: HOME_TAB_ID, label: '首页', kind: 'home' });
            // ★ 首页永远排在**顶栏第一位**（后打开也插到最左 ✓）
            const button = this.buttons.get(HOME_TAB_ID);
            if (button) this.tabStrip.prepend(button);
        }
        this.home?.setMarkets(this.markets);
        this.activate(HOME_TAB_ID);
        this.send('home', { active: true });
    }

    private _routeInitial(): void {
        if (this.initialRouted) return;
        this.initialRouted = true;
        // ★ 首页只在「命令行带账号登录」时自动出现（用户要求 ✓）
        if (this.autoHome) {
            this.openHome();
            return;
        }
        this.home?.setMarkets(this.markets);
        if (this.markets.futures || this.markets.stocks) {
            this.openQuote();
            return;
        }
        this._dropHome();
        this.pendingLocalAutoLoad = true;
        this.openLocalChart();
    }

    /** 打开行情报价（按需创建 + 拉数；首页启动时不请求全市场 ✓） */
    openQuote(): void {
        const first = !this.quoteRequested;
        this.quoteRequested = true;
        this._ensureQuoteTab();
        this.activate(QUOTE_TAB_ID);
        // ★ 关闭后重新打开 / 全局搜索进入：chips 也要重发（否则类型 /
        //   交易所按钮全空 ✗）
        this.send('quote_chips', {});
        if (!first) return;
        const queued = this.quoteQueue;
        this.quoteQueue = [];
        for (const patch of queued) this.applyPatch(patch);
        this.send('reload_contracts', {});
    }

    private _ensureQuoteTab(): void {
        if (this.tabs.has(QUOTE_TAB_ID)) return;
        this._createQuotePage();
        this._addTab({
            id: QUOTE_TAB_ID,
            label: '行情报价',
            kind: 'quote',
        });
    }

    /** 报价页还没打开：先攒补丁（只留 screen 状态，rows 打开后会重拉）✓ */
    private _queueQuote(patch: Record<string, any>): void {
        if (this.quoteQueue.length >= 120) return;
        this.quoteQueue.push(patch);
    }

    // ------------------------------------------------------------- tabs
    private _addTab(tab: TabItem): void {
        this.tabs.set(tab.id, tab);
        const button = document.createElement('button');
        button.className = 'desk-tab';
        button.dataset.id = tab.id;
        const label = document.createElement('span');
        label.textContent = tab.label;
        button.appendChild(label);
        if (tab.kind !== 'home') {
            const close = document.createElement('span');
            close.className = 'desk-tab-close';
            close.textContent = '×';
            close.addEventListener('click', (event) => {
                event.stopPropagation();
                this.closeTab(tab.id);
            });
            button.appendChild(close);
        }
        button.addEventListener('click', () => this.activate(tab.id));
        this.tabStrip.appendChild(button);
        this.buttons.set(tab.id, button);
    }

    /** 打开「运行日志」页（独立 tab；历史日志一起带过来 ✓） */
    openLog(): LogPage {
        const id = LOG_TAB_ID;
        if (!this.logPage) {
            const page = new LogPage({
                theme: this.theme,
                items: this.logBuffer.slice(),
            });
            this.logPage = page;
            this.pages.set(id, page);
            this._addTab({ id, label: '运行日志', kind: 'log' });
            this.stack.appendChild(page.element);
        }
        this.logPage.setTheme(this.theme);
        this.activate(id);
        return this.logPage;
    }

    /** 图表工作台：当前打开的图表列表 + 新建入口 ✓ */
    openWorkspace(): WorkspacePage {
        if (!this.tabs.has(WORKSPACE_TAB_ID)) {
            const page = new WorkspacePage({
                theme: this.theme,
                getTabs: () => [...this.tabs.values()].map((tab) => ({
                    id: tab.id, label: tab.label, kind: tab.kind,
                })),
                onActivate: (id) => this.activate(id),
                onNewQuote: () => this.openQuote(),
                onNewLocal: () => this.openLocalChart(),
            });
            this.workspacePage = page;
            this.pages.set(WORKSPACE_TAB_ID, page as never);
            this.stack.appendChild(page.element);
            this._addTab({ id: WORKSPACE_TAB_ID, label: '图表工作台',
                           kind: 'workspace' });
        }
        this.activate(WORKSPACE_TAB_ID);
        return this.workspacePage as WorkspacePage;
    }

    /** 回放实验室：打开本地图表并可直接进入回放 ✓ */
    openReplayLab(): ReplayLabPage {
        if (!this.tabs.has(REPLAY_LAB_TAB_ID)) {
            const page = new ReplayLabPage({
                theme: this.theme,
                onOpenLocal: () => this.openLocalChart(),
                onStartReplay: () => this._startReplayLab(),
            });
            this.replayLabPage = page;
            this.pages.set(REPLAY_LAB_TAB_ID, page as never);
            this.stack.appendChild(page.element);
            this._addTab({ id: REPLAY_LAB_TAB_ID, label: '回放实验室',
                           kind: 'replay-lab' });
        }
        this.activate(REPLAY_LAB_TAB_ID);
        return this.replayLabPage as ReplayLabPage;
    }

    private _startReplayLab(): void {
        let page = this._activeLocalPage();
        if (!page) {
            const id = this.openLocalChart();
            page = this.pages.get(id) as unknown as LocalChartPage | null;
        }
        window.setTimeout(() => {
            (page as unknown as { toggleReplay?: () => void })
                ?.toggleReplay?.();
        }, 450);
    }

    /** 预警中心：全局预警列表 / 删除 / 清空 ✓ */
    openAlertCenter(): AlertCenterPage {
        if (!this.tabs.has(ALERT_CENTER_TAB_ID)) {
            const page = new AlertCenterPage({
                theme: this.theme,
                onRefresh: () => this.send('alerts', {}),
                onDrop: (id) => this.send('drop_alert', { id }),
                onClear: () => this.send('clear_alerts', {}),
                onOpen: (symbol) => this.openChart(symbol),
            });
            this.alertCenter = page;
            this.pages.set(ALERT_CENTER_TAB_ID, page as never);
            this.stack.appendChild(page.element);
            this._addTab({ id: ALERT_CENTER_TAB_ID, label: '预警中心',
                           kind: 'alerts' });
        }
        this.activate(ALERT_CENTER_TAB_ID);
        this.send('alerts', {});
        return this.alertCenter as AlertCenterPage;
    }

    // -------------------------------------------------- 扩展功能页
    private _suitePage<T extends { element: HTMLDivElement }>(
            id: string, label: string, kind: TabItem['kind'],
            make: () => T, command: string): T {
        if (!this.tabs.has(id)) {
            const page = make();
            this.pages.set(id, page as never);
            this.stack.appendChild(page.element);
            this._addTab({ id, label, kind });
        }
        this.activate(id);
        this.send(command, {});
        return this.pages.get(id) as unknown as T;
    }

    /** 交易工作台：订单票 / 条件单 / 风控 / 对账 / 审计 ✓ */
    openWorkbench(): WorkbenchPage {
        const page = this._suitePage(WORKBENCH_TAB_ID, '交易工作台',
            'workbench',
            () => new WorkbenchPage({
                theme: this.theme,
                onCommand: (cmd, payload) => this.send(cmd, payload),
            }),
            'workbench');
        this.workbenchPage = page;
        return page;
    }

    /** 策略研究：walk-forward / 批量 / 网格 / 实验库 ✓ */
    openResearch(): ResearchPage {
        const page = this._suitePage(RESEARCH_TAB_ID, '策略研究',
            'research',
            () => new ResearchPage({
                theme: this.theme,
                onCommand: (cmd, payload) => this.send(cmd, payload),
            }),
            'research');
        this.researchPage = page;
        return page;
    }

    /** 本地数据平台：行情库 / 质检 / 换月 / SQL / Tick ✓ */
    openDataHub(): DataPage {
        const page = this._suitePage(DATAHUB_TAB_ID, '数据平台',
            'datahub',
            () => new DataPage({
                theme: this.theme,
                onCommand: (cmd, payload) => this.send(cmd, payload),
            }),
            'datahub');
        this.datahubPage = page;
        return page;
    }

    /** 运维：API Token / 定时任务 / 告警 / 策略版本 ✓ */
    openOps(): OpsPage {
        const page = this._suitePage(OPS_TAB_ID, '平台 / 运维',
            'ops',
            () => new OpsPage({
                theme: this.theme,
                onCommand: (cmd, payload) => this.send(cmd, payload),
            }),
            'ops');
        this.opsPage = page;
        return page;
    }

    // -------------------------------------------------- 命令面板
    private _paletteCommands(): CommandItem[] {
        return [
            { label: '首页', hint: 'Home', run: () => this.openHome() },
            { label: '行情报价', hint: '搜索合约 / 双击看盘',
              run: () => this.openQuote() },
            { label: '实时图表（空白看盘）', hint: '空格搜索合约',
              run: () => this.openBlankChart() },
            { label: '本地图表', hint: 'CSV / 回放',
              run: () => this.openLocalChart() },
            { label: '图表工作台', hint: '当前打开的图表',
              run: () => this.openWorkspace() },
            { label: '回放实验室', hint: '本地图表回放',
              run: () => this.openReplayLab() },
            { label: '预警中心', hint: '全局价格预警',
              run: () => this.openAlertCenter() },
            /* 扩展功能入口暂时关闭：需要时再打开 ✓
            { label: '交易工作台', hint: '订单票 / 风控 / 审计',
              keywords: 'order trade risk audit',
              run: () => this.openWorkbench() },
            { label: '策略研究', hint: 'walk-forward / 实验库',
              keywords: 'research walk forward pareto',
              run: () => this.openResearch() },
            { label: '数据平台', hint: '质检 / 换月 / SQL',
              keywords: 'data parquet duckdb quality',
              run: () => this.openDataHub() },
            { label: '平台 / 运维', hint: 'Token / 定时任务 / 告警',
              keywords: 'ops token cron notify version',
              run: () => this.openOps() },
            */
            { label: '运行日志', hint: '后端日志',
              run: () => this.openLog() },
            { label: '设置', hint: '本地文件 / 图表 / 个性化',
              run: () => this.openSettings() },
            { label: '期货登录', hint: '天勤（模拟 / 实盘）',
              run: () => this.openLogin('futures') },
            { label: '股票连接', hint: '富途 OpenD',
              run: () => this.openLogin('stocks') },
            /* 扩展功能入口暂时关闭：需要时再打开 ✓
            { label: '工作台：对账', hint: '本地流水 vs 券商',
              keywords: 'reconcile',
              run: () => { this.openWorkbench();
                  this.send('workbench_reconcile', {}); } },
            { label: '工作台：导出审计 CSV', hint: '交易审计日志',
              run: () => { this.openWorkbench();
                  this.send('workbench_export', { table: 'audit' }); } },
            */
        ];
    }

    /** 全局命令面板（Ctrl / ⌘ + K）✓ */
    openPalette(): CommandPalette {
        if (!this.palette) {
            this.palette = new CommandPalette({
                theme: this.theme,
                commands: () => this._paletteCommands(),
            });
            this.root.appendChild(this.palette.element);
        }
        this.palette.applyTheme(this.theme);
        this.palette.open();
        return this.palette;
    }

    /** 打开「设置」页（顶栏页签，可关闭 ✓） */
    openSettings(section = 'personal'): SettingsPage {
        const id = SETTINGS_TAB_ID;
        if (!this.settingsPage) {
            const page = new SettingsPage({
                theme: this.theme,
                values: this.settingsValues,
                version: this.version,
                onSetting: (key, value) => this._onSetting(key, value),
                onCommand: (cmd, payload) => this.send(cmd, payload),
            });
            this.settingsPage = page;
            this.pages.set(id, page);
            this._addTab({ id, label: '设置', kind: 'settings' });
            this.stack.appendChild(page.element);
        }
        this.settingsPage.setTheme(this.theme);
        this.settingsPage.setValues({
            ...this.settingsValues, theme: this.theme,
        });
        this.activate(id);
        this.settingsPage.show(section);
        this.settingsButton?.classList.add('on');
        return this.settingsPage;
    }

    /** 设置页改了某一项 → 立即生效 + 交给后端落盘 ✓ */
    private _onSetting(key: string, value: unknown): void {
        if (key === 'app_theme') {
            this.applyTheme(value === 'light' ? 'light' : 'dark');
            this.send('set_theme', { theme: this.theme });
            this.settingsValues = { ...this.settingsValues, theme: this.theme };
            return;
        }
        if (key === 'chart_reset') {
            // ★ 必须交给后端统一恢复：后端会一起清掉
            //   `indicator_main/sub/custom_interval_ms` / `custom_new_bar`，
            //   再由 settings 补丁回推，前端按真实默认值重绘 ✓。
            //   以前前端手写 defaults（且没有指标刷新键）→ 指标刷新不恢复 ✗
            this.send('set_setting', { key: 'chart_reset', value: true });
            return;
        }
        this.settingsValues = { ...this.settingsValues, [key]: value };
        this.send('set_setting', { key, value });
        // 立即在前端生效（不用等后端回推 ✓）
        const charts = [...this.pages.values()].filter(
            (page): page is ChartPage | LocalChartPage =>
                page instanceof ChartPage || page instanceof LocalChartPage);
        if (key === 'position_line' || key === 'order_line') {
            // 立即作用到**所有**图表（不等后端回推 ✓）
            for (const page of charts) {
                (page as unknown as {
                    setChartConfig?: (item: Record<string, unknown>) => void;
                }).setChartConfig?.({ [key]: value });
            }
            return;
        }
        if (key === 'ui_zoom') {
            this._applyZoom(Number(value) || 0);
        } else if (key === 'theme_accent') {
            this._applyAccent(String(value || ''));
        } else {
            const patch = { [key]: value };
            for (const page of charts) {
                (page as unknown as {
                    setChartConfig?: (values: Record<string, unknown>) => void;
                }).setChartConfig?.(patch);
            }
            // 策略回测 / 参数优化页的图是 iframe，也要立即同步（字体 / 鼠标标签色 ✓）
            for (const page of this.strategyPages.values()) {
                page.setChartConfig?.(patch);
            }
        }
    }

    /** 后端推来的设置 → 一次性应用到界面 ✓ */
    private _applySettings(values: Record<string, unknown>): void {
        if (!values) return;
        if ('ui_zoom' in values) this._applyZoom(Number(values.ui_zoom) || 0);
        if ('theme_accent' in values) {
            this._applyAccent(String(values.theme_accent || ''));
        }
        if ('watch_default_group' in values) {
            this.home?.setDefaultGroup(String(values.watch_default_group || ''));
        }
        const chartKeys = ['chart_font_size', 'chart_color_up',
            'chart_color_down', 'chart_color_crosshair',
            'chart_crosshair_style', 'position_line', 'order_line',
            'editor_format_on_save'];
        if (chartKeys.some((key) => key in values)) {
            // 策略回测 / 参数优化页的图表是 iframe，也要跟着改字号 ✓
            for (const page of this.strategyPages.values()) {
                page.setChartConfig?.(values);
            }
            for (const page of this.pages.values()) {
                if (page instanceof ChartPage
                    || page instanceof LocalChartPage) {
                    (page as unknown as {
                        setChartConfig?: (item: Record<string, unknown>) => void;
                    }).setChartConfig?.(values);
                }
            }
        }
    }

    /** 界面缩放（`ui_zoom`：0 = 跟随系统 ✓） */
    /**
     * 界面缩放（`ui_zoom`：0 = 跟随系统 ✓）
     *
     * 用 `transform: scale()` 而不是 CSS `zoom`：
     * `.desk-root` 是 `position:absolute; inset:0`，`zoom` 在 QtWebEngine 里
     * 表现不一致（缩 125% 后右侧 / 底部留白 ✗）。`transform` 不影响布局，
     * 再配合 `width/height = 100%/z` 就刚好铺满视口 ✓
     */
    private _applyZoom(zoom: number): void {
        const value = Number(zoom) || 0;
        const root = this.root;
        if (value > 0 && Math.abs(value - 1) > 0.001) {
            root.style.zoom = '';
            root.style.inset = 'auto';
            root.style.left = '0';
            root.style.top = '0';
            root.style.right = 'auto';
            root.style.bottom = 'auto';
            root.style.width = `${100 / value}%`;
            root.style.height = `${100 / value}%`;
            root.style.transformOrigin = '0 0';
            root.style.transform = `scale(${value})`;
        } else {
            root.style.zoom = '';
            root.style.transform = '';
            root.style.transformOrigin = '';
            root.style.inset = '0';
            root.style.left = '';
            root.style.top = '';
            root.style.right = '';
            root.style.bottom = '';
            root.style.width = '';
            root.style.height = '';
        }
    }

    /** 当前主题色（启动时由 settings 补丁恢复 ✓） */
    private accent = '';

    /**
     * 主题色（`theme_accent`：空 = 用主题默认 accent ✓）
     *
     * ★ 同时写到 `html` 和 `body`：浅色主题的 `body.theme-light` 自己声明了
     *   `--desk-accent`，只写 html 会被 body 的 CSS 变量盖住（重启后按钮还
     *   是蓝色，用户实测 ✗）。
     */
    private _applyAccent(accent: string): void {
        this.accent = String(accent || '');
        for (const node of [document.documentElement, document.body]) {
            if (this.accent) {
                node.style.setProperty('--desk-accent', this.accent);
                // 选中 / 开启态的背景也从主题色派生（以前固定蓝色 ✗）
                node.style.setProperty('--desk-active',
                    `color-mix(in srgb, ${this.accent} 16%, transparent)`);
            } else {
                node.style.removeProperty('--desk-accent');
                node.style.removeProperty('--desk-active');
            }
        }
    }

    openChart(symbol: string, options: { name?: string; cycle?: number;
        blank?: boolean; label?: string } = {}): string {
        const id = `chart:${symbol}`;
        if (this.tabs.has(id)) {
            this.activate(id);
            return id;
        }
        if (this.tabs.size >= MAX_CHART_TABS + 1) {
            this.toast('warning',
                `最多同时打开 ${MAX_CHART_TABS} 个图表，请先关掉一些`);
            return id;
        }
        // ⚠ 这些回调是**创建时**闭包：切合约后 `page.symbol` 变了，
        //   闭包里的 `symbol` 仍是旧合约 → 周期 / 指标会被推到旧 tab，
        //   图表出现新旧合约混合 / 闪烁 ✗。统一走 currentSymbol()。
        let pageRef: ChartPage | null = null;
        const currentSymbol = () => pageRef?.symbol || symbol;
        const page = new ChartPage({
            symbol,
            theme: this.theme,
            name: options.name,
            cycle: options.cycle,
            onCycleChange: (cycle) => this.send('set_cycle', {
                symbol: currentSymbol(), cycle,
            }),
            onChartTypeChange: (kind) => this.send('set_chart_type', {
                symbol: currentSymbol(), kind,
            }),
            onIndicatorMenu: () => this.send('indicator_menu', {
                symbol: currentSymbol(),
            }),
            onCommand: (cmd, payload) => this.send(cmd, payload),
            onAddIndicator: (key, params) => this.send('add_indicator', {
                symbol: currentSymbol(), key, params: params || {},
            }),
            onToast: (level, text) => this.toast(level, text),
            favorites: this.favorites,
            strategyFavorites: this.strategyFavorites,
        });
        pageRef = page;
        page.element.style.display = 'none';
        this.stack.appendChild(page.element);
        this.pages.set(id, page);
        (page as unknown as {
            setChartConfig?: (values: Record<string, unknown>) => void;
        }).setChartConfig?.({ ...this.settingsValues });
        this._addTab({ id, label: options.label || symbol,
                       kind: 'chart', symbol });
        this.activate(id);
        // ★ 必须让后端推 K 线（以前只在前端建了空页 → 打开后没有图 ✗）
        // 空白实时图表（未连天勤）不请求后端，避免 `blank:` 非法合约告警 ✓
        if (!options.blank) {
            this.send('open_chart', {
                symbol, name: options.name, cycle: options.cycle,
            });
        }
        this.home?.recordRecent(symbol, options.name || '', 'chart');
        // 交易开关 / 是否实盘（开启下单按钮 + 二次确认 ✓）
        page.applyTheme(this.theme);
        // ★ 跨周期联动：任一 tab 拖动时间轴 → 其它 tab 按**时间**对齐 ✓
        page.onRangeChange = (from, to) => this._broadcastRange(id, from, to);
        this.send('trading_state', { symbol });
        this.send('alerts', {});
        this.send('favorites', {});
        this.send('templates', {});
        this.send('layouts', {});
        return id;
    }

    /**
     * 「＋ → 本地图表」：静态 CSV 图表（独立副本，不跟实时看盘共用 ✓）。
     * 不带 name 时先开一个空页，用户点左上角数据名选择内置 / 本地 CSV。
     */
    openLocalChart(name = ''): string {
        const id = `local:${name || 'new'}`;
        if (this.tabs.has(id)) {
            this.activate(id);
            if (name) this.send('local_load', { name, cell: 0 });
            return id;
        }
        if (this.tabs.size >= MAX_CHART_TABS + 1) {
            this.toast('warning',
                `最多同时打开 ${MAX_CHART_TABS} 个图表，请先关掉一些`);
            return id;
        }
        // ⚠ App/AccountDock 在**构造期间**就会发 `account` 命令；这时闭包里的
        //   `page` 还在 TDZ（`Cannot access 'page' before initialization` ✗）。
        //   用 ref + 函数取当前数据名，构造完再赋值 ✓
        let pageRef: LocalChartPage | null = null;
        const currentSymbol = () => pageRef?.symbol || name;
        const page = new LocalChartPage({
            symbol: name || '',
            theme: this.theme,
            // 编辑器打开时问一次：LSP 就绪就用，否则静默降级 ✓
            lsp: () => this.lspInfo || undefined,
            cycle: 60,
            onCycleChange: () => undefined,      // 周期固定，禁用 ✓
            onChartTypeChange: (kind) => pageRef?.setChartType(kind),
            onIndicatorMenu: () => this.send('indicator_menu', {
                symbol: pageRef?.symbolForCell(pageRef.activeCellIndex)
                    || currentSymbol(), local: true,
            }),
            onCommand: (cmd, payload) => {
                const localCmd = cmd === 'add_indicator'
                    ? 'local_add_indicator'
                    : (cmd === 'remove_indicator'
                        ? 'local_remove_indicator'
                        : (cmd === 'account_action'
                            ? 'local_account_action'
                            : (cmd === 'account' ? 'local_account' : cmd)));
                const body = (payload || {}) as Record<string, unknown>;
                const cell = Number(body.cell ?? pageRef?.activeCellIndex ?? 0);
                // ★ 指标命令按**格**取数据名：格 2 的 MA 不能用格 1 的 CSV 算
                //   （旧代码取 page.symbol，多布局下永远是第一格 ✗）
                const cellSymbol = pageRef?.symbolForCell(cell) || '';
                const indicatorCmd = cmd === 'add_indicator'
                    || cmd === 'remove_indicator';
                this.send(localCmd, {
                    ...body,
                    symbol: (indicatorCmd && cellSymbol)
                        ? cellSymbol : (body.symbol || currentSymbol()),
                    cell,
                    local: true,
                });
            },
            onAddIndicator: (key, params) => {
                const cell = pageRef?.activeCellIndex ?? 0;
                this.send('local_add_indicator', {
                    symbol: pageRef?.symbolForCell(cell) || currentSymbol(),
                    key, params: params || {},
                    cell,
                    local: true,
                });
            },
            onToast: (level, text) => this.toast(level, text),
            favorites: this.favorites,
            strategyFavorites: this.strategyFavorites,
            onStrategy: (path, mode) => this.openStrategyLab(path, mode),
        });
        pageRef = page;
        page.element.style.display = 'none';
        this.stack.appendChild(page.element);
        this.pages.set(id, page);
        (page as unknown as {
            setChartConfig?: (values: Record<string, unknown>) => void;
        }).setChartConfig?.({ ...this.settingsValues });
        this._addTab({ id, label: name || '本地图表', kind: 'local' });
        this.activate(id);
        if (name) this.home?.recordRecent(name, name, 'local');
        page.applyTheme(this.theme);
        this.send('local_list', {});
        this.send('local_account', { symbol: name });
        this.send('favorites', {});
        if (name) this.send('local_load', { name, cell: 0 });
        return id;
    }

    // ------------------------------------------------------------- strategy lab
    /** 编辑器「策略回测 / 参数优化」→ 独立策略 Tab（原本地图表保留）✓ */
    openStrategyLab(path: string,
                    mode: 'backtest' | 'optimize' = 'backtest'): string {
        const file = String(path || '');
        if (!file) return '';
        for (const page of this.strategyPages.values()) {
            if (page.file === file && page.mode === mode) {
                this.activate(page.id);
                return page.id;
            }
        }
        const id = `strategy:${mode}:${++this.strategySeq}`;
        const source = this.activeId.startsWith('local:')
            ? this.activeId
            : (this.tabs.has('local:new') ? 'local:new' : this.activeId);
        const name = file.replace(/^.*[\\/]/, '').replace(/\.py$/i, '') || '策略';
        const page = new StrategyLabPage({
            id, file, mode, theme: this.theme, sourceId: source,
            fontSize: Number(this.settingsValues.chart_font_size) || 13,
            crosshairColor: String(this.settingsValues.chart_color_crosshair || ''),
            onCommand: (cmd, payload) => this.send(cmd, {
                ...(payload || {}), id,
            }),
            onExit: () => this.closeTab(id),
            onToast: (level, text) => this.toast(level, text),
            onWriteParams: (params) => {
                const sourcePage = this.pages.get(source);
                if (sourcePage instanceof LocalChartPage) {
                    sourcePage.openEditor();
                    sourcePage.editorPanel?.applyParams(file, params);
                } else {
                    this.toast('warning', '找不到原本地图表编辑器');
                }
            },
        });
        page.hide();
        this.strategyPages.set(id, page);
        this.strategySources.set(id, source);
        this.pages.set(id, page);
        this.stack.appendChild(page.element);
        this._addTab({
            id,
            label: `${mode === 'optimize' ? '优化' : '回测'}: ${name}`,
            kind: 'strategy',
        });
        this.activate(id);
        this.send('strategy_start', { id, file, mode });
        return id;
    }

    closeTab(id: string): void {
        if (id === HOME_TAB_ID) return;       // 首页固定，不可关闭 ✓
        const sourceTab = this.strategySources.get(id) || '';
        const page = this.pages.get(id);
        if (page instanceof ChartPage) {
            page.destroy();
            this.send('close_chart', { symbol: page.symbol });
        } else if (page instanceof LocalChartPage) {
            page.destroy();
        } else if (page instanceof StrategyLabPage) {
            this.send('strategy_cancel', { id });
            page.destroy();
            this.strategyPages.delete(id);
            this.strategySources.delete(id);
            // ★ 关掉回测 / 优化页 → 编辑器里的「策略回测 / 参数优化」要能再点 ✓
            this._refreshEditors();
        } else if (page instanceof SettingsPage) {
            this.settingsPage = null;
            this.settingsButton?.classList.remove('on');
        } else if (id === LOG_TAB_ID) {
            this.logPage = null;          // 关掉后重新打开会带最新缓冲 ✓
        } else if (id === WORKSPACE_TAB_ID) {
            this.workspacePage = null;
        } else if (id === REPLAY_LAB_TAB_ID) {
            this.replayLabPage = null;
        } else if (id === ALERT_CENTER_TAB_ID) {
            this.alertCenter = null;
        } else if (id === WORKBENCH_TAB_ID) {
            this.workbenchPage = null;
        } else if (id === RESEARCH_TAB_ID) {
            this.researchPage = null;
        } else if (id === DATAHUB_TAB_ID) {
            this.datahubPage = null;
        } else if (id === OPS_TAB_ID) {
            this.opsPage = null;
        } else if (id === QUOTE_TAB_ID) {
            this.quoteRequested = false;
            this.quotePage = null;
            this.preview?.hide();
            this.preview?.element.remove();
            this.preview = null;
        }
        for (const [url, tabId] of [...this.webTabs]) {
            if (tabId === id) this.webTabs.delete(url);
        }
        page?.element.remove();
        this.pages.delete(id);
        this.tabs.delete(id);
        this.buttons.get(id)?.remove();
        this.buttons.delete(id);
        if (this.activeId !== id) return;
        if (sourceTab && this.tabs.has(sourceTab)) {
            this.activate(sourceTab);
            return;
        }
        if (this.tabs.has(HOME_TAB_ID)) {
            this.activate(HOME_TAB_ID);
            return;
        }
        const fallback = [...this.tabs.keys()].pop();
        if (fallback) this.activate(fallback);
        else this.openLocalChart();
    }

    activate(id: string): void {
        if (!this.tabs.has(id)) return;
        closeMenu();
        if (id !== QUOTE_TAB_ID) this.preview?.hide();
        // ★ 离开报价页 → 可见范围为空 → 后端把股票订阅全退掉
        //   （富途正股额度只有 100，不退就会越滚越多 ✗）
        if (this.activeId === QUOTE_TAB_ID && id !== QUOTE_TAB_ID) {
            this.send('visible', { keys: [], hidden: true });
        }
        this.activeId = id;
        for (const [key, button] of this.buttons) {
            button.classList.toggle('on', key === id);
        }
        for (const [key, page] of this.pages) {
            if (page instanceof SettingsPage) {
                page.element.style.display = key === id ? 'flex' : 'none';
                continue;
            }
            if (key === id) page.show();
            else page.hide();
        }
        // ★ 上报"哪些页面可见"：首页 / 报价页没打开时后端**不拉报价**
        //   （实盘 query_quotes 可能卡几秒，后台空转会把界面拖住 ✓）
        this.send('ui_state', {
            home: id === HOME_TAB_ID,
            quote: id === QUOTE_TAB_ID,
            chart: (this.tabs.get(id) || {} as { kind?: string }).kind === 'chart',
        });
        // ★ 首页可见性：不可见时后端停止刷新 home；避免离线时加载 ✓
        const homeVisible = id === HOME_TAB_ID;
        if (homeVisible !== this.homeActive) {
            this.homeActive = homeVisible;
            if (this.initialRouted) {
                this.send('home', { active: homeVisible });
            }
        }
        const page = this.pages.get(id);
        if (page instanceof ChartPage || page instanceof LocalChartPage) {
            page.resize();
        }
    }

    // ------------------------------------------------------------- quote page
    /** 左键气泡（首页 / 报价页共用；按需创建，**不**建报价页 ✓） */
    private _ensurePreview(): SymbolPreview {
        if (!this.preview) {
            this.preview = new SymbolPreview((symbol) => this.send(
                'open_chart', { symbol, cycle: undefined }));
            this.root.appendChild(this.preview.element);
        }
        return this.preview;
    }

    /** 行情报价 / 右键「加入自选」→ 加进某个分组（自选 / 黑色系 / 自建 ✓） */
    addToWatchGroup(groupId: string, symbol: string): void {
        if (!symbol || !groupId) return;
        addToGroup(groupId, symbol);
        this.home?.refreshWatch();
        // 让后端补这些合约的报价（首页自选行才有价 ✓）
        const symbols = new Set<string>();
        for (const group of writableGroups()) {
            for (const item of groupSymbols(group.id)) symbols.add(item);
        }
        this._syncHomeSymbols();
        this.toast('success', `已加入自选：${symbol}`);
    }

    /**
     * 把「收藏 + 各分组手动加入」的合约同步给后端 ✓
     *
     * 后端会把它们并进首页自选，**每 2 秒跟着刷新**（迷你图 / 自选行实时 ✓）
     */
    private _syncHomeSymbols(): void {
        const symbols = new Set<string>(watchFavorites());
        for (const group of writableGroups()) {
            for (const item of groupSymbols(group.id)) symbols.add(item);
        }
        this.send('home_symbols', { symbols: [...symbols] });
        this.send('watch_set', watchSnapshot());     // ★ 顺便落盘 ✓
    }

    private _createQuotePage(): QuotePage {
        const page = new QuotePage({
            favorites: watchFavorites(),
            onToggleFavorite: (symbol) => {
                toggleWatchFavorite(symbol);
                this.home?.refreshWatch();
                this._syncHomeSymbols();
                return watchFavorites();
            },
            onRowClick: (key, row, at) => this.send('row_click', {
                symbol: key, name: row?.name, x: at.x, y: at.y,
            }),
            onRowDoubleClick: (key, row) => this.send('open_chart', {
                symbol: key, name: row?.name, cycle: undefined,
            }),
            onRowContext: (key, row, event) => this.send('context_menu', {
                symbol: key, name: row?.name,
                x: Math.round(event.clientX), y: Math.round(event.clientY),
            }),
            onFilterChange: (filter) => {
                // 换交易所 / 换类型 → 旧的那批股票立刻退订 ✓
                this.send('visible', { keys: [], hidden: true });
                this.send('filter', filter);
            },
            onVisibleChange: (keys) => this.send('visible', { keys }),
            onRefresh: () => this.send('reload_contracts', {}),
            onExportEmpty: () => this.toast('warning', '当前列表没有数据'),
            onGlobalSearch: (text) => this.send('symbol_search', { text }),
            onTickerSetting: (key, value) => this.send('set_setting', {
                key, value,
            }),
            onTickerRefresh: () => this.send('ticker_refresh', {}),
            onOpenSymbol: (symbol, name) => this.send('open_chart', {
                symbol, name,
            }),
            onExportHistory: () => this.send('exports', {}),
            onOpenExport: (path, folder) => this.send('open_export', {
                path, folder: !!folder,
            }),
            onExportRemove: (path) => this.send('export_remove', { path }),
            onExportClear: () => this.send('exports_clear', {}),
            onExportCsv: (filename, text) => {
                this.send('export_csv', { name: filename, text });
                return true;
            },
        });
        page.element.classList.add('on');
        this.stack.appendChild(page.element);
        this.pages.set(QUOTE_TAB_ID, page);
        this.quotePage = page;
        page.setSettings?.({ ...this.settingsValues });
        page.applyTheme(this.theme);          // ★ 报价页后建也要跟主题 ✓
        // 左键气泡（挂在 root 上：切换 tab 也保留倒计时 ✓）
        this._ensurePreview();
        return page;
    }

    // ------------------------------------------------------------- patches
    /** Single entry point used by every backend (`window.__desk.applyPatch`). */
    applyPatch(patch: Record<string, any>): void {
        if (!patch || typeof patch !== 'object') return;
        switch (patch.type) {
            case 'boot':
                this.autoHome = !!patch.home;
                // 编辑器要的 jedi LSP：启动时就拉起来（幂等、几十毫秒 ✓）
                this.send('lsp_start', {});
                if (patch.theme) this.applyTheme(patch.theme);
                if (patch.markets) {
                    this.markets = {
                        futures: !!patch.markets.futures,
                        stocks: !!patch.markets.stocks,
                        offline: !!patch.markets.offline,
                        no_service: !!patch.markets.no_service,
                    };
                    this.home?.setMarkets(this.markets);
                }
                // ★ title 是**窗口 / 浏览器标题**，不再拿来改「行情报价」
                //   页签（用户要求：标题栏 = minibt桌面端，页签仍是行情报价 ✓）
                if (patch.title) document.title = String(patch.title);
                this._routeInitial();
                break;
            case 'markets': {
                // 登录成功 / 断线 → 数据源状态、首页、菜单立刻更新 ✓
                const markets = patch.markets || {};
                this.markets = {
                    futures: !!markets.futures,
                    stocks: !!markets.stocks,
                    offline: !!markets.offline,
                    no_service: !!markets.no_service,
                };
                this.home?.setMarkets(this.markets);
                this._setStatus();
                break;
            }
            case 'login': {
                // ★ 只在登录框**开着**时更新它（别被后台补丁弹出来 ✗）
                const dialog = this.login;
                if (!dialog) break;
                dialog.setTheme(this.theme);
                const kind = patch.kind === 'stocks' ? 'stocks' : 'futures';
                if (patch.saved) dialog.setSaved(kind, patch.saved);
                else dialog.setState(patch);
                break;
            }
            case 'types':
                if (!this.quoteRequested) { this._queueQuote(patch); break; }
                this._ensureQuoteTab();
                this.quotePage?.setTypes(patch.items || [], patch.current);
                break;
            case 'exchanges':
                if (!this.quoteRequested) { this._queueQuote(patch); break; }
                this._ensureQuoteTab();
                this.quotePage?.setExchanges(patch.items || [], patch.current);
                break;
            case 'option_mode':
                if (!this.quoteRequested) { this._queueQuote(patch); break; }
                this.quotePage?.setOptionMode(!!patch.on);
                break;
            case 'rows_loading': {
                if (!this.quoteRequested) { this._queueQuote(patch); break; }
                this._ensureQuoteTab();
                this.quotePage?.setLoading(true, String(patch.text || ''));
                break;
            }
            case 'rows':
                if (!this.quoteRequested) { this._queueQuote(patch); break; }
                if (patch.rows?.length) {
                    if (patch.replace === false) {
                        // chunked streaming of the first payload
                        this.quotePage?.appendRows(patch.rows);
                    } else {
                        this.quotePage?.setRows(patch.rows);
                    }
                } else if (patch.replace) {
                    this.quotePage?.setRows([]);
                }
                break;
            case 'rows_update':
                if (!this.quoteRequested) { this._queueQuote(patch); break; }
                if (patch.rows?.length) this.quotePage?.updateRows(patch.rows);
                break;
            case 'ticker':
                if (!this.quoteRequested) { this._queueQuote(patch); break; }
                if (patch.items?.length) this.quotePage?.setTicker(patch.items);
                break;
            case 'home':
                this.home?.setPayload(patch as never);
                break;
            case 'home_update':
                this.home?.setUpdate(patch as never);
                break;
            case 'home_account':
                this.home?.setAccount(patch.account as never);
                break;
            case 'watch': {
                applyWatchState({
                    favorites: (patch.favorites || []) as string[],
                    groups: (patch.groups || []) as never,
                    pins: (patch.pins || {}) as never,
                });
                this.quotePage?.setFavorites(watchFavorites());
                this.home?.refreshWatch();
                // ★ 启动时拿到「上次保存的收藏 / 分组」→ 告诉后端去拉报价
                //   （否则首页收藏行 / 迷你图一直是 `--` ✗）
                const symbols = new Set<string>(watchFavorites());
                for (const group of writableGroups()) {
                    for (const item of groupSymbols(group.id)) symbols.add(item);
                }
                if (symbols.size) {
                    this.send('home_symbols', { symbols: [...symbols] });
                }
                break;
            }
            case 'web_page':
                this.setWebPage(patch as never);
                break;
            case 'lsp': {
                this.lspInfo = patch.status === 'ready' && patch.url
                    ? { url: String(patch.url), root: String(patch.root || '') }
                    : null;
                this.lspStatus = String(patch.status || '');
                this.lspError = String(patch.error || '');
                if (this.lspStatus === 'missing') {
                    this.toast('warning',
                               `编辑器智能提示不可用：${this.lspError}`,
                               [], undefined, 'top');
                }
                break;
            }
            case 'alert':            // 体检不通过 / 加到图表失败 → 弹窗提醒 ✓
                this.showAlert(patch as unknown as {
                    title?: string; message?: string; detail?: string;
                    level?: string;
                });
                break;
            case 'strategy_manage':
                // 「策略管理」弹窗：所有图表的策略 + 两个运行开关 ✓
                this.showStrategyManage(patch);
                break;
            case 'strategy_live': {
                // 策略实盘 / 模拟盘的运行状态（按钮变「运行中 PID」✓）
                const running = !!patch.running;
                this._forEditors((page) => (page as never as {
                    setStrategyLive?: (p: Record<string, any>) => void;
                }).setStrategyLive?.(patch));
                this.toast(running ? 'success' : 'info',
                    running
                        ? `策略实盘已启动：${String(patch.file || '')
                            .split(/[\/]/).pop()}`
                        : '策略实盘已停止');
                break;
            }
            case 'strategy_reload': {
                // 指标参数改了 → 后端重建了 HTML → 让页面重新装载 iframe ✓
                const page = this.strategyPages.get(String(patch.id || ''));
                page?.reloadCharts?.();
                break;
            }
            case 'strategy_check':
                this._forEditors((page) => page.setStrategyCheck?.(patch));
                break;
            case 'editor_help':
                this._showEditorHelp(String(patch.text || ''));
                break;
            case 'home_main':
                this.home?.setMainRows(patch as never);
                break;
            case 'home_preview':
                this.home?.setPreviewBars(patch as never);
                break;
            case 'home_symbols':
                this.home?.setUpdate({ rows: patch.rows || [] } as never);
                break;
            case 'strategy_state': {
                const id = String(patch.id || '');
                const page = this.strategyPages.get(id);
                page?.setState(patch);
                // ★ 页签标题用**策略/指标类名**（"回测: 文件名" 不直观 ✗）
                const names = (patch.strategies || []) as Array<{ name?: string }>;
                const first = names.length ? String(names[0].name || '') : '';
                if (first) {
                    const tab = this.tabs.get(id);
                    const label = `${patch.mode === 'optimize' ? '优化' : '回测'}: ${first}`;
                    if (tab && tab.label !== label) {
                        tab.label = label;
                        const button = this.buttons.get(id);
                        const span = button?.querySelector('span');
                        if (span) span.textContent = label;
                    }
                }
                break;
            }
            case 'strategy_result': {
                const page = this.strategyPages.get(String(patch.id || ''));
                page?.setResult(patch as never);
                break;
            }
            case 'strategy_chart': {
                const page = this.strategyPages.get(String(patch.id || ''));
                page?.setChart(patch);
                break;
            }
            case 'strategy_chart_file': {
                const page = this.strategyPages.get(String(patch.id || ''));
                page?.setChartFile(patch);
                break;
            }
            case 'strategy_trades': {
                const page = this.strategyPages.get(String(patch.id || ''));
                page?.setTrades((patch.rows || []) as never);
                break;
            }
            case 'strategy_opt': {
                const page = this.strategyPages.get(String(patch.id || ''));
                page?.setOptimization(patch);
                break;
            }
            case 'strategy_error': {
                const page = this.strategyPages.get(String(patch.id || ''));
                page?.setError(String(patch.message || ''));
                break;
            }
            case 'strategy_progress': {
                const page = this.strategyPages.get(String(patch.id || ''));
                page?.setProgress(Number(patch.current) || 0,
                    Number(patch.total) || 0,
                    String(patch.text || ''));
                break;
            }
            case 'strategy_log': {
                // ★ 回测 / 优化后台日志不能丢：进全局日志页 + 缓冲 ✓
                const text = String(patch.line || patch.text || '');
                const ts = String(patch.ts || '');
                if (text) {
                    this.logBuffer.push({ text, level: 'info', ts });
                    if (this.logBuffer.length > LOG_BUFFER) {
                        this.logBuffer.splice(0,
                            this.logBuffer.length - LOG_BUFFER);
                    }
                    this.logPage?.append(text, 'info', ts);
                }
                break;
            }
            case 'open_tab':
                this.openChart(String(patch.symbol || ''), {
                    name: patch.name, cycle: patch.cycle,
                });
                break;
            case 'close_tab':
                if (patch.symbol) this.closeTab(`chart:${patch.symbol}`);
                break;
            case 'kline': {
                const page = this._chartPageFor(String(patch.symbol || ''));
                if (page instanceof ChartPage) {
                    const bars = patch.bars || [];
                    if (patch.cell) {
                        page.setCellBars(Number(patch.cell), bars,
                                         patch.replace !== false);
                    } else {
                        page.setBars(bars, patch.replace !== false);
                    }
                }
                break;
            }
            case 'ui_action': {
                // ★ 后端（`Gui.Desk` / btplot / Bt）让前端**建页面**用的补丁：
                //   页面归前端所有，后端只能"请求"，不能自己建 ✓
                const action = String(patch.action || '');
                const name = String(patch.name || '');
                const file = String(patch.file || '');
                if (action === 'open_local_chart') {
                    // name 为空 = 空白本地图表页（Gui.Desk 策略会随后自动选 CSV）✓
                    this.openLocalChart(name);
                } else if (action === 'open_strategy_lab' && file) {
                    this.openStrategyLab(file,
                        patch.mode === 'optimize' ? 'optimize' : 'backtest');
                } else if (action === 'open_home') {
                    this.openHome();
                }
                break;
            }
            case 'workbench':
                this.workbenchPage?.apply(patch);
                break;
            case 'research':
            case 'research_state':
            case 'research_progress':
            case 'research_result':
            case 'research_error':
                this.researchPage?.apply(patch);
                break;
            case 'datahub':
            case 'datahub_quality':
            case 'datahub_result':
            case 'datahub_query':
                this.datahubPage?.apply(patch);
                break;
            case 'ops':
            case 'ops_token':
            case 'ops_tasks':
            case 'ops_notify':
            case 'ops_versions':
                this.opsPage?.apply(patch);
                break;
            case 'preview': {
                const data = patch.data || {};
                if (!this.preview) this._ensurePreview();
                if (patch.hide) {
                    this.preview?.hide();
                } else {
                    this.preview?.show(data, Number(patch.x) || 0,
                                       Number(patch.y) || 0);
                }
                break;
            }
            case 'menu': {
                const items = (patch.items || []) as Array<Record<string, any>>;
                const symbol = String(patch.symbol || '');
                const mapped: Array<{
                    label: string; disabled?: boolean; separator?: boolean;
                    submenu?: MenuItem[];
                    run?: () => void;
                }> = items.map((item) => {
                    // ★ 支持**二级菜单**（「周期 ›」里列所有周期 ✓）
                    const sub = (item.submenu || []) as Array<
                        Record<string, any>>;
                    const entry: {
                        label: string; disabled?: boolean;
                        separator?: boolean; submenu?: MenuItem[];
                        run?: () => void;
                    } = {
                        label: String(item.label || ''),
                        disabled: !!item.disabled,
                        separator: !!item.separator,
                    };
                    if (sub.length) {
                        entry.submenu = sub.map((child) => ({
                            label: String(child.label || ''),
                            run: () => this.send('open_chart', {
                                symbol: patch.symbol,
                                name: patch.name,
                                cycle: child.cycle,
                            }),
                        }));
                    } else {
                        entry.run = () => this.send('open_chart', {
                            symbol: patch.symbol,
                            name: patch.name,
                            cycle: item.cycle,
                        });
                    }
                    return entry;
                });
                // ★ 右键「加入自选 ›」：子菜单 = 自选 / 黑色系 / 有色金属 /
                //   股指期货 / 能源化工 + 用户自建的分组（用户要求 ✓）
                if (symbol) {
                    mapped.push({
                        label: isFavorite(symbol) ? '取消收藏' : '加入收藏',
                        separator: true,
                        run: () => {
                            toggleWatchFavorite(symbol);
                            this.quotePage?.setFavorites(watchFavorites());
                            this.home?.refreshWatch();
                            this._syncHomeSymbols();
                        },
                    }, {
                        label: '加入自选',
                        submenu: writableGroups().map((group) => ({
                            label: group.label,
                            run: () => this.addToWatchGroup(group.id, symbol),
                        })),
                    });
                }
                showMenu(Number(patch.x) || 0, Number(patch.y) || 0, mapped);
                break;
            }
            case 'close_menu':
                closeMenu();
                break;
            case 'settings': {
                const settings = (patch.settings || {}) as Record<string, unknown>;
                this.settingsValues = settings as SettingsValues;
                this._applySettings(settings);          // 缩放 / 主题色 / 图表项 ✓
                this.settingsPage?.setValues({
                    ...this.settingsValues, theme: this.theme,
                });
                this.quotePage?.setSettings?.(settings);
                this.pages.forEach((page) => {
                    if (page instanceof ChartPage
                        || page instanceof LocalChartPage) {
                        page.setSettings(settings);
                    }
                });
                break;
            }
            case 'sim_analysis': {
                // 设置页「模拟账户」：权益曲线 / 各品种盈亏 / 统计表 ✓
                this.settingsPage?.setSim(patch as never);
                break;
            }
            case 'book': {
                const page = this.pages.get(`chart:${patch.symbol}`);
                if (page instanceof ChartPage) page.setBook(patch as never);
                break;
            }
            case 'position': {
                const sides = {
                    long: (patch.long ?? null) as never,
                    short: (patch.short ?? null) as never,
                };
                const symbol = String(patch.symbol || '');
                // ★ 本地模拟账户的持仓线：本地图表（`local:true`）和
                //   看盘窗口回放都会推这个补丁 ✓
                if (patch.local) {
                    const locals = [...this.pages.values()].filter(
                        (item): item is LocalChartPage =>
                            item instanceof LocalChartPage);
                    const matched = locals.filter(
                        (item) => item.localDataName === symbol);
                    for (const page of (matched.length ? matched : locals)) {
                        // ★ 带格子号 → 画到**那一格**（多布局各自持仓线 ✓）
                        (page as unknown as {
                            setPosition: (p: unknown, cell?: number) => void;
                        }).setPosition(sides, typeof patch.cell === 'number'
                            ? patch.cell : undefined);
                    }
                    break;
                }
                const page = this.pages.get(`chart:${symbol}`)
                    || this._chartPageFor(symbol);
                if (page instanceof ChartPage) {
                    // ★ 多布局：`patch.cell` 决定画到哪一格（每格各自的持仓线 ✓）
                    page.setPosition(sides, typeof patch.cell === 'number'
                        ? patch.cell : 0);
                }
                break;
            }
            case 'orders': {
                // ★ 挂单线：天勤模拟 → 看盘窗口；本地模拟 → 本地图表 ✓
                const items = (patch.items || []) as never;
                const symbol = String(patch.symbol || '');
                if (patch.local) {
                    const locals = [...this.pages.values()].filter(
                        (item): item is LocalChartPage =>
                            item instanceof LocalChartPage);
                    const matched = locals.filter(
                        (item) => item.localDataName === symbol);
                    for (const page of (matched.length ? matched : locals)) {
                        page.setOrders(items, typeof patch.cell === 'number'
                            ? patch.cell : 0);
                    }
                    break;
                }
                const page = this._chartPageFor(symbol);
                if (page instanceof ChartPage) {
                    page.setOrders(items, typeof patch.cell === 'number'
                        ? patch.cell : 0);
                }
                break;
            }
            case 'account': {
                if (!patch.symbol) this.home?.setAccount(patch as never);
                const page = this._chartPageFor(
                    String(patch.symbol || ''));
                if (page instanceof ChartPage) page.setAccount(patch as never);
                break;
            }
            case 'log': {
                const text = String(patch.text || '');
                const level = String(patch.level || 'info');
                const ts = String(patch.ts || '');
                // ★ 所有日志：缓冲 + 独立日志页 + 底部面板（三处都有 ✓）
                this.logBuffer.push({ text, level, ts });
                if (this.logBuffer.length > LOG_BUFFER) {
                    this.logBuffer.splice(0,
                        this.logBuffer.length - LOG_BUFFER);
                }
                this.logPage?.append(text, level, ts);
                const page = this._chartPageFor(
                    String(patch.symbol || ''));
                if (page instanceof ChartPage) {
                    page.appendLog(text, level, ts);
                }
                for (const local of this.pages.values()) {
                    if (local instanceof LocalChartPage) local.appendLog(
                        text, level, ts);
                }
                break;
            }
            case 'table_rows': {
                // 表格跟随鼠标：后端按行重算后只更新 tbody ✓
                for (const page of this.pages.values()) {
                    (page as unknown as {
                        setTableRows?: (p: { key?: string;
                            rows?: string[][] }) => void;
                    }).setTableRows?.(patch as never);
                }
                break;
            }
            case 'indicator': {
                const page = this.pages.get(`chart:${patch.symbol}`);
                if (page instanceof ChartPage) page.setIndicators(patch as never);
                break;
            }
            case 'indicator_menu': {
                const incoming = (patch.items || []) as Array<Record<string, any>>;
                // 编辑器保存后推的「个人指标」只是**刷新数据**，不该弹菜单 ✗
                if (patch.personal) {
                    this.personalIndicators = incoming as never;
                    break;
                }
                // 把之前存下的个人指标并进菜单（保存后不用重启就能加 ✓）
                const seen = new Set(incoming.map((item) => item.key));
                const items = incoming.concat(this.personalIndicators.filter(
                    (item) => !seen.has(item.key))) as Array<
                    Record<string, any>>;
                const local = this._activeLocalPage();
                const page = this._activeChartPage();
                if (!local && !page) break;
                const anchor = document.querySelector(
                    '.desk-chart-toolbar') as HTMLElement | null;
                const localCell = local?.activeCellIndex ?? 0;
                const target = local
                    ? local.symbolForCell(localCell)
                    : (patch.symbol || page?.symbol || '');
                const addCmd = local ? 'local_add_indicator' : 'add_indicator';
                const removeCmd = local ? 'local_remove_indicator'
                    : 'remove_indicator';
                openIndicatorMenu(anchor, items as never,
                    (key, params) => this.send(addCmd, {
                        symbol: target, key, params, local: !!local,
                        ...(local ? { cell: localCell } : {}),
                    }),
                    {
                        onImport: (kind) => this.send('pick_personal', { kind }),
                        onManage: () => this.send('personal_menu', {}),
                        onClear: () => this.send(removeCmd, {
                            symbol: target, key: '*', local: !!local,
                            ...(local ? { cell: localCell } : {}),
                        }),
                    });
                break;
            }
            // ---- 本地图表（静态 CSV + 本地模拟账户）----
            case 'local_data': {
                for (const page of this.pages.values()) {
                    if (page instanceof LocalChartPage) {
                        page.setLocalData((patch.items || []) as never,
                                          (patch.folders || []) as never);
                    }
                }
                // ★ 离线启动：自动加载第一个内置 CSV（有数据才有意义 ✓）
                if (this.pendingLocalAutoLoad) {
                    this.pendingLocalAutoLoad = false;
                    const items = (patch.items || []) as Array<Record<string, any>>;
                    const first = items.find((item) => item.source === '内置')
                        || items[0];
                    if (first?.name) {
                        this.send('local_load', {
                            name: String(first.name), cell: 0,
                        });
                    }
                }
                break;
            }
            case 'local_kline': {
                const name = String(patch.name || '');
                const page = (name
                    ? this.pages.get(`local:${name}`) : null)
                    || this._activeLocalPage()
                    || ([...this.pages.values()].find(
                        (item) => item instanceof LocalChartPage
                            && item.localDataName === name) as
                        LocalChartPage | undefined);
                if (page instanceof LocalChartPage) {
                    page.setLocalBars(patch as never);
                    if (name) this.home?.recordRecent(name, name, 'local');
                }
                break;
            }
            case 'local_indicator': {
                const symbol = String(patch.symbol || '');
                const page = this.pages.get(`local:${symbol}`)
                    || this._activeLocalPage()
                    || ([...this.pages.values()].find(
                        (item) => item instanceof LocalChartPage
                            && item.localDataName === symbol) as
                        LocalChartPage | undefined);
                if (page instanceof LocalChartPage) {
                    page.setCellLocalIndicators(
                        Number(patch.cell) || 0, patch as never);
                }
                break;
            }
            case 'local_account': {
                for (const page of this.pages.values()) {
                    if (page instanceof LocalChartPage) {
                        page.setLocalAccount(patch as never);
                    }
                }
                break;
            }
            case 'personal_menu':
                showPersonalManager(
                    (patch.items || []) as Array<{ category: string;
                        path: string; kind: string }>,
                    (category) => this.send('drop_personal', { category }));
                break;
            case 'symbol_search': {
                // 报价页搜索框也能用（「其他市场」列表 ✓）
                // 报价页搜索框的「其他市场」列表（不管当前在哪个 tab ✓）
                this.quotePage?.setGlobalResults((patch.items || []) as never);
                const page = this._activeChartPage();
                if (page) {
                    page.setSearchResults(
                        (patch.items || []) as never,
                        (patch.markets || []) as never,
                        String(patch.market || ''),
                        Number(patch.total || 0),
                        !!patch.loading);
                }
                break;
            }
            case 'editor_files':
            case 'editor_file':
            case 'editor_saved':
            case 'editor_check':
            case 'explorer':
            case 'explorer_op':
            case 'explorer_personal':
            case 'editor_formatted':
            case 'editor_deleted': {
                // 看盘窗口 / **本地图表**都有编辑器（P68 ✓）
                const page = (this.pages.get(this.activeId) || null) as
                    | ChartPage | LocalChartPage | null;
                const panel = page?.editorPanel;
                if (!panel) break;
                if (patch.type === 'editor_files') {
                    // 老补丁（个人指标 / 策略两栏）已被资源管理器取代 → 忽略 ✓
                    break;
                } else if (patch.type === 'editor_file') {
                    panel.setFile((patch.file || {}) as never);
                } else if (patch.type === 'editor_saved') {
                    panel.markSaved(String(patch.path || ''));
                    if (typeof patch.text === 'string') {
                        panel.setFormatted(String(patch.path || ''),
                                           String(patch.text), 'save');
                    }
                } else if (patch.type === 'editor_check') {
                    panel.setCheck(String(patch.path || ''),
                                   (patch.result || {}) as never);
                } else if (patch.type === 'explorer') {
                    panel.setExplorer(patch as never);
                } else if (patch.type === 'explorer_personal') {
                    panel.setPersonalKind((patch.kind || '') as never);
                } else if (patch.type === 'editor_formatted') {
                    panel.setFormatted(String(patch.path || ''),
                                       String(patch.text || ''),
                                       String(patch.tool || 'basic'));
                } else if (patch.type === 'editor_deleted') {
                    panel.remove(String(patch.path || ''));
                }
                // `explorer_op` 只用来刷界面（结果已经由 explorer 补丁带回 ✓）
                break;
            }
            case 'ask_folder': {
                // ★ 选择目录一律走**系统**对话框（后端 `choose_directory`）：
                //   这里只在极端情况下（没 GUI / 没 tkinter）提示，不再让用户
                //   手输路径（用户要求 ✓）
                this.toast('warning',
                    '当前环境没有系统文件夹对话框：请用桌面版，'
                    + '或把目录放到默认位置（设置 → 本地文件）');
                break;
            }
            case 'history_bars': {
                const page = this._activeChartPage();
                page?.prependHistory((patch.bars || []) as never,
                                     !!patch.exhausted);
                break;
            }
            case 'sprite': {
                // 键盘精灵的搜索结果（空格键 → 指标 / 策略 / 合约 / 股票 ✓）
                const page = this._activeChartPage();
                const local = this._activeLocalPage();
                const hint = String(patch.text || '')
                    ? `共 ${Number(patch.total || 0)} 项 · `
                      + '↑↓ 选择 · Enter 确认 · Esc 关闭'
                    : '↑↓ 选择 · Enter 确认 · Esc 关闭';
                if (local) {
                    local.setSpriteResults((patch.items || []) as never, hint);
                } else if (page) {
                    page.setSpriteResults((patch.items || []) as never, hint);
                }
                break;
            }
            case 'default_realtime': {
                // 「＋ → 实时图表」：天勤连接后默认打开主力 / 上期所第一个合约；
                // 未连接时后端返回空 symbol → 空白图表 + 商品搜索 ✓
                if (!this.pendingRealtime) break;
                this.pendingRealtime = false;
                const symbol = String(patch.symbol || '');
                if (symbol) {
                    this.openChart(symbol, {
                        name: String(patch.name || '实时图表'),
                    });
                } else {
                    this._openBlankChartFallback();
                }
                break;
            }
            case 'symbol_index': {
                // 全市场索引建好了 → 让搜索框显示 chips（几万个合约 ✓）
                const page = this._activeChartPage();
                if (page) {
                    page.setSearchMarkets((patch.markets || []) as never,
                                          Number(patch.count || 0));
                }
                break;
            }
            case 'switch_symbol': {
                this._renameChart(String(patch.old || ''),
                                  String(patch.new || ''),
                                  String(patch.name || ''));
                break;
            }
            case 'favorites': {
                if (patch.kind === 'strategy') {
                    this.strategyFavorites = (patch.items || []) as never;
                } else {
                    this.favorites = (patch.items || []) as never;
                }
                const strategies = (patch.strategies || []) as never;
                void strategies;
                for (const page of this.pages.values()) {
                    if (page instanceof ChartPage ||
                        page instanceof LocalChartPage) {
                        page.setFavorites(this.favorites,
                                          this.strategyFavorites);
                    }
                }
                break;
            }
            case 'indicator_picker': {
                const page = this._activeChartPage();
                const local = this._activeLocalPage();
                if (local) local.setPicker(patch as never);
                else if (page) page.setPicker(patch as never);
                break;
            }
            case 'templates': {
                const local = this._activeLocalPage();
                if (local) {
                    local.setTemplates((patch.items || []) as never);
                } else {
                    const page = this._activeChartPage();
                    if (page) page.setTemplates((patch.items || []) as never);
                }
                break;
            }
            case 'layout': {
                if (patch.local) {
                    const local = this._activeLocalPage();
                    if (local) local.applyLayout(patch as never);
                    break;
                }
                const page = this._chartPageFor(String(patch.symbol || ''));
                if (page instanceof ChartPage) page.applyLayout(patch as never);
                break;
            }
            case 'layouts': {
                const local = this._activeLocalPage();
                if (local) {
                    local.setLayouts((patch.items || []) as never,
                                     String(patch.exportText || ''));
                } else {
                    const page = this._activeChartPage();
                    if (page) {
                        page.setLayouts((patch.items || []) as never,
                                        String(patch.exportText || ''));
                    }
                }
                break;
            }
            case 'replay': {
                const page = this._chartPageFor(String(patch.symbol || ''));
                if (page instanceof ChartPage) page.setReplay(patch as never);
                break;
            }
            case 'chart_type': {
                const page = this.pages.get(`chart:${patch.symbol}`);
                if (page instanceof ChartPage) page.setChartType(
                    String(patch.kind || 'candle'));
                break;
            }
            case 'alerts': {
                const items = (patch.items || []) as never;
                this.alertCenter?.setAlerts(items);
                const symbol = String(patch.symbol || '');
                const page = this._chartPageFor(symbol);
                if (page instanceof ChartPage) page.setAlerts(items);
                // ★ 预警线对**本地模拟**也生效：本地图表按合约匹配 ✓
                const locals = [...this.pages.values()].filter(
                    (item): item is LocalChartPage =>
                        item instanceof LocalChartPage);
                const matched = locals.filter(
                    (item) => item.localDataName === symbol);
                for (const local of (matched.length ? matched : locals)) {
                    local.setAlerts(items);
                }
                break;
            }
            case 'alert_fired': {
                // ★ 价格按**合约小数位**显示（`decimals` 由后端 price_tick 推 ✓）
                const text = `${patch.symbol} 触发预警 `
                    + `${fmtPrice(patch.price, patch.decimals)}`
                    + `（最新 ${fmtPrice(patch.last, patch.decimals)}）→ 下单？`;
                if (!window.confirm(text)) break;
                this.send('place_order', {
                    symbol: patch.symbol, side: patch.action || 'buy',
                    volume: patch.qty || 1, price: patch.price,
                });
                break;
            }
            case 'theme':
                if (patch.theme) this.applyTheme(patch.theme);
                break;
            case 'trading': {
                for (const page of this.pages.values()) {
                    if (page instanceof ChartPage) {
                        page.setTrading(!!patch.enabled, !!patch.real);
                    }
                }
                break;
            }
            case 'toast':
                this.toast(String(patch.level || 'info'),
                           String(patch.text || ''),
                           patch.actions as ToastAction[] | undefined,
                           patch.detail ? String(patch.detail) : undefined);
                break;
            case 'exports': {
                const items = (patch.items || []) as ExportItem[];
                this.exportHistory = items;
                this.quotePage?.setExports(items);
                for (const page of this.pages.values()) {
                    if (page instanceof ChartPage) page.setExports(items);
                }
                break;
            }
            case 'status':
                this.serverStatus = String(patch.text || '');
                this.status.textContent = this.serverStatus;
                break;
            default:
                // unknown patches are ignored on purpose (forward compatible)
                break;
        }
        this._setStatus();
    }

    /** 最近导出的文件（后端 `exports` 补丁；供外部 SDK 读 ✓） */
    get exports(): ExportItem[] {
        return this.exportHistory;
    }

    toast(level: string, text: string, actions?: ToastAction[],
          detail?: string, placement: 'bottom' | 'top' = 'bottom'): void {
        const box = document.createElement('div');
        // `top` = 顶部中间（体检 / 校验类提示用 ✓）
        box.className = `desk-toast ${level}${placement === 'top' ? ' top' : ''}`;
        const line = document.createElement('div');
        line.className = 'desk-toast-text';
        line.textContent = text;
        if (detail) {
            line.title = detail;                 // 完整路径（小字 / 悬浮 ✓）
            box.title = detail;
        }
        box.appendChild(line);
        for (const action of actions || []) {
            const button = document.createElement('button');
            button.className = 'desk-toast-action';
            button.textContent = action.label;
            button.title = action.payload?.path
                ? String(action.payload.path) : action.label;
            button.addEventListener('click', () => {
                this.send(action.cmd, action.payload || {});
                box.remove();
            });
            box.appendChild(button);
        }
        this.root.appendChild(box);
        window.setTimeout(() => box.classList.add('on'), 10);
        // 有按钮 → 多留一会（够点 ✓）
        const ttl = actions && actions.length ? 9000 : 4000;
        window.setTimeout(() => {
            box.classList.remove('on');
            window.setTimeout(() => box.remove(), 250);
        }, ttl);
    }

    toggleTheme(): void {
        this.applyTheme(this.theme === 'light' ? 'dark' : 'light');
        this.send('set_theme', { theme: this.theme });
    }

    private _readTheme(): 'light' | 'dark' | null {
        try {
            const value = window.localStorage.getItem(THEME_KEY);
            return value === 'light' || value === 'dark' ? value : null;
        } catch {
            return null;
        }
    }

    /** 代理页里点链接：`postMessage` 回来 → 用同一个 tab 继续代理 ✓ */
    private _installWebNav(): void {
        window.addEventListener('message', (event) => {
            const data = (event.data || {}) as Record<string, unknown>;
            const target = String(data.__deskWebNav || '');
            if (!target) return;
            // ★ 只接受 desk 自己网页 tab 里的 iframe —— 外部页面 / 任意
            //   `window.postMessage` 不能借这里让后端抓任意 URL ✓
            const frames = Array.from(this.root.querySelectorAll(
                'iframe.desk-web-frame')) as HTMLIFrameElement[];
            if (!frames.some((frame) => frame.contentWindow === event.source)) {
                return;
            }
            this.openWebPage(target);
        });
    }

    /** 网页页签：`url → tab id`（同一个网址只开一个 ✓） */
    private readonly webTabs = new Map<string, string>();
    private webSeq = 0;
    /** 官网固定用这一个 tab（点几次都只有一个 ✓） */
    private static readonly SITE_TAB_ID = 'web:site';
    private static readonly SITE_HOSTS = ['minibt.cn', 'www.minibt.cn'];

    /**
     * 拦截页面里所有 `http(s)` 链接（**悬停文档里的网址**也在内 ✓）：
     * 直接 `preventDefault`，改成在顶栏开一个新 tab 用 iframe 打开。
     *
     * 不拦的话 webview 会**整个导航走**，再也回不到 desk 界面 ✗
     */
    private _installLinkGuard(): void {
        const open = (url: string) => this.openWebPage(url);
        document.addEventListener('click', (event) => {
            const target = event.target as HTMLElement | null;
            const anchor = target?.closest?.('a[href]') as HTMLAnchorElement
                | null;
            if (!anchor) return;
            const href = String(anchor.getAttribute('href') || '');
            if (!/^https?:\/\//i.test(href)) return;   // 站内锚点 / 自定义协议放过
            event.preventDefault();
            event.stopPropagation();
            open(href);
        }, true);
        // 中键 / Ctrl+点击 / 拖拽 也不会把页面导航走 ✓
        document.addEventListener('mousedown', (event) => {
            const anchor = (event.target as HTMLElement | null)
                ?.closest?.('a[href]') as HTMLAnchorElement | null;
            if (!anchor) return;
            const href = String(anchor.getAttribute('href') || '');
            if (!/^https?:\/\//i.test(href)) return;
            if (event.button === 1 || event.ctrlKey || event.metaKey) {
                event.preventDefault();
                open(href);
            }
        }, true);
    }

    /** 在顶栏开一个网页 tab（iframe 加载；加载不了可以用「系统浏览器」兜底 ✓） */
    /**
     * 在**顶栏**开一个网页 tab（iframe）；同一个网址只开一个，官网固定一个 ✓
     *
     * 内容由**后端抓取**（`web_page` 命令）后塞进 `srcdoc` —— 直接
     * `<iframe src>` 会被站点的 `X-Frame-Options` / CDN 的「禁止嵌入」拦掉 ✗
     */
    openWebPage(rawUrl: string): string {
        const url = String(rawUrl || '').trim();
        if (!/^https?:\/\//i.test(url)) return '';
        let host = '';
        try {
            host = new URL(url).host.toLowerCase();
        } catch {
            host = '';
        }
        const bare = host.replace(/^www\./, '');
        const isSite = DeskApp.SITE_HOSTS.includes(host) || bare === 'minibt.cn';
        let id: string;
        if (isSite) {
            // ★ 官网：**有且只有一个 tab**，再点只是把地址换过去 ✓
            id = DeskApp.SITE_TAB_ID;
            if (!this.tabs.has(id)) this._createWebTab(url, host, id);
        } else {
            const existing = this.webTabs.get(url);
            if (existing && this.tabs.has(existing)) {
                this.activate(existing);
                return existing;
            }
            id = `web:${++this.webSeq}`;
            this._createWebTab(url, host, id);
        }
        this.webTabs.set(url, id);
        // Qt 壳有 `deskweb://` 代理（剥掉 X-Frame-Options）→ **直接加载整页** ✓
        const proxy = (window as unknown as { __deskWebProxy?: boolean })
            .__deskWebProxy;
        if (proxy) {
            const page = (this.pages.get(id) as unknown as
                { element: HTMLElement } | undefined)?.element;
            if (page) {
                page.dataset.webUrl = url;
                const hint = page.querySelector('.desk-web-hint') as
                    HTMLElement | null;
                if (hint) hint.style.display = 'none';
                let local = url;
                try {
                    const parsed = new URL(url);
                    local = `deskweb://${parsed.host}${parsed.pathname}`
                        + `${parsed.search}`;
                } catch {
                    local = url;
                }
                const frame = page.querySelector('iframe') as
                    HTMLIFrameElement | null;
                if (frame) {
                    frame.removeAttribute('srcdoc');
                    frame.style.display = '';
                    frame.src = local;
                }
                const label = page.querySelector('.desk-web-url') as
                    HTMLElement | null;
                if (label) {
                    label.textContent = url;
                    label.title = url;
                }
            }
            this.activate(id);
            return id;
        }
        this._loadWebPage(id, url);
        this.activate(id);
        return id;
    }

    /** 真正建一个网页 tab 的骨架（内容稍后由 `_loadWebPage` 填 ✓） */
    private _createWebTab(url: string, host: string, id: string): string {
        this.webTabs.set(url, id);
        const isSite = DeskApp.SITE_HOSTS.includes(host)
            || host.replace(/^www\./, '') === 'minibt.cn';
        const label = isSite ? '官网' : (host || url);
        const page = document.createElement('div');
        page.className = 'desk-web-page';
        page.dataset.webUrl = url;
        const safeUrl = escapeHtml(url);
        const safeLabel = escapeHtml(label);
        page.innerHTML = `
            <div class="desk-web-bar">
                <span class="desk-web-title" title="${safeUrl}">${safeLabel}</span>
                <span class="desk-web-url" title="${safeUrl}">正在加载…</span>
                <button class="desk-btn desk-btn-sm" data-web-reload
                    title="重新加载">重新加载</button>
                <button class="desk-btn desk-btn-sm" data-web-external
                    title="用系统浏览器打开（网页禁止被嵌入时用 ✓）">系统浏览器</button>
            </div>
            <div class="desk-web-body">
                <div class="desk-web-hint">正在抓取页面…</div>
                <iframe class="desk-web-frame" style="display:none"></iframe>
            </div>`;
        page.querySelector('[data-web-reload]')?.addEventListener('click', () => {
            const target = String(page.dataset.webUrl || url);
            const proxy = (window as unknown as { __deskWebProxy?: boolean })
                .__deskWebProxy;
            const frame = page.querySelector('iframe') as
                HTMLIFrameElement | null;
            if (proxy && frame) {
                frame.src = frame.src;               // 直接 reload ✓
                return;
            }
            this._loadWebPage(id, target);
        });
        page.querySelector('[data-web-external]')
            ?.addEventListener('click', () => this.send('open_url', {
                url: String(page.dataset.webUrl || url),
            }));
        page.style.display = 'none';
        this.stack.appendChild(page);
        // `activate()` 调的是 `page.show()/hide()` → 包一层最小页面对象 ✓
        const wrapper = {
            element: page,
            show: () => { page.style.display = 'flex'; },
            hide: () => { page.style.display = 'none'; },
        };
        this.pages.set(id, wrapper as never);
        this._addTab({ id, label, kind: 'web' });
        return id;
    }

    /** 让后端抓 HTML → `srcdoc` 显示（不再被 `X-Frame-Options` 拦 ✓） */
    private _loadWebPage(id: string, url: string): void {
        const page = (this.pages.get(id) as unknown as
            { element: HTMLElement } | undefined)?.element;
        if (!page) return;
        page.dataset.webUrl = url;
        const frame = page.querySelector('iframe') as HTMLIFrameElement | null;
        const hint = page.querySelector('.desk-web-hint') as HTMLElement | null;
        const urlLabel = page.querySelector('.desk-web-url') as HTMLElement
            | null;
        if (urlLabel) {
            urlLabel.textContent = url;
            urlLabel.title = url;
        }
        if (frame) {
            frame.style.display = 'none';
            frame.removeAttribute('srcdoc');
            frame.removeAttribute('src');
        }
        if (hint) {
            hint.style.display = '';
            hint.textContent = '正在抓取页面…';
        }
        this.send('web_page', { url, id });
    }

    /** 后端抓好了：塞进 iframe（失败就去掉提示，让用户点「系统浏览器」） */
    setWebPage(patch: Record<string, any>): void {
        const id = String(patch.id || '');
        const page = (this.pages.get(id) as unknown as
            { element: HTMLElement } | undefined)?.element;
        if (!page) return;
        const frame = page.querySelector('iframe') as HTMLIFrameElement | null;
        const hint = page.querySelector('.desk-web-hint') as HTMLElement | null;
        const urlLabel = page.querySelector('.desk-web-url') as HTMLElement
            | null;
        const finalUrl = String(patch.final || patch.url || '');
        if (urlLabel && finalUrl) {
            urlLabel.textContent = finalUrl;
            urlLabel.title = finalUrl;
        }
        if (patch.ok && frame) {
            page.dataset.webUrl = finalUrl || page.dataset.webUrl || '';
            if (hint) hint.style.display = 'none';
            frame.style.display = '';
            frame.srcdoc = String(patch.html || '');
            return;
        }
        const reason = String(patch.error || '抓取失败');
        if (hint) {
            hint.style.display = '';
            hint.textContent = `这个页面抓不下来（${reason}）—— 点右上角「系统浏览器」打开`;
        }
        this.toast('warning', `网页加载失败：${reason}`, [], undefined, 'top');
    }

    private _installShortcuts(): void {
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                closeMenu();
                this.preview?.hide();
                return;
            }
            const mod = event.ctrlKey || event.metaKey;
            if (mod && (event.key === 'k' || event.key === 'K')) {
                event.preventDefault();
                this.openPalette();
                return;
            }
            if (mod && (event.key === 'w' || event.key === 'W')) {
                if (this.activeId !== HOME_TAB_ID) {
                    event.preventDefault();
                    this.closeTab(this.activeId);
                }
                return;
            }
            if (mod && event.key === 'Tab') {
                const ids = [...this.tabs.keys()];
                if (ids.length < 2) return;
                event.preventDefault();
                const index = ids.indexOf(this.activeId);
                this.activate(ids[(index + 1) % ids.length]);
            }
        });
    }

    applyTheme(theme: 'light' | 'dark'): void {
        this.theme = theme;
        this.logo.innerHTML = deskLogo(theme);
        this.home?.applyTheme(theme);
        this.quotePage?.applyTheme(theme);
        this.logPage?.setTheme(theme);
        this.settingsPage?.setTheme?.(theme);
        this.palette?.applyTheme(theme);
        for (const page of this.pages.values()) {
            if (page instanceof ChartPage || page instanceof LocalChartPage
                || page instanceof StrategyLabPage
                || page instanceof WorkspacePage
                || page instanceof ReplayLabPage
                || page instanceof AlertCenterPage
                || page instanceof WorkbenchPage
                || page instanceof ResearchPage
                || page instanceof DataPage
                || page instanceof OpsPage) {
                page.applyTheme(theme);
            }
        }
        this.root.classList.toggle('theme-light', theme === 'light');
        this.root.classList.toggle('theme-dark', theme !== 'light');
        document.body.classList.toggle('theme-light', theme === 'light');
        document.body.classList.toggle('theme-dark', theme !== 'light');
        // 切主题后 body 的 CSS 变量会重新生效 → 把用户主题色再压回去 ✓
        this._applyAccent(this.accent);
        try {
            window.localStorage.setItem(THEME_KEY, theme);
        } catch {
            /* 隐私模式忽略 */
        }
    }

    /** 看盘 tab 换合约：tab / page / button 的 key 一起换 ✓ */
    private _renameChart(oldSymbol: string, newSymbol: string,
                         name = ''): void {
        if (!oldSymbol || !newSymbol || oldSymbol === newSymbol) return;
        const oldId = `chart:${oldSymbol}`;
        const newId = `chart:${newSymbol}`;
        const page = this.pages.get(oldId);
        if (!(page instanceof ChartPage)) return;
        // 切换合约：先把旧指标的线 / 副图 / 图例清干净，
        // 后端随后推的 indicator 补丁按新合约重建（否则旧的线会留在图上 ✗）
        page.resetIndicators();
        page.resetForSymbol();
        page.setSymbol(newSymbol, name);
        this.send('focus_chart', { symbol: newSymbol });

        this.pages.delete(oldId);
        this.pages.set(newId, page);
        const tab = this.tabs.get(oldId);
        if (tab) {
            this.tabs.delete(oldId);
            tab.id = newId;
            tab.symbol = newSymbol;
            tab.label = newSymbol;
            this.tabs.set(newId, tab);
        }
        const button = this.buttons.get(oldId);
        if (button) {
            button.dataset.id = newId;
            const label = button.firstElementChild;
            if (label) label.textContent = newSymbol;
            this.buttons.delete(oldId);
            this.buttons.set(newId, button);
        }
        if (this.activeId === oldId) {
            this.activeId = newId;
            for (const [key, item] of this.buttons) {
                item.classList.toggle('on', key === newId);
            }
        }
        this._setStatus();
    }

    /** 把时间区间广播给其它图表 tab（不同周期也对得上 ✓） */
    private _broadcastRange(sourceId: string, from: number, to: number): void {
        if (this._rangeLock) return;
        this._rangeLock = true;
        try {
            for (const [id, page] of this.pages) {
                if (id === sourceId) continue;
                if (page instanceof ChartPage) page.applyTimeRange(from, to);
            }
        } finally {
            this._rangeLock = false;
        }
    }

    private _rangeLock = false;

    private _activeChartPage(): ChartPage | null {
        const page = this.pages.get(this.activeId);
        return page instanceof ChartPage ? page : null;
    }

    /** 按补丁里的 symbol 找**精确**图页；旧合约的迟到补丁绝不落到新合约 ✓ */
    private _chartPageFor(symbol: string): ChartPage | null {
        const exact = this.pages.get(`chart:${symbol}`);
        if (exact instanceof ChartPage) return exact;
        const active = this._activeChartPage();
        if (active && (!symbol || active.symbol === symbol)) return active;
        return null;
    }

    private _activeLocalPage(): LocalChartPage | null {
        const page = this.pages.get(this.activeId);
        return page instanceof LocalChartPage ? page : null;
    }

    get activePageId(): string { return this.activeId; }

    private _setStatus(): void {
        const page = this.pages.get(this.activeId);
        const transport = this.transport;
        const detail = page instanceof ChartPage ? ` · ${page.symbol}` : '';
        const base = this.serverStatus
            ? `${this.serverStatus} · ${transport.kind}`
            : transport.kind;
        this.status.textContent = `${base}${detail}`;
    }
}

/**
 * 价格 → 文本：按合约小数位 + 千分位（预警弹窗 / 日志用 ✓）
 */
export function fmtPrice(value: unknown, decimals?: unknown): string {
    const number = Number(value);
    if (value === null || value === undefined || !Number.isFinite(number)) {
        return '--';
    }
    const places = Number(decimals);
    const digits = Number.isFinite(places)
        ? Math.max(0, Math.min(6, Math.round(places))) : 2;
    return number.toLocaleString('en-US', {
        minimumFractionDigits: digits, maximumFractionDigits: digits,
    });
}

/** Register the app for the backend: `window.__desk.applyPatch(...)`. */
export function registerDesk(app: DeskApp): DeskApp {
    (window as any).__desk = app;
    return app;
}

export { MockTransport };
