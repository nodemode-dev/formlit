#!/usr/bin/env bash
FORMLIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export FORMLIT_ROOT
fl_say() { printf '[formlit] %s\n' "$*"; }
fl_die() { printf '[formlit] error: %s\n' "$*" >&2; exit 1; }
fl_os() {
  case "$(uname -s 2>/dev/null)" in
    Darwin) echo macos ;;
    Linux) echo linux ;;
    MINGW*|MSYS*|CYGWIN*) echo windows ;;
    *) echo unknown ;;
  esac
}
fl_python() {
  local c
  for c in python3.14 python3.13 python3.12 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
      echo "$c"
      return 0
    fi
  done
  return 1
}
fl_venv() {
  [ -f "$FORMLIT_ROOT/backend/venv/bin/activate" ] || fl_die "engine venv missing, run ./formlit install"
  # shellcheck disable=SC1091
  source "$FORMLIT_ROOT/backend/venv/bin/activate"
}
fl_target_triple() {
  if [ -n "${FORMLIT_TARGET:-}" ]; then echo "$FORMLIT_TARGET"; return 0; fi
  command -v rustc >/dev/null 2>&1 || return 1
  rustc -vV | awk '/^host:/ {print $2}'
}
fl_exe() { [ "$(fl_os)" = windows ] && echo ".exe" || echo ""; }
