# Intake

## Use, build, or both

| Signal in the request | Class | First specialist |
| --- | --- | --- |
| Photos, a shoot, a folder of raws, "my catalog", picks, edits, an export, a PDF, a gallery | use | `formlit-driving`, then catalog-keeper for depth |
| A file path under `backend/app`, `frontend/src`, `src-tauri` or `setup` | build | the owner of that path |
| A missing feature ("formlit can't...", "add a ...") | build | engine-builder |
| A bug the person saw in the window | build | ui-builder, or engine-builder when the command returned wrong data |
| A slow render, wrong colours, a seam at 1:1 | build | pipeline-builder |
| "Release", "version", "zip", "desktop app", "CI" | build | release-keeper |
| A feature that does not exist yet, for photos that do | both | engine-builder, then the use specialist |

## When to ask

Ask one short question, in prose with the options written out, only when a wrong guess is expensive or cannot be undone: deleting or moving files, overwriting exports, publishing to a live site, or a large batch where the person's taste decides the result (a look for 800 wedding photos). Everything else takes the most reasonable reading, states it, and proceeds; every catalog change can be undone.

## Ledger row

```
step | specialist | asked | produced | evidence
1    | cull-assistant | cull the 2026-09 Lisbon import | 41 picks, 12 rejects | apply_culling result, 4 previews checked
```

## Paths that matter

| Path | What lives there |
| --- | --- |
| `backend/app/engine/` | commands, catalog, query, tasks, events, boot |
| `backend/app/develop/` | the develop pipeline and its kernel |
| `backend/app/ai/` | models, nets, merges, culling, enhance |
| `backend/app/output/` | export, encode, layout, pages, slideshow, web, publish |
| `backend/app/routers/` | REST, SSE, MCP |
| `frontend/src/modules/` | Library, Develop, output modules, shared commands and dialogs |
| `frontend/src/ui/` | shell, panels, forms, dialogs, icons, thumbs, viewer |
| `src-tauri/` | the desktop shell and sidecar config |
| `setup/` | install, boot, build, freeze, mcp, agents, cli scripts |
