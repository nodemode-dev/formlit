# formlit demo 3: share

The output modules of formlit running in a browser tab: Map, Book, Slideshow, Print and Web, on a library of nineteen photographs. No engine, no network, no CDN, no account. Open `index.html` straight from disk (`file://`) or serve this folder with any static server. Photos you open never leave the page.

The three demos: [demo 1](../../demo/index.html) (library, develop basics, export), [develop](../develop/index.html) (masks, presets, virtual copies), and this one. The status bar of each links to the others.

## What it shows

- Map. Thirteen of the nineteen photos carry a location and show as pins, grouped into clusters you can click. Drag the photos without one from the filmstrip onto the map, edit the latitude and longitude, Use Map Centre, Remove Location, add Saved Locations (one is private, and photos inside a private location lose their location on export), search the map, filter Visible, Tagged or Untagged, and switch between six map styles. Load GPX tags the selected photos from a track log.
- Book. A twelve-photo book with a cover, auto layout, the page template strip, custom pages, captions and page numbers. Export Book writes a PDF of the pages.
- Slideshow. Ten photographs with an intro and an ending screen, pan and zoom, captions and a piano recording. Play runs it in the window with sound; Export PDF writes the slides.
- Print. A four-up contact sheet on letter paper with an identity plate, captions and page numbers, laid out with the same grid, package and custom styles. Print writes a PDF.
- Web. A justified gallery with a title, description, colour palette, a watermark and a lightbox. Export writes a ZIP with `index.html`, large images and thumbnails; the images carry the watermark and a copyright field.
- Export (Shift+Ctrl+E, or File, Export) writes JPEG, PNG or WebP of the selected photos with size, sharpening, watermark and metadata options.
- Templates and saved creations work as in the app: Template Browser, Saved Books, Saved Slideshows, Saved Prints and Saved Webs, with the plus button and the context menus.

Open your own photographs with File, Open Photos or by dropping files on the window: JPEG, PNG and WebP files join the filmstrip, and a JPEG with a location in its EXIF appears on the map.

## Run it

```
open demos/share/index.html
```

or

```
cd demos/share && python3 -m http.server 5399
```

## How it is built

`src/` imports the app's own interface code from `frontend/src` (Shell, filmstrip, thumbnails, panels, Form, the Map, Book, Slideshow, Print and Web module classes and their styles) and demo 1's styles. Nothing under `demo/`, `demos/develop/` or `frontend/` is changed. The backend is replaced at build time: a Vite plugin in `vite.config.mjs` resolves the app's `io/api`, `io/events`, `modules/shared/tasks`, `modules/shared/captions` and `ui/folder-picker` imports to small modules in `src/shims/`, and the command table in `src/engine.ts` answers the same command ids as the desktop engine (`library.query`, `photo.setGps`, `location.*`, `gps.*`, `print.*`, `book.*`, `slideshow.*`, `web.*`, `export.*`).

The layout logic is a TypeScript port of the engine's Python: `layout.ts` (print pages, book pages, auto layout, shelf packing), `pages.ts`, `slides.ts`, `site.ts` and `exporter.ts`. Outputs are real files made in the page: JPEG, PNG and WebP from canvas with EXIF written by `exif.ts`, PDFs by `pdf.ts`, ZIPs by `writers.ts`. Each is kept as a blob and offered through the Save button on the toast.

The map is the app's own map module. A second Vite plugin replaces only its tile table (three remote tile servers) with `OFFLINE_STYLES` from `src/map-styles.ts`, which cuts tiles in the page from a downsized NASA Blue Marble image and draws the graticule and place labels from the small list in `src/gazetteer.ts`. The map zooms to level 6; Search Map and Look Up Address use the same list.

The photographs, music and basemap are JavaScript data packs in `assets/media/` loaded by injecting a script tag, because Chrome blocks `fetch` of local files from `file://`. The build is a classic script (IIFE) with no `crossorigin` attributes.

Rebuild after changing anything under `src/` (run from this folder; node_modules is the app's own, in `frontend/`):

```
../../frontend/node_modules/.bin/tsc -p tsconfig.json
node ../../frontend/node_modules/vite/bin/vite.js build --config ./vite.config.mjs
```

The build writes `index.html` and `assets/` into this folder. The type check also lists a few unused-variable notices from `frontend/src` files this demo imports; they are the app's, not this demo's.

## Limits

The map has no street data: it shows land, sea and a graticule, with names from a short built-in list. Look Up Address fills places from that list only. Slideshow video export, Book export to a print service and Upload need the desktop app. PDF text uses the standard Helvetica font, so characters outside Latin-1 are replaced. Exported files are saved through the browser's download, not to a folder.
