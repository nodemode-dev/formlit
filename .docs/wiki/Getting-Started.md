# Getting Started

## Requirements

Node 20.19 or newer (22 recommended), Python 3.12 or newer, git. ffmpeg on the PATH for video export, slideshows and graded video. For the desktop app, Rust stable and the Tauri 2 system packages for your OS. For tethering, gphoto2 (macOS, Linux) or digiCamControl (Windows).

## Install and boot

```bash
./formlit install        # engine with ONNX Runtime, then the frontend; --lite skips the AI extra
./formlit boot           # engine on 127.0.0.1:8390 and the frontend on localhost:5390
```

On Windows use `formlit.bat` with the same commands.

## Dispatcher commands

| Command | What it does |
| --- | --- |
| `./formlit` or `boot` | Boot the engine and the frontend together |
| `install [--lite]` | Install the engine, the AI extra and the frontend |
| `install-ml` | Install the optional AI runtime extras |
| `install-desktop` | Install PyInstaller and check the Rust and Tauri toolchain |
| `backend`, `frontend` | Boot one side only |
| `build` | Production build of the frontend into `frontend/dist` |
| `serve` | Serve the built frontend from the engine on 127.0.0.1:8390 |
| `freeze` | Freeze the engine into the Tauri sidecar binary |
| `desktop dev`, `desktop build` | Run or bundle the desktop app |
| `mcp` | The MCP server over stdio (starts the engine if needed) |
| `agents install`, `agents sync` | Register formlit with Claude Code, Codex and Cursor, or refresh the skill's tool reference |
| `cli <command> key=value ...` | Run any engine command from the terminal; `./formlit cli list` lists them |
| `doctor` | Check the toolchain, the installs and the ports |
| `counts [--check]` | Print the code sizes the README states, or check them |
| `clean [--all]` | Remove build output (`--all` also the venv and node_modules) |

## Ports

| Service | Address |
| --- | --- |
| Frontend (dev) | http://localhost:5390, bound to localhost only, strict port |
| Engine | http://127.0.0.1:8390 (`FORMLIT_PORT`; `0` picks a free port, and the desktop sidecar uses one only when 8390 is already taken) |
| Preview | http://localhost:5391 |

## The data folder

`~/Formlit` by default (`FORMLIT_DATA_DIR`). It holds `Catalog/formlit.fldb` (SQLite) with its `Previews/` and `Masks/` beside it, `Presets/`, `Profiles/` (imported .cube and Adobe .xmp looks and .dcp camera profiles, each with a small JSON file for its name), `Plugins/` (publish plug-ins), `Models/` (local AI models, each pinned to its SHA-256) and `Exports/`. File > New Catalog and Open Catalog switch catalogs; each keeps its previews and masks in its own folder.
