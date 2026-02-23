import torch
import numpy as np
from typing import Optional, Dict


class VADDetector:
    def __init__(
        self,
        threshold: float = 0.5,
        min_silence_ms: int = 550,
        min_speech_ms: int = 250,
        prefix_padding_ms: int = 300,
        sampling_rate: int = 16000
    ):
        """
        Initialize VAD detector with Silero VAD.

        Args:
            threshold: Speech detection threshold 0-1 (higher = require louder audio)
            min_silence_ms: Silence duration before turn complete (default 550ms per research)
            min_speech_ms: Minimum speech duration to avoid false positives
            prefix_padding_ms: Audio to include before speech starts (avoid clipped words)
            sampling_rate: Must be 8000 or 16000 (Silero VAD requirement)
        """
        # Load Silero VAD via torch.hub (CPU inference)
        self.model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False
        )

        # Extract utility functions
        (self.get_speech_timestamps, _, _,
         self.vad_iterator, _) = utils

        # Configuration
        self.threshold = threshold
        self.min_silence_ms = min_silence_ms
        self.min_speech_ms = min_speech_ms
        self.prefix_padding_ms = prefix_padding_ms
        self.sampling_rate = sampling_rate

        # State tracking
        self.is_speaking = False
        self.silence_duration_ms = 0
        self.speech_duration_ms = 0

        # Prefix padding buffer (rolling buffer of last 300ms)
        self.prefix_buffer = []
        self.prefix_buffer_max = int(prefix_padding_ms / 20)  # 20ms chunks

    def process_chunk(self, audio_chunk: np.ndarray) -> Dict[str, any]:
        """
        Process audio chunk and detect speech/silence transitions.

        Args:
            audio_chunk: PCM 16kHz int16 numpy array (typically 20-30ms)

        Returns:
            dict: {
                "is_speech": bool,
                "turn_complete": bool,
                "speech_probability": float
            }
        """
        # Convert int16 to float32 normalized to [-1, 1]
        audio_float = audio_chunk.astype(np.float32) / 32768.0

        # Convert to torch tensor
        audio_tensor = torch.from_numpy(audio_float)

        # Run VAD inference (returns speech probability 0-1)
        speech_prob = self.model(audio_tensor, self.sampling_rate).item()

        # Detect speech based on threshold
        is_speech = speech_prob > self.threshold

        # Update prefix buffer (always maintain last 300ms)
        self.prefix_buffer.append(audio_chunk)
        if len(self.prefix_buffer) > self.prefix_buffer_max:
            self.prefix_buffer.pop(0)

        # Track speech/silence durations
        chunk_duration_ms = len(audio_chunk) / self.sampling_rate * 1000

        if is_speech:
            self.speech_duration_ms += chunk_duration_ms
            self.silence_duration_ms = 0  # Reset silence counter

            if not self.is_speaking:
                # Transition: silence → speech
                self.is_speaking = True
        else:
            self.silence_duration_ms += chunk_duration_ms

        # Check for turn completion
        turn_complete = False
        if self.is_speaking and self.silence_duration_ms >= self.min_silence_ms:
            # Sufficient silence after speech → turn complete
            if self.speech_duration_ms >= self.min_speech_ms:
                turn_complete = True

        return {
            "is_speech": is_speech,
            "turn_complete": turn_complete,
            "speech_probability": speech_prob,
            "silence_duration_ms": self.silence_duration_ms,
            "speech_duration_ms": self.speech_duration_ms
        }

    def get_prefix_buffer(self) -> np.ndarray:
        """
        Get prefix padding buffer (audio before speech started).

        Returns:
            np.ndarray: Concatenated audio chunks from prefix buffer
        """
        if not self.prefix_buffer:
            return np.array([], dtype=np.int16)
        return np.concatenate(self.prefix_buffer)

    def reset(self):
        """Reset VAD state for next turn."""
        self.is_speaking = False
        self.silence_duration_ms = 0
        self.speech_duration_ms = 0
        self.prefix_buffer = []
