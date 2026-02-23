"""
Conversation manager for per-call message history.

Tracks user/assistant messages and manages context window for the LLM.
Each phone call gets its own ConversationManager instance.
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are a friendly and natural-sounding AI phone assistant. "
    "Keep your responses concise and conversational — you're on a phone call, "
    "not writing an essay. Respond in 1-3 sentences unless the caller asks for detail. "
    "Be warm, helpful, and speak naturally like a real person would on the phone."
)


class ConversationManager:
    """
    Per-call conversation history manager.

    Tracks the system prompt, user transcripts from STT, and
    assistant responses from the LLM. Formats messages for the
    OpenAI-compatible chat completion API.
    """

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        max_history_messages: int = 20,
    ):
        """
        Initialize conversation manager for a single call.

        Args:
            system_prompt: System message defining AI behavior.
            max_history_messages: Max user+assistant messages to keep.
                Oldest messages are trimmed when limit is reached.
        """
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.max_history_messages = max_history_messages
        self.history: List[Dict[str, str]] = []

    def add_user_message(self, text: str) -> None:
        """Add a user message (from STT final transcript)."""
        if not text or not text.strip():
            return
        self.history.append({"role": "user", "content": text.strip()})
        self._trim_history()
        logger.debug(f"Added user message: {text[:50]}...")

    def add_assistant_message(self, text: str) -> None:
        """Add an assistant message (from LLM response)."""
        if not text or not text.strip():
            return
        self.history.append({"role": "assistant", "content": text.strip()})
        self._trim_history()
        logger.debug(f"Added assistant message: {text[:50]}...")

    def get_messages(self) -> List[Dict[str, str]]:
        """
        Get full message list for LLM API call.

        Returns:
            List with system prompt + conversation history.
        """
        return [
            {"role": "system", "content": self.system_prompt},
            *self.history,
        ]

    def get_turn_count(self) -> int:
        """Get number of user turns in the conversation."""
        return sum(1 for m in self.history if m["role"] == "user")

    def _trim_history(self) -> None:
        """Trim oldest messages if history exceeds max."""
        while len(self.history) > self.max_history_messages:
            removed = self.history.pop(0)
            logger.debug(f"Trimmed oldest message: {removed['role']}")

    def add_assistant_message_partial(self, spoken_text: str) -> None:
        """
        Add a partial assistant message (response was interrupted by barge-in).

        Only saves the portion that was actually spoken aloud. Appends an
        [interrupted] marker so the LLM knows its previous response was cut off.
        """
        if not spoken_text or not spoken_text.strip():
            return
        content = spoken_text.strip() + " [interrupted]"
        self.history.append({"role": "assistant", "content": content})
        self._trim_history()
        logger.debug(f"Added partial assistant message: {spoken_text[:50]}...")

    def reset(self) -> None:
        """Reset conversation history (keep system prompt)."""
        self.history = []
