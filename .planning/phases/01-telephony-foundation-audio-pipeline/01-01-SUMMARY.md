---
phase: 01-telephony-foundation-audio-pipeline
plan: 01
subsystem: telephony-server
tags: [websocket, audio-conversion, twilio, fastapi]
dependencies:
  requires: []
  provides:
    - websocket-endpoint
    - twilio-message-handlers
    - audio-conversion-pipeline
    - audio-resampling-utilities
  affects: []
tech-stack:
  added:
    - FastAPI (web framework)
    - Twilio SDK (telephony integration)
    - pydub (audio format conversion)
    - librosa + resampy (audio resampling)
    - pydantic-settings (configuration management)
  patterns:
    - WebSocket message routing pattern
    - Connection manager for active call tracking
    - Mu-law ↔ PCM conversion pipeline
    - 8kHz ↔ 16kHz resampling pipeline
key-files:
  created:
    - src/main.py (FastAPI application with WebSocket endpoint)
    - src/config.py (pydantic-based configuration)
    - src/twilio/models.py (Pydantic models for message validation)
    - src/twilio/handlers.py (message handlers and ConnectionManager)
    - src/audio/conversion.py (mu-law ↔ PCM conversion functions)
    - src/audio/resampling.py (8kHz ↔ 16kHz resampling functions)
    - tests/test_audio_conversion.py (unit tests for audio pipeline)
    - requirements.txt (Python dependencies)
    - .env.example (environment configuration template)
  modified:
    - .gitignore (added Python/venv artifacts)
decisions:
  - decision: Use pydub instead of deprecated audioop module
    rationale: audioop removed in Python 3.13, pydub provides modern alternative with FFmpeg backend
    impact: Requires FFmpeg as system dependency
  - decision: Use librosa with kaiser_fast resampling mode
    rationale: 5x faster than default quality mode, acceptable quality trade-off for real-time audio
    impact: Added resampy dependency for kaiser_fast support
  - decision: Configure pydantic Settings with extra="ignore"
    rationale: Allow existing .env file to contain additional keys without validation errors
    impact: Settings model is more flexible for future expansion
metrics:
  duration_minutes: 4
  tasks_completed: 3
  files_created: 12
  tests_added: 3
  commits: 3
  completed_at: "2026-02-22T08:55:03Z"
---

# Phase 01 Plan 01: WebSocket Server & Audio Pipeline Summary

**One-liner:** FastAPI WebSocket server with Twilio Media Streams integration, mu-law/PCM conversion, and 8kHz/16kHz resampling using pydub and librosa

## What Was Built

Established the foundational infrastructure for real-time telephony by creating a FastAPI WebSocket server that handles Twilio Media Streams connections and implements a complete audio format conversion pipeline.

### Core Components

1. **FastAPI WebSocket Server** (`src/main.py`)
   - WebSocket endpoint at `/ws` for Twilio Media Streams
   - Health check endpoint at `/health` with active connection count
   - Comprehensive error handling and logging
   - Message-based routing to event handlers

2. **Twilio Message Handling** (`src/twilio/handlers.py`, `src/twilio/models.py`)
   - ConnectionManager tracks active WebSocket connections by call_sid
   - Pydantic models validate Twilio message structure
   - Handlers for connected, start, media, stop events
   - Audio echo functionality for initial testing

3. **Audio Conversion Pipeline** (`src/audio/conversion.py`)
   - `mulaw_to_pcm()`: Convert Twilio's 8-bit mu-law to 16-bit PCM numpy arrays
   - `pcm_to_mulaw()`: Convert 16-bit PCM back to mu-law for Twilio
   - `twilio_to_model_format()`: Complete pipeline (base64 → mu-law → PCM)
   - `model_to_twilio_format()`: Reverse pipeline (PCM → mu-law → base64)
   - Uses pydub with FFmpeg backend (not deprecated audioop)

4. **Audio Resampling** (`src/audio/resampling.py`)
   - `resample_8k_to_16k()`: Upsample for ML models (Whisper, CSM)
   - `resample_16k_to_8k()`: Downsample for Twilio telephony
   - Uses librosa with kaiser_fast mode (5x faster than default)
   - All functions work with int16 numpy arrays

5. **Configuration Management** (`src/config.py`)
   - Pydantic-based Settings for type-safe configuration
   - Environment variable loading with .env support
   - Configured to ignore extra keys for flexibility

### Test Coverage

