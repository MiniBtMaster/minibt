/**
 * SettingsPage —— 「设置」页（复刻 miniqt 设置界面 ✓）
 *
 * 结构（`tradingview/设置页面样式*.png`）：
 *
 *   ┌ 左侧导航 ────────┬ 右侧内容 ──────────────────────────────┐
 *   │ 系统设置         │  本地文件 / 个性化 / 关于                │
 *   │ 图表设置         │  图表配置 / 图表颜色                     │
 *   └──────────────────┴────────────────────────────────────────┘
 *
 * 所有值都通过 `onSetting(key, value)` 交给 `DeskApp` → 后端 `set_setting`
 * 落盘（`~/.minibt/desk_user_prefs.json`），重开也在 ✓。
 * 数据目录 / 帮助 / 反馈这些动作走 `onCommand`（`open_data_dir` / `open_url`）。
 */
import { LINE_COLORS } from './indicator-settings';
import { renderMiniChart } from './mini-chart';
import { CROSSHAIR_PRESETS } from './crosshair';

export type SettingsTheme = 'light' | 'dark';

export interface SettingsValues {
    theme?: SettingsTheme;
    theme_accent?: string;
    ui_zoom?: number;
    chart_font_size?: number;
    chart_history?: number;
    chart_data_length?: number;
    chart_color_up?: string;
    chart_color_down?: string;
    chart_color_crosshair?: string;
    chart_crosshair_style?: string;
    /** 持仓线（全局开关，默认开 ✓） */
    position_line?: boolean;
    /** 挂单线（全局开关，默认开 ✓） */
    order_line?: boolean;
    /** 指标 / 策略图表更新频率（ms，10..3000） */
    indicator_refresh_interval_ms?: number;
    /** VP / 表格只在新 K 线更新 */
    indicator_custom_new_bar?: boolean;
    /** 运行日志：终端输出（默认开 ✓） */
    log_terminal?: boolean;
    editor_format_on_save?: boolean;
    /** 运行日志：程序内输出（日志页 / 底部面板） */
    log_ui?: boolean;
    /** 指标选择器默认分组：all / overlay / sub */
    indicator_overlay_filter?: string;
    /** 播放条只显示有报价的合约 */
    ticker_only_quoted?: boolean;
    /** 首页自选默认分组：recent / all / favorites */
    watch_default_group?: string;
}

/** 「设置 → 模拟账户」的数据（后端 `sim_analysis` 补丁 ✓） */
export interface SimAnalysis {
    initial_cash?: number;
    balance?: number;
    realized?: number;
    commission?: number;
    trades?: number;
    closes?: number;
    wins?: number;
}

export interface SimPayload {
    settings?: {
        initial_cash?: number;
        fee_mode?: string;
        fee_value?: number;
    };
    summary?: SimAnalysis;
    equity?: Array<[string, number]>;
    series?: Array<{ name: string; color?: string;
                     points: Array<[string, number]> }>;
    table?: { columns?: string[]; rows?: string[][] };
}

/** 初始现金预设（下拉选了直接填进输入框，也可以手动填任意值 ✓） */
export const CASH_PRESETS: Array<{ value: number; label: string }> = [
    { value: 100000, label: '10 万' },
    { value: 200000, label: '20 万' },
    { value: 300000, label: '30 万' },
    { value: 500000, label: '50 万' },
    { value: 800000, label: '80 万' },
    { value: 1000000, label: '100 万' },
];

/** 手续费模式（只能设置其中之一 ✓） */
export const FEE_MODES: Array<{ value: string; label: string }> = [
    { value: 'fixed', label: '固定手续费用（每手）' },
    { value: 'percent', label: '百分比手续费用（成交额 %）' },
];

export interface SettingsPageOptions {
    theme: SettingsTheme;
    values: SettingsValues;
    version?: string;
    /** 改一个设置项（落盘 + 立即生效 ✓） */
    onSetting: (key: string, value: unknown) => void;
    /** 后端动作：`open_url` / `open_data_dir` ✓ */
    onCommand: (cmd: string, payload?: unknown) => void;
}

/** 主题色候选（miniqt「主题色」下拉 ✓） */
export const ACCENTS: Array<{ value: string; label: string }> = [
    { value: '', label: '默认颜色' },
    { value: '#2962ff', label: '蓝色' },
    { value: '#1f9d55', label: '绿色' },
    { value: '#9c27b0', label: '紫色' },
    { value: '#ff9800', label: '橙色' },
    { value: '#e91e63', label: '玫红' },
];

/** 界面缩放（miniqt 有「跟随系统」，这里给固定档位 + 跟随 ✓） */
export const ZOOMS: Array<{ value: number; label: string }> = [
    { value: 0, label: '跟随系统' },
    { value: 0.8, label: '80%' },
    { value: 0.9, label: '90%' },
    { value: 1, label: '100%' },
    { value: 1.1, label: '110%' },
    { value: 1.25, label: '125%' },
];

/** 图表数据长度候选 ✓ */
export const LENGTHS: Array<{ value: number; label: string }> = [
    { value: 500, label: '500' },
    { value: 1000, label: '1000' },
    { value: 2000, label: '2000' },
    { value: 5000, label: '5000' },
];

