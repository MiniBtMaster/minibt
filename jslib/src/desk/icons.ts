/**
 * Desk 工具栏图标 —— 单色 SVG（`currentColor`）✓
 *
 * 以前用 emoji（🗑 🧹 ✏️ 📷 🔔）：**颜色由系统字体决定，不跟主题**，
 * 浅色主题下又淡又花（用户反馈“图标描边比较淡”✗）。
 * 现在和 miniqt 一样用**线条图标**，颜色跟着工具栏文字色走 → 深浅主题都对 ✓
 */

const wrap = (body: string, size = 14): string => `<svg width="${size}"
    height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"
    aria-hidden="true">${body}</svg>`;

/** 🗑 删除指标 */
export const ICON_TRASH = wrap(
    '<path d="M3 6h18"/><path d="M8 6V4h8v2"/>'
    + '<path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/>');

/** 🧹 清除画线（橡皮擦） */
export const ICON_ERASER = wrap(
    '<path d="M7 21h10"/><path d="M5 15l6-6a2 2 0 0 1 2.8 0l3.2 3.2a2 2 0 0 1 0 2.8'
    + 'L14 18H9l-4-4z"/>');

/** ✏️ 画线工具 */
export const ICON_PENCIL = wrap(
    '<path d="M4 20h4L20 8a2.8 2.8 0 0 0-4-4L4 16v4z"/>'
    + '<path d="M14 6l4 4"/>');

/** 📷 截图 */
export const ICON_CAMERA = wrap(
    '<path d="M4 8h3l1.5-2h7L17 8h3v11H4z"/>'
    + '<circle cx="12" cy="13" r="3.2"/>');

/** 🔔 价格预警 */
export const ICON_BELL = wrap(
    '<path d="M18 15V10a6 6 0 1 0-12 0v5l-1.6 2.4h15.2L18 15z"/>'
    + '<path d="M10 19a2 2 0 0 0 4 0"/>');

/** ↻ 刷新（编辑器工具栏） */
export const ICON_REFRESH = `<svg width="14" height="14" viewBox="0 0 16 16"
    aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5"
    stroke-linecap="round" stroke-linejoin="round">
    <path d="M13.5 8a5.5 5.5 0 1 1-1.9-4.16"/>
    <path d="M13.6 1.9v3.2h-3.2"/></svg>`;

/** ⧉ 复制（复制全部代码，不是相机 ✓） */
export const ICON_COPY = `<svg width="14" height="14" viewBox="0 0 16 16"
    aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5"
    stroke-linecap="round" stroke-linejoin="round">
    <rect x="5.2" y="5.2" width="8.6" height="8.6" rx="1.4"/>
    <path d="M10.8 5.2V3.6A1.4 1.4 0 0 0 9.4 2.2H3.6A1.4 1.4 0 0 0 2.2 3.6v5.8"
    /><path d="M2.2 9.4v0"/></svg>`;

/** ↦ 前进一根（回放工具条） */
export const ICON_STEP = `<svg width="14" height="14" viewBox="0 0 16 16"
    aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6"
    stroke-linecap="round" stroke-linejoin="round">
    <path d="M2 8h9"/><path d="M8 4.5 L11.5 8 L8 11.5"/></svg>`;

/** ⏮ 回放（miniqt 的 rewind：两个向左三角） */
export const ICON_REWIND = `<svg width="14" height="14" viewBox="0 0 16 16"
    aria-hidden="true"><g fill="currentColor" stroke="none">
    <path d="M1.5 3 L1.5 13 L7.5 8 Z"/><path d="M8 3 L8 13 L14 8 Z"/>
    </g></svg>`;


/** ▶ 播放（回放工具条，实心） */
export const ICON_PLAY = `<svg width="14" height="14" viewBox="0 0 16 16"
    aria-hidden="true"><path d="M4 2.5 L13 8 L4 13.5 Z"
    fill="currentColor" stroke="none"/></svg>`;

/** ⏸ 暂停（回放工具条，实心） */
export const ICON_PAUSE = `<svg width="14" height="14" viewBox="0 0 16 16"
    aria-hidden="true"><g fill="currentColor" stroke="none">
    <rect x="3.5" y="2.5" width="3.5" height="11" rx=".6"/>
    <rect x="9" y="2.5" width="3.5" height="11" rx=".6"/>
    </g></svg>`;
