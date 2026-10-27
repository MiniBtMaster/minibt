/**
 * minibt desk 顶栏 LOGO（两套：深色 / 浅色）。
 *
 * 图形：4 根蜡烛 + 一条上升趋势线 = “看盘 / 行情终端”；
 * 文字：`minibt`（粗体）+ `desk`（细体，字距略大）。
 *
 * 两套配色分开写死（而不是 `currentColor`），这样在深色 / 浅色主题下
 * 都有足够的对比度，也不会被宿主页的 `color` 意外覆盖 ✓。
 */

export const DESK_LOGO_DARK = `<svg xmlns="http://www.w3.org/2000/svg"
    width="126" height="22" viewBox="0 0 126 22" fill="none"
    role="img" aria-label="minibt desk">
  <path d="M2 18.5L8.5 13.2L14 15.2L21.5 5.6"
        stroke="#38bdf8" stroke-width="1.6" stroke-linecap="round"
        stroke-linejoin="round" opacity=".9"/>
  <rect x="1.5" y="8" width="3" height="8" rx="1" fill="#2dd4bf"/>
  <rect x="6.5" y="4.5" width="3" height="10" rx="1" fill="#38bdf8"/>
  <rect x="11.5" y="9.5" width="3" height="7" rx="1" fill="#2dd4bf"/>
  <rect x="16.5" y="3.5" width="3" height="8" rx="1" fill="#60a5fa"/>
  <rect x="71" y="5" width="1" height="12" rx=".5" fill="#2a303a"/>
  <text x="27" y="16"
        font-family="Segoe UI, Inter, Arial, sans-serif"
        font-size="14.5" font-weight="700" letter-spacing="-.2"
        fill="#e8eaed">minibt</text>
  <text x="76" y="16"
        font-family="Segoe UI, Inter, Arial, sans-serif"
        font-size="13" font-weight="500" letter-spacing=".6"
        fill="#8b93a1">desk</text>
</svg>`;

export const DESK_LOGO_LIGHT = `<svg xmlns="http://www.w3.org/2000/svg"
    width="126" height="22" viewBox="0 0 126 22" fill="none"
    role="img" aria-label="minibt desk">
  <path d="M2 18.5L8.5 13.2L14 15.2L21.5 5.6"
        stroke="#1a73e8" stroke-width="1.6" stroke-linecap="round"
        stroke-linejoin="round" opacity=".9"/>
  <rect x="1.5" y="8" width="3" height="8" rx="1" fill="#0f9d8a"/>
  <rect x="6.5" y="4.5" width="3" height="10" rx="1" fill="#1a73e8"/>
  <rect x="11.5" y="9.5" width="3" height="7" rx="1" fill="#34b3a0"/>
  <rect x="16.5" y="3.5" width="3" height="8" rx="1" fill="#4285f4"/>
  <rect x="71" y="5" width="1" height="12" rx=".5" fill="#d9dee6"/>
  <text x="27" y="16"
        font-family="Segoe UI, Inter, Arial, sans-serif"
        font-size="14.5" font-weight="700" letter-spacing="-.2"
        fill="#1f2329">minibt</text>
  <text x="76" y="16"
        font-family="Segoe UI, Inter, Arial, sans-serif"
        font-size="13" font-weight="500" letter-spacing=".6"
        fill="#6b7280">desk</text>
</svg>`;

export function deskLogo(theme: 'light' | 'dark'): string {
    return theme === 'light' ? DESK_LOGO_LIGHT : DESK_LOGO_DARK;
}
