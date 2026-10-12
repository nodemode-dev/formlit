# formlit

formlit is the form family's photo library and raw developer, an alternative to Adobe Lightroom Classic. It keeps a catalog of your photos, develops raw files non-destructively, and has the Library, Develop, Map, Book, Slideshow, Print and Web modules. It runs in a browser against its local engine and as a Tauri desktop app for macOS, Windows and Linux, and agents drive it through its MCP server.

| Page | What it covers |
| --- | --- |
| [Getting Started](Getting-Started) | Install, boot, every dispatcher command, ports, the data folder |
| [Engine](Engine) | The FastAPI engine: catalog, commands, events, tasks, previews |
| [Pipeline](Pipeline) | The develop pipeline, its stages and the two renderers |
| [Interface](Interface) | The shell, modules, panels and the zero-flash rules |
| [Agents and MCP](Agents-and-MCP) | Using formlit from Claude, the MCP server, the driving skill and the harness |
| [Publish Plug-ins](Publish-Plug-ins) | Writing a publish service plug-in |
| [Keyboard Shortcuts](Keyboard-Shortcuts) | The main shortcuts |
| [Desktop](Desktop) | The Tauri shell and the frozen engine |
| [Releasing](Releasing) | Secrets, the updater key and cutting a desktop release |
| [Verification](Verification) | The throttled browser procedure every interface change passes |

Status at v0.3.0: 57.5 of 58 Lightroom Classic 15 feature rows (57 complete, reflection removal partial) (`docs/PARITY.md` in the repository); the README's Status section and `CHANGELOG.md` list what is not verified yet.

These pages are the source of truth in the repository under `.docs/wiki/`. Edit them there; the wiki workflow publishes them.
