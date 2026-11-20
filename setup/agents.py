#!/usr/bin/env python3
"""./formlit agents: formlit for Claude Code, Codex, Cursor and Antigravity.

  sync [--check]            regenerate the driving skill's tool, preset and template references from the engine, write
                            agents/manifest.json (what formlit offers agents) and mirror the skill from .claude/skills to
                            .agents/skills; --check exits 1 when any of them has drifted
  install [--dry-run] [claude|codex|cursor|antigravity ...]
                            register the MCP server (./formlit mcp at this folder's absolute path) and the driving skill
                            for this user account (all four by default); files are backed up before they change.
                            Antigravity gets the MCP server only, in ~/.gemini/config/mcp_config.json; a server named
                            formlit that formlit did not write is left alone.
                            This is the developer path; everyone else adds the formlit plugin from the Form marketplace.
"""

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "formlit-driving"
LEGACY = "formlit-editing"
SKILL = ROOT / ".claude" / "skills" / NAME
MIRROR = ROOT / ".agents" / "skills" / NAME
LAUNCH = str(ROOT / ("formlit.bat" if os.name == "nt" else "formlit"))
APP = "formlit"
MANIFEST = ROOT / "agents" / "manifest.json"
SKILLS = ROOT / ".claude" / "skills"
DOCK = {"present": True, "positions": ["bottom", "right"], "tabs": ["chat", "terminal", "claude-code", "codex", "cursor", "antigravity"]}
DOCK_MODULE = ROOT / "frontend" / "src" / "dock"
LOOKUP = ROOT / "backend" / "app" / "engine" / "agent_lookup.py"
LOOKUP_HASHES = {
    "1.0.0": "252ea9bb9419d4990f174f91914f09800497bc69e98f849f5643bbf4217cc3f3",
    "1.0.1": "62667f9b68b7d101e1896ce617240424e33b7e498c560bc79d45f0ab26c77d51",
}
GROUPS = [
    ("Look", ["get_catalog", "find_photos", "get_photo", "get_preview", "analyze_photo", "get_develop", "get_develop_controls", "list_presets", "list_people", "list_export_presets"]),
    ("Import and organize", ["import_photos", "set_rating", "set_flag", "set_label", "add_keywords", "set_metadata", "set_location", "create_collection", "add_to_collection", "stack_photos"]),
    ("Jobs and templates", ["setup_shoot", "list_templates", "apply_template"]),
    ("Cull and people", ["analyze_culling", "apply_culling", "refine_photos", "find_faces", "name_person"]),
    ("Develop", ["develop_set", "develop_patch", "match_look", "match_exposures", "noise_by_iso", "virtual_copy", "snapshot", "auto_tone", "auto_white_balance", "reset_develop", "apply_preset", "save_preset", "sync_settings", "add_ai_mask", "add_gradient_mask", "auto_straighten", "upright"]),
    ("Enhance and merge", ["denoise", "super_resolution", "merge_hdr", "merge_panorama"]),
    ("Output", ["export_photos", "print_pdf", "make_book", "export_slideshow", "export_web_gallery", "publish"]),
    ("Window, history and everything else", ["show_in_window", "undo", "redo", "list_commands", "run_command", "extensions_list", "extension_command", "get_agent_access"]),
]


def tools_reference() -> str:
    sys.path.insert(0, str(ROOT / "backend"))
    from app.routers.mcp import TOOLS
    tools = [t for t, _ in TOOLS]
    out = ["# formlit tools", "", "Generated from formlit's own tool catalogue; do not edit by hand. Every tool works on the catalog of the formlit app on the person's computer.", "", "## Contents", ""]
    listed: set[str] = set()
    for title, names in GROUPS:
        here = [t["name"] for t in tools if t["name"] in names]
        listed.update(here)
        out.append(f"- {title}: " + ", ".join(f"`{n}`" for n in here))
    rest = [t["name"] for t in tools if t["name"] not in listed]
    if rest:
        out.append("- Other: " + ", ".join(f"`{n}`" for n in rest))
    out.append("")
    for t in tools:
        a = t["annotations"]
        marks = [m for m, on in (("read-only", a["readOnlyHint"]), ("replaces or removes", a["destructiveHint"])) if on]
        out += [f"## {t['name']}", "", t["description"], ""]
        props, required = t["inputSchema"]["properties"], set(t["inputSchema"]["required"])
        for k, v in props.items():
            kind = v.get("type", "any") + (f" ({' | '.join(map(str, v['enum']))})" if "enum" in v else "")
            extra = "; ".join(x for x in (("required" if k in required else ""), (f"default {json.dumps(v['default'])}" if "default" in v else ""), v.get("description", "")) if x)
            out.append(f"- `{k}`: {kind}" + (f"; {extra}" if extra else ""))
        if not props:
            out.append("- no parameters")
        if marks:
            out += ["", "Note: " + ", ".join(marks) + "."]
        out.append("")
    return "\n".join(out)


