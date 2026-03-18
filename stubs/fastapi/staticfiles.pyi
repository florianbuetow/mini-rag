"""Type stubs for fastapi.staticfiles — covers only the API surface used by minirag."""

from typing import Any

class StaticFiles:
    def __init__(self, *, directory: str, html: bool = ..., **kwargs: Any) -> None: ...
    async def __call__(self, scope: Any, receive: Any, send: Any) -> None: ...
