# Contributing to FormLit

Thank you for helping. FormLit aims to be a free, local-first photo library and raw
developer, and it gets there through real use and real contributions.

## Where to start

- **Use it and report what goes wrong.** A clear bug report, with steps, the version
  and your platform, is one of the most useful things you can give.
- **Look at the open issues.** Comment on one before starting larger work, so nobody
  builds the same thing twice.
- **Translations** are welcome: FormLit ships in 26 languages, with the tables in
  `frontend/src/i18n`.

## Setting up

Clone the repository and run `./formlit install`, then `./formlit boot` (or
`formlit.bat install` and `formlit.bat boot` on Windows). The first installs the
engine and the interface; the second starts both. `./formlit help` lists every
command, `./formlit doctor` checks the toolchain and ports, and the README's Quick
Start has the details and the requirements.

The code lives in:

| Folder | What is there |
| --- | --- |
| `backend/app` | the engine (Python, FastAPI): catalog, commands, develop pipeline, local models, output, MCP |
| `shared/controls.json` | the develop control table read by the engine, the interface and the agents |
| `frontend/src` | the interface (TypeScript, Vite) |
| `src-tauri` | the desktop shell (Rust, Tauri) |
| `setup` | install, build, packaging and agent scripts |
| `backend/tests`, `frontend/tests/window` | the engine tests and the window smoke test |
| `.docs/wiki` | the wiki's source, published on push |

## Before you open a pull request

Run the same checks CI runs:

```sh
(cd frontend && npm ci && npm audit --audit-level=low && npm run build)
(cd backend && python -m compileall -q app formlit_engine.py && python formlit_engine.py --selfcheck)
(cd backend && python -m pytest tests -q -p no:cacheprovider)
python -m pytest frontend/tests/window -q -p no:cacheprovider
```

The engine tests need `backend/requirements.txt` and `backend/requirements-test.txt`;
the window smoke test needs the built window and Playwright's Chromium. CI also checks
the shell scripts with `bash -n` and refuses an em dash in tracked Markdown or an
emoji in any tracked text.

- Keep each pull request to one change, with tests for what it adds or fixes.
- Write commit subjects the way the history does, in Conventional Commits:
  `feat(develop): ...`, `fix(library): ...`, `docs(...)`, with a body that says why
  (see [.docs/BRANCHING.md](.docs/BRANCHING.md)). Leave the version alone; the
  maintainer bumps it when releasing.
- Every action is a command registered in the engine and reached the same way by the
  interface, the command line and the MCP server. After changing the MCP tools, run
  `./formlit agents sync` so the skill's tool reference follows.
- Rendering happens in the engine only, and the numba kernel and its numpy reference
  must agree.
- Every new dependency, binary, model, font or data file gets a row in `NOTICE.md`
  before it is used.
- Other vendors' product names appear only to name a file format or compatibility.
  Preset values come from FormLit's own tuning or published technique articles,
  never from another vendor's or creator's preset file. Never copy vendor help text
  or icons.

## Maintainers

FormLit is maintained by:

- the [nodemode-dev](https://github.com/nodemode-dev) organisation on GitHub
- [@nodemode-ai](https://github.com/nodemode-ai)
- [@gbarnai](https://github.com/gbarnai)

Reach them through issues and pull requests.

## How changes land

Only a maintainer pushes to `main`. Everyone else forks the repository and opens a pull request into `main`. A pull request merges when all five checks pass on an up-to-date branch and a maintainer has approved it after its last push.

## Releases

A release is a version, and only a maintainer makes one: after the version is bumped on
`main`, a maintainer cuts a `compile_vX.Y.Z` branch, and formcompiler
(`nodemode-dev/formcompiler`) builds every platform and publishes them together. No
push from a contributor starts a release. See [.docs/BRANCHING.md](.docs/BRANCHING.md)
and the Releasing page of the wiki.

## Licensing

FormLit is licensed under the Apache License, Version 2.0 ([LICENSE](LICENSE), SPDX
`Apache-2.0`). By contributing, you agree that your contribution is licensed under
the same terms. Only add code you have the right to contribute, and name any
third-party code and its licence in the pull request.

## Patents and other people's IP

Some features are deliberately not built, or were taken out, because they come too close to someone else's patent, trademark, copyright or design. The maintainers hold that line with counsel; contributors do not decide it, and nobody here redesigns a feature on their own reading of a patent. This is engineering diligence, not legal advice.

### Features this project will not implement

No feature of formlit has been held back so far. The rules below apply to every change, and a feature can still be held back or removed later; when that happens it is listed here first.

### Rules for every contribution

- Patents: do not add a feature, or a dependency that provides one, that reproduces a method you know to be patented. If you are unsure, open an issue that describes what the feature does, not which patent it resembles. Patent numbers stay out of code, commits, comments, logs and changelogs.
- Trademarks: other vendors' product and feature names appear only to name a file format or compatibility ("opens <format> files", "for use with"). No command, menu, panel, tool, preset, template, theme or agent tool takes another product's feature name, and no text says "like X" or "the way X does it". Describe what the feature does.
- Copyright: never copy another product's help, tooltip, dialog or documentation text (link to it instead); never trace or import vendor icons; never bundle vendor templates, themes, presets, brushes, swatches, LUTs, materials, sample files, sound libraries, stock media or fonts; colour-book names only when reading a person's file. Compatibility layers carry names and signatures only. Test fixtures come from this repository's own scripts.
- Licences: every new dependency, binary, model, font, profile or data file gets a row in `NOTICE.md` before it is used. GPL stays outside the distributed bundle, AGPL nowhere, LGPL dynamically linked and replaceable, MPL files unedited. CC BY credited, CC BY-SA only unmodified, CC NC and ND never. Models with gated or non-commercial terms are optional downloads, never bundled.
- Licence conditions: formlit reads and writes DNG under a specification patent licence whose condition is a prominent notice: the DNG notice stays in the About box, in the ledger and in the README while the app reads or writes DNG.

## Conduct

Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md). Security
problems go through [SECURITY.md](SECURITY.md), never a public issue.
