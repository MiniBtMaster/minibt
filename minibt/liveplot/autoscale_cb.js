// if (!window._bt_scale_range) {
//     window._bt_scale_range = function (range, min, max, pad) {
//         "use strict";
//         if (min !== Infinity && max !== -Infinity) {
//             pad = pad ? (max - min) * .03 : 0;
//             range.start = min - pad;
//             range.end = max + pad;
//         } else console.error('backtesting: scale range error:', min, max, range);
//     };
// }

// // if (!window._bt_scale_range) {
// //     window._x_scale_range = function (range, min, max, pad) {
// //         "use strict";
// //         if (min !== Infinity && max !== -Infinity) {
// //             range.start = min ;
// //             range.end = max + pad;
// //         } else console.error('backtesting: scale range error:', min, max, range);
// //     };
// // }

// clearTimeout(window._bt_autoscale_timeout);

// window._bt_autoscale_timeout = setTimeout(function () {
//     /**
//      * @variable cb_obj `fig_ohlc.x_range`.
//      * @variable source `ColumnDataSource`
//      * @variable ohlc_range `fig_ohlc.y_range`.
//      * @variable volume_range `fig_volume.y_range`.
//      */
//     "use strict";
//     let i = Math.max(Math.floor(cb_obj.start), 0),
//         j = Math.min(Math.ceil(cb_obj.end), source.data['High'].length);

//     let max = Math.max.apply(null, source.data['High'].slice(i, j)),
//         min = Math.min.apply(null, source.data['Low'].slice(i, j));

//     // let x = Math.max.apply(null, source.data['index'].slice(i, j)),
//     //     max_x = source.data['index'].length;
//     _bt_scale_range(ohlc_range, min, max, true);
//     if (indicator_range) {
//         for (i = 0; i < indicator_range.length; i++) {
//             let ii = Math.max(Math.floor(cb_obj.start), 0),
//                 jj = Math.min(Math.ceil(cb_obj.end), source.data[indicator_h[i]].length);

//             let max_ = Math.max.apply(null, source.data[indicator_h[i]].slice(ii, jj)),
//                 min_ = Math.min.apply(null, source.data[indicator_l[i]].slice(ii, jj));
//             _bt_scale_range(indicator_range[i], min_, max_, true);
//         }
//     }
//     // if (candles_range) {
//     //     for (ix = 0; ix < candles_range.length; ix++) {
//     //         _bt_scale_range(candles_range[ix], min, max, true);
//     //     }
//     // }
//     if (volume_range) {
//         max = Math.max.apply(null, source.data['volume'].slice(i, j));
//         _bt_scale_range(volume_range, 0, max * 1.03, false);
//     }
//     label_x = j + 100

// }, 50);

// ========== 修改 AUTOSCALE_JS_CALLBACK 代码 ==========
if (!window._bt_scale_range) {
    window._bt_scale_range = function (range, min, max, pad) {
        "use strict";
        if (min !== Infinity && max !== -Infinity && !isNaN(min) && !isNaN(max)) {
            pad = pad ? (max - min) * .03 : 0;
            range.start = min - pad;
            range.end = max + pad;
        } else console.error('backtesting: scale range error:', min, max, range);
    };
}

// 新增：更严格的参数校验
if (!cb_obj || !source || !source.data ||
    !source.data['High'] || !source.data['Low'] ||
    !ohlc_range) {
    console.warn('autoscale js: missing core data', {
        cb_obj: cb_obj,
        source: source,
        ohlc_range: ohlc_range
    });
    return;
}

clearTimeout(window._bt_autoscale_timeout);

window._bt_autoscale_timeout = setTimeout(function () {
    "use strict";
    let start = Math.max(Math.floor(cb_obj.start), 0),
        end = Math.min(Math.ceil(cb_obj.end), source.data['High'].length);

    // 新增：数据长度校验
    if (end - start < 1 || source.data['High'].length < 1) {
        console.warn('autoscale js: no data in range', { start, end, length: source.data['High'].length });
        return;
    }

    // 修复：使用slice后检查空数组
    let highSlice = source.data['High'].slice(start, end);
    let lowSlice = source.data['Low'].slice(start, end);
    if (highSlice.length === 0 || lowSlice.length === 0) {
        console.warn('autoscale js: empty slice', { start, end });
        return;
    }

    let max = Math.max.apply(null, highSlice),
        min = Math.min.apply(null, lowSlice);

    // 修复：NaN判断
    if (isNaN(max) || isNaN(min)) {
        console.warn('autoscale js: NaN values', { max, min });
        return;
    }

    _bt_scale_range(ohlc_range, min, max, true);

    if (indicator_range && indicator_h && indicator_l) {
        for (let idx = 0; idx < indicator_range.length; idx++) {
            let hKey = indicator_h[idx];
            let lKey = indicator_l[idx];
            // 新增：指标字段存在性校验
            if (!source.data[hKey] || !source.data[lKey]) {
                console.warn('autoscale js: missing indicator data', { hKey, lKey });
                continue;
            }

            let ii = Math.max(Math.floor(cb_obj.start), 0),
                jj = Math.min(Math.ceil(cb_obj.end), source.data[hKey].length);

            let hSlice = source.data[hKey].slice(ii, jj);
            let lSlice = source.data[lKey].slice(ii, jj);
            if (hSlice.length === 0 || lSlice.length === 0) {
                continue;
            }

            let max_ = Math.max.apply(null, hSlice),
                min_ = Math.min.apply(null, lSlice);

            if (!isNaN(max_) && !isNaN(min_)) {
                _bt_scale_range(indicator_range[idx], min_, max_, true);
            }
        }
    }

    if (volume_range && source.data['volume']) {
        let volSlice = source.data['volume'].slice(start, end);
        if (volSlice.length > 0) {
            let maxVol = Math.max.apply(null, volSlice);
            if (!isNaN(maxVol)) {
                _bt_scale_range(volume_range, 0, maxVol * 1.03, false);
            }
        }
    }

    label_x = end + 100;

}, 50);
