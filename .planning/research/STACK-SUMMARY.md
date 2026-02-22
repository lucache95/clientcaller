# Stack Research Summary

**Generated:** 2026-02-22
**Confidence:** MEDIUM-HIGH

## Core Stack (Production-Ready)

### Audio Pipeline
```
Twilio (8kHz μ-law)
  ↓ [WebSocket, FastAPI]
librosa resample (→16kHz)
  ↓ [NumPy buffers, sounddevice]
faster-whisper + Silero VAD (STT + voice detection)
  ↓ [streaming transcription]
vLLM + Gemma 3 27B INT4 (conversation logic)
  ↓ [streaming tokens]
CSM 1B (conversational TTS)
  ↓ [RVQ audio codes, Mimi codec]
resample + encode (→8kHz μ-law, base64)
  ↓ [WebSocket]
Twilio (back to caller)
```

### Key Technology Versions

| Component | Technology | Version | Confidence |
|-----------|-----------|---------|------------|
| Telephony | Twilio + twilio-python | API v2010, SDK 9.10.1+ | HIGH |
| Web Server | FastAPI + Uvicorn | Latest stable, 0.40.0+ | HIGH |
| STT | faster-whisper | Latest 0.x | HIGH |
| STT (low-latency) | distil-whisper (distil-large-v3) | Latest | MEDIUM |
| LLM | Gemma 3 27B IT (INT4) | Latest google/gemma-3-27b-it | HIGH |
| LLM Serving | vLLM | 0.9.0+ | HIGH |
| TTS | CSM (csm-1b) | 1B (sesame/csm-1b) | MEDIUM |
| VAD | Silero VAD | Latest | HIGH |
| Audio I/O | sounddevice | 0.5.5+ | HIGH |
| Audio Processing | librosa + NumPy | Latest | HIGH |
| GPU | NVIDIA A100 80GB | N/A | MEDIUM-HIGH |
| Cloud Hosting | RunPod | N/A | MEDIUM |
| Runtime | Python 3.12+ | 3.10-3.13 supported | HIGH |
| GPU Runtime | CUDA 12.4 or 12.6 | 12.x | HIGH |

## Critical Decisions

### 1. FastAPI over Flask
**Why:** ASGI async, 15k-20k req/sec vs 2k-3k, native WebSocket support. 64% latency reduction proven in 2026 case study.

### 2. faster-whisper over base Whisper
**Why:** 4x faster (59-103s vs 143s for 13-min audio), same accuracy. CTranslate2-based.

### 3. distil-whisper for latency-critical paths
**Why:** 6x faster than Whisper Large V3, within 1% WER. 756M vs 1.54B params.

### 4. vLLM over TensorRT-LLM
**Why:** Better Python SDK, easier deployment, proven 20k+ tok/sec on Gemma 3 27B. TensorRT for advanced optimization later if needed.

### 5. Silero VAD over WebRTC VAD
**Why:** ML-based, trained on 6000+ languages. Higher AUC, RTF 0.004 (fast enough). Better for diverse audio sources.

### 6. INT4 quantization for Gemma 3 27B
**Why:** 54GB BF16 → 14.1GB INT4. Fits single RTX 3090 or leaves 65GB free on A100 80GB for KV cache + other models.

### 7. CSM over ElevenLabs/Play.ht APIs
**Why:** Self-hosted = no API latency. Apache 2.0 license. Sesame-quality conversational output (prosody, fillers).

### 8. sounddevice over PyAudio
**Why:** NumPy array support, better scipy/librosa integration, actively maintained (Jan 2026 release).

## Latency Budget Analysis

**Target:** Sub-500ms end-to-end (caller stops speaking → AI starts speaking)

| Stage | Estimated Time | Notes |
|-------|---------------|-------|
| Network (Twilio ↔ Server) | 50-100ms | Edge routing, 40-80ms buffer |
| STT (faster-whisper + VAD) | 100-150ms | Streaming mode, distil-whisper variant |
| LLM (vLLM Gemma 27B) | 100-200ms | Continuous batching, streaming |
| TTS (CSM) | 100-150ms | **NEEDS BENCHMARKING** |
| Audio conversion | 10-30ms | Resampling, encoding |
| Headroom | 50-100ms | Variance, spikes |
| **Total** | **410-730ms** | **CSM latency is critical unknown** |

**RISK:** CSM latency not documented. Must profile to confirm sub-500ms achievable.

## VRAM Planning (A100 80GB)

| Component | VRAM Usage | Notes |
|-----------|-----------|-------|
| Gemma 3 27B INT4 | 14.1GB | QAT quantized model |
| KV Cache | 20-30GB | Depends on context length |
| CSM 1B | 2-4GB | **ESTIMATED** (Llama + audio decoder) |
| faster-whisper | 2-5GB | large-v3 vs distil-large-v3 |
| Silero VAD | 50-100MB | Tiny model |
| CUDA overhead | 5-10GB | Kernels, buffers |
| **Total** | **45-65GB** | Fits A100 80GB with headroom |

**Alternative:** Multi-GPU with tensor parallelism if needed.

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| OpenAI Realtime API | Vendor lock-in, no latency control, can't self-host | Self-hosted pipeline |
| Flask | WSGI sync, 2k-3k req/sec, no native WebSocket | FastAPI (ASGI async) |
| Base Whisper | 4x slower than faster-whisper | faster-whisper or distil-whisper |
| WebRTC VAD | GMM-based, lower accuracy on diverse audio | Silero VAD (ML-based) |
| pydub for streaming | File manipulation tool, not for real-time | sounddevice + librosa |
| Celery for audio | Background jobs, not real-time streaming | FastAPI async + asyncio |

## Installation Quick Reference

```bash
# Core environment (Python 3.10+, 3.12+ recommended)
pip install twilio>=9.10.1
pip install faster-whisper
pip install vllm>=0.9.0
pip install torch torchaudio transformers --index-url https://download.pytorch.org/whl/cu124
pip install -r https://raw.githubusercontent.com/SesameAILabs/csm/main/requirements.txt
pip install silero-vad
pip install "fastapi[standard]" uvicorn[standard]
pip install sounddevice librosa numpy scipy pydantic
```

## Open Questions / Validation Needed

1. **CSM latency**: Not documented in official sources. Needs benchmarking to confirm sub-500ms target is achievable.
2. **CSM VRAM**: Estimated 2-4GB based on architecture (Llama backbone + audio decoder). Needs measurement.
3. **End-to-end latency**: Budget analysis is theoretical. Real-world testing required.
4. **Multi-model GPU orchestration**: Loading Gemma 27B + CSM + faster-whisper concurrently on single A100 80GB needs validation.
5. **Twilio 8kHz audio quality**: Resampling to 16kHz won't recover lost frequency information. Impact on ASR/TTS quality needs testing.

## Next Steps for Roadmap

1. **Phase 1 (Foundation)**: Twilio WebSocket ↔ FastAPI server, audio format conversions
2. **Phase 2 (STT)**: faster-whisper integration, Silero VAD, streaming transcription
3. **Phase 3 (LLM)**: vLLM server deployment, Gemma 3 27B INT4 loading, streaming inference
4. **Phase 4 (TTS)**: CSM integration, audio synthesis pipeline, format conversion back to Twilio
5. **Phase 5 (Integration)**: Full pipeline testing, latency profiling, interruption handling
6. **Phase 6 (Production)**: Docker deployment, RunPod hosting, multi-GPU scaling if needed

---
*Quick reference for roadmap creation*
*See full STACK.md for detailed rationale and sources*
