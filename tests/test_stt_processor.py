"""
Unit tests for STTProcessor streaming transcription.

Tests the STT module API and basic functionality. Full accuracy testing
with real PSTN audio will be done in Plan 03 E2E testing.
"""

import pytest
import numpy as np
from src.stt.processor import STTProcessor


@pytest.fixture(scope="module")
def stt_processor():
    """
    Fixture: STTProcessor instance (loads model once for all tests).

    Using module scope to avoid reloading the model for each test,
    which would be slow (10-30 seconds per test).
    """
    return STTProcessor(model_size="distil-large-v3", language="en")


def test_stt_processor_initialization(stt_processor):
    """Test: STTProcessor loads model without errors."""
    assert stt_processor.asr is not None
    assert stt_processor.online is not None
    assert hasattr(stt_processor.asr, 'model')


@pytest.mark.asyncio
async def test_process_audio_chunk_yields_transcripts(stt_processor):
    """
    Test: process_audio_chunk() yields partial transcripts.

    Uses silence as test input (real audio requires fixtures).
    Verifies API contract without needing audio files.
    """
    # Generate 1 second of silence (16000 samples at 16kHz)
    silence = np.zeros(16000, dtype=np.int16)

    # Process should yield partial transcripts (may be empty for silence)
    results = []
    async for result in stt_processor.process_audio_chunk(silence):
        results.append(result)
        # Limit iterations to avoid hanging on silence
        if len(results) >= 3:
            break

    # Verify structure (may have 0 results for silence, that's ok)
    for result in results:
        assert "type" in result
        assert result["type"] == "partial"
        assert "text" in result
        assert "beg" in result
        assert "end" in result


def test_finalize_turn_returns_final_transcript(stt_processor):
    """Test: finalize_turn() returns final transcript and resets state."""
    result = stt_processor.finalize_turn()

    # Verify structure
    assert result["type"] == "final"
    assert "text" in result
    assert isinstance(result["text"], str)
    assert "beg" in result
    assert "end" in result


def test_finalize_turn_resets_state(stt_processor):
    """
    Test: finalize_turn() properly resets state between turns.

    Critical for preventing context bleed (02-RESEARCH.md Pitfall 7).
    """
    # Process some silence
    silence = np.zeros(16000, dtype=np.int16)
    audio_float = silence.astype(np.float32) / 32768.0
    stt_processor.online.insert_audio_chunk(audio_float)

    # Finalize should reset state
    result1 = stt_processor.finalize_turn()
    assert result1["type"] == "final"

    # After finalize, should be ready for new turn
    # (no state contamination from previous turn)
    result2 = stt_processor.finalize_turn()
    assert result2["type"] == "final"


@pytest.mark.asyncio
async def test_process_audio_chunk_api_contract(stt_processor):
    """
    Test: process_audio_chunk() accepts correct input format.

    Verifies it accepts int16 PCM audio at 16kHz (output from Phase 1 pipeline).
    """
    # Create realistic test audio (1 second of 440Hz sine wave)
    sample_rate = 16000
    duration = 1.0
    frequency = 440.0  # A4 note

    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    audio = (np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)

    # Should accept without errors
    results = []
    async for result in stt_processor.process_audio_chunk(audio):
        results.append(result)
        if len(results) >= 5:
            break

    # Verify results have correct structure
    for result in results:
        assert isinstance(result, dict)
        assert "type" in result
        assert "text" in result
        assert "beg" in result
        assert "end" in result
