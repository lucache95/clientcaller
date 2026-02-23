"""
LLM client for streaming text generation via OpenAI-compatible API.

Works with vLLM, RunPod, or any OpenAI-compatible endpoint.
Uses AsyncOpenAI for non-blocking streaming in FastAPI.
"""

import logging
from typing import AsyncGenerator, List, Dict, Optional
from openai import AsyncOpenAI
from src.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Async LLM client for streaming chat completions.

    Uses the OpenAI-compatible API to talk to vLLM, RunPod, or OpenAI.
    Streams tokens one-by-one for minimum latency.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        self.model = model or settings.llm_model
        self.max_tokens = max_tokens or settings.llm_max_tokens
        self.temperature = temperature or settings.llm_temperature

        self.client = AsyncOpenAI(
            api_key=api_key or settings.llm_api_key,
            base_url=base_url or settings.llm_base_url,
        )

        logger.info(f"LLMClient initialized: model={self.model}, base_url={base_url or settings.llm_base_url}")

    async def generate_streaming(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from the LLM.

        Args:
            messages: Chat messages in OpenAI format
                [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            max_tokens: Override default max tokens
            temperature: Override default temperature

        Yields:
            str: Individual text tokens as they're generated
        """
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            raise

    async def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Generate a complete (non-streaming) response.

        Args:
            messages: Chat messages in OpenAI format
            max_tokens: Override default max tokens
            temperature: Override default temperature

        Returns:
            str: Complete response text
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            raise