def presets_reference() -> str:
    sys.path.insert(0, str(ROOT / "backend"))
    os.environ.setdefault("FORMLIT_CATALOG", str(Path(os.environ.get("TMPDIR", "/tmp")) / "formlit-agents-sync" / "sync.fldb"))
    from app.engine import presets
    items = [{"id": presets.builtin_id(p), **p} for p in presets.BUILTIN]
    groups: dict[str, list[dict]] = {}
    for p in items:
        groups.setdefault(p["group"], []).append(p)
    out = ["# formlit built-in presets", "", "Generated from formlit's preset list; do not edit by hand. Preview one with `get_preview` or `analyze_photo` and `preset`, apply it with `apply_preset` and an `amount` (100 is the preset as made, 50 half strength: colour-grading hues stay fixed and only their saturation scales, and curves ease toward straight).",
           "`list_presets` with a `query` searches names, groups, descriptions and tags; the person's own presets are listed there too.", "",
           f"{len(items)} presets in {len(groups)} groups. Adaptive presets add AI masks, which are computed for each photo they reach.", "", "## Contents", ""]
    out += [f"- {name} ({len(ps)})" for name, ps in groups.items()] + [""]
    for name, ps in groups.items():
        out += [f"## {name}", "", "| Preset | What it does | Touches |", "| --- | --- | --- |"]
        for p in ps:
            desc = (p.get("description") or presets.NOTES.get(p["name"], "")).replace("|", "/")
            touches = ", ".join(sorted(k for k in p["settings"]))
            out.append(f"| {p['name']} (`{p['id']}`) | {desc} | {touches} |")
        out.append("")
    return "\n".join(out)


def templates_reference() -> str:
    sys.path.insert(0, str(ROOT / "backend"))
    from app.engine.template_library import FILENAME, FOLDER, KEYWORDS, METADATA, SHOOTS, SMART
    from app.output.export import BUILTIN as EXPORTS
    cell = lambda s: str(s).replace("|", "/")
    out = ["# formlit built-in templates", "", "Generated from formlit's template library; do not edit by hand. `list_templates` returns the same with a `query`; "
           "`apply_template` applies one by id or name; `setup_shoot` runs a whole shoot recipe.", "",
           "Metadata placeholders: {creator} {email} {url} (remembered after the first use), {client} {event} {job} (per call), {year} (this year). A field whose placeholder has no value is skipped.", "",
           "## Contents", "", "- Shoot recipes", "- Export presets", "- Filename templates", "- Folder templates", "- Metadata templates", "- Keyword sets", "- Intelligent collection templates", "",
           "## Shoot recipes", "", "| Recipe | What it sets | Naming, metadata, keywords | Exports | Workflow prompt |", "| --- | --- | --- | --- | --- |"]
    for s in SHOOTS:
        v = s["value"]
        extra = " Noise by ISO at import." if v["isoNoise"] else ""
        out.append(f"| {s['name']} (`{s['id']}`) | {cell(s['description'])}{extra} | {v['folder']}, {v['rename']}, {v['metadata']}, {v['keywords']} | {', '.join(v['exports'])} | {v['workflow']} |")
    out += ["", "## Export presets", "", "| Preset | Group | What it is for |", "| --- | --- | --- |"]
    out += [f"| {p['name']} (`{p['id']}`) | {p.get('group', 'General')} | {cell(p.get('description', ''))} |" for p in EXPORTS]
    for title, items in (("Filename templates", FILENAME), ("Folder templates", FOLDER)):
        out += ["", f"## {title}", "", "| Template | Pattern | Use |", "| --- | --- | --- |"]
        out += [f"| {t['name']} (`{t['id']}`) | `{t['value'] or '(none)'}` | {cell(t['description'])} |" for t in items]
    out += ["", "## Metadata templates", "", "| Template | Fields | Use |", "| --- | --- | --- |"]
    out += [f"| {t['name']} (`{t['id']}`) | {', '.join(t['value'])} | {cell(t['description'])} |" for t in METADATA]
    out += ["", "## Keyword sets", "", "| Set | Keywords |", "| --- | --- |"]
    out += [f"| {t['name']} (`{t['id']}`) | {', '.join(t['value'])} |" for t in KEYWORDS]
    out += ["", "## Intelligent collection templates", "", "| Template | Rules | Use |", "| --- | --- | --- |"]
    out += [f"| {t['name']} (`{t['id']}`) | {'; '.join(cell(r['field'] + ' ' + r['op'] + ('' if r.get('value') in (None, '') else ' ' + str(r['value']))) for r in t['value']['rules'])} | {cell(t['description'])} |" for t in SMART]
    out.append("")
    return "\n".join(out)


