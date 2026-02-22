# Roadmap: Client Caller

## Overview

Build a real-time AI phone calling system from the ground up, starting with Twilio telephony integration and audio pipeline, then adding streaming speech recognition, conversational intelligence via Gemma 3 27B, natural speech synthesis with CSM, interruption handling for natural conversation flow, and finally deploying all models concurrently on cloud GPU infrastructure. Each phase delivers a complete, verifiable capability targeting sub-500ms response latency and human-like conversation quality.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Telephony Foundation & Audio Pipeline** - Twilio WebSocket integration with bidirectional audio streaming (completed 2026-02-22)
- [ ] **Phase 2: Speech-to-Text with Streaming** - Real-time speech transcription with VAD-based turn detection
- [ ] **Phase 3: Language Model with Streaming** - Conversational responses via Gemma 3 27B with context retention
- [ ] **Phase 4: Text-to-Speech with Streaming** - Natural voice synthesis using CSM with conversational prosody
- [ ] **Phase 5: Interruption Handling & Polish** - Barge-in capability with context drift prevention
- [ ] **Phase 6: Cloud GPU Deployment & Production Hardening** - RunPod A100 deployment with concurrent model serving

## Phase Details

### Phase 1: Telephony Foundation & Audio Pipeline
**Goal**: Real-time bidirectional audio streaming with Twilio working end-to-end
**Depends on**: Nothing (first phase)
**Requirements**: TEL-01, TEL-02, TEL-03, TEL-04
**Success Criteria** (what must be TRUE):
  1. User can call a phone number and system answers the call
  2. User can speak and system receives clear audio (verified via logging/playback)
  3. System can play audio back to caller (test with pre-recorded message)
  4. System maintains stable connection throughout 2+ minute call without dropouts
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Core infrastructure setup (FastAPI WebSocket + audio conversion)
- [ ] 01-02-PLAN.md — Bidirectional streaming & call management (backpressure + state + outbound)
- [ ] 01-03-PLAN.md — Testing & verification (ngrok + end-to-end call testing)

### Phase 2: Speech-to-Text with Streaming
**Goal**: Real-time speech transcription with fast turn detection
**Depends on**: Phase 1
**Requirements**: STT-01, STT-02, STT-03
**Success Criteria** (what must be TRUE):
  1. User speaks during call and sees real-time transcript (logged/displayed)
  2. System detects when user stops speaking within 300ms
  3. System produces accurate transcription of user's words within 200ms of speech ending
  4. System handles natural pauses (2-3 second silence) without premature cutoff
**Plans**: TBD

Plans:
- TBD (populated during `/gsd:plan-phase 2`)

### Phase 3: Language Model with Streaming
**Goal**: Natural conversational responses with streaming generation
**Depends on**: Phase 2
**Requirements**: CONV-01, CONV-02
**Success Criteria** (what must be TRUE):
  1. System generates contextually relevant responses to user's speech
  2. System remembers conversation history within the same call (3+ turn exchanges)
  3. System begins response generation within 200ms of receiving transcript
**Plans**: TBD

Plans:
- TBD (populated during `/gsd:plan-phase 3`)

### Phase 4: Text-to-Speech with Streaming
**Goal**: Natural-sounding AI voice with conversational prosody
**Depends on**: Phase 3
**Requirements**: TTS-01, TTS-02, TTS-03
**Success Criteria** (what must be TRUE):
  1. User hears AI speaking with natural tone and emotion (not robotic)
  2. AI starts speaking within 500ms of user finishing their sentence
  3. AI's speech flows naturally with proper pauses and intonation
  4. Complete conversation loop works: user speaks → AI transcribes → AI thinks → AI responds
**Plans**: TBD

Plans:
- TBD (populated during `/gsd:plan-phase 4`)

### Phase 5: Interruption Handling & Polish
**Goal**: Natural conversation with barge-in capability
**Depends on**: Phase 4
**Requirements**: FLOW-01, FLOW-02
**Success Criteria** (what must be TRUE):
  1. User can interrupt AI mid-sentence and AI immediately stops talking
  2. AI responds to interruption within 200ms (no robotic delay)
  3. Conversation context remains accurate after 3+ interruptions (no drift)
  4. System recovers from errors (network glitch, model timeout) without hanging up on caller
**Plans**: TBD

Plans:
- TBD (populated during `/gsd:plan-phase 5`)

### Phase 6: Cloud GPU Deployment & Production Hardening
**Goal**: Production-ready deployment with all models running concurrently
**Depends on**: Phase 5
**Requirements**: INFRA-01, INFRA-02
**Success Criteria** (what must be TRUE):
  1. System runs on RunPod A100 GPU with all models loaded (Whisper + Gemma + CSM)
  2. System handles 3+ concurrent calls without performance degradation
  3. End-to-end latency remains under 500ms on cloud infrastructure (not just localhost)
  4. System stays stable for 10+ consecutive calls without crashes or memory leaks
**Plans**: TBD

Plans:
- TBD (populated during `/gsd:plan-phase 6`)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Telephony Foundation & Audio Pipeline | 3/3 | Complete   | 2026-02-22 |
| 2. Speech-to-Text with Streaming | 0/? | Not started | - |
| 3. Language Model with Streaming | 0/? | Not started | - |
| 4. Text-to-Speech with Streaming | 0/? | Not started | - |
| 5. Interruption Handling & Polish | 0/? | Not started | - |
| 6. Cloud GPU Deployment & Production Hardening | 0/? | Not started | - |
