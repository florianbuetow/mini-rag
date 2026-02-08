#!/usr/bin/env python
"""E2E test server launcher.

Starts the mini-rag service using an externally provided config file.
Usage: uv run tests_e2e/start_server.py <config_path>
"""

import logging
import sys
from pathlib import Path

import uvicorn

from minirag.api.app import create_app
from minirag.config import Config


def main() -> None:
    """Launch the service with the supplied config path."""
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <config_path>", file=sys.stderr)
        sys.exit(1)

    config_path = Path(sys.argv[1]).resolve()
    project_root = Path(__file__).resolve().parent.parent

    config = Config.from_yaml(config_path)
    service = config.get_service_config()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = create_app(config=config, project_root=project_root)
    uvicorn.run(
        app=app,
        host=service.host,
        port=service.port,
        log_level=service.log_level.lower(),
    )


if __name__ == "__main__":
    main()
