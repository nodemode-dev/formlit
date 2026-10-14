import asyncio
import importlib
import threading

from app.engine import catalog as catalog_mod
from app.engine import events

COMMAND_MODULES = [
    "app.engine.cmd_library",
    "app.engine.cmd_develop",
    "app.engine.presets",
    "app.engine.cmd_ai",
    "app.engine.cmd_search",
    "app.engine.cmd_retouch",
    "app.engine.cmd_sessions",
    "app.engine.cmd_output",
    "app.engine.agents",
    "app.engine.cmd_terminal",
    "app.engine.cmd_analyze",
    "app.engine.cmd_workflow",
    "app.engine.cmd_templates",
    "app.engine.cmd_captions",
    "app.engine.cmd_layers",
    "app.engine.cmd_color",
    "app.engine.cmd_chat",
    "app.engine.claude_code",
]


def load_commands() -> None:
    for name in COMMAND_MODULES:
        importlib.import_module(name)


def _warm() -> None:
    try:
        from app.develop import kernel
        kernel.warm()
        events.publish("engine", state="kernel-ready")
    except Exception as exc:
        events.publish("engine", state="kernel-failed", error=str(exc))


def _restore_catalog() -> None:
    import os
    from pathlib import Path
    from app.core import prefs
    last = prefs.load().get("catalog")
    if last and not os.environ.get("FORMLIT_CATALOG") and Path(last).is_file():
        os.environ["FORMLIT_CATALOG"] = last


async def start() -> None:
    events.bind(asyncio.get_running_loop())
    load_commands()
    _restore_catalog()
    catalog_mod.get()
    from app.services import watch, xmpwrite
    watch.restart()
    xmpwrite.start()
    threading.Thread(target=_warm, name="formlit-kernel", daemon=True).start()


async def stop() -> None:
    from app.services import watch
    watch.stop()
    catalog_mod.get().close()
