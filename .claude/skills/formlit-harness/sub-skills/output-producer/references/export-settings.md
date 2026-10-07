# Export settings

`export_photos` takes `preset` and/or `settings`; settings are merged over the preset, section by section. `run_command` with `export.options` returns the live defaults.

```json
{
  "destination": {"folder": "/abs/path", "subfolder": "{date:%Y-%m-%d}", "useSubfolder": false, "sameAsOriginal": false,
                  "existing": "unique | overwrite | skip", "addToCatalog": false, "stack": false},
  "naming": {"rename": false, "template": "{name}-{seq:3}", "custom": "", "start": 1, "case": "keep | lower | upper"},
  "file": {"format": "jpeg | png | tiff | webp | avif | heic | dng | original", "quality": 85, "limitKB": 0,
           "depth": 8, "compression": "none | zip", "space": "srgb | p3 | adobergb | prophoto | rec2020"},
  "size": {"resize": false, "mode": "long | short | wh | dims | mp | percent", "value": 2048, "w": 2048, "h": 2048,
           "mp": 12, "percent": 50, "noEnlarge": true, "ppi": 240},
  "sharpen": {"on": false, "for": "screen | matte | glossy", "amount": "low | standard | high"},
  "metadata": {"include": "none | copyright | contact | noCamera | noRaw | all", "removePerson": true, "removeLocation": false},
  "watermark": {"on": false, "kind": "text | image", "text": "{copyright}", "image": "/abs/logo.png", "size": 0.035,
                "opacity": 0.7, "anchor": "tl | t | tr | l | c | r | bl | b | br", "inset": 0.025, "color": "#ffffff", "shadow": true},
  "video": {"include": true, "format": "original | h264", "quality": "max | high | medium | low"},
  "post": {"action": "none | reveal | open", "app": ""}
}
```

## Notes

- `depth` 16 applies to PNG and TIFF; the other formats are 8-bit.
- `size.mode`: `long` and `short` use `value`; `wh` fits inside w by h as oriented; `dims` fits whichever way round is larger; `mp` targets megapixels; `percent` scales.
- `original` copies the file and writes an XMP sidecar with the develop settings; `dng` writes a linear DNG of the original plus the sidecar.
- Naming tokens: `{name}` `{ext}` `{seq:3}` `{num}` `{date:%Y%m%d}` `{year}` `{month}` `{day}` `{hour}` `{minute}` `{camera}` `{lens}` `{iso}` `{focal}` `{aperture}` `{rating}` `{label}` `{title}` `{creator}` `{city}` `{country}` `{folder}` `{custom}` `{copy}`.
- Watermark text tokens: `{copyright}` `{creator}` `{title}` `{name}` `{year}` `{caption}`.
- Keywords marked "do not export" are left out; People keywords go when `removePerson` is false.

## Built-in presets

| id | what |
| --- | --- |
| `builtin.web` | JPEG 82, sRGB, long edge 2048, screen sharpening, copyright only |
| `builtin.full` | JPEG 92, sRGB, full size, all metadata |
| `builtin.email` | JPEG 75, sRGB, long edge 1200, light screen sharpening, copyright only |
| `builtin.tiff` | TIFF 16-bit ZIP, ProPhoto RGB, all metadata |
| `builtin.print` | TIFF 16-bit ZIP, Adobe RGB, 300 ppi, matte sharpening |
| `builtin.original` | the original file and an XMP sidecar |
| `builtin.dng` | a linear DNG with the edits in a sidecar |
