"""Thin JSON-RPC-over-stdio client for the MCP server.

Uses only stdlib modules (subprocess, json, threading, queue, time).
"""

import json
import subprocess
import threading
import time
from queue import Empty, Queue


class McpClient:
    """Manages an MCP server subprocess and speaks JSON-RPC over stdio."""

    def __init__(self, command: list[str], env: dict[str, str], cwd: str) -> None:
        self._proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=cwd,
        )
        self._next_id = 1
        self._response_queue: Queue[dict] = Queue()
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def initialize(self) -> dict:
        """Send initialize request and initialized notification."""
        result = self._send_request(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.1.0"},
            },
        )
        self._send_notification("notifications/initialized", {})
        return result

    def list_tools(self) -> list[dict]:
        """Return the list of tool definitions from the server."""
        result = self._send_request("tools/list", {})
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Call a tool and return the result dict (content + isError)."""
        return self._send_request("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        """Terminate the subprocess and join the reader thread."""
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
        self._reader_thread.join(timeout=3)

    def _send_request(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC request and wait for the matching response."""
        request_id = self._next_id
        self._next_id += 1

        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        self._write(message)

        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                assert self._proc.stderr is not None
                stderr_output = self._proc.stderr.read().decode(errors="replace")
                raise RuntimeError(f"MCP server exited unexpectedly (exit={self._proc.returncode})\nstderr: {stderr_output}")

            try:
                response = self._response_queue.get(timeout=0.5)
            except Empty:
                continue

            if response.get("id") == request_id:
                if "error" in response:
                    err = response["error"]
                    raise RuntimeError(f"JSON-RPC error {err.get('code')}: {err.get('message')}")
                return response.get("result", {})

        raise RuntimeError(f"Timeout waiting for response to {method} (id={request_id})")

    def _send_notification(self, method: str, params: dict) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        self._write(message)

    def _write(self, message: dict) -> None:
        """Write a JSON message followed by a newline to stdin."""
        assert self._proc.stdin is not None
        line = json.dumps(message) + "\n"
        self._proc.stdin.write(line.encode())
        self._proc.stdin.flush()

    def _reader_loop(self) -> None:
        """Read stdout line by line and enqueue responses (messages with 'id')."""
        assert self._proc.stdout is not None
        for raw_line in self._proc.stdout:
            line = raw_line.decode().strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and "id" in parsed:
                self._response_queue.put(parsed)
