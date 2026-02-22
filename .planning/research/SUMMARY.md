# Project Research Summary

**Project:** Client Caller (Real-Time AI Voice Calling System)
**Domain:** Conversational AI / Voice Telephony
**Researched:** 2026-02-22
**Confidence:** HIGH

## Executive Summary

Client Caller is a real-time AI voice calling system that integrates Twilio telephony with self-hosted ML models to create natural, sub-500ms latency phone conversations. Experts build these systems using cascaded streaming pipelines where STT, LLM, and TTS operate concurrently with bidirectional audio flow, not sequentially. The recommended architecture uses faster-whisper for speech recognition (4x faster than vanilla Whisper), Gemma 3 27B via vLLM for conversational intelligence, and CSM for natural-sounding TTS, all running on shared GPU infrastructure with careful memory management.

The core technical challenge is latency budget discipline. With only 500ms from user speech to AI response, network overhead (50-100ms), audio conversions (50ms), STT (100-150ms), LLM TTFT (100-200ms), and TTS (100-150ms) consume the entire budget. Streaming at every stage is mandatory, not an optimization. Sequential processing adds latencies (2-5s total) and destroys conversational feel. Critical architectural decisions include VAD-based turn detection, interruption handling with context truncation, intelligent buffering (100-300ms, not seconds), and component co-location in the same datacenter.

The highest-risk pitfall is context drift from interruption misalignment—when the AI generates responses the user never heard, conversation state corrupts over multiple turns. Prevention requires token-level tracking of what was actually spoken, not just generated. Other critical risks include audio format conversion latency silently consuming 100-200ms, GPU memory fragmentation from concurrent model serving, and TTS chunking that breaks prosody. These aren't edge cases to handle later; they're architectural requirements that must be designed into Phase 1 or they become prohibitively expensive to retrofit.

## Key Findings

### Recommended Stack

The stack prioritizes self-hosted models to eliminate API latency overhead, optimized variants for speed (faster-whisper over vanilla Whisper, distil-whisper for sub-300ms STT), and streaming-first frameworks. Twilio provides PSTN connectivity via WebSocket Media Streams, delivering bidirectional 8kHz mu-law audio that requires careful resampling to 16kHz for model compatibility.

**Core technologies:**
- **Twilio Programmable Voice (API v2010)** + **twilio-python 9.10.1+**: Phone network integration with Media Streams WebSocket API for bidirectional audio. Edge locations provide sub-100ms network latency. Industry standard for telephony, handles PSTN complexity.
- **faster-whisper** + **distil-whisper (distil-large-v3)**: Streaming ASR with 4-6x speedup over vanilla Whisper. CTranslate2-based, achieves 100-200ms latency vs 1-5s for baseline. Critical for meeting latency budget.
- **Gemma 3 27B IT** via **vLLM 0.9.0+**: Self-hosted LLM with streaming token generation. Eliminates 100-300ms API round-trip latency. INT4 quantization fits 14.1GB on A100 80GB with headroom for KV cache and other models.
- **CSM (csm-1b)**: Conversational TTS with natural prosody, pauses, filler sounds. Open-source (Apache 2.0), self-hosted. Traditional TTS pipelines can't match conversational quality—CSM processes text+audio together for contextual prosody.
- **Silero VAD**: ML-based voice activity detection with 0.93 F1 score in clean conditions. RTF 0.004 on CPU. Critical for turn detection and interruption handling. Superior to WebRTC VAD for diverse audio conditions.
- **FastAPI** + **Uvicorn**: ASGI framework handles 15,000-20,000 req/sec vs Flask's 2,000-3,000. Native WebSocket support for long-lived connections. Critical for real-time workloads.
- **RunPod / NVIDIA A100 80GB**: Cloud GPU hosting at $1.99-2.17/hr. 80GB VRAM accommodates Gemma 27B INT4 (14.1GB) + CSM (2-4GB) + Whisper (2-5GB) + KV cache (20-30GB) with overhead.

