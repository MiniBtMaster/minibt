/**
 * ExportHistory — 导出历史菜单（报价页 / 看盘页共用 ✓）
 *
 *   ┌ q.csv  · 2 行 · 2026-10-18 13:18:03        ✕ ┐
 *   │ a.csv  · 1 行 · 2026-10-18 13:17:55        ✕ │
 *   ├───────────────────────────────────────────────┤
 *   │ 📂 打开导出文件夹                              │
 *   │ 🗑 清空历史                                    │
 *   └───────────────────────────────────────────────┘
 *
 * 点条目 = 用系统程序打开该文件（Qt → `QDesktopServices`，见后端 `open_export`）✓
 */
import { showMenuBelow, type MenuItem } from './menu';

export interface ExportRow {
    path: string;
    name?: string;
    rows?: number;
    at?: string;
}

export interface ExportHistoryHooks {
    /** 打开某个导出文件（`folder=true` → 打开所在文件夹） */
    onOpen?: (path: string, folder?: boolean) => void;
    /** 删除一条记录（只删记录，文件还在 ✓） */
    onDelete?: (path: string) => void;
    /** 清空历史（文件不动 ✓） */
    onClear?: () => void;
    /** 数量上限（默认 10 条 ✓） */
    limit?: number;
}

export function showExportHistory(
    anchor: HTMLElement | null,
    items: ExportRow[] | undefined,
    hooks: ExportHistoryHooks = {},
): void {
    if (!anchor) return;
    const rows = (items || []).slice(0, hooks.limit ?? 10);
    if (!rows.length) {
        showMenuBelow(anchor, [
            { label: '（还没有导出过文件）', disabled: true },
        ]);
        return;
    }
    const menu: MenuItem[] = rows.map((item) => ({
        label: `${item.name || item.path}`
            + (item.rows ? `  · ${item.rows} 行` : '')
            + (item.at ? `  · ${item.at}` : ''),
        run: () => hooks.onOpen?.(item.path),
        onDelete: hooks.onDelete ? () => hooks.onDelete?.(item.path) : undefined,
    }));
    menu.push({ label: '📂 打开导出文件夹', separator: true,
                run: () => hooks.onOpen?.(rows[0].path, true) });
    if (hooks.onClear) {
        menu.push({ label: '🗑 清空历史', run: () => hooks.onClear?.() });
    }
    showMenuBelow(anchor, menu);
}
