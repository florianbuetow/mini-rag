"""Interactive query loop for searching a mini-rag corpus."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from minirag.clients.query import QueryClient
from minirag.config import Config

SEARCH_MODES = {"dense", "sparse", "hybrid"}
TOP_K = 5


def print_help() -> None:
    """Print usage instructions."""
    print()
    print("Commands:")
    print("  <query>             search using current mode")
    print("  /mode <mode>        switch mode (dense, sparse, hybrid)")
    print("  /topk <n>           set number of results")
    print("  /help               show this help")
    print("  /quit               exit")
    print()


def handle_mode(query: str) -> str | None:
    """Parse /mode command and return new mode, or None on invalid input."""
    parts = query.split(maxsplit=1)
    if len(parts) < 2 or parts[1] not in SEARCH_MODES:
        print(f"Usage: /mode <{'|'.join(sorted(SEARCH_MODES))}>")
        return None
    print(f"Switched to {parts[1]} mode")
    return parts[1]


def handle_topk(query: str) -> int | None:
    """Parse /topk command and return new top_k, or None on invalid input."""
    parts = query.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit() or int(parts[1]) <= 0:
        print("Usage: /topk <n>  (positive integer)")
        return None
    print(f"top_k set to {parts[1]}")
    return int(parts[1])


def run_search(client: QueryClient, corpus: str, mode: str, query: str, top_k: int) -> None:
    """Execute search and print results as JSON."""
    try:
        if mode == "dense":
            results = client.search_dense(corpus=corpus, query=query, top_k=top_k)
        elif mode == "sparse":
            results = client.search_sparse(corpus=corpus, query=query, top_k=top_k)
        else:
            results = client.search_hybrid(corpus=corpus, query=query, top_k=top_k)
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        return

    output = [asdict(r) for r in results]
    print(json.dumps(output, indent=2, ensure_ascii=False))


def handle_command(query: str, client: QueryClient, corpus: str, mode: str, top_k: int) -> tuple[str, int]:
    """Dispatch a single input line. Returns updated (mode, top_k)."""
    if query == "/help":
        print_help()
    elif query.startswith("/mode"):
        new_mode = handle_mode(query)
        if new_mode is not None:
            mode = new_mode
    elif query.startswith("/topk"):
        new_topk = handle_topk(query)
        if new_topk is not None:
            top_k = new_topk
    elif query.startswith("/"):
        print(f"Unknown command: {query}")
        print_help()
    else:
        run_search(client, corpus, mode, query, top_k)
    return mode, top_k


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Interactive search over a mini-rag corpus")
    parser.add_argument("--corpus", required=True, help="Name of the corpus to search")
    return parser.parse_args()


def main() -> None:
    """Run interactive query loop."""
    args = parse_args()
    corpus: str = args.corpus

    project_root = Path(__file__).resolve().parent.parent
    config = Config.from_yaml(project_root / "config.yaml")
    service_config = config.get_service_config()
    client = QueryClient(host=service_config.host, port=service_config.port, http_client=None)

    mode = "hybrid"
    top_k = TOP_K

    print()
    print(f"Connected to {service_config.host}:{service_config.port}")
    print(f"Corpus: {corpus} | Search mode: {mode} | top_k: {top_k}")
    print_help()

    while True:
        try:
            query = input(f"[{corpus}:{mode}] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if query == "":
            continue

        if query == "/quit":
            break

        mode, top_k = handle_command(query, client, corpus, mode, top_k)


if __name__ == "__main__":
    main()