/** 图表历史长度候选（要 ≥ 数据长度 ✓） */
export const HISTORIES: Array<{ value: number; label: string }> = [
    { value: 1000, label: '1000' },
    { value: 2000, label: '2000' },
    { value: 5000, label: '5000' },
    { value: 10000, label: '10000' },
];

const STYLE_ID = 'desk-settings-style';

const CSS = `
.desk-settings { position: absolute; inset: 0; display: flex;
    background: var(--desk-bg); color: var(--desk-text); overflow: hidden; }
.desk-settings-nav { flex: 0 0 210px; padding: 14px 10px; overflow-y: auto;
    border-right: 1px solid var(--desk-border); }
.desk-settings-group { color: var(--desk-muted); font-size: 10.5px;
    margin: 10px 8px 4px; letter-spacing: .4px; }
.desk-settings-link { display: flex; align-items: center; gap: 8px;
    padding: 7px 10px; border-radius: 6px; cursor: pointer; font-size: 12.5px;
    user-select: none; }
.desk-settings-link:hover { background: var(--desk-hover); }
.desk-settings-link.on { background: var(--desk-active); color: var(--desk-accent);
    font-weight: 600; }
.desk-settings-body { flex: 1 1 auto; overflow-y: auto; padding: 18px 26px 40px; }
.desk-settings-title { font-size: 20px; font-weight: 600; margin: 0 0 14px; }
.desk-settings-section { font-size: 14px; font-weight: 600; margin: 18px 0 8px; }
.desk-settings-color { width: 34px; min-width: 34px; padding: 0 2px;
    cursor: pointer; }
.desk-settings-input { height: 28px; padding: 0 8px; border-radius: 6px;
    border: 1px solid var(--desk-border); background: var(--desk-bg);
    color: var(--desk-text); font-size: 12px; }
.desk-settings-actions { display: flex; gap: 10px; margin: 14px 0 4px; }
.desk-settings-inline { display: inline-flex; align-items: center; gap: 8px; }
.desk-settings-cards { display: grid; gap: 10px; margin: 6px 0 4px;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
.desk-settings-card { border: 1px solid var(--desk-border); border-radius: 8px;
    padding: 10px 12px; background: var(--desk-panel); }
.desk-settings-card-title { font-size: 11px; color: var(--desk-muted); }
.desk-settings-card-value { font-size: 18px; font-weight: 600; margin-top: 4px; }
.desk-settings-card-value.up { color: var(--desk-up, #f23645); }
.desk-settings-card-value.down { color: var(--desk-down, #089981); }
.desk-settings-chart { border: 1px solid var(--desk-border); border-radius: 8px;
    padding: 8px 6px; background: var(--desk-panel); margin-bottom: 8px; }
.desk-mini-chart-svg { display: block; }
.desk-mini-chart-grid { stroke: var(--desk-border); stroke-width: 1; opacity: .55; }
.desk-mini-chart-zero { stroke: var(--desk-muted); stroke-width: 1;
    stroke-dasharray: 3 3; }
.desk-mini-chart-axis { fill: var(--desk-text); font-size: 12px;
    font-family: inherit; font-weight: 400; }
.desk-mini-chart-empty { color: var(--desk-muted); font-size: 12px;
    padding: 26px 8px; text-align: center; }
.desk-mini-chart-legend { display: flex; flex-wrap: wrap; gap: 10px;
    padding: 6px 8px 2px; }
.desk-mini-chart-chip { display: inline-flex; align-items: center; gap: 5px;
    font-size: 12px; color: var(--desk-text); }
.desk-mini-chart-chip i { width: 8px; height: 8px; border-radius: 50%;
    display: inline-block; }
.desk-settings-table { border: 1px solid var(--desk-border); border-radius: 8px;
    overflow: hidden; }
.desk-settings-table-row { display: grid; gap: 6px; padding: 7px 12px;
    grid-template-columns: 1.3fr .8fr .8fr .8fr 1fr 1fr 1fr; font-size: 12px; }
.desk-settings-table-row.head { background: var(--desk-hover);
    color: var(--desk-muted); font-size: 11px; }
.desk-settings-table-row span.up { color: var(--desk-up, #f23645); }
.desk-settings-table-row span.down { color: var(--desk-down, #089981); }
.desk-settings-row { display: flex; align-items: center; gap: 12px;
    padding: 10px 12px; border: 1px solid var(--desk-border); border-radius: 8px;
    background: var(--desk-panel); margin-bottom: 8px; }
.desk-settings-icon { width: 22px; height: 22px; flex: 0 0 auto;
    display: inline-flex; align-items: center; justify-content: center;
    color: var(--desk-muted); }
.desk-settings-text { flex: 1 1 auto; min-width: 0; }
.desk-settings-name { font-size: 12.5px; }
.desk-settings-desc { color: var(--desk-muted); font-size: 11px;
    margin-top: 2px; }
.desk-settings-control { flex: 0 0 auto; display: flex; align-items: center;
    gap: 8px; }
.desk-settings-select, .desk-settings-input {
    height: 26px; min-width: 96px; padding: 0 6px; border-radius: 4px;
    border: 1px solid var(--desk-border); background: var(--desk-bg);
    color: var(--desk-text); font-size: 12px; }
.desk-settings-btn { height: 26px; padding: 0 12px; border-radius: 4px;
    border: 1px solid var(--desk-border); background: var(--desk-hover);
    color: var(--desk-text); font-size: 12px; cursor: pointer; }
.desk-settings-btn.primary { background: var(--desk-accent); color: #fff;
    border-color: var(--desk-accent); }
.desk-settings-btn:hover { filter: brightness(1.08); }
.desk-settings-switch { position: relative; width: 38px; height: 20px;
    border-radius: 10px; background: var(--desk-border); cursor: pointer;
    transition: background .15s ease; }
.desk-settings-switch.on { background: var(--desk-accent); }
.desk-settings-switch::after { content: ''; position: absolute; top: 2px;
    left: 2px; width: 16px; height: 16px; border-radius: 50%;
    background: #fff; transition: transform .15s ease; }
.desk-settings-switch.on::after { transform: translateX(18px); }
.desk-settings-slider { width: 150px; accent-color: var(--desk-accent); }
.desk-settings-slider-value { min-width: 26px; text-align: right;
    font-variant-numeric: tabular-nums; font-size: 12px; }
.desk-settings-colors { display: flex; gap: 4px; }
.desk-settings-chip { width: 18px; height: 18px; border-radius: 50%;
    border: 2px solid transparent; cursor: pointer; }
.desk-settings-chip.on { border-color: var(--desk-text); }
.desk-settings-empty { color: var(--desk-muted); font-size: 12px; }
`;

