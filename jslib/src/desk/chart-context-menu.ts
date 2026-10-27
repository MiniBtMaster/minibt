/**
 * 看盘窗口的**图表右键菜单**（复刻 miniqt `show_context_menu`）。
 *
 * 菜单结构：
 *
 *   指标 / 收藏指标 / 收藏策略 / 删除指标策略
 *   ── 周期
 *   ── 布局 / 收藏布局
 *   ── 画线 / 清除画线
 *   ── 价格预警 / 清除预警
 *   ── 截图
 *
 * 实时看盘与本地图表共用这一个构建器；两者把各自的数据（收藏、布局、
 * 周期、预警）和回调传进来即可。
 */
import { showMenu, type MenuItem } from './menu';

export interface ChartContextSpec {
    favorites: Array<Record<string, unknown>>;
    strategies: Array<Record<string, unknown>>;
    layouts: Array<Record<string, unknown>>;
    cycle: number;
    cycleGroups: Array<{
        label: string;
        items: Array<{ value: number; label: string }>;
    }>;
    /** 本地图表：周期固定 ✓ */
    local?: boolean;
    /** 本地图表的多图布局（传了就用它，不再用「固定单图」） */
    layoutItems?: MenuItem[];
    hasAlerts?: boolean;
    /** 当前页有 ≥2 个图表 → 「关闭图表」可用（用户要求 ✓） */
    canCloseChart?: boolean;
    onIndicatorPicker: () => void;
    onAddFavorite: (key: string) => void;
    /** 收藏策略 → 按文件路径加到图表（和编辑器「加到图表」同一条命令 ✓） */
    onAddStrategy?: (path: string, key?: string) => void;
    onRemove: () => void;
    onCycle: (cycle: number) => void;
    onLayoutPreset: (cols: number, rows: number) => void;
    onLayoutApply: (key: string) => void;
    onToggleToolBox: () => void;
    onClearDrawings: () => void;
    onAlert: () => void;
    onClearAlerts: () => void;
    onScreenshot: () => void;
    /** 右键「全部K线」/「最新K线」（作用在鼠标最后点击的那格 ✓） */
    onFitAll?: () => void;
    onLastBars?: () => void;
    /** 关闭**鼠标最后点击的那一格**（布局里只剩一格时不会调用 ✓） */
    onCloseChart?: () => void;
}

function favoriteLabel(row: Record<string, unknown>): string {
    const provider = String(row.provider || '').trim();
    const label = String(row.label || row.key || '');
    return provider ? `${provider}.${label}` : label;
}

export function showChartContextMenu(spec: ChartContextSpec,
                                     x: number, y: number): void {
    const favoriteItems: MenuItem[] = spec.favorites.length
        ? spec.favorites.map((row) => ({
            label: favoriteLabel(row),
            run: () => spec.onAddFavorite(String(row.key || '')),
        }))
        : [{ label: '（还没有收藏的指标）', disabled: true }];

    const strategyItems: MenuItem[] = spec.strategies.length
        ? spec.strategies.map((row) => ({
            label: favoriteLabel(row),
            disabled: !row.path || !spec.onAddStrategy,
            run: () => spec.onAddStrategy?.(String(row.path || ''),
                                            String(row.key || '')),
        }))
        : [{ label: '（还没有收藏的策略）', disabled: true }];

    const cycleItems: MenuItem[] = spec.local
        ? [{ label: '本地图表：周期由数据决定', disabled: true }]
        : spec.cycleGroups.map((group) => ({
            label: group.label,
            submenu: group.items.map((item) => ({
                label: `${item.label}${item.value === spec.cycle ? '  ✓' : ''}`,
                run: () => spec.onCycle(item.value),
            })),
        }));

    const layoutPresets: MenuItem[] = spec.layoutItems
        || (spec.local
            ? [{ label: '本地图表：固定单图', disabled: true }]
            : [
                { label: '单图', run: () => spec.onLayoutPreset(1, 1) },
                { label: '左右两图', run: () => spec.onLayoutPreset(2, 1) },
                { label: '四图', run: () => spec.onLayoutPreset(2, 2) },
            ]);
    const savedLayouts: MenuItem[] = spec.layouts.map((row) => ({
        label: `${row.name || row.key}${row.favorite ? '  ★' : ''}`,
        run: () => spec.onLayoutApply(String(row.key || '')),
    }));
    if (savedLayouts.length) {
        layoutPresets.push({
            label: '已保存的布局', separator: true, submenu: savedLayouts,
        });
    }
    const favoriteLayouts: MenuItem[] = spec.layouts
        .filter((row) => row.favorite)
        .map((row) => ({
            label: String(row.name || row.key || ''),
            run: () => spec.onLayoutApply(String(row.key || '')),
        }));

    const items: MenuItem[] = [
        { label: '指标', run: spec.onIndicatorPicker },
        { label: '收藏指标', submenu: favoriteItems },
        { label: '收藏策略', submenu: strategyItems },
        { label: '删除指标策略', run: spec.onRemove },

        { label: '周期', separator: true, submenu: cycleItems },

        { label: '布局', separator: true, submenu: layoutPresets },
        {
            label: spec.canCloseChart ? '关闭图表' : '关闭图表（只有一格）',
            disabled: !spec.canCloseChart,
            run: spec.onCloseChart,
        },
        {
            label: '收藏布局',
            submenu: favoriteLayouts.length ? favoriteLayouts
                : [{ label: '（暂无收藏布局）', disabled: true }],
        },

        { label: '画线', separator: true, run: spec.onToggleToolBox },
        { label: '清除画线', run: spec.onClearDrawings },

        { label: '价格预警', separator: true, run: spec.onAlert },
        {
            label: '清除预警',
            disabled: !spec.hasAlerts,
            run: spec.onClearAlerts,
        },

        { label: '全部K线', separator: true, run: spec.onFitAll },
        { label: '最新K线（300 根）', run: spec.onLastBars },
        { label: '截图', separator: true, run: spec.onScreenshot },
    ];
    showMenu(x, y, items);
}
