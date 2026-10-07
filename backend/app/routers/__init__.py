from app.engine import boot
from app.routers import commands, events, faces, files, output, photos, system

ROUTERS = [system.router, commands.router, photos.router, events.router, files.router, faces.router, output.router]
STARTUP = [boot.start]
SHUTDOWN = [boot.stop]


async def startup() -> None:
    for hook in STARTUP:
        await hook()


async def shutdown() -> None:
    for hook in SHUTDOWN:
        await hook()
