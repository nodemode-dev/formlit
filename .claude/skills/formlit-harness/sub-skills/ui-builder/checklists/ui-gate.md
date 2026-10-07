# UI gate

- [ ] `npx tsc --noEmit` in `frontend/` prints nothing
- [ ] No list is cleared and refilled; keyed lists use `patchList`, and new rows are painted on creation
- [ ] No raw colour outside a token block, no raw z-index, no icon library import
- [ ] Every new control has a label or `aria-label`; buttons that run commands use `data-cmd` so their titles show the shortcut
- [ ] Shortcuts are written `Alt+Shift+Mod+Key` and do not collide with an existing command (`ctx.commands.forCombo`)
- [ ] The change was exercised under 4x CPU and network throttling after a hard reload, watching the moment of change
- [ ] Layout holds at 1280 x 800 and 1920 x 1080; the module bar collapses inactive labels under 1540 px
- [ ] No emoji, no U+2014 em dash, no new comments; `frontend/HASHOUT_LOG.md` has the entry
