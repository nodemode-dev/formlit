<p align="center">
  <img src="assets/app-icon/formlit-256.png" width="128" height="128" alt="FormLit icon">
</p>

<h1 align="center">FormLit</h1>

<p align="center">
  <b>Photography; a photo library and raw developer for the web and the desktop.</b><br>
  Catalog, cull, develop, map, print and publish,<br>
  non-destructively, on your own machine. No account, and agents can work in it over MCP.
</p>

<p align="center">
  <img alt="version 0.51.0" src="https://img.shields.io/badge/version-0.51.0-eef0f4?style=flat-square">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-7-3178c6?style=flat-square&logo=typescript&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square&logo=python&logoColor=white">
  <img alt="macOS, Windows, Linux" src="https://img.shields.io/badge/macOS%20%C2%B7%20Windows%20%C2%B7%20Linux-native-2f7bf5?style=flat-square">
  <img alt="License: Apache 2.0" src="https://img.shields.io/badge/license-Apache--2.0-3a3a3a?style=flat-square">
  <img alt="Status: pre-release" src="https://img.shields.io/badge/status-pre--release-d69e2e?style=flat-square">
</p>

<p align="center">
  <a href="https://formlit.formai.studio/"><b>Download FormLit on formai.studio</b></a> ·
  <a href="#run-it-from-source">Run it from source</a> ·
  <a href="demo/README.md">Try the offline demo</a> (open <code>demo/index.html</code>, no install), and its two companions: <a href="demos/develop/README.md">develop</a> (masks, presets, virtual copies) and <a href="demos/share/README.md">share</a> (map, book, slideshow, print, web)
</p>

<br>

<p align="center">
  <img src="docs/images/formlit-hero.jpg" alt="The Develop module showing a coastal photo of driftwood and rocks, with the navigator and preset groups on the left, the tone curve on the right and a filmstrip of twelve coast picks below" width="100%">
  <br>
  <sub>The Develop module on a coastal photo, with presets, the tone curve and the filmstrip.</sub>
</p>

<p align="center">
  <a href="#features">Features</a> ·
  <a href="#everything-in-the-box">In the box</a> ·
  <a href="#built-for-agents">Agents</a> ·
  <a href="#under-the-hood">Under the hood</a> ·
  <a href="#download">Download</a> ·
  <a href="#run-it-from-source">Run from source</a>
</p>

<br>

<table>
  <tr>
    <td width="25%" valign="top"><h3>Non-destructive</h3>One catalog with undo for every change, and edits kept in settings and sidecars, never in your originals.</td>
    <td width="25%" valign="top"><h3>Raw to print</h3>Library, Develop, Map, Book, Slideshow, Print and Web modules take a shoot from import to delivery.</td>
    <td width="25%" valign="top"><h3>Local AI</h3>Masks, denoise, culling and search by description run on your machine with ONNX Runtime and pinned models.</td>
    <td width="25%" valign="top"><h3>Agent-ready</h3>The same 288 commands from the window, the terminal and an MCP server for Claude Code, Codex and Cursor.</td>
  </tr>
</table>

<br>

## Features

<table>
  <tr>
    <td width="50%" valign="top"><img src="docs/images/formlit-library.png" alt="The Library grid with star ratings, flags and colour labels, the catalog and keyword panels" width="100%"><br><sub>The Library grid with ratings, flags, colour labels and keywords.</sub><h3>A catalog that keeps up</h3>Rate, flag, label and keyword photos, then find them again with collections, filters and search by description.</td>
    <td width="50%" valign="top"><img src="docs/images/formlit-before-after.webp" alt="Develop with a split Before and After view of a sunset photo" width="100%"><br><sub>Develop with a split Before and After view.</sub><h3>One pipeline for screen and export</h3>The engine renders the preview, 1:1 regions and exports from the same pipeline, so what you see is what you save.</td>
  </tr>
  <tr>
    <td width="50%" valign="top"><img src="docs/images/formlit-export.png" alt="The Export dialog with presets for web, print, client galleries and archives" width="100%"><br><sub>The Export dialog and its built-in presets.</sub><h3>Export for the job</h3>Presets for web, email, print, client galleries, stock and archive, with sizing, sharpening, colour space and metadata choices.</td>
    <td width="50%" valign="top"><h3>Proof, publish and tether</h3>Export a proofing gallery a client opens in any browser, publish to folders, FTP, WebDAV, Nextcloud or S3, and tether a camera with gphoto2 or digiCamControl.</td>
  </tr>
</table>

<sub>Screenshot content: CC0 photos from Poly Haven.</sub>

## Everything in the box

<table>
  <tr>
    <td width="33%" valign="top"><h4>7 modules</h4>Library · Develop · Map · Book · Slideshow · Print · Web</td>
    <td width="33%" valign="top"><h4>978 presets in 103 groups</h4>Color · Film · Cinematic · B&amp;W · Portrait · Landscape · Golden Hour · Night &amp; Astro · Travel · Food</td>
    <td width="33%" valign="top"><h4>Formats</h4>Opens: raw through LibRaw, JPEG, TIFF, PNG, PSD, HEIC, AVIF, WebP, JPEG XL, video · Saves: JPEG, PNG, TIFF, PSD, JPEG XL, WebP, AVIF, HEIC, DNG</td>
  </tr>
  <tr>
    <td width="33%" valign="top"><h4>26 languages</h4>English by default, with the engine's messages and preset names translated too</td>
    <td width="33%" valign="top"><h4>Masks and retouching</h4>Brush · Gradients · Range masks · AI subject and sky · Heal · Clone · Remove</td>
    <td width="33%" valign="top"><h4>Merges</h4>HDR · Panorama · Focus stack · Astro stack · Flash and window blend</td>
  </tr>
