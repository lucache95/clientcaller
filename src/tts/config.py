"""TTS configuration."""

from dataclasses import dataclass


@dataclass
class TTSConfig:
    engine: str = "edge"          # "edge" (CPU/dev) or "csm" (GPU/prod)
    voice: str = "en-US-AriaNeural"  # Edge TTS voice ID
    rate: str = "+0%"             # Speech rate adjustment
    volume: str = "+0%"           # Volume adjustment
    sample_rate: int = 24000      # Edge TTS native output sample rate
