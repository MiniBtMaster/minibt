import { beforeEach, describe, expect, it } from 'vitest';

import { Legend } from '../src/general/legend';
import { DomStub, StubElement, installDom } from './dom';

let dom: DomStub;

beforeEach(() => {
    dom = installDom();
});

// `legendTimeFormat` does not touch `this`, so the prototype method is enough.
const formatTime = (time: any): string =>
    (Legend.prototype as any).legendTimeFormat(time);

describe('legend time format (one-line readout)', () => {
    it('formats a lightweight-charts business day', () => {
        expect(formatTime({ year: 2024, month: 1, day: 2 })).toBe('2024-01-02');
    });

    it('shows only the date for a daily bar (00:00 UTC)', () => {
        expect(formatTime(Date.UTC(2024, 0, 2) / 1000)).toBe('2024-01-02');
    });

    it('adds HH:mm for an intraday bar', () => {
        expect(formatTime(Date.UTC(2024, 0, 2, 3, 4, 5) / 1000))
            .toBe('2024-01-02 03:04');
    });

    it('returns an empty string when there is no time', () => {
        expect(formatTime(undefined)).toBe('');
        expect(formatTime(null)).toBe('');
    });
});

describe('legend collapse button', () => {
    function makeLegend(): any {
        const legend: any = Object.create(Legend.prototype);
        legend.div = new StubElement('div');
        legend.seriesContainer = new StubElement('div');
        return legend;
    }

    it('hides itself with no rows and toggles the rows', () => {
        const legend = makeLegend();
        legend.enableCollapse();
        const button = legend.div.children[0] as StubElement;
        expect(button.style.display).toBe('none');

        legend.seriesContainer.appendChild(new StubElement('div'));
        button.click();
        expect(button.textContent).toBe('∨ 1');
        expect(button.style.display).toBe('block');
        expect(legend.seriesContainer.style.display).toBe('none');

        button.click();
        expect(button.textContent).toBe('∧');
        expect(legend.seriesContainer.style.display).toBe('');
    });

    it('is idempotent (one button per chart)', () => {
        const legend = makeLegend();
        legend.enableCollapse();
        legend.enableCollapse();
        expect(legend.div.children.length).toBe(1);
    });
});
