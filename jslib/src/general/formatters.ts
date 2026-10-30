/**
 * Declarative formatters.
 *
 * `localization.priceFormatter` / `timeFormatter` are synchronous JS callbacks,
 * so python cannot supply a function directly. Instead python supplies a small
 * *spec*, which is turned into a real JS function here. Users who need full
 * control can register a JS function by name:
 *
 *   Lib.registerFormatter('eur', value => '€' + value.toFixed(2))
 *
 * and then reference it from python: `chart.set_price_formatter('eur')`.
 */

export interface NumberFormatterSpec {
    /** fixed number of decimals; omit for the raw value */
    decimals?: number | null;
    /** group thousands with commas */
    thousands?: boolean;
    prefix?: string;
    suffix?: string;
    /** 1.2K / 3.4M / 5.6B */
    compact?: boolean;
}

export interface TimeFormatterSpec {
    /** e.g. 'YYYY-MM-DD HH:mm' (default 'YYYY-MM-DD') */
    template?: string;
    /** default true */
    utc?: boolean;
}

type FormatterFn = (value: any) => string;

const registry = new Map<string, FormatterFn>();

/** Register a JS formatter so it can be referenced by name from python. */
export function registerFormatter(name: string, fn: FormatterFn): void {
    registry.set(name, fn);
}

export function lookupFormatter(name: string): FormatterFn | undefined {
    return registry.get(name);
}

function formatNumber(value: number, spec: NumberFormatterSpec): string {
    if (typeof value !== 'number' || !isFinite(value)) {
        return String(value ?? '');
    }
    let text: string;
    if (spec.compact) {
        const magnitude = Math.abs(value);
        const decimals = spec.decimals ?? 2;
        if (magnitude >= 1e9) {
            text = (value / 1e9).toFixed(decimals) + 'B';
        } else if (magnitude >= 1e6) {
            text = (value / 1e6).toFixed(decimals) + 'M';
        } else if (magnitude >= 1e3) {
            text = (value / 1e3).toFixed(spec.decimals ?? 1) + 'K';
        } else {
            text = value.toFixed(spec.decimals ?? 0);
        }
    } else if (spec.decimals !== undefined && spec.decimals !== null) {
        text = value.toFixed(spec.decimals);
    } else {
        text = String(value);
    }

    if (spec.thousands) {
        const negative = text.startsWith('-');
        const body = negative ? text.slice(1) : text;
        const [whole, fraction] = body.split('.');
        const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        text = (negative ? '-' : '') + grouped + (fraction ? '.' + fraction : '');
    }
    return `${spec.prefix ?? ''}${text}${spec.suffix ?? ''}`;
}

export function makeNumberFormatter(spec: NumberFormatterSpec = {}): FormatterFn {
    return (value: number) => formatNumber(value, spec);
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function toDate(time: any): Date | null {
    if (time instanceof Date) return time;
    if (typeof time === 'number') {
        // seconds vs milliseconds vs a bare year
        if (time > 1e11) return new Date(time);
        if (time > 1e6) return new Date(time * 1000);
        return null;
    }
    if (time && typeof time === 'object' && 'year' in time) {
        return new Date(Date.UTC(time.year, (time.month ?? 1) - 1, time.day ?? 1));
    }
    return null;
}

export function makeTimeFormatter(spec: TimeFormatterSpec = {}): FormatterFn {
    const template = spec.template ?? 'YYYY-MM-DD';
    const utc = spec.utc !== false;
    return (time: any): string => {
        const date = toDate(time);
        if (!date) return String(time ?? '');
        const pad = (value: number, width = 2) => String(value).padStart(width, '0');
        const part = (method: string) =>
            (utc ? (date as any)['getUTC' + method]() : (date as any)['get' + method]());
        return template.replace(/YYYY|YY|MMM|MM|DD|HH|mm|ss/g, token => {
            switch (token) {
                case 'YYYY': return String(part('FullYear'));
                case 'YY': return pad(part('FullYear') % 100);
                case 'MMM': return MONTHS[part('Month')];
                case 'MM': return pad(part('Month') + 1);
                case 'DD': return pad(part('Date'));
                case 'HH': return pad(part('Hours'));
                case 'mm': return pad(part('Minutes'));
                case 'ss': return pad(part('Seconds'));
                default: return token;
            }
        });
    };
}

export function resolveFormatter(specOrName: NumberFormatterSpec | TimeFormatterSpec | string,
                                 kind: 'price' | 'time'): FormatterFn {
    if (typeof specOrName === 'string') {
        const found = registry.get(specOrName);
        if (!found) {
            throw new Error(`pylightcharts: no formatter registered as '${specOrName}'`);
        }
        return found;
    }
    return kind === 'time'
        ? makeTimeFormatter(specOrName as TimeFormatterSpec)
        : makeNumberFormatter(specOrName as NumberFormatterSpec);
}
