#!/usr/bin/env python3
"""./formlit agents: formlit for Claude Code, Codex and Cursor.

  sync [--check]            regenerate the driving skill's tool and preset references from the engine and mirror the
                            skill from .claude/skills to .agents/skills; --check exits 1 when either has drifted
  install [--dry-run] [claude|codex|cursor ...]
                            register the MCP server (./formlit mcp at this folder's absolute path) and the driving skill
                            for this user account (all three by default); files are backed up before they change.
                            This is the developer path; everyone else adds the formlit plugin from the Form marketplace.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "formlit-driving"
LEGACY = "formlit-editing"
SKILL = ROOT / ".claude" / "skills" / NAME
MIRROR = ROOT / ".agents" / "skills" / NAME
LAUNCH = str(ROOT / ("formlit.bat" if os.name == "nt" else "formlit"))
GROUPS = [
    ("Look", ["get_catalog", "find_photos", "get_photo", "get_preview", "analyze_photo", "get_develop", "get_develop_controls", "list_presets", "list_people", "list_export_presets"]),
    ("Import and organize", ["import_photos", "set_rating", "set_flag", "set_label", "add_keywords", "set_metadata", "set_location", "create_collection", "add_to_collection", "stack_photos"]),
    ("Cull and people", ["analyze_culling", "apply_culling", "refine_photos", "find_faces", "name_person"]),
    ("Develop", ["develop_set", "develop_patch", "match_look", "match_exposures", "virtual_copy", "snapshot", "auto_tone", "auto_white_balance", "reset_develop", "apply_preset", "save_preset", "sync_settings", "add_ai_mask", "add_gradient_mask", "auto_straighten", "upright"]),
    ("Enhance and merge", ["denoise", "super_resolution", "merge_hdr", "merge_panorama"]),
    ("Output", ["export_photos", "print_pdf", "make_book", "export_slideshow", "export_web_gallery", "publish"]),
    ("Window, history and everything else", ["show_in_window", "undo", "redo", "list_commands", "run_command", "get_agent_access"]),
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
    items = [{"id": f"builtin:{presets._slug(p['group'])}/{presets._slug(p['name'])}", **p} for p in presets.BUILTIN]
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


def _files(folder: Path) -> dict:
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def sync(check: bool) -> int:
    drift = []
    for ref, want in ((SKILL / "references" / "tools.md", tools_reference()), (SKILL / "references" / "presets.md", presets_reference())):
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
    claude = shutil.which("claude")
    if claude:
        have = subprocess.run([claude, "mcp", "get", "formlit"], capture_output=True, text=True)
        if have.returncode == 0 and LAUNCH in have.stdout:
            said.append("  MCP server formlit already set (user scope)")
        else:
            said.append(f"  claude mcp add --scope user formlit -- {LAUNCH} mcp")
            if not dry:
                if have.returncode == 0:
                    subprocess.run([claude, "mcp", "remove", "formlit", "--scope", "user"], capture_output=True)
                subprocess.run([claude, "mcp", "add", "--scope", "user", "formlit", "--", LAUNCH, "mcp"], check=True, capture_output=True)
    else:
        said.append(f"  the claude command is not installed here; once it is, run: claude mcp add --scope user formlit -- {LAUNCH} mcp")
    _copy_skill(home / ".claude" / "skills" / NAME, dry, said)


def install_codex(home: Path, dry: bool, said: list) -> None:
    said.append("Codex:")
    cfg = Path(os.environ.get("CODEX_HOME", home / ".codex")) / "config.toml"
    block = f'[mcp_servers.formlit]\ncommand = "{LAUNCH}"\nargs = ["mcp"]\nstartup_timeout_sec = 90\ntool_timeout_sec = 3600\n'
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


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "install"
    rest = argv[1:]
    if cmd == "sync":
        return sync("--check" in rest)
    if cmd == "install":
        dry = "--dry-run" in rest
        which = [a for a in rest if not a.startswith("--")] or ["claude", "codex", "cursor"]
        bad = [w for w in which if w not in ("claude", "codex", "cursor")]
        if bad:
            print(f"agents: unknown client {', '.join(bad)} (claude, codex or cursor)", file=sys.stderr)
            return 2
        home, said = Path(os.environ.get("HOME", str(Path.home()))), []
        for w in which:
            {"claude": install_claude, "codex": install_codex, "cursor": install_cursor}[w](home, dry, said)
        print(("Would do (dry run):\n" if dry else "") + "\n".join(said))
        if not dry:
            print("\nRestart the clients, then ask one to cull or develop your photos. The engine starts on the first call, and formlit asks in its window whether to allow outside agents (change it later in Preferences, AI agents).")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
