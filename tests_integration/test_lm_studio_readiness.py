"""Layer C — Integration tests: LM Studio readiness.

Tests 5-7 from specifications2.md section 7:
5. GET /v1/models returns empty data when LM Studio unreachable.
6. LM Studio readiness helper accepts already-loaded allowed model.
7. LM Studio readiness helper unloads disallowed, loads allowed model.
"""

import pytest

from tests_integration.helpers_runtime import (
    ensure_allowed_model_loaded,
    find_allowed_loaded_model,
    get_loaded_models,
    is_model_allowed,
    lm_studio_available,
    lms_cli_available,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.timeout(30),
]


class TestModelPolicy:
    """Test allowed model policy without LM Studio dependency."""

    def test_allowed_model_accepts_small(self) -> None:
        """Small models pass the policy."""
        assert is_model_allowed("gemma-3-1b-it")
        assert is_model_allowed("qwen-2.5-7b-instruct")
        assert is_model_allowed("gemma-3-12b-it")

    def test_allowed_model_rejects_large(self) -> None:
        """Very large models are rejected."""
        assert not is_model_allowed("llama-3.1-70b-instruct")
        assert not is_model_allowed("qwen-2.5-72b-instruct")
        assert not is_model_allowed("mixtral-8x110b")
        assert not is_model_allowed("llama-3.1-405b")


class TestLMStudioReadiness:
    """Tests 6-7: Readiness helpers with live LM Studio (skipped if unavailable)."""

    def test_accepts_loaded_allowed_model(self) -> None:
        """Test 6: If an allowed model is loaded, the helper finds it."""
        if not lm_studio_available():
            pytest.skip("LM Studio not running")

        models = get_loaded_models()
        if not models:
            pytest.skip("No models loaded in LM Studio")

        allowed = find_allowed_loaded_model()
        if allowed is None:
            pytest.skip("No allowed models currently loaded")

        assert is_model_allowed(allowed), f"Model '{allowed}' should pass allowed policy"

    def test_loaded_models_list(self) -> None:
        """Verify get_loaded_models returns a list."""
        if not lm_studio_available():
            pytest.skip("LM Studio not running")

        models = get_loaded_models()
        assert isinstance(models, list)

    def test_ensure_allowed_model_loaded(self) -> None:
        """Test 7: ensure_allowed_model_loaded uses CLI to prepare an allowed model.

        Skips if LM Studio or the lms CLI is unavailable.
        """
        if not lm_studio_available():
            pytest.skip("LM Studio not running")
        if not lms_cli_available():
            pytest.skip("lms CLI not available on PATH")

        model_id = ensure_allowed_model_loaded()
        assert model_id is not None, "ensure_allowed_model_loaded should return a model ID"
        assert is_model_allowed(model_id), f"Model '{model_id}' should pass allowed policy"
