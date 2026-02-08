"""Tests for main module utilities."""

from pathlib import Path

from src.main import resolve_project_root


def test_resolve_project_root() -> None:
    """Resolved project root should contain pyproject.toml."""
    project_root = resolve_project_root()
    assert isinstance(project_root, Path)
    assert (project_root / "pyproject.toml").exists()
