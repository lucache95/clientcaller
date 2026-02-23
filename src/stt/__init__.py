"""
Speech-to-Text (STT) module for real-time transcription.

Exports:
    STTProcessor: Streaming STT processor using faster-whisper
"""

from .processor import STTProcessor

__all__ = ["STTProcessor"]