def manifest_reference() -> str:
    sys.path.insert(0, str(ROOT / "backend"))
    from app.routers import mcp
    from app.services import formext_host
    tools = [t for t, _ in mcp.TOOLS]
    names = [t["name"] for t in tools]
    transports = [t for t, on in (("stdio", (ROOT / "setup" / "mcp_stdio.py").is_file()), ("http", any(getattr(r, "path", "") == "/mcp" for r in mcp.router.routes))) if on]
    skills = [{"name": s.name, "sub_skills": sorted(p.parent.name for p in (s / "sub-skills").glob("*/SUB-SKILL.md"))}
              for s in sorted(SKILLS.iterdir()) if (s / "SKILL.md").is_file()]
    data = {"format": "form-agent-manifest", "version": 1, "app": APP,
            "mcp": {"tools": names, "read_only": [t["name"] for t in tools if t["annotations"]["readOnlyHint"]], "approval_gated": names, "transports": transports},
            "skills": skills, "dock": DOCK, "extensions": {"host_api": formext_host.API}}
    return json.dumps(data, indent=2) + "\n"


def _files(folder: Path) -> dict:
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def dock_module_drift() -> list[str]:
    import hashlib
    held = DOCK_MODULE / "MANIFEST.json"
    if not held.is_file():
        return [str(held.relative_to(ROOT))]
    want = json.loads(held.read_text(encoding="utf-8"))["files"]
    have = {p.name for p in DOCK_MODULE.iterdir() if p.is_file()} - {"MANIFEST.json"}
    bad = sorted(set(want) ^ have) + sorted(n for n in set(want) & have if hashlib.sha256((DOCK_MODULE / n).read_bytes()).hexdigest() != want[n])
    for name in sorted(have):
        if name.endswith(".ts") and any(not (m.startswith("./") or m.startswith("@xterm/")) for m in re.findall(r"""(?:from|import)\s*\(?\s*['"]([^'"]+)['"]""", (DOCK_MODULE / name).read_text(encoding="utf-8"))):
            bad.append(name)
    return [str((DOCK_MODULE / n).relative_to(ROOT)) for n in dict.fromkeys(bad)]


def lookup_problems() -> list[str]:
    import hashlib
    rel = LOOKUP.relative_to(ROOT).as_posix()
    try:
        raw = LOOKUP.read_bytes()
    except OSError:
        return [f"{rel}: missing (the shared finder for the agent programs)"]
    said = re.search(rb'^VERSION = "([^"\r\n]+)"\r?$', raw, re.M)
    version = said.group(1).decode("ascii", "replace") if said else "unknown"
    if LOOKUP_HASHES.get(version) != hashlib.sha256(raw).hexdigest():
        return [f"{rel}: does not match the hash recorded for version {version} (the shared finder changes only as a whole new version)"]
    return []


