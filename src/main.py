"""Service entry point for mini-rag."""

import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from minirag.api.app import create_app
from minirag.config import Config


def resolve_project_root() -> Path:
    """Resolve repository root from current file location."""
    return Path(__file__).resolve().parent.parent


def configure_logging(log_level: str) -> None:
    """Configure root logging with validated level name."""
    uppercase_level = log_level.upper()

    if not hasattr(logging, uppercase_level):
        raise ValueError(f"invalid log level: {log_level}")

    log_level_value = getattr(logging, uppercase_level)
    if not isinstance(log_level_value, int):
        raise ValueError(f"invalid log level value: {log_level}")

    logging.basicConfig(
        level=log_level_value,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def load_config(project_root: Path) -> Config:
    """Load and validate application config from disk."""
    return Config.from_yaml(project_root / "config.yaml")


def create_uvicorn_app() -> FastAPI:
    """Factory function used by uvicorn reload mode."""
    project_root = resolve_project_root()
    config = load_config(project_root)
    service_config = config.get_service_config()
    configure_logging(service_config.log_level)
    app = create_app(config=config, project_root=project_root)
    return app


def main() -> None:
    """Launch uvicorn server with configuration from config.yaml."""
    project_root = resolve_project_root()
    config = load_config(project_root)
    service_config = config.get_service_config()
    configure_logging(service_config.log_level)

    if service_config.reload:
        uvicorn.run(
            app="main:create_uvicorn_app",
            host=service_config.host,
            port=service_config.port,
            reload=service_config.reload,
            log_level=service_config.log_level.lower(),
            factory=True,
        )
    else:
        app = create_app(config=config, project_root=project_root)
        uvicorn.run(
            app=app,
            host=service_config.host,
            port=service_config.port,
            reload=service_config.reload,
            log_level=service_config.log_level.lower(),
        )


if __name__ == "__main__":
    main()
