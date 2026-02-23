"""
Unit tests for LLM client.

Tests API contract and configuration — does NOT require a running vLLM server.
Uses mocking to verify client behavior without network calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.llm.client import LLMClient


def test_llm_client_initialization():
    """Test: LLMClient initializes with default settings"""
    client = LLMClient()
    assert client.model is not None
    assert client.max_tokens > 0
    assert 0 < client.temperature <= 2.0
    assert client.client is not None


def test_llm_client_custom_config():
    """Test: LLMClient accepts custom configuration"""
    client = LLMClient(
        base_url="http://custom:9000/v1",
        api_key="test-key",
        model="test-model",
        max_tokens=100,
        temperature=0.5,
    )
    assert client.model == "test-model"
    assert client.max_tokens == 100
    assert client.temperature == 0.5


@pytest.mark.asyncio
async def test_generate_streaming_yields_tokens():
    """Test: generate_streaming() yields string tokens"""
    client = LLMClient()

    # Create mock async iterator for streaming chunks
    mock_chunk_1 = MagicMock()
    mock_chunk_1.choices = [MagicMock()]
    mock_chunk_1.choices[0].delta.content = "Hello"

    mock_chunk_2 = MagicMock()
    mock_chunk_2.choices = [MagicMock()]
    mock_chunk_2.choices[0].delta.content = " world"

    # Create an async iterable that yields our chunks
    async def mock_stream():
        yield mock_chunk_1
        yield mock_chunk_2

    with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_stream()

        messages = [{"role": "user", "content": "Hi"}]
        tokens = []
        async for token in client.generate_streaming(messages):
            tokens.append(token)

        assert len(tokens) == 2
        assert tokens[0] == "Hello"
        assert tokens[1] == " world"


@pytest.mark.asyncio
async def test_generate_returns_complete_response():
    """Test: generate() returns complete string"""
    client = LLMClient()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello world"

    with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response

        messages = [{"role": "user", "content": "Hi"}]
        result = await client.generate(messages)

        assert result == "Hello world"
        mock_create.assert_called_once()
