# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-21)

**Core value:** The call must sound and feel like talking to a real person — natural voice, natural timing, no robotic pauses or awkward delays.
**Current focus:** Phase 2 - Speech-to-Text with Streaming

## Current Position

Phase: 2 of 6 (Speech-to-Text with Streaming)
Plan: 2 of 3 (02-02-PLAN.md complete)
Status: In progress
Last activity: 2026-02-23 — Completed plan 02-02: Voice Activity Detection with Silero VAD

Progress: [███░░░░░░░] 33%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: 7 minutes
- Total execution time: 0.5 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | 24 min | 8 min/plan |
| 02 | 1 | 4 min | 4 min/plan |

**Recent Completions:**
| Phase 01 P01 | 4 min | 3 tasks | 12 files |
| Phase 01 P02 | 5 | 3 tasks | 7 files |
| Phase 01 P03 | 15 | 2 tasks | 3 files |
| Phase 02 P02 | 4 | 3 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- CSM for TTS over ElevenLabs/Play.ht (open-source, Sesame-level quality, no API latency overhead)
- Gemma 3 27B over GPT-4/Claude API (self-hosted for latency control, no external API round-trips)
- vLLM or TensorRT for inference (industry-standard serving with batching and streaming support)
- Cloud GPU (RunPod) over local hardware (scalable, no upfront hardware investment)

**Phase 01 decisions:**
- Use pydub instead of deprecated audioop for mu-law conversion (audioop removed in Python 3.13)
- Use librosa with kaiser_fast resampling mode (5x faster, acceptable quality for real-time)
- Configure pydantic Settings with extra="ignore" for .env flexibility
- Use bounded queue with maxsize=50 for audio backpressure (~1 second buffer at 20ms/chunk)
- Send loop paces at 20ms per chunk to match real-time playback rate
- Track calls by temp_id until call_sid arrives from Twilio 'start' message
- Railway used for production deployment with automatic HTTPS
- ngrok for local development testing before production deployment
- Human verification checkpoint required for telephony testing (cannot automate real phone calls)
- [Phase 02]: Silero VAD over WebRTC VAD for ML-based detection with 0.93 F1 score
- [Phase 02]: CPU inference for VAD to reserve GPU for Whisper/Gemma/CSM
- [Phase 02]: 550ms silence threshold for turn detection (balances responsiveness vs false positives)
- [Phase 02]: 300ms prefix padding buffer to prevent clipped words at speech start

### Pending Todos

None yet.

### Blockers/Concerns

**Phase 1 Complete - All architecture decisions resolved:**
- ✅ Audio format conversion strategy (8kHz mu-law ↔ 16kHz PCM) implemented and tested
- ✅ State machine design for call lifecycle (IDLE → CONNECTING → ACTIVE → STOPPING) implemented
- Future: Context drift prevention architecture (token-level tracking) will be addressed in Phase 5

**Validation needed during execution:**
- Phase 3: Gemma 27B TTFT may be too slow (800ms) — decision point: stick with Gemma, switch to Gemma 9B, or use commercial API
- Phase 4: CSM latency characteristics not documented — needs benchmarking to confirm sub-150ms TTS budget
- Phase 2: VAD tuning requires real PSTN audio quality testing, not just development data

## Session Continuity

Last session: 2026-02-23T03:05:00Z (plan execution)
Stopped at: Completed 02-02-PLAN.md (Voice Activity Detection with Silero VAD)
Resume file: .planning/phases/02-speech-to-text-with-streaming/02-02-SUMMARY.md

---
*Next step: Execute plan 02-03 (Streaming STT with faster-whisper integration)*
