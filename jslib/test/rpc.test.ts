import { beforeEach, describe, expect, it } from 'vitest';
import { applyOptions, deepMerge, invoke, lookup, register, unregister } from '../src/general/rpc';

describe('lookup', () => {
    beforeEach(() => {
        unregister('thing');
        unregister('outer');
    });

    it('resolves registered handles', () => {
        const target = { value: 1 };
        register('thing', target);
        expect(lookup('thing')).toBe(target);
    });

    it('throws for an unknown handle', () => {
        expect(() => lookup('definitely-not-registered')).toThrow(/cannot resolve/);
    });

    it('resolves a sub-path of a registered handle', () => {
        const inner = { a: 1 };
        register('outer', { inner });
        expect(lookup('outer.inner')).toBe(inner);
    });

    it('falls back to global paths', () => {
        (globalThis as any).__plc_test = { nested: { value: 42 } };
        expect((lookup('__plc_test.nested') as any).value).toBe(42);
    });

    it('unregisters handles', () => {
        register('thing', {});
        unregister('thing');
        expect(() => lookup('thing')).toThrow();
    });
});

describe('invoke', () => {
    it('calls a method with arguments', () => {
        register('math', { add: (a: number, b: number) => a + b });
        expect(invoke('math', 'add', [2, 3])).toBe(5);
    });

    it('stores the return value under storeAs', () => {
        register('factory', { make: () => ({ made: true }) });
        invoke('factory', 'make', [], 'made-thing');
        expect((lookup('made-thing') as any).made).toBe(true);
    });

    it('reports a missing method', () => {
        register('empty', {});
        expect(() => invoke('empty', 'nope')).toThrow(/is not a function/);
    });

    it('resolves $ref arguments to live objects', () => {
        const dependency = { name: 'dep' };
        register('dep', dependency);
        register('collector', { take: (arg: unknown) => arg });
        expect(invoke('collector', 'take', [{ $ref: 'dep' }])).toBe(dependency);
    });

    it('resolves $ref nested in arrays and objects', () => {
        const dependency = { id: 'a' };
        register('dep-a', dependency);
        register('collector-2', { take: (arg: any) => arg });
        const result = invoke('collector-2', 'take', [[{ $ref: 'dep-a' }]]) as any[];
        expect(result[0].id).toBe('a');
    });
});

describe('applyOptions / deepMerge', () => {
    it('forwards to applyOptions', () => {
        const received: unknown[] = [];
        register('opts', { applyOptions: (options: unknown) => received.push(options) });
        applyOptions('opts', { lineWidth: 2 });
        expect(received).toEqual([{ lineWidth: 2 }]);
    });

    it('merges nested objects', () => {
        expect(deepMerge({ a: { b: 1, c: 2 } }, { a: { c: 3 } })).toEqual({ a: { b: 1, c: 3 } });
    });

    it('replaces arrays', () => {
        expect(deepMerge({ a: [1, 2] }, { a: [3] })).toEqual({ a: [3] });
    });
});
