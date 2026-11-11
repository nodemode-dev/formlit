# HASHOUT_LOG · demos/share · formlit

Rationale and decisions for demo 3 (share). Source files stay comment-free.

Current build version: v0.50.0 (the version of the app this demo was built against).

## What this demo adds to demos 1 and 2

Demo 1 is the library, develop basics and export; demo 2 is masks, presets and virtual copies. The focus table names "map, book, slideshow, print, web gallery, export". This demo is those output modules, driven by the app's own module classes (`modules/output/{map,book,slideshow,print,web}.ts` and `modules/shared/export.ts`) so the windows are the app's, not a copy.

## Why a command table instead of per-module fakes

Every output module talks to the engine through `api.cmd(id, params)` and reads files through `api.url`. The Vite plugin in `vite.config.mjs` resolves `io/api`, `io/events`, `modules/shared/tasks`, `modules/shared/captions` and `ui/folder-picker` to `src/shims/`, and `src/engine.ts` answers the same command ids as `backend/app/engine/cmd_output.py` and `cmd_library.py`. The module code therefore runs unmodified, including its error paths. A command the demo does not carry throws `EngineMiss`, which the app's own error toast shows as "part of the desktop app".

`src/main.ts` sits outside `frontend/src`, so the plugin does not rewrite its imports; it imports the shims directly. Both import the same module instance, so events and the api object are shared.

## Ports of the Python layout code

`layout.ts` ports `layout.py` (print pages, book pages, auto book, `place`, `pan_zoom`, shelf packing), `pages.ts` ports `pages._overlays` and `caption`, `slides.ts` the slideshow page layout, `site.ts` `web.build_html`, `exporter.ts` `export.scale_for`, the watermark and the metadata rules of `encode.filtered`. Structure follows the Python so a fix there can be carried over line by line. The page then renders the same layout the engine produces: the book, print and slide pages are drawn by `render.ts` onto a canvas and the PDF writer (`pdf.ts`) embeds the JPEGs.

## Outputs are blobs, saved by the person

A browser cannot write to a folder it was not given. `putOutput` keeps each result as a blob under the path the engine would have used; the toast's Open shows it where the browser can (PDF, HTML) and Save downloads it. A set of files that share a group (a web gallery) downloads as one stored ZIP (`writers.ts`). The toast text "Show in Folder" is relabelled Save because there is no folder.

## Metadata

`exif.ts` reads capture date, camera and GPS from JPEG files you open and writes EXIF into JPEG exports: description, camera, exposure, copyright, artist and GPS. Private saved locations drop the GPS block of photos inside their radius, as the engine does. Degrees, minutes and seconds are derived from integer ten-thousandths of a second so 42.15 degrees is 42, 9, 0 and not 42, 8, 60.

## The offline map

The Map module draws tiles from three remote hosts. A transform in `vite.config.mjs` replaces only that table (from `const OSM =` up to `const VIEW_KEY`) with `OFFLINE_STYLES`; the build fails if the markers move, so a change in `map.ts` cannot silently bring the remote tiles back. `map-styles.ts` samples a 3600 by 1800 equirectangular Blue Marble image per Web Mercator tile, with bilinear filtering, and shades it for six looks (hybrid, road, satellite, terrain, light, dark). Snow is told from desert by saturation as well as brightness, because Saharan sand is as bright as ice. The resolution of the source caps useful zoom at 6. Labels come from `gazetteer.ts`, about ninety names in four kinds (sea, country, city, spot) with the zoom at which each appears; Search Map and Look Up Address use the same list. Tiles are cached as data URLs, at most 600.

## Events

The modules refresh from engine events: `photos.changed`, `list.changed` with `collections` or `locations`, `task`. `location.save` and `location.delete` emit `list.changed` for `locations`, without which the Saved Locations panel does not update after Create.

## Zero flash

The window boots with `is-booting`: the stage keeps a placeholder panel and the left and right foot columns are hidden until the first render, so nothing moves when the photos arrive. A layout-shift observer under 4x CPU throttling reads 0 for the opening screen. The status bar sits in grid row 5 (`.fl-app > .fl-status`) because the hidden terminal dock leaves the footer in the dock row, which is 0 px tall.

## Building on Windows (v0.51.2 fix)

`front` in vite.config.mjs is written with forward slashes, because Vite's importer ids use them on Windows and the shim swap compared them with a backslashed path, so a Windows build bundled the real engine client. See demo/HASHOUT_LOG.md, "Building on Windows". Not run on Windows.

## Not done

Video export for the slideshow, FTP upload, book printer packages, TIFF, street-level address lookup: all need the desktop app or a network. The slideshow plays its music through an `Audio` element from a blob URL made from the data pack.
