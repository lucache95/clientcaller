"""
CSM (Conversational Speech Model) TTS client for GPU production.

Uses HuggingFace transformers CsmForConditionalGeneration for high-quality
conversational speech synthesis. Outputs 24kHz PCM — same downstream pipeline
as edge-tts (resample to 8kHz mu-law for Twilio).

Speaker conditioning: maintains a rolling context of recent speech segments
for voice consistency within a call.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import AsyncGenerator, List, Optional

import numpy as np
import torch

from src.tts.config import TTSConfig

logger = logging.getLogger(__name__)


@dataclass
class SpeechSegment:
    """A segment of speech for CSM context conditioning."""
    speaker: int
    text: str
    audio: torch.Tensor  # 1D tensor at 24kHz


class CSMTTSClient:
    """
    CSM-based TTS client for GPU environments.

    Same interface as TTSClient (synthesize yields numpy int16 at 24kHz).
    Uses HuggingFace transformers for model loading and inference.
    """

    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig(engine="csm")
        self.model = None
        self.processor = None
        self._context_segments: List[SpeechSegment] = []
        self._max_context = 3
        logger.info(
            f"CSMTTSClient initialized: speaker_id={self.config.csm_speaker_id}"
        )

    def load_model(self, device: str = "cuda"):
        """
        Load CSM model onto GPU. Called once at startup.

        Args:
            device: Target device ("cuda" or "cpu")
        """
        from transformers import CsmForConditionalGeneration, AutoProcessor

        model_id = "sesame/csm-1b"
        logger.info(f"Loading CSM model: {model_id} on {device}")

        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = CsmForConditionalGeneration.from_pretrained(
            model_id, device_map=device
        )
        self.model.eval()
        logger.info("CSM model loaded successfully")

    def is_loaded(self) -> bool:
        """Check if model is loaded and ready."""
        return self.model is not None and self.processor is not None

    async def synthesize(self, text: str) -> AsyncGenerator[np.ndarray, None]:
        """
        Synthesize text to speech, yielding PCM audio chunks.

        Runs CSM inference in a thread to avoid blocking the event loop.
        Outputs int16 numpy array at 24kHz (same format as TTSClient).

        Args:
            text: Text to synthesize

        Yields:
            numpy array of int16 PCM samples at 24kHz
        """
        if not text or not text.strip():
            return

        if not self.is_loaded():
            logger.error("CSM model not loaded — call load_model() first")
            return

        # Build conversation for CSM processor
        audio_tensor = await asyncio.to_thread(self._generate_speech, text)

        if audio_tensor is not None and audio_tensor.numel() > 0:
            # Convert torch tensor to numpy int16
            pcm = self._tensor_to_int16(audio_tensor)
            if len(pcm) > 0:
                yield pcm

            # Update context for voice consistency
            self._add_context(text, audio_tensor)

    def _generate_speech(self, text: str) -> Optional[torch.Tensor]:
        """
        Run CSM inference (blocking — call via asyncio.to_thread).

        Returns:
            1D torch.Tensor of audio samples at 24kHz, or None on error
        """
        try:
            speaker = str(self.config.csm_speaker_id)

            # Build conversation with context segments
            conversation = []
            for seg in self._context_segments:
                audio_np = seg.audio.cpu().numpy()
                conversation.append({
                    "role": str(seg.speaker),
                    "content": [
                        {"type": "text", "text": seg.text},
                        {"type": "audio", "audio": audio_np},
                    ],
                })

            # Add the new text to generate
            conversation.append({
                "role": speaker,
                "content": [{"type": "text", "text": text}],
            })

            inputs = self.processor.apply_chat_template(
                conversation, tokenize=True, return_dict=True
            ).to(self.model.device)

            with torch.no_grad():
                audio_output = self.model.generate(**inputs, output_audio=True)

            # Extract audio tensor (model returns at 24kHz)
            if isinstance(audio_output, torch.Tensor):
                return audio_output.squeeze().cpu()

            return None

        except Exception as e:
            logger.error(f"CSM generation error: {e}")
            return None

    def _tensor_to_int16(self, audio: torch.Tensor) -> np.ndarray:
        """Convert a float audio tensor to int16 numpy array."""
        audio_np = audio.float().numpy()
        # Normalize to int16 range
        if audio_np.max() > 0:
            audio_np = audio_np / max(abs(audio_np.max()), abs(audio_np.min()))
        audio_int16 = (audio_np * 32767).astype(np.int16)
        return audio_int16

    def _add_context(self, text: str, audio: torch.Tensor):
        """Add a speech segment to the rolling context buffer."""
        segment = SpeechSegment(
            speaker=self.config.csm_speaker_id,
            text=text,
            audio=audio,
        )
        self._context_segments.append(segment)
        # Trim to max context
        while len(self._context_segments) > self._max_context:
            self._context_segments.pop(0)

    def clear_context(self):
        """Clear speaker context (call this on call end)."""
        self._context_segments.clear()
