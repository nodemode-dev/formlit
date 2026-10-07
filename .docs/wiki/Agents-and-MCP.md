# Agents and MCP

formlit speaks the Model Context Protocol so Claude Code, Codex and Cursor can work on your photos with tools, and it ships skills for agents that work on formlit's own code.

## The server

The engine serves MCP over streamable HTTP at `http://127.0.0.1:8390/mcp`. `./formlit mcp` is the stdio shim agents run; it starts the engine when it is not running. `.mcp.json` (Claude Code), `.codex/config.toml` and `.cursor/mcp.json` point at it for this repository, and `./formlit agents install` registers it for your user account in all three.

There are 49 curated tools in seven groups (Look, Import and organize, Cull and people, Develop, Enhance and merge, Output, Window and history) plus `run_command`, which reaches any of the engine's 217 commands. Two prompts, `culling_workflow` and `develop_strategy`, give agents a starting order of work. `GET /api/mcp/status` reports the endpoint, the counts and the protocol versions.

## Skills

- `formlit-editing` (`.claude/skills` and its `.agents/skills` mirror) teaches agents to drive formlit: the order of work, the develop ids, checking with previews. Its `references/tools.md` is generated from the server by `./formlit agents sync`; run it after changing `backend/app/routers/mcp.py`.
- `formlit-harness` (`.claude/skills/formlit-harness`) is the pack for both kinds of agent work. Its director routes to catalog-keeper, cull-assistant, develop-artist and output-producer for working on photos, and to engine-builder, pipeline-builder, ui-builder and release-keeper for changing formlit.

## Safety

Deleting photos or folders and opening or creating catalogs are reserved for the person in the window unless `FORMLIT_MCP_ALLOW_DELETE=1`. Every agent change is a command, so it is undoable like any other.
