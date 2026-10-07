# Third-party notices

formlit is licensed under the Apache License 2.0 (see `LICENSE`). Copyright 2026 nodemode-ai. It includes, ports or depends on the following works.

## Included in this repository

| Work | License | Where |
| --- | --- | --- |
| formvis 1.63.0 design system: tokens, shell, panel and dialog sheets, theme profiles and the pre-paint theme boot, DOM helpers, commands, menus, dialogs, dropdowns, toasts and the icon set (nodemode-ai) | Apache-2.0 | `frontend/src/styles/{tokens,shell,panels,dialogs,light-mode,scrollbars,fonts}.css`, `frontend/src/ui/{dom,themes,commands,menu,dialogs,toast,dropdown,icons}.ts`, `frontend/index.html` |
| formvis 1.63.0 infrastructure: setup scripts, the PyInstaller sidecar, the Tauri 2 shell, the CI and desktop workflows, the MCP bridge and agents installer pattern (nodemode-ai) | Apache-2.0 | `setup/`, `src-tauri/`, `.github/workflows/`, `backend/formlit_engine.py` |
| NodeMode stylized design system (tokens, theme profiles, dom-stable helpers), as carried by formvis | MIT | `frontend/src/styles/tokens.css`, `frontend/src/ui/themes.ts`, `frontend/src/ui/dom.ts` |
| `paintbrush` and `hand` icons from Remix Icon, as carried by formvis | Apache-2.0 | `frontend/src/ui/icons.ts` |

The formlit mark is original.

## Distributed with the app

| Package | License | Notes |
| --- | --- | --- |
| Inter, JetBrains Mono (via @fontsource) | SIL OFL 1.1 fonts, MIT packaging | bundled font files |
| tauri, tauri-plugin-shell, tauri-plugin-dialog, tauri-plugin-updater, regex, serde | Apache-2.0 or MIT | desktop shell |
| fastapi, uvicorn, python-multipart, httpx | MIT, BSD-3-Clause | engine |
| Pillow | MIT-CMU | engine |
| numpy | BSD-3-Clause | engine |
| opencv-python-headless | Apache-2.0 (OpenCV), MIT (packaging) | engine; its wheels carry LGPL FFmpeg as separate shared libraries, kept separable in the frozen engine |
| rawpy, with LibRaw | MIT (rawpy); LibRaw is LGPL-2.1 or CDDL-1.0 at the recipient's choice | camera raw decoding; LibRaw ships in rawpy's wheels as a separate shared library, kept separable and replaceable in the frozen engine |
| pillow-heif | BSD-3-Clause; bundles LGPL libheif and GPL x265 | server-side engine only; excluded from the frozen desktop engine |
| exifread | BSD-3-Clause | EXIF reading for every format |
| tifffile | BSD-3-Clause | 16-bit and float TIFF |
| reportlab | BSD-3-Clause | Book and Print PDF output |
| onnxruntime | MIT | local AI models |
| numba, llvmlite | BSD-2-Clause | the compiled develop kernel; llvmlite carries LLVM under Apache-2.0 with LLVM exceptions |
| ffmpeg | LGPL or GPL builds | not bundled; used as an external program for slideshow video and video export when it is installed |
| gphoto2 | GPL-2.0-or-later | not bundled; tethered capture runs the user's installed gphoto2 command in its shell mode and reads its output, without linking to libgphoto2 |
| digiCamControl | MIT | not bundled; tethered capture on Windows runs the user's installed CameraControlCmd.exe |
| imagecodecs | BSD-3-Clause; bundles libjxl (BSD-3-Clause), libavif (BSD-2-Clause), libultrahdr (Apache-2.0), aom and dav1d (BSD-2-Clause) and other permissively licensed codecs, each licence in its `licenses/` folder | JPEG XL import and export, HDR AVIF and JPEG XL export, Ultra HDR checks |

## Downloaded on first use, never bundled

Each model is fetched from a pinned revision and checked against its SHA-256 before use.

| Model | License | Use |
| --- | --- | --- |
| U-2-Net (rembg release) | Apache-2.0 | Select Subject, Select Background |
| Sky segmenter (xiongzhu666, Hugging Face copy) | MIT | Select Sky |
| YuNet face detector, SFace recognizer (OpenCV Zoo) | MIT, Apache-2.0 | People view, Select People |
| Depth Anything V2 Small (onnx-community export) | Apache-2.0 | Depth Range masks, Lens Blur |
| SAM 2.1 tiny (ONNX) | Apache-2.0 | Select Objects |
| LaMa (Carve ONNX export) | Apache-2.0 | Generative Remove |
| Real-ESRGAN x4plus | BSD-3-Clause | Super Resolution |

The lens profile database is downloaded when the person chooses Download Lens Profiles in Lens Corrections: the Lensfun project's XML files (data/db, lensfun.github.io), used unmodified under CC BY-SA 3.0 and credited in the panel. formlit reads the files and keeps a derived index beside them in the models folder; Lensfun's LGPL library code is not used. Unlike the models, the files track Lensfun's main branch and are not hash-pinned, because the database is updated as lenses are calibrated.

## Map tiles

The Map module shows OpenStreetMap tiles. Map data copyright OpenStreetMap contributors, available under the Open Database License; the attribution is drawn on the map. The Terrain style shows OpenTopoMap tiles (CC-BY-SA, with SRTM elevation data), also attributed on the map. Tiles are fetched while the Map module is open and are not stored in the repository. Look Up Address asks the OpenStreetMap Nominatim service for place names (one request per second, only when the user runs it); results are data from OpenStreetMap contributors under the ODbL. Search Map uses the same Nominatim service, one request per second, only when the user presses Enter. The Satellite and Hybrid styles show Sentinel-2 cloudless 2016 by EOX IT Services GmbH (https://s2maps.eu), licensed CC BY 4.0, containing modified Copernicus Sentinel data 2016; the attribution is drawn on the map. Only the 2016 layer is used, because the later EOX years are licensed CC BY-NC-SA, which this project does not accept. The Light and Dark styles are the OpenStreetMap tiles recoloured in the browser.
