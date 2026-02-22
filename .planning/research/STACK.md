# Technology Stack

**Project:** Client Caller (Real-Time AI Voice Calling System)
**Researched:** 2026-02-22
**Overall Confidence:** MEDIUM-HIGH

## Recommended Stack

### Telephony Layer

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Twilio Programmable Voice | API v2010 | Phone network integration, WebSocket audio streaming | Industry standard for telephony with Media Streams WebSocket API for bidirectional audio. Handles PSTN/VoIP complexity, global routing, sub-100ms network latency via edge locations. **Confidence: HIGH** |
| twilio-python | 9.10.1+ | Twilio API client and TwiML generation | Official Python SDK, actively maintained (latest release Feb 5, 2026). Provides VoiceResponse class for TwiML and client.calls API. **Confidence: HIGH** |

### Speech-to-Text (STT)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| faster-whisper | Latest (0.x) | Streaming ASR transcription | CTranslate2-based reimplementation delivers 4x speed improvement over OpenAI Whisper with same accuracy. Requires Python 3.9+. Achieves ~59-103s for 13-min audio vs 143s baseline. Supports batching for throughput optimization. **Confidence: HIGH** |
| distil-whisper (distil-large-v3) | Latest | Low-latency alternative to base Whisper | 6x faster than Whisper Large V3, within 1% WER. 756M params vs 1.54B. Compatible with faster-whisper via CTranslate2. Best for sub-500ms latency targets. **Confidence: MEDIUM** |
| whisper_streaming | Latest | Realtime streaming transcription | Self-adaptive latency with local agreement policy. Achieves 3.3s latency on long-form speech. Required for turn-by-turn conversation vs batch processing. **Confidence: MEDIUM** |

### Language Model (LLM)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Gemma 3 27B IT | Latest (google/gemma-3-27b-it) | Conversational AI reasoning | Open-weight LLM with strong conversational capabilities. Self-hosted = no API latency overhead. Requires 54GB BF16 or 14.1GB INT4 quantized. Fits on single A100 80GB with headroom for KV cache. **Confidence: HIGH** |
| vLLM | 0.9.0+ (latest stable) | LLM inference serving | High-throughput memory-efficient engine with streaming support. Achieves 20,000+ tokens/sec on Gemma 3 27B with multi-H100. Python 3.10+ required (3.12+ recommended as of Feb 2026). Supports async streaming, continuous batching, tensor parallelism. **Confidence: HIGH** |

### Text-to-Speech (TTS)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| CSM (csm-1b) | 1B (sesame/csm-1b) | Natural conversational speech synthesis | Sesame's open-source conversational TTS with human-like prosody, pauses, filler sounds ("um", "uh"). Llama backbone + Mimi audio decoder producing RVQ codes. Apache 2.0 license. Python 3.10 recommended. Requires separate LLM for dialogue logic. **Confidence: MEDIUM** |
| Mimi codec | Latest | Audio encoding/decoding for CSM | Required dependency for CSM audio code generation. Part of CSM pipeline for RVQ audio output. **Confidence: MEDIUM** |

### Voice Activity Detection (VAD)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Silero VAD | Latest | Speech/silence detection and interruption handling | ML-based VAD trained on 6000+ languages. RTF 0.004 on CPU (15.4s to process 1hr audio). Superior accuracy vs WebRTC VAD (higher AUC). MIT license, zero telemetry. Better for diverse audio quality/backgrounds. **Confidence: HIGH** |

