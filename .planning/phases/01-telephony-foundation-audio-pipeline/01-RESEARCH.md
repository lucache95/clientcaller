# Phase 1: Telephony Foundation & Audio Pipeline - Research

**Researched:** 2026-02-22
**Domain:** Twilio Media Streams WebSocket integration, real-time audio streaming, audio format conversion
**Confidence:** HIGH

## Summary

Phase 1 establishes the foundation for real-time voice AI by integrating Twilio Media Streams with a FastAPI WebSocket server, implementing bidirectional audio streaming, and handling audio format conversions between telephony (8kHz mu-law) and ML model formats (16kHz PCM). The core challenge is building a robust async pipeline that maintains sub-500ms latency while gracefully handling connection lifecycle, audio buffering, and format conversions.

**Key technical decisions:**
- FastAPI with native WebSocket support provides 5-7x better throughput than Flask (15k-20k req/sec vs 2k-3k)
- Audio format conversion must be explicit and optimized—silent conversion overhead can consume 100-200ms of latency budget
- Connection state management requires careful async patterns to prevent race conditions
- Testing locally requires ngrok tunneling since Twilio requires public WSS endpoints

**Primary recommendation:** Build a minimal viable pipeline first (connect, receive audio, convert formats, send back test audio) before adding sophistication. Measure latency at every boundary. Use proper audio libraries (not deprecated audioop) and implement backpressure handling from the start.

<phase_requirements>
## Phase Requirements

This phase addresses requirements TEL-01, TEL-02, TEL-03, TEL-04 from REQUIREMENTS.md.

| ID | Description | Research Support |
|----|-------------|-----------------|
| TEL-01 | System accepts inbound calls via Twilio WebSocket Media Streams | FastAPI WebSocket endpoint with Twilio Media Streams integration (see Standard Stack: FastAPI + websockets). Message handling pattern documented in Architecture Patterns. |
| TEL-02 | System initiates outbound calls to specified phone numbers | Twilio Python SDK client.calls.create() API with TwiML Voice response (see Standard Stack: twilio-python 9.10.1+). TwiML Stream tag configuration documented. |
| TEL-03 | System converts audio between mu-law 8kHz (Twilio) and PCM 16kHz (models) | Mu-law ↔ PCM conversion using pydub/soundfile (audioop deprecated in Python 3.13). Resampling with librosa or torchaudio (see Audio Format Conversion pattern). |
| TEL-04 | System maintains bidirectional audio streaming throughout call | Bidirectional Media Streams with WebSocket backpressure handling (see Bidirectional Streaming Pattern). Async connection manager prevents blocking. |

</phase_requirements>

## Standard Stack

### Core Web Framework

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115.0+ | Async WebSocket server for Twilio Media Streams | Native async/await support, 15k-20k req/sec throughput (vs Flask 2k-3k). Built-in WebSocket support without extensions. Critical for long-lived streaming connections. **Confidence: HIGH** |
| uvicorn | 0.40.0+ | ASGI server for FastAPI | Latest stable release (Jan 2026). Production-ready with Gunicorn workers for multi-process scaling. Standard ASGI server for FastAPI. **Confidence: HIGH** |
| websockets | 16.0+ | WebSocket protocol implementation | Used by FastAPI internally. Can also be used directly for custom WebSocket clients. Supports async patterns. **Confidence: MEDIUM** |

### Twilio Integration

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| twilio | 9.10.1+ | Twilio API client and TwiML generation | Official Python SDK, actively maintained (Feb 5, 2026 release). Provides client.calls.create() for outbound calls and VoiceResponse for TwiML generation. **Confidence: HIGH** |

### Audio Processing

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydub | 0.25.1+ | Audio format conversion (mu-law ↔ PCM) | High-level audio manipulation. Replacement for deprecated audioop module (removed Python 3.13). Supports format conversions via FFmpeg. **Confidence: MEDIUM-HIGH** |
| soundfile | 0.12.1+ | Audio I/O and format handling | PySoundFile provides mu-law encoding/decoding via libsndfile. Clean API for reading/writing audio files. Alternative to deprecated audioop. **Confidence: MEDIUM-HIGH** |
| numpy | 1.26.0+ | Audio buffer manipulation | Essential for real-time audio array operations. Block-based processing for streaming buffers. Fast C-backed operations. **Confidence: HIGH** |
| librosa | 0.11.0+ | Audio resampling (8kHz ↔ 16kHz) | Industry standard for audio feature extraction and resampling. Simple API: librosa.load(sr=16000). Use res_type='kaiser_fast' for real-time performance (5x faster than default). **Confidence: HIGH** |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.10.0+ | Data validation for WebSocket messages | FastAPI dependency. Use for validating Twilio message structure, configuration models. Type-safe state objects. **Confidence: HIGH** |
| python-dotenv | 1.0.0+ | Environment variable management | Load Twilio credentials, ngrok URLs, configuration from .env file. Standard practice for secrets management. **Confidence: HIGH** |
| pytest-asyncio | 0.25.0+ | Testing async WebSocket handlers | Required for testing FastAPI WebSocket endpoints. Supports async test functions with @pytest.mark.asyncio. **Confidence: MEDIUM** |

