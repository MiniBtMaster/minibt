# Events

Handlers are attached with `+=` on `chart.events` and receive the chart as their
first argument. They run on the main loop, so async handlers are supported.

```python
def on_click(chart, time, price):
    print('clicked', time, price)

chart.events.click += on_click
```

| event | handler signature |
|---|---|
| `new_bar` | `(chart)` — a bar with a new timestamp arrived |
| `click` | `(chart, time, price)` |
| `dblclick` | `(chart, time, price)` |
| `crosshair_move` | `(chart, time, price)` |
| `range_change` | `(chart, bars_before, bars_after)` |
| `search` | `(chart)` — the in-chart search box emitted a query |

## Unsubscribing

```python
chart.events.crosshair_move.unsubscribe()
```

This removes both the JS subscription and the Python callback.

### Several subscribers at once

`click` and `crosshair_move` are **additive**: subscribing does not evict an
existing subscriber, and `unsubscribe()` only removes your own callback.

```python
chart.events.click += on_click
chart.events.crosshair_move += on_move
chart.events.crosshair_move += log_price     # both run, in subscription order
```

Re-subscribing (``+=`` again) replaces your previous callback instead of adding a
second copy, so it is safe to do in a loop. This matters because the drawing
toolbox and the legend listen on the same events: a plain
`chart.subscribeClick()` holds a *single* handler, so a host that re-subscribed
after adding an indicator used to silently disable drawing.

## Arrow keys (built in)

Every chart handles the arrow keys by default - the behaviour domestic trading
software has - so nothing has to be registered:

| key | action |
|---|---|
| `ArrowLeft` / `ArrowRight` | move the **visible window** by one step (default 10% of its width), so `100..200` becomes ~`90..190` for `ArrowLeft` |
| `ArrowUp` / `ArrowDown` | zoom in / out by one step, around the **middle** of the window (both edges move inwards / outwards, like the mouse wheel). Zooming *out* (`ArrowDown`) never stretches to the right once the newest bar is on screen: the extra width goes to the older side, so the live edge stays where it was |
| `Shift` + arrows | a near-full page (90%) / 2.5x step |
| `Ctrl` + `ArrowLeft` / `ArrowRight`, `PageUp` / `PageDown` | a **full page** (100% of the window) |
| `Home` | first bar at the left edge | 
| `End` | scroll to the latest bar (`scrollToRealTime`) |
| `Ctrl` + `0` | fit the whole series (`chart.fit()`) |

Zooming out with the newest bar in view keeps the right edge pinned (the extra
width all goes to the older bars), which is what you want at the live edge; with
the newest bar off screen the zoom stays centred on the window as before.

Holding a key repeats, because the browser keeps firing `keydown`. The step
(default `0.1`) is configurable per chart:

```python
chart = Chart(keyboard_step=0.2)     # 20% per press
chart.keyboard(step=0.05)            # ... or later
chart.keyboard(enabled=False)        # same as keyboard=False
```


This is a pylightcharts extension (`jslib/src/general/handler.ts`,
`_handleArrowKey`) wired through the same `commandFunctions` list as
`chart.hotkey(...)`, with three deliberate rules:

- **your own hotkeys win**: `hotkey()` handlers are unshifted to the front of the
  list and the built-in handler only runs when none of them consumed the key -
  so `chart.hotkey(None, 'ArrowUp', my_zoom)` replaces the built-in zoom;
- **typing is never hijacked**: the arrows are ignored while a topbar textbox or
  the in-chart search box has focus;
- **only the focused chart moves**: `window.handlerInFocus` decides which chart
  reacts. The **first chart of the page keeps it** until the pointer moves over
  another one, so a subchart created later (or a layout chart) cannot silently
  take the keyboard away from the main chart - hovering always switches.

`Chart(..., keyboard=False)` turns it off (`create_subchart(..., keyboard=False)`
for a single subchart); the default is `True`.

## Live example

```python
import asyncio
from pylightcharts import Chart

chart = Chart()
chart.set(df)

def on_bar(chart):
    print('new bar at', chart.last_value_data())

chart.events.new_bar += on_bar

async def on_click(chart, time, price):
    await asyncio.sleep(0)
    print('clicked', price)

chart.events.click += on_click
chart.show(block=True)
```
