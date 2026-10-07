# Command gate

- [ ] The decorator's params name exactly the parameters the function takes
- [ ] Mutations happen inside one `catalog.change(label)` with a label a person would recognise in the History menu
- [ ] Work longer than a second runs as a task with progress and honours `progress.cancelled`
- [ ] Error messages say what to do next, not what went wrong inside
- [ ] `./formlit cli [command-id] ...` returns the expected result; a mutating command is reversed by `./formlit cli edit.undo`
- [ ] When agents need it: an MCP tool exists, `./formlit agents sync` ran, `./formlit agents sync --check` prints in step
- [ ] `python -m compileall -q backend/app` is clean
- [ ] `backend/HASHOUT_LOG.md` has the entry; the code has no new comments
- [ ] New dependencies were vetted (permissive or LGPL server side; never GPL in the desktop bundle; never AGPL) and recorded in BUILD_NOTES
