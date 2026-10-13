#!/usr/bin/env python3
"""formlit.bat claude: Claude Code in this terminal with formlit's MCP tools attached (the Windows twin of ./formlit claude)."""

import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def config() -> str:
    server = {"type": "stdio", "command": sys.executable, "args": [os.path.join(ROOT, "setup", "mcp_stdio.py")]}
    return json.dumps({"mcpServers": {"formlit": server}})


def main(argv: list[str]) -> int:
    claude = shutil.which("claude")
    if not claude:
        print("[formlit] Claude Code is not installed: https://claude.com/claude-code", file=sys.stderr)
        return 1
    if "--print-config" in argv:
        print(config())
        return 0
    return subprocess.call([claude, "--mcp-config", config(), "--allowedTools", "mcp__formlit", *argv])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
