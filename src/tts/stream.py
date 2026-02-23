"""
TTS-to-Twilio streaming pipeline.

Converts TTSClient PCM output (24kHz int16) to Twilio's format:
24kHz PCM → 8kHz PCM → mu-law → base64

Yields base64 payloads ready for AudioStreamer.queue_audio().
"""

import logging
from typing import AsyncGenerator, Optional

import numpy as np
import librosa

from src.tts.client import TTSClient
from src.tts.config import TTSConfig
from src.audio.conversion import pcm_to_mulaw

import base64

logger = logging.getLogger(__name__)

# Twilio expects 20ms chunks at 8kHz = 160 samples per chunk
TWILIO_CHUNK_SAMPLES = 160
TWILIO_SAMPLE_RATE = 8000
TTS_SAMPLE_RATE = 24000


def resample_to_8k(audio: np.ndarray, orig_sr: int) -> np.ndarray:
    """Resample audio from any sample rate to 8kHz for Twilio."""
    if orig_sr == TWILIO_SAMPLE_RATE:
        return audio
    resampled = librosa.resample(
        audio.astype(np.float32),
        orig_sr=orig_sr,
        target_sr=TWILIO_SAMPLE_RATE,
        res_type="kaiser_fast",
    )
    return resampled.astype(np.int16)


class TTSStream:
    """
    Streaming pipeline: text → TTS → resampled PCM → mu-law base64.

    Produces payloads ready to send to Twilio via AudioStreamer.
    Each payload is one 20ms chunk of base64-encoded mu-law audio.
    """

    def __init__(self, config: Optional[TTSConfig] = None):
        self.tts_client = TTSClient(config=config)
        self.config = self.tts_client.config

    async def generate(self, text: str) -> AsyncGenerator[str, None]:
        """
        Synthesize text and yield Twilio-ready base64 mu-law payloads.

        Args:
            text: Text to synthesize

        Yields:
            str: Base64-encoded mu-law audio payloads (20ms chunks)
        """
        async for pcm_chunk in self.tts_client.synthesize(text):
            for payload in self._pcm_to_twilio_payloads(pcm_chunk):
                yield payload

    async def generate_streaming(
        self, text_stream: AsyncGenerator[str, None]
    ) -> AsyncGenerator[str, None]:
        """
        Synthesize streaming text and yield Twilio-ready payloads.

        Args:
            text_stream: Async generator yielding text tokens (from LLM)

        Yields:
            str: Base64-encoded mu-law audio payloads (20ms chunks)
        """
        async for pcm_chunk in self.tts_client.synthesize_streaming(text_stream):
            for payload in self._pcm_to_twilio_payloads(pcm_chunk):
                yield payload

    def _pcm_to_twilio_payloads(self, pcm_24k: np.ndarray) -> list[str]:
        """
        Convert a PCM chunk at TTS sample rate to Twilio base64 mu-law payloads.

        Pipeline: 24kHz PCM → 8kHz PCM → split into 20ms chunks → mu-law → base64

        Args:
            pcm_24k: int16 numpy array at TTS sample rate

        Returns:
            List of base64-encoded mu-law payloads (one per 20ms chunk)
        """
        # Resample to 8kHz
        pcm_8k = resample_to_8k(pcm_24k, self.config.sample_rate)

        # Split into 20ms Twilio chunks
        payloads = []
        for i in range(0, len(pcm_8k), TWILIO_CHUNK_SAMPLES):
            chunk = pcm_8k[i : i + TWILIO_CHUNK_SAMPLES]

            # Pad last chunk if needed
            if len(chunk) < TWILIO_CHUNK_SAMPLES:
                chunk = np.pad(chunk, (0, TWILIO_CHUNK_SAMPLES - len(chunk)))

            chunk = chunk.astype(np.int16)
            mulaw_bytes = pcm_to_mulaw(chunk, sample_rate=TWILIO_SAMPLE_RATE)
            payload = base64.b64encode(mulaw_bytes).decode("utf-8")
            payloads.append(payload)

        return payloads