const ICONS: Record<string, string> = {
    folder: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        + 'stroke="currentColor" stroke-width="1.7"><path d="M3 7h6l2 2h10v10H3z"/>'
        + '</svg>',
    theme: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        + 'stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="8"/>'
        + '<path d="M12 4v16"/></svg>',
    money: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        + 'stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="8"/>'
        + '<path d="M12 8v8"/><path d="M9 10h4a1.5 1.5 0 010 3h-3"/></svg>',
    palette: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        + 'stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="8"/>'
        + '<circle cx="9" cy="10" r="1.2"/><circle cx="15" cy="10" r="1.2"/>'
        + '<circle cx="12" cy="15" r="1.2"/></svg>',
    zoom: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        + 'stroke="currentColor" stroke-width="1.7"><rect x="4" y="5" width="16" '
        + 'height="14" rx="2"/><path d="M9 12h6M12 9v6"/></svg>',
    chart: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        + 'stroke="currentColor" stroke-width="1.7"><path d="M4 19V5M4 19h16"/>'
        + '<path d="M8 15l3-4 3 3 4-6"/></svg>',
    reset: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        + 'stroke="currentColor" stroke-width="1.7"><path d="M4 12a8 8 0 1 1 3 6"/>'
        + '<path d="M4 5v5h5"/></svg>',
    up: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        + 'stroke="currentColor" stroke-width="1.7"><path d="M12 20V4"/>'
        + '<path d="M6 10l6-6 6 6"/></svg>',
    down: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        + 'stroke="currentColor" stroke-width="1.7"><path d="M12 4v16"/>'
        + '<path d="M6 14l6 6 6-6"/></svg>',
    cursor: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        + 'stroke="currentColor" stroke-width="1.7"><path d="M5 3l14 8-6 1-2 6z"/>'
        + '</svg>',
    help: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        + 'stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="8"/>'
        + '<path d="M9.5 9.5a2.5 2.5 0 1 1 3.6 2.3c-.7.4-.6 1.2-.6 1.7"/>'
        + '<circle cx="12" cy="16.6" r=".8" fill="currentColor"/></svg>',
    feedback: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        + 'stroke="currentColor" stroke-width="1.7"><path d="M4 5h16v11H9l-5 4z"/>'
        + '</svg>',
    info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        + 'stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="8"/>'
        + '<path d="M12 11v6"/><circle cx="12" cy="7.6" r=".9" fill="currentColor"/>'
        + '</svg>',
};

/** 左侧导航：分组 → 页面 ✓ */
const NAV: Array<{ group: string; items: Array<{ key: string; label: string }> }> = [
    { group: '系统设置', items: [
        { key: 'files', label: '本地文件' },
        { key: 'personal', label: '个性化' },
        { key: 'about', label: '关于' },
    ] },
    { group: '模拟账户', items: [
        { key: 'sim', label: '模拟账户' },
    ] },
    { group: '图表设置', items: [
        { key: 'chart-config', label: '图表配置' },
        { key: 'chart-colors', label: '图表颜色' },
    ] },
];

export class SettingsPage {
    readonly element: HTMLDivElement;
    private readonly body: HTMLDivElement;
    private readonly links = new Map<string, HTMLDivElement>();
    private options: SettingsPageOptions;
    private active = 'personal';
    /** 「模拟账户」的分析数据（曲线 / 统计表 ✓） */
    private sim: SimPayload = {};
    /** 后端刚推数据回来时的重画：不要再请求一次（否则死循环 ✗） */
    private quiet = false;

