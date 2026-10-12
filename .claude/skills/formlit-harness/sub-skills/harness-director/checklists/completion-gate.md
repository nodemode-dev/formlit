# Completion gate

Run before telling the person a formlit task is done. Every line needs evidence, not a belief.

## Use work

- [ ] Every photo changed was looked at with `get_preview` after the change, or a sample of at least four when the batch is large
- [ ] Every file written is named by its absolute path in the reply
- [ ] Nothing was deleted or moved without the person asking for exactly that
- [ ] Ratings, flags and develop changes can be undone, and the reply says how (`undo`, or Edit > Undo in the window)

## Build work

- [ ] Each changed command was run through `./formlit cli` or the MCP endpoint and its result read
- [ ] `npx tsc --noEmit` in `frontend/` is clean and the backend imports (`python -m compileall -q backend/app`)
- [ ] UI changes were checked in a browser under 4x CPU and network throttling, or the reply says they were not
- [ ] `./formlit agents sync --check` passes when a tool or the MCP server changed
- [ ] A change to the MCP tools or the consent gate was called through `/mcp` or `setup/mcp_stdio.py` with `outsideAgents` allowed, ask and blocked, and the refusals were read
- [ ] HASHOUT logs carry the decisions; no comments were added to code
- [ ] No emoji and no U+2014 em dash in any changed file
- [ ] Commits are Conventional Commits as nodemode-ai with the version in the summary, and release-keeper's hand-back ran
