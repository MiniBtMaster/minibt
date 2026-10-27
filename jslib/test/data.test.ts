import { describe, expect, it } from 'vitest';
import { decodeData } from '../src/general/data';

function encode(values: number[]): string {
    const bytes = new Uint8Array(new Float64Array(values).buffer);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    return btoa(binary);
}

describe('decodeData', () => {
    it('rebuilds column-major rows', () => {
        // columns: time = [1,2,3], close = [10.5,11.5,12.5]
        const rows = decodeData(encode([1, 2, 3, 10.5, 11.5, 12.5]), ['time', 'close']);
        expect(rows).toEqual([
            { time: 1, close: 10.5 },
            { time: 2, close: 11.5 },
            { time: 3, close: 12.5 },
        ]);
    });

    it('turns NaN into whitespace points', () => {
        const rows = decodeData(encode([1, 2, 1, NaN]), ['time', 'close']);
        expect(rows[0]).toEqual({ time: 1, close: 1 });
        expect(rows[1]).toEqual({ time: 2 });
    });

    it('merges string columns', () => {
        const rows = decodeData(encode([1, 2, 1, 2]), ['time', 'value'], { color: ['#a', null] });
        expect((rows[0] as any).color).toBe('#a');
        expect((rows[1] as any).color).toBeUndefined();
    });

    it('handles empty input', () => {
        expect(decodeData('', ['time'])).toEqual([]);
    });

    it('handles a large payload', () => {
        const rows = 5000;
        const buffer: number[] = [];
        for (let i = 0; i < rows; i++) buffer.push(i);
        for (let i = 0; i < rows; i++) buffer.push(i * 2);
        const decoded = decodeData(encode(buffer), ['time', 'value']);
        expect(decoded).toHaveLength(rows);
        expect(decoded[rows - 1]).toEqual({ time: rows - 1, value: (rows - 1) * 2 });
    });
});
