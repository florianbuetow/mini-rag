"""Errors shared by persisted retrieval backends."""


class IndexConfigurationError(ValueError):
    """A persisted index requires rebuilding under the configured settings."""
