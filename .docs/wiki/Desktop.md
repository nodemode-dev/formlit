# Desktop

The desktop app is a Tauri 2 shell (`src-tauri/`) around the same interface, with the engine frozen into a sidecar binary.

- `./formlit install-desktop` installs PyInstaller and checks the Rust and Tauri toolchain.
- `./formlit freeze` builds `formlit-engine` with PyInstaller from `backend/formlit_engine.py` (collecting the app, uvicorn, rawpy, numba and llvmlite, ONNX Runtime, reportlab and imagecodecs, and bundling `shared/` and the built frontend) into `src-tauri/binaries/`, which git ignores. Command modules and publish services that the engine imports by name are listed with `--hidden-import` in `setup/freeze_backend` and `freeze_backend.bat`; the new binary must pass `--selfcheck` (every one of those modules imports) before it is copied.
- `./formlit desktop dev` runs the shell against the dev frontend; `./formlit desktop build` bundles the app for this OS.

At launch the shell shows a splash, spawns the sidecar with `FORMLIT_PORT=0` (the frozen entry marks itself as the desktop engine and serves the bundled interface), reads the port from the engine's startup line, and loads the interface from it. Closing the window stops the engine. `.fldb` catalogs are associated with the app. In-app updates come from GitHub Releases once the updater key is set (see [Releasing](Releasing)).
