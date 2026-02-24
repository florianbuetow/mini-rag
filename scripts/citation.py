"""Fetch citation metadata for one or more citation keys from a mini-rag corpus."""

import argparse
import json
import sys
from pathlib import Path

from minirag.clients.query import QueryClient
from minirag.config import Config


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Fetch citation metadata from a mini-rag corpus")
    parser.add_argument("--corpus", required=True, help="Name of the corpus")
    parser.add_argument("--config", default=None, help="Path to config file (default: config.yaml in project root)")
    parser.add_argument("--keys-file", default=None, help="Path to file containing citation keys (use '-' for stdin)")
    parser.add_argument("citation_keys", nargs="*", help="One or more citation keys to look up")
    return parser.parse_args()


def _load_citation_keys(args: argparse.Namespace) -> list[str]:
    if args.keys_file is None and not args.citation_keys:
        raise ValueError("no citation keys provided")
    if args.keys_file is not None and args.citation_keys:
        raise ValueError("provide citation keys via positional args or --keys-file, not both")

    if args.keys_file is None:
        return [key for key in args.citation_keys if key.strip() != ""]

    raw = sys.stdin.read() if args.keys_file == "-" else Path(args.keys_file).read_text(encoding="utf-8")
    keys = [key for key in raw.split() if key.strip() != ""]
    if not keys:
        raise ValueError("no citation keys provided")
    return keys


def main() -> None:
    """Fetch and print citation data for each key."""
    args = parse_args()
    corpus: str = args.corpus
    try:
        citation_keys = _load_citation_keys(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    project_root = Path(__file__).resolve().parent.parent
    config_path = Path(args.config).resolve() if args.config else project_root / "config.yaml"
    config = Config.from_yaml(config_path)
    service_config = config.get_service_config()
    client = QueryClient(host=service_config.host, port=service_config.port, http_client=None)

    errors = 0
    for citation_key in citation_keys:
        try:
            data = client.get_citation(corpus=corpus, citation_key=citation_key)
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except RuntimeError as err:
            print(f"Error [{citation_key}]: {err}", file=sys.stderr)
            errors += 1

    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
