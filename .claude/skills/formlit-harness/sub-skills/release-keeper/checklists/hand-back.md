# Hand-back

- [ ] Every change is committed; `git status` is clean
- [ ] The version reads the same in all six files and in both zip names, written `vX.Y.Z` with dots
- [ ] The bump commit is the last commit of the series
- [ ] `origin` is `git@github.com:nodemode-ai/formlit.git`
- [ ] `npx tsc --noEmit` clean, the backend compiles, `./formlit agents sync --check` in step
- [ ] The formlit-harness pack validates with zero FAIL (the god-tier-skill-creator validator)
- [ ] README, CHANGELOG, `docs/PARITY.md`, both HASHOUT logs and the wiki reflect the change
- [ ] No emoji in any file; no U+2014 em dash in any markdown
- [ ] The repo zip excludes `node_modules`, `venv`, `dist`, `target`, caches and models; the sidecar zip holds the four planning documents
- [ ] The turn ledger states the throttled verification result
