/**
 * Fast bulk data transfer.
 *
 * Passing large arrays as JavaScript source text is slow: the payload has to be
 * serialized to decimal strings, shipped, re-parsed and re-evaluated. Instead we
 * ship a base64-encoded column-major Float64 buffer and rebuild the rows here.
 *
 * Layout: one contiguous block of `columns.length` columns, each `rowCount`
 * values, i.e. `floats[columnIndex * rowCount + rowIndex]`.
 *
 * NaN values are omitted so they become whitespace data points, exactly like
 * the JSON path.
 */
export function decodeData(
    base64: string,
    columns: string[],
    strings?: Record<string, Array<string | null>>,
): Array<Record<string, unknown>> {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    const floats = new Float64Array(bytes.buffer);
    const columnCount = columns.length;
    const rowCount = columnCount > 0 ? Math.floor(floats.length / columnCount) : 0;

    const rows = new Array<Record<string, unknown>>(rowCount);
    for (let r = 0; r < rowCount; r++) {
        const row: Record<string, unknown> = {};
        for (let c = 0; c < columnCount; c++) {
            const value = floats[c * rowCount + r];
            if (!Number.isNaN(value)) {
                row[columns[c]] = value;
            }
        }
        rows[r] = row;
    }

    if (strings) {
        for (const key of Object.keys(strings)) {
            const values = strings[key];
            for (let r = 0; r < rowCount; r++) {
                const value = values[r];
                if (value !== null && value !== undefined) {
                    rows[r][key] = value;
                }
            }
        }
    }
    return rows;
}
