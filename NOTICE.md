# Third-party notices

formlit is licensed under the Apache License 2.0 (see `LICENSE`). Copyright 2026 NodeAgentc, Inc. It includes, ports or depends on the following works.

## Included in this repository

| Work | License | Where |
| --- | --- | --- |
| formvis 1.63.0 design system: tokens, shell, panel and dialog sheets, theme profiles and the pre-paint theme boot, DOM helpers, commands, menus, dialogs, dropdowns, toasts and the icon set (nodemode-ai) | Apache-2.0 | `frontend/src/styles/{tokens,shell,panels,dialogs,light-mode,scrollbars,fonts}.css`, `frontend/src/ui/{dom,themes,commands,menu,dialogs,toast,dropdown,icons}.ts`, `frontend/index.html` |
| Format 0.13.0 terminal and Claude Code pieces: the pseudo-terminal sessions, the terminal WebSocket, the xterm.js dock, the Claude Code discovery, and the one-shot `build_app` script (nodemode-ai) | Apache-2.0 | `backend/app/engine/{terminal,cmd_terminal,claude_code}.py`, `backend/app/routers/terminal_socket.py`, `frontend/src/ui/terminal-dock.ts`, `build_app` |
| formvis 1.63.0 infrastructure: setup scripts, the PyInstaller sidecar, the Tauri 2 shell, the CI and desktop workflows, the MCP bridge and agents installer pattern (nodemode-ai) | Apache-2.0 | `setup/`, `src-tauri/`, `.github/workflows/`, `backend/formlit_engine.py` |
| Form Extension Contract kit, API 1: the host bridge and the extension resolver and file server (nodemode) | Apache-2.0 | `frontend/src/ui/host-bridge.ts`, `backend/app/services/formext_host.py` |
| NodeMode stylized design system (tokens, theme profiles, dom-stable helpers), as carried by formvis | MIT | `frontend/src/styles/tokens.css`, `frontend/src/ui/themes.ts`, `frontend/src/ui/dom.ts` |
| `paintbrush` and `hand` icons from Remix Icon, as carried by formvis | Apache-2.0 | `frontend/src/ui/icons.ts` |
| 25 photographs from Pexels, resized and re-encoded, in the offline demo (photographers and source pages in `demo/CREDITS.md`) | Pexels License | `demo/assets/media/` |
| 9 photographs from Pexels and 6 selection bitmaps made from them, in the develop demo (photographers and source pages in `demos/develop/CREDITS.md`) | Pexels License | `demos/develop/assets/media/` |
| 19 photographs from Pexels, the NASA Blue Marble Next Generation image (NASA Earth Observatory, reduced in size) and a 64 second excerpt of Piano Fantasia No. 1 by Peter Bille Larsen (CC0 1.0), in the share demo (sources and changes in `demos/share/CREDITS.md`) | Pexels License; NASA media usage guidelines; CC0 1.0 | `demos/share/assets/media/` |
The formlit mark is original.

Material used only to test this build on the developer's machine is not included in the repository or any bundle: raw sample files from raw.pixls.us (CC0) and camera DCPs from RawTherapee (used to check DCP rendering, not distributed).

## Format and method references (no code copied)

| Reference | License | Used for |
| --- | --- | --- |
| CUBE TO XMP (github.com/OwenWhw/CUBE-to-XMP), Copyright (c) 2026 魏浩文 (Claw) | MIT | The byte layout of Adobe RGBTable creative profiles (base85 alphabet and order, the compressed block, delta encoding). formlit's reader in `backend/app/develop/adobe_profile.py` was written independently and checked against this project's encoder output. |
| Adobe DNG specification and the published DNG SDK enumerations for RGB tables (primaries, gamma, gamut) | Specification | The meaning of the enum values in creative profiles and the DCP tag numbers read by `backend/app/develop/dcp.py`. No SDK source is included or ported. |

Camera-matching profile names (for example Faithful, Velvia/Vivid, CLASSIC CHROME, ACROS, Cinelike, i-Enhance) are the names camera makers give to settings in their cameras. formlit uses them only to say which in-camera setting a profile approximates; they are trademarks of their owners, and formlit is not affiliated with or endorsed by any camera maker. The profiles themselves are formlit's own approximations, built on a per-photo fit to the camera's embedded JPEG; no maker or Adobe profile data is included.

## Adobe DNG patent licence

This product includes DNG technology under license by Adobe Systems Incorporated.

formlit reads and writes DNG files (AI Denoise and import conversion write them, through `backend/app/ai/dng.py`). Adobe's DNG Specification patent licence is worldwide and royalty-free for reading and writing files that comply with the DNG Specification, on condition that distributed products display the notice above prominently; it is shown in formlit's About box under Licences and notices. Adobe may revoke the licence from anyone who, with their affiliates, brings a patent action against Adobe over reading or writing DNG files. Source: the licence text Adobe ships with the DNG SDK (`PATENTS`).

