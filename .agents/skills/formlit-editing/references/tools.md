# formlit tools

Generated from the engine's catalogue by `./formlit agents sync`; edit backend/app/routers/mcp.py, not this file.

## Contents

- Look: `get_catalog`, `find_photos`, `get_photo`, `get_preview`, `list_people`, `get_develop_controls`, `get_develop`, `list_presets`, `list_export_presets`
- Import and organize: `import_photos`, `set_rating`, `set_flag`, `set_label`, `add_keywords`, `set_metadata`, `set_location`, `create_collection`, `add_to_collection`, `stack_photos`
- Cull and people: `analyze_culling`, `apply_culling`, `find_faces`, `name_person`
- Develop: `develop_set`, `develop_patch`, `auto_tone`, `auto_white_balance`, `reset_develop`, `apply_preset`, `sync_settings`, `add_ai_mask`, `add_gradient_mask`, `auto_straighten`, `upright`
- Enhance and merge: `denoise`, `super_resolution`, `merge_hdr`, `merge_panorama`
- Output: `export_photos`, `print_pdf`, `make_book`, `export_slideshow`, `export_web_gallery`, `publish`
- Window, history and everything else: `show_in_window`, `undo`, `redo`, `list_commands`, `run_command`

## get_catalog

The catalog: name and counts, folders (id, path, count), collections (id, name, kind, count) and keywords. Use the ids as find_photos sources.

- no parameters

Note: read-only.

## find_photos

Lists photos: source picks where (kind all, folder, collection, keyword, person, previousImport, quick, ids), filter narrows (text, rating with ratingOp >= <= =, flags [pick reject none], labels, kinds [raw jpeg video...], edited, cameras, lenses, keywords [ids], dates [YYYY or YYYY-MM-DD]), sort orders (by captureTime, importTime, editTime, fileName, rating; desc). Returns ids with file, capture time, rating, flag, label and size.

- `source`: object
- `filter`: object
- `sort`: object
- `limit`: integer; default 200

Note: read-only.

## get_photo

One photo in full: path, camera, lens, exposure, GPS, metadata, keywords, collections and develop settings.

- `id`: integer; required; A photo id from find_photos.

Note: read-only.

## get_preview

The photo as developed, as a JPEG image (long side max_size). values renders proposed develop values without saving them; before true shows it with no edits.

- `id`: integer; required; A photo id from find_photos.
- `max_size`: integer; default 1024
- `values`: object; Develop ids to values, e.g. {"light.exposure": 0.5}.
- `before`: boolean; default false

Note: read-only.

## import_photos

Adds photos from folders or files (absolute paths) to the catalog; mode add keeps them in place, copy or move put them under destination.

- `paths`: array; required
- `mode`: string (add | copy | move); default "add"
- `destination`: string
- `keywords`: array

## set_rating

Sets star ratings, 0 to 5.

- `ids`: array; required; Photo ids from find_photos.
- `rating`: integer; required

## set_flag

Flags photos as pick, reject or none.

- `ids`: array; required; Photo ids from find_photos.
- `flag`: string (pick | reject | none); required

## set_label

Sets colour labels.

- `ids`: array; required; Photo ids from find_photos.
- `label`: string (red | yellow | green | blue | purple | none); required

## add_keywords

Adds keywords; a | separates levels (Places|France|Paris).

- `ids`: array; required; Photo ids from find_photos.
- `keywords`: array; required

## set_metadata

Sets IPTC fields: title, caption, headline, creator, copyright, location, city, state, country and the rest of the Metadata panel.

- `ids`: array; required; Photo ids from find_photos.
- `fields`: object; required

## set_location

Sets GPS coordinates (decimal degrees), or clears them when lat and lon are left out.

- `ids`: array; required; Photo ids from find_photos.
- `lat`: number
- `lon`: number

## create_collection

Makes a collection holding the photos; returns its id.

- `name`: string; required
- `ids`: array; Photo ids from find_photos.

## add_to_collection

Adds photos to a collection by id.

