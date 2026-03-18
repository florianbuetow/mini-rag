"""Static file serving for the Chat UI."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


def mount_static_files(app: FastAPI, web_dir: Path) -> None:
    """Mount static files from the web directory at the root path.

    API routes registered before this mount take precedence.
    If the web directory does not exist, a warning is logged and
    no static files are served (API endpoints remain functional).

    Args:
        app: The FastAPI application instance.
        web_dir: Path to the web/ directory containing static files.
    """
    if not web_dir.exists():
        logger.warning("Web directory not found at %s — static file serving disabled", web_dir)
        return

    if not web_dir.is_dir():
        logger.warning("Web path %s is not a directory — static file serving disabled", web_dir)
        return

    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="static")
    logger.info("Serving static files from %s", web_dir)
