"""Run one hybrid search through the local mini-rag REST API."""

import argparse
import json
import os
import sys
from typing import Any

import httpx

DEFAULT_REST_BASE = "http://127.0.0.1:9191"
HEALTH_TIMEOUT_SECONDS = 3.0
REQUEST_TIMEOUT_SECONDS = 5.0
DEFAULT_TOP_K = 10


def parse_top_k(value: str) -> int:
    """Parse a positive result count."""
    try:
        top_k = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("k must be a positive integer") from exc
    if top_k <= 0:
        raise argparse.ArgumentTypeError("k must be a positive integer")
    return top_k


def parse_alpha(value: str) -> float | None:
    """Parse an optional hybrid dense-weight override."""
    if value == "":
        return None
    try:
        alpha = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("alpha must be between 0.0 and 1.0") from exc
    if not 0.0 <= alpha <= 1.0:
        raise argparse.ArgumentTypeError("alpha must be between 0.0 and 1.0")
    return alpha


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Run one hybrid search against mini-rag")
    parser.add_argument("corpus", help="Name of the corpus to search")
    parser.add_argument("query", help="Search query text")
    parser.add_argument(
        "--alpha",
        type=parse_alpha,
        default=None,
        help="Dense weight from 0.0 to 1.0 (default: service configuration)",
    )
    parser.add_argument(
        "--k",
        "--top-k",
        dest="top_k",
        type=parse_top_k,
        default=DEFAULT_TOP_K,
        help=f"Number of results (default: {DEFAULT_TOP_K})",
    )
    return parser.parse_args()


def error_message(response: httpx.Response) -> str:
    """Extract the service error envelope or fall back to the HTTP status."""
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    if isinstance(body, dict) and isinstance(body.get("error"), str):
        return body["error"]
    return f"HTTP {response.status_code}"


def check_health(client: httpx.Client, rest_base: str) -> None:
    """Require the service health endpoint to report healthy."""
    try:
        response = client.get(f"{rest_base}/v1/health")
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Search system is unreachable: {exc}") from exc
    if not response.is_success:
        raise RuntimeError(f"Search system health check failed: HTTP {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError("Search system health check returned invalid JSON") from exc
    if not isinstance(body, dict) or body.get("data", {}).get("status") != "healthy":
        raise RuntimeError("Search system is currently offline.")


def run_search(args: argparse.Namespace) -> dict[str, Any]:
    """Call the health and hybrid search endpoints and return the raw API envelope."""
    rest_base = os.environ.get("REST_BASE", DEFAULT_REST_BASE).rstrip("/")
    payload: dict[str, Any] = {"query": args.query, "top_k": args.top_k}
    if args.alpha is not None:
        payload["alpha"] = args.alpha

    with httpx.Client(timeout=HEALTH_TIMEOUT_SECONDS) as client:
        check_health(client, rest_base)
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = client.post(f"{rest_base}/v1/corpus/{args.corpus}/query/hybrid", json=payload)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Error: {exc}") from exc

    if not response.is_success:
        raise RuntimeError(f"Search failed: {error_message(response)}")
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError(f"Search failed to parse JSON response: {exc}") from exc
    if not isinstance(body, dict):
        raise RuntimeError("Search failed: response JSON must be an object")
    return body


def main() -> int:
    """Run the search and print the unchanged API envelope to stdout."""
    args = parse_args()
    try:
        result = run_search(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
