"""LM Studio metadata helpers."""

import logging
from collections.abc import Mapping
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)


class LMStudioModelInfo:
    """Fetch and cache LM Studio model context-window metadata."""

    def __init__(self, base_url: str, *, fallback_context_window_tokens: int, timeout_seconds: float) -> None:
        """Initialize the metadata client."""
        if fallback_context_window_tokens <= 0:
            raise ValueError("fallback_context_window_tokens must be greater than 0")
        self._api_root = api_root_from_openai_base_url(base_url)
        self._fallback_context_window_tokens = fallback_context_window_tokens
        self._timeout_seconds = timeout_seconds
        self._cache: dict[str, int] = {}

    def context_window_tokens(self, model: str) -> int:
        """Return the active model context window, falling back conservatively."""
        cached = self._cache.get(model)
        if cached is not None:
            return cached

        try:
            context_window = self._fetch_context_window_tokens(model)
        except Exception:
            logger.exception("Failed to fetch LM Studio context window for model=%s", model)
            context_window = self._fallback_context_window_tokens

        self._cache[model] = context_window
        return context_window

    def _fetch_context_window_tokens(self, model: str) -> int:
        """Fetch context-window tokens from LM Studio REST metadata endpoints."""
        with httpx.Client(base_url=self._api_root, timeout=self._timeout_seconds) as client:
            response = cast(Any, client.get("/api/v1/models"))
            if response.status_code == 404:
                return self._fetch_v0_context_window_tokens(client, model)
            response.raise_for_status()
            payload = response.json()

        context_window = context_window_from_v1_models_payload(payload, model)
        if context_window is None:
            raise ValueError(f"model context length not found in LM Studio /api/v1/models response for model={model!r}")
        return context_window

    def _fetch_v0_context_window_tokens(self, client: httpx.Client, model: str) -> int:
        """Fallback for older LM Studio REST metadata."""
        response = cast(Any, client.get("/api/v0/models"))
        response.raise_for_status()
        payload = response.json()
        context_window = context_window_from_v0_models_payload(payload, model)
        if context_window is None:
            raise ValueError(f"model context length not found in LM Studio /api/v0/models response for model={model!r}")
        return context_window


def api_root_from_openai_base_url(base_url: str) -> str:
    """Derive LM Studio server root from an OpenAI-compatible base URL."""
    stripped = base_url.rstrip("/")
    if stripped.endswith("/v1"):
        stripped = stripped[: -len("/v1")]
    return stripped + "/"


def context_window_from_v1_models_payload(payload: object, model: str) -> int | None:
    """Extract active context length from `/api/v1/models` payload."""
    if not isinstance(payload, dict):
        return None
    payload_map = cast(Mapping[str, object], payload)
    models = payload_map.get("models")
    if not isinstance(models, list):
        return None

    models_list = cast(list[object], models)
    for item in models_list:
        if not isinstance(item, dict):
            continue
        item_map = cast(Mapping[str, object], item)
        context_length = _context_window_from_v1_model_item(item_map, model)
        if context_length is not None:
            return context_length
    return None


def _context_window_from_v1_model_item(item: Mapping[str, object], model: str) -> int | None:
    """Extract context length from one `/api/v1/models` model object."""
    model_key = item.get("key")
    loaded_context_length = _context_window_from_loaded_instances(
        item.get("loaded_instances"),
        model=model,
        model_key=model_key,
    )
    if loaded_context_length is not None:
        return loaded_context_length
    if model_key != model:
        return None
    return _positive_int(item.get("max_context_length"))


def _context_window_from_loaded_instances(
    loaded_instances: object,
    *,
    model: str,
    model_key: object,
) -> int | None:
    """Extract active context length from loaded model instances."""
    if not isinstance(loaded_instances, list):
        return None
    instances = cast(list[object], loaded_instances)
    for instance in instances:
        if not isinstance(instance, dict):
            continue
        instance_map = cast(Mapping[str, object], instance)
        if instance_map.get("id") != model and model_key != model:
            continue
        config = instance_map.get("config")
        if not isinstance(config, dict):
            continue
        config_map = cast(Mapping[str, object], config)
        context_length = _positive_int(config_map.get("context_length"))
        if context_length is not None:
            return context_length
    return None


def context_window_from_v0_models_payload(payload: object, model: str) -> int | None:
    """Extract max context length from `/api/v0/models` payload."""
    if not isinstance(payload, dict):
        return None
    payload_map = cast(Mapping[str, object], payload)
    data = payload_map.get("data")
    if not isinstance(data, list):
        return None
    data_items = cast(list[object], data)
    for item in data_items:
        if not isinstance(item, dict):
            continue
        item_map = cast(Mapping[str, object], item)
        if item_map.get("id") != model:
            continue
        return _positive_int(item_map.get("max_context_length"))
    return None


def _positive_int(value: object) -> int | None:
    """Return value as a positive int when possible."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    return None
