# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-21)

**Core value:** The call must sound and feel like talking to a real person — natural voice, natural timing, no robotic pauses or awkward delays.
**Current focus:** Phase 4 complete — Ready for Phase 5 (Interruption Handling)

## Current Position

Phase: 4 of 6 (Text-to-Speech with Streaming — COMPLETE)
Plan: 3 of 3 (all plans executed)
Status: Complete
Last activity: 2026-02-23 — Completed Phase 4 (TTS client + audio pipeline + handler integration)

Progress: [████████░░] 80%

## Performance Metrics

**Velocity:**
- Total plans completed: 12
- Average duration: 5 minutes
- Total execution time: 1.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | 24 min | 8 min/plan |
| 02 | 3 | 17 min | 6 min/plan |
| 03 | 3 | 11 min | 4 min/plan |
| 04 | 3 | 14 min | 5 min/plan |

**Recent Completions:**
| Phase 01 P01 | 4 min | 3 tasks | 12 files |
| Phase 01 P02 | 5 | 3 tasks | 7 files |
| Phase 01 P03 | 15 | 2 tasks | 3 files |
| Phase 02 P01 | 8 | 3 tasks | 5 files |
| Phase 02 P02 | 4 | 3 tasks | 4 files |
| Phase 02 P03 | 5 | 2 tasks | 3 files |
| Phase 03 P01 | 4 | 3 tasks | 6 files |
| Phase 03 P02 | 3 | 2 tasks | 3 files |
| Phase 03 P03 | 4 | 2 tasks | 2 files |
| Phase 04 P01 | 6 | 3 tasks | 7 files |
| Phase 04 P02 | 4 | 2 tasks | 2 files |
| Phase 04 P03 | 4 | 2 tasks | 2 files |

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

**Phase 02 decisions:**
- Use distil-large-v3 model over large-v3 (6x faster with <1% WER loss)
- Use int8 quantization on CPU, float16 on CUDA (11.3GB → 3.1GB VRAM)
- Vendor whisper_streaming instead of pip install (not a standard package)
- Create CustomFasterWhisperASR wrapper for CPU/macOS support

**Phase 03 decisions:**
- Use openai Python package with AsyncOpenAI for vLLM/RunPod compatibility
- Shared LLM client (stateless), per-call ConversationManager (stateful)
- Default system prompt for natural phone assistant behavior
- Max 20 history messages (~2000 tokens, covers 10+ exchanges)
- Graceful LLM error handling (logged, doesn't crash the call)
- RunPod endpoint URL format: https://api.runpod.ai/v2/<ENDPOINT_ID>/openai/v1

**Phase 04 decisions:**
- edge-tts over kokoro for CPU/dev TTS (kokoro fails on Python 3.14, edge-tts is lightweight + high quality)
- MP3 chunked decoding: accumulate ~4.8KB before pydub parse for reliable streaming
- Sentence-level TTS streaming: collect LLM tokens until sentence boundary for natural prosody
- 24kHz → 8kHz resampling + mu-law encoding for Twilio format
- 20ms chunk splitting (160 samples at 8kHz) matching Twilio's real-time playback
- stream_sid → call_sid mapping added for media handler streamer lookups
- CSM remains target for GPU/production (edge-tts is CPU/dev bridge)

### Pending Todos

None yet.

### Blockers/Concerns

**Phase 1 Complete - All architecture decisions resolved:**
- ✅ Audio format conversion strategy (8kHz mu-law ↔ 16kHz PCM) implemented and tested
- ✅ State machine design for call lifecycle (IDLE → CONNECTING → ACTIVE → STOPPING) implemented
- Future: Context drift prevention architecture (token-level tracking) will be addressed in Phase 5

**Validation needed during execution:**
- Phase 2: VAD integration with STT (Plan 03) requires real PSTN audio quality testing
- Phase 2: STT latency benchmarking needed to confirm sub-200ms transcription budget
- Phase 3: Gemma 27B TTFT may be too slow (800ms) — decision point: stick with Gemma, switch to Gemma 9B, or use commercial API
- Phase 4: Edge-tts latency depends on network (Microsoft servers) — measure in E2E testing

## Session Continuity

Last session: 2026-02-23 (plan execution)
Stopped at: Completed Phase 4 (all 3 plans)
Resume file: .planning/phases/04-text-to-speech-with-streaming/04-03-SUMMARY.md

---
*Next step: Plan and execute Phase 5 (Interruption Handling & Polish)*
