"""Tests for interrupt handling (Phase 5 Plan 02)."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


async def _fake_to_thread(fn, *args):
    """Replace asyncio.to_thread in tests."""
    result = fn(*args)
    if asyncio.iscoroutine(result):
        return await result
    return result


class TestHandleInterrupt:
    """Test the _handle_interrupt function."""

    @pytest.mark.asyncio
    async def test_interrupt_cancels_response_task(self):
        """Response task gets cancelled on interrupt."""
        from src.twilio.handlers import _handle_interrupt, manager

        stream_sid = "test_interrupt_cancel"

        # Create a long-running task
        async def slow_task():
            await asyncio.sleep(10)

        task = asyncio.create_task(slow_task())
        manager.response_tasks[stream_sid] = task
        manager.is_responding[stream_sid] = True
        manager.interrupt_events[stream_sid] = asyncio.Event()
        manager.interrupt_events[stream_sid].set()

        # Mock websocket and streamer
        mock_ws = AsyncMock()
        manager.stream_to_call[stream_sid] = "call_001"
        mock_streamer = AsyncMock()
        manager.streamers["call_001"] = mock_streamer

        # Mock VAD
        mock_vad = MagicMock()
        manager.vad_detectors[stream_sid] = mock_vad

        await _handle_interrupt(mock_ws, stream_sid)

        assert task.cancelled()

        # Cleanup
        manager.response_tasks.pop(stream_sid, None)
        manager.is_responding.pop(stream_sid, None)
        manager.interrupt_events.pop(stream_sid, None)
        manager.stream_to_call.pop(stream_sid, None)
        manager.streamers.pop("call_001", None)
        manager.vad_detectors.pop(stream_sid, None)

    @pytest.mark.asyncio
    async def test_interrupt_clears_audio_queue(self):
        """Audio queue is cleared on interrupt."""
        from src.twilio.handlers import _handle_interrupt, manager

        stream_sid = "test_interrupt_queue"
        call_sid = "call_queue"

        manager.stream_to_call[stream_sid] = call_sid
        mock_streamer = AsyncMock()
        manager.streamers[call_sid] = mock_streamer
        manager.is_responding[stream_sid] = True
        manager.interrupt_events[stream_sid] = asyncio.Event()
        manager.interrupt_events[stream_sid].set()

        mock_vad = MagicMock()
        manager.vad_detectors[stream_sid] = mock_vad

        await _handle_interrupt(AsyncMock(), stream_sid)

        mock_streamer.clear_queue.assert_awaited_once()

        # Cleanup
        manager.stream_to_call.pop(stream_sid, None)
        manager.streamers.pop(call_sid, None)
        manager.is_responding.pop(stream_sid, None)
        manager.interrupt_events.pop(stream_sid, None)
        manager.vad_detectors.pop(stream_sid, None)

    @pytest.mark.asyncio
    async def test_interrupt_sends_twilio_clear(self):
        """Twilio 'clear' message is sent on interrupt."""
        from src.twilio.handlers import _handle_interrupt, manager

        stream_sid = "test_interrupt_clear"

        manager.is_responding[stream_sid] = True
        manager.interrupt_events[stream_sid] = asyncio.Event()
        manager.interrupt_events[stream_sid].set()

        mock_vad = MagicMock()
        manager.vad_detectors[stream_sid] = mock_vad

        mock_ws = AsyncMock()
        await _handle_interrupt(mock_ws, stream_sid)

        # Verify clear message was sent
        mock_ws.send_text.assert_awaited_once()
        sent_msg = json.loads(mock_ws.send_text.call_args[0][0])
        assert sent_msg["event"] == "clear"
        assert sent_msg["streamSid"] == stream_sid

        # Cleanup
        manager.is_responding.pop(stream_sid, None)
        manager.interrupt_events.pop(stream_sid, None)
        manager.vad_detectors.pop(stream_sid, None)

    @pytest.mark.asyncio
    async def test_interrupt_resets_state(self):
        """is_responding=False and interrupt_event cleared after interrupt."""
        from src.twilio.handlers import _handle_interrupt, manager

        stream_sid = "test_interrupt_reset"

        manager.is_responding[stream_sid] = True
        event = asyncio.Event()
        event.set()
        manager.interrupt_events[stream_sid] = event

        mock_vad = MagicMock()
        manager.vad_detectors[stream_sid] = mock_vad

        await _handle_interrupt(AsyncMock(), stream_sid)

        assert manager.is_responding[stream_sid] is False
        assert not event.is_set()

        # Cleanup
        manager.is_responding.pop(stream_sid, None)
        manager.interrupt_events.pop(stream_sid, None)
        manager.vad_detectors.pop(stream_sid, None)

    @pytest.mark.asyncio
    async def test_new_response_after_interrupt(self):
        """Can start a new response task after interruption."""
        from src.twilio.handlers import _handle_interrupt, _generate_response, manager

        stream_sid = "test_interrupt_new"
        call_sid = "call_new"

        # Setup interrupt state
        manager.is_responding[stream_sid] = True
        manager.interrupt_events[stream_sid] = asyncio.Event()
        manager.interrupt_events[stream_sid].set()
        manager.stream_to_call[stream_sid] = call_sid

        mock_vad = MagicMock()
        manager.vad_detectors[stream_sid] = mock_vad

        await _handle_interrupt(AsyncMock(), stream_sid)

        # Now setup for a new response
        manager.conversations[stream_sid] = MagicMock()
        manager.conversations[stream_sid].get_messages.return_value = [
            {"role": "user", "content": "new question"}
        ]
        manager.conversations[stream_sid].get_turn_count.return_value = 2

        async def mock_generate(messages):
            yield "New response!"

        mock_llm = AsyncMock()
        mock_llm.generate_streaming = mock_generate
        manager.llm_client = mock_llm
        manager.streamers[call_sid] = None  # Skip TTS

        # Should succeed without error
        await _generate_response(stream_sid, "new question")
        assert manager.is_responding.get(stream_sid) is False

        # Cleanup
        manager.conversations.pop(stream_sid, None)
        manager.stream_to_call.pop(stream_sid, None)
        manager.streamers.pop(call_sid, None)
        manager.is_responding.pop(stream_sid, None)
        manager.interrupt_events.pop(stream_sid, None)
        manager.llm_client = None
        manager.vad_detectors.pop(stream_sid, None)

    @pytest.mark.asyncio
    async def test_response_handles_cancellation_gracefully(self):
        """Response task handles CancelledError without crashing."""
        from src.twilio.handlers import _generate_response, manager

        stream_sid = "test_cancel_grace"
        call_sid = "call_grace"

        manager.conversations[stream_sid] = MagicMock()
        manager.conversations[stream_sid].get_messages.return_value = [
            {"role": "user", "content": "hello"}
        ]
        manager.stream_to_call[stream_sid] = call_sid
        manager.streamers[call_sid] = None

        async def slow_generate(messages):
            yield "Hello"
            yield " there"
            await asyncio.sleep(10)  # Will be cancelled here
            yield " friend"

        mock_llm = AsyncMock()
        mock_llm.generate_streaming = slow_generate
        manager.llm_client = mock_llm

        # Start as task and cancel quickly
        task = asyncio.create_task(_generate_response(stream_sid, "hello"))
        manager.response_tasks[stream_sid] = task

        await asyncio.sleep(0.01)  # Let it start
        task.cancel()

        # Should not raise — graceful handling
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected if cancel happens before try/except catches it

        assert manager.is_responding.get(stream_sid) is False

        # Cleanup
        manager.conversations.pop(stream_sid, None)
        manager.stream_to_call.pop(stream_sid, None)
        manager.streamers.pop(call_sid, None)
        manager.is_responding.pop(stream_sid, None)
        manager.response_tasks.pop(stream_sid, None)
        manager.llm_client = None
