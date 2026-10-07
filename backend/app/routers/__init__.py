from app.routers import system

ROUTERS = [system.router]
STARTUP = []
SHUTDOWN = []


async def startup() -> None:
    for hook in STARTUP:
        await hook()


async def shutdown() -> None:
    for hook in SHUTDOWN:
        await hook()
