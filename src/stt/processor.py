"""
Speech-to-Text (STT) processor using faster-whisper and whisper_streaming.

Provides real-time streaming transcription with sub-200ms latency using:
- faster-whisper (CTranslate2-based Whisper, 4x faster than vanilla)
- whisper_streaming (LocalAgreement policy for adaptive latency)
"""

from .whisper_online import FasterWhisperASR, OnlineASRProcessor
import numpy as np
from typing import AsyncGenerator, Dict, Any
import sys
import platform


class CustomFasterWhisperASR(FasterWhisperASR):
    """
    Custom FasterWhisperASR that supports CPU execution for macOS.

    The upstream whisper_streaming hardcodes device="cuda", which doesn't
    work on macOS. This wrapper overrides load_model to use CPU with int8
    quantization for development/testing.
    """

    def __init__(self, lan, modelsize=None, cache_dir=None, model_dir=None,
                 device="cpu", compute_type="int8", logfile=sys.stderr):
        self.device = device
        self.compute_type = compute_type
        super().__init__(lan, modelsize, cache_dir, model_dir, logfile)

    def load_model(self, modelsize=None, cache_dir=None, model_dir=None):
        from faster_whisper import WhisperModel

        if model_dir is not None:
            model_size_or_path = model_dir
        elif modelsize is not None:
            model_size_or_path = modelsize
        else:
            raise ValueError("modelsize or model_dir parameter must be set")

        # Use configurable device and compute_type (default: CPU with int8)
        # This allows both macOS development (CPU) and production (CUDA)
        model = WhisperModel(
            model_size_or_path,
            device=self.device,
            compute_type=self.compute_type,
            download_root=cache_dir
        )
        return model


class STTProcessor:
    """
    Streaming STT processor with faster-whisper backend.

    Accepts PCM 16kHz audio chunks and yields partial/final transcripts
    using whisper_streaming's LocalAgreement policy for real-time transcription.

    Architecture:
    - Loads model once at initialization (not per request)
    - Uses OnlineASRProcessor with LocalAgreement for adaptive latency
    - Accepts PCM 16kHz numpy arrays (pre-converted by Phase 1 pipeline)
    - Yields partial transcripts during speech, final on completion
    - Resets state between turns to prevent context bleed
    """

    def __init__(self, model_size: str = "distil-large-v3", language: str = "en",
                 device: str = None, compute_type: str = None):
        """
        Initialize streaming STT processor.

        Args:
            model_size: Model to use. Options:
                - "distil-large-v3" (default): 6x faster, <1% WER loss
                - "large-v3": More accurate but slower
            language: Target language code (default: "en" for English)
            device: Device to use ("cpu" or "cuda"). Auto-detects if None.
            compute_type: Compute type ("int8", "float16"). Auto-selects if None.

        Notes:
            - Model loads on first init (may take 10-30s, downloads if needed)
            - Uses int8 quantization on CPU: 11.3GB → 3.1GB VRAM
            - Auto-detects CPU (macOS) vs CUDA (production)
            - Leaves headroom for Gemma 27B and CSM in future phases
        """
        # Auto-detect device and compute_type if not specified
        if device is None:
            from src.config import settings
            if settings.use_gpu:
                device = "cuda"
            else:
                device = "cpu"

        if compute_type is None:
            # Use int8 on CPU, float16 on CUDA
            compute_type = "int8" if device == "cpu" else "float16"

        # Load faster-whisper model once at startup (not per call)
        # Use custom wrapper that supports CPU execution
        self.asr = CustomFasterWhisperASR(
            lan=language,
            modelsize=model_size,
            device=device,
            compute_type=compute_type
        )

        # Initialize online processor with LocalAgreement policy
        self.online = OnlineASRProcessor(self.asr)

    async def process_audio_chunk(
        self,
        pcm_16khz: np.ndarray
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process incoming PCM 16kHz audio chunk and yield partial transcripts.

        Args:
            pcm_16khz: numpy array of int16 audio samples at 16kHz

        Yields:
            dict: Partial transcript with structure:
                {
                    "type": "partial",
                    "text": str,
                    "beg": float,  # start timestamp
                    "end": float   # end timestamp
                }

        Notes:
            - Yields iteratively as LocalAgreement policy confirms text
            - Partial transcripts may update/refine as more audio arrives
            - Call finalize_turn() to get final transcript and reset state
            - May not yield anything for silence or very short audio
        """
        # Convert int16 to float32 normalized to [-1, 1]
        # Whisper expects float32 audio in range [-1.0, 1.0]
        audio_float = pcm_16khz.astype(np.float32) / 32768.0

        # Feed audio chunk to whisper streaming processor
        self.online.insert_audio_chunk(audio_float)

        # Get partial transcripts (iterative, yields as text is confirmed)
        # process_iter() returns (beg, end, text) or (None, None, "")
        result = self.online.process_iter()
        if result is not None:
            beg, end, text = result
            # Only yield if we have actual text (not silence)
            if text:
                yield {
                    "type": "partial",
                    "text": text,
                    "beg": beg,
                    "end": end
                }

    def finalize_turn(self) -> Dict[str, Any]:
        """
        Finalize current turn and get final transcript.

        Returns:
            dict: Final transcript with structure:
                {
                    "type": "final",
                    "text": str,
                    "beg": float,  # start timestamp
                    "end": float   # end timestamp
                }

        Notes:
            - Automatically resets state for next turn (prevents context bleed)
            - CRITICAL: Must call between turns per 02-RESEARCH.md Pitfall 7
        """
        # Get final transcript from remaining audio
        # finish() returns (beg, end, text) or (None, None, "")
        beg, end, final_text = self.online.finish()

        # Reset processor state for next turn
        # CRITICAL: Prevents context from previous turn bleeding into next
        self.online.init()

        return {
            "type": "final",
            "text": final_text,
            "beg": beg,
            "end": end
        }
