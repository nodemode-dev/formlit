#!/usr/bin/env python3
"""formlit.bat claude: Claude Code in this terminal with formlit's MCP tools attached (the Windows twin of ./formlit claude)."""

import importlib.util
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def config() -> str:
    server = {"type": "stdio", "command": sys.executable, "args": [os.path.join(ROOT, "setup", "mcp_stdio.py")]}
    return json.dumps({"mcpServers": {"formlit": server}})


def lookup():
    spec = importlib.util.spec_from_file_location("formlit_agent_lookup", os.path.join(ROOT, "backend", "app", "engine", "agent_lookup.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: list[str]) -> int:
    finder = lookup()
    found = finder.check(finder.find("claude", override_vars=("FORMLIT_CLAUDE_BIN",)))
    if found.state != "runs":
        print(f"[formlit] {finder.sentence(found, finder.install('claude'))}", file=sys.stderr)
        return 1
    claude = found.path
    if "--print-config" in argv:
        print(config())
        return 0
    return subprocess.call(finder.start_argv([claude, "--mcp-config", config(), "--allowedTools", "mcp__formlit", *argv]), env=finder.child_env(claude))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