**Critical versions:**
- Python 3.10+ (3.12+ recommended for vLLM 0.9.0+)
- CUDA 12.4 or 12.6 (match across vLLM, torch, CSM)
- Avoid vanilla Whisper (too slow), Flask (no async), batch-only processing, separate regional deployments

### Expected Features

Research reveals that sub-500ms latency and barge-in handling are table stakes, not differentiators. Every production voice AI system in 2026 supports interruption. Missing it means the product feels broken. Natural prosody requires CSM's architecture—traditional TTS pipelines fail to convey conversational tone even with high-quality voices.

**Must have (table stakes):**
- **Sub-500ms response latency** — Human conversation rhythm requires <500ms pauses. Above 800ms feels awkward, above 1500ms feels broken. Requires streaming at every stage.
- **Barge-in/Interruption handling** — Users expect to interrupt AI mid-sentence. Foundation of natural conversation. Needs VAD with 300-500ms silence threshold, <200ms interrupt detection.
- **Real-time audio streaming** — Twilio Media Streams bidirectional WebSocket. Batch processing breaks conversation flow.
- **Call recording & transcription** — Every production system records for compliance, QA, debugging, analytics.
- **Natural prosody & emotion** — Robotic voices kill trust. CSM specifically designed for this—traditional TTS pipelines fail.
- **Inbound call handling** — Core use case. AI answers phone calls via Twilio integration.
- **Basic error handling** — Retry logic, timeout handling, fallback responses.

**Should have (competitive differentiators):**
- **Self-hosted models (no API latency)** — API round-trips add 100-300ms. Self-hosting gives sub-500ms edge competitors can't match.
- **Conversation memory & context retention** — AI remembers past calls, reduces repetitive verification. Requires vector DB optimization to stay within latency budget.
- **Real-time sentiment analysis** — Detect frustration/satisfaction in caller's voice, adapt responses dynamically.
- **Sub-200ms interrupt response** — While 300-500ms is table stakes, <200ms feels instantaneous and human-like.
- **Voicemail detection & smart handling** — Automatically detects voicemail systems, saves cost on outbound calls.

**Defer (v2+):**
- **Voice cloning** — Users report robotic sound, pronunciation problems. High complexity, questionable quality. Use CSM's default voices.
- **Real-time analytics dashboard** — Premature optimization. Build analytics after proving core call flow works.
- **Multi-tenant SaaS features** — Scope creep. Prove technical feasibility first.
- **Web UI** — Voice-only product. Phone interface is the UX. CLI for testing until call quality is production-ready.
- **DTMF/IVR navigation** — Legacy phone trees. Conversational AI should replace this, not integrate with it.
- **Compliance & PII redaction** — Important for production, but defer until core technical approach validated.

### Architecture Approach

Real-time voice AI requires an event-driven, cascaded streaming pipeline where components operate concurrently via async message passing. The orchestrator maintains a finite state machine (IDLE → LISTENING → PROCESSING → SPEAKING → INTERRUPTED) to prevent race conditions from concurrent audio streams. VAD continuously monitors incoming audio even during AI playback to enable immediate interruption handling.

**Major components:**
1. **Twilio Telephony Bridge** — PSTN WebSocket integration, sends 8kHz mu-law audio frames, receives base64-encoded responses. Only talks to orchestrator.
2. **Orchestrator / Event Loop** — State machine, audio buffering (100-300ms), turn detection via VAD, interruption handling, routes events between components. Critical component that coordinates everything.
3. **Whisper STT (GPU)** — Streaming speech-to-text with chunked inference. Receives audio frames, outputs text chunks. faster-whisper for 4x speedup.
4. **Gemma 3 27B LLM (GPU)** — Conversational reasoning with streaming token generation via vLLM. Receives text prompts, outputs token stream.
5. **CSM TTS (GPU)** — Natural speech synthesis. Receives text chunks, outputs audio frames. Requires full semantic context for proper prosody.
6. **Silero VAD** — Speech/silence detection. Monitors audio continuously for turn detection and interruptions. Returns speech probability scores.

