# Adding a command

## A mutating command

```python
@command("photo.setCopyright", "Set Copyright", {"ids": {"type": "array"}, "text": {"type": "string"}})
def set_copyright(ids: Any = None, text: str = "") -> dict:
    pids = resolve_ids(ids)
    c = cat()
    with c.change("Set Copyright") as ch:
        for pid in pids:
            meta = loads(c.scalar("SELECT meta FROM photos WHERE id=?", (pid,)), {})
            meta["copyright"] = text.strip()
            ch.update("photos", pid, meta=meta)
    return {"ids": pids}
```

- The params dict documents the call for the catalogue and MCP; `dispatch` refuses names the signature does not have.
- `resolve_ids(None)` means the window's selection; agents always pass ids.
- `ch.update`, `ch.insert`, `ch.delete` record undo operations and touched rows; the commit publishes `photos.changed` with the changed fields and `list.changed` for list tables.
- `undoable=False` on `change()` for derived data (scores, faces) that undo should not walk through.

## A read-only command

Pass `mutates=False`. It must not open a change.

## A long job

```python
def job(progress):
    for i, pid in enumerate(pids):
        if progress.cancelled:
            break
        ...
        progress(i + 1, len(pids), f"Working {i + 1} of {len(pids)}")
    return {"done": len(pids)}
return _wait(tasks.start("kind", "Label shown in the window", job), wait)
```

Tasks publish `task` events (`running`, `done` with `result`, `failed` with `error`); the window shows them in the status bar, and `whenDone(task)` in `frontend/src/modules/shared/tasks.ts` awaits them.

## Errors

`raise CommandError("A sentence that says what to do next", status)`. 404 for a missing thing, 409 for a missing prerequisite (a model, ffmpeg), 403 for refused actions. The router returns `{"ok": false, "error": ...}`; MCP returns `isError` with the same text.

## An MCP tool

```python
(_tool("set_copyright", "Sets the copyright line on photos.", {"ids": IDS, "text": {"type": "string"}}, ["ids", "text"], idempotent=True),
 lambda a: _cmd("photo.setCopyright", ids=a["ids"], text=a["text"])),
```

Hints: `read=True` for read-only, `destructive=True` for anything that replaces or removes, `idempotent=True` when repeating changes nothing. Then `./formlit agents sync` and add the tool to a group in `setup/agents.py` `GROUPS`.

## Events the window listens to

`photos.added`, `photos.removed`, `photos.changed` (`photos: {id: [fields]}`), `list.changed` (`list`: collections, keywords, folders, people, publish, stacks, locations, meta), `render` (a preview size finished), `task`, `undo`, `redo`, `agent.activity`, `agent.show`.
