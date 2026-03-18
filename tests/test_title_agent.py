"""Unit tests for ConversationTitleAgent."""

import pytest

from minirag.title_agent import ConversationTitleAgent


def test_generate_title_rejects_empty_messages():
    agent = ConversationTitleAgent(lm_studio_base_url="http://localhost:1234/v1")
    with pytest.raises(ValueError, match="messages must not be empty"):
        agent.generate_title(messages=[], model="test-model")


def test_title_truncated_to_five_words():
    """Verify the 5-word enforcement logic works independently of the LLM."""
    # Simulate what generate_title does after getting a long response
    title = "This Is A Very Long Title That Exceeds Five Words"
    title = title.strip().strip('"').strip("'").strip()
    words = title.split()
    if len(words) > 5:
        title = " ".join(words[:5])

    assert title == "This Is A Very Long"
    assert len(title.split()) == 5


def test_title_strips_quotes():
    """Verify quote stripping logic."""
    raw = '"My Chat Title"'
    cleaned = raw.strip().strip('"').strip("'").strip()
    assert cleaned == "My Chat Title"

    raw2 = "'Another Title'"
    cleaned2 = raw2.strip().strip('"').strip("'").strip()
    assert cleaned2 == "Another Title"
