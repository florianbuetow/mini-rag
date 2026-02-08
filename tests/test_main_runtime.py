"""Unit tests for main runtime helpers and uvicorn launch branching."""

from pathlib import Path
from typing import cast

import pytest

import main as main_module
from minirag.config import Config


class FakeServiceConfig:
    """Fake service config used for main launch tests."""

    def __init__(self, reload: bool, log_level: str) -> None:
        self.host = "127.0.0.1"
        self.port = 7001
        self.reload = reload
        self.log_level = log_level


class FakeConfig:
    """Fake config object with service config accessor."""

    def __init__(self, reload: bool, log_level: str) -> None:
        self._service = FakeServiceConfig(reload=reload, log_level=log_level)

    def get_service_config(self) -> FakeServiceConfig:
        return self._service


def test_configure_logging_invalid_level_raises() -> None:
    """Invalid logging levels should fail fast."""
    with pytest.raises(ValueError):
        main_module.configure_logging("NOT_A_LEVEL")


def test_create_uvicorn_app_uses_loader_and_factory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Uvicorn app factory should load config and create app."""
    fake_config = FakeConfig(reload=False, log_level="INFO")

    def fake_resolve_project_root() -> Path:
        return tmp_path

    def fake_load_config(_: Path) -> Config:
        return cast(Config, fake_config)

    def fake_create_app(config: Config, project_root: Path) -> object:
        del config, project_root
        return object()

    monkeypatch.setattr(main_module, "resolve_project_root", fake_resolve_project_root)
    monkeypatch.setattr(main_module, "load_config", fake_load_config)
    monkeypatch.setattr(main_module, "create_app", fake_create_app)

    app = main_module.create_uvicorn_app()
    assert app is not None


def test_main_calls_uvicorn_with_factory_when_reload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reload-enabled config should launch uvicorn in factory mode."""
    fake_config = FakeConfig(reload=True, log_level="INFO")

    def fake_resolve_project_root() -> Path:
        return Path("/tmp/project")

    def fake_load_config(_: Path) -> Config:
        return cast(Config, fake_config)

    monkeypatch.setattr(main_module, "resolve_project_root", fake_resolve_project_root)
    monkeypatch.setattr(main_module, "load_config", fake_load_config)

    captured: dict[str, object] = {}

    def fake_run(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(main_module.uvicorn, "run", fake_run)

    main_module.main()

    assert captured["app"] == "main:create_uvicorn_app"
    assert captured["factory"] is True
    assert captured["reload"] is True


def test_main_calls_uvicorn_with_app_object_when_not_reload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reload-disabled config should launch uvicorn with instantiated app."""
    fake_config = FakeConfig(reload=False, log_level="INFO")

    def fake_resolve_project_root() -> Path:
        return Path("/tmp/project")

    def fake_load_config(_: Path) -> Config:
        return cast(Config, fake_config)

    def fake_create_app(config: Config, project_root: Path) -> object:
        del config, project_root
        return "app-object"

    monkeypatch.setattr(main_module, "resolve_project_root", fake_resolve_project_root)
    monkeypatch.setattr(main_module, "load_config", fake_load_config)
    monkeypatch.setattr(main_module, "create_app", fake_create_app)

    captured: dict[str, object] = {}

    def fake_run(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(main_module.uvicorn, "run", fake_run)

    main_module.main()

    assert captured["app"] == "app-object"
    assert captured["reload"] is False
