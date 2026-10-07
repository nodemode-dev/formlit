# Print, book, slideshow and web settings

Every module computes its pages in the engine, so the window's preview and the written file come from one layout. `run_command` with `print.options`, `book.options`, `slideshow.options` or `web.options` returns the defaults and templates.

## Print (`print_pdf` settings, `print.run`)

| key | values |
| --- | --- |
| `style` | `grid` (single image and contact sheets), `package` (fixed sizes, one photo per page), `custom` (cells you place) |
| `paper`, `orientation` | `letter`, `legal`, `tabloid`, `a5`, `a4`, `a3`, `a3plus`, `a2`, `4x6`, `5x7`, `8x10`, `11x14`, `13x19`, `16x20`, `17x22`; `portrait` or `landscape` |
| `margins` | `[left, right, top, bottom]` in inches |
| `rows`, `cols`, `gapX`, `gapY` | grid shape, gaps in inches |
| `fill`, `rotate`, `repeat` | zoom to fill the cell, rotate to fit, one photo repeated per page |
| `package` | `[{"size": "5x7"}, {"size": "wallet"}]`; sizes `wallet`, `2x3`, `3x5`, `4x6`, `5x7`, `8x10` |
| `cells` | custom cells `[{"x", "y", "w", "h"}]` in inches |
| `stroke`, `strokeColor`, `background` | border in points, colours as #rrggbb |
| `identity` | `{"on", "text", "size", "x", "y", "color"}` with x and y as fractions of the page |
| `pageNumbers`, `pageInfo`, `cropMarks` | booleans |
| `caption` | `{"on", "field": "title | caption | titleCaption | fileName | date | exposure | custom", "custom", "size"}` |
| `job` | `{"output": "pdf | jpeg | printer", "ppi": 300, "sharpen": {...}, "space", "printer", "copies", "quality"}` |

Templates: Fine Art Mat, Maximize Size, 1 Large with Stroke, 2 x 2 Cells, 4 x 5 Contact Sheet, 5 x 8 Contact Sheet, Triptych, three picture packages, Custom Centered.

## Book (`make_book`, `book.layout`, `book.export`)

`size`: `small-square` 7x7, `standard-landscape` 10x8, `standard-portrait` 8x10, `large-landscape` 13x11, `large-square` 12x12, `letter`, `a4`, `a4-landscape`. `cover` and each of `pages` is `{"template", "photos": [ids], "texts": [strings]}`. Page templates: `full`, `single`, `single-caption`, `single-small`, `two-h`, `two-v`, `three`, `three-col`, `four`, `text`, `blank`, and `cover` for the cover. Also `background`, `textColor`, `titleSize`, `textSize`, `pageNumbers`, `captions`, `captionField`, and `job` as in print. `book.autoLayout` with `mode` `mixed` or `one` fills pages and adds a blank to keep spreads even.

## Slideshow (`export_slideshow`, `slideshow.layout`)

`fill`, `margin` (fraction of the width), `stroke`, `strokeColor`, `shadow`, `background`, `duration` and `fade` in seconds, `panZoom` 0 to 1, `random`, `repeat`, `caption` and `identity` as in print, `intro` and `ending` `{"on", "text"}`, `music` `{"path", "fit"}` (fit stretches slides to the track), `video` `{"size": "480p | 720p | 1080p | 4k", "fps", "quality"}`.

## Web (`export_web_gallery`, `web.export`, `web.preview`)

`layout` `grid | square | justified | column`, `site` `{"title", "collection", "description", "contact", "link"}`, `colors` `{"background", "text", "muted", "cell", "accent"}`, `thumbSize`, `largeSize`, `quality`, `rowHeight`, `gap`, `captions` `{"field", "lightbox", "exposure"}`, `watermark` `{"on", "text", "opacity"}`, `metadata`, `sharpen`, `upload` `{"host", "port", "user", "password", "path", "tls"}`. The folder holds `index.html`, `gallery.json` and `images/thumb`, `images/large`.