### Web Framework & Server

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| FastAPI | Latest stable | Async WebSocket server for Twilio Media Streams | ASGI-based async framework handles 15,000-20,000 req/sec (vs Flask's 2,000-3,000). Native WebSocket support without extensions. Perfect for long-lived connections with streaming audio. Critical for real-time workloads. **Confidence: HIGH** |
| Uvicorn | 0.40.0+ | ASGI server for FastAPI | Leading ASGI server as of 2026. Improved performance, HTTP/1.1 + WebSocket support, Cython compatibility. Production-ready with Gunicorn workers for scaling. **Confidence: HIGH** |

### Audio Processing

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| sounddevice | 0.5.5+ | Audio I/O and NumPy streaming | More user-friendly than PyAudio, supports NumPy arrays natively. Actively maintained (v0.5.5 released Jan 23, 2026). Better for integration with scipy/librosa. Cross-platform (Linux/macOS/Windows). **Confidence: HIGH** |
| librosa | Latest | Audio resampling (8kHz → 16kHz) | Industry standard for audio feature extraction and resampling. Simple API: librosa.load('audio.wav', sr=16000). Critical since Twilio streams 8kHz μ-law but models need 16kHz. **Confidence: HIGH** |
| NumPy | Latest | Audio buffer processing | Standard for real-time audio array operations. Block-based processing for streaming buffers. Fast C-backed operations via np.PyArray_DATA(). **Confidence: HIGH** |
| PyAV | Latest (bundled with faster-whisper) | Audio decoding | Bundles FFmpeg libraries internally. Used by faster-whisper for format support (MP3, WAV, etc). No separate FFmpeg install required. **Confidence: HIGH** |

### GPU Infrastructure

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| RunPod | N/A | Cloud GPU hosting | A100 80GB starting at $1.99-2.17/hr (serverless). 30-second deployment, 31 global regions. Community Cloud (cheaper, vetted hosts) vs Secure Cloud (SLA, persistent storage). Per-second billing option. **Confidence: MEDIUM** |
| NVIDIA A100 80GB | 80GB HBM2e | GPU for concurrent inference | Gemma 27B INT4 (14.1GB) + CSM (TBD) + faster-whisper (TBD) + KV cache. 80GB provides headroom for concurrent model serving. Compute capability 8.0 (vLLM requires 7.0+). **Confidence: MEDIUM-HIGH** |
| Docker | Latest | Container deployment | vLLM official image: vllm/vllm-openai:latest. GPU passthrough via nvidia-docker2. Compose files for multi-GPU tensor parallelism. Health checks + resource limits for production. **Confidence: HIGH** |
| CUDA | 12.4 or 12.6 | GPU runtime | Tested versions for CSM. vLLM requires CUDA-compatible drivers. cuBLAS + cuDNN 9 for faster-whisper. **Confidence: HIGH** |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| torch | 2.x (with CUDA) | PyTorch for CSM/Silero VAD | Required for CSM model loading and Silero VAD inference. Ensure CUDA build matches driver version. **Confidence: HIGH** |
| torchaudio | Latest | Audio I/O for PyTorch models | CSM outputs torch tensors saved via torchaudio.save(). Native integration with PyTorch ecosystem. **Confidence: HIGH** |
| transformers | Latest | Hugging Face model loading | Required for CSM's Llama-3.2-1B backbone access. Authentication needed for gated models. **Confidence: HIGH** |
| websockets | 16.0+ | Async WebSocket client/server | Built on asyncio. FastAPI uses internally. Alternative: use FastAPI's native WebSocket class. **Confidence: MEDIUM** |
| pydantic | Latest | Data validation for FastAPI | FastAPI dependency for request/response validation. Type-safe configuration objects. **Confidence: HIGH** |
| redis-py | Latest | Optional: task queue for async processing | Use if decoupling inference from WebSocket handling. RQ (Redis Queue) for background workers. Not required for MVP but useful at scale. **Confidence: LOW** |

## Installation

```bash
# System dependencies
sudo apt-get install -y ffmpeg portaudio19-dev  # Linux
brew install ffmpeg portaudio  # macOS

# Core Python environment (Python 3.10+ required, 3.12+ recommended)
pip install --upgrade pip

# Telephony
pip install twilio>=9.10.1

# STT
pip install faster-whisper  # Includes PyAV, no separate FFmpeg needed
pip install git+https://github.com/ufal/whisper_streaming  # Streaming support

# LLM serving
pip install vllm>=0.9.0  # Python 3.10-3.13 supported
pip install vllm[audio]  # For Whisper model support if needed

# TTS (CSM)
pip install torch torchaudio transformers --index-url https://download.pytorch.org/whl/cu124  # CUDA 12.4
pip install -r https://raw.githubusercontent.com/SesameAILabs/csm/main/requirements.txt
# Note: Windows requires triton-windows instead of triton

# VAD
pip install silero-vad  # or load via torch.hub

# Web framework
pip install "fastapi[standard]" uvicorn[standard]

# Audio processing
pip install sounddevice librosa numpy scipy

# Utilities
pip install pydantic python-dotenv redis  # redis optional
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| STT | faster-whisper + distil-whisper | OpenAI Whisper baseline | 4-6x slower, same accuracy. Latency budget too tight. |
| STT | faster-whisper | Parakeet TDT | Parakeet mentioned for low-latency but less ecosystem support. Whisper ecosystem more mature. |
| LLM Serving | vLLM | TensorRT-LLM | TensorRT supports Gemma 3 (added recently) but vLLM has better Python SDK, easier deployment, and proven 20k+ tok/sec on Gemma 3 27B. TensorRT for advanced optimization later. |
| TTS | CSM | ElevenLabs API / Play.ht | API latency kills sub-500ms target. CSM is self-hosted, Apache 2.0, Sesame-quality output. |
| Web Framework | FastAPI | Flask + Flask-SocketIO | Flask is WSGI (sync), handles 2k-3k req/sec vs FastAPI's 15k-20k. No native WebSocket support. Case study showed 64% latency drop migrating Flask → FastAPI. |
| Web Framework | FastAPI | Bare websockets library | FastAPI provides routing, dependency injection, validation. Websockets library too low-level for full application. |
| Audio I/O | sounddevice | PyAudio | PyAudio is lower-level, returns bytes vs NumPy arrays. sounddevice better for scipy/librosa integration, actively maintained (Jan 2026 release). |
| VAD | Silero VAD | WebRTC VAD | WebRTC uses GMM (traditional signal processing), lower AUC than Silero. Silero trained on 6000+ languages, handles diverse audio better. RTF 0.004 is fast enough. |
| Cloud GPU | RunPod | Lambda Labs / Vast.ai | RunPod has 30s deployment, 31 regions, per-second billing. Competitive pricing ($1.99-2.17/hr for A100 80GB). Community + Secure Cloud options. |
| Quantization | INT4 (QAT models) | INT8 / BF16 | Gemma 3 27B: 54GB BF16 vs 14.1GB INT4. INT4 QAT models designed for 1% accuracy loss. Fits single RTX 3090 (24GB) or leaves 65GB free on A100 80GB for KV cache + other models. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| OpenAI Realtime API | Vendor lock-in, no control over latency, costs scale with usage, can't self-host models. Project requires self-hosted Gemma + CSM. | Self-hosted pipeline (faster-whisper + vLLM + CSM) |
| Celery for real-time audio | Celery is for background jobs, not real-time streaming. Adds unnecessary latency vs direct async processing. | FastAPI async endpoints with asyncio |
| Flask for WebSocket server | WSGI is synchronous, Flask-SocketIO is a workaround. 2k-3k req/sec vs FastAPI's 15k-20k. Poor fit for long-lived streaming connections. | FastAPI with native ASGI WebSocket support |
| Batch-only Whisper | Requires full audio before transcription. Incompatible with streaming conversation (need turn detection). | faster-whisper + whisper_streaming for realtime |
| Base Whisper without distil/faster | Too slow (143s for 13-min audio). Latency budget is sub-500ms end-to-end. | faster-whisper (4x faster) or distil-whisper (6x faster) |
| WebRTC VAD for diverse audio | GMM-based, trained on narrow dataset. Lower accuracy (AUC) than Silero on out-of-domain audio. Twilio sources have background noise. | Silero VAD (ML-based, 6000+ languages) |
| pydub for real-time streaming | Designed for file manipulation, not streaming buffers. Higher overhead than sounddevice + NumPy. | sounddevice for I/O + librosa for resampling |
| Pip install torch without CUDA | CSM and Silero VAD require GPU inference. CPU-only torch won't work for TTS. | torch with CUDA 12.4/12.6 from PyTorch index |
| Gunicorn alone (without Uvicorn) | Gunicorn is WSGI server. Need ASGI for FastAPI. Pattern: Gunicorn manages Uvicorn workers. | Uvicorn (dev) or Gunicorn + Uvicorn workers (prod) |

## Stack Patterns by Configuration

### Development Setup
- **Uvicorn standalone**: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- **Local GPU**: Test on RTX 3090 (24GB) with Gemma 3 27B INT4 (14.1GB)
- **ngrok for Twilio webhook**: Expose local server for Media Streams WebSocket

### Production Setup
- **Gunicorn + Uvicorn workers**: `gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker`
- **Docker Compose**: vLLM container + FastAPI app container + Redis (optional)
- **Multi-GPU**: vLLM with `--tensor-parallel-size 4` to split Gemma 3 across GPUs
- **RunPod Secure Cloud**: SLA + persistent storage for model weights
- **Health checks**: `/health` endpoint, Docker healthcheck every 30s

### Quantization Strategy
- **Development**: BF16 if VRAM available (54GB for Gemma 27B) for debugging
- **Production**: INT4 QAT (14.1GB for Gemma 27B) to maximize VRAM for KV cache
- Use `--gpu-memory-utilization 0.90` in vLLM to reserve 90% for KV cache

### Audio Format Conversions
- **Twilio → Models**: 8kHz μ-law PCM → 16kHz PCM via librosa.load(sr=16000)
- **Models → Twilio**: Resample TTS output to 8kHz μ-law, base64 encode for Media Streams
- **CSM output**: Native sample rate via torchaudio.save() → resample → Twilio format

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| vLLM 0.9.0+ | Python 3.10-3.13 | Python 3.12+ recommended as of Feb 2026. vLLM released Feb 5, 2026. |
| vLLM | CUDA 12.4/12.6 | Match CUDA version between vLLM and torch installations. |
| faster-whisper | Python 3.9+ | Requires cuBLAS + cuDNN 9 for GPU. PyAV bundled (no FFmpeg install needed). |
| CSM | Python 3.10 | Tested with CUDA 12.4/12.6. Newer Python versions may work. Windows needs triton-windows. |
| FastAPI | Uvicorn 0.40.0+ | Uvicorn is ASGI server for FastAPI. Use Gunicorn to manage Uvicorn workers in prod. |
| sounddevice 0.5.5 | NumPy latest | Released Jan 23, 2026. Cross-platform (Linux/macOS/Windows). |
| Gemma 3 27B INT4 | vLLM 0.8.0+ | Quantized models require vLLM >= 0.8.0. RedHatAI/gemma-3-27b-it-quantized.w4a16 on HF. |
| distil-large-v3 | faster-whisper | Distil-Whisper designed for faster-whisper CTranslate2 algorithm. |
| Silero VAD | torch 2.x | Load via torch.hub or standalone package. Requires PyTorch (CPU inference OK). |

## Critical Configuration Notes

### Latency Budget Breakdown (Sub-500ms Target)
- **Network (Twilio ↔ Server)**: ~50-100ms (edge routing, buffer 40-80ms)
- **STT (faster-whisper + VAD)**: ~100-150ms (streaming mode, distil-whisper for speed)
- **LLM (vLLM Gemma 27B)**: ~100-200ms (depends on prompt length, continuous batching helps)
- **TTS (CSM)**: ~100-150ms (streaming audio generation, unclear from docs - needs benchmarking)
- **Audio conversion overhead**: ~10-30ms (resampling, encoding)
- **Headroom**: ~50-100ms (variance, spikes)

**Risk**: CSM latency characteristics not well-documented. May need profiling to confirm sub-500ms is achievable.

### VRAM Planning (A100 80GB)
- **Gemma 3 27B INT4**: 14.1GB
- **KV Cache**: ~20-30GB (depends on context length, batch size)
- **CSM 1B**: ~2-4GB (estimated, Llama backbone + audio decoder)
- **faster-whisper**: ~2-5GB (depends on model size: large-v3 vs distil-large-v3)
- **Silero VAD**: ~50-100MB (tiny model)
- **Overhead (CUDA kernels, buffers)**: ~5-10GB
- **Total**: ~45-65GB (fits A100 80GB with headroom)

**Alternative**: Multi-GPU with tensor parallelism if single GPU insufficient.

### Twilio Audio Quirks
- **Sample rate**: 8kHz μ-law (PSTN standard), low quality for modern ASR
- **Always resample to 16kHz**: Models trained on 16kHz+ (Whisper, etc). Quality loss from 8kHz source but unavoidable.
- **Bidirectional streams**: Requires base64 encoding for audio sent back to Twilio
- **Frame size**: ~20ms packets, expect jitter, buffer 40-80ms

### vLLM Streaming API
- **AsyncLLM.generate()**: Returns async iterator for token streaming
- **OpenAI-compatible server**: `/v1/chat/completions` with `stream=true`
- **New (2026)**: `/v1/realtime` WebSocket endpoint for streaming inputs + outputs
- Use streaming to reduce perceived latency (start TTS as soon as first tokens arrive)

### CSM Limitations
- **Not a multimodal LLM**: Only generates audio, doesn't generate text responses
- **Requires separate LLM**: Gemma 3 27B for dialogue logic → CSM for audio synthesis
- **Context parameter**: `context=[]` for conversation history (audio snippets to maintain continuity)
- **Hugging Face auth**: Needs HF token for Llama-3.2-1B and CSM-1B checkpoints

### FastAPI + Twilio Media Streams Pattern
```python
from fastapi import FastAPI, WebSocket
app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Twilio sends JSON messages: {"event": "media", "media": {"payload": "<base64>"}}
    # Decode base64 → process → encode response → send back
```

## Sources

### High Confidence (Official Docs, Context7, Recent Releases)
- [Twilio Media Streams Overview](https://www.twilio.com/docs/voice/media-streams) — WebSocket API, audio formats
- [Twilio Media Streams WebSocket Messages](https://www.twilio.com/docs/voice/media-streams/websocket-messages) — Message format, bidirectional streams
- [twilio-python GitHub Releases](https://github.com/twilio/twilio-python/releases) — v9.10.1 released Feb 5, 2026
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) — Performance benchmarks, installation
- [vLLM Documentation](https://docs.vllm.ai/) — Streaming API, deployment
- [vLLM Async Streaming Example](https://docs.vllm.ai/en/latest/examples/offline_inference/async_llm_streaming/) — AsyncLLM usage
- [vLLM Blog: Streaming & Realtime API](https://blog.vllm.ai/2026/01/31/streaming-realtime.html) — Feb 2026 features
- [CSM GitHub](https://github.com/SesameAILabs/csm) — Model architecture, installation, limitations
- [Silero VAD GitHub](https://github.com/snakers4/silero-vad) — Performance metrics, usage
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) — Native WebSocket support
- [sounddevice PyPI](https://pypi.org/project/sounddevice/) — v0.5.5 release Jan 23, 2026
- [Google Gemma 3 Model Overview](https://ai.google.dev/gemma/docs/core) — Official model specs

### Medium Confidence (Verified Web Sources, Multiple Sources Agree)
- [Use vLLM on GKE to serve Gemma 3 27B](https://docs.cloud.google.com/ai-hypercomputer/docs/tutorials/gpu/gemma-3-vllm-inference) — Google Cloud tutorial, 20k+ tok/sec
- [Gemma 3 QAT Models](https://developers.googleblog.com/en/gemma-3-quantized-aware-trained-state-of-the-art-ai-to-consumer-gpus/) — INT4 quantization, 14.1GB VRAM
- [RunPod A100 Pricing](https://www.runpod.io/gpu-models/a100-pcie) — $1.39-2.17/hr range
- [Choosing Best VAD 2026](https://picovoice.ai/blog/best-voice-activity-detection-vad/) — Silero vs WebRTC comparison
- [Best STT Model 2026 Benchmarks](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks) — faster-whisper, distil-whisper performance
- [FastAPI vs Flask 2026 Migration](https://medium.com/@inprogrammer/fastapi-vs-flask-in-2026-i-migrated-a-real-app-with-metrics-864042103f5a) — 64% latency drop
- [Core Latency in AI Voice Agents (Twilio)](https://www.twilio.com/en-us/blog/developers/best-practices/guide-core-latency-ai-voice-agents) — Latency best practices
- [Deploying CSM (Cerebrium)](https://www.cerebrium.ai/articles/deploying-sesame-csm-the-most-realistic-voice-model) — CSM deployment guide
- [vLLM Docker Deployment Guide (2026)](https://inference.net/content/vllm-docker-deployment/) — Production setup

### Low Confidence (Single Source or Needs Validation)
- CSM latency characteristics — Not documented, needs benchmarking
- Exact VRAM for CSM 1B — Estimated 2-4GB based on architecture, not verified
- RunPod 30-second deployment claim — From marketing materials, not independently verified
- whisper_streaming 3.3s latency — From repo docs, needs validation on this project's audio sources

---
*Stack research for: Real-Time AI Voice Calling System*
*Researched: 2026-02-22*
*Primary researcher focus: Ecosystem + latency optimization + self-hosted stack*
