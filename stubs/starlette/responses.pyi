"""Type stubs for starlette.responses — covers only the API surface used by minirag."""

from collections.abc import Iterator
from typing import Any

class StreamingResponse:
    status_code: int
    headers: dict[str, str]

    def __init__(
        self,
        content: Iterator[str],
        *,
        status_code: int = ...,
        headers: dict[str, str] | None = ...,
        media_type: str = ...,
        **kwargs: Any,
    ) -> None: ...
