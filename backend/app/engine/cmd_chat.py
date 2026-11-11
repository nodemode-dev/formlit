import base64
import json
import os
import shlex
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from app.core import config
from app.engine import claude_code, events, terminal
from app.engine.commands import CommandError, command

NOTE = (claude_code.NOTE + " You are answering in formlit's Chat tab, which shows Markdown to people who may never have used a terminal: "
        "write short paragraphs, use **bold** for setting names and a bulleted list when you changed several things, avoid tables and code blocks, "
        "say what you changed in photographer's words, and keep tool calls few by batching values.")
MAX_MESSAGES = 200
HIDDEN = {"ToolSearch"}
_lock = threading.Lock()


def _blank_usage() -> dict:
    return {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "costUsd": 0.0, "context": 0, "window": 0, "model": ""}


STATE: dict[str, Any] = {"session": None, "proc": None, "busy": False, "messages": [], "turn": 0, "usage": _blank_usage()}


def _publish(kind: str, **data: Any) -> None:
    events.publish(f"chat.{kind}", turn=STATE["turn"], **data)


def _tool_name(name: str) -> str:
    return name.split("__")[-1] if name.startswith("mcp__") else name


def _photos(args: Any) -> list[int]:
    out: list[int] = []
    if isinstance(args, dict):
        for key in ("id", "ids", "reference", "from", "photo"):
            v = args.get(key)
            for x in v if isinstance(v, list) else [v]:
                if isinstance(x, int) and not isinstance(x, bool) and x not in out:
                    out.append(x)
    return out[:200]


def _brief(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return text if len(text) <= 160 else text[:157] + "..."


def _save_image(block: dict) -> str | None:
    src = block.get("source") or {}
    if src.get("type") != "base64" or not src.get("data"):
        return None
    ext = {"image/png": "png", "image/webp": "webp"}.get(str(src.get("media_type")), "jpg")
    folder = config.data_dir() / "Chat"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{uuid.uuid4().hex}.{ext}"
        path.write_bytes(base64.b64decode(src["data"]))
    except (OSError, ValueError):
        return None
    return str(path)


def _usage_of(u: dict) -> tuple[int, int]:
    context = int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0) + int(u.get("cache_read_input_tokens") or 0)
    return context, int(u.get("output_tokens") or 0)


def _argv(path: str, text: str, session: str | None) -> list[str]:
    cmd = [path, "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
           "--mcp-config", claude_code.mcp_config(), "--allowedTools", "mcp__formlit", "--append-system-prompt", NOTE]
    if session:
        cmd += ["--resume", session]
    cmd += ["--", text]
    return cmd if os.name == "nt" else terminal.login_shell() + ["-c", "exec " + shlex.join(cmd)]


