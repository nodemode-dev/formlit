import json
import os
import shlex
import subprocess
import threading
import time
from typing import Any

from app.engine import claude_code, events, terminal
from app.engine.commands import CommandError, command

NOTE = (claude_code.NOTE + " You are answering in formlit's Chat tab, not a terminal: reply in short plain sentences without markdown tables, "
        "say what you changed in photographer's words, and keep tool calls few by batching values.")
MAX_MESSAGES = 200
HIDDEN = {"ToolSearch"}
_lock = threading.Lock()
STATE: dict[str, Any] = {"session": None, "proc": None, "busy": False, "messages": [], "turn": 0}


def _publish(kind: str, **data: Any) -> None:
    events.publish(f"chat.{kind}", turn=STATE["turn"], **data)


def _tool_name(name: str) -> str:
    return name.split("__")[-1] if name.startswith("mcp__") else name


def _brief(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return text if len(text) <= 160 else text[:157] + "..."


def _argv(path: str, text: str, session: str | None) -> list[str]:
    cmd = [path, "-p", text, "--output-format", "stream-json", "--verbose", "--include-partial-messages",
           "--mcp-config", claude_code.mcp_config(), "--allowedTools", "mcp__formlit", "--append-system-prompt", NOTE]
    if session:
        cmd += ["--resume", session]
    return cmd if os.name == "nt" else terminal.login_shell() + ["-c", "exec " + shlex.join(cmd)]


def _run(text: str, path: str, folder: str) -> None:
    reply: dict[str, Any] = {"role": "assistant", "parts": [], "error": "", "meta": {}}
    tail: list[str] = []
    started = time.time()
    result: dict | None = None
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
            elif t == "stream_event":
                e = ev.get("event") or {}
                d = e.get("delta") or {}
                if e.get("type") == "content_block_delta" and d.get("type") == "text_delta" and d.get("text"):
                    if not reply["parts"] or reply["parts"][-1]["kind"] != "text":
                        reply["parts"].append({"kind": "text", "text": ""})
                    reply["parts"][-1]["text"] += d["text"]
                    _publish("delta", text=d["text"])
            elif t == "assistant":
                for b in (ev.get("message") or {}).get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") not in HIDDEN:
                        part = {"kind": "tool", "id": b.get("id"), "name": _tool_name(str(b.get("name") or "")), "input": _brief(b.get("input") or {}), "status": "running"}
                        reply["parts"].append(part)
                        _publish("tool", **{k: part[k] for k in ("id", "name", "input")})
            elif t == "user":
                for b in (ev.get("message") or {}).get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_result" and any(p["kind"] == "tool" and p["id"] == b.get("tool_use_id") for p in reply["parts"]):
                        status = "error" if b.get("is_error") else "done"
                        for p in reply["parts"]:
                            if p["kind"] == "tool" and p["id"] == b.get("tool_use_id"):
                                p["status"] = status
                        _publish("toolDone", id=b.get("tool_use_id"), status=status)
            elif t == "result":
                result = ev
                STATE["session"] = ev.get("session_id") or STATE["session"]
        proc.wait(timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        reply["error"] = f"Claude Code could not run: {e}"
    finally:
        STATE["proc"] = None
    if result is None and not reply["error"]:
        reply["error"] = "Claude Code stopped before answering" + (f": {tail[-1]}" if tail else "") if STATE.get("cancelled") is not True else "Stopped"
    elif result is not None and result.get("is_error"):
        reply["error"] = str(result.get("result") or result.get("subtype") or "Claude Code reported an error")
    reply["meta"] = {"seconds": round(time.time() - started, 1), "turns": (result or {}).get("num_turns"), "costUsd": (result or {}).get("total_cost_usd")}
    with _lock:
        STATE["messages"].append(reply)
        del STATE["messages"][:-MAX_MESSAGES]
        STATE["busy"] = False
        STATE["cancelled"] = False
    _publish("done", error=reply["error"], meta=reply["meta"])


@command("chat.state", "Chat", mutates=False, description="The Chat tab's conversation so far and whether Claude Code is answering. The window only.")
def state() -> dict:
    return {"busy": STATE["busy"], "messages": STATE["messages"], "session": bool(STATE["session"]), "turn": STATE["turn"]}


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
    _publish("reset")
    return {"reset": True}
