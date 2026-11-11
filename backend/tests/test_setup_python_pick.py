"""Which Python makes backend/venv (0.48.0). On an Intel Mac, onnxruntime and rawpy publish no wheels for Python 3.14,
so the venv must come from 3.12 or 3.13. 0.47.9 taught setup/lib.sh's fl_python that rule, but backend/oc_install (what
`./formlit install` runs) kept its own picker and still made the venv with python3.14, so the Intel build failed on
rawpy==0.25.1. These tests fake `uname` and three Pythons on PATH and run the real scripts."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(os.name == "nt" or shutil.which("bash") is None, reason="bash scripts")

FAKE_PYTHON = """#!/bin/sh
# A stand-in Python {minor} built for {arch}: answers `-c` with version_info 3.{minor} and platform.machine() {arch},
# makes a recording venv for `-m venv`.
if [ "$1" = -c ]; then
  exec "{real}" -c "import platform, sys; sys.version_info = (3, {minor}, 0, 'final', 0); platform.machine = lambda: '{arch}'; exec(sys.argv[1])" "$2"
fi
if [ "$1" = -V ]; then echo "Python 3.{minor}.0"; exit 0; fi
if [ "$1" = -m ] && [ "$2" = venv ]; then
  mkdir -p "$3/bin"
  echo "3.{minor}" > "$3/made-by"
  cp "$0" "$3/bin/python"
  printf 'python() {{ :; }}\\npip() {{ echo "$*" >> "$VIRTUAL_ENV_LOG"; }}\\n' > "$3/bin/activate"
  exit 0
