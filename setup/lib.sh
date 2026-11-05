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
# fl_python_ok EXE: EXE is a Python formlit supports here (3.12 to 3.14; 3.12 to 3.13 on Intel Macs, where
# onnxruntime and rawpy publish no wheels for 3.14).
fl_python_ok() {
  local top=14
  if [ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = x86_64 ]; then top=13; fi
  "$1" -c "import sys; raise SystemExit(0 if (3, 12) <= sys.version_info[:2] <= (3, $top) else 1)" 2>/dev/null
}
fl_python() {
  local c
  for c in python3.14 python3.13 python3.12 python3; do
    if command -v "$c" >/dev/null 2>&1 && fl_python_ok "$c"; then
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
fl_rust_env() {
  [ -d "$HOME/.cargo/bin" ] && PATH="$HOME/.cargo/bin:$PATH"
  export PATH
  unset RUSTC RUSTC_WORKSPACE_WRAPPER RUSTFLAGS CARGO_ENCODED_RUSTFLAGS CARGO_BUILD_RUSTFLAGS CARGO_BUILD_TARGET CARGO_TARGET_DIR CARGO_BUILD_TARGET_DIR CARGO_BUILD_RUSTC
  export RUSTC_WRAPPER="" CARGO_BUILD_RUSTC_WRAPPER=""
  if command -v rustup >/dev/null 2>&1 && rustup toolchain list 2>/dev/null | grep -q '^stable'; then
    export RUSTUP_TOOLCHAIN="${FORMLIT_RUST_TOOLCHAIN:-stable}"
  fi
}
fl_rust_fresh() {
  local target="$FORMLIT_ROOT/src-tauri/target" now
  now="$(rustc -vV 2>/dev/null | tr '\n' ' ')"
  if [ -d "$target/release" ] && [ "$(cat "$target/.formlit-rustc" 2>/dev/null)" != "$now" ]; then
    fl_say "the Rust compiler differs from the one that built src-tauri/target; cleaning it"
    ( cd "$FORMLIT_ROOT/src-tauri" && cargo clean )
  fi
  mkdir -p "$target"
  printf '%s' "$now" > "$target/.formlit-rustc"
}
