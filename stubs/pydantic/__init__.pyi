"""Type stubs for pydantic v2 — covers only the API surface used by minirag."""

from collections.abc import Callable
from typing import Any, ClassVar, Self, TypeVar

_F = TypeVar("_F", bound=Callable[..., Any])

class ConfigDict:
    def __init__(self, *, extra: str = ..., **kwargs: Any) -> None: ...

class BaseModel:
    model_config: ClassVar[ConfigDict]

    def __init__(self, **kwargs: Any) -> None: ...
    def model_dump(self) -> dict[str, Any]: ...

    @classmethod
    def model_validate(cls, obj: Any) -> Self: ...

class ValidationError(ValueError): ...

def field_validator(__field: str, *fields: str, mode: str = ...) -> Callable[[_F], _F]: ...

