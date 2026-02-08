"""Type stubs for fastapi.responses — covers only the API surface used by minirag."""

from typing import Any

class JSONResponse:
    status_code: int
    body: bytes

    def __init__(self, *, status_code: int = ..., content: Any = ..., **kwargs: Any) -> None: ...
