"""Conversation title agent — generates short titles for chat sessions."""

import asyncio
import logging
import queue
import threading

from strands import Agent
from strands.models import OpenAIModel

logger = logging.getLogger(__name__)

TITLE_SYSTEM_PROMPT: str = (
    "You are a concise title generator. Given a conversation, "
    "generate a short, descriptive title. The title MUST be 5 words or fewer. "
    "Respond with ONLY the title, nothing else. No quotes, no punctuation at the end, "
    "no explanation."
)


class ConversationTitleAgent:
    """Generates short titles for conversations using the same LLM backend.

    Uses a synchronous completion to produce a title of at most
    five words from the first user-assistant exchange.
    """

    def __init__(self, lm_studio_base_url: str) -> None:
        """Initialize the title agent.

        Args:
            lm_studio_base_url: OpenAI-compatible endpoint (e.g. LM Studio).
        """
        self._lm_studio_base_url = lm_studio_base_url

    def generate_title(self, messages: list[dict[str, str]], model: str) -> str:
        """Generate a short title for the conversation.

        Args:
            messages: The conversation messages (at minimum one user + one assistant).
            model: The LLM model ID to use (same model as the chat).

        Returns:
            A title string of at most five words.

        Raises:
            ValueError: If messages is empty.
            RuntimeError: If title generation fails.
        """
        if not messages:
            raise ValueError("messages must not be empty")

        conversation_text = "\n".join(f"{msg['role'].capitalize()}: {msg['content']}" for msg in messages)
        prompt = f"Here is a conversation:\n\n{conversation_text}\n\nGenerate a title for this conversation in 5 words or fewer."

        strands_model_id = model if model.startswith("openai/") else f"openai/{model}"

        openai_model = OpenAIModel(
            client_args={
                "api_key": "lm-studio",
                "base_url": self._lm_studio_base_url,
            },
            model_id=strands_model_id,
        )

        agent = Agent(
            model=openai_model,
            system_prompt=TITLE_SYSTEM_PROMPT,
            tools=[],
        )

        title = _collect_response(agent, prompt)
        title = title.strip().strip('"').strip("'").strip()

        # Enforce the 5-word limit
        words = title.split()
        if len(words) > 5:
            title = " ".join(words[:5])

        return title


def _collect_response(agent: Agent, prompt: str) -> str:
    """Run the agent and collect the full response as a string.

    Uses the same thread+queue bridge pattern as the main agent
    to avoid event loop conflicts with the FastAPI async runtime.
    """
    q: queue.Queue[str | None | Exception] = queue.Queue()

    async def _consume() -> None:
        try:
            async for event in agent.stream_async(prompt):
                if "data" in event:
                    q.put(event["data"])
        except Exception as exc:
            q.put(exc)
        finally:
            q.put(None)

    def _run() -> None:
        asyncio.run(_consume())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    parts: list[str] = []
    while True:
        item = q.get()
        if item is None:
            break
        if isinstance(item, Exception):
            raise item
        parts.append(item)

    thread.join()
    return "".join(parts)
