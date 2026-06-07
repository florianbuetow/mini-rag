"""Startup environment validation helpers."""

from pathlib import Path

from minirag.config import Config


def validate_startup_environment(config: Config, project_root: Path) -> None:
    """Validate filesystem prerequisites required to boot the service."""
    data_dir = config.resolve_data_dir(project_root)
    index_config = config.get_index_config()

    if not data_dir.exists():
        raise FileNotFoundError(f"data directory not found: {data_dir}")

    if not data_dir.is_dir():
        raise ValueError(f"data path is not a directory: {data_dir}")

    # Only the fastText provider loads a local model file; the LM Studio provider
    # resolves its model remotely and is validated at embed time, not at startup.
    if index_config.embeddings.provider == "fasttext":
        model_path = data_dir / "models" / index_config.embeddings.model_name
        if not model_path.exists():
            raise FileNotFoundError(f"embedding model file not found: {model_path}")

        if not model_path.is_file():
            raise ValueError(f"embedding model path is not a file: {model_path}")

    probe_path = data_dir / ".minirag_write_probe"
    try:
        with probe_path.open("w", encoding="utf-8") as file_handle:
            file_handle.write("probe")
    except OSError as exc:
        raise OSError(f"data directory is not writable: {data_dir}") from exc
    finally:
        if probe_path.exists():
            probe_path.unlink()
