"""
Audio resampling: 8kHz ↔ 16kHz

Twilio streams 8kHz audio (telephony standard).
Whisper and ML models expect 16kHz+ audio.

Using librosa with kaiser_fast for speed (5x faster than default).
"""
import librosa
import numpy as np
import logging

logger = logging.getLogger(__name__)


def resample_8k_to_16k(audio_8k: np.ndarray) -> np.ndarray:
    """
    Resample audio from 8kHz to 16kHz for ML models.

    Args:
        audio_8k: numpy array of samples at 8kHz

    Returns:
        numpy array of samples at 16kHz
    """
    try:
        # Use kaiser_fast for speed (5x faster than default)
        # Trade-off: slightly lower quality but acceptable for real-time
        audio_16k = librosa.resample(
            audio_8k.astype(np.float32),
            orig_sr=8000,
            target_sr=16000,
            res_type='kaiser_fast'  # Fast resampling for real-time
        )

        result = audio_16k.astype(np.int16)
        logger.debug(f"Resampled 8kHz → 16kHz: {len(audio_8k)} → {len(result)} samples")
        return result

    except Exception as e:
        logger.error(f"Error resampling 8kHz → 16kHz: {e}")
        raise


def resample_16k_to_8k(audio_16k: np.ndarray) -> np.ndarray:
    """
    Resample audio from 16kHz to 8kHz for Twilio.

    Args:
        audio_16k: numpy array of samples at 16kHz

    Returns:
        numpy array of samples at 8kHz
    """
    try:
        audio_8k = librosa.resample(
            audio_16k.astype(np.float32),
            orig_sr=16000,
            target_sr=8000,
            res_type='kaiser_fast'
        )

        result = audio_8k.astype(np.int16)
        logger.debug(f"Resampled 16kHz → 8kHz: {len(audio_16k)} → {len(result)} samples")
        return result

    except Exception as e:
        logger.error(f"Error resampling 16kHz → 8kHz: {e}")
        raise
