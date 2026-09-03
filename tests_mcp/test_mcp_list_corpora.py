"""Focused MCP contract tests for corpus listing."""

import json
import os
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from tests_mcp.mcp_client import McpClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class _ApiHandler(BaseHTTPRequestHandler):
    """Serve the two REST endpoints used by the MCP corpus-listing tool."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/v1/health":
            payload = {"status": 200, "data": {"status": "healthy"}}
        elif self.path == "/v1/corpora":
            payload = self.server.corpora_payload  # type: ignore[attr-defined]
        else:
            self.send_error(404)
            return

        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


def test_list_corpora_returns_api_envelope_and_rejects_malformed_descriptions() -> None:
    if shutil.which("npx") is None:
        pytest.skip("npx not found; Node.js is required for MCP tests")

    server = ThreadingHTTPServer(("127.0.0.1", 0), _ApiHandler)
    server.corpora_payload = {  # type: ignore[attr-defined]
        "status": 200,
        "data": {
            "corpora": ["books", "notes"],
            "descriptions": {"books": "# Books", "notes": "No description available."},
        },
    }
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    client = McpClient(
        command=["npx", "tsx", "mini-rag.ts"],
        env={**os.environ, "REST_BASE": f"http://127.0.0.1:{server.server_port}"},
        cwd=str(PROJECT_ROOT / "mcp"),
    )
    try:
        client.initialize()
        populated = client.call_tool("list_corpora", {})
        assert populated.get("isError") is not True
        assert json.loads(populated["content"][0]["text"]) == server.corpora_payload  # type: ignore[attr-defined]

        server.corpora_payload = {"status": 200, "data": {"corpora": [], "descriptions": {}}}  # type: ignore[attr-defined]
        empty = client.call_tool("list_corpora", {})
        assert empty.get("isError") is not True
        assert json.loads(empty["content"][0]["text"]) == server.corpora_payload  # type: ignore[attr-defined]

        server.corpora_payload = {"status": 200, "data": {"corpora": ["books"], "descriptions": {}}}  # type: ignore[attr-defined]
        malformed = client.call_tool("list_corpora", {})
        assert malformed.get("isError") is True
        assert "missing string description for corpus books" in malformed["content"][0]["text"]
    finally:
        client.close()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=3)