    constructor(options: SettingsPageOptions) {
        this.options = options;
        this.element = document.createElement('div');
        this.element.className = 'desk-settings';

        const nav = document.createElement('div');
        nav.className = 'desk-settings-nav';
        for (const group of NAV) {
            const title = document.createElement('div');
            title.className = 'desk-settings-group';
            title.textContent = group.group;
            nav.appendChild(title);
            for (const item of group.items) {
                const link = document.createElement('div');
                link.className = 'desk-settings-link';
                link.innerHTML = `<span class="desk-settings-icon">${
                    ICONS[item.key === 'files' ? 'folder'
                        : item.key === 'personal' ? 'theme'
                        : item.key === 'sim' ? 'money'
                        : item.key === 'about' ? 'info' : 'chart']}</span>`;
                const text = document.createElement('span');
                text.textContent = item.label;
                link.appendChild(text);
                link.addEventListener('click', () => this.show(item.key));
                nav.appendChild(link);
                this.links.set(item.key, link);
            }
        }
        this.body = document.createElement('div');
        this.body.className = 'desk-settings-body';
        this.element.append(nav, this.body);
        this.show(this.active);
    }

    /** 后端推来的设置（主题 / 缩放等）→ 重画 ✓ */
    setValues(values: SettingsValues): void {
        this.options = { ...this.options, values };
        this.show(this.active);
    }

    /** 后端 `sim_analysis` 补丁 → 刷新「模拟账户」分析 ✓ */
    setSim(payload: SimPayload): void {
        this.sim = payload || {};
        if (this.active !== 'sim') return;
        this.quiet = true;
        try {
            this.show('sim');
        } finally {
            this.quiet = false;
        }
    }

    setTheme(theme: SettingsTheme): void {
        this.options = { ...this.options, theme };
        this.show(this.active);
    }

    get current(): string {
        return this.active;
    }

    show(key: string): void {
        this.active = key;
        for (const [name, link] of this.links) {
            link.classList.toggle('on', name === key);
        }
        this._ensureStyle();
        this.body.textContent = '';
        switch (key) {
            case 'files': this._renderFiles(); break;
            case 'about': this._renderAbout(); break;
            case 'chart-config': this._renderChartConfig(); break;
            case 'chart-colors': this._renderChartColors(); break;
            case 'sim': this._renderSim(); break;
            default: this._renderPersonal(); break;
        }
    }

    // ------------------------------------------------------------ 本地文件
    private _renderFiles(): void {
        this._title('本地文件');
        this._section('数据目录');
        this._row('folder', 'minibt 本地数据',
            'K 线缓存、模拟盘账本、布局 / 指标设置都保存在这里',
            this._button('打开文件夹', () => {
                this.options.onCommand('open_data_dir', {});
            }, true));
        this._section('导出');
        this._row('feedback', '导出历史',
            '最近导出的 CSV（也可以在看盘窗口的「导出历史」里打开）',
            this._button('查看最近导出', () => {
                this.options.onCommand('exports', {});
            }));
    }

    // ------------------------------------------------------------ 个性化
    private _renderPersonal(): void {
        const v = this.options.values || {};
        this._title('个性化');
        this._section('外观');
        this._row('theme', '应用主题', '调整你的应用的外观',
            this._select(
                [{ value: 'dark', label: '深色' },
                 { value: 'light', label: '浅色' }],
                String(v.theme || this.options.theme || 'dark'),
                (value) => this.options.onSetting('app_theme', value)));
        this._row('palette', '主题色', '调整你的应用的主题色（支持自定义颜色）',
            this._accentControl(String(v.theme_accent || '')));
        // ★ 运行日志输出位置（P92）：终端 / 程序内 ✓
        this._section('运行日志');
        this._row('log_terminal', '终端输出',
            '把运行日志打印到启动 minibt desk 的终端（界面卡住也能复制 ✓）',
            this._switch(v.log_terminal !== false, (checked) =>
                this.options.onSetting('log_terminal', checked)));
        this._row('log_ui', '程序内输出',
            '同时写进「运行日志」页和看盘窗口底部面板',
            this._switch(v.log_ui !== false, (checked) =>
                this.options.onSetting('log_ui', checked)));
        // ★ 编辑器：保存时自动格式化（P127）
        this._section('指标与自选');
        this._row('indicator_filter', '指标选择器默认分组',
            '每次打开指标选择器时默认停在哪个分组',
            this._select(
                [{ value: 'all', label: '全部指标' },
                 { value: 'overlay', label: '主图叠加' },
                 { value: 'sub', label: '副图' }],
                String(v.indicator_overlay_filter || 'all'),
                (value) => this.options.onSetting(
                    'indicator_overlay_filter', value)));
        this._row('ticker_only', '播放条只显示有报价的合约',
            '底部播放条隐藏暂无报价的合约',
            this._switch(v.ticker_only_quoted === true,
                (checked) => this.options.onSetting(
                    'ticker_only_quoted', checked)));
        this._row('watch_default', '自选默认分组',
            '打开首页时默认选中的自选分组',
            this._select(
                [{ value: 'recent', label: '最近打开' },
                 { value: 'all', label: '全部自选' },
                 { value: 'favorites', label: '收藏' }],
                String(v.watch_default_group || 'recent'),
                (value) => this.options.onSetting(
                    'watch_default_group', value)));

        this._section('编辑器');
        this._row('editor_format_on_save', '保存时自动格式化',
            'Ctrl+S 保存前先用 ruff / black 格式化（可 Ctrl+Z 撤销 ✓）',
            this._switch(!!v.editor_format_on_save, (checked) =>
                this.options.onSetting('editor_format_on_save', checked)));
        this._row('zoom', '界面缩放', '调整小部件和字体的大小',
            this._select(
                ZOOMS.map((item) => ({ value: String(item.value),
                    label: item.label })),
                String(Number(v.ui_zoom || 0)),
                (value) => this.options.onSetting('ui_zoom',
                    Number(value) || 0)));
    }

