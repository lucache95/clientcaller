"""
TTS client for streaming speech synthesis.

Uses edge-tts for CPU/dev environments (high quality, free, async streaming).
CSM support planned for GPU/production deployment.

Edge TTS streams MP3 chunks over WebSocket from Microsoft's TTS service.
We decode to PCM and yield numpy arrays for downstream processing.
"""

import io
import logging
from typing import AsyncGenerator, Optional

import numpy as np
from pydub import AudioSegment
import edge_tts

from src.tts.config import TTSConfig

logger = logging.getLogger(__name__)


class TTSClient:
    """
    Async TTS client with streaming audio generation.

    Accepts text, synthesizes speech via edge-tts, yields PCM audio chunks
    at the engine's native sample rate (24kHz for edge-tts).

    Caller handles resampling and format conversion to Twilio's mu-law 8kHz.
    """

    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        logger.info(
            f"TTSClient initialized: engine={self.config.engine}, "
            f"voice={self.config.voice}"
        )

    async def synthesize(self, text: str) -> AsyncGenerator[np.ndarray, None]:
        """
        Synthesize text to speech, yielding PCM audio chunks.

        Streams audio from edge-tts, decodes MP3 chunks, yields PCM int16
        numpy arrays at 24kHz mono.

        Args:
            text: Text to synthesize

        Yields:
            numpy array of int16 PCM samples at 24kHz
        """
        if not text or not text.strip():
            return

        communicate = edge_tts.Communicate(
            text,
            self.config.voice,
            rate=self.config.rate,
            volume=self.config.volume,
        )

        # Accumulate MP3 data and decode in chunks for streaming
        # Edge-tts sends small MP3 frames (~720 bytes each)
        # We accumulate enough for reliable MP3 decoding then yield
        mp3_buffer = b""
        chunk_threshold = 4800  # ~4.8KB of MP3 ≈ ~200ms of audio

        async for chunk in communicate.stream():
            if chunk["type"] != "audio":
                continue

            mp3_buffer += chunk["data"]

            if len(mp3_buffer) >= chunk_threshold:
                pcm_chunk = self._decode_mp3_to_pcm(mp3_buffer)
                if pcm_chunk is not None and len(pcm_chunk) > 0:
                    yield pcm_chunk
                mp3_buffer = b""

        # Flush remaining buffer
        if mp3_buffer:
            pcm_chunk = self._decode_mp3_to_pcm(mp3_buffer)
            if pcm_chunk is not None and len(pcm_chunk) > 0:
                yield pcm_chunk

    async def synthesize_streaming(
        self, text_stream: AsyncGenerator[str, None]
    ) -> AsyncGenerator[np.ndarray, None]:
        """
        Synthesize streaming text input to speech.

        Collects LLM tokens into sentence-sized chunks, synthesizes each
        sentence as soon as it's complete for minimum latency.

        Args:
            text_stream: Async generator yielding text tokens (e.g., from LLM)

        Yields:
            numpy array of int16 PCM samples at 24kHz
        """
        sentence_buffer = ""
        sentence_endings = {".", "!", "?", "\n"}

        async for token in text_stream:
            sentence_buffer += token

            # Check if we have a complete sentence
            if any(sentence_buffer.rstrip().endswith(end) for end in sentence_endings):
                text = sentence_buffer.strip()
                if text:
                    async for chunk in self.synthesize(text):
                        yield chunk
                sentence_buffer = ""

        # Flush remaining text
        if sentence_buffer.strip():
            async for chunk in self.synthesize(sentence_buffer.strip()):
                yield chunk

    def _decode_mp3_to_pcm(self, mp3_data: bytes) -> Optional[np.ndarray]:
        """
        Decode MP3 bytes to PCM int16 numpy array.

        Args:
            mp3_data: Raw MP3 bytes

        Returns:
            numpy array of int16 PCM samples, or None if decode fails
        """
        try:
            audio = AudioSegment.from_mp3(io.BytesIO(mp3_data))
            # Ensure mono 16-bit
            audio = audio.set_channels(1).set_sample_width(2)
            samples = np.array(audio.get_array_of_samples(), dtype=np.int16)
            return samples
        except Exception as e:
            logger.warning(f"MP3 decode failed (may need more data): {e}")
            return None
