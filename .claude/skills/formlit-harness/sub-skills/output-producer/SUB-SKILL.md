---
name: output-producer
description: "Owns everything formlit writes out over MCP: exports with presets and settings, print layouts and contact sheets to PDF, JPEG or a printer, photo books, slideshow video or PDF, web galleries with FTP upload, publish services, and Edit In. Load for any request to export, deliver, print, make a book, slideshow or gallery, or publish photos."
---

# Output Producer

## Purpose

Write the files the person needs, to the place they need them, at the right size, colour space and metadata, and prove it by naming the written paths. Hands back the paths and a sentence on each output's specification.

## Preconditions

The photo ids, developed and checked by develop-artist when looks matter.

## Procedure

1. Pin the destination. Ask for a folder only when the person named none and the work is for delivery; otherwise the engine's Exports folder is fine and the reply says where it is.
2. Pick the starting preset from `references/export-settings.md` and override only what the request says: web is `builtin.web`, email is `builtin.email` (1200 px), print labs take `builtin.print` (16-bit TIFF, Adobe RGB, 300 ppi, matte sharpening), archives take `builtin.tiff` or `builtin.dng`.
3. `export_photos` with `ids`, `preset`, `folder` and any `settings` overrides. Metadata defaults to all; client deliveries usually want `metadata.include: "copyright"` and `removeLocation: true`.
4. Pages and motion, with the settings in `references/layouts.md`:
   - contact sheets and prints: `print_pdf`
   - books: `make_book` (auto layout); for page-by-page control use `run_command` with `book.layout` and `book.export`
   - slideshows: `export_slideshow` as `mp4` (needs ffmpeg) or `pdf`
   - galleries: `export_web_gallery`; uploading uses `run_command` with `web.export` and `upload: true` once FTP settings exist
5. Publish services keep a destination in step: `run_command` with `publish.services` to find the collection, then `publish`. New and changed photos go out, photos removed from the collection are deleted at the destination; say so before publishing. Service kinds are `folder`, `ftp`, the built-in plug-ins `webdav` (Nextcloud, ownCloud, any WebDAV folder) and `s3` (S3, R2, B2, Wasabi, MinIO), and any plug-in listed by `publish.plugins`. Comments on published photos are read with `publish.comments` and posted with `publish.addComment` when the service takes them. Exports drop GPS for photos inside a private saved location.
6. Edit In: `run_command` with `photo.editIn` writes a 16-bit TIFF copy stacked with the original and opens the person's chosen editor.
7. Confirm: the result lists the written paths. Open one image with `get_preview` only for catalog photos; for files, report the path, size and format.

## Gate

Done when every requested output has a written path in the tool result, and nothing was overwritten that the person did not agree to overwrite (the default naming is unique).

## Hands back

The written paths, the preset or settings used, and for publish the counts published and removed.

## Owned resources

- `references/export-settings.md` the export settings object, formats, sizing modes and presets
- `references/layouts.md` print, book, slideshow and web settings
