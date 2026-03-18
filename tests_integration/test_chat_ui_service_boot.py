"""Layer C — Integration tests: Service boot and static serving.

Tests 11-12 from specifications2.md section 7:
11. just start serves / and /v1/* on the same port.
12. Startup without web/ still serves API endpoints and returns 404 at /.
"""

import shutil
import tempfile
from pathlib import Path

import httpx
import pytest

from tests_integration.helpers_runtime import (
    create_temp_data_dir,
    find_free_port,
    start_service,
    stop_service,
    wait_for_service,
)

PROJECT_ROOT: Path = Path(__file__).parent.parent


pytestmark = [
    pytest.mark.integration,
    pytest.mark.timeout(60),
]


class TestServiceBoot:
    """Test 11: Service serves both static files and API on same port."""

    def test_serves_root_and_api(self) -> None:
        """Root URL serves HTML, /v1/health returns 200."""
        tmp_dir = create_temp_data_dir()
        port = find_free_port()
        base_url = f"http://127.0.0.1:{port}"
        proc = start_service(port, tmp_dir / "data")

        try:
            assert wait_for_service(f"{base_url}/v1/health", timeout=30.0), f"Service did not start on port {port}"

            # API endpoint
            resp_api = httpx.get(f"{base_url}/v1/health", timeout=5.0)
            assert resp_api.status_code == 200

            # Static root
            resp_root = httpx.get(base_url, timeout=5.0)
            assert resp_root.status_code == 200
            assert "html" in resp_root.headers.get("content-type", "").lower()
        finally:
            stop_service(proc, base_url)
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestServiceBootWithoutWeb:
    """Test 12: Startup without web/ serves API, returns 404 at /."""

    def test_no_web_dir_still_serves_api(self) -> None:
        """Without web/ directory, API works but / returns 404."""
        tmp_dir = create_temp_data_dir()
        port = find_free_port()
        base_url = f"http://127.0.0.1:{port}"

        # Create a temp web dir override to simulate missing web/
        # We pass an env var to point web_dir somewhere empty
        empty_web = Path(tempfile.mkdtemp(prefix="minirag_noweb_"))
        proc = start_service(
            port,
            tmp_dir / "data",
            config_env={"MINIRAG_WEB_DIR": str(empty_web)},
        )

        try:
            assert wait_for_service(f"{base_url}/v1/health", timeout=30.0), f"Service did not start on port {port}"

            # API should work
            resp_api = httpx.get(f"{base_url}/v1/health", timeout=5.0)
            assert resp_api.status_code == 200

            # Root should 404 (no static files)
            resp_root = httpx.get(f"{base_url}/", timeout=5.0, follow_redirects=True)
            assert resp_root.status_code in (404, 422), f"Expected 404 without web/, got {resp_root.status_code}"
        finally:
            stop_service(proc, base_url)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            shutil.rmtree(empty_web, ignore_errors=True)
