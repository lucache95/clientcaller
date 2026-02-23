"""Tests for barge-in detection infrastructure (Phase 5 Plan 01)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


async def _fake_to_thread(fn, *args):
    """Replace asyncio.to_thread in tests — just call the function directly."""
    result = fn(*args)
    if asyncio.iscoroutine(result):
        return await result
    return result


class TestInterruptEventManagement:
    """Test per-call interrupt event creation and cleanup."""

    def test_interrupt_event_created_per_call(self):
        """Interrupt event is created on first access for a stream_sid."""
        from src.twilio.handlers import ConnectionManager

        mgr = ConnectionManager()
        event = mgr.get_interrupt_event("stream_001")

        assert isinstance(event, asyncio.Event)
        assert not event.is_set()

    def test_interrupt_event_reused_for_same_call(self):
        """Same event returned for same stream_sid."""
        from src.twilio.handlers import ConnectionManager

        mgr = ConnectionManager()
        event1 = mgr.get_interrupt_event("stream_001")
        event2 = mgr.get_interrupt_event("stream_001")

        assert event1 is event2

    def test_separate_events_per_call(self):
        """Different calls get different interrupt events."""
        from src.twilio.handlers import ConnectionManager

        mgr = ConnectionManager()
        event1 = mgr.get_interrupt_event("stream_001")
        event2 = mgr.get_interrupt_event("stream_002")

        assert event1 is not event2

    def test_set_responding_flag(self):
        """is_responding flag tracks AI response state."""
        from src.twilio.handlers import ConnectionManager

        mgr = ConnectionManager()
        mgr.set_responding("stream_001", True)
        assert mgr.is_responding["stream_001"] is True

        mgr.set_responding("stream_001", False)
        assert mgr.is_responding["stream_001"] is False


class TestBargeInDetection:
    """Test that speech during AI response triggers barge-in."""

    @pytest.mark.asyncio
    async def test_barge_in_triggers_interrupt_handler(self):
        """Speech detected while AI is responding triggers the interrupt handler."""
        from src.twilio.handlers import manager, handle_media

        stream_sid = "test_stream_barge"

        # Setup: AI is responding
        manager.is_responding[stream_sid] = True
        manager.get_interrupt_event(stream_sid)

        # Mock VAD to return speech
        mock_vad = MagicMock()
        mock_vad.process_chunk.return_value = {
            "is_speech": True,
            "turn_complete": False,
            "speech_probability": 0.9,
            "silence_duration_ms": 0,
            "speech_duration_ms": 100,
        }
        manager.vad_detectors[stream_sid] = mock_vad

        # Mock STT
        mock_stt = MagicMock()
        mock_stt.process_audio_chunk.return_value = []
        manager.stt_processor = mock_stt

        # Build a minimal media message
        import base64
        payload = base64.b64encode(b"\x00" * 160).decode()
        data = {"media": {"payload": payload}, "streamSid": stream_sid}

        with patch("src.twilio.handlers.mulaw_to_pcm", return_value=b"\x00" * 320), \
             patch("src.twilio.handlers.resample_8k_to_16k") as mock_resample, \
             patch("src.twilio.handlers.asyncio.to_thread", side_effect=_fake_to_thread), \
             patch("src.twilio.handlers._handle_interrupt", new_callable=AsyncMock) as mock_interrupt:
            import numpy as np
            mock_resample.return_value = np.zeros(512, dtype=np.int16)
            await handle_media(AsyncMock(), data)

        # Verify interrupt handler was called
        mock_interrupt.assert_awaited_once()
        call_args = mock_interrupt.call_args
        assert call_args[0][1] == stream_sid  # stream_sid is second arg

        # Cleanup
        manager.vad_detectors.pop(stream_sid, None)
        manager.is_responding.pop(stream_sid, None)
        manager.interrupt_events.pop(stream_sid, None)
        manager.stt_processor = None

    @pytest.mark.asyncio
    async def test_no_barge_in_when_not_responding(self):
        """Speech during listening mode does NOT set interrupt event."""
        from src.twilio.handlers import manager, handle_media

        stream_sid = "test_stream_no_barge"

        # Setup: AI is NOT responding
        manager.is_responding[stream_sid] = False
        event = manager.get_interrupt_event(stream_sid)

        # Mock VAD to return speech
        mock_vad = MagicMock()
        mock_vad.process_chunk.return_value = {
            "is_speech": True,
            "turn_complete": False,
            "speech_probability": 0.9,
            "silence_duration_ms": 0,
            "speech_duration_ms": 100,
        }
        manager.vad_detectors[stream_sid] = mock_vad

        mock_stt = MagicMock()
        mock_stt.process_audio_chunk.return_value = []
        manager.stt_processor = mock_stt

        import base64
        payload = base64.b64encode(b"\x00" * 160).decode()
        data = {"media": {"payload": payload}, "streamSid": stream_sid}

        with patch("src.twilio.handlers.mulaw_to_pcm", return_value=b"\x00" * 320), \
             patch("src.twilio.handlers.resample_8k_to_16k") as mock_resample, \
             patch("src.twilio.handlers.asyncio.to_thread", side_effect=_fake_to_thread):
            import numpy as np
            mock_resample.return_value = np.zeros(512, dtype=np.int16)
            await handle_media(AsyncMock(), data)

        assert not event.is_set()

        # Cleanup
        manager.vad_detectors.pop(stream_sid, None)
        manager.is_responding.pop(stream_sid, None)
        manager.interrupt_events.pop(stream_sid, None)
        manager.stt_processor = None

    @pytest.mark.asyncio
    async def test_interrupt_event_cleanup_on_stop(self):
        """Interrupt state is cleaned up when call stops."""
        from src.twilio.handlers import manager, handle_stop

        stream_sid = "test_stream_cleanup"
        call_sid = "test_call_cleanup"

        # Setup state
        manager.interrupt_events[stream_sid] = asyncio.Event()
        manager.is_responding[stream_sid] = True
        manager.stream_to_call[stream_sid] = call_sid

        data = {"stop": {"callSid": call_sid, "streamSid": stream_sid}}

        with patch("src.twilio.handlers.state_manager") as mock_sm:
            mock_sm.on_stop = AsyncMock()
            mock_sm.cleanup = AsyncMock()
            await handle_stop(AsyncMock(), data)

        assert stream_sid not in manager.interrupt_events
        assert stream_sid not in manager.is_responding


class TestResponseTask:
    """Test that response pipeline runs as a cancellable task."""

    @pytest.mark.asyncio
    async def test_response_task_sets_responding(self):
        """_generate_response sets is_responding True then False."""
        from src.twilio.handlers import _generate_response, manager

        stream_sid = "test_stream_task"

        # Setup mocks
        manager.conversations[stream_sid] = MagicMock()
        manager.conversations[stream_sid].get_messages.return_value = [
            {"role": "user", "content": "hello"}
        ]
        manager.conversations[stream_sid].get_turn_count.return_value = 1

        mock_llm = AsyncMock()

        async def mock_generate(messages):
            # Verify responding is True during generation
            assert manager.is_responding.get(stream_sid) is True
            yield "Hello!"

        mock_llm.generate_streaming = mock_generate
        manager.llm_client = mock_llm
        manager.stream_to_call[stream_sid] = "call_001"
        manager.streamers["call_001"] = None  # No streamer = skip TTS

        await _generate_response(stream_sid, "hello")

        assert manager.is_responding.get(stream_sid) is False

        # Cleanup
        manager.conversations.pop(stream_sid, None)
        manager.stream_to_call.pop(stream_sid, None)
        manager.streamers.pop("call_001", None)
        manager.llm_client = None
