# Drawing tools

```python
chart.trend_line(t1, p1, t2, p2, color='#1E80F0')
chart.horizontal_line(price, color='#7A92CA', text='support')
chart.vertical_line(time)
chart.ray_line(start_time, value)
chart.box(t1, p1, t2, p2, fill_color='rgba(255,255,255,0.2)')

chart.fibonacci(t1, p1, t2, p2, levels=(0, 0.382, 0.5, 0.618, 1))
chart.measure(t1, p1, t2, p2)                        # price %, bar count
chart.parallel_channel(t1, p1, t2, p2, offset=5)     # parallel shifted 5 price units

chart.position(t1, entry, t2, target, risk_ratio=1.5)   # profit + stop zones
chart.long_position(t1, entry, t2, target)
chart.short_position(t1, entry, t2, target)

chart.andrews_pitchfork(t1, p1, t2, p2, t3, p3)      # 3 points
chart.triangle(t1, p1, t2, p2, t3, p3)               # 3 points
chart.fibonacci_extension(t1, p1, t2, p2, t3, p3)    # impulse + retracement
chart.gann_fan(t1, p1, t2, p2)                       # 1x1 plus steeper/shallower rays
```

Each returns a drawing object with `update(...)`, `options(...)` and `delete()`:

```python
fib = chart.fibonacci(t1, p1, t2, p2)
fib.update(t1, new_p1, t2, new_p2)
fib.delete()
```

### Labels on a horizontal line

`horizontal_line` shows its `text` on the price axis by default. Pass
`label_visible=True` to also draw it **inside the pane** (pinned to the left
edge of the visible range), and `axis_label_visible=False` to drop the axis
badge entirely - the price scale then no longer reserves room for the label:

```python
chart.horizontal_line(8000, text='压力', color='#ef5350',
                      label_visible=True,
                      label_background_color='#ef5350',
                      label_text_color='#fff', label_font='13px sans-serif')
```

The same keywords are accepted by `line.options(...)` to restyle it later.

## Interactive drawing

Pass `toolbox=True` when creating the chart to get a toolbar; every tool also
has an `Alt+<key>` shortcut.

```python
chart = Chart(toolbox=True)
```

| Tool | Key | Points |
|---|---|---|
| Trend line | `Alt+T` | 2 |
| Horizontal line | `Alt+H` | 1 |
| Ray | `Alt+R` | 2 |
| Box | `Alt+B` | 2 |
| Vertical line | `Alt+V` | 2 |
| Fibonacci | `Alt+F` | 2 |
| Measure | `Alt+M` | 2 |
| Channel | `Alt+C` | 2 |
| Position | `Alt+P` | 2 |
| Pitchfork | `Alt+A` | 3 |
| Triangle | `Alt+G` | 3 |
| Fibonacci extension | `Alt+X` | 3 |
| Gann fan | `Alt+N` | 2 |

Drawings can be persisted:

```python
toolbox = chart.toolbox
toolbox.save_drawings_under('layout')
toolbox.export_drawings('drawings.json')
toolbox.load_drawings('drawings.json')
```