**Critical patterns:**
- **Stream everything:** Start TTS as soon as first sentence from LLM is ready. Never wait for complete outputs.
- **Small buffers:** 100-300ms for smoothing, not 1-2s that adds latency. Large buffers hide infrastructure problems.
- **VAD-based turn detection:** Adaptive to speaking patterns, not fixed timeouts. Tune for production environments with background noise.
- **Concurrent GPU inference:** Run all models on same GPU(s) with proper memory management. Separate GPUs waste money. A100 80GB fits all models with batching.
- **Graceful interruption:** Detect user speech during playback, immediately cancel TTS, clear Twilio buffer, return to listening. Track spoken vs generated tokens to prevent context drift.

**Build order (architectural dependencies):**
1. Telephony + audio pipeline (foundation)
2. STT with VAD (input working)
3. TTS (output working)
4. LLM integration (intelligence connects input→output)
5. Interruption handling (requires all pieces working)
6. Optimization (after it works correctly)

### Critical Pitfalls

Research identified 10 critical pitfalls. Top 5 with highest impact:

1. **Context drift from interruption misalignment** — When AI generates text the user never heard (due to interruption), conversation state corrupts. LLM success drops from 90% to 65% in multi-turn dialogues. Prevention: implement conversation.item.truncate pattern, track spoken vs generated tokens separately, truncate history to only what user heard. Must address in Phase 1 architecture—cannot retrofit easily. **Phase 1 & 3.**

2. **Latency budget exhausted by audio format conversion** — Twilio's 8kHz mu-law → Whisper's 16kHz → LLM → CSM → 8kHz mu-law consumes 100-200ms with naive resampling. Use proper DSP libraries (sox, ffmpeg), minimize conversions (ideally once on input, once on output), measure each conversion's latency contribution. Changing formats after integration requires pipeline rework. **Phase 1.**

3. **Endpointing threshold creates response delay paradox** — Too low (100ms) creates false positives from natural pauses. Too high (800ms) creates awkward delays. The 300-500ms window is extremely narrow. VAD F1 score drops from 0.93 clean to 0.71 with street noise. Use production-grade VAD (Silero), test with real phone audio, implement adaptive thresholds, plan for 200-250ms detection latency. **Phase 2.**

4. **GPU memory fragmentation from concurrent model loading** — KV cache dominates production memory (2-3x parameter memory). Without proper allocation, OOM errors occur despite sufficient total VRAM. Use vLLM's PagedAttention (eliminates 60-80% waste), configure explicit memory limits, INT8 quantization for Whisper (11.3GB → 3.1GB), monitor GPU memory in production. **Phase 1 & 5.**

5. **Streaming text chunks break prosody and natural speech** — Aggressive chunking for latency disrupts TTS prosody planning. Five open-source TTS systems fail to convey accurate prosodic boundaries from punctuation alone. Chunk at natural phrase boundaries (not just punctuation), send 100-200 tokens of look-ahead context, test subjective quality with users. CSM specifically requires full semantic context. **Phase 4.**

**Other critical pitfalls:**
- **Regional network latency** — Regional distribution adds 100-150ms per hop. Co-locate all components in same datacenter. **Phase 5.**
- **Vanilla Whisper latency** — 1-5s latency vs 100-200ms for faster-whisper. Use optimized implementations. **Phase 2.**
- **Jitter buffer misconfiguration** — Default 50-100ms buffers add hidden latency. Configure 15-20ms (3-4 packets) for voice AI. **Phase 1.**
- **WebSocket backpressure** — TTS generates faster than network transmits. Implement flow control, monitor buffer depth. **Phase 4.**
- **LLM generation latency** — Gemma 27B is "notably slow" (34 tok/s, 800ms TTFT). May need smaller model or commercial API if testing shows degraded conversational quality. **Phase 3.**

