# Client Caller

## What This Is

A real-time AI phone calling system powered by Twilio that handles both inbound and outbound calls. The AI engages in natural, human-sounding conversations with sub-500ms response latency, targeting the same voice quality and conversational fluidity as Sesame AI Labs. Built on a pipeline of Whisper (speech-to-text), Gemma 3 27B (conversation), and CSM (natural speech synthesis), running on cloud GPUs.

## Core Value

The call must sound and feel like talking to a real person — natural voice, natural timing, no robotic pauses or awkward delays.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Twilio integration for inbound and outbound phone calls
- [ ] Whisper-based speech-to-text with streaming/low-latency transcription
- [ ] Gemma 3 27B as the conversational LLM, served via vLLM or TensorRT
- [ ] CSM (Sesame AI Labs' Conversational Speech Model) for natural text-to-speech
- [ ] Sub-500ms end-to-end response latency (caller stops speaking → AI starts speaking)
- [ ] Audio streaming pipeline connecting Twilio ↔ Whisper ↔ Gemma ↔ CSM
- [ ] Rate limiting and error handling to prevent crashes under load
- [ ] Cloud GPU deployment (RunPod or similar) for inference serving
- [ ] Interruption handling — caller can interrupt the AI mid-sentence
- [ ] End-to-end call flow: call a number, AI picks up, natural conversation happens

### Out of Scope

- Appointment booking or any business logic — get the technical call flow working first
- Multi-tenant SaaS features — building for personal use
- Web UI or dashboard — phone call interface only
- Custom voice cloning — using CSM's default voice capabilities
- SMS or chat channels — voice calls only

## Context

- Sesame AI Labs released CSM (csm1b) as an open-source conversational speech model: https://github.com/SesameAILabs/csm
- The target is matching Sesame's demo quality: natural prosody, emotion, conversational timing
- Gemma 3 27B is Google's open-weight LLM with strong conversational capabilities
- The inference stack needs GPU acceleration — Gemma 27B + CSM + Whisper all need VRAM
- Twilio provides telephony infrastructure — handles the actual phone network integration
- The latency budget is tight: ~500ms total split across STT + LLM + TTS + network overhead
- Streaming at every stage is critical to hit latency targets (don't wait for full outputs)

## Constraints

- **Latency**: Sub-500ms response time — requires streaming inference at every pipeline stage
- **GPU**: Needs enough VRAM for Gemma 27B + CSM + Whisper running concurrently (likely A100 80GB or multiple GPUs)
- **Hosting**: Cloud GPU provider (RunPod or similar) — no local hardware
- **Audio Format**: Must work with Twilio's audio codec (typically mulaw 8kHz for PSTN, or Opus for WebRTC)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| CSM for TTS over ElevenLabs/Play.ht | Open-source, Sesame-level quality, no API latency overhead | — Pending |
| Gemma 3 27B over GPT-4/Claude API | Self-hosted for latency control, no external API round-trips | — Pending |
| vLLM or TensorRT for inference | Industry-standard serving with batching and streaming support | — Pending |
| Cloud GPU (RunPod) over local hardware | Scalable, no upfront hardware investment | — Pending |

---
*Last updated: 2026-02-21 after initialization*
