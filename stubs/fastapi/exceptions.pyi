"""Type stubs for fastapi.exceptions — covers only the API surface used by minirag."""

from typing import Any

class RequestValidationError(Exception):
    def __init__(self, errors: Any) -> None: ...
    def errors(self) -> list[dict[str, Any]]: ...
