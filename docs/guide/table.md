# Floating tables

`create_table(...)` puts a small HTML table **on top of the chart** (a legend
box, a quote card, an indicator read-out). It is a plain DOM element next to
the chart canvas, so it never touches the Lightweight Charts engine - you can
build it before or after the data, move it around, and re-fill it at any time.

```python
table = chart.create_table(
    320, 180,                          # width / height: 0..1 = fraction, int = px
    headings=('symbol', 'price', 'change'),
    widths=(140, 90, 90),              # optional: same units as the size
    alignments=('left', 'right', 'right'),
    position='top-right', draggable=True,
)
table.new_row('BTCUSDT', 64231.5, 1.23)
table.new_row('ETHUSDT', 3120.4, -0.85)
```

`create_table` lives on `Window`, so it is also available as
`chart.win.create_table(...)` and works on a chart-less
[`QtPanel`](panels.md#hosting-a-full-page-qtpanel).

## Rows

| call | effect |
| --- | --- |
| `table.new_row(*values, id=None) -> Row` | append a row, values in `headings` order; returns the row |
| `table[id]` / `table.get(id)` | fetch a row back by its id |
| `row['price'] = 65120.0` | update one cell (column formatters apply) |
| `row[('symbol', 'change')] = ('BTCUSDT', 2.05)` | update several cells at once |
| `row.background_color(column, color)` / `row.text_color(column, color)` | tint one cell |
| `row.delete()` | remove the row |
| `table.clear()` | remove every row (keeps the table and its headings) |

`new_row` returns a `Row`, which is a `dict` keyed by heading - so you can keep
the handle and update the same row in place instead of rebuilding the table:

```python
row = table.new_row('BTCUSDT', 64231.5, 1.23)
row['price'] = 65120.0
```

!!! note "Headings must be unique"
    A `Row` is keyed by heading, so two columns with the same (or an empty)
    name overwrite each other. Keep the names distinct.

### Formatting

`Table.format(column, format_str)` registers a per-column format; the literal
`Table.VALUE` marker is replaced by the cell's value when it is written:

```python
table.format('change', Table.VALUE + '%')
table.format('price', '$' + Table.VALUE)
row['change'] = 1.23          # renders "1.23%"
```

## Header and footer

`table.header` / `table.footer` are `Section`s - one or more text boxes above
and below the rows. Pass the number of boxes, then assign by index:

```python
table.header(1)
table.header[0] = 'MARKET WATCH'
table.footer(1)
table.footer[0] = 'streaming…'
```

Pass a callback to a section (`table.header(1, func)`) to make its boxes
clickable; the callback receives `(table, box_index)`.

## Position, margins and dragging

`position` (and `Table.set_position`) anchors the table to a corner of the
window: `'top-left'` / `'top-right'` / `'bottom-left'` / `'bottom-right'`,
plus `'center'`. The legacy spellings `'left'` / `'right'` / `'top'` /
`'bottom'` are accepted for compatibility.

`margin_x` / `margin_y` inset the table from the **nearest two edges** (pixels)
- handy to clear the top bar or the price scale:

```python
chart.create_table(300, 160, headings=('Field', 'Value'),
                   position='top-left', margin_x=12, margin_y=12)

table.set_position('bottom-right', margin_x=8, margin_y=8)   # later, too
```

With `draggable=True` the user can drag the table anywhere; the anchor still
pins it on resize until it is dragged. `table.resize(w, h)` and
`table.visible(False)` change the size / visibility at runtime.

## Clicked cells

Set `return_clicked_cells=True` and pass a `func`; it is called with the
clicked `Row`, and - when the callback accepts a second argument - the column
name too:

```python
def on_cell(row, column=None):
    print(dict(row), column)

table = chart.create_table(..., return_clicked_cells=True, func=on_cell)
```

The wrapper inspects the callback's signature, so `def on_cell(row)` and
`def on_cell(row, column)` both work.

## Following the crosshair (indicator value table)

A common recipe is a table that shows the indicator values **at the bar under
the cursor** and falls back to the last bar when the pointer leaves the chart:

```python
def on_crosshair(chart, time_value, price):
    index = index_by_time.get(time_value)      # None when off the bars
    render(len(values) - 1 if index is None else index)

chart.events.crosshair_move += on_crosshair
```

Combine it with `series.subscribe_data_changed(...)` (or `chart.update(...)`)
to refresh the same table when new bars arrive. The full runnable version -
including the background-thread feed that keeps the crosshair events flowing -
is [`examples/11_api_tour/25_live_value_table.py`](examples.md).

## Theming

`table.set_colors(background_color=, border_color=, text_color=,
section_color=)` re-styles a table after it was built (the constructor bakes the
colours into the DOM). Tables created through a themed `Window` follow
[`window.theme('light' | 'dark')`](options.md#themes-whole-ui-light-dark)
automatically; pass explicit colours to opt out.

## See also

- [`HtmlPanel`](../api.md) (`chart.create_html_panel()`) - a full-page,
  scrollable HTML report on top of the chart, for statistics / trade tables.
- [`DataGrid`](panels.md#datagrid) - a virtualised, sortable, filterable table
  for thousands of rows (the financial-panels layer).