</table>

## Built for agents

The window, the terminal and the MCP server call the same registry of 288 engine commands, and the MCP server exposes 82 curated tools over it.

```sh
./formlit cli list                                  # every engine command
./formlit cli library.import 'paths=["/path/to/photos"]' mode=add   # import a folder
./formlit cli photo.rate ids=[1,2] rating=5         # rate photos
./formlit mcp                                       # MCP server on stdio for Claude Code, Codex and Cursor
```

`.mcp.json`, `.codex/config.toml` and `.cursor/mcp.json` are already wired in this repo. See [`AGENTS.md`](AGENTS.md).

## Extensions

formlit loads Form extensions (Form Extension Contract, API 1): web pages in a sandboxed frame that read and change the catalog through formlit's own commands, each change one undo step. Install them with FormPortal or make one with form.ext; they appear in the Extensions menu and the Extensions panel, and agents reach them with the `extensions_list` and `extension_command` tools. [`docs/EXTENSIONS.md`](docs/EXTENSIONS.md) is the API page.

## Under the hood

- **Engine:** Python 3.12 and FastAPI, with a SQLite catalog in WAL mode and a numba develop kernel.
- **Interface:** vanilla TypeScript and Vite, no UI framework, with the Form family's Studio Dark design.
- **Desktop:** a Tauri 2 shell around the engine as a sidecar; it picks a free port when 8390 is taken.
- **Local models:** ONNX Runtime, downloaded on first use and pinned to a SHA-256.
- **Zero flash:** the shell mounts once and every list is patched by key, not re-rendered.

## Download

| Platform | Download | Release |
|---|---|---|
| macOS | [Download FormLit for macOS](https://formai.studio/get/formlit/macos) | [FormLit releases on FormCompiler](https://github.com/nodemode-dev/formcompiler/releases?q=formlit-v&expanded=true) |
| Windows | [Download FormLit for Windows](https://formai.studio/get/formlit/windows) | [FormLit releases on FormCompiler](https://github.com/nodemode-dev/formcompiler/releases?q=formlit-v&expanded=true) |
| Linux | [Download FormLit for Linux](https://formai.studio/get/formlit/linux) | [FormLit releases on FormCompiler](https://github.com/nodemode-dev/formcompiler/releases?q=formlit-v&expanded=true) |

All FormLit builds are compiled and released from [FormCompiler](https://github.com/nodemode-dev/formcompiler); this repo holds the source.

## Run it from source

Prefer it in your browser, or want to contribute? Run the web UI straight from this repo.

**Requires:** Node 20.19 or newer, Python 3.12 or newer, git. `ffmpeg` on the PATH for video export and slideshows.

```sh
git clone git@github.com:nodemode-dev/formlit.git
cd formlit
./formlit install     # engine (add --lite to skip the AI extra) and frontend
./formlit boot        # web UI at http://localhost:5390
```

`./formlit desktop dev` opens the desktop window instead (needs Rust and the Tauri 2 system packages), and `./formlit help` lists every command.

On Windows use `formlit.bat install` and `formlit.bat boot`. The engine listens on http://127.0.0.1:8390 (API under `/api`, MCP at `/mcp`); `FORMLIT_DATA_DIR` moves the data root (default `~/Formlit`).

> [!IMPORTANT]
> **Status:** pre-release. The desktop bundle has not been built from a release branch yet, and tethering, printing and Windows terminals are untested on real hardware. See [`docs/PARITY.md`](docs/PARITY.md).

**Contributing:** branch from `main`, keep changes to source here, and leave packaging and releases to FormCompiler. See [`.docs/BRANCHING.md`](.docs/BRANCHING.md) and [`AGENTS.md`](AGENTS.md).

## Repository

| Path | What it is |
|---|---|
| `backend/` | FastAPI engine: catalog, develop pipeline, local AI, output |
| `frontend/` | Vite app in vanilla TypeScript |
| `src-tauri/` | Tauri 2 desktop shell |

Docs: [`.docs/wiki`](.docs/wiki) · Agents: [`CLAUDE.md`](CLAUDE.md), [`AGENTS.md`](AGENTS.md) · Contributing: [`.docs/BRANCHING.md`](.docs/BRANCHING.md)

<br>

---

## Maintainers

| Maintainer | Role |
|---|---|
| [@nodemode-ai](https://github.com/nodemode-ai) | Owner |
| [@gbarnai](https://github.com/gbarnai) | Co-owner |

Code owners are set in [`.github/CODEOWNERS`](.github/CODEOWNERS).

## License

FormLit is licensed under the Apache License 2.0 ([`LICENSE`](LICENSE), SPDX `Apache-2.0`). Copyright 2026 NodeAgentc, Inc. Third-party notices: [`NOTICE.md`](NOTICE.md).

This product includes DNG technology under license by Adobe Systems Incorporated.

<sub>Adobe, Camera Raw, Lightroom and Photoshop are trademarks of Adobe. FormLit is an independent project and is not affiliated with or endorsed by Adobe; the names describe file formats and compatibility only.</sub>
