# formlit

A photo library and raw developer (a Lightroom Classic alternative) for the web and the desktop: vanilla TypeScript and Vite frontend, Python and FastAPI engine, Tauri 2 shell. Two kinds of work happen here; pick the one the person asked for.

## Working on photos (natural language)

When the person wants photos imported, culled, rated, keyworded, developed, masked, merged, exported, printed, made into a book, slideshow or web gallery, or published, use the `formlit` MCP server's tools, guided by the `formlit-driving` skill in `.agents/skills/formlit-driving` (its `references/tools.md` lists every tool). Start with `get_catalog` and `find_photos`, and check develop changes with `get_preview`. The first call asks the person in formlit's window to allow outside agents; when a call is refused, say they can change it in formlit under Preferences, AI agents, and stop instead of retrying.

The MCP server is configured for this repository in `.codex/config.toml` (Codex) and `.cursor/mcp.json` (Cursor); both run `./formlit mcp`, which starts the formlit engine when it is not running. From any other folder, `./formlit agents install` sets Claude Code, Codex and Cursor up for the user account. Deleting photos or folders and opening catalogs stay with the person in the formlit window unless `FORMLIT_MCP_ALLOW_DELETE=1`.

## Changing formlit's code

Read `CLAUDE.md` and `.claude/skills/formlit-harness/SKILL.md` first: they map the subsystems, the laws that apply everywhere, and the specialist sub-skills. After changing the MCP tools in `backend/app/routers/mcp.py`, run `./formlit agents sync` so the driving skill's tool reference and its mirror follow.
