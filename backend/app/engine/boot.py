import asyncio
import importlib
import threading

from app.engine import catalog as catalog_mod
from app.engine import events

COMMAND_MODULES = [
    "app.engine.cmd_library",
    "app.engine.cmd_develop",
    "app.engine.presets",
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


async def start() -> None:
    events.bind(asyncio.get_running_loop())
    load_commands()
    catalog_mod.get()
    threading.Thread(target=_warm, name="formlit-kernel", daemon=True).start()


async def stop() -> None:
    catalog_mod.get().close()
