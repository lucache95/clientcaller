# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-21)

**Core value:** The call must sound and feel like talking to a real person — natural voice, natural timing, no robotic pauses or awkward delays.
**Current focus:** Phase 1 - Telephony Foundation & Audio Pipeline

## Current Position

Phase: 1 of 6 (Telephony Foundation & Audio Pipeline)
Plan: 2 of 3 (01-02-PLAN.md complete)
Status: Executing phase
Last activity: 2026-02-22 — Completed plan 01-02: Bidirectional Audio Streaming & Call Management

Progress: [████░░░░░░] 67%

## Performance Metrics

**Velocity:**
- Total plans completed: 2
- Average duration: 4.5 minutes
- Total execution time: 0.15 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 2 | 9 min | 4.5 min/plan |

**Recent Completions:**
| Phase 01 P01 | 4 min | 3 tasks | 12 files |
| Phase 01 P02 | 5 | 3 tasks | 7 files |

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

### Pending Todos

None yet.

### Blockers/Concerns

**Architecture decisions needed in Phase 1:**
- Audio format conversion strategy (8kHz mu-law ↔ 16kHz PCM) affects entire pipeline
- State machine design for conversation flow (IDLE → LISTENING → PROCESSING → SPEAKING → INTERRUPTED)
- Context drift prevention architecture (token-level tracking of spoken vs generated)

**Validation needed during execution:**
- Phase 3: Gemma 27B TTFT may be too slow (800ms) — decision point: stick with Gemma, switch to Gemma 9B, or use commercial API
- Phase 4: CSM latency characteristics not documented — needs benchmarking to confirm sub-150ms TTS budget
- Phase 2: VAD tuning requires real PSTN audio quality testing, not just development data

## Session Continuity

Last session: 2026-02-22T08:57:42Z (plan execution)
Stopped at: Completed 01-02-PLAN.md (Bidirectional Audio Streaming & Call Management)
Resume file: .planning/phases/01-telephony-foundation-audio-pipeline/01-02-SUMMARY.md

---
*Next step: `/gsd:execute-phase 1` to continue with plan 01-03*
