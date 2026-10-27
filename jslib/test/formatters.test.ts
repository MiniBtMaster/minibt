import { describe, expect, it } from 'vitest';
import {
    makeNumberFormatter, makeTimeFormatter, registerFormatter, resolveFormatter,
} from '../src/general/formatters';

const TIMESTAMP = Date.UTC(2024, 0, 2, 3, 4, 5) / 1000;   // 2024-01-02 03:04:05 UTC

describe('number formatter', () => {
    it('formats decimals, thousands and a prefix', () => {
        const format = makeNumberFormatter({ decimals: 2, thousands: true, prefix: '$' });
        expect(format(1234567.891)).toBe('$1,234,567.89');
    });

    it('keeps the sign with thousands separators', () => {
        expect(makeNumberFormatter({ decimals: 1, thousands: true })(-1234.5)).toBe('-1,234.5');
    });

    it('omits decimals when not requested', () => {
        expect(makeNumberFormatter({})(3.14159)).toBe('3.14159');
    });

    it('compacts large numbers', () => {
        expect(makeNumberFormatter({ compact: true })(1234)).toBe('1.2K');
        expect(makeNumberFormatter({ compact: true })(12345)).toBe('12.3K');
        expect(makeNumberFormatter({ compact: true })(1500000)).toBe('1.50M');
        expect(makeNumberFormatter({ compact: true })(999)).toBe('999');
    });

    it('appends a suffix', () => {
        expect(makeNumberFormatter({ decimals: 1, suffix: '%' })(12.34)).toBe('12.3%');
    });

    it('passes non-finite values through as text', () => {
        expect(makeNumberFormatter({})(NaN as unknown as number)).toBe('NaN');
    });
});

describe('time formatter', () => {
    it('formats a unix timestamp', () => {
        expect(makeTimeFormatter({ template: 'YYYY-MM-DD HH:mm:ss' })(TIMESTAMP))
            .toBe('2024-01-02 03:04:05');
    });

    it('formats a millisecond timestamp', () => {
        expect(makeTimeFormatter({ template: 'YYYY-MM-DD' })(TIMESTAMP * 1000)).toBe('2024-01-02');
    });

    it('supports month names and short years', () => {
        expect(makeTimeFormatter({ template: 'MMM DD, YY' })(TIMESTAMP)).toBe('Jan 02, 24');
    });

    it('formats business day objects', () => {
        expect(makeTimeFormatter({ template: 'YYYY-MM-DD' })({ year: 2024, month: 3, day: 9 }))
            .toBe('2024-03-09');
    });

    it('falls back to the raw value when it cannot parse', () => {
        expect(makeTimeFormatter({})(null as unknown as number)).toBe('');
    });
});

describe('formatter registry', () => {
    it('resolves a registered formatter by name', () => {
        registerFormatter('eur', value => '\u20ac' + value.toFixed(2));
        const resolved = resolveFormatter('eur', 'price');
        expect(resolved(12.5)).toBe('\u20ac12.50');
    });

    it('throws for an unknown name', () => {
        expect(() => resolveFormatter('nope', 'price')).toThrow(/no formatter registered/);
    });

    it('builds a formatter from a spec', () => {
        expect(resolveFormatter({ decimals: 0, suffix: '!' }, 'price')(9.6)).toBe('10!');
    });
});
