"""
Audio format conversion: mu-law ↔ PCM

Twilio uses 8-bit mu-law encoding (telephony standard).
ML models expect 16-bit PCM.

Note: Using pydub instead of deprecated audioop module (removed Python 3.13).
"""
import numpy as np
import io
from pydub import AudioSegment
import logging

logger = logging.getLogger(__name__)


def mulaw_to_pcm(mulaw_bytes: bytes, sample_rate: int = 8000) -> np.ndarray:
    """
    Convert mu-law encoded bytes to PCM numpy array.

    Args:
        mulaw_bytes: Raw mu-law audio bytes from Twilio
        sample_rate: Sample rate (Twilio uses 8000 Hz)

    Returns:
        numpy array of int16 PCM samples
    """
    try:
        # Create AudioSegment from mu-law bytes
        audio = AudioSegment.from_file(
            io.BytesIO(mulaw_bytes),
            format="mulaw",
            frame_rate=sample_rate,
            channels=1,
            sample_width=1  # mu-law is 8-bit
        )

        # Convert to 16-bit PCM
        pcm_audio = audio.set_sample_width(2)  # 2 bytes = 16-bit

        # Convert to numpy array
        samples = np.array(pcm_audio.get_array_of_samples(), dtype=np.int16)

        logger.debug(f"Converted mu-law to PCM: {len(samples)} samples")
        return samples

    except Exception as e:
        logger.error(f"Error converting mu-law to PCM: {e}")
        raise


def pcm_to_mulaw(pcm_samples: np.ndarray, sample_rate: int = 8000) -> bytes:
    """
    Convert PCM numpy array to mu-law encoded bytes.

    Args:
        pcm_samples: numpy array of int16 PCM samples
        sample_rate: Sample rate (Twilio expects 8000 Hz)

    Returns:
        mu-law encoded bytes (base64 encode before sending to Twilio)
    """
    try:
        # Ensure correct dtype
        if pcm_samples.dtype != np.int16:
            pcm_samples = pcm_samples.astype(np.int16)

        # Create AudioSegment from numpy array
        audio = AudioSegment(
            pcm_samples.tobytes(),
            frame_rate=sample_rate,
            sample_width=2,  # 16-bit PCM
            channels=1
        )

        # Export as mu-law
        buffer = io.BytesIO()
        audio.export(buffer, format="mulaw", codec="pcm_mulaw")
        mulaw_bytes = buffer.getvalue()

        logger.debug(f"Converted PCM to mu-law: {len(mulaw_bytes)} bytes")
        return mulaw_bytes

    except Exception as e:
        logger.error(f"Error converting PCM to mu-law: {e}")
        raise


def twilio_to_model_format(mulaw_payload: str) -> np.ndarray:
    """
    Complete conversion from Twilio audio to ML model format.

    Pipeline: base64 → mu-law bytes → PCM 8kHz → (caller resamples to 16kHz)

    Args:
        mulaw_payload: Base64-encoded mu-law audio from Twilio

    Returns:
        numpy array of 16-bit PCM samples at 8kHz (ready for resampling)
    """
    import base64

    # Decode base64
    mulaw_bytes = base64.b64decode(mulaw_payload)

    # Convert mu-law → PCM
    pcm_8k = mulaw_to_pcm(mulaw_bytes, sample_rate=8000)

    return pcm_8k


def model_to_twilio_format(pcm_8k: np.ndarray) -> str:
    """
    Complete conversion from ML model output to Twilio format.

    Pipeline: PCM 8kHz → mu-law → base64

    Args:
        pcm_8k: numpy array of 16-bit PCM samples at 8kHz (already resampled)

    Returns:
        Base64-encoded mu-law audio for Twilio
    """
    import base64

    # Convert PCM → mu-law
    mulaw_bytes = pcm_to_mulaw(pcm_8k, sample_rate=8000)

    # Encode base64
    mulaw_payload = base64.b64encode(mulaw_bytes).decode('utf-8')

    return mulaw_payload