def lookup():
    import importlib.util
    spec = importlib.util.spec_from_file_location("formlit_agent_lookup", LOOKUP)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sync(check: bool) -> int:
    held = lookup_problems()
    if held:
        print("agents: " + "; ".join(held))
        return 1
    drift = dock_module_drift()
    if drift and not check:
        print("agents: the shared dock folder does not match its MANIFEST.json and is never written here: " + ", ".join(drift))
        return 1
    for ref, want in ((SKILL / "references" / "tools.md", tools_reference()), (SKILL / "references" / "presets.md", presets_reference()),
                      (SKILL / "references" / "templates.md", templates_reference()), (MANIFEST, manifest_reference())):
        if not ref.exists() or ref.read_text(encoding="utf-8") != want:
            drift.append(str(ref.relative_to(ROOT)))
            if not check:
                ref.parent.mkdir(parents=True, exist_ok=True)
                ref.write_text(want, encoding="utf-8")
    if not MIRROR.exists() or _files(MIRROR) != _files(SKILL):
        drift.append(str(MIRROR.relative_to(ROOT)))
        if not check:
            shutil.rmtree(MIRROR, ignore_errors=True)
            shutil.copytree(SKILL, MIRROR)
    if check:
        print("agents: in step" if not drift else "agents: drifted: " + ", ".join(drift) + " (run ./formlit agents sync)")
        return 1 if drift else 0
    print("agents: " + ("updated " + ", ".join(drift) if drift else "already in step"))
    return 0


def _backup(path: Path, dry: bool) -> None:
    if path.exists() and not dry:
        shutil.copy2(path, path.with_name(path.name + f".bak-{time.strftime('%Y%m%d-%H%M%S')}"))


def _drop_legacy(parent: Path, dry: bool, said: list) -> None:
    old = parent / LEGACY
    manifest = old / "SKILL.md"
    if manifest.is_file() and f"name: {LEGACY}" in manifest.read_text(encoding="utf-8"):
        said.append(f"  remove the old skill {old} (now {NAME})")
        if not dry:
            shutil.rmtree(old, ignore_errors=True)


def _copy_skill(to: Path, dry: bool, said: list) -> None:
    _drop_legacy(to.parent, dry, said)
    if to.exists() and _files(to) == _files(SKILL):
        said.append(f"  skill already at {to}")
        return
    said.append(f"  skill -> {to}")
    if not dry:
        shutil.rmtree(to, ignore_errors=True)
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SKILL, to)


def install_claude(home: Path, dry: bool, said: list) -> None:
    said.append("Claude Code:")
    finder = lookup()
    found = finder.check(finder.find("claude", override_vars=("FORMLIT_CLAUDE_BIN",), home=home))
    claude = found.path if found.state == "runs" else None
    if claude:
        env = finder.child_env(claude, home=home)
        have = finder.run([claude, "mcp", "get", "formlit"], env, 60)
        if have.returncode == 0 and LAUNCH in have.stdout:
            said.append("  MCP server formlit already set (user scope)")
        else:
            said.append(f"  claude mcp add --scope user formlit -- {LAUNCH} mcp")
            if not dry:
                if have.returncode == 0:
                    finder.run([claude, "mcp", "remove", "formlit", "--scope", "user"], env, 60)
                finder.run([claude, "mcp", "add", "--scope", "user", "formlit", "--", LAUNCH, "mcp"], env, 60).check_returncode()
    else:
        said.append(f"  {finder.sentence(found, finder.install('claude'))} Once it runs: claude mcp add --scope user formlit -- {LAUNCH} mcp")
    _copy_skill(home / ".claude" / "skills" / NAME, dry, said)


