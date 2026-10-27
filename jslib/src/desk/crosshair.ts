/**
 * 图表鼠标十字线样式（实时图表 + 本地图表共用）。
 *
 * `classic` 默认跟随主题：深色不是黑线、浅色也不会发白。
 * 其余预设参考 TradingView 超级图表 / pylightcharts 原生风格。
 */
export type CrosshairPreset =
    'classic' | 'tradingview' | 'native' | 'neon' | 'minimal';

export const CROSSHAIR_PRESETS: Array<{ value: CrosshairPreset; label: string }> = [
    { value: 'classic', label: '常规（跟随深/浅主题）' },
    { value: 'tradingview', label: 'TradingView 紫色宽线' },
    { value: 'native', label: 'pylightcharts 原生' },
    { value: 'neon', label: '霓虹青色' },
    { value: 'minimal', label: '细点线' },
];

interface LineStyle {
    color: string;
    style: number;
    width: number;
    label: string;
}

function presetStyles(theme: 'light' | 'dark', preset: string): {
    vert: LineStyle; horz: LineStyle;
} {
    const dark = theme === 'dark';
    switch (String(preset || 'classic')) {
        case 'tradingview':
            // examples/11_api_tour/13_workspace.py 的 crosshair 配置
            return {
                vert: {
                    color: '#C3BCDB44', style: 0, width: 8,
                    label: '#9B7DFF',
                },
                horz: {
                    color: '#9B7DFF', style: 0, width: 1,
                    label: '#9B7DFF',
                },
            };
        case 'native':
            return {
                vert: {
                    color: dark ? '#758696' : '#6b7280', style: 3, width: 1,
                    label: dark ? '#2e2e2e' : '#f1f3f6',
                },
                horz: {
                    color: dark ? '#758696' : '#6b7280', style: 3, width: 1,
                    label: dark ? '#373737' : '#e3e6ea',
                },
            };
        case 'neon':
            return {
                vert: {
                    color: dark ? '#00e5ff' : '#0097a7', style: 0, width: 1,
                    label: '#00bcd4',
                },
                horz: {
                    color: dark ? '#00e5ff' : '#0097a7', style: 0, width: 1,
                    label: '#00bcd4',
                },
            };
        case 'minimal':
            return {
                vert: {
                    color: dark ? 'rgba(180,190,205,.5)' : 'rgba(70,80,95,.4)',
                    style: 1, width: 1,
                    label: dark ? '#2962ff' : '#1a73e8',
                },
                horz: {
                    color: dark ? 'rgba(180,190,205,.5)' : 'rgba(70,80,95,.4)',
                    style: 1, width: 1,
                    label: dark ? '#2962ff' : '#1a73e8',
                },
            };
        case 'classic':
        default:
            return {
                vert: {
                    color: dark ? 'rgba(180,190,205,.62)' : 'rgba(60,70,85,.5)',
                    style: 2, width: 1,
                    label: dark ? '#2962ff' : '#1a73e8',
                },
                horz: {
                    color: dark ? 'rgba(180,190,205,.62)' : 'rgba(60,70,85,.5)',
                    style: 2, width: 1,
                    label: dark ? '#2962ff' : '#1a73e8',
                },
            };
    }
}

/** LWC `chart.applyOptions({...})` 可直接展开的十字线配置。 */
export function crosshairOptions(
    theme: 'light' | 'dark',
    preset = 'classic',
    customLabel = '',
): Record<string, unknown> {
    const styles = presetStyles(theme, preset);
    // X/Y 轴标签只由「图表颜色 → 鼠标标签颜色」控制；默认蓝色。
    // 主题色只控制控件状态，不再混入鼠标标签 ✓
    const defaultLabel = theme === 'light' ? '#1a73e8' : '#2962ff';
    const label = (_fallback: string) => customLabel || defaultLabel;
    return {
        crosshair: {
            mode: 0,                    // CrosshairMode.Normal
            vertLine: {
                visible: true,
                color: styles.vert.color,
                width: styles.vert.width,
                style: styles.vert.style,
                labelBackgroundColor: label(styles.vert.label),
            },
            horzLine: {
                visible: true,
                color: styles.horz.color,
                width: styles.horz.width,
                style: styles.horz.style,
                labelBackgroundColor: label(styles.horz.label),
            },
        },
    };
}
