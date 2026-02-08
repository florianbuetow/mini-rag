"""Unit tests for API response envelope utilities and health guard."""

from fastapi import FastAPI
from starlette.requests import Request
from starlette.types import Scope

from minirag.api.utils import ensure_healthy, error_response, success_response


def make_request(app_status: str) -> Request:
    """Build a minimal Request object with custom app state."""
    app = FastAPI()
    app.state.app_status = app_status
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "http_version": "1.1",
        "root_path": "",
        "app": app,
    }
    return Request(scope)


def test_success_response_envelope() -> None:
    """Success response should include status and data."""
    response = success_response(status=200, data={"ok": True})
    assert response.status_code == 200
    assert response.body == b'{"status":200,"data":{"ok":true}}'


def test_error_response_envelope() -> None:
    """Error response should include status and error."""
    response = error_response(status=503, message="service is shutting_down")
    assert response.status_code == 503
    assert response.body == b'{"status":503,"error":"service is shutting_down"}'


def test_ensure_healthy_allows_healthy_state() -> None:
    """Healthy app state should return None guard response."""
    request = make_request("healthy")
    assert ensure_healthy(request) is None


def test_ensure_healthy_blocks_unhealthy_state() -> None:
    """Non-healthy app state should return a 503 response."""
    request = make_request("shutting_down")
    response = ensure_healthy(request)

    assert response is not None
    assert response.status_code == 503
    assert response.body == b'{"status":503,"error":"service is shutting_down"}'
