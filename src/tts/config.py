"""TTS configuration."""

from dataclasses import dataclass


@dataclass
class TTSConfig:
    engine: str = "edge"          # "edge" (CPU/dev) or "csm" (GPU/prod)
    voice: str = "en-US-AriaNeural"  # Edge TTS voice ID
    rate: str = "+0%"             # Speech rate adjustment
    volume: str = "+0%"           # Volume adjustment
    sample_rate: int = 24000      # Both edge-tts and CSM output at 24kHz

    # CSM-specific settings
    csm_speaker_id: int = 0       # CSM speaker embedding index
    csm_max_context: int = 3      # Max context segments for voice conditioning