## Distributed with the app

| Package | License | Notes |
| --- | --- | --- |
| Inter, JetBrains Mono (via @fontsource) | SIL OFL 1.1 fonts, MIT packaging | bundled font files |
| The in-app demos' media: the 25 demo photographs (`demo/CREDITS.md`), the 6 selection bitmaps of the develop demo (`demos/develop/CREDITS.md`), and the share demo's 19 photographs and the Piano Fantasia No. 1 excerpt by Peter Bille Larsen (`demos/share/CREDITS.md`), the same files the browser demos carry, decoded from their packs by `scripts/demo-media.mjs` | Pexels License; CC0 1.0 | `frontend/public/demos/`, copied into the interface build; Help > Demos copies a demo's files into a new demo catalog folder under Formlit/Demos. The share demo's NASA basemap is not shipped (the app's Map module uses its own tiles) |
| Liberation Sans, Serif and Mono 2.1 (Red Hat; Arimo, Tinos, Cousine digitized data by Google) | SIL OFL 1.1 | `shared/fonts/liberation`, embedded in PDF/X book files (metric-compatible with Helvetica, Times and Courier); licence in that folder |
| paramiko, pikepdf | LGPL-2.1, MPL-2.0 | engine: SFTP sending, PDF/X finishing |
| tauri, tauri-plugin-shell, tauri-plugin-dialog, tauri-plugin-updater, regex, serde | Apache-2.0 or MIT | desktop shell |
| fastapi, uvicorn, python-multipart, httpx | MIT, BSD-3-Clause | engine |
| Pillow | MIT-CMU | engine |
| numpy | BSD-3-Clause | engine |
| opencv-python-headless | Apache-2.0 (OpenCV), MIT (packaging) | engine; its Linux and Windows wheels carry LGPL FFmpeg as separate shared libraries, kept separable in the frozen engine. The macOS wheel carries GPL FFmpeg parts (libx264, libx265, rubberband, vidstab, postproc), so macOS builds install OpenCV from source without FFmpeg and `setup/freeze_backend` stops if any of those libraries are in the installed OpenCV |
| rawpy, with LibRaw | MIT (rawpy); LibRaw is LGPL-2.1 or CDDL-1.0 at the recipient's choice | camera raw decoding; LibRaw ships in rawpy's wheels as a separate shared library, kept separable and replaceable in the frozen engine |
| pillow-heif | BSD-3-Clause; bundles LGPL libheif and GPL x265 | server-side engine only; excluded from the frozen desktop engine |
| exifread | BSD-3-Clause | EXIF reading for every format |
| tifffile | BSD-3-Clause | 16-bit and float TIFF |
| reportlab | BSD-3-Clause | Book and Print PDF output |
| onnxruntime | MIT | local AI models |
| @xterm/xterm, @xterm/addon-fit | MIT | the terminal dock |
| ptyprocess (macOS, Linux), pywinpty (Windows) | ISC, MIT | pseudo-terminals for the terminal dock |
| numba, llvmlite | BSD-2-Clause | the compiled develop kernel; llvmlite carries LLVM under Apache-2.0 with LLVM exceptions |
| ffmpeg 7.1.5, ffprobe | LGPL-2.1-or-later for the downloaded build; an installed one keeps its own licence | not bundled; an installed ffmpeg is used as before, and when none is found the engine downloads the LGPL build (`--disable-gpl --disable-nonfree`; libopus and libvpx BSD-3-Clause) from the nodemode-dev/formcut-binaries release on first run, checks every file's SHA-256 against `backend/app/ffmpeg_record.py`, and runs it as an external program for video thumbnails, slideshow video and video export; its source is attached to that release |
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
| U-2-Net human segmentation (u2net_human_seg.onnx, rembg release v0.0.0), https://github.com/danielgatis/rembg/releases/tag/v0.0.0 | Apache-2.0, as `backend/app/ai/models.py` records | Select People |
| MediaPipe selfie multiclass (Google), 256x256 ONNX export senty-au/selfie_multiclass_256x256-ONNX, https://huggingface.co/senty-au/selfie_multiclass_256x256-ONNX | Apache-2.0, as `models.py` records | Parts masks: hair, skin, clothes |
| SCUNet real-world denoiser (Kai Zhang et al.), scunet_color_real_psnr as ONNX by Heliosoph, https://huggingface.co/Heliosoph/scunet-onnx | Apache-2.0 (SCUNet), MIT (KAIR weights), as `models.py` records | AI Denoise |
| Mask R-CNN v2 ResNet-50 FPN (torchvision), ONNX export in the ONNX Model Zoo, https://huggingface.co/onnxmodelzoo/maskrcnn_resnet50_fpn_v2_Opset17 | BSD-3-Clause weights, Apache-2.0 export, as `models.py` records | Selecting each person apart |
| SigLIP base patch16-224 (Google), quantized ONNX export by Xenova, https://huggingface.co/Xenova/siglip-base-patch16-224 | Apache-2.0, as `models.py` records | Search by description |

The lens profile database is downloaded when the person chooses Download Lens Profiles in Lens Corrections: the Lensfun project's XML files (data/db, lensfun.github.io), used unmodified under CC BY-SA 3.0 and credited in the panel. formlit reads the files and keeps a derived index beside them in the models folder; Lensfun's LGPL library code is not used. Unlike the models, the files track Lensfun's main branch and are not hash-pinned, because the database is updated as lenses are calibrated. The data is downloaded only on request, and no checksum is pinned or checked for it.

## Python packages frozen into the engine, beyond the tables above

The engine is frozen with PyInstaller `--onefile` (`setup/freeze_backend`). These packages are installed in `backend/venv` from `backend/requirements.txt` and are collected by the freeze (directly or as dependencies of fastapi, uvicorn[standard], httpx, paramiko, pikepdf and onnxruntime); each licence is read from the package's installed metadata. "Frozen in" is inferred from the freeze flags and imports, not from a built bundle.

| Package | Licence |
| --- | --- |
| CPython runtime and standard library | PSF-2.0 |
| typing_extensions | PSF-2.0 |
| certifi 2026.10.19 | MPL-2.0 (cacert.pem unedited) |
| PyInstaller 6.22.3 (its bootloader is the executable stub of the frozen engine) | GPL-2.0-or-later with the PyInstaller exception that permits distributing the frozen program under another licence (PyPI metadata for 6.22.3) |
| starlette, pydantic, pydantic_core, annotated-types, annotated-doc, typing-inspection, anyio, h11, httptools, uvloop, watchfiles, PyYAML, Deprecated | MIT (uvloop: MIT or Apache-2.0) |
| websockets, click, httpcore, idna, python-dotenv, protobuf, lxml, pycparser | BSD-3-Clause |
| invoke, wrapt | BSD-2-Clause |
| charset-normalizer | MIT |
| bcrypt, PyNaCl | Apache-2.0 |
| cryptography 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| cffi 2.1.1 | MIT-0 |
| flatbuffers 25.12.19 | Apache-2.0 |
| packaging | Apache-2.0 OR BSD-2-Clause |

## Desktop shell: crates under other licences

Tauri links these crates unedited (no `[patch]` and no vendored copy):

| Crate | Licence | Why it is there |
| --- | --- | --- |
| cssparser, selectors, dtoa-short, option-ext | MPL-2.0 | Tauri's HTML handling (tauri-utils); used unmodified, source at crates.io |
| ring | Apache-2.0 AND ISC | TLS for the updater (rustls) |
| webpki-root-certs | CDLA-Permissive-2.0 | root certificates for the updater's TLS |
| r-efi | MIT OR Apache-2.0 OR LGPL-2.1-or-later | used under MIT |

The Linux AppImage also carries the build machine's WebKitGTK, GTK and GLib (LGPL-2.1-or-later) as separate shared libraries.

## Development only, never shipped

| Package | Licence | Notes |
| --- | --- | --- |
| pytest 9.1.1 (with iniconfig, packaging, pluggy, pygments) | MIT (pytest, iniconfig, pluggy), Apache-2.0 OR BSD-2-Clause (packaging), BSD-2-Clause (pygments) | runs `backend/tests` in CI (`backend/requirements-test.txt`); never installed in the app |
| Playwright for Python 1.63.0 (with its Chromium) | Apache-2.0 | runs `frontend/tests/window` (the window smoke) in CI; never installed in the app |

## Map tiles

The Map module shows OpenStreetMap tiles. Map data copyright OpenStreetMap contributors, available under the Open Database License; the attribution is drawn on the map. The Terrain style shows OpenTopoMap tiles (CC-BY-SA, with SRTM elevation data), also attributed on the map. Tiles are fetched while the Map module is open and are not stored in the repository. Look Up Address asks the OpenStreetMap Nominatim service for place names (one request per second, only when the user runs it); results are data from OpenStreetMap contributors under the ODbL. Search Map uses the same Nominatim service, one request per second, only when the user presses Enter. The Satellite and Hybrid styles show Sentinel-2 cloudless 2016 by EOX IT Services GmbH (https://s2maps.eu), licensed CC BY 4.0, containing modified Copernicus Sentinel data 2016; the attribution is drawn on the map. Only the 2016 layer is used, because the later EOX years are licensed CC BY-NC-SA, which this project does not accept. The Light and Dark styles are the OpenStreetMap tiles recoloured in the browser.

## Trademarks

Adobe, Camera Raw, Lightroom and Photoshop are either registered trademarks or trademarks of Adobe in the United States and/or other countries. formlit is not affiliated with or endorsed by Adobe; the names describe file formats and compatibility only (XMP sidecars and DNG files that Lightroom and Camera Raw read and write).