    // ------------------------------------------------------------ 关于
    private _renderAbout(): void {
        const version = this.options.version || '1.3.3';
        this._title('关于');
        this._row('help', '帮助', '发现新功能并了解 minibt desk 的使用技巧',
            this._button('打开帮助页面', () => {
                this.options.onCommand('open_url', {
                    url: 'https://www.minibt.cn' });
            }));
        this._row('feedback', '提供反馈', '通过提供反馈帮助我们改进 minibt',
            this._button('提供反馈', () => {
                this.options.onCommand('open_url', {
                    url: 'https://github.com/MiniBtMaster/minibt/issues' });
            }));
        this._row('info', '关于',
            `minibt desk · 当前版本 ${version}`,
            this._button('检查更新', () => {
                this.options.onCommand('open_url', {
                    url: 'https://pypi.org/project/minibt/' });
            }));
    }

    // ------------------------------------------------------------ 图表配置
    private _renderChartConfig(): void {
        const v = this.options.values || {};
        this._title('图表设置');
        this._section('图表配置');
        this._row('reset', '恢复当前页面默认值',
            '只恢复「图表配置」页的设置，不影响图表颜色 / 模拟账户 / 主题',
            this._button('恢复默认', () => {
                this.options.onSetting('chart_reset', true);
            }));
        this._row('chart', '期货历史长度',
            '无限历史能在左加载的总根数（需 ≥ 数据长度；相等 = 无限历史）',
            this._select(
                HISTORIES.map((item) => ({ value: String(item.value),
                    label: item.label })),
                String(Number(v.chart_history || 1000)),
                (value) => this.options.onSetting('chart_history',
                    Number(value) || 1000)));
        this._row('chart', '期货数据长度',
            '设置获取期货K线数据的长度（根数），越大加载越慢',
            this._select(
                LENGTHS.map((item) => ({ value: String(item.value),
                    label: item.label })),
                String(Number(v.chart_data_length || 1000)),
                (value) => this.options.onSetting('chart_data_length',
                    Number(value) || 1000)));
        this._row('chart', '图表字体大小',
            '设置图表左上角标签（图例 / 指标标签 / 买卖盘）的文字大小',
            this._slider(10, 22, Number(v.chart_font_size || 13),
                (value) => this.options.onSetting('chart_font_size', value)));
        this._row('crosshair', '鼠标十字线',
            '设置图表鼠标十字线样式；不选时默认跟随深色 / 浅色主题',
            this._select(
                CROSSHAIR_PRESETS.map((item) => ({
                    value: item.value, label: item.label,
                })),
                String(v.chart_crosshair_style || 'classic'),
                (value) => this.options.onSetting('chart_crosshair_style',
                    value)));
        // ★ 持仓线 / 挂单线：**所有图表**统一由这里控制（默认开 ✓）
        this._row('position_line', '持仓线',
            '在图表上显示持仓成本线（多仓绿 / 空仓红，含天勤模拟与本地模拟）',
            this._switch(v.position_line !== false, (checked) =>
                this.options.onSetting('position_line', checked)));
        this._row('order_line', '挂单线',
            '在图表上显示未成交的挂单价（天勤模拟 / 本地模拟的挂单都会显示）',
            this._switch(v.order_line !== false, (checked) =>
                this.options.onSetting('order_line', checked)));
        this._section('指标刷新');
        this._row('chart', '指标/策略图表更新频率',
            '主图 / 副图 / VP / 表格，以及策略 Strategy.__init__ 里的指标'
            + '重算，全部按这一个频率更新（10–3000ms；实际最快受 500ms'
            + ' 看盘节拍限制）。策略逻辑 next 的频率由「新K线next / on_close」'
            + '决定，不单独占用刷新频率。',
            this._slider(10, 3000,
                Number(v.indicator_refresh_interval_ms || 1000),
                (value) => this.options.onSetting(
                    'indicator_refresh_interval_ms', value)));
        this._row('chart', 'VP / 表格只在新 K 线更新',
            '开启后 VP 图 / 动态表格只在出现新 K 线时更新'
            + '（默认关闭 = 按上面的统一频率刷新；开启后开销最低）',
            this._switch(v.indicator_custom_new_bar === true, (checked) =>
                this.options.onSetting('indicator_custom_new_bar', checked)));
        this._row('chart', 'K 线推送',
            'K 线不受指标刷新设置影响，始终保持即时推送',
            document.createElement('span'));
    }

