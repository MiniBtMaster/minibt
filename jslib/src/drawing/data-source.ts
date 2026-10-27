import {
    BusinessDay,
    Logical,
    Time,
} from 'lightweight-charts';

export interface Point {
    time: Time | null;
    logical: Logical;
    price: number;
}

export interface DiffPoint {
    logical: number;
    price: number;
}

/** `Time` -> 秒（`BusinessDay` 按 UTC 零点算）；不是时间就返回 null */
export function toSeconds(time: Time | null): number | null {
    if (time == null) return null;
    if (typeof time === 'number') return time;
    if (typeof time === 'string') {
        const parsed = Date.parse(time);
        return Number.isNaN(parsed) ? null : Math.floor(parsed / 1000);
    }
    const day = time as BusinessDay;
    if (typeof day.year === 'number') {
        return Date.UTC(day.year, day.month - 1, day.day) / 1000;
    }
    return null;
}

/**
 * 把 bar 序号夹到 `[0, count - 1]`。
 *
 * 用于没有时间锚的点：它的 `logical` 是在**另一个周期**里量出来的，直接拿到当前周期用
 * 会跑到可见范围之外（例如 1 分钟图的第 480 根，而 5 分钟图只有 120 根），画线看起来
 * 就像“丢了”。
 */
export function clampLogical(logical: number, count: number): Logical {
    if (!Number.isFinite(logical) || count <= 0) return 0 as Logical;
    // 不要取整：logical 允许是小数（点落在两根 bar 之间），取整会把跨周期插值出来的
    // 位置抹到相邻的 bar 上 —— 日线上就差整整一天。
    return Math.min(count - 1, Math.max(0, logical)) as Logical;
}


/**
 * `Time` -> bar 序号（可以是小数）。
 *
 * 渲染画线用的是 `logical`（见 `pane-view._getX`），而 `logical` 只在**保存它的那个
 * 周期**里成立。切周期后要拿 `time` 重算，这里用**当前周期的 bar 时间数组**做二分查找：
 *
 * - 精确命中 -> 直接用它；
 * - 落在两根 bar 之间 -> **按时间线性插值**（于是 1 小时图 13:00 的线在日线上落在
 *   「第 300 天 + 13/24」的位置，时间段保持一致）；
 * - 早于首根 / 晚于末根 -> 吸附到两端。
 *
 * **不用 `timeScale().timeToCoordinate()`**：那个依赖布局，图表还没渲染/尺子宽度为 0 时
 * 它会返回一个错误的坐标（实测是 0）而不是 `null`，于是点会被映射到任意位置。用 bar
 * 时间数组则是确定性的，也与是否已经渲染无关。
 */
export function timeToLogical(times: number[], time: Time | null): number | null {
    const target = toSeconds(time);
    if (target === null || times.length === 0) return null;
    if (target <= times[0]) return 0 as Logical;
    if (target >= times[times.length - 1]) return (times.length - 1) as Logical;

    // 二分找到第一个 >= target 的 bar
    let low = 0;
    let high = times.length - 1;
    while (low < high) {
        const mid = (low + high) >> 1;
        if (times[mid] < target) low = mid + 1;
        else high = mid;
    }
    if (times[low] === target) return low as Logical;

    const before = low - 1;
    const span = times[low] - times[before];
    const fraction = span > 0 ? (target - times[before]) / span : 0;
    return (before + Math.min(1, Math.max(0, fraction))) as Logical;
}