### Installation

```bash
# Core web framework
pip install "fastapi[standard]" uvicorn[standard]

# Twilio integration
pip install twilio>=9.10.1

# Audio processing
pip install pydub soundfile numpy librosa

# Note: FFmpeg required for pydub (system dependency)
# Linux: sudo apt-get install ffmpeg
# macOS: brew install ffmpeg

# Supporting libraries
pip install pydantic python-dotenv websockets

# Development/testing
pip install pytest pytest-asyncio httpx  # httpx for FastAPI testing
```

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI | Flask + Flask-SocketIO | Flask is WSGI (synchronous), handles 2k-3k req/sec vs FastAPI's 15k-20k. No native WebSocket support. 64% latency increase in migration case studies. |
| pydub/soundfile | audioop module | audioop deprecated in Python 3.11, removed in Python 3.13. No longer available for modern Python versions. |
| librosa resampling | scipy.signal.resample | librosa uses soxr backend by default (higher quality). scipy.signal is lower-level, requires more manual configuration for proper anti-aliasing. |
| Twilio Media Streams | Twilio Programmable Voice API (non-streaming) | Voice API provides call recording/transcription but not real-time audio access. Media Streams required for <500ms latency streaming use case. |
| FastAPI WebSocket | websockets library only | FastAPI provides routing, dependency injection, validation. Raw websockets library is too low-level for full application. |

## Architecture Patterns

### Recommended Project Structure

```
src/
├── main.py                    # FastAPI app, WebSocket endpoint
├── twilio/
│   ├── client.py             # Twilio API client (outbound calls, TwiML)
│   ├── handlers.py           # WebSocket message handlers (connected, start, media, stop)
│   └── models.py             # Pydantic models for Twilio messages
├── audio/
│   ├── conversion.py         # Mu-law ↔ PCM conversion
│   ├── resampling.py         # 8kHz ↔ 16kHz resampling
│   └── buffers.py            # Audio buffer management
├── state/
│   └── manager.py            # Connection state machine (IDLE, LISTENING, SPEAKING)
└── config.py                 # Configuration (Twilio credentials, URLs)

tests/
├── test_websocket.py         # WebSocket connection tests
├── test_audio_conversion.py  # Audio format conversion tests
└── fixtures/
    └── sample_audio.wav      # Test audio files
```

### Pattern 1: FastAPI WebSocket Endpoint for Twilio Media Streams

**What:** FastAPI WebSocket route that accepts Twilio Media Streams connections, handles message types, and maintains bidirectional audio flow.

**When to use:** Required for all Twilio Media Streams integrations. This is the foundation pattern.

**Implementation:**

```python
# Source: FastAPI official docs + Twilio Media Streams docs
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict
import json
import base64

app = FastAPI()

# Connection manager for tracking active calls
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, call_sid: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[call_sid] = websocket

    def disconnect(self, call_sid: str):
        self.active_connections.pop(call_sid, None)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    call_sid = None

    try:
        async for message in websocket.iter_text():
            data = json.loads(message)
            event = data.get("event")

            if event == "connected":
                print("WebSocket connected to Twilio")

            elif event == "start":
                # Extract stream metadata
                call_sid = data["start"]["callSid"]
                stream_sid = data["start"]["streamSid"]
                await manager.connect(call_sid, websocket)
                print(f"Stream started: {stream_sid}")

            elif event == "media":
                # Receive audio from Twilio
                payload = data["media"]["payload"]
                audio_bytes = base64.b64decode(payload)
                # TODO: Process audio (convert mu-law → PCM, send to STT)

                # Echo audio back (for testing)
                response = {
                    "event": "media",
                    "streamSid": data["streamSid"],
                    "media": {
                        "payload": payload  # Echo back same audio
                    }
                }
                await websocket.send_text(json.dumps(response))

            elif event == "stop":
                print(f"Stream stopped: {data['stop']['callSid']}")
                if call_sid:
                    manager.disconnect(call_sid)

    except WebSocketDisconnect:
        print(f"WebSocket disconnected: {call_sid}")
        if call_sid:
            manager.disconnect(call_sid)
```