    // ------------------------------------------------------------ 图表颜色
    private _renderChartColors(): void {
        const v = this.options.values || {};
        this._title('图表颜色');
        this._row('cursor', '鼠标标签颜色', '设置鼠标悬停时标签的背景颜色',
            this._colorPicker(String(v.chart_color_crosshair || ''),
                (value) => this.options.onSetting('chart_color_crosshair',
                    value)));
        this._row('up', '上涨颜色', '设置K线上涨时的颜色（阳线）',
            this._colorPicker(String(v.chart_color_up || ''),
                (value) => this.options.onSetting('chart_color_up', value)));
        this._row('down', '下跌颜色', '设置K线下跌时的颜色（阴线）',
            this._colorPicker(String(v.chart_color_down || ''),
                (value) => this.options.onSetting('chart_color_down', value)));
    }

    // ------------------------------------------------------------ 小部件
    private _title(text: string): void {
        const title = document.createElement('h2');
        title.className = 'desk-settings-title';
        title.textContent = text;
        this.body.appendChild(title);
    }

    // ------------------------------------------------------------ 模拟账户
    private _renderSim(): void {
        const settings = this.sim.settings || {};
        // 打开这一页时向后端要一次（后端刚推回来的那次不要 ✗）
        if (!this.quiet) this.options.onCommand('sim_analysis', {});
        this._title('模拟账户');
        this._section('账户设置');
        // ★ 回放带策略时以 minibt 的 config / 合约为准（用户要求 ✓）
        const note = document.createElement('div');
        note.className = 'desk-muted';
        note.style.margin = '0 0 8px';
        note.textContent = '回放带策略时：初始资金 / 保证金率 / 手续费 / 合约乘数'
            + ' 跟随策略的 minibt 配置；这里用于手动交易 / 无策略回放。';
        this.body.appendChild(note);
        // 初始现金：下拉预设（10 万 ~ 100 万）+ 手动填任意值 ✓
        const cashBox = document.createElement('div');
        cashBox.className = 'desk-settings-inline';
        const current = Math.round(Number(settings.initial_cash) || 100000);
        const cash = document.createElement('input');
        cash.type = 'number';
        cash.className = 'desk-settings-input';
        cash.min = '1';
        cash.step = '1000';
        cash.style.width = '130px';
        cash.value = String(current);
        cash.title = '本地模拟账户的初始现金（可以直接填任意金额 ✓）';
        const preset = this._select(
            CASH_PRESETS.map((item) => ({ value: String(item.value),
                                          label: item.label })),
            CASH_PRESETS.some((item) => item.value === current)
                ? String(current) : '',
            (value) => {
                const picked = Number(value);
                if (!Number.isFinite(picked) || picked <= 0) return;
                cash.value = String(picked);      // 选了下拉 → 填进输入框 ✓
                this._applyCash(picked);
            });
        // 下拉里加一条「自定义」（当前值不在预设里时选中它 ✓）
        const custom = document.createElement('option');
        custom.value = '';
        custom.textContent = '自定义';
        preset.insertBefore(custom, preset.firstChild);
        const apply = this._button('应用', () => {
            const value = Number(cash.value);
            if (!Number.isFinite(value) || value <= 0) {
                cash.focus();
                return;
            }
            this._applyCash(value);
        });
        cash.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') this._applyCash(Number(cash.value));
        });
        cash.addEventListener('change', () => {
            const value = Number(cash.value);
            if (Number.isFinite(value) && value > 0) this._applyCash(value);
        });
        cashBox.append(preset, cash, apply);
        this._row('money', '账户初始现金',
                  '选 10 万 ~ 100 万，或直接在框里填任意金额（应用后按新金额重置账户 ✓）',
                  cashBox);

        const mode = this._select(FEE_MODES,
                                  String(settings.fee_mode || 'fixed'),
                                  (value) => this.options.onSetting(
                                      'sim_fee_mode', value));
        this._row('chart', '交易手续费用', '只能设置其中之一：固定每手 / 成交额百分比',
                  mode);

        const fee = document.createElement('input');
        fee.type = 'number';
        fee.className = 'desk-settings-input';
        fee.min = '0';
        fee.step = '0.01';
        fee.style.width = '110px';
        fee.value = String(Number(settings.fee_value) || 0);
        const isPercent = String(settings.fee_mode || 'fixed') === 'percent';
        fee.title = isPercent ? '成交额的百分之几（0.5 = 0.5%）'
            : '每手固定多少钱';
        fee.addEventListener('change', () => {
            const value = Number(fee.value);
            if (Number.isFinite(value) && value >= 0) {
                this.options.onSetting('sim_fee_value', value);
            }
        });
        this._row('money', isPercent ? '百分比手续费（%）' : '固定手续费（元 / 手）',
                  isPercent ? '例：0.5 表示成交额的 0.5%'
                      : '例：5 表示每手 5 元', fee);

        const actions = document.createElement('div');
        actions.className = 'desk-settings-actions';
        actions.append(
            this._button('刷新分析', () => this.options.onCommand(
                'sim_analysis', {})),
            this._button('重置模拟账户', () => this.options.onCommand(
                'sim_reset', {}), true));
        this.body.appendChild(actions);

        const summary = this.sim.summary || {};
        this._section('账户概况');
        const cards = document.createElement('div');
        cards.className = 'desk-settings-cards';
        const initial = Number(summary.initial_cash
            || settings.initial_cash || 0);
        for (const [name, value, tone] of [
                ['账户权益', summary.balance, 'vs-initial'],
                ['平仓盈亏', summary.realized, 'sign'],
                ['手续费', summary.commission, 'none'],
                ['成交次数', summary.trades, 'count'],
                ['平仓次数', summary.closes, 'count'],
                ['盈利次数', summary.wins, 'count']] as const) {
            const card = document.createElement('div');
            card.className = 'desk-settings-card';
            const title = document.createElement('div');
            title.className = 'desk-settings-card-title';
            title.textContent = name;
            const number = document.createElement('div');
            number.className = 'desk-settings-card-value';
            if (tone === 'vs-initial') {
                const amount = Number(value) || 0;
                number.textContent = amount.toLocaleString(undefined, {
                    minimumFractionDigits: 2, maximumFractionDigits: 2,
                });
                // 和初始现金比：多 → 红（盈利），少 → 绿（亏损）✓
                number.classList.toggle('up', amount > initial);
                number.classList.toggle('down', amount < initial);
            } else if (tone === 'sign') {
                const amount = Number(value) || 0;
                number.textContent = amount.toLocaleString(undefined, {
                    minimumFractionDigits: 2, maximumFractionDigits: 2,
                });
                number.classList.toggle('up', amount > 0);
                number.classList.toggle('down', amount < 0);
            } else if (tone === 'none') {
                number.textContent = (Number(value) || 0).toLocaleString(
                    undefined, { minimumFractionDigits: 2,
                                 maximumFractionDigits: 2 });
            } else {
                number.textContent = value === undefined || value === null
                    ? '--' : String(value);
            }
            card.append(title, number);
            cards.appendChild(card);
        }
        this.body.appendChild(cards);

        this._section('账户权益曲线');
        const equityHost = document.createElement('div');
        equityHost.className = 'desk-settings-chart';
        this.body.appendChild(equityHost);
        renderMiniChart(equityHost, [{
            name: '账户权益',
            color: 'var(--desk-accent, #2962ff)',
            points: this.sim.equity || [],
        }], {
            height: 180,
            area: true,
            format: (value) => value.toFixed(0),
            empty: '还没有成交，权益曲线为空',
        });

        this._section('各品种累计盈亏');
        const profitHost = document.createElement('div');
        profitHost.className = 'desk-settings-chart';
        this.body.appendChild(profitHost);
        renderMiniChart(profitHost, (this.sim.series || []).map((item) => ({
            name: item.name,
            color: item.color,
            points: item.points || [],
        })), {
            height: 180,
            zeroLine: true,
            format: (value) => value.toFixed(0),
            empty: '还没有平仓记录（平仓后这里会出现累计盈亏曲线）',
        });

        this._section('各品种统计');
        const table = this.sim.table || {};
        const columns = table.columns || [];
        const rows = table.rows || [];
        if (!columns.length || !rows.length) {
            const empty = document.createElement('div');
            empty.className = 'desk-settings-desc';
            empty.textContent = '暂无成交记录';
            this.body.appendChild(empty);
            return;
        }
        const grid = document.createElement('div');
        grid.className = 'desk-settings-table';
        const head = document.createElement('div');
        head.className = 'desk-settings-table-row head';
        for (const name of columns) {
            const cell = document.createElement('span');
            cell.textContent = name;
            head.appendChild(cell);
        }
        grid.appendChild(head);
        for (const row of rows) {
            const line = document.createElement('div');
            line.className = 'desk-settings-table-row';
            row.forEach((value, index) => {
                const cell = document.createElement('span');
                cell.textContent = String(value);
                const numeric = Number(String(value).replace(/[,\s]/g, ''));
                if (index >= 4 && Number.isFinite(numeric)) {
                    cell.classList.toggle('up', numeric > 0);
                    cell.classList.toggle('down', numeric < 0);
                }
                line.appendChild(cell);
            });
            grid.appendChild(line);
        }
        this.body.appendChild(grid);
    }

    /** 应用初始现金（立刻落盘 + 重置账户 ✓） */
    private _applyCash(value: number): void {
        const amount = Math.round(Number(value) || 0);
        if (amount <= 0) return;
        this.options.onSetting('sim_initial_cash', amount);
    }

    private _section(text: string): void {
        const section = document.createElement('div');
        section.className = 'desk-settings-section';
        section.textContent = text;
        this.body.appendChild(section);
    }

    /** 主题色：预设色 + 「自定义颜色…」→ 系统调色板 ✓ */
    private _accentControl(value: string): HTMLDivElement {
        const box = document.createElement('div');
        box.className = 'desk-settings-control';
        const presetValues = new Set(ACCENTS.map((item) => item.value));
        const isCustom = !!value && !presetValues.has(value);
        const custom = document.createElement('input');
        custom.type = 'color';
        custom.className = 'desk-settings-input desk-settings-color';
        custom.title = '自定义主题色';
        custom.value = value && value.startsWith('#') ? value : '#2962ff';
        custom.style.display = isCustom ? '' : 'none';
        const items = ACCENTS.map((item) => ({
            value: item.value || 'default', label: item.label,
        }));
        items.push({ value: 'custom', label: '自定义颜色…' });
        const select = this._select(
            items, isCustom ? 'custom' : (value || 'default'),
            (picked) => {
                if (picked === 'custom') {
                    custom.style.display = '';
                    custom.click();       // 打开系统调色板（input 时再应用）
                } else {
                    custom.style.display = 'none';
                    this.options.onSetting(
                        'theme_accent', picked === 'default' ? '' : picked);
                }
            });
        custom.addEventListener('input', () =>
            this.options.onSetting('theme_accent', custom.value));
        custom.addEventListener('change', () =>
            this.options.onSetting('theme_accent', custom.value));
        box.append(select, custom);
        return box;
    }

    private _row(icon: string, name: string, desc: string,
                 control: HTMLElement | null): void {
        const row = document.createElement('div');
        row.className = 'desk-settings-row';
        const box = document.createElement('span');
        box.className = 'desk-settings-icon';
        box.innerHTML = ICONS[icon] || ICONS.info;
        const text = document.createElement('div');
        text.className = 'desk-settings-text';
        const title = document.createElement('div');
        title.className = 'desk-settings-name';
        title.textContent = name;
        const detail = document.createElement('div');
        detail.className = 'desk-settings-desc';
        detail.textContent = desc;
        text.append(title, detail);
        row.append(box, text);
        if (control) {
            const right = document.createElement('div');
            right.className = 'desk-settings-control';
            right.appendChild(control);
            row.appendChild(right);
        }
        this.body.appendChild(row);
    }

    private _button(label: string, run: () => void,
                    primary = false): HTMLButtonElement {
        const button = document.createElement('button');
        button.className = 'desk-settings-btn' + (primary ? ' primary' : '');
        button.textContent = label;
        button.addEventListener('click', run);
        return button;
    }

    private _select(items: Array<{ value: string; label: string }>,
                    value: string,
                    onPick: (value: string) => void): HTMLSelectElement {
        const select = document.createElement('select');
        select.className = 'desk-settings-select';
        for (const item of items) {
            const option = document.createElement('option');
            option.value = item.value;
            option.textContent = item.label;
            if (item.value === value) option.selected = true;
            select.appendChild(option);
        }
        select.addEventListener('change', () => onPick(select.value));
        return select;
    }

    private _switch(checked: boolean,
                    onToggle: (checked: boolean) => void): HTMLDivElement {
        const box = document.createElement('div');
        box.className = 'desk-settings-switch' + (checked ? ' on' : '');
        box.addEventListener('click', () => {
            const next = !box.classList.contains('on');
            box.classList.toggle('on', next);
            onToggle(next);
        });
        return box;
    }

    private _slider(min: number, max: number, value: number,
                    onPick: (value: number) => void): HTMLDivElement {
        const box = document.createElement('div');
        box.className = 'desk-settings-control';
        const input = document.createElement('input');
        input.type = 'range';
        input.className = 'desk-settings-slider';
        input.min = String(min);
        input.max = String(max);
        input.value = String(value);
        const label = document.createElement('span');
        label.className = 'desk-settings-slider-value';
        label.textContent = String(value);
        input.addEventListener('input', () => {
            label.textContent = input.value;
        });
        input.addEventListener('change', () => onPick(Number(input.value)));
        box.append(label, input);
        return box;
    }

    /** 颜色：一排色块 + 「默认颜色」下拉（miniqt 是下拉，这里两者都有 ✓） */
    private _colorPicker(value: string,
                         onPick: (value: string) => void): HTMLDivElement {
        const box = document.createElement('div');
        box.className = 'desk-settings-control';
        const colors = document.createElement('div');
        colors.className = 'desk-settings-colors';
        const choices = ['', ...LINE_COLORS];
        for (const color of choices) {
            const chip = document.createElement('span');
            chip.className = 'desk-settings-chip'
                + (String(color).toLowerCase() === String(value).toLowerCase()
                    ? ' on' : '');
            chip.title = color || '默认颜色';
            chip.style.background = color
                || (this.options.theme === 'light' ? '#d7dbe0' : '#3a4048');
            chip.addEventListener('click', () => {
                colors.querySelectorAll('.desk-settings-chip')
                    .forEach((node) => node.classList.remove('on'));
                chip.classList.add('on');
                onPick(color);
            });
            colors.appendChild(chip);
        }
        const custom = document.createElement('input');
        custom.type = 'color';
        custom.className = 'desk-settings-input';
        custom.style.minWidth = '42px';
        custom.style.padding = '0 2px';
        custom.value = value && value.startsWith('#') ? value : '#2962ff';
        custom.addEventListener('input', () => onPick(custom.value));
        box.append(colors, custom);
        return box;
    }

    private _ensureStyle(): void {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = CSS;
        document.head.appendChild(style);
    }
}