## Implications for Roadmap

Based on research, suggested 6-phase structure follows architectural dependencies and latency optimization priorities:

### Phase 1: Telephony Foundation & Audio Pipeline
**Rationale:** Cannot test anything without call connectivity. Audio format decisions lock in early—changing them later requires full pipeline rework. Critical pitfalls (format conversion latency, jitter buffer config, context drift architecture) must be addressed in foundation or they become prohibitively expensive to retrofit.

**Delivers:** Working Twilio WebSocket integration, audio format conversions (8kHz mu-law ↔ 16kHz PCM), basic state machine (idle/listening/speaking), audio buffering strategy, test with pre-recorded playback.

**Addresses:** Real-time audio streaming (table stakes), basic error handling (table stakes).

**Avoids:** Pitfall #2 (audio conversion latency), Pitfall #8 (jitter buffer), architectural decisions for Pitfall #1 (context drift).

**Research flag:** Standard Twilio integration patterns. Skip phase-level research—use STACK.md guidance.

### Phase 2: Speech-to-Text with Streaming
**Rationale:** Need input working before output. Easier to debug with visual transcript than audio. VAD tuning requires real audio data—leave iteration time. Whisper variant choice (faster-whisper vs distil-whisper) impacts entire latency budget.

**Delivers:** faster-whisper integration with streaming mode, audio buffering and chunking (100-125ms chunks), Silero VAD for turn detection, test: call in, speak, see transcript.

**Addresses:** Sub-500ms latency component (100-200ms STT budget), barge-in foundation (VAD).

**Avoids:** Pitfall #7 (vanilla Whisper 1-5s latency), Pitfall #3 (VAD threshold tuning), establishes streaming architecture.

**Stack:** faster-whisper, distil-whisper, Silero VAD, whisper_streaming library.

**Research flag:** Standard streaming STT patterns. Skip research—use ARCHITECTURE.md build order.

### Phase 3: Language Model with Streaming
**Rationale:** Combines STT + TTS (easier when both work independently). LLM streaming is complex—sentence detection for TTS chunking, token buffer management, TTFT optimization. Model selection (Gemma 27B vs smaller/commercial) impacts conversational quality—needs testing.

**Delivers:** Gemma 3 27B via vLLM deployment, streaming token generation with async iterator, sentence detection for TTS chunking, test: full conversation loop (speak → transcript → LLM → response text).

**Addresses:** Sub-500ms latency component (100-200ms LLM budget), conversational intelligence.

**Avoids:** Pitfall #10 (LLM generation latency), streaming architecture for context management.

**Stack:** vLLM 0.9.0+, Gemma 3 27B INT4 quantized, GPU deployment pattern.

**Research flag:** May need research for vLLM optimization, GPU memory tuning. Consider `/gsd:research-phase 3` if TTFT testing shows >600ms.

### Phase 4: Text-to-Speech with Streaming
**Rationale:** Simpler to test with static responses before full LLM integration. Prosody quality is subjective—needs user testing iteration. Streaming TTS has backpressure concerns that require proper async architecture.

**Delivers:** CSM integration with streaming, audio encoding for Twilio (16kHz → 8kHz mu-law), playback synchronization, chunking strategy that preserves prosody, test: send text, hear AI speak.

**Addresses:** Natural prosody & emotion (table stakes), sub-500ms latency component (100-150ms TTS budget).

**Avoids:** Pitfall #5 (prosody chunking), Pitfall #9 (WebSocket backpressure).

**Stack:** CSM (csm-1b), Mimi codec, torch + torchaudio, HuggingFace transformers.

**Research flag:** CSM integration is less documented than commercial TTS. Consider `/gsd:research-phase 4` for CSM-specific streaming patterns.

