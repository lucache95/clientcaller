"""Tests for context drift prevention and error recovery (Phase 5 Plan 03)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.llm.conversation import ConversationManager


class TestPartialAssistantMessage:
    """Test ConversationManager.add_assistant_message_partial()."""

    def test_partial_message_has_interrupted_marker(self):
        """Partial message includes [interrupted] marker."""
        conv = ConversationManager()
        conv.add_assistant_message_partial("Hello, I was saying")

        assert len(conv.history) == 1
        msg = conv.history[0]
        assert msg["role"] == "assistant"
        assert msg["content"] == "Hello, I was saying [interrupted]"

    def test_partial_message_empty_ignored(self):
        """Empty partial messages are not saved."""
        conv = ConversationManager()
        conv.add_assistant_message_partial("")
        conv.add_assistant_message_partial("   ")

        assert len(conv.history) == 0

    def test_full_message_no_marker(self):
        """Full (non-interrupted) message has no marker."""
        conv = ConversationManager()
        conv.add_assistant_message("Hello, how can I help you?")

        assert len(conv.history) == 1
        assert "[interrupted]" not in conv.history[0]["content"]

    def test_context_accurate_after_multiple_interrupts(self):
        """3+ interrupts leave clean history with only spoken portions."""
        conv = ConversationManager()

        # Turn 1: user speaks, AI interrupted
        conv.add_user_message("What's the weather?")
        conv.add_assistant_message_partial("The weather today is")

        # Turn 2: user speaks again, AI interrupted again
        conv.add_user_message("Never mind, what time is it?")
        conv.add_assistant_message_partial("It's currently")

        # Turn 3: user speaks, AI interrupted yet again
        conv.add_user_message("Actually, tell me a joke")
        conv.add_assistant_message_partial("Why did the chicken")

        # Verify history has all 6 messages
        assert len(conv.history) == 6

        # All assistant messages have [interrupted] marker
        assistant_msgs = [m for m in conv.history if m["role"] == "assistant"]
        assert len(assistant_msgs) == 3
        for msg in assistant_msgs:
            assert msg["content"].endswith("[interrupted]")

        # No unsent content leaked — only the spoken portions
        assert "The weather today is [interrupted]" == assistant_msgs[0]["content"]
        assert "It's currently [interrupted]" == assistant_msgs[1]["content"]
        assert "Why did the chicken [interrupted]" == assistant_msgs[2]["content"]

        # Messages format correctly for LLM
        messages = conv.get_messages()
        assert messages[0]["role"] == "system"
        assert len(messages) == 7  # system + 6 history


class TestContextDriftInResponse:
    """Test that _generate_response saves correct tokens on cancellation."""

    @pytest.mark.asyncio
    async def test_partial_response_saved_after_interrupt(self):
        """Only spoken portion committed to history after barge-in."""
        from src.twilio.handlers import _generate_response, manager

        stream_sid = "test_drift_partial"
        call_sid = "call_drift"

        conv = ConversationManager()
        conv.add_user_message("Tell me a story")
        manager.conversations[stream_sid] = conv
        manager.stream_to_call[stream_sid] = call_sid

        # Mock streamer that tracks queued audio
        mock_streamer = AsyncMock()
        manager.streamers[call_sid] = mock_streamer

        # Mock TTS that yields payloads
        mock_tts = AsyncMock()

        async def mock_generate(text):
            yield "audio_chunk"

        mock_tts.generate = mock_generate
        manager.tts_stream = mock_tts

        # LLM generates 3 sentences, cancel after first sentence is spoken
        async def slow_llm(messages):
            yield "First sentence. "
            yield "Second sentence. "
            await asyncio.sleep(10)  # Will be cancelled during this wait
            yield "Third sentence."

        mock_llm = AsyncMock()
        mock_llm.generate_streaming = slow_llm
        manager.llm_client = mock_llm

        # Start task and cancel after first sentence
        task = asyncio.create_task(_generate_response(stream_sid, "Tell me a story"))
        manager.response_tasks[stream_sid] = task

        await asyncio.sleep(0.05)  # Let first sentence process
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Check history: should have partial message with [interrupted]
        assistant_msgs = [m for m in conv.history if m["role"] == "assistant"]
        assert len(assistant_msgs) == 1

        msg = assistant_msgs[0]["content"]
        assert "[interrupted]" in msg
        # Should NOT contain "Third sentence" (never generated)
        assert "Third sentence" not in msg

        # Cleanup
        manager.conversations.pop(stream_sid, None)
        manager.stream_to_call.pop(stream_sid, None)
        manager.streamers.pop(call_sid, None)
        manager.tts_stream = None
        manager.llm_client = None
        manager.is_responding.pop(stream_sid, None)
        manager.response_tasks.pop(stream_sid, None)

    @pytest.mark.asyncio
    async def test_full_response_saved_when_no_interrupt(self):
        """Normal case: full response saved without interrupted marker."""
        from src.twilio.handlers import _generate_response, manager

        stream_sid = "test_drift_full"
        call_sid = "call_full"

        conv = ConversationManager()
        conv.add_user_message("Hello")
        manager.conversations[stream_sid] = conv
        manager.stream_to_call[stream_sid] = call_sid
        manager.streamers[call_sid] = None  # Skip TTS

        async def mock_generate(messages):
            yield "Hi there!"

        mock_llm = AsyncMock()
        mock_llm.generate_streaming = mock_generate
        manager.llm_client = mock_llm

        await _generate_response(stream_sid, "Hello")

        assistant_msgs = [m for m in conv.history if m["role"] == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0]["content"] == "Hi there!"
        assert "[interrupted]" not in assistant_msgs[0]["content"]

        # Cleanup
        manager.conversations.pop(stream_sid, None)
        manager.stream_to_call.pop(stream_sid, None)
        manager.streamers.pop(call_sid, None)
        manager.llm_client = None
        manager.is_responding.pop(stream_sid, None)


class TestErrorRecovery:
    """Test error recovery in _generate_response."""

    @pytest.mark.asyncio
    async def test_llm_error_sends_filler(self):
        """LLM failure triggers filler response via TTS."""
        from src.twilio.handlers import _generate_response, manager, FILLER_RESPONSE

        stream_sid = "test_error_filler"
        call_sid = "call_filler"

        conv = ConversationManager()
        conv.add_user_message("Hello")
        manager.conversations[stream_sid] = conv
        manager.stream_to_call[stream_sid] = call_sid

        mock_streamer = AsyncMock()
        manager.streamers[call_sid] = mock_streamer

        # TTS mock tracks what text was synthesized
        synthesized_texts = []
        mock_tts = AsyncMock()

        async def mock_generate(text):
            synthesized_texts.append(text)
            yield "audio_chunk"

        mock_tts.generate = mock_generate
        manager.tts_stream = mock_tts

        # LLM raises an error
        async def failing_llm(messages):
            raise ConnectionError("LLM timeout")
            yield  # Make it an async generator

        mock_llm = AsyncMock()
        mock_llm.generate_streaming = failing_llm
        manager.llm_client = mock_llm

        await _generate_response(stream_sid, "Hello")

        # Filler response should have been sent via TTS
        assert FILLER_RESPONSE in synthesized_texts

        # No assistant message in history (LLM failed)
        assistant_msgs = [m for m in conv.history if m["role"] == "assistant"]
        assert len(assistant_msgs) == 0

        # Cleanup
        manager.conversations.pop(stream_sid, None)
        manager.stream_to_call.pop(stream_sid, None)
        manager.streamers.pop(call_sid, None)
        manager.tts_stream = None
        manager.llm_client = None
        manager.is_responding.pop(stream_sid, None)

    @pytest.mark.asyncio
    async def test_tts_error_continues_call(self):
        """TTS failure for a sentence doesn't crash — call continues."""
        from src.twilio.handlers import _generate_response, manager

        stream_sid = "test_tts_error"
        call_sid = "call_tts_err"

        conv = ConversationManager()
        conv.add_user_message("Hello")
        manager.conversations[stream_sid] = conv
        manager.stream_to_call[stream_sid] = call_sid

        mock_streamer = AsyncMock()
        manager.streamers[call_sid] = mock_streamer

        # TTS that fails
        mock_tts = AsyncMock()

        async def failing_tts(text):
            raise RuntimeError("TTS synthesis failed")
            yield  # Make it an async generator

        mock_tts.generate = failing_tts
        manager.tts_stream = mock_tts

        # LLM succeeds
        async def mock_generate(messages):
            yield "Hello there."

        mock_llm = AsyncMock()
        mock_llm.generate_streaming = mock_generate
        manager.llm_client = mock_llm

        # Should not raise — graceful error handling
        await _generate_response(stream_sid, "Hello")

        # Response still saved to history even if TTS failed
        assistant_msgs = [m for m in conv.history if m["role"] == "assistant"]
        assert len(assistant_msgs) == 1
        assert "Hello there." in assistant_msgs[0]["content"]

        # is_responding reset
        assert manager.is_responding.get(stream_sid) is False

        # Cleanup
        manager.conversations.pop(stream_sid, None)
        manager.stream_to_call.pop(stream_sid, None)
        manager.streamers.pop(call_sid, None)
        manager.tts_stream = None
        manager.llm_client = None
        manager.is_responding.pop(stream_sid, None)
