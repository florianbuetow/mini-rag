"""Type stubs for strands.models — covers only the API surface used by minirag."""

from typing import Any

class OpenAIModel:
    def __init__(
        self,
        *,
        client_args: dict[str, Any] | None = ...,
        model_id: str = ...,
        **kwargs: Any,
    ) -> None: ...
