"""Unit tests for LM Studio metadata parsing."""

from minirag.lm_studio import (
    api_root_from_openai_base_url,
    context_window_from_v0_models_payload,
    context_window_from_v1_models_payload,
)


def test_api_root_from_openai_base_url_strips_v1_suffix() -> None:
    """OpenAI-compatible base URLs should map to the LM Studio server root."""
    assert api_root_from_openai_base_url("http://127.0.0.1:1234/v1") == "http://127.0.0.1:1234/"


def test_v1_model_payload_prefers_loaded_instance_context_length() -> None:
    """Loaded instance context_length is the active model context window."""
    payload: dict[str, object] = {
        "models": [
            {
                "key": "qwen/qwen3",
                "loaded_instances": [
                    {
                        "id": "qwen/qwen3",
                        "config": {"context_length": 8192},
                    }
                ],
                "max_context_length": 131072,
            }
        ]
    }

    assert context_window_from_v1_models_payload(payload, "qwen/qwen3") == 8192


def test_v1_model_payload_falls_back_to_model_max_context_length() -> None:
    """Unloaded model metadata can still expose a supported max context length."""
    payload: dict[str, object] = {
        "models": [
            {
                "key": "qwen/qwen3",
                "loaded_instances": [],
                "max_context_length": 131072,
            }
        ]
    }

    assert context_window_from_v1_models_payload(payload, "qwen/qwen3") == 131072


def test_v0_model_payload_uses_max_context_length() -> None:
    """Older LM Studio API metadata exposes max_context_length in data items."""
    payload: dict[str, object] = {"data": [{"id": "gemma", "max_context_length": 32768}]}

    assert context_window_from_v0_models_payload(payload, "gemma") == 32768
