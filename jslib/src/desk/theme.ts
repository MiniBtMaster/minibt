/** 主题色板：DataGrid / LWC 图表 / 副图都要跟着 desk 主题走 ✓ */

export type DeskTheme = 'light' | 'dark';

export interface GridPalette {
    background: string;
    headerBackground: string;
    headerText: string;
    text: string;
    muted: string;
    border: string;
    rowHover: string;
    striped: string;
    gridLine: string;
    scrollbar: string;
    accent: string;
    positive: string;
    negative: string;
}

const GRID_DARK: GridPalette = {
    background: '#0f1115',
    headerBackground: '#161a20',
    headerText: '#8b93a1',
    text: '#d8d9db',
    muted: '#8b93a1',
    border: '#262c36',
    rowHover: '#1e242d',
    striped: 'rgba(255,255,255,0.02)',
    gridLine: 'rgba(255,255,255,0.04)',
    scrollbar: '#3a3f4b',
    accent: '#2962ff',
    positive: '#ef5350',
    negative: '#26a69a',
};

const GRID_LIGHT: GridPalette = {
    background: '#ffffff',
    headerBackground: '#f1f3f6',
    headerText: '#6b7280',
    text: '#1f2329',
    muted: '#6b7280',
    border: '#e3e6ea',
    rowHover: '#eef1f5',
    striped: 'rgba(0,0,0,0.03)',
    gridLine: 'rgba(0,0,0,0.06)',
    scrollbar: '#c9ced6',
    accent: '#1a73e8',
    positive: '#d93b3b',
    negative: '#1f9d55',
};

/** Ticker-Tape（底部滚动报价条）色板 ✓ */
export interface TickerPalette {
    background: string;
    text: string;
    muted: string;
    border: string;
    hover: string;
    positive: string;
    negative: string;
}

const TICKER_DARK: TickerPalette = {
    background: '#0f1115', text: '#d8d9db', muted: '#8b93a1',
    border: '#262c36', hover: 'rgba(255,255,255,0.06)',
    positive: '#ef5350', negative: '#26a69a',
};

const TICKER_LIGHT: TickerPalette = {
    background: '#f7f8fa', text: '#1f2329', muted: '#6b7280',
    border: '#e3e6ea', hover: 'rgba(0,0,0,0.045)',
    positive: '#d93b3b', negative: '#1f9d55',
};

export function tickerPalette(theme: DeskTheme): TickerPalette {
    return theme === 'light' ? TICKER_LIGHT : TICKER_DARK;
}

export function gridPalette(theme: DeskTheme): GridPalette {
    return theme === 'light' ? GRID_LIGHT : GRID_DARK;
}

export interface ChartPalette {
    background: string;
    text: string;
    grid: string;
    border: string;
    up: string;
    down: string;
}

const CHART_DARK: ChartPalette = {
    background: '#0f1115', text: '#d8d9db',
    grid: 'rgba(255,255,255,0.05)', border: '#262c36',
    up: '#ef5350', down: '#26a69a',
};

const CHART_LIGHT: ChartPalette = {
    background: '#ffffff', text: '#1f2329',
    grid: 'rgba(0,0,0,0.06)', border: '#e3e6ea',
    up: '#d93b3b', down: '#1f9d55',
};

export function chartPalette(theme: DeskTheme): ChartPalette {
    return theme === 'light' ? CHART_LIGHT : CHART_DARK;
}

/**
 * 全局 UI 色板（pylightcharts 的根 CSS 变量：画线工具箱 / 右键菜单 / tooltip）。
 *
 * `Lib.Handler.setRootStyles()` 读的就是这些键名（backgroundColor …）。
 * 以前 desk 直接 `new Handler`，从来没人调它 → 工具箱永远用 `styles.css`
 * 里的深色默认值，切浅色主题也不变（用户实测 ✗）。
 */
export interface UiPalette {
    background: string;
    hoverBackground: string;
    clickBackground: string;
    activeBackground: string;
    mutedBackground: string;
    border: string;
    color: string;
    activeColor: string;
}

const UI_DARK: UiPalette = {
    background: '#0f1115',
    hoverBackground: '#1e242d',
    clickBackground: '#262c36',
    activeBackground: 'rgba(41, 98, 255, 0.35)',
    mutedBackground: 'rgba(41, 98, 255, 0.16)',
    border: '#262c36',
    color: '#d8d9db',
    activeColor: '#ffffff',
};

const UI_LIGHT: UiPalette = {
    background: '#ffffff',
    hoverBackground: '#eef1f5',
    clickBackground: '#e3e6ea',
    activeBackground: 'rgba(26, 115, 232, 0.22)',
    mutedBackground: 'rgba(26, 115, 232, 0.10)',
    border: '#e3e6ea',
    color: '#1f2329',
    activeColor: '#1a73e8',
};

export function uiPalette(theme: DeskTheme): UiPalette {
    return theme === 'light' ? UI_LIGHT : UI_DARK;
}

/** LWC 的 `applyOptions` 参数（背景 / 文字 / 网格 / 边框）✓ */
export function chartOptions(theme: DeskTheme): Record<string, unknown> {
    const pal = chartPalette(theme);
    return {
        layout: {
            background: { type: 0 /* ColorType.Solid */, color: pal.background },
            textColor: pal.text,
            attributionLogo: false,
            // 主图 / 副图之间的分隔线：**2px + 深浅主题都看得见**的底色
            // （以前全透明 → 视觉上是 0 高，看盘窗口/本地图表都看不到分隔 ✗）
            // 仍保留 `enableResize`，所以拖高度照样能拖 ✓
            panes: {
                enableResize: true,
                separatorColor: theme === 'light'
                    ? 'rgba(100,116,139,0.32)' : 'rgba(148,163,184,0.45)',
                separatorHoverColor: 'rgba(56,189,248,0.55)',
            },
        },
        grid: {
            vertLines: { color: pal.grid },
            horzLines: { color: pal.grid },
        },
        rightPriceScale: { borderColor: pal.border },
        timeScale: { borderColor: pal.border },
    };
}