### Phase 5: Interruption Handling & Polish
**Rationale:** Requires all components working correctly. Table stakes feature that makes conversation feel natural. Addresses critical context drift pitfall.

**Delivers:** VAD monitoring during playback, TTS cancellation on interrupt, Twilio buffer clearing (`<Clear>` message), conversation state truncation (spoken vs generated tokens), test: interrupt AI mid-sentence, verify context accuracy.

**Addresses:** Barge-in/interruption handling (table stakes), sub-200ms interrupt response (differentiator).

**Avoids:** Pitfall #1 (context drift from interruption misalignment—critical architectural fix).

**Research flag:** Standard interruption patterns. Use ARCHITECTURE.md guidance, test thoroughly with 5+ interruptions per call.

### Phase 6: Cloud GPU Deployment & Production Hardening
**Rationale:** After core conversation quality proven, deploy to production infrastructure. GPU memory decisions, regional co-location, concurrent call handling, error recovery.

**Delivers:** RunPod A100 80GB deployment, all models loaded once at startup, Docker containerization (vLLM + FastAPI), GPU memory monitoring, concurrent call testing (3-5 calls), error recovery and fallbacks.

**Addresses:** Production deployment, scalability for 1-10 concurrent calls.

**Avoids:** Pitfall #4 (GPU memory fragmentation), Pitfall #6 (regional latency), scaling performance traps.

**Stack:** RunPod, Docker, vLLM PagedAttention, Redis for state (optional at this scale), monitoring/alerts.

**Research flag:** Standard cloud GPU deployment. Use STACK.md RunPod guidance. May need research for multi-GPU tensor parallelism if scaling >10 concurrent calls.

### Phase Ordering Rationale

- **Telephony first** because nothing works without call connectivity. Audio format decisions made here lock in the pipeline.
- **STT before TTS** because visual transcripts are easier to debug than audio output. VAD tuning requires real call data.
- **LLM after both input/output work** because it's easier to test LLM with static STT input and validate TTS with static text before connecting them.
- **Interruption after full loop works** because you need STT, LLM, and TTS all functioning to test interruption handling correctly.
- **Cloud deployment last** because optimizing for production before proving the approach works is premature. Deploy after latency and conversation quality validated.

This ordering minimizes rework by addressing architectural dependencies early (audio formats, streaming architecture, state machine) and deferring optimizations (prosody tuning, GPU scaling) until core functionality proven.

### Research Flags

**Phases likely needing deeper research:**
- **Phase 3 (LLM streaming):** vLLM configuration for TTFT optimization, KV cache management, potential need for TensorRT-LLM if Gemma 27B too slow. Trigger `/gsd:research-phase 3` if initial testing shows TTFT >600ms.
- **Phase 4 (TTS streaming):** CSM integration patterns less documented than commercial TTS. Streaming audio generation, prosody context requirements, chunking strategies. Trigger `/gsd:research-phase 4` during planning.

**Phases with well-documented patterns (skip research):**
- **Phase 1:** Twilio Media Streams integration well-documented. Use STACK.md and ARCHITECTURE.md guidance.
- **Phase 2:** faster-whisper, VAD integration standard patterns. Use ARCHITECTURE.md build order.
- **Phase 5:** Interruption handling patterns established (OpenAI Realtime API pattern). Use PITFALLS.md prevention strategies.
- **Phase 6:** Cloud GPU deployment standard. Use STACK.md RunPod section.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | Official docs for Twilio, vLLM, faster-whisper. Context7 performance data. Recent releases (Feb 2026). Version compatibility verified. |
| Features | **MEDIUM** | Based on competitor analysis (Bland AI, Vapi, Retell), market research, and domain expert blogs. Table stakes clear, but differentiator prioritization is subjective. |
| Architecture | **HIGH** | Multiple authoritative sources agree on cascaded streaming pipeline pattern. Twilio official docs, vLLM examples, established VAD/TTS patterns. Build order validated by dependency analysis. |
| Pitfalls | **HIGH** | Sourced from production post-mortems, latency optimization guides, Twilio best practices, academic research on prosody/VAD. Top 5 pitfalls have multiple independent sources confirming impact. |

