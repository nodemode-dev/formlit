from app.engine import boot, terminal
from app.routers import commands, events, extensions, faces, files, mcp, output, photos, system, terminal_socket

ROUTERS = [system.router, commands.router, photos.router, events.router, files.router, faces.router, output.router, mcp.router, terminal_socket.router, extensions.router]
STARTUP = [boot.start, terminal.start]
SHUTDOWN = [terminal.stop, boot.stop]


async def startup() -> None:
    for hook in STARTUP:
        await hook()


async def shutdown() -> None:
    for hook in SHUTDOWN:
        await hook()