**Key requirements:**
- Use `await websocket.accept()` immediately upon connection
- Handle all message types: connected, start, media, stop (optionally: mark, dtmf)
- Decode base64 audio payload from media messages
- Encode base64 audio when sending back to Twilio
- Track active connections by call_sid for multi-call support

### Pattern 2: Audio Format Conversion (Mu-law ↔ PCM)

**What:** Convert between Twilio's 8-bit mu-law format and standard 16-bit PCM for ML models.

**Why critical:** Twilio uses mu-law (telephony standard), but Whisper/ML models expect linear PCM. Conversion must be correct or audio will be garbled.

**Implementation:**

```python
# Source: pydub documentation + mu-law conversion examples
from pydub import AudioSegment
from pydub.utils import mediainfo
import numpy as np
import io

def mulaw_to_pcm(mulaw_bytes: bytes, sample_rate: int = 8000) -> np.ndarray:
    """
    Convert mu-law encoded bytes to PCM numpy array.

    Args:
        mulaw_bytes: Raw mu-law audio bytes
        sample_rate: Sample rate (Twilio uses 8000 Hz)

    Returns:
        numpy array of int16 PCM samples
    """
    # Create AudioSegment from mu-law bytes
    audio = AudioSegment.from_file(
        io.BytesIO(mulaw_bytes),
        format="mulaw",
        frame_rate=sample_rate,
        channels=1,
        sample_width=1  # mu-law is 8-bit
    )

    # Convert to 16-bit PCM
    pcm_audio = audio.set_sample_width(2)  # 2 bytes = 16-bit

    # Convert to numpy array
    samples = np.array(pcm_audio.get_array_of_samples(), dtype=np.int16)
    return samples

def pcm_to_mulaw(pcm_samples: np.ndarray, sample_rate: int = 8000) -> bytes:
    """
    Convert PCM numpy array to mu-law encoded bytes.

    Args:
        pcm_samples: numpy array of int16 PCM samples
        sample_rate: Sample rate (Twilio expects 8000 Hz)

    Returns:
        mu-law encoded bytes (base64 encode before sending to Twilio)
    """
    # Create AudioSegment from numpy array
    audio = AudioSegment(
        pcm_samples.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,  # 16-bit PCM
        channels=1
    )

    # Export as mu-law
    buffer = io.BytesIO()
    audio.export(buffer, format="mulaw", codec="pcm_mulaw")
    return buffer.getvalue()

# Alternative using soundfile (if preferred)
import soundfile as sf

def mulaw_to_pcm_soundfile(mulaw_bytes: bytes) -> np.ndarray:
    """Alternative using soundfile library"""
    with io.BytesIO(mulaw_bytes) as f:
        data, samplerate = sf.read(f, dtype='int16', format='RAW',
                                     subtype='ULAW', channels=1, samplerate=8000)
    return data
```

**Pitfall to avoid:** Don't use deprecated `audioop` module (removed in Python 3.13). Use pydub or soundfile instead.

### Pattern 3: Audio Resampling (8kHz ↔ 16kHz)

**What:** Resample audio between Twilio's 8kHz and ML model's 16kHz sample rates.

**Why necessary:** Whisper and other STT models are trained on 16kHz+ audio. 8kHz telephony audio must be upsampled. TTS output must be downsampled to 8kHz for Twilio.

**Implementation:**

