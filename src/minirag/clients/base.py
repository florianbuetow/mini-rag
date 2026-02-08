"""Base HTTP client for mini-rag service communication."""

import logging
from typing import cast

import httpx

logger = logging.getLogger(__name__)


class BaseClient:
    """Base HTTP client with health guard and envelope parsing."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize base client with explicit host and port."""
        if host.strip() == "":
            raise ValueError("host must not be empty")

        if port <= 0:
            raise ValueError("port must be greater than 0")

        if port > 65535:
            raise ValueError("port must be less than or equal to 65535")

        self._host = host
        self._port = port
        self._base_url = f"http://{host}:{port}"

    def _as_object_map(self, value: object, context: str) -> dict[str, object]:
        """Validate and cast a generic object into a string-key object map."""
        if not isinstance(value, dict):
            raise RuntimeError(f"{context} must be a JSON object")

        typed_value = cast(dict[object, object], value)
        result: dict[str, object] = {}
        for raw_key, raw_value in typed_value.items():
            if not isinstance(raw_key, str):
                raise RuntimeError(f"{context} contains a non-string key")
            result[raw_key] = raw_value

        return result

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
        require_healthy: bool,
    ) -> dict[str, object]:
        """Send one HTTP request and return envelope data payload."""
        if require_healthy:
            self._ensure_healthy()

        with httpx.Client(base_url=self._base_url, timeout=30.0) as client:
            response = client.request(method=method, url=path, json=payload)

        try:
            raw_envelope: object = response.json()
        except Exception as exc:
            raise RuntimeError(f"invalid JSON response from {path}: {response.text}") from exc

        envelope = self._as_object_map(raw_envelope, f"response envelope from {path}")

        status_value = envelope.get("status")
        if not isinstance(status_value, int):
            raise RuntimeError(f"missing integer status in response from {path}")

        if response.status_code != status_value:
            raise RuntimeError(f"status mismatch from {path}: http={response.status_code}, envelope={status_value}")

        if response.status_code >= 400:
            error_value = envelope.get("error")
            if not isinstance(error_value, str):
                raise RuntimeError(f"error response from {path} missing string error field")
            raise RuntimeError(error_value)

        data_value = envelope.get("data")
        return self._as_object_map(data_value, f"response data from {path}")

    def _ensure_healthy(self) -> None:
        """Assert the service is healthy before making guarded calls."""
        with httpx.Client(base_url=self._base_url, timeout=10.0) as client:
            response = client.get("/v1/health")

        try:
            raw_envelope: object = response.json()
        except Exception as exc:
            raise RuntimeError("health endpoint returned invalid JSON") from exc

        envelope = self._as_object_map(raw_envelope, "health response envelope")

        data_value = envelope.get("data")
        if not isinstance(data_value, dict):
            raise RuntimeError("health endpoint missing data object")
        data_map = self._as_object_map(cast(object, data_value), "health response data")

        app_status = data_map.get("status")
        if not isinstance(app_status, str):
            raise RuntimeError("health endpoint missing string status")

        if app_status != "healthy":
            raise RuntimeError(f"service is {app_status}")

        if response.status_code != 200:
            raise RuntimeError(f"health endpoint status is {response.status_code}")

        logger.debug("Service health check passed for %s", self._base_url)
