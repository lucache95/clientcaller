"""
Unit tests for TTS streaming pipeline.

Tests the conversion pipeline from TTS PCM output to Twilio mu-law base64.
Uses mocking to avoid actual TTS synthesis.
"""

import base64
import pytest
import numpy as np
from unittest.mock import patch, AsyncMock, MagicMock
from src.tts.stream import TTSStream, resample_to_8k, TWILIO_CHUNK_SAMPLES


def test_resample_to_8k():
    """Test: resample_to_8k converts 24kHz to 8kHz"""
    # 24000 samples at 24kHz = 1 second
    audio_24k = np.zeros(24000, dtype=np.int16)
    audio_8k = resample_to_8k(audio_24k, orig_sr=24000)
    # Should be ~8000 samples (1 second at 8kHz)
    assert abs(len(audio_8k) - 8000) < 10  # Allow small rounding


def test_resample_to_8k_noop():
    """Test: resample_to_8k passes through 8kHz audio unchanged"""
    audio_8k = np.ones(160, dtype=np.int16)
    result = resample_to_8k(audio_8k, orig_sr=8000)
    np.testing.assert_array_equal(result, audio_8k)


def test_pcm_to_twilio_payloads():
    """Test: _pcm_to_twilio_payloads produces valid base64 strings"""
    stream = TTSStream()
    # 2400 samples at 24kHz = 100ms → should produce ~800 samples at 8kHz → 5 chunks
    pcm_24k = np.random.randint(-1000, 1000, size=2400, dtype=np.int16)
    payloads = stream._pcm_to_twilio_payloads(pcm_24k)

    assert len(payloads) > 0
    for payload in payloads:
        assert isinstance(payload, str)
        # Should be valid base64
        decoded = base64.b64decode(payload)
        assert len(decoded) > 0


@pytest.mark.asyncio
async def test_generate_yields_base64_payloads():
    """Test: generate() yields base64 mu-law payloads"""
    stream = TTSStream()

    fake_pcm = np.random.randint(-1000, 1000, size=2400, dtype=np.int16)

    async def mock_synthesize(text):
        yield fake_pcm

    with patch.object(stream.tts_client, "synthesize", side_effect=mock_synthesize):
        payloads = []
        async for payload in stream.generate("Hello"):
            payloads.append(payload)

        assert len(payloads) > 0
        for payload in payloads:
            assert isinstance(payload, str)
            # Verify valid base64
            base64.b64decode(payload)


@pytest.mark.asyncio
async def test_generate_streaming_yields_payloads():
    """Test: generate_streaming() accepts text stream and yields payloads"""
    stream = TTSStream()

    fake_pcm = np.random.randint(-1000, 1000, size=2400, dtype=np.int16)

    async def mock_synthesize_streaming(text_stream):
        yield fake_pcm

    with patch.object(
        stream.tts_client, "synthesize_streaming", side_effect=mock_synthesize_streaming
    ):

        async def token_stream():
            yield "Hello world."

        payloads = []
        async for payload in stream.generate_streaming(token_stream()):
            payloads.append(payload)

        assert len(payloads) > 0


@pytest.mark.asyncio
async def test_generate_empty_text():
    """Test: generate() handles empty text gracefully"""
    stream = TTSStream()

    async def mock_synthesize(text):
        return
        yield  # make it an async generator

    with patch.object(stream.tts_client, "synthesize", side_effect=mock_synthesize):
        payloads = []
        async for payload in stream.generate(""):
            payloads.append(payload)

        assert len(payloads) == 0