```python
# Source: librosa documentation
import librosa
import numpy as np

def resample_8k_to_16k(audio_8k: np.ndarray) -> np.ndarray:
    """
    Resample audio from 8kHz to 16kHz for ML models.

    Args:
        audio_8k: numpy array of samples at 8kHz

    Returns:
        numpy array of samples at 16kHz
    """
    # Use kaiser_fast for speed (5x faster than default)
    # Trade-off: slightly lower quality but acceptable for real-time
    audio_16k = librosa.resample(
        audio_8k.astype(np.float32),
        orig_sr=8000,
        target_sr=16000,
        res_type='kaiser_fast'  # Fast resampling for real-time
    )
    return audio_16k.astype(np.int16)

def resample_16k_to_8k(audio_16k: np.ndarray) -> np.ndarray:
    """
    Resample audio from 16kHz to 8kHz for Twilio.

    Args:
        audio_16k: numpy array of samples at 16kHz

    Returns:
        numpy array of samples at 8kHz
    """
    audio_8k = librosa.resample(
        audio_16k.astype(np.float32),
        orig_sr=16000,
        target_sr=8000,
        res_type='kaiser_fast'
    )
    return audio_8k.astype(np.int16)

# Complete pipeline: Twilio → ML model format
def twilio_to_model_format(mulaw_payload: str) -> np.ndarray:
    """
    Complete conversion from Twilio audio to ML model format.

    Args:
        mulaw_payload: Base64-encoded mu-law audio from Twilio

    Returns:
        numpy array of 16-bit PCM samples at 16kHz
    """
    import base64

    # Decode base64
    mulaw_bytes = base64.b64decode(mulaw_payload)

    # Convert mu-law → PCM
    pcm_8k = mulaw_to_pcm(mulaw_bytes, sample_rate=8000)

    # Resample 8kHz → 16kHz
    pcm_16k = resample_8k_to_16k(pcm_8k)

    return pcm_16k

# Complete pipeline: ML model → Twilio format
def model_to_twilio_format(pcm_16k: np.ndarray) -> str:
    """
    Complete conversion from ML model output to Twilio format.

    Args:
        pcm_16k: numpy array of 16-bit PCM samples at 16kHz

    Returns:
        Base64-encoded mu-law audio for Twilio
    """
    import base64

    # Resample 16kHz → 8kHz
    pcm_8k = resample_16k_to_8k(pcm_16k)

    # Convert PCM → mu-law
    mulaw_bytes = pcm_to_mulaw(pcm_8k, sample_rate=8000)

    # Encode base64
    mulaw_payload = base64.b64encode(mulaw_bytes).decode('utf-8')

    return mulaw_payload
```

**Performance note:** librosa with `res_type='kaiser_fast'` is 5x faster than default but still may add 10-30ms latency. For ultra-low latency, consider torchaudio or custom resampling.

### Pattern 4: Bidirectional Streaming with Backpressure

**What:** Handle audio flowing both directions (Twilio → server, server → Twilio) without buffer overflow or blocking.

**Why critical:** TTS may generate audio faster than network can transmit. Without backpressure, buffers overflow or memory leaks occur.

**Implementation:**

```python
# Source: FastAPI WebSocket docs + asyncio patterns
import asyncio
from asyncio import Queue
from typing import Optional

class AudioStreamer:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.outbound_queue: Queue[bytes] = Queue(maxsize=50)  # ~1 second buffer
        self.running = False

    async def start(self):
        """Start background task to send queued audio to Twilio"""
        self.running = True
        asyncio.create_task(self._send_loop())

    async def stop(self):
        """Stop background sending"""
        self.running = False

    async def queue_audio(self, audio_payload: str):
        """
        Queue audio for sending to Twilio.

        Implements backpressure: if queue is full, this will block
        until space is available, preventing memory overflow.
        """
        try:
            # This blocks if queue is full (backpressure)
            await asyncio.wait_for(
                self.outbound_queue.put(audio_payload),
                timeout=1.0  # Fail if can't queue within 1 second
            )
        except asyncio.TimeoutError:
            print("WARNING: Audio queue full, dropping packet")

    async def _send_loop(self):
        """Background task to send queued audio to Twilio"""
        while self.running:
            try:
                # Get next audio chunk (blocks if empty)
                payload = await self.outbound_queue.get()

                # Send to Twilio
                message = {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": payload}
                }
                await self.websocket.send_text(json.dumps(message))

                # Small delay to match real-time playback rate
                # Prevents sending faster than Twilio can play
                await asyncio.sleep(0.020)  # 20ms per chunk

            except Exception as e:
                print(f"Error sending audio: {e}")
                break

# Usage in WebSocket handler
streamer = AudioStreamer(websocket)
await streamer.start()

# Later, when TTS generates audio
audio_chunk = model_to_twilio_format(tts_output)
await streamer.queue_audio(audio_chunk)
```

**Key requirements:**
- Use bounded queue (maxsize) to prevent unbounded memory growth
- Implement timeout on queue.put() to detect stalls
- Send audio at real-time rate (~20ms chunks) to match playback speed
- Use asyncio.create_task() for background sending, don't block main loop

### Pattern 5: State Machine for Call Lifecycle

**What:** Track call state to prevent race conditions and ensure proper resource cleanup.

**States:**
- IDLE: No active call
- CONNECTING: WebSocket accepted, waiting for "start" message
- ACTIVE: Call in progress, audio flowing
- STOPPING: Received "stop" message, cleaning up
- ERROR: Abnormal termination

