// 策略图表前端驱动（`miniqt_backtest_chart.DESK_DRIVER_JS`）的行为测试。
// 用最小假 LWC 跑：回放截断 / 图表类型 / 画线工具 / 删除画线 ✓
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// 驱动源码路径由调用方传入（pytest 会把 `DESK_DRIVER_JS` 写到临时文件）✓
const DRIVER_PATH = process.argv[2]
  || path.join(__dirname, '..', '..', '_driver_under_test.js');
const source = fs.readFileSync(DRIVER_PATH, 'utf8');

function makeSeries(rows) {
  let data = rows;
  return {
    rows,
    data() { return data; },
    setData(next) { data = next; },
    applyOptions(options) { this.options = { ...(this.options || {}), ...options }; },
    priceScale() { return { applyOptions() {} }; },
    seriesType: 'Line',
  };
}

function makeChart() {
  const created = [];
  return {
    created,
    removed: [],
    priceScale() { return { applyOptions() {} }; },
    addSeries(def, options, pane) {
      const series = makeSeries([]);
      series.seriesType = def === 'Line' ? 'Line' : (def || 'Line');
      series.pane = pane;
      created.push(series);
      return series;
    },
    removeSeries(series) { this.removed.push(series); },
    scale: {
      range: null,
      history: [],
      setVisibleLogicalRange(range) {
        this.range = range;
        this.history.push({ from: range.from, to: range.to });
      },
      getVisibleLogicalRange() {
        return this.range || { from: 0, to: 300 };
      },
    },
    timeScale() { return this.scale; },
  };
}

function build(bars) {
  const time = Array.from({ length: bars }, (_, i) => 1700000000 + i * 86400);
  const candles = time.map((t, i) => ({
    time: t, open: 100 + i, high: 102 + i, low: 99 + i, close: 101 + i,
  }));
  const line = time.map((t, i) => ({ time: t, value: 100 + i }));
  const candleSeries = makeSeries(candles);
  const volume = makeSeries(time.map((t) => ({ time: t, value: 10 })));
  const ma = makeSeries(line);
  const chart = makeChart();
  const handler = {
    chart,
    series: candleSeries,
    volumeSeries: volume,
    _seriesList: [volume, ma],
    toolBox: {
      cleared: 0,
      clearDrawings() { this.cleared += 1; },
    },
  };
  return { handler, candleSeries, volume, ma, chart };
}

function makeContext(handler) {
  const timers = [];
  const messages = [];
  const bodyClasses = new Set();
  const sandbox = {
    console,
    setInterval(fn) { timers.push(fn); return timers.length; },
    clearInterval() {},
    parent: { postMessage: (data) => messages.push(data) },
    document: {
      readyState: 'complete',
      body: {
        classList: {
          toggle(name, on) { if (on) bodyClasses.add(name); else bodyClasses.delete(name); },
          contains(name) { return bodyClasses.has(name); },
        },
      },
    },
    LightweightCharts: {
      LineSeries: 'Line', AreaSeries: 'Area', BarSeries: 'Bar',
    },
    addEventListener(type, fn) {
      if (type === 'message') sandbox.__onMessage = fn;
    },
    __handler: handler,
  };
  sandbox.window = sandbox;
  sandbox.Object = Object;
  sandbox.window.__deskSLHandler = handler;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox);
  return { sandbox, timers, messages };
}

