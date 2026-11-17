import base64
import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Callable

from app.core import config
from app.services.cameras import CameraError, Entry, arrived, inside, safe_name, short_id

Runner = Callable[[dict, float], dict]

SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
function Out-Json($value) { [Console]::Out.Write((ConvertTo-Json -InputObject $value -Depth 6 -Compress)) }
function Item-Name($item) {
  if (-not $item.IsFolder) { try { $n = $item.ExtendedProperty('System.FileName'); if ($n) { return [string]$n } } catch { } }
  return [string]$item.Name
}
function Safe-Name($name) {
  $text = [string]$name
  $leaf = [System.IO.Path]::GetFileName($text)
  if ([string]::IsNullOrWhiteSpace($leaf) -or $leaf -ne $text -or $leaf -match '[\\/:%]' -or $leaf.Contains('..')) { throw ('Refused a file name from the camera: ' + $text) }
  return $leaf
}
function Checked-Name($item, $wanted) {
  $name = Safe-Name (Item-Name $item)
  if ($name -ne (Safe-Name $wanted)) { throw ('The camera named the file ' + $name + ', not ' + [string]$wanted) }
  return $name
}
function Inside-Path($folder, $name) {
  $root = [System.IO.Path]::GetFullPath([string]$folder).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  $full = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($root, (Safe-Name $name)))
  if (-not $full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase) -or $full.Length -le $root.Length) { throw ('Refused a path outside the import folder: ' + $full) }
  return $full
}
function Item-Size($item) { try { return [int64]$item.ExtendedProperty('System.Size') } catch { try { return [int64]$item.Size } catch { return [int64]0 } } }
function Item-Time($item) { try { return [DateTimeOffset]::new([datetime]$item.ModifyDate).ToUnixTimeSeconds() } catch { return 0 } }
function Device-List($shell) {
  @($shell.NameSpace(17).Items() | Where-Object { -not $_.IsFileSystem -and ([string]$_.Path) -match '\\\\\?\\' })
}
function Find-Device($shell, $key) {
  foreach ($d in (Device-List $shell)) { if ([string]$d.Path -eq $key) { return $d } }
  throw 'The camera is no longer connected'
}
function Find-Child($folderItem, $name) {
  foreach ($i in $folderItem.GetFolder.Items()) { if ((Item-Name $i) -eq $name) { return $i } }
  throw ('Not on the camera: ' + $name)
}
function Resolve-Item($device, $rel) {
  $item = $device
  foreach ($part in ($rel -split '/' | Where-Object { $_ })) { $item = Find-Child $item $part }
  return $item
}
function Wait-File($path, $size, $seconds) {
  $deadline = (Get-Date).AddSeconds($seconds)
  $last = -1
  while ((Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $path) {
      $len = (Get-Item -LiteralPath $path).Length
      if (($size -gt 0 -and $len -eq $size) -or ($size -le 0 -and $len -gt 0 -and $len -eq $last)) {
        try { $fs = [System.IO.File]::Open($path, 'Open', 'Read', 'None'); $fs.Close(); return } catch { }
      }
      $last = $len
    }
    Start-Sleep -Milliseconds 250
  }
  throw ('The copy from the camera did not finish: ' + (Split-Path -Leaf $path))
}
try {
  $req = $env:FORMLIT_WPD_REQUEST | ConvertFrom-Json
  $shell = New-Object -ComObject Shell.Application
  switch ($req.op) {
    'devices' { Out-Json @(Device-List $shell | ForEach-Object { @{ name = [string]$_.Name; key = [string]$_.Path } }) }
    'list' {
      $folder = Resolve-Item (Find-Device $shell $req.device) $req.path
      $dirs = @(); $files = @()
      foreach ($i in $folder.GetFolder.Items()) {
        if ($i.IsFolder) { $dirs += (Item-Name $i) } else { $files += @{ name = (Item-Name $i); size = (Item-Size $i); mtime = (Item-Time $i) } }
      }
      Out-Json @{ dirs = $dirs; files = $files }
    }
    'get' {
      $item = Resolve-Item (Find-Device $shell $req.device) $req.path
      $name = Checked-Name $item $req.name
      $target = Inside-Path $req.dest $name
      if (Test-Path -LiteralPath $target) { throw ('Refused to overwrite ' + $name) }
      $shell.NameSpace([string]$req.dest).CopyHere($item, 0x614)
      Wait-File $target (Item-Size $item) ([int]$req.timeout)
      Out-Json @{ copied = $name }
    }
    'delete' {
      $item = Resolve-Item (Find-Device $shell $req.device) $req.path
      $name = Checked-Name $item $req.name
      $target = Inside-Path $req.dest $name
      if (Test-Path -LiteralPath $target) { throw ('Refused to overwrite ' + $name) }
      $size = Item-Size $item
      $shell.NameSpace([string]$req.dest).MoveHere($item, 0x614)
      Wait-File $target $size ([int]$req.timeout)
      Remove-Item -LiteralPath $target -Force
      Out-Json @{ deleted = $name }
    }
    default { throw ('Unknown request ' + $req.op) }
  }
} catch {
  Out-Json @{ error = [string]$_.Exception.Message }
  exit 1
}
"""


def _encoded() -> str:
    return base64.b64encode(SCRIPT.encode("utf-16-le")).decode("ascii")


def _run(request: dict, timeout: float) -> dict:
    env = dict(os.environ, FORMLIT_WPD_REQUEST=json.dumps(request))
    argv = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", _encoded()]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run(argv, capture_output=True, timeout=timeout + 30, env=env, creationflags=flags)
    except subprocess.TimeoutExpired as exc:
        raise CameraError(f"The camera did not answer within {int(timeout)} s") from exc
    except OSError as exc:
        raise CameraError(f"Windows PowerShell could not be started: {exc}") from exc
    return decode_reply(r.stdout.decode("utf-8", "replace"), r.returncode)


def decode_reply(text: str, code: int) -> dict:
    try:
        reply = json.loads(text.strip() or "null")
    except ValueError as exc:
        raise CameraError(f"The camera helper answered something unreadable: {text.strip()[:200]}") from exc
    if isinstance(reply, dict) and reply.get("error"):
        raise CameraError(str(reply["error"]))
    if code != 0:
        raise CameraError("The camera helper failed")
    return {"items": reply} if isinstance(reply, list) else reply if isinstance(reply, dict) else {"items": [] if reply is None else [reply]}


def _many(value) -> list:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


class WpdCamera:
    backend = "wpd"

    def __init__(self, name: str, key: str, run: Runner = _run):
        self.name = name
        self.key = key
        self.id = short_id("wpd", key)
        self._run = run
        self._lock = threading.Lock()

    def _ask(self, op: str, path: str, timeout: float = 120.0, **extra) -> dict:
        with self._lock:
            return self._run({"op": op, "device": self.key, "path": path, "timeout": int(timeout), **extra}, timeout)

    def list_dir(self, folder: str) -> tuple[list[str], list[Entry]]:
        reply = self._ask("list", folder)
        dirs = sorted(str(d) for d in _many(reply.get("dirs")))
        files = [Entry(str(f.get("name", "")), int(f.get("size") or 0), float(f.get("mtime") or 0), exact=bool(f.get("size")))
                 for f in _many(reply.get("files")) if isinstance(f, dict) and f.get("name")]
        return dirs, sorted(files, key=lambda e: e.name.lower())

    def fetch(self, file: str, dest: Path) -> Path:
        name = safe_name(file.rsplit("/", 1)[-1])
        dest.mkdir(parents=True, exist_ok=True)
        if inside(dest / name, dest).exists():
            raise CameraError(f"Refused to overwrite {name} while copying it from the camera")
        self._ask("get", file, 900.0, dest=str(dest), name=name)
        return arrived(dest, name)

    def delete(self, file: str) -> None:
        name = safe_name(file.rsplit("/", 1)[-1])
        scratch = config.temp_dir() / "camera-delete" / self.id
        scratch.mkdir(parents=True, exist_ok=True)
        if inside(scratch / name, scratch).exists():
            (scratch / name).unlink()
        self._ask("delete", file, 300.0, dest=str(scratch), name=name)

    def thumbnail(self, file: str) -> bytes | None:
        return None


def devices(run: Runner = _run) -> list[WpdCamera]:
    reply = run({"op": "devices"}, 30.0)
    items = reply.get("items") or []
    return [WpdCamera(str(d.get("name") or "Camera"), str(d["key"]), run) for d in items if isinstance(d, dict) and d.get("key")]