def _run(text: str, path: str, folder: str) -> None:
    reply: dict[str, Any] = {"role": "assistant", "parts": [], "error": "", "meta": {}}
    tail: list[str] = []
    started = time.time()
    result: dict | None = None
    done_out = 0
    call_out = 0
    usage = STATE["usage"]
    try:
        proc = subprocess.Popen(_argv(path, text, STATE["session"]), cwd=folder, env=claude_code.child_env(), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, encoding="utf-8", errors="replace")
        STATE["proc"] = proc

        def drain() -> None:
            for line in proc.stderr:
                tail.append(line.rstrip())
                del tail[:-15]
        threading.Thread(target=drain, daemon=True).start()
        for line in proc.stdout:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            t = ev.get("type")
            if ev.get("parent_tool_use_id"):
                continue
            if t == "system" and ev.get("subtype") == "init":
                STATE["session"] = ev.get("session_id") or STATE["session"]
                usage["model"] = str(ev.get("model") or usage["model"])
            elif t == "stream_event":
                e = ev.get("event") or {}
                d = e.get("delta") or {}
                if e.get("type") in ("message_start", "message_delta"):
                    u = (e.get("message") or {}).get("usage") if e.get("type") == "message_start" else e.get("usage")
                    if isinstance(u, dict):
                        context, out = _usage_of(u)
                        if e.get("type") == "message_start":
                            done_out += call_out
                            call_out = 0
                            usage["context"] = context or usage["context"]
                        else:
                            call_out = out
                        _publish("usage", context=usage["context"], window=usage["window"], output=done_out + call_out, model=usage["model"],
                                 session={k: usage[k] for k in ("input", "output", "costUsd")})
                elif e.get("type") == "content_block_delta" and d.get("type") == "text_delta" and d.get("text"):
                    if not reply["parts"] or reply["parts"][-1]["kind"] != "text":
                        reply["parts"].append({"kind": "text", "text": ""})
                    reply["parts"][-1]["text"] += d["text"]
                    _publish("delta", text=d["text"])
            elif t == "assistant":
                for b in (ev.get("message") or {}).get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") not in HIDDEN:
                        part = {"kind": "tool", "id": b.get("id"), "name": _tool_name(str(b.get("name") or "")), "input": _brief(b.get("input") or {}),
                                "photos": _photos(b.get("input")), "status": "running"}
                        reply["parts"].append(part)
                        _publish("tool", **{k: part[k] for k in ("id", "name", "input", "photos")})
            elif t == "user":
                for b in (ev.get("message") or {}).get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_result" and any(p["kind"] == "tool" and p["id"] == b.get("tool_use_id") for p in reply["parts"]):
                        status = "error" if b.get("is_error") else "done"
                        content = b.get("content") if isinstance(b.get("content"), list) else []
                        images = [p for p in (_save_image(c) for c in content if isinstance(c, dict) and c.get("type") == "image") if p]
                        for p in reply["parts"]:
                            if p["kind"] == "tool" and p["id"] == b.get("tool_use_id"):
                                p["status"] = status
                                if images:
                                    p["images"] = images
                        _publish("toolDone", id=b.get("tool_use_id"), status=status, images=images)
            elif t == "result":
                result = ev
                STATE["session"] = ev.get("session_id") or STATE["session"]
                total = ev.get("usage") or {}
                usage["input"] += int(total.get("input_tokens") or 0) + int(total.get("cache_creation_input_tokens") or 0) + int(total.get("cache_read_input_tokens") or 0)
                usage["output"] += int(total.get("output_tokens") or 0)
                usage["cacheRead"] += int(total.get("cache_read_input_tokens") or 0)
                usage["cacheWrite"] += int(total.get("cache_creation_input_tokens") or 0)
                usage["costUsd"] = round(usage["costUsd"] + float(ev.get("total_cost_usd") or 0), 6)
                per = (ev.get("modelUsage") or {}).get(usage["model"]) or {}
                usage["window"] = int(per.get("contextWindow") or usage["window"] or 0)
        proc.wait(timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        reply["error"] = f"Claude Code could not run: {e}"
    finally:
        STATE["proc"] = None
    if result is None and not reply["error"]:
        reply["error"] = "Claude Code stopped before answering" + (f": {tail[-1]}" if tail else "") if STATE.get("cancelled") is not True else "Stopped"
    elif result is not None and result.get("is_error"):
        reply["error"] = str(result.get("result") or result.get("subtype") or "Claude Code reported an error")
    tokens = (result or {}).get("usage") or {}
    reply["meta"] = {"seconds": round(time.time() - started, 1), "turns": (result or {}).get("num_turns"), "costUsd": (result or {}).get("total_cost_usd"),
                     "inputTokens": _usage_of(tokens)[0], "outputTokens": int(tokens.get("output_tokens") or 0), "context": usage["context"], "window": usage["window"]}
    with _lock:
        STATE["messages"].append(reply)
        del STATE["messages"][:-MAX_MESSAGES]
        STATE["busy"] = False
        STATE["cancelled"] = False
    _publish("done", error=reply["error"], meta=reply["meta"], usage=dict(usage))


@command("chat.state", "Chat", mutates=False, description="The Chat tab's conversation so far and whether Claude Code is answering. The window only.")
def state() -> dict:
    return {"busy": STATE["busy"], "messages": STATE["messages"], "session": STATE["session"] or "", "turn": STATE["turn"], "usage": STATE["usage"]}


@command("chat.send", "Ask in Chat", {"text": {"type": "string"}, "context": {"type": "string", "description": "what the window adds for Claude, such as the selected photo ids"},
                                      "note": {"type": "string", "description": "a short label for the context shown under the message"}}, mutates=False,
         description="Sends a message to Claude Code from the Chat tab: it answers through claude -p with formlit's tools only, continuing the same conversation. The window only.")
def send(text: str, context: str = "", note: str = "") -> dict:
    shown = str(text or "").strip()
    if not shown:
        raise CommandError("Type a message first")
    text = f"{shown} ({context.strip()})" if context.strip() else shown
    found = claude_code.info(fresh=True)
    if not found["installed"]:
        raise CommandError(claude_code.INSTALL, 400)
    folder = str(claude_code.workdir())
    with _lock:
        if STATE["busy"]:
            raise CommandError("Claude is still answering; wait or press Stop", 409)
        STATE["busy"] = True
        STATE["turn"] += 1
        STATE["messages"].append({"role": "user", "text": shown, "note": note.strip()})
    _publish("start", text=shown, note=note.strip())
    threading.Thread(target=_run, args=(text, found["path"], folder), daemon=True).start()
    return {"turn": STATE["turn"]}


@command("chat.cancel", "Stop Chat", mutates=False, description="Stops the answer Claude Code is writing in the Chat tab. The window only.")
def cancel() -> dict:
    proc = STATE["proc"]
    if proc is not None and proc.poll() is None:
        STATE["cancelled"] = True
        proc.terminate()
    return {"stopped": proc is not None}


@command("chat.reset", "New Chat", mutates=False, description="Starts a new conversation in the Chat tab, stopping any answer in progress. The window only.")
def reset() -> dict:
    cancel()
    with _lock:
        STATE["session"] = None
        STATE["messages"] = []
        STATE["turn"] += 1
        STATE["usage"] = _blank_usage()
    _publish("reset")
    return {"reset": True}


def _project_dir(folder: str) -> Path:
    root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()
    return root / "projects" / "".join(ch if ch.isalnum() else "-" for ch in folder)


def _transcript(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        msg = ev.get("message") or {}
        if ev.get("type") not in ("user", "assistant") or ev.get("isSidechain") or ev.get("isMeta"):
            continue
        content = msg.get("content")
        texts = [content] if isinstance(content, str) else [b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text"]
        tools = [b for b in content or [] if isinstance(b, dict) and b.get("type") == "tool_use"] if isinstance(content, list) else []
        text = "\n\n".join(t for t in texts if t and not t.startswith("<"))
        if ev["type"] == "user" and text:
            out.append({"role": "user", "text": text, "note": "from Claude Code"})
        elif ev["type"] == "assistant" and (text or tools):
            parts = [{"kind": "tool", "id": b.get("id"), "name": _tool_name(str(b.get("name") or "")), "input": _brief(b.get("input") or {}),
                      "photos": _photos(b.get("input")), "status": "done"} for b in tools if b.get("name") not in HIDDEN]
            if text:
                parts.append({"kind": "text", "text": text})
            if out and out[-1]["role"] == "assistant":
                out[-1]["parts"] += parts
            elif parts:
                out.append({"role": "assistant", "parts": parts, "error": "", "meta": {}})
    return out[-MAX_MESSAGES:]


@command("chat.sessions", "Claude Code Conversations", mutates=False,
         description="The Claude Code conversations started in formlit's agent folder, newest first, so the Chat tab can continue one. The window only.")
def sessions() -> dict:
    folder = _project_dir(str(claude_code.workdir()))
    items = []
    for f in sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
        first = next((m["text"] for m in _transcript(f) if m["role"] == "user"), "")
        items.append({"id": f.stem, "modified": f.stat().st_mtime, "title": first[:90], "current": f.stem == STATE["session"]})
    return {"sessions": items, "folder": str(folder)}


@command("chat.adopt", "Continue a Conversation in Chat", {"session": {"type": "string", "description": "a session id from chat.sessions; the newest when left out"}}, mutates=False,
         description="Brings a Claude Code conversation into the Chat tab: its messages are shown and the next message continues it. The window only.")
def adopt(session: str = "") -> dict:
    if STATE["busy"]:
        raise CommandError("Claude is still answering; wait or press Stop", 409)
    listed = sessions()["sessions"]
    pick = next((s for s in listed if s["id"] == session), None) if session else (listed[0] if listed else None)
    if pick is None:
        raise CommandError("No Claude Code conversation was found in formlit's agent folder yet", 404)
    messages = _transcript(_project_dir(str(claude_code.workdir())) / f"{pick['id']}.jsonl")
    with _lock:
        STATE["session"] = pick["id"]
        STATE["messages"] = messages
        STATE["turn"] += 1
        STATE["usage"] = _blank_usage()
    _publish("adopted", session=pick["id"], count=len(messages))
    return {"session": pick["id"], "messages": len(messages)}