Created `tests/test_audio_conversion.py` with 3 passing tests:
- **test_mulaw_roundtrip**: Validates >95% correlation after PCM → mu-law → PCM conversion
- **test_resampling_roundtrip**: Ensures 8kHz → 16kHz → 8kHz preserves sample count within 1%
- **test_resampling_doubles_length**: Verifies upsampling ratio is 1.9-2.1x (expected ~2x)

All tests pass with strong validation metrics.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Settings validation error with existing .env file**
- **Found during:** Task 1, config loading test
- **Issue:** Pydantic Settings rejected extra environment variables (RUNPOD_API_KEY, GOOGLE_API_KEY, etc.) that were already in .env
- **Fix:** Added `extra = "ignore"` to Settings.Config to allow additional env vars without validation errors
- **Files modified:** `src/config.py`
- **Commit:** d870ee9

**2. [Rule 3 - Blocking] Missing resampy dependency**
- **Found during:** Task 3, running audio tests
- **Issue:** librosa's kaiser_fast resampling mode requires resampy package, which was not in requirements.txt
- **Fix:** Added `resampy>=0.4.0` to requirements.txt and installed package
- **Files modified:** `requirements.txt`
- **Commit:** bdb51cf
- **Impact:** Tests now pass; resampy is required for fast real-time resampling

## Verification Results

All plan verification criteria met:

- ✅ FastAPI server starts without errors
- ✅ `/health` endpoint returns 200 OK with connection count
- ✅ `/ws` WebSocket endpoint exists and accepts connections
- ✅ Audio conversion tests pass (>95% correlation)
- ✅ Audio resampling tests pass (1.9-2.1x length ratio)
- ✅ All Python imports succeed without ImportError
- ✅ Message handlers exist for all Twilio event types (connected, start, media, stop)
- ✅ Project structure matches research recommendations

### Test Output
```
tests/test_audio_conversion.py::test_mulaw_roundtrip PASSED
tests/test_audio_conversion.py::test_resampling_roundtrip PASSED
tests/test_audio_conversion.py::test_resampling_doubles_length PASSED
============================== 3 passed in 1.34s ==============================
```

### Server Validation
```
Routes: ['/health', '/ws']
Status: All imports successful
Audio functions: mulaw_to_pcm, pcm_to_mulaw, resample_8k_to_16k, resample_16k_to_8k available
```

## Dependencies Added

**Python packages (requirements.txt):**
- fastapi[standard]>=0.115.0 (web framework)
- uvicorn[standard]>=0.40.0 (ASGI server)
- twilio>=9.10.1 (SDK)
- pydub>=0.25.1 (audio conversion)
- soundfile>=0.12.1 (audio I/O)
- numpy>=1.26.0 (array operations)
- librosa>=0.11.0 (audio resampling)
- resampy>=0.4.0 (kaiser_fast resampling backend)
- pydantic>=2.10.0 (validation)
- python-dotenv>=1.0.0 (env loading)
- websockets>=16.0 (WebSocket support)
- pytest>=8.0.0, pytest-asyncio>=0.25.0 (testing)
- httpx>=0.27.0 (async HTTP client)

**System dependencies:**
- FFmpeg (required by pydub for audio format conversion)

## Ready for Next Plan

This plan establishes the foundation for:
- **Plan 02:** Deepgram STT integration (audio pipeline is ready)
- **Plan 03:** Call state management (WebSocket handlers and ConnectionManager in place)
- **Future phases:** LLM integration, TTS, interruption handling

**No blockers.** Core infrastructure is solid and tested.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | d870ee9 | Initialize project structure and dependencies |
| 2 | 5988b54 | Implement FastAPI WebSocket endpoint with Twilio message handling |
| 3 | bdb51cf | Implement audio format conversion and resampling modules |

## Self-Check: PASSED

**Files created verification:**
```
✓ src/main.py
✓ src/config.py
✓ src/twilio/models.py
✓ src/twilio/handlers.py
✓ src/audio/conversion.py
✓ src/audio/resampling.py
✓ tests/test_audio_conversion.py
✓ requirements.txt
✓ .env.example
```

**Commits verification:**
```
✓ d870ee9 (Task 1)
✓ 5988b54 (Task 2)
✓ bdb51cf (Task 3)
```

**Functionality verification:**
```
✓ Server starts without errors
✓ Health endpoint responds correctly
✓ WebSocket endpoint exists
✓ All tests pass (3/3)
✓ All imports work
```

All claimed deliverables exist and function as specified.
