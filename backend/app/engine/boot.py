import asyncio
import importlib

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


async def start() -> None:
    events.bind(asyncio.get_running_loop())
    load_commands()
    catalog_mod.get()


async def stop() -> None:
    catalog_mod.get().close()
