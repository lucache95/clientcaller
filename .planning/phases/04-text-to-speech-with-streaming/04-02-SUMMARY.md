---
phase: 04-text-to-speech-with-streaming
plan: 02
subsystem: tts-pipeline
tags: [tts, audio-pipeline, resampling, mulaw, twilio]
completed: 2026-02-23
duration_minutes: 4
dependencies:
  requires:
    - phase: 04
      plan: 01
      provides: tts-client
  provides: [tts-stream, twilio-audio-pipeline]
  affects:
    - phase: 04
      plan: 03
      reason: Handler integration will use TTSStream.generate()
tech_stack:
  added: []
  patterns:
    - 24kHz PCM → 8kHz resample → mu-law → base64
    - 20ms chunks (160 samples at 8kHz) match Twilio playback rate
    - Streaming yield as chunks complete
key_files:
  created:
    - src/tts/stream.py
    - tests/test_tts_stream.py
  modified: []
metrics:
  tasks_completed: 2
  files_changed: 2
  tests_added: 6
  commits: 1
---

# Phase 04 Plan 02: TTS-to-Twilio Pipeline Summary

**One-liner:** Created TTSStream pipeline that converts TTS audio to Twilio's mu-law base64 format with 20ms chunking for real-time playback.

## What Was Built

- TTSStream class with generate() and generate_streaming() methods
- Resampling: 24kHz → 8kHz using librosa kaiser_fast
- Format conversion: PCM → mu-law → base64 using existing audio utilities
- 20ms chunk splitting (160 samples at 8kHz) matching Twilio's playback rate
- 6 unit tests covering resampling, payload generation, streaming, empty input

## Commits

1. `aa736f9` - feat(04-02): add TTS-to-Twilio streaming pipeline
