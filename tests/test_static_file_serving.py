"""Unit tests for static file serving from web/ directory.

Spec: docs/specs/static-file-serving-specification.md
Test spec: docs/specs/static-file-serving-test-specification.md

These tests will FAIL until the static file serving feature is implemented.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from minirag.api.app import unhandled_exception_handler
from minirag.api.routes_info import router as info_router


class FakeServiceConfig:
    def __init__(self, reload: bool) -> None:
        self.reload = reload


class FakeConfig:
    def model_dump(self):
        return {"service": {"host": "127.0.0.1", "port": 9191}}

    def get_service_config(self):
        return FakeServiceConfig(reload=False)


class FakeCorpusManager:
    def list_corpora(self) -> list[str]:
        return ["test"]

    def corpus_description(self, corpus: str) -> str:
        if corpus != "test":
            raise FileNotFoundError(f"Corpus not found: {corpus}")
        return "No description available."

    def corpus_descriptions(self, corpora: list[str] | None = None) -> dict[str, str]:
        names = self.list_corpora() if corpora is None else corpora
        return {name: self.corpus_description(name) for name in names}


def _make_app_with_static(web_dir: Path) -> FastAPI:
    """Create app with static file serving from the given web directory.

    This imports the static file serving setup that does not exist yet.
    The import will fail until the feature is implemented.
    """
    # This will need to import the static serving setup from the implementation
    # For now, we build the app the same way the implementation should work:
    # mount static files from web_dir at the root, with API routes taking precedence.
    from minirag.api.static import mount_static_files  # noqa: F401  # will fail until implemented

    app = FastAPI()
    app.state.app_status = "healthy"
    app.state.config = FakeConfig()
    app.state.corpus_manager = FakeCorpusManager()
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(info_router)
    mount_static_files(app, web_dir)
    return app


@pytest.fixture()
def web_dir(tmp_path: Path) -> Path:
    """Create a web directory with sample files."""
    web = tmp_path / "web"
    web.mkdir()
    (web / "css").mkdir()
    (web / "gfx").mkdir()

    (web / "index.html").write_text("<html>Chat UI</html>")
    (web / "css" / "style.css").write_text("body { color: red; }")

    # Minimal PNG header
    png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    (web / "gfx" / "logo.png").write_bytes(png_header)

    return web


# TS-1: Serve index.html at root
def test_serve_index_html_at_root(web_dir: Path):
    client = TestClient(_make_app_with_static(web_dir))

    resp = client.get("/")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Chat UI" in resp.text


# TS-2: Serve CSS files
def test_serve_css_file(web_dir: Path):
    client = TestClient(_make_app_with_static(web_dir))

    resp = client.get("/css/style.css")

    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]
    assert "body { color: red; }" in resp.text


# TS-3: Serve image files
def test_serve_image_file(web_dir: Path):
    client = TestClient(_make_app_with_static(web_dir))

    resp = client.get("/gfx/logo.png")

    assert resp.status_code == 200
    assert "image/png" in resp.headers["content-type"]


# TS-4: Return 404 for non-existent root file
def test_404_for_nonexistent_root_file(web_dir: Path):
    client = TestClient(_make_app_with_static(web_dir))

    resp = client.get("/nonexistent.html")

    assert resp.status_code == 404


# TS-5: Return 404 for non-existent CSS file
def test_404_for_nonexistent_css_file(web_dir: Path):
    client = TestClient(_make_app_with_static(web_dir))

    resp = client.get("/css/nonexistent.css")

    assert resp.status_code == 404


# TS-6: API routes take precedence over static files
def test_api_routes_take_precedence_over_static(web_dir: Path):
    client = TestClient(_make_app_with_static(web_dir))

    resp = client.get("/v1/corpora")

    assert resp.status_code == 200
    assert "corpora" in resp.json()["data"]


# TS-7: Service works without web/ directory
def test_service_works_without_web_directory(tmp_path: Path):
    nonexistent_web = tmp_path / "web_missing"
    client = TestClient(_make_app_with_static(nonexistent_web))

    root_resp = client.get("/")
    assert root_resp.status_code == 404

    health_resp = client.get("/v1/health")
    assert health_resp.status_code == 200


# TS-8: Reject path traversal attempts
def test_reject_path_traversal(web_dir: Path):
    # Create a sensitive file outside web/
    secret = web_dir.parent / "secret.txt"
    secret.write_text("TOP SECRET DATA")

    client = TestClient(_make_app_with_static(web_dir))

    resp = client.get("/../secret.txt")

    assert resp.status_code in (400, 404)
    assert "TOP SECRET DATA" not in resp.text