**Implementation:**

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class CallState(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    ACTIVE = "active"
    STOPPING = "stopping"
    ERROR = "error"

@dataclass
class CallContext:
    state: CallState
    call_sid: Optional[str] = None
    stream_sid: Optional[str] = None
    websocket: Optional[WebSocket] = None
    connected_at: Optional[datetime] = None

class CallStateManager:
    def __init__(self):
        self.calls: Dict[str, CallContext] = {}

    async def on_connected(self, websocket: WebSocket):
        """Handle WebSocket connection"""
        ctx = CallContext(state=CallState.CONNECTING, websocket=websocket)
        # Temporarily store by websocket id until we get call_sid
        temp_id = id(websocket)
        self.calls[temp_id] = ctx
        return ctx

    async def on_start(self, temp_id: int, call_sid: str, stream_sid: str):
        """Handle stream start message"""
        ctx = self.calls.pop(temp_id)
        ctx.call_sid = call_sid
        ctx.stream_sid = stream_sid
        ctx.state = CallState.ACTIVE
        ctx.connected_at = datetime.now()
        self.calls[call_sid] = ctx
        return ctx

    async def on_stop(self, call_sid: str):
        """Handle stream stop message"""
        ctx = self.calls.get(call_sid)
        if ctx:
            ctx.state = CallState.STOPPING
            # Cleanup will happen in finally block
        return ctx

    async def cleanup(self, call_sid: str):
        """Remove call from tracking"""
        self.calls.pop(call_sid, None)
```

### Anti-Patterns to Avoid

**Anti-Pattern 1: Synchronous Audio Processing in WebSocket Handler**

**What:** Processing audio synchronously in the message handler, blocking the WebSocket receive loop.

**Why bad:** WebSocket can't receive new messages while processing, causing buffering and latency spikes.

**Instead:** Use asyncio.create_task() to process audio in background, keep WebSocket loop responsive.

```python
# BAD - blocks WebSocket loop
async def handle_media(data):
    audio = process_audio(data["payload"])  # Takes 100ms
    result = await model.transcribe(audio)  # Takes 200ms
    # WebSocket can't receive messages for 300ms!

# GOOD - non-blocking
async def handle_media(data):
    asyncio.create_task(process_audio_async(data["payload"]))
    # WebSocket loop continues immediately
```

**Anti-Pattern 2: Not Handling WebSocket Disconnects**

**What:** Missing try/except for WebSocketDisconnect, causing crashes and resource leaks.

**Why bad:** Users hang up, networks fail. Ungraceful handling leaves orphaned resources.

**Instead:** Always wrap WebSocket loops in try/except and cleanup in finally block.

**Anti-Pattern 3: Ignoring Audio Format Specifications**

**What:** Assuming Twilio accepts any audio format, or that conversion happens automatically.

**Why bad:** Twilio requires exactly 8kHz mu-law, base64-encoded. Wrong format = silent failure or garbled audio.

**Instead:** Explicitly validate and convert to required format. Test with known-good audio samples.

**Anti-Pattern 4: Using Deprecated audioop Module**

**What:** Using audioop.ulaw2lin() and audioop.lin2ulaw() for mu-law conversion.

**Why bad:** audioop removed in Python 3.13. Code will break on newer Python versions.

**Instead:** Use pydub or soundfile libraries (see Pattern 2).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket connection pooling | Custom connection manager with locks | FastAPI + async patterns | FastAPI handles concurrency correctly with async/await. Custom connection pools are prone to race conditions and deadlocks. |
| Audio format detection | Custom header parsing | pydub/soundfile libraries | Audio format detection is complex (dozens of container formats, codecs). Libraries handle edge cases. |
| Resampling algorithms | Custom interpolation | librosa or torchaudio | Proper resampling requires anti-aliasing filters. Custom code introduces artifacts. Libraries are 10-100x faster. |
| Base64 encoding/decoding | Custom base64 implementation | Python's built-in base64 module | Built-in is C-optimized, handles padding/line breaks correctly. No reason to reimplement. |
| WebSocket heartbeat/keepalive | Custom ping/pong | FastAPI's built-in keepalive | FastAPI and underlying libraries handle connection health automatically. |

**Key insight:** Audio processing is deceptively complex. Sample rate conversion, format encoding, and buffer management have edge cases that take years to discover. Use battle-tested libraries.

## Common Pitfalls

### Pitfall 1: Audio Format Conversion Consumes Latency Budget

**What goes wrong:** Each conversion (base64 decode, mu-law → PCM, resample 8kHz → 16kHz) adds latency. Naive implementations consume 100-200ms of the 500ms budget before any AI processing.

**Why it happens:** Developers focus on correctness, not performance. Default resampling algorithms prioritize quality over speed.

**How to avoid:**
1. Profile every conversion step individually—measure actual latency
2. Use `librosa.resample(res_type='kaiser_fast')` instead of default (5x speedup)
3. Consider torchaudio for GPU-accelerated resampling if needed
4. Minimize conversions—ideally convert once on input, process in native format, convert once on output
5. Batch conversions where possible (process 100-200ms chunks, not 20ms frames)

**Warning signs:**
- Total latency exceeds budget but model inference looks reasonable
- CPU usage spikes during audio handling
- Profiling shows >15% of time in resampling functions

### Pitfall 2: WebSocket Backpressure Causes Audio Stalls

**What goes wrong:** TTS generates audio faster than network can transmit. WebSocket send buffer fills up, causing bursts of audio followed by silence.

**Why it happens:** WebSocket doesn't automatically slow producers when consumers can't keep up. TTS generates at 10x+ real-time speed.

**How to avoid:**
1. Implement flow control with bounded queues (see Pattern 4)
2. Monitor queue depth—alert if consistently >70% full
3. Send audio at real-time rate (20-40ms chunks) matching playback speed
4. Use asyncio.wait_for() with timeout on queue operations to detect stalls
5. Test with bandwidth throttling to simulate mobile networks

**Warning signs:**
- Audio plays in bursts with silence between
- WebSocket send buffer memory grows over time
- Successful test calls but failures after 30-60 seconds in production
- Network monitoring shows bursty traffic instead of smooth stream

### Pitfall 3: Using Deprecated audioop Module

**What goes wrong:** Code works on Python 3.12 but breaks on Python 3.13+ when audioop is removed.

**Why it happens:** audioop was convenient and well-documented, but deprecated in Python 3.11 and removed in 3.13.

**How to avoid:**
1. Use pydub or soundfile for mu-law conversions (see Pattern 2)
2. Check Python version in CI/CD—fail if audioop is imported
3. Test on Python 3.13 to catch breakage early

**Warning signs:**
- ImportError: No module named 'audioop' on Python 3.13
- Deprecation warnings in Python 3.11-3.12

### Pitfall 4: Jitter Buffer Misconfiguration Creates Sluggish Feel

**What goes wrong:** Default jitter buffers (50-100ms) optimize for audio quality but make AI feel slow to respond.

**Why it happens:** Telecom defaults prioritize zero packet loss over latency. Adaptive jitter buffers grow for worst-case jitter and don't shrink.

**How to avoid:**
1. This is primarily a Twilio/network-level concern, not application code
2. Be aware that network jitter buffering adds 40-80ms beyond your control
3. Use WebRTC mode instead of PSTN when possible (better jitter handling, Opus codec)
4. Budget 50-100ms for network overhead in latency calculations
5. Test on real PSTN calls, not just localhost—network characteristics differ dramatically

**Warning signs:**
- Consistent "delay feeling" even when processing times are good
- 100-150ms latency that doesn't correlate with processing or distance
- Latency dramatically better on local network vs real calls

### Pitfall 5: No Local Testing Strategy

**What goes wrong:** Can't test without deploying to public server. Development cycle is slow and painful.

**Why it happens:** Twilio requires public WSS endpoint. Localhost isn't accessible from internet.

**How to avoid:**
1. Use ngrok for local development tunneling (see Pattern 6)
2. Create mock Twilio WebSocket clients for unit testing
3. Record real Twilio WebSocket messages for replay testing
4. Set up staging environment that mirrors production

**Warning signs:**
- Only testing in production
- Long cycle time for minor changes (deploy, test, fix, repeat)
- No automated tests for WebSocket handling

### Pitfall 6: Connection State Race Conditions

**What goes wrong:** Multiple async tasks modify call state simultaneously, causing corruption or crashes.

**Why it happens:** WebSocket receives messages while background tasks send audio. Without proper synchronization, race conditions occur.

**How to avoid:**
1. Use single-threaded async event loop—don't use threading
2. Implement state machine with atomic transitions (see Pattern 5)
3. Use asyncio.Lock for critical sections if needed
4. Avoid shared mutable state—prefer message passing via queues

**Warning signs:**
- Intermittent failures that are hard to reproduce
- State machine in impossible states (e.g., ACTIVE but no WebSocket)
- Deadlocks or hanging connections

## Code Examples

### Pattern 6: Local Development with ngrok

**Setting up ngrok for Twilio development:**

```bash
# Install ngrok (macOS)
brew install ngrok

# Or download from https://ngrok.com/download

# Start ngrok tunnel to local server
ngrok http 8000

# ngrok will display a forwarding URL like:
# Forwarding: https://abc123.ngrok.io -> http://localhost:8000

# Use this URL in Twilio configuration
```

**Configuring Twilio phone number to use ngrok URL:**

```python
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream

# Initialize Twilio client
client = Client(account_sid, auth_token)

# Update phone number with TwiML webhook
twiml = VoiceResponse()
connect = Connect()
stream = Stream(url='wss://abc123.ngrok.io/ws')  # Use ngrok WSS URL
connect.append(stream)
twiml.append(connect)

# Update phone number
phone_number = client.incoming_phone_numbers.get(phone_number_sid)
phone_number.update(voice_url=f'https://abc123.ngrok.io/twiml')

# Or use TwiML Bin for static configuration
```

**FastAPI endpoint to serve TwiML:**

```python
from fastapi.responses import Response

@app.post("/twiml")
async def twiml():
    """Serve TwiML to establish Media Stream"""
    response = VoiceResponse()
    connect = Connect()
    # Replace with actual ngrok URL or production domain
    stream = Stream(url='wss://your-domain.ngrok.io/ws')
    connect.append(stream)
    response.append(connect)

    return Response(content=str(response), media_type="application/xml")
```

### Pattern 7: Testing Audio Conversion Pipeline

**Unit test for format conversion:**

```python
import pytest
import numpy as np
from audio.conversion import mulaw_to_pcm, pcm_to_mulaw
from audio.resampling import resample_8k_to_16k, resample_16k_to_8k

def test_mulaw_roundtrip():
    """Test mu-law → PCM → mu-law preserves audio"""
    # Generate test audio (1 second sine wave at 440 Hz)
    sample_rate = 8000
    duration = 1.0
    frequency = 440
    t = np.linspace(0, duration, int(sample_rate * duration))
    original_pcm = (np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)

    # Convert PCM → mu-law → PCM
    mulaw_bytes = pcm_to_mulaw(original_pcm, sample_rate)
    recovered_pcm = mulaw_to_pcm(mulaw_bytes, sample_rate)

    # Check similarity (mu-law is lossy, so allow some error)
    correlation = np.corrcoef(original_pcm, recovered_pcm)[0, 1]
    assert correlation > 0.95, "Audio significantly degraded"

def test_resampling_roundtrip():
    """Test 8kHz → 16kHz → 8kHz preserves shape"""
    # Generate 8kHz test audio
    audio_8k = np.random.randint(-32768, 32767, size=8000, dtype=np.int16)

    # Resample up and down
    audio_16k = resample_8k_to_16k(audio_8k)
    audio_8k_recovered = resample_16k_to_8k(audio_16k)

    # Check lengths match
    assert len(audio_8k_recovered) == len(audio_8k)

    # Check correlation (resampling is lossy)
    correlation = np.corrcoef(audio_8k, audio_8k_recovered)[0, 1]
    assert correlation > 0.90

@pytest.mark.asyncio
async def test_websocket_echo():
    """Test WebSocket audio echo"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    with client.websocket_connect("/ws") as websocket:
        # Simulate Twilio connected message
        websocket.send_json({"event": "connected", "protocol": "Call", "version": "1.0.0"})

        # Simulate start message
        websocket.send_json({
            "event": "start",
            "start": {
                "streamSid": "test-stream",
                "callSid": "test-call",
                "tracks": ["inbound"],
                "mediaFormat": {
                    "encoding": "audio/x-mulaw",
                    "sampleRate": 8000,
                    "channels": 1
                }
            }
        })

        # Send test audio
        test_payload = base64.b64encode(b'\x00' * 160).decode()  # 20ms of silence
        websocket.send_json({
            "event": "media",
            "streamSid": "test-stream",
            "media": {"payload": test_payload}
        })

        # Receive echo response
        response = websocket.receive_json()
        assert response["event"] == "media"
        assert "payload" in response["media"]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| audioop module for mu-law | pydub/soundfile libraries | Python 3.13 (2024) | audioop removed, must use alternatives |
| Flask + Flask-SocketIO | FastAPI native WebSocket | FastAPI 0.6+ (2019+) | 5-7x throughput improvement, native async |
| Default librosa resampling | kaiser_fast mode | Always available but often overlooked | 5x speed improvement for real-time use |
| Synchronous request handlers | Async/await patterns | Python 3.5+ (2015) but adoption ongoing | Enables concurrent request handling without threads |

**Deprecated/outdated:**
- **audioop module**: Removed in Python 3.13. Use pydub or soundfile.
- **Flask-SocketIO for production**: Not async-native. Use FastAPI.
- **Default resampling without res_type**: Too slow for real-time. Use kaiser_fast.

## Open Questions

1. **What is actual latency overhead of audio conversion pipeline?**
   - What we know: librosa kaiser_fast is 5x faster than default, conversion adds some overhead
   - What's unclear: Exact latency in milliseconds for complete pipeline (base64 → mu-law → PCM → resample)
   - Recommendation: Profile in Phase 1 with instrumentation. Measure each step individually. Target <50ms total conversion overhead.

2. **Can we use GPU for audio resampling to reduce latency?**
   - What we know: torchaudio supports GPU-accelerated resampling
   - What's unclear: Whether GPU overhead (data transfer) offsets benefits for small chunks
   - Recommendation: Test torchaudio GPU resampling if profiling shows resampling >30ms. May not be worth complexity.

3. **How to handle Twilio WebSocket reconnections?**
   - What we know: WebSockets can disconnect due to network issues
   - What's unclear: Does Twilio automatically reconnect? Do we need to implement reconnection logic?
   - Recommendation: Research Twilio Media Streams reconnection behavior. Implement graceful degradation (hang up call if WebSocket fails).

4. **What's the optimal chunk size for real-time processing?**
   - What we know: Twilio sends ~20ms chunks. Larger chunks improve batching but increase latency.
   - What's unclear: Optimal chunk size for balancing latency and throughput
   - Recommendation: Start with 100-200ms chunks (5-10 Twilio frames buffered). Test with varying sizes.

## Sources

### Primary (HIGH confidence)

- [Twilio Media Streams Overview](https://www.twilio.com/docs/voice/media-streams) - Official documentation for Media Streams
- [Media Streams WebSocket Messages](https://www.twilio.com/docs/voice/media-streams/websocket-messages) - Message format specification
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) - Official FastAPI WebSocket documentation
- [twilio-python GitHub](https://github.com/twilio/twilio-python) - Official Python SDK (v9.10.1 Feb 2026)
- [librosa.resample documentation](https://librosa.org/doc/main/generated/librosa.resample.html) - Resampling API
- [Python audioop deprecation](https://docs.python.org/3/library/audioop.html) - Official notice of removal

### Secondary (MEDIUM confidence)

- [Consume Real-Time Media Stream with WebSockets (Twilio Tutorial)](https://www.twilio.com/docs/voice/tutorials/consume-real-time-media-stream-using-websockets-python-and-flask) - Official tutorial
- [FastAPI WebSocket Best Practices 2026](https://oneuptime.com/blog/post/2026-02-02-fastapi-websockets/view) - Recent implementation guide
- [Managing Multiple WebSocket Clients in FastAPI](https://hexshift.medium.com/managing-multiple-websocket-clients-in-fastapi-ce5b134568a2) - Connection manager pattern
- [Goodbye audioop: NumPy, SciPy, and Pydub alternatives](https://runebook.dev/en/docs/python/library/audioop) - Migration guide
- [Python audio streaming with asyncio backpressure](https://medium.com/@python-javascript-php-html-css/python-based-effective-audio-streaming-over-websocket-using-asyncio-and-threading-a926ecf087c4) - Backpressure patterns
- [FastAPI vs Flask 2026 comparison](https://medium.com/@inprogrammer/fastapi-vs-flask-in-2026-i-migrated-a-real-app-with-metrics-864042103f5a) - Performance benchmarks

### Tertiary (LOW confidence - needs validation)

- Exact latency overhead of audio conversion pipeline - Requires profiling in actual implementation
- GPU-accelerated resampling benefits for real-time streaming - Needs benchmarking
- Twilio WebSocket automatic reconnection behavior - Not clearly documented

## Metadata

**Confidence breakdown:**
- Twilio Media Streams integration: HIGH - Official documentation, multiple working examples
- FastAPI WebSocket patterns: HIGH - Official docs, production use cases
- Audio format conversion: MEDIUM-HIGH - audioop deprecation confirmed, alternatives documented but less tested
- Performance optimization: MEDIUM - Recommendations based on research but need validation in actual implementation

**Research date:** 2026-02-22
**Valid until:** ~60 days (stable technologies, but audio libraries update frequently)

**Key decisions for Phase 1:**
1. Use FastAPI (not Flask) for WebSocket server
2. Use pydub or soundfile (not audioop) for mu-law conversion
3. Use librosa with kaiser_fast (not default) for resampling
4. Implement backpressure from the start (bounded queues)
5. Use ngrok for local development/testing

**Ready for planning:** Yes. Planner has enough detail to create specific implementation tasks.
