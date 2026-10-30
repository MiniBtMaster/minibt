/**
 * 指标断点（NaN 缺口）回归 —— `gapLineData()`：
 *
 * 1. **中间缺口一个都不能丢**：LWC v5 的 whitespace 只延长时间轴、不会断线，
 *    所以缺口点要补前值 + 染透明色（引擎按**线段起点颜色**决定画不画）。
 *    以前“空点比例 > 20% 就整段丢掉空点”，于是 `Chandelier_Exit` /
 *    `SuperTrend_STRATEGY` 这类「一半 up、一半 dn」（缺口在中间、占一半）的
 *    线会被一条直线从缺口上连过去（用户实测 ✗）。
 * 2. **首尾空点要裁掉**：策略只回放了一段时，前面成千上万个 NaN 会变成同样
 *    多的透明点，LWC 整条线都画不出来（副图 / 图例在，就是没线 ✗）。
 * 3. **有效点不带逐点颜色**，否则设置卡里改的线色永远不生效。
 */
import { describe, expect, it } from 'vitest';

import { GAP_COLOR, gapLineData } from '../src/desk/indicator';

type Row = [number, number | null];

describe('gapLineData', () => {
    it('中间缺口补前值 + 透明色，点数不变', () => {
        const rows: Row[] = [
            [1, 1], [2, 2], [3, 3], [4, null], [5, null], [6, 6], [7, 7],
        ];
        const out = gapLineData(rows);
        expect(out).toHaveLength(rows.length);
        expect(out[3]).toEqual({ time: 4, value: 3, color: GAP_COLOR });
        expect(out[4]).toEqual({ time: 5, value: 3, color: GAP_COLOR });
        // 有效点：值原样、**不带** color（序列颜色才生效 ✓）
        expect(out[5]).toEqual({ time: 6, value: 6 });
        expect(out[5]).not.toHaveProperty('color');
    });

    it('首尾空点裁掉（否则成千上万个透明点 → 整条线画不出来）', () => {
        const rows: Row[] = [
            [1, null], [2, null], [3, null],
            [4, 10], [5, null], [6, 12],
            [7, null], [8, null],
        ];
        const out = gapLineData(rows);
        expect(out.map((point) => point.time)).toEqual([4, 5, 6]);
        expect(out[1]).toEqual({ time: 5, value: 10, color: GAP_COLOR });
    });

    it('一半以上是缺口也要断线（Chandelier_Exit：长段交替）', () => {
        // 60 根：15 有效 / 15 空 / 15 有效 / 5 空 / 10 有效 —— 空点占 33% > 20% ✓
        const rows: Row[] = [];
        for (let index = 0; index < 60; index += 1) {
            const blank = (index >= 15 && index < 30)
                || (index >= 45 && index < 50);
            rows.push([index + 1, blank ? null : index + 1]);
        }
        const out = gapLineData(rows);
        // 中间缺口不能丢（丢了线就连过去了 ✗）
        expect(out).toHaveLength(60);
        expect(out[15].color).toBe(GAP_COLOR);
        expect(out[45].color).toBe(GAP_COLOR);
        expect(out[50]).not.toHaveProperty('color');
        // 缺口里补的是前值 → 引擎画出一条平线，但因为起点透明，看不见 ✓
        expect(out[15].value).toBe(15);
    });

    it('缺口点颜色可以被 hist 分支识别（值有、颜色是透明）', () => {
        const out = gapLineData([[1, 1], [2, null], [3, 3]] as Row[]);
        expect(out[1].value).toBe(1);
        expect(out[1].color).toBe('rgba(0,0,0,0)');
    });

    it('全是空点 → 空数组（不建序列）', () => {
        expect(gapLineData([[1, null], [2, null]] as Row[])).toEqual([]);
        expect(gapLineData([])).toEqual([]);
    });

    it('数值里混着 undefined / NaN 也当缺口', () => {
        const out = gapLineData([
            [1, 5],
            [2, undefined],
            [3, Number.NaN],
            [4, 8],
        ] as Array<[number, number | null | undefined]>);
        expect(out).toHaveLength(4);
        expect(out[1].color).toBe(GAP_COLOR);
        expect(out[2].color).toBe(GAP_COLOR);
        expect(out[3]).toEqual({ time: 4, value: 8 });
    });
});
