"""Type stubs for strands — covers only the API surface used by minirag."""

from collections.abc import AsyncIterator, Callable
from typing import Any, overload

class DecoratedFunctionTool:
    """Opaque handle for a @tool-decorated function."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

@overload
def tool(__func: Callable[..., Any], /) -> DecoratedFunctionTool: ...
@overload
def tool(
    description: str | None = ...,
    inputSchema: dict[str, Any] | None = ...,
    name: str | None = ...,
    context: bool | str = ...,
) -> Callable[[Callable[..., Any]], DecoratedFunctionTool]: ...

class Agent:
    def __init__(
        self,
        *,
        model: Any = ...,
        system_prompt: str = ...,
        tools: list[Any] | None = ...,
        **kwargs: Any,
    ) -> None: ...
    def __call__(self, prompt: str) -> Any: ...
    def stream_async(self, prompt: str) -> AsyncIterator[dict[str, Any]]: ...