- `collection`: integer; required
- `ids`: array; required; Photo ids from find_photos.

## stack_photos

Stacks photos together, the first on top.

- `ids`: array; required; Photo ids from find_photos.

## analyze_culling

Scores sharpness and exposure, finds faces when the faces model is installed, and groups near-duplicates. Writes the scores; changes no flags.

- `ids`: array; required; Photo ids from find_photos.
- `wait`: boolean; default true; Wait for the job to finish (default) or return its task id.

## apply_culling

After analyze_culling: pickBest flags the best of each group as a pick; rejectBlurry and rejectDuplicates flag the rest as rejects.

- `ids`: array; required; Photo ids from find_photos.
- `pickBest`: boolean; default true
- `rejectBlurry`: boolean; default false
- `rejectDuplicates`: boolean; default false
- `threshold`: number; default 35; Sharpness score under which rejectBlurry rejects.

## find_faces

Finds faces in the photos (all when ids is left out) and groups them by person.

- `ids`: array; Photo ids from find_photos.
- `wait`: boolean; default true; Wait for the job to finish (default) or return its task id.

## list_people

Named people with counts, and unnamed face groups with their face and photo ids.

- no parameters

Note: read-only.

## name_person

Names a group of faces (face ids from list_people); adds a People keyword to their photos.

- `faces`: array; required
- `name`: string; required

## get_develop_controls

Every develop setting id with its label, range and default, the local (mask) adjustment ids, white balance presets and crop aspects.

- no parameters

Note: read-only.

## get_develop

A photo's develop settings and their effective values.

- `id`: integer; required; A photo id from find_photos.

Note: read-only.

## develop_set

Sets develop values on photos: values maps ids from get_develop_controls to numbers; delta true adds to the current values.

- `ids`: array; required; Photo ids from find_photos.
- `values`: object; required
- `delta`: boolean; default false

## develop_patch

Merges a nested develop object into the photos' settings: treatment ("color" or "bw"), crop (rect [x0,y0,x1,y1] 0 to 1, angle), geometry, masks, curve points. Plain numbers such as grading.shadows.hue go through develop_set.

- `ids`: array; required; Photo ids from find_photos.
- `patch`: object; required
- `label`: string

## auto_tone

Auto exposure, contrast, highlights, shadows, whites and blacks, like the Auto button.

- `ids`: array; required; Photo ids from find_photos.

## auto_white_balance

Auto white balance.

- `ids`: array; required; Photo ids from find_photos.

## reset_develop

Resets develop settings to defaults (undoable).

- `ids`: array; required; Photo ids from find_photos.

Note: replaces or removes.

## list_presets

Develop presets by group, with ids for apply_preset.

- no parameters

Note: read-only.

## apply_preset

Applies a develop preset at an amount (0 to 200 percent).

- `ids`: array; required; Photo ids from find_photos.
- `preset`: string; required
- `amount`: number; default 100

## sync_settings

Copies develop settings from one photo to others, limited to groups when given (whiteBalance, basicTone, presence, toneCurve, colorMixer, pointColor, bwMix, treatment, colorGrading, detail, lensCorrections, transform, effects, calibration, profile, crop, masks, spots, redEye, lensBlur); with no groups, everything but crop, masks, spots and red eye.

- `from`: integer; required; A photo id from find_photos.
- `ids`: array; required; Photo ids from find_photos.
- `groups`: array

## add_ai_mask

Adds a local adjustment through an AI mask (sky, subject, background, people, object with box [x0,y0,x1,y1] 0 to 1, or depth). adjust uses local ids: exposure, contrast, highlights, shadows, whites, blacks, temp, tint, saturation, texture, clarity, dehaze, sharpness, noise.

- `id`: integer; required; A photo id from find_photos.
- `kind`: string (sky | subject | background | people | object | depth); required
- `box`: array
- `adjust`: object
- `name`: string

## add_gradient_mask

Adds a linear gradient (start and end points, 0 to 1 of the frame) or a radial gradient (center, rx, ry, feather, invert) with local adjust values.

