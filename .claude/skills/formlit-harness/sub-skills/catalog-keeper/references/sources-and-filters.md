# Sources, filters and metadata fields

## Sources (`find_photos` source)

| kind | extra | photos |
| --- | --- | --- |
| `all` | | every photo, stacks expanded |
| `folder` | `id`, `recursive` | a folder from `get_catalog`, with its subfolders when recursive |
| `collection` | `id` | a collection, intelligent collection or saved creation |
| `keyword` | `id` | photos with the keyword or any keyword below it |
| `person` | `id` | photos with a confirmed face of a named person (ids from `list_people`) |
| `previousImport` | | the last import |
| `quick` | | the Quick Collection |
| `recent` | | photos edited in the last days |
| `missing` | | photos whose files are gone |
| `ids` | `ids` | exactly these photos |

## Filters (`find_photos` filter)

| key | value | example |
| --- | --- | --- |
| `text` | words matched against file name, title, caption, keywords, camera and lens | `"harbour"` |
| `rating` with `ratingOp` | 0 to 5, with `>=`, `<=` or `=` | `{"rating": 4, "ratingOp": ">="}` |
| `flags` | any of `pick`, `reject`, `none` | `["pick"]` |
| `labels` | any of `red`, `yellow`, `green`, `blue`, `purple`, `none` | `["green"]` |
| `kinds` | `raw`, `jpeg`, `tiff`, `png`, `heic`, `video`, `other` | `["raw"]` |
| `edited` | true or false | `true` |
| `cameras`, `lenses` | exact names as `get_photo` shows them | `["Canon EOS R5"]` |
| `keywords` | keyword ids | `[12, 14]` |
| `dates` | `YYYY`, `YYYY-MM` or `YYYY-MM-DD` | `["2026-09"]` |

Sort: `{"by": "captureTime" | "importTime" | "editTime" | "fileName" | "rating" | "flag" | "label" | "camera", "desc": false}`.

## IPTC fields (`set_metadata` fields)

title, caption, headline, altText, extendedDescription, creator, creatorJob, creatorAddress, creatorCity, creatorState, creatorCountry, creatorEmail, creatorPhone, creatorUrl, copyright, copyrightStatus, rightsUsage, copyrightUrl, location, city, state, country, isoCountryCode, sublocation, jobId, instructions, provider, source, intellectualGenre, scene, subjectCode, event, personShown.

`run_command` with `photo.saveMetadata` writes the catalog's metadata to XMP sidecars; `photo.readMetadata` reads changes made by other applications.