def install_codex(home: Path, dry: bool, said: list) -> None:
    said.append("Codex:")
    cfg = Path(os.environ.get("CODEX_HOME", home / ".codex")) / "config.toml"
    block = f'[mcp_servers.formlit]\ncommand = {json.dumps(LAUNCH)}\nargs = ["mcp"]\nstartup_timeout_sec = 90\ntool_timeout_sec = 3600\n'
    text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
    found = re.search(r"(?ms)^\[mcp_servers\.formlit\]\n.*?(?=^\[|\Z)", text)
    if found and found.group(0).strip() == block.strip():
        said.append(f"  MCP server formlit already in {cfg}")
    else:
        said.append(f"  MCP server formlit -> {cfg}")
        if not dry:
            _backup(cfg, dry)
            cfg.parent.mkdir(parents=True, exist_ok=True)
            new = text[:found.start()] + block + "\n" + text[found.end():] if found else (text.rstrip("\n") + "\n\n" if text.strip() else "") + block
            cfg.write_text(new, encoding="utf-8")
    _copy_skill(home / ".agents" / "skills" / NAME, dry, said)


def install_cursor(home: Path, dry: bool, said: list) -> None:
    said.append("Cursor:")
    cfg = home / ".cursor" / "mcp.json"
    data = json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() and cfg.read_text(encoding="utf-8").strip() else {}
    entry = {"command": LAUNCH, "args": ["mcp"]}
    if data.get("mcpServers", {}).get("formlit") == entry:
        said.append(f"  MCP server formlit already in {cfg}")
    else:
        said.append(f"  MCP server formlit -> {cfg}")
        if not dry:
            _backup(cfg, dry)
            data.setdefault("mcpServers", {})["formlit"] = entry
            cfg.parent.mkdir(parents=True, exist_ok=True)
            cfg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _copy_skill(home / ".agents" / "skills" / NAME, dry, said)


def _ours(entry: object) -> bool:
    return isinstance(entry, dict) and entry.get("args") == ["mcp"] and Path(str(entry.get("command", ""))).name == Path(LAUNCH).name


def install_antigravity(home: Path, dry: bool, said: list) -> None:
    said.append("Antigravity:")
    cfg = home / ".gemini" / "config" / "mcp_config.json"
    older = home / ".gemini" / "antigravity-cli" / "mcp_config.json"
    if older.exists() and not cfg.exists():
        said.append(f"  an older file was seen at {older} and left alone; the documented file is {cfg}")
    try:
        data = json.loads(cfg.read_text(encoding="utf-8") or "{}") if cfg.exists() else {}
    except ValueError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("mcpServers", {}), dict):
        said.append(f"  {cfg} is not an MCP servers file formlit can read; left alone")
        return
    entry = {"command": LAUNCH, "args": ["mcp"]}
    have = data.get("mcpServers", {}).get("formlit")
    if have == entry:
        said.append(f"  MCP server formlit already in {cfg}")
    elif have is not None and not _ours(have):
        said.append(f"  {cfg} has a server named formlit that formlit did not write; left alone")
    else:
        said.append(f"  MCP server formlit -> {cfg}")
        if not dry:
            _backup(cfg, dry)
            data.setdefault("mcpServers", {})["formlit"] = entry
            cfg.parent.mkdir(parents=True, exist_ok=True)
            part = cfg.with_name(cfg.name + f".part-{os.getpid()}")
            part.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            os.replace(part, cfg)


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "install"
    rest = argv[1:]
    if cmd == "sync":
        return sync("--check" in rest)
    if cmd == "install":
        dry = "--dry-run" in rest
        which = [a for a in rest if not a.startswith("--")] or ["claude", "codex", "cursor", "antigravity"]
        bad = [w for w in which if w not in ("claude", "codex", "cursor", "antigravity")]
        if bad:
            print(f"agents: unknown client {', '.join(bad)} (claude, codex, cursor or antigravity)", file=sys.stderr)
            return 2
        home, said = Path(os.environ.get("HOME", str(Path.home()))), []
        for w in which:
            {"claude": install_claude, "codex": install_codex, "cursor": install_cursor, "antigravity": install_antigravity}[w](home, dry, said)
        print(("Would do (dry run):\n" if dry else "") + "\n".join(said))
        if not dry:
            print("\nRestart the clients, then ask one to cull or develop your photos. The engine starts on the first call, and formlit asks in its window whether to allow outside agents (change it later in Preferences, AI agents).")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