- `id`: integer; required; A photo id from find_photos.
- `kind`: string (linear | radial); required
- `start`: array
- `end`: array
- `center`: array
- `rx`: number
- `ry`: number
- `feather`: number
- `invert`: boolean
- `adjust`: object

## auto_straighten

Levels the horizon from the lines in the photo.

- `ids`: array; required; Photo ids from find_photos.

## upright

Perspective correction: auto, level, vertical or full.

- `ids`: array; required; Photo ids from find_photos.
- `mode`: string (auto | level | vertical | full | off); required

## denoise

AI Denoise: writes an enhanced DNG next to each raw and stacks it.

- `ids`: array; required; Photo ids from find_photos.
- `amount`: number; default 50
- `wait`: boolean; default true; Wait for the job to finish (default) or return its task id.

## super_resolution

Doubles the resolution into an enhanced DNG, stacked with the original.

- `ids`: array; required; Photo ids from find_photos.
- `wait`: boolean; default true; Wait for the job to finish (default) or return its task id.

## merge_hdr

Merges bracketed exposures into an HDR DNG, stacked with the brackets.

- `ids`: array; required; Photo ids from find_photos.
- `deghost`: string (off | low | medium | high); default "off"
- `wait`: boolean; default true; Wait for the job to finish (default) or return its task id.

## merge_panorama

Stitches overlapping photos into a panorama DNG.

- `ids`: array; required; Photo ids from find_photos.
- `projection`: string (spherical | cylindrical | plane); default "spherical"
- `wait`: boolean; default true; Wait for the job to finish (default) or return its task id.

## list_export_presets

Export presets (id and name) and the last export's settings.

- no parameters

Note: read-only.

## export_photos

Exports photos to files: a preset id (builtin.web, builtin.full, builtin.tiff, builtin.print, builtin.original, builtin.dng or a user preset) and/or settings (destination.folder absolute path, file.format jpeg png tiff webp avif heic dng original, file.quality, size.resize with size.mode long and size.value, sharpen, metadata.include, watermark). Returns the written paths.

- `ids`: array; required; Photo ids from find_photos.
- `preset`: string
- `settings`: object
- `folder`: string; Absolute output folder; shorthand for settings.destination.folder.

## print_pdf

Lays photos out for print (settings as the Print module: paper, orientation, rows, cols, margins, style grid or package, fill, caption) and writes a PDF; path optional.

- `ids`: array; required; Photo ids from find_photos.
- `settings`: object
- `path`: string

## make_book

Auto-lays out the photos as a book (size, title) and writes a PDF.

- `ids`: array; required; Photo ids from find_photos.
- `title`: string
- `size`: string; default "standard-landscape"
- `path`: string

## export_slideshow

Writes a slideshow of the photos as MP4 (needs ffmpeg) or PDF; settings as the Slideshow module (duration, fade, panZoom, fill, music.path).

- `ids`: array; required; Photo ids from find_photos.
- `format`: string (mp4 | pdf); default "mp4"
- `settings`: object
- `path`: string

## export_web_gallery

Writes a web gallery folder (index.html plus images); settings as the Web module (site.title, layout, colors).

- `ids`: array; required; Photo ids from find_photos.
- `settings`: object
- `folder`: string

## publish

Publishes a published collection: new and edited photos go out, removed ones are deleted from the service.

- `collection`: integer; required

## show_in_window

Shows something in the formlit window if it is open: a module (library, develop, map, book, slideshow, print, web), a photo id, a source like find_photos takes, and a short message for the person.

- `module`: string
- `photo`: integer
- `source`: object
- `message`: string

## undo

Undoes the last change.

- no parameters

## redo

Redoes the last undone change.

- no parameters

## list_commands

Every engine command (id, group, parameters) for run_command, optionally one group.

- `group`: string

Note: read-only.

## run_command

Runs any engine command by id with its params (see list_commands). Deleting files and switching catalogs stay in the window.

- `command`: string; required
- `params`: object
