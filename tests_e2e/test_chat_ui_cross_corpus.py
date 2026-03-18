"""Layer B — Real-RAG browser tests: Cross-corpus isolation.

4 scenarios (CC-01 through CC-04) from specifications2.md section 12.
Requires: mini-rag service on port 9191, LM Studio with allowed model,
both knowledgebase and llmevals corpora seeded and ingested.
"""

import pytest

from tests_e2e.helpers_chat_ui import (
    LLM_TIMEOUT,
    assert_has_citation_keys,
    assert_has_keywords,
    assert_lacks_citation_keys,
    corpus_available,
    create_new_chat,
    lm_studio_available,
    select_corpus,
    send_message_and_wait,
    service_available,
    wait_for_selectors_loaded,
)

KB_CITATION_KEYS: list[str] = [
    "kb_intent_engineering",
    "kb_prompt_engineering",
    "kb_rag_basics",
    "kb_hybrid_search",
    "kb_chunking",
    "kb_citations",
    "kb_chat_persistence",
    "kb_export",
    "kb_corpora",
    "kb_models",
    "kb_streaming",
    "kb_no_results",
]

LE_CITATION_KEYS: list[str] = [
    "le_rouge_l",
    "le_precision_recall_at_k",
    "le_groundedness",
    "le_hallucination",
    "le_judge_models",
    "le_pairwise",
    "le_dataset_design",
    "le_latency",
    "le_reproducibility",
    "le_error_analysis",
    "le_thresholds",
    "le_reporting",
]


def _skip_unless_ready() -> None:
    if not service_available():
        pytest.skip("mini-rag service not running on port 9191")
    if not lm_studio_available():
        pytest.skip("LM Studio not running on port 1234")
    if not corpus_available("knowledgebase"):
        pytest.skip("corpus 'knowledgebase' not available")
    if not corpus_available("llmevals"):
        pytest.skip("corpus 'llmevals' not available")


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.rag,
    pytest.mark.timeout(300),
]


class TestCrossCorpus:
    """CC-01 through CC-04: cross-corpus isolation scenarios."""

    def test_cc01_groundedness_different_corpora(self, page) -> None:
        """CC-01: Same question on different corpora yields different citations."""
        _skip_unless_ready()
        wait_for_selectors_loaded(page)
        prompt = "What is groundedness?"

        # Ask in knowledgebase
        select_corpus(page, "knowledgebase")
        create_new_chat(page)
        text_kb = send_message_and_wait(page, prompt, LLM_TIMEOUT)
        assert text_kb

        # Ask in llmevals
        select_corpus(page, "llmevals")
        create_new_chat(page)
        text_le = send_message_and_wait(page, prompt, LLM_TIMEOUT)
        assert text_le

        # llmevals should cite le_groundedness
        assert_has_citation_keys(text_le, ["le_groundedness"])
        # knowledgebase should NOT cite le_ docs
        assert_lacks_citation_keys(text_kb, LE_CITATION_KEYS)

    def test_cc02_export_question_isolation(self, page) -> None:
        """CC-02: Export question — kb cites kb_export, llmevals should not."""
        _skip_unless_ready()
        wait_for_selectors_loaded(page)
        prompt = "What is export for?"

        # knowledgebase
        select_corpus(page, "knowledgebase")
        create_new_chat(page)
        text_kb = send_message_and_wait(page, prompt, LLM_TIMEOUT)
        assert text_kb
        assert_has_citation_keys(text_kb, ["kb_export"])

        # llmevals — should not cite kb_ docs
        select_corpus(page, "llmevals")
        create_new_chat(page)
        text_le = send_message_and_wait(page, prompt, LLM_TIMEOUT)
        assert text_le
        assert_lacks_citation_keys(text_le, KB_CITATION_KEYS)

    def test_cc03_corpus_switch_mid_session(self, page) -> None:
        """CC-03: Start in kb, switch to llmevals, second turn cites only le_ docs."""
        _skip_unless_ready()
        wait_for_selectors_loaded(page)

        # Start chat in knowledgebase
        select_corpus(page, "knowledgebase")
        create_new_chat(page)
        text1 = send_message_and_wait(page, "What is intent engineering?", LLM_TIMEOUT)
        assert text1
        assert_has_keywords(text1, ["intent", "engineering"])

        # Switch to llmevals and ask eval question
        select_corpus(page, "llmevals")
        create_new_chat(page)
        text2 = send_message_and_wait(
            page,
            "What does ROUGE-L recall measure?",
            LLM_TIMEOUT,
        )
        assert text2
        assert_has_citation_keys(text2, ["le_rouge_l"])
        assert_lacks_citation_keys(text2, KB_CITATION_KEYS)

    def test_cc04_reopen_saved_chat_restores_corpus(self, page, api_client) -> None:
        """CC-04: Reopen a saved chat whose stored corpus is knowledgebase."""
        _skip_unless_ready()
        wait_for_selectors_loaded(page)

        # Create and use a knowledgebase chat
        select_corpus(page, "knowledgebase")
        create_new_chat(page)
        send_message_and_wait(page, "What is RAG?", LLM_TIMEOUT)

        # Get corpus selector value
        corpus_val = page.locator("#corpus-selector").input_value()
        assert corpus_val == "knowledgebase"

        # Switch to llmevals to change the selector
        select_corpus(page, "llmevals")

        # Click back on the knowledgebase chat (first entry since it's newest)
        entries = page.locator("[data-testid='chat-entry']")
        assert entries.count() >= 1
        entries.first.click()
        page.wait_for_timeout(2000)

        # Corpus selector should be restored to knowledgebase
        restored_corpus = page.locator("#corpus-selector").input_value()
        assert restored_corpus == "knowledgebase", f"Stored corpus should be 'knowledgebase', got '{restored_corpus}'"
