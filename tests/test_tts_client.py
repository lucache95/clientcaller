"""
Unit tests for TTS client.

Tests API contract and configuration — does NOT require network calls.
Uses mocking to verify client behavior without hitting edge-tts service.
"""

import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from src.tts.client import TTSClient
from src.tts.config import TTSConfig


def test_tts_config_defaults():
    """Test: TTSConfig has sensible defaults"""
    config = TTSConfig()
    assert config.engine == "edge"
    assert config.voice == "en-US-AriaNeural"
    assert config.sample_rate == 24000


def test_tts_client_initialization():
    """Test: TTSClient initializes with default config"""
    client = TTSClient()
    assert client.config.engine == "edge"
    assert client.config.voice == "en-US-AriaNeural"


def test_tts_client_custom_config():
    """Test: TTSClient accepts custom configuration"""
    config = TTSConfig(voice="en-US-GuyNeural", rate="+10%")
    client = TTSClient(config=config)
    assert client.config.voice == "en-US-GuyNeural"
    assert client.config.rate == "+10%"


@pytest.mark.asyncio
async def test_synthesize_yields_pcm_chunks():
    """Test: synthesize() yields int16 numpy arrays"""
    client = TTSClient()

    # Create mock audio data (valid MP3-like response)
    # We mock _decode_mp3_to_pcm to return known PCM data
    fake_pcm = np.zeros(4800, dtype=np.int16)

    mock_chunk_audio = {"type": "audio", "data": b"\xff" * 5000}

    async def mock_stream():
        yield mock_chunk_audio

    with patch("edge_tts.Communicate") as MockCommunicate:
        mock_instance = MagicMock()
        mock_instance.stream = mock_stream
        MockCommunicate.return_value = mock_instance

        with patch.object(client, "_decode_mp3_to_pcm", return_value=fake_pcm):
            chunks = []
            async for chunk in client.synthesize("Hello world"):
                chunks.append(chunk)

            assert len(chunks) >= 1
            for chunk in chunks:
                assert isinstance(chunk, np.ndarray)
                assert chunk.dtype == np.int16


@pytest.mark.asyncio
async def test_synthesize_empty_text():
    """Test: synthesize() yields nothing for empty text"""
    client = TTSClient()

    chunks = []
    async for chunk in client.synthesize(""):
        chunks.append(chunk)

    assert len(chunks) == 0


@pytest.mark.asyncio
async def test_synthesize_streaming_collects_sentences():
    """Test: synthesize_streaming() synthesizes sentence by sentence"""
    client = TTSClient()

    synthesized_texts = []
    original_synthesize = client.synthesize

    async def mock_synthesize(text):
        synthesized_texts.append(text)
        yield np.zeros(100, dtype=np.int16)

    client.synthesize = mock_synthesize

    async def token_stream():
        for token in ["Hello", " world", ".", " How", " are", " you", "?"]:
            yield token

    chunks = []
    async for chunk in client.synthesize_streaming(token_stream()):
        chunks.append(chunk)

    # Should have synthesized 2 sentences: "Hello world." and "How are you?"
    assert len(synthesized_texts) == 2
    assert synthesized_texts[0] == "Hello world."
    assert synthesized_texts[1] == "How are you?"


@pytest.mark.asyncio
async def test_synthesize_streaming_flushes_remaining():
    """Test: synthesize_streaming() flushes text without sentence ending"""
    client = TTSClient()

    synthesized_texts = []

    async def mock_synthesize(text):
        synthesized_texts.append(text)
        yield np.zeros(100, dtype=np.int16)

    client.synthesize = mock_synthesize

    async def token_stream():
        for token in ["Hello", " world"]:
            yield token

    chunks = []
    async for chunk in client.synthesize_streaming(token_stream()):
        chunks.append(chunk)

    # Should flush "Hello world" even without sentence ending
    assert len(synthesized_texts) == 1
    assert synthesized_texts[0] == "Hello world"
