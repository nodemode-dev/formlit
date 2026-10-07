# MCP tools, commands and files

Each curated tool in `backend/app/routers/mcp.py` and the engine commands it calls. A command's group (the part before the dot) names the module that defines it:

| group | module |
| --- | --- |
| `ai` | `backend/app/engine/cmd_ai.py` |
| `book` | `backend/app/engine/cmd_output.py` |
| `collection` | `backend/app/engine/cmd_library.py` |
| `cull` | `backend/app/engine/cmd_ai.py` |
| `develop` | `backend/app/engine/cmd_develop.py` |
| `edit` | `backend/app/engine/cmd_library.py` |
| `export` | `backend/app/engine/cmd_output.py` |
| `folder` | `backend/app/engine/cmd_library.py` |
| `gps` | `backend/app/engine/cmd_output.py` |
| `keyword` | `backend/app/engine/cmd_library.py` |
| `library` | `backend/app/engine/cmd_library.py` |
| `location` | `backend/app/engine/cmd_output.py` |
| `people` | `backend/app/engine/cmd_ai.py` |
| `photo` | `backend/app/engine/cmd_library.py` |
| `preset` | `backend/app/engine/presets.py` |
| `print` | `backend/app/engine/cmd_output.py` |
| `publish` | `backend/app/engine/cmd_output.py` |
| `slideshow` | `backend/app/engine/cmd_output.py` |
| `snapshot` | `backend/app/engine/cmd_develop.py` |
| `stack` | `backend/app/engine/cmd_library.py` |
| `web` | `backend/app/engine/cmd_output.py` |

`photo.setGps` lives in `cmd_output.py` beside the other location commands; `develop.aiMask`, `develop.removeFill`, `develop.autoStraighten` and `develop.upright` live in `cmd_ai.py` because they need models or line detection.

| tool | commands |
| --- | --- |
| `get_catalog` | `library.tree` |
| `find_photos` | `library.query` |
| `get_photo` | `photo.get` |
| `get_preview` | `previews.render_rgb8` |
| `import_photos` | `library.import` |
| `set_rating` | `photo.rate` |
| `set_flag` | `photo.flag` |
| `set_label` | `photo.label` |
| `add_keywords` | `photo.addKeywords` |
| `set_metadata` | `photo.setMeta` |
| `set_location` | `photo.setGps` |
| `create_collection` | `collection.create` |
| `add_to_collection` | `collection.addPhotos` |
| `stack_photos` | `stack.group` |
| `analyze_culling` | `cull.analyze` |
| `apply_culling` | `cull.apply` |
| `find_faces` | `ai.findFaces` |
| `list_people` | `people.list` |
| `name_person` | `people.name` |
| `get_develop_controls` | `develop.controls` |
| `get_develop` | `develop.get` |
| `develop_set` | `develop.set` |
| `develop_patch` | `develop.update` |
| `auto_tone` | `develop.auto` |
| `auto_white_balance` | `develop.autoWhiteBalance` |
| `reset_develop` | `develop.reset` |
| `list_presets` | `preset.list` |
| `apply_preset` | `preset.apply` |
| `sync_settings` | `develop.sync` |
| `add_ai_mask` | `develop.aiMask`, `develop.get`, `develop.update` |
| `add_gradient_mask` | `develop.get`, `develop.update` |
| `auto_straighten` | `develop.autoStraighten` |
| `upright` | `develop.upright` |
| `denoise` | `ai.denoise` |
| `super_resolution` | `ai.superResolution` |
| `merge_hdr` | `ai.hdrMerge` |
| `merge_panorama` | `ai.panoMerge` |
| `list_export_presets` | `export.presets` |
| `export_photos` | `export.run` |
| `print_pdf` | `print.run` |
| `make_book` | `book.autoLayout`, `book.export` |
| `export_slideshow` | `slideshow.export` |
| `export_web_gallery` | `web.export` |
| `publish` | `publish.run` |
| `show_in_window` | `event agent.show` |
| `undo` | `edit.undo` |
| `redo` | `edit.redo` |
| `list_commands` | the registry catalogue (`GET /api/commands`) |
| `run_command` | any command id, except `photo.delete`, `folder.remove`, `library.newCatalog` and `library.openCatalog` |
