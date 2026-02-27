"""
Audio resampling: 8kHz ↔ 16kHz

Uses numpy linear interpolation for speed (microseconds vs 13s librosa cold start).
"""
import numpy as np
import logging

logger = logging.getLogger(__name__)


def resample_8k_to_16k(audio_8k: np.ndarray) -> np.ndarray:
    """Resample 8kHz int16 audio to 16kHz using linear interpolation."""
    # Simple 2x upsample with linear interpolation
    n = len(audio_8k)
    x_old = np.arange(n)
    x_new = np.linspace(0, n - 1, n * 2)
    audio_16k = np.interp(x_new, x_old, audio_8k.astype(np.float32))
    return audio_16k.astype(np.int16)


def resample_16k_to_8k(audio_16k: np.ndarray) -> np.ndarray:
    """Resample 16kHz int16 audio to 8kHz by taking every other sample."""
    return audio_16k[::2].copy()
