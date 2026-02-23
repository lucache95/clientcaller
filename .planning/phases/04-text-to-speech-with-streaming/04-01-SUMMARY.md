---
phase: 04-text-to-speech-with-streaming
plan: 01
subsystem: tts
tags: [tts, edge-tts, streaming, synthesis]
completed: 2026-02-23
duration_minutes: 6
dependencies:
  requires: []
  provides: [tts-client, tts-config, streaming-synthesis]
  affects:
    - phase: 04
      plan: 02
      reason: TTSStream will use TTSClient output for Twilio format conversion
tech_stack:
  added: [edge-tts]
  patterns:
    - Edge-tts streams MP3 chunks via WebSocket
    - MP3 decoded to PCM int16 numpy arrays via pydub
    - Sentence-level streaming for LLM token input
    - TTSClient is stateless (shared across calls)
key_files:
  created:
    - src/tts/__init__.py
    - src/tts/client.py
    - src/tts/config.py
    - tests/test_tts_client.py
  modified:
    - requirements.txt
    - src/config.py
    - .env.example
metrics:
  tasks_completed: 3
  files_changed: 7
  tests_added: 7
  commits: 1
---

# Phase 04 Plan 01: TTS Client Module Summary

**One-liner:** Created TTSClient with edge-tts backend for streaming neural speech synthesis on CPU — yields PCM audio chunks at 24kHz.

## What Was Built

- TTSConfig dataclass with engine/voice/rate/sample_rate settings
- TTSClient with two synthesis modes:
  - `synthesize(text)` — full text to streaming PCM chunks
  - `synthesize_streaming(text_stream)` — LLM token stream to PCM (sentence-level)
- MP3 decoding pipeline: edge-tts MP3 → pydub → int16 numpy arrays
- 7 unit tests covering config, client init, synthesis, empty text, sentence collection

## Key Decisions

- **edge-tts over kokoro**: kokoro failed to install on Python 3.14 (spacy/blis build failure). edge-tts is lightweight, high quality, async-native, free.
- **MP3 chunked decoding**: Accumulate ~4.8KB of MP3 (~200ms) before decoding for reliable pydub parsing
- **Sentence-level streaming**: Collect LLM tokens until sentence boundary, then synthesize entire sentence for natural prosody

## Commits

1. `e5b582f` - feat(04-01): add TTS client with edge-tts streaming synthesis
