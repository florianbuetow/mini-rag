"""Integration tests for auto-launch: service starts on port 9191 with Chat UI.

Spec: docs/specs/integration-specification.md
Test spec: docs/specs/integration-test-specification.md
Test impl spec: docs/specs/integration-test-implementation-specification.md

These tests start/stop the actual mini-rag service process.
They require port 9191 to be available.

Run with: uv run pytest tests_integration/
"""

import contextlib
import socket
import subprocess
import time
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SERVICE_PORT = 9191
BASE_URL = f"http://localhost:{SERVICE_PORT}"


def _port_in_use(port: int) -> bool:
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def _wait_for_service(url: str, timeout: float = 30.0, interval: float = 1.0) -> bool:
    """Poll a URL until it returns 200 or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        time.sleep(interval)
    return False


def _start_service(config_env: dict | None = None) -> subprocess.Popen:
    """Start the mini-rag service as a subprocess."""
    env = None
    if config_env:
        import os

        env = {**os.environ, **config_env}

    proc = subprocess.Popen(
        ["uv", "run", "src/main.py"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    return proc


def _stop_service(proc: subprocess.Popen) -> None:
    """Stop the service by sending shutdown request, then terminate if needed."""
    with contextlib.suppress(httpx.ConnectError, httpx.ReadTimeout):
        httpx.post(f"{BASE_URL}/v1/shutdown", timeout=5.0)

    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait(timeout=5)


# TS-1: Service starts on port 9191
def test_service_starts_on_port_9191():
    if _port_in_use(SERVICE_PORT):
        pytest.skip(f"Port {SERVICE_PORT} already in use")

    proc = _start_service()
    try:
        assert _wait_for_service(f"{BASE_URL}/v1/health"), f"Service did not become healthy on port {SERVICE_PORT}"

        resp = httpx.get(f"{BASE_URL}/v1/health", timeout=5.0)
        assert resp.status_code == 200
    finally:
        _stop_service(proc)


# TS-2: Root URL serves Chat UI
def test_root_url_serves_chat_ui():
    if _port_in_use(SERVICE_PORT):
        pytest.skip(f"Port {SERVICE_PORT} already in use")

    proc = _start_service()
    try:
        assert _wait_for_service(f"{BASE_URL}/v1/health")

        resp = httpx.get(f"{BASE_URL}/", timeout=5.0)
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
    finally:
        _stop_service(proc)


# TS-3: API endpoints accessible on 9191
def test_api_endpoints_on_same_port():
    if _port_in_use(SERVICE_PORT):
        pytest.skip(f"Port {SERVICE_PORT} already in use")

    proc = _start_service()
    try:
        assert _wait_for_service(f"{BASE_URL}/v1/health")

        resp = httpx.get(f"{BASE_URL}/v1/corpora", timeout=5.0)
        assert resp.status_code == 200
        assert "corpora" in resp.json()["data"]
    finally:
        _stop_service(proc)


# TS-4: Service stops and frees port
def test_service_stops_and_frees_port():
    if _port_in_use(SERVICE_PORT):
        pytest.skip(f"Port {SERVICE_PORT} already in use")

    proc = _start_service()
    try:
        assert _wait_for_service(f"{BASE_URL}/v1/health")
    except Exception:
        _stop_service(proc)
        raise

    # Stop the service
    _stop_service(proc)

    # Wait a moment for the port to be freed
    time.sleep(2)

    # Port should no longer be in use
    with pytest.raises(httpx.ConnectError):
        httpx.get(f"{BASE_URL}/", timeout=2.0)


# TS-5: Port conflict error
def test_port_conflict_error():
    if _port_in_use(SERVICE_PORT):
        pytest.skip(f"Port {SERVICE_PORT} already in use")

    # Occupy the port
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        blocker.bind(("localhost", SERVICE_PORT))
        blocker.listen(1)

        proc = _start_service()
        # The service should fail to start
        try:
            exit_code = proc.wait(timeout=15)
            assert exit_code != 0, "Service should fail to start when port is occupied"
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait(timeout=5)
            pytest.fail("Service did not exit when port was occupied")
    finally:
        blocker.close()


# TS-6: Start without web/ directory
def test_start_without_web_directory():
    if _port_in_use(SERVICE_PORT):
        pytest.skip(f"Port {SERVICE_PORT} already in use")

    # Check if web/ exists — if it doesn't, this test runs against real config
    web_dir = PROJECT_ROOT / "web"
    if web_dir.exists():
        pytest.skip("web/ directory exists — cannot test missing web/ scenario without modifying project")

    proc = _start_service()
    try:
        assert _wait_for_service(f"{BASE_URL}/v1/health")

        # Health should work
        health_resp = httpx.get(f"{BASE_URL}/v1/health", timeout=5.0)
        assert health_resp.status_code == 200

        # Root should return 404 (no web/ directory)
        root_resp = httpx.get(f"{BASE_URL}/", timeout=5.0)
        assert root_resp.status_code == 404
    finally:
        _stop_service(proc)
