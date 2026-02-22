import pytest
import numpy as np
from src.audio.conversion import mulaw_to_pcm, pcm_to_mulaw
from src.audio.resampling import resample_8k_to_16k, resample_16k_to_8k


def test_mulaw_roundtrip():
    """Test mu-law → PCM → mu-law preserves audio"""
    # Generate test audio (1 second sine wave at 440 Hz)
    sample_rate = 8000
    duration = 1.0
    frequency = 440
    t = np.linspace(0, duration, int(sample_rate * duration))
    original_pcm = (np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)

    # Convert PCM → mu-law → PCM
    mulaw_bytes = pcm_to_mulaw(original_pcm, sample_rate)
    recovered_pcm = mulaw_to_pcm(mulaw_bytes, sample_rate)

    # Check similarity (mu-law is lossy, so allow some error)
    correlation = np.corrcoef(original_pcm, recovered_pcm)[0, 1]
    assert correlation > 0.95, f"Audio significantly degraded: correlation={correlation}"


def test_resampling_roundtrip():
    """Test 8kHz → 16kHz → 8kHz preserves shape"""
    # Generate 8kHz test audio
    audio_8k = np.random.randint(-32768, 32767, size=8000, dtype=np.int16)

    # Resample up and down
    audio_16k = resample_8k_to_16k(audio_8k)
    audio_8k_recovered = resample_16k_to_8k(audio_16k)

    # Check lengths approximately match (within 1%)
    assert abs(len(audio_8k_recovered) - len(audio_8k)) < len(audio_8k) * 0.01


def test_resampling_doubles_length():
    """Test that 8kHz → 16kHz approximately doubles sample count"""
    audio_8k = np.random.randint(-32768, 32767, size=8000, dtype=np.int16)
    audio_16k = resample_8k_to_16k(audio_8k)

    # Should be close to 2x (allow 5% variance for filter edge effects)
    ratio = len(audio_16k) / len(audio_8k)
    assert 1.9 < ratio < 2.1, f"Unexpected resampling ratio: {ratio}"
