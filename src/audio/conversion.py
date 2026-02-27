"""
Audio format conversion: mu-law ↔ PCM

Twilio uses 8-bit mu-law encoding (telephony standard).
ML models expect 16-bit PCM.

Uses pure numpy for speed (~microseconds vs ~100ms with pydub/ffmpeg).
"""
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Pre-compute mu-law to PCM lookup table (256 entries, one per byte value)
# ITU-T G.711 mu-law decoding formula
_MULAW_BIAS = 33
_MULAW_MAX = 0x1FFF  # 8191

def _build_mulaw_decode_table() -> np.ndarray:
    """Build mu-law byte → int16 PCM lookup table."""
    table = np.zeros(256, dtype=np.int16)
    for i in range(256):
        # Complement the bits
        val = ~i & 0xFF
        sign = val & 0x80
        exponent = (val >> 4) & 0x07
        mantissa = val & 0x0F
        # Decode
        sample = (mantissa << (exponent + 3)) + _MULAW_BIAS
        sample = sample << (exponent)
        sample = sample - _MULAW_BIAS
        if sign:
            sample = -sample
        # Clamp to int16 range
        sample = max(-32768, min(32767, sample))
        table[i] = sample
    return table

_MULAW_DECODE_TABLE = _build_mulaw_decode_table()

# Pre-compute PCM to mu-law encode table
def _build_mulaw_encode_table() -> np.ndarray:
    """Build int16 PCM → mu-law byte lookup table for positive values."""
    # We'll encode on the fly since the table would be 65536 entries
    pass

def _encode_mulaw_sample(sample: int) -> int:
    """Encode a single int16 PCM sample to mu-law byte."""
    BIAS = 0x84  # 132
    CLIP = 32635

    sign = 0
    if sample < 0:
        sign = 0x80
        sample = -sample
    if sample > CLIP:
        sample = CLIP
    sample = sample + BIAS

    exponent = 7
    mask = 0x4000
    for _ in range(8):
        if sample & mask:
            break
        exponent -= 1
        mask >>= 1

    mantissa = (sample >> (exponent + 3)) & 0x0F
    mulaw_byte = ~(sign | (exponent << 4) | mantissa) & 0xFF
    return mulaw_byte


def mulaw_to_pcm(mulaw_bytes: bytes, sample_rate: int = 8000) -> np.ndarray:
    """
    Convert mu-law encoded bytes to PCM numpy array using lookup table.

    Args:
        mulaw_bytes: Raw mu-law audio bytes from Twilio
        sample_rate: Sample rate (unused, kept for API compat)

    Returns:
        numpy array of int16 PCM samples
    """
    indices = np.frombuffer(mulaw_bytes, dtype=np.uint8)
    return _MULAW_DECODE_TABLE[indices].copy()


def pcm_to_mulaw(pcm_samples: np.ndarray, sample_rate: int = 8000) -> bytes:
    """
    Convert PCM numpy array to mu-law encoded bytes.

    Args:
        pcm_samples: numpy array of int16 PCM samples
        sample_rate: Sample rate (unused, kept for API compat)

    Returns:
        mu-law encoded bytes
    """
    if pcm_samples.dtype != np.int16:
        pcm_samples = pcm_samples.astype(np.int16)

    result = bytearray(len(pcm_samples))
    for i, sample in enumerate(pcm_samples):
        result[i] = _encode_mulaw_sample(int(sample))
    return bytes(result)


def twilio_to_model_format(mulaw_payload: str) -> np.ndarray:
    """
    Complete conversion from Twilio audio to ML model format.

    Pipeline: base64 → mu-law bytes → PCM 8kHz → (caller resamples to 16kHz)
    """
    import base64
    mulaw_bytes = base64.b64decode(mulaw_payload)
    return mulaw_to_pcm(mulaw_bytes, sample_rate=8000)


def model_to_twilio_format(pcm_8k: np.ndarray) -> str:
    """
    Complete conversion from ML model output to Twilio format.

    Pipeline: PCM 8kHz → mu-law → base64
    """
    import base64
    mulaw_bytes = pcm_to_mulaw(pcm_8k, sample_rate=8000)
    return base64.b64encode(mulaw_bytes).decode('utf-8')
