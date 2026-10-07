# Module recipe

## A module

```ts
registerModule({
  id: 'library', label: 'Library', icon: 'modLibrary', key: 'Alt+Mod+1', order: 1,
  mount(ctx, hosts) { /* build once into hosts.left, hosts.stage, hosts.toolbar, hosts.right, hosts.leftFoot, hosts.rightFoot */ },
  activate() { /* refresh what may have changed while hidden */ },
  deactivate() {},
  onKey(e, combo) { return false; },
});
```

Modules mount once at start; switching only toggles which host pages show. Add the import to `src/modules/index.ts`. Module keys follow Lightroom: `Alt+Mod+1` to `Alt+Mod+7`, `D` for Develop.

## A panel

```ts
const p = new Panel('lib.people', 'People', { open: false, tools: [button] });
p.body.append(content);
p.onOpen = (open) => { if (open) load(); };
host.appendChild(p.root);
```

Panel open state persists per id. Alt-click a head solos the panel.

## An output module

Extend `OutputModule` (`src/modules/output/base.ts`) and supply `optionsCmd` (an engine command returning `defaults` and `templates` or `presets`), `kind` (the collection kind for saved creations), and five builders: toolbar, stage, panels (use `formPanel(host, id, title, specs)`), foots, and `refresh()` which asks the engine for a layout and paints it. The base gives the Template Browser, Saved panel, the Use selector (all, selected, flagged), settings persistence and debounced refresh.

Pages paint through `PageView` (`src/modules/output/page.ts`): cells and overlays come from the engine's layout in inches and are positioned in percentages of the page, so the preview and the PDF agree. Images use `previewUrl` when the page is large and `thumbUrl` when small.

## Stores and events

`library` (`src/state/library.ts`) holds the source, filter, sort, ids, photos, selection and active photo; `listen('list' | 'photos' | 'selection' | 'render', fn)`. `catalog` holds the folder, collection and keyword tree. `events.on(kind, fn)` reaches every SSE event, including `task`, `agent.activity` and `agent.show`.