**Overall confidence:** **HIGH**

Research is comprehensive with strong source quality. Stack choices have clear rationale with performance benchmarks. Architecture patterns are well-established for this domain. Pitfalls are documented from real production systems.

### Gaps to Address

**CSM latency characteristics:** CSM documentation doesn't specify streaming latency or TTFT. Research notes this needs benchmarking to confirm sub-150ms TTS budget is achievable. Plan for Phase 4 to include latency profiling and potential fallback to commercial TTS (Deepgram Aura, CartesiaAI) if CSM can't meet target.

**Gemma 3 27B conversational quality:** Benchmarks show 34 tok/s throughput and "notably slow" TTFT (~800ms). Research flags this may degrade conversational feel despite meeting technical latency budget. Phase 3 planning should include subjective quality testing and decision point: stick with Gemma 27B, switch to Gemma 9B (faster but less capable), or use commercial API (Claude, GPT-4—adds API latency but better TTFT).

**VAD tuning for production environments:** Silero VAD F1 score drops from 0.93 (clean) to 0.71 (street noise). Research indicates this is expected, but production tuning requires real call recordings with diverse conditions. Phase 2 should include time for threshold calibration based on actual PSTN audio quality, not just development testing.

**Multi-GPU scaling strategy:** Research covers single A100 80GB deployment (sufficient for 1-5 concurrent calls). Scaling beyond 10 concurrent calls requires tensor parallelism, model sharding, or dedicated GPU pools. Defer detailed scaling research until Phase 6 validates single-GPU approach and determines actual concurrency targets.

**Context drift prevention implementation:** Research identifies the problem and general solution (track spoken vs generated tokens, truncate on interrupt), but specific implementation pattern for vLLM + CSM not documented. Phase 5 planning should research conversation state management, potentially using OpenAI Realtime API's truncate pattern as reference.

## Sources

### Primary (HIGH confidence)
- **Twilio official documentation:** Media Streams WebSocket API, TwiML, audio formats, latency best practices
- **vLLM official docs & blog:** v0.9.0 streaming API, async examples, Feb 2026 realtime features
- **faster-whisper GitHub:** Performance benchmarks (4x speedup), CTranslate2 optimization, installation
- **CSM (Sesame) GitHub:** Model architecture, conversational speech generation, limitations
- **Silero VAD GitHub:** Performance metrics (RTF 0.004), F1 scores, language support
- **FastAPI official docs:** WebSocket support, async patterns, performance comparisons
- **Context7 sources:** Google Cloud Gemma 3 deployment (20k+ tok/s), quantization guides, GPU requirements

### Secondary (MEDIUM confidence)
- **Domain expert blogs:** AssemblyAI (300ms rule), Twilio (core latency guide), Deepgram (TTS optimization)
- **Competitor analysis:** Bland AI, Vapi AI, Retell AI platform documentation and comparison articles
- **Academic research:** Prosodic boundary generation (ISCA), KV cache memory analysis (arXiv)
- **Production case studies:** FastAPI vs Flask migration (64% latency drop), Whisper microservice scaling
- **Technology comparisons:** vLLM vs TensorRT-LLM, Whisper variants, VAD benchmarks 2026

### Tertiary (LOW confidence—needs validation)
- CSM latency characteristics (not documented, estimated 100-150ms)
- RunPod 30-second deployment claim (marketing material)
- Exact VRAM for CSM 1B (estimated 2-4GB based on architecture)
- whisper_streaming 3.3s latency claim (from repo, needs validation on PSTN audio)

---
*Research completed: 2026-02-22*
*Ready for roadmap: YES*
