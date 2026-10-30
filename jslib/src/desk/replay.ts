/**
 * Replay — K 线**回放**（复刻 miniqt 的回放：播放 / 暂停 / 单步 / 速度）。
 *
 * 后端只负责把一段历史 K 线交给前端（`{type:'replay', bars, speed}`），
 * 之后**完全在前端逐根播放**（不联网、不打后端 ✓）。
 */
export interface ReplayBar {
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
}

export interface ReplayOptions {
    /**
     * 每根回放。
     *
     * `advance` = 这一次是**真的往前走了**（播放 tick / 前进一根）；
     * 进入回放、暂停、seek 的刷新都是 `false` —— 后端据此决定是否让策略
     * 跑 `next()` / 成交（用户要求：点回放不能先成交 ✗）。
     */
    onBars: (bars: ReplayBar[], finished: boolean,
             advance?: boolean) => void;
    onState?: (state: { playing: boolean; index: number; total: number }) => void;
}

/** 每秒播放多少根（速度档位 ✓） */
/** 速度档位（和 miniqt 一致：0.5x / 1x / 2x / 4x ✓） */
export const REPLAY_SPEEDS: Array<[string, number]> = [
    ['0.5x', 2], ['1x', 5], ['2x', 10], ['4x', 20],
];

/** 「选择时间段」的比例（从已加载数据里取开始位置 ✓） */
export const REPLAY_SEEKS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9];

export class Replay {
    private bars: ReplayBar[] = [];
    private index = 0;
    private speed = 5;             // 每秒根数
    private timer: number | undefined;
    private playing = false;

    constructor(private readonly options: ReplayOptions) {}

    get active(): boolean {
        return this.bars.length > 0;
    }

    get isPlaying(): boolean {
        return this.playing;
    }

    get progress(): { index: number; total: number } {
        return { index: this.index, total: this.bars.length };
    }

    /** 装载一段历史（`seek` = 从哪开始，0.3 = 30% 处，和 miniqt 一样 ✓） */
    load(bars: ReplayBar[], speed = 5, seek = 0.1): void {
        this.stop();
        this.bars = bars.slice();
        this.speed = Math.max(1, speed);
        const ratio = Math.min(0.95, Math.max(0.02, seek));
        // 先显示前面一部分（避免空图），位置按比例算 ✓
        // ★ 少于 5 根时不能 `max(5)` 超过总数（1–4 根回放进度会错 ✗）
        this.index = this.bars.length
            ? Math.max(1, Math.min(this.bars.length,
                                   Math.round(this.bars.length * ratio)))
            : 0;
        this._emit(false, false);
    }

    /** 拖动 / 点「选择时间段」→ 直接跳到某个比例（0..1 ✓） */
    seek(fraction: number): void {
        if (!this.active) return;
        const ratio = Math.min(1, Math.max(0, fraction));
        this.index = this.bars.length
            ? Math.max(1, Math.round(this.bars.length * ratio)) : 0;
        this._emit(this.index >= this.bars.length, false);
    }

    start(): void {
        if (!this.active) return;
        if (this.index >= this.bars.length) {
            // 播完了再点播放 → 从 30% 处重新来（miniqt 同款 ✓）
            this.index = this.bars.length
                ? Math.max(1, Math.round(this.bars.length * 0.3)) : 0;
        }
        this.playing = true;
        this._tick();
        this._emit(false, false);
    }

    pause(): void {
        this.playing = false;
        if (this.timer !== undefined) {
            window.clearInterval(this.timer);
            this.timer = undefined;
        }
        this._emit(false, false);
    }

    step(): void {
        this.pause();
        if (this.index < this.bars.length) this.index += 1;
        this._emit(this.index >= this.bars.length, true);
    }

    setSpeed(perSecond: number): void {
        this.speed = Math.max(1, perSecond);
        if (this.playing) {
            this.pause();
            this.start();
        }
    }

    /** 退出回放（恢复实时） */
    stop(): void {
        this.pause();
        this.bars = [];
        this.index = 0;
        this._emit(false, false);
    }

    private _tick(): void {
        if (this.timer !== undefined) window.clearInterval(this.timer);
        this.timer = window.setInterval(() => {
            if (!this.playing) return;
            this.index = Math.min(this.bars.length, this.index + 1);
            const finished = this.index >= this.bars.length;
            this._emit(finished, true);
            if (finished) this.pause();
        }, Math.max(50, Math.round(1000 / this.speed)));
    }

    private _emit(finished: boolean, advance = false): void {
        this.options.onBars(this.bars.slice(0, this.index), finished, advance);
        this.options.onState?.({
            playing: this.playing, index: this.index, total: this.bars.length,
        });
    }
}
