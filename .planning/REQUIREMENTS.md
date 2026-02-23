# Requirements: Client Caller

**Defined:** 2026-02-21
**Core Value:** The call must sound and feel like talking to a real person — natural voice, natural timing, no robotic pauses or awkward delays.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Telephony

- [x] **TEL-01**: System accepts inbound calls via Twilio WebSocket Media Streams
- [x] **TEL-02**: System initiates outbound calls to specified phone numbers
- [x] **TEL-03**: System converts audio between mu-law 8kHz (Twilio) and PCM 16kHz (models)
- [x] **TEL-04**: System maintains bidirectional audio streaming throughout call

### Speech-to-Text

- [x] **STT-01**: System transcribes caller speech in real-time using faster-whisper streaming
- [x] **STT-02**: System detects speech/silence boundaries using Silero VAD
- [x] **STT-03**: System endpoints speech quickly (<300ms after caller stops) for fast response

### Conversation

- [ ] **CONV-01**: System generates conversational responses via Gemma 3 27B with streaming tokens
- [ ] **CONV-02**: System maintains conversation context within a single call

### Text-to-Speech

- [ ] **TTS-01**: System synthesizes natural speech using CSM (Sesame AI Labs)
- [ ] **TTS-02**: System streams audio output (starts speaking before full response generated)
- [ ] **TTS-03**: System chunks text intelligently for natural prosody/intonation

### Call Flow

- [ ] **FLOW-01**: Caller can interrupt AI mid-sentence (barge-in) and AI stops/responds
- [ ] **FLOW-02**: System recovers gracefully from errors without hanging up

### Infrastructure

- [ ] **INFRA-01**: System deploys on cloud GPU (RunPod A100) for inference serving
- [ ] **INFRA-02**: System runs Whisper + Gemma 27B + CSM concurrently on same GPU

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Telephony

- **TEL-05**: System records calls and stores transcripts
- **TEL-06**: System supports multiple phone numbers

### Conversation

- **CONV-03**: System supports configurable system prompt/persona
- **CONV-04**: System remembers context across multiple calls (long-term memory)
- **CONV-05**: System can call external tools/APIs during conversation

### Call Flow

- **FLOW-03**: System rate limits concurrent calls to prevent overload
- **FLOW-04**: System fills silence intelligently during processing delays

### Infrastructure

- **INFRA-03**: System auto-scales GPU instances for concurrent calls
- **INFRA-04**: System includes health monitoring and structured logging
- **INFRA-05**: System deploys multi-region for lower latency

### Business Logic

- **BIZ-01**: System books/reschedules/confirms appointments
- **BIZ-02**: System integrates with calendar APIs (Google Calendar, etc.)
- **BIZ-03**: System provides analytics dashboard for call metrics

## Out of Scope

| Feature | Reason |
|---------|--------|
| Web UI / dashboard | Phone call interface only for v1 |
| Custom voice cloning | Using CSM's default voice capabilities |
| SMS / chat channels | Voice calls only |
| Multilingual support | English-first, optimize pipeline before expanding |
| Multi-party conferencing | Not needed for 1:1 AI conversations |
| Speaker diarization | Single caller scenario |
| OAuth / user accounts | Personal use, no multi-tenant |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TEL-01 | Phase 1 | Complete |
| TEL-02 | Phase 1 | Complete |
| TEL-03 | Phase 1 | Complete |
| TEL-04 | Phase 1 | Complete |
| STT-01 | Phase 2 | Complete |
| STT-02 | Phase 2 | Complete |
| STT-03 | Phase 2 | Complete |
| CONV-01 | Phase 3 | Pending |
| CONV-02 | Phase 3 | Pending |
| TTS-01 | Phase 4 | Pending |
| TTS-02 | Phase 4 | Pending |
| TTS-03 | Phase 4 | Pending |
| FLOW-01 | Phase 5 | Pending |
| FLOW-02 | Phase 5 | Pending |
| INFRA-01 | Phase 6 | Pending |
| INFRA-02 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-21*
*Last updated: 2026-02-22 after roadmap creation*