function run() {
  const fails = [];
  const check = (name, ok, extra) => {
    if (!ok) fails.push(`${name} ${extra === undefined ? '' : JSON.stringify(extra)}`);
  };

  // ---- 回放：逐根放出，指标跟着截断
  const fixture = build(50);
  const { sandbox, messages } = makeContext(fixture.handler);
  const api = sandbox.__deskSL;
  check('driver exposes api', !!api && typeof api.command === 'function');

  api.command('replayStart', { bars: 10 });
  check('replay state', api.state.replay === true);
  check('replay bars', api.state.bars === 10, api.state.bars);
  // K 线两端各补了 `padLen` 根空白（能看到 -100 / 长度+100）✓
  const pad = (api.state.padLen || 0) * 2;
  check('candles truncated (with pad)',
        fixture.candleSeries.data().length === pad + 10,
        { len: fixture.candleSeries.data().length, pad });
  check('indicator truncated', fixture.ma.data().length === 10,
        fixture.ma.data().length);
  check('volume truncated', fixture.volume.data().length === 10);

  api.command('replayStep', {});
  check('step +1', api.state.bars === 11, api.state.bars);

  api.command('replaySeek', { frac: 0.5 });
  check('seek 50%', api.state.bars === 25, api.state.bars);

  api.command('replayExit', {});
  check('exit restores', fixture.candleSeries.data().length === pad + 50,
        { len: fixture.candleSeries.data().length, pad });
  check('exit replay flag', api.state.replay === false);

  // ---- 图表类型：收盘线（隐藏蜡烛 + 新序列用 close）
  api.command('type', { kind: 'line' });
  check('kind line', api.state.kind === 'line', api.state.kind);
  check('candle hidden', fixture.candleSeries.options.visible === false,
        fixture.candleSeries.options);
  const alt = fixture.chart.created[fixture.chart.created.length - 1];
  check('alt created', !!alt && alt.pane === 0);
  check('alt uses close', alt.data().length === 50
        && alt.data()[0].value === 101, alt.data()[0]);
  check('alt type line', alt.seriesType === 'Line', alt.seriesType);

  // 切回蜡烛：新序列移除、蜡烛重新可见
  api.command('type', { kind: 'candle' });
  check('alt removed', fixture.chart.removed.length === 1);
  check('candle visible', fixture.candleSeries.options.visible === true);

  // 柱状（OHLC 原样）
  api.command('type', { kind: 'bar' });
  const bar = fixture.chart.created[fixture.chart.created.length - 1];
  check('bar keeps ohlc', 'open' in bar.data()[0] && 'high' in bar.data()[0]);
  check('bar type', bar.seriesType === 'Bar', bar.seriesType);

  // ---- 画线工具 / 删除画线
  api.command('toolbox', { show: true });
  check('toolbox class on', sandbox.document.body.classList.contains('desk-sl-toolbox'));
  check('toolbox state', api.state.toolbox === true);
  api.command('toolbox', { show: false });
  check('toolbox class off', !sandbox.document.body.classList.contains('desk-sl-toolbox'));

  api.command('clearDrawings', {});
  check('drawings cleared', fixture.handler.toolBox.cleared === 1,
        fixture.handler.toolBox.cleared);

  // ---- 回放：可视范围宽度恒定（新增一根 → 整体左移一根）✓
  const nextFixture = build(60);
  const nextCtx = makeContext(nextFixture.handler);
  const nextApi = nextCtx.sandbox.__deskSL;
  nextFixture.chart.scale.setVisibleLogicalRange({ from: 0, to: 40 });
  nextApi.command('replayStart', { bars: 20 });
  const scale = nextFixture.chart.scale;
  const startRange = { from: scale.range.from, to: scale.range.to };
  const width = startRange.to - startRange.from;
  check('replay width kept', Math.round(width) === 40, width);

  // 用户缩放（宽度变大）→ 后续每根只平移，缩放级别不能被拉回去 ✓
  scale.setVisibleLogicalRange({ from: 5, to: 85 });
  const zoomed = { from: scale.range.from, to: scale.range.to };
  for (let i = 0; i < 5; i += 1) nextApi.command('replayStep', {});
  const after = { from: scale.range.from, to: scale.range.to };
  check('zoom kept after steps',
        Math.round(after.to - after.from) === Math.round(zoomed.to - zoomed.from),
        { zoomed, after });
  // 「最新 K 线到右边界的距离」必须保持（缩放前 bars=20 → 最新下标 19）✓
  check('right gap kept',
        Math.round(after.to - (nextApi.state.bars - 1))
        === Math.round(zoomed.to - 19), { zoomed, after, bars: nextApi.state.bars });
  check('replay shifts left', after.to > zoomed.to, { zoomed, after });

  // 拖到历史里（最新一根在视窗右侧之外）→ 不再打扰 ✓
  scale.setVisibleLogicalRange({ from: 0, to: 10 });
  const history = { from: scale.range.from, to: scale.range.to };
  nextApi.command('replayStep', {});
  check('history view untouched',
        Math.round(scale.range.from) === Math.round(history.from)
        && Math.round(scale.range.to) === Math.round(history.to),
        { history, now: scale.range });

  // 未变化的序列不再 setData（回测结果图每个 tick 十几条序列，防卡 ✓）
  const calls = { candle: 0 };
  const original = nextFixture.candleSeries.setData;
  nextFixture.candleSeries.setData = function (data) {
    calls.candle += 1;
    return original.call(this, data);
  };
  nextApi.command('replaySeek', { frac: 0.5 });
  const samePos = calls.candle;
  nextApi.command('replaySeek', { frac: 0.5 });     // 同一位置 → 不重发 ✓
  check('unchanged series skipped', calls.candle === samePos,
        { before: samePos, now: calls.candle });

  // ---- 状态回传父窗口
  const state = messages.filter((m) => m.__deskSL === 'state').pop();
  check('posts state to parent', !!state && state.total === 50, state);

  if (fails.length) {
    console.error('FAILED:\n' + fails.join('\n'));
    process.exit(1);
  }
  console.log('strategy driver: all checks passed');
}

run();