fi
exit 1
"""


def fake_bin(tmp_path: Path, machine: str, system: str, minors: tuple[int, ...], arches: dict[int, str] | None = None,
             apple_silicon: bool | None = None) -> Path:
    bin_dir = tmp_path / "bin"
    shutil.rmtree(bin_dir, ignore_errors=True)
    bin_dir.mkdir()
    uname = bin_dir / "uname"
    uname.write_text(f'#!/bin/sh\ncase "$1" in -m) echo {machine} ;; *) echo {system} ;; esac\n')
    uname.chmod(0o755)
    sysctl = bin_dir / "sysctl"
    arm = machine == "arm64" if apple_silicon is None else apple_silicon
    sysctl.write_text(f'#!/bin/sh\n[ "$2" = hw.optional.arm64 ] && echo {1 if arm else 0}\n')
    sysctl.chmod(0o755)
    # Hide the machine's own Pythons (Ubuntu has /usr/bin/python3 and python3.12) behind stubs that fail.
    for name in ("python3", "python", *(f"python3.{m}" for m in range(10, 16) if m not in minors)):
        stub = bin_dir / name
        stub.write_text("#!/bin/sh\nexit 1\n")
        stub.chmod(0o755)
    for minor in minors:
        exe = bin_dir / f"python3.{minor}"
        exe.write_text(FAKE_PYTHON.format(minor=minor, real=sys.executable, arch=(arches or {}).get(minor, machine)))
        exe.chmod(0o755)
    return bin_dir


def env_with(bin_dir: Path, tmp_path: Path) -> dict[str, str]:
    return {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path), "VIRTUAL_ENV_LOG": str(tmp_path / "pip.log")}


def pick(tmp_path: Path, machine: str, system: str, minors: tuple[int, ...] = (14, 13, 12),
         arches: dict[int, str] | None = None, apple_silicon: bool | None = None) -> str:
    bin_dir = fake_bin(tmp_path, machine, system, minors, arches, apple_silicon)
    out = subprocess.run(["bash", "-c", f'source "{ROOT}/setup/lib.sh"; fl_python'], env=env_with(bin_dir, tmp_path),
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def test_apple_silicon_skips_an_intel_python_3_14(tmp_path):
    """0.51.3: an x86_64 python3.14 (uv's build) on an arm64 shell passed the shell's check and failed on rawpy."""
    assert pick(tmp_path, "arm64", "Darwin", arches={14: "x86_64"}) == "python3.13"


def test_apple_silicon_prefers_a_native_python(tmp_path):
    assert pick(tmp_path, "arm64", "Darwin", (13, 12), arches={13: "x86_64"}) == "python3.12"


def test_apple_silicon_with_only_an_intel_python_takes_it_up_to_3_13(tmp_path):
    assert pick(tmp_path, "arm64", "Darwin", arches={14: "x86_64", 13: "x86_64", 12: "x86_64"}) == "python3.13"


def test_a_rosetta_shell_on_apple_silicon_still_takes_a_native_python_3_14(tmp_path):
    assert pick(tmp_path, "x86_64", "Darwin", arches={14: "arm64", 13: "arm64", 12: "arm64"}, apple_silicon=True) == "python3.14"


def test_an_intel_mac_skips_python_3_14(tmp_path):
    assert pick(tmp_path, "x86_64", "Darwin") == "python3.13"


@pytest.mark.parametrize(("machine", "system"), [("arm64", "Darwin"), ("x86_64", "Linux"), ("aarch64", "Linux")])
def test_other_machines_still_take_python_3_14(tmp_path, machine, system):
    assert pick(tmp_path, machine, system) == "python3.14"


def run_oc_install(tmp_path: Path, machine: str, system: str, minors: tuple[int, ...]) -> subprocess.CompletedProcess:
    tree = tmp_path / "tree"
    (tree / "backend").mkdir(parents=True, exist_ok=True)
    (tree / "setup").mkdir(exist_ok=True)
    shutil.copy(ROOT / "backend" / "oc_install", tree / "backend" / "oc_install")
    shutil.copy(ROOT / "setup" / "lib.sh", tree / "setup" / "lib.sh")
    bin_dir = fake_bin(tmp_path, machine, system, minors)
    return subprocess.run(["bash", str(tree / "backend" / "oc_install")], env=env_with(bin_dir, tmp_path),
                          capture_output=True, text=True)


def test_install_makes_the_intel_mac_venv_with_python_3_13(tmp_path):
    done = run_oc_install(tmp_path, "x86_64", "Darwin", (14, 13, 12))
    assert done.returncode == 0, done.stderr
    assert (tmp_path / "tree/backend/venv/made-by").read_text().strip() == "3.13"
    assert "install -r requirements" in (tmp_path / "pip.log").read_text()


def test_install_makes_the_apple_silicon_venv_with_python_3_14(tmp_path):
    done = run_oc_install(tmp_path, "arm64", "Darwin", (14, 13, 12))
    assert done.returncode == 0, done.stderr
    assert (tmp_path / "tree/backend/venv/made-by").read_text().strip() == "3.14"


def test_install_replaces_an_intel_mac_venv_made_with_python_3_14(tmp_path):
    first = run_oc_install(tmp_path, "arm64", "Darwin", (14,))
    assert first.returncode == 0, first.stderr
    (tmp_path / "tree/backend/venv/bin/python").write_text(FAKE_PYTHON.format(minor=14, real=sys.executable, arch="x86_64"))
    again = run_oc_install(tmp_path, "x86_64", "Darwin", (14, 12))
    assert again.returncode == 0, again.stderr
    assert (tmp_path / "tree/backend/venv/made-by").read_text().strip() == "3.12"
    assert "recreating it" in again.stdout


def test_an_intel_mac_with_only_python_3_14_is_told_why(tmp_path):
    done = run_oc_install(tmp_path, "x86_64", "Darwin", (14,))
    assert done.returncode != 0
    assert "3.12 or 3.13 on Intel Macs" in done.stderr


def test_every_shell_venv_comes_from_fl_python():
    """No script makes a venv with its own Python list again: each `-m venv` line uses a fl_python result."""
    offenders = []
    for path in [ROOT / "build_app", ROOT / "formlit", *ROOT.glob("setup/*"), *ROOT.glob("backend/*")]:
        if not path.is_file() or path.suffix in {".bat", ".py", ".txt", ".md", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "-m venv" in text and "fl_python" not in text:
            offenders.append(path.name)
    assert not offenders, offenders
