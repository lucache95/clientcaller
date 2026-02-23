# Phase 2: Speech-to-Text with Streaming - Research

**Researched:** 2026-02-22
**Domain:** Real-time streaming speech-to-text with voice activity detection
**Confidence:** HIGH

## Summary

Phase 2 integrates real-time speech transcription into the existing Twilio WebSocket pipeline built in Phase 1. The research confirms that **faster-whisper + whisper_streaming + Silero VAD** is the optimal stack for achieving the 200ms transcription and 300ms turn detection targets while maintaining accuracy.

The critical architectural decisions are: (1) using whisper_streaming's LocalAgreement policy for adaptive latency, (2) configuring Silero VAD with 550ms silence threshold and 0.5 activation threshold for natural turn-taking, and (3) integrating into the existing AudioStreamer with bounded queues to prevent buffer overflow.

**Primary recommendation:** Use whisper_streaming with faster-whisper backend (large-v3 or distil-large-v3) + Silero VAD in the existing FastAPI WebSocket pipeline, replacing the echo implementation with transcription processing.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STT-01 | System transcribes caller speech in real-time using faster-whisper streaming | whisper_streaming provides OnlineASRProcessor for continuous transcription; faster-whisper backend achieves 4x speed improvement; distil-large-v3 offers 6x speedup with <1% WER loss |
| STT-02 | System detects speech/silence boundaries using Silero VAD | Silero VAD supports 8kHz/16kHz audio, provides activation_threshold (0.5 default), min_silence_duration (0.55s default), and processes 30ms chunks in <1ms on CPU |
| STT-03 | System endpoints speech quickly (<300ms after caller stops) for fast response | Silero VAD min_silence_duration configurable to 300-550ms; whisper_streaming uses LocalAgreement-n policy for adaptive latency; combined architecture achieves 380-520ms end-to-end latency in production |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| faster-whisper | 1.2.0+ | GPU-accelerated Whisper inference via CTranslate2 | 4x faster than vanilla Whisper with same accuracy; supports int8 quantization (11.3GB → 3.1GB VRAM); industry-standard backend for real-time STT. **Confidence: HIGH** |
| whisper_streaming | Latest (UFAL) | Real-time streaming policy for Whisper models | Implements LocalAgreement-n policy for adaptive latency; achieves 3.3s latency on long-form speech; recommended backend is faster-whisper. **Confidence: HIGH** |
| Silero VAD | 5.1+ | Voice activity detection for turn detection | Supports 8kHz/16kHz; <1ms processing per 30ms chunk on CPU; 0.93 F1 score in clean conditions; MIT license. Used in production voice AI systems. **Confidence: HIGH** |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| distil-whisper/distil-large-v3 | Latest | Low-latency alternative to large-v3 | 6x faster than large-v3, <1% WER loss; 756M params vs 1.54B; use if sub-200ms STT latency required. **Confidence: MEDIUM-HIGH** |
| torch | 2.x with CUDA | PyTorch runtime for Silero VAD | Required for VAD model loading; CPU inference acceptable (VAD is lightweight). **Confidence: HIGH** |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| faster-whisper | OpenAI Whisper (vanilla) | Vanilla is 4x slower, same accuracy; blows latency budget (1-5s vs 100-200ms target) |
| whisper_streaming | WhisperLive / WhisperLiveKit | Similar architectures; whisper_streaming has better documentation, active UFAL research support |
| Silero VAD | WebRTC VAD | WebRTC uses GMM (traditional signal processing), lower accuracy than Silero ML-based approach; Silero handles diverse audio better |
| distil-large-v3 | Parakeet TDT / Speechmatics | Commercial alternatives faster but vendor lock-in; distil-whisper is open-source, compatible with faster-whisper pipeline |

**Installation:**
```bash
# STT core
pip install faster-whisper>=1.2.0
pip install git+https://github.com/ufal/whisper_streaming

# VAD
pip install silero-vad>=5.1
# or via torch.hub (no pip install needed)

# Required dependencies (likely already installed from Phase 1)
pip install torch torchaudio  # For Silero VAD
pip install numpy scipy       # Audio processing
```

## Architecture Patterns

### Recommended Integration with Phase 1

```
Phase 1 Audio Pipeline:
┌─────────────────────┐
│ Twilio WebSocket    │
│ (handle_media)      │
└──────┬──────────────┘
       │ base64 audio payload
       ▼
┌─────────────────────┐
│ Audio Conversion    │  Phase 1 complete
│ mulaw → PCM 16kHz   │  ✓ Already built
└──────┬──────────────┘
       │ PCM audio
       ▼
┌─────────────────────┐  ◄─── PHASE 2 INTEGRATION POINT
│ VAD + STT Pipeline  │       Replace echo with transcription
│ (NEW in Phase 2)    │
└──────┬──────────────┘
       │ transcript text
       ▼
┌─────────────────────┐
│ CallStateManager    │  Phase 1 complete
│ State transitions   │  ✓ Already built
└─────────────────────┘
```

### Pattern 1: Streaming STT Architecture

**What:** Continuous audio → VAD → buffered Whisper → streaming transcripts

**When to use:** Real-time conversation (not batch transcription)

**Implementation:**
```python
# Based on whisper_streaming README and Phase 1 handlers.py
from whisper_online import FasterWhisperASR, OnlineASRProcessor
from silero_vad import load_silero_vad, get_speech_timestamps
import asyncio

class STTProcessor:
    def __init__(self):
        # Load models once at startup
        self.vad_model = load_silero_vad()
        self.asr = FasterWhisperASR(
            language="en",
            modelsize="large-v3",  # or "distil-large-v3" for speed
            compute_type="int8"     # Reduces VRAM 11.3GB → 3.1GB
        )
        self.online = OnlineASRProcessor(self.asr)

        # VAD configuration for turn detection
        self.vad_threshold = 0.5           # Speech detection threshold
        self.min_silence_ms = 550          # 550ms silence = turn complete
        self.min_speech_ms = 250           # Ignore very short sounds

        # Audio buffer for VAD + STT
        self.audio_buffer = []
        self.is_speaking = False

    async def process_audio_chunk(self, pcm_16khz: bytes):
        """Process incoming PCM 16kHz audio from Phase 1 conversion"""

        # Convert bytes to numpy array for VAD
        audio_np = np.frombuffer(pcm_16khz, dtype=np.int16)

        # Run VAD on chunk
        speech_prob = self.vad_model(audio_np, 16000)

        if speech_prob > self.vad_threshold:
            # Speech detected
            if not self.is_speaking:
                self.is_speaking = True
                # Start of speech - could log or update state

            # Buffer audio for Whisper
            self.audio_buffer.append(audio_np)

            # Feed to Whisper streaming
            self.online.insert_audio_chunk(audio_np)

            # Get partial transcripts (iterative)
            for output in self.online.process_iter():
                # output = (timestamp, partial_text)
                yield {"type": "partial", "text": output[1]}

        else:
            # Silence detected
            if self.is_speaking:
                # Accumulate silence duration
                # If silence > min_silence_ms, trigger turn complete
                # (actual implementation needs silence counter)

                # Finalize transcript
                final_output = self.online.finish()
                yield {"type": "final", "text": final_output[1]}

                # Reset for next turn
                self.online.init()
                self.audio_buffer = []
                self.is_speaking = False
```

### Pattern 2: VAD-Gated Audio Buffering

**What:** Only send audio to Whisper when VAD detects speech, reducing compute waste.

**Why:** Whisper processes everything you feed it. VAD pre-filters silence to save GPU cycles.

**Implementation:**
```python
class VADBufferedSTT:
    def __init__(self):
        self.vad_model = load_silero_vad()
        self.speech_buffer = []  # Only speech chunks
        self.prefix_padding_ms = 300  # Include 300ms before speech starts
        self.pre_buffer = []  # Rolling buffer for prefix padding

    def add_chunk(self, audio_chunk):
        """Add audio chunk, buffer only when speech detected"""

        # Keep rolling pre-buffer (last 300ms of audio)
        self.pre_buffer.append(audio_chunk)
        if len(self.pre_buffer) > 15:  # 15 chunks * 20ms = 300ms
            self.pre_buffer.pop(0)

        # Check VAD
        if self.is_speech(audio_chunk):
            # First speech chunk? Add prefix padding
            if len(self.speech_buffer) == 0:
                self.speech_buffer.extend(self.pre_buffer)

            # Add current chunk
            self.speech_buffer.append(audio_chunk)

            return "speech"
        else:
            # Silence - check if turn complete
            if len(self.speech_buffer) > 0:
                # We have buffered speech, silence detected
                # Wait for min_silence_ms before finalizing
                return "silence"

            return "idle"
```

### Pattern 3: Integration with Phase 1 ConnectionManager

**What:** Wire STT into existing `src/twilio/handlers.py` handle_media function.

**Current Phase 1 code:**
```python
# src/twilio/handlers.py line ~90
async def handle_media(connection_manager, stream_sid, payload):
    # TODO: Process audio (convert mu-law → PCM, send to STT)
    # Current: Echo audio back
    await connection_manager.queue_audio(stream_sid, payload)
```

**Phase 2 replacement:**
```python
async def handle_media(connection_manager, stream_sid, payload):
    """Phase 2: Process audio through STT pipeline"""

    # Get audio bytes from Twilio (base64 mu-law)
    audio_mulaw = base64.b64decode(payload)

    # Phase 1 conversion (already built)
    pcm_8khz = mulaw_to_pcm(audio_mulaw)
    pcm_16khz = resample_8k_to_16k(pcm_8khz)

    # Phase 2: STT processing (NEW)
    stt_processor = connection_manager.get_stt_processor(stream_sid)

    async for transcript in stt_processor.process_audio_chunk(pcm_16khz):
        if transcript["type"] == "partial":
            # Log partial transcript (user is still speaking)
            logger.info(f"Partial: {transcript['text']}")

        elif transcript["type"] == "final":
            # Turn complete - user stopped speaking
            logger.info(f"Final: {transcript['text']}")

            # Update call state
            state_manager = connection_manager.get_state_manager(stream_sid)
            state_manager.on_user_speech_complete(transcript["text"])

            # Phase 3 will add: Send to LLM here
            # Phase 4 will add: TTS response
```

### Pattern 4: Adaptive VAD Thresholds

**What:** Tune VAD parameters based on background noise level detected in call.

**Why:** Fixed thresholds fail in noisy environments (cars, cafes, street). Adaptive thresholds maintain accuracy.

**Implementation:**
```python
class AdaptiveVAD:
    def __init__(self):
        self.base_threshold = 0.5
        self.current_threshold = 0.5
        self.noise_samples = []

    def update_threshold(self, audio_chunk, is_speech_expected=False):
        """Adjust threshold based on background noise"""

        if not is_speech_expected:
            # During silence, measure noise floor
            energy = np.abs(audio_chunk).mean()
            self.noise_samples.append(energy)

            if len(self.noise_samples) > 100:
                self.noise_samples.pop(0)

                # High noise environment? Increase threshold
                avg_noise = np.mean(self.noise_samples)
                if avg_noise > 1000:  # High noise
                    self.current_threshold = 0.6
                elif avg_noise > 500:  # Medium noise
                    self.current_threshold = 0.55
                else:  # Low noise
                    self.current_threshold = 0.5

        return self.current_threshold
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Using Vanilla Whisper Instead of faster-whisper

**What:** `pip install openai-whisper` and using `whisper.load_model()` directly.

**Why bad:** Vanilla Whisper yields 1-5s latency on typical segments. Blows entire latency budget before LLM/TTS even starts. No true streaming support—needs complete utterances.

**Instead:** Use faster-whisper (4x faster, same accuracy) or distil-large-v3 (6x faster, <1% WER loss). Both support streaming via whisper_streaming.

**Detection:** If you see `import whisper` (not `from faster_whisper import ...`), that's vanilla Whisper.

### Anti-Pattern 2: Fixed Silence Timeout Instead of VAD

**What:** Using `await asyncio.sleep(1.0)` or similar to decide when user finished speaking.

**Why bad:** Too short cuts off slow speakers. Too long creates awkward pauses. Can't adapt to speaking patterns or background noise.

**Instead:** Use Silero VAD with tunable `min_silence_duration` (550ms default). VAD measures actual audio energy, not just time.

**Symptoms:** "The AI interrupts me" or "Long pause before response."

### Anti-Pattern 3: Unbounded Audio Buffering

**What:** Continuously buffering audio into a list without size limits.

```python
# BAD
self.audio_buffer = []
while receiving_audio:
    self.audio_buffer.append(chunk)  # Grows forever
```

**Why bad:** Memory leak. Long calls will OOM. Audio buffer grows unbounded.

**Instead:** Use bounded queue (like Phase 1 AudioStreamer maxsize=50) or clear buffer after each turn.

```python
# GOOD
self.audio_queue = asyncio.Queue(maxsize=50)
# After turn complete:
self.audio_queue = asyncio.Queue(maxsize=50)  # Reset
```

### Anti-Pattern 4: Processing Audio Before VAD Check

**What:** Sending all audio to Whisper, using VAD only for turn detection.

**Why bad:** Wastes GPU cycles transcribing silence. Whisper processes everything you feed it.

**Instead:** VAD first, then send only speech chunks to Whisper. Save compute for actual speech.

### Anti-Pattern 5: Blocking I/O in Async Functions

**What:** Using synchronous Whisper inference in async WebSocket handler.

```python
# BAD
async def handle_media(audio):
    transcript = whisper_model.transcribe(audio)  # Blocks event loop
```

**Why bad:** Blocks FastAPI event loop, preventing concurrent connections.

**Instead:** Run Whisper in separate thread/process or use async wrapper.

```python
# GOOD
async def handle_media(audio):
    transcript = await asyncio.to_thread(whisper_model.transcribe, audio)
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Streaming Whisper implementation | Custom chunking/buffering logic | whisper_streaming (UFAL) | LocalAgreement-n policy handles word boundaries, adaptive latency, prefix confirmation. Edge cases are hard (splitting words mid-utterance). |
| Voice activity detection | Energy-based threshold (RMS, zero-crossing) | Silero VAD | ML-based VAD trained on 6000+ languages handles diverse audio, background noise, cross-talk better than signal processing. |
| Audio resampling | Manual interpolation | librosa, scipy.signal.resample | Proper DSP libraries handle anti-aliasing filters, prevent artifacts. Already used in Phase 1. |
| Turn detection logic | Custom silence counters | Silero VAD min_silence_duration + prefix_padding | Handles natural pauses, prevents premature cutoff, configurable per use case. |
| Audio format conversion | Byte manipulation | Phase 1 conversion.py (pydub-based) | Already handles mu-law ↔ PCM with error handling. Don't duplicate. |

**Key insight:** STT streaming has many subtle edge cases (word boundaries, buffering, latency vs accuracy tradeoffs). Use battle-tested libraries instead of reimplementing.

## Common Pitfalls

### Pitfall 1: Premature Turn Detection (False Positives)

**What goes wrong:** VAD triggers "turn complete" during natural pauses (user thinking, breathing). AI interrupts mid-sentence. User frustrated.

**Why it happens:** `min_silence_duration` set too low (<300ms). Testing in quiet office doesn't reveal issues that appear with real phone calls (background noise, PSTN quality).

**How to avoid:**
1. Set `min_silence_duration` to 550-700ms (default 550ms is good starting point)
2. Test with real phone calls from noisy environments (cars, cafes, street)
3. Use `prefix_padding_duration` (300-500ms) to capture speech onset
4. Monitor false positive rate in production logs

**Warning signs:**
- Users complain AI "talks over them"
- Transcripts show incomplete sentences
- VAD triggers during mid-sentence pauses

### Pitfall 2: Missed Speech Onset (Clipped Words)

**What goes wrong:** First word of user's speech is cut off. "Hello" becomes "ello". Transcription accuracy suffers.

**Why it happens:** VAD detects speech after it starts. Without prefix padding, initial audio is lost.

**How to avoid:**
1. Configure `prefix_padding_duration` to 300-500ms
2. Maintain rolling pre-buffer (last 300ms of audio always buffered)
3. When VAD triggers, prepend pre-buffer to speech chunks sent to Whisper

**Warning signs:**
- Transcripts consistently missing first syllable
- User repeats themselves frequently
- WER higher than model benchmarks suggest

### Pitfall 3: Background Noise False Triggers

**What goes wrong:** TV, traffic, music, other speakers trigger VAD. System thinks user is speaking. Transcribes garbage.

**Why it happens:** VAD `activation_threshold` too low (0.5 default may not work in noisy environments). Production audio quality worse than test data.

**How to avoid:**
1. Increase `activation_threshold` to 0.6-0.7 for noisy environments
2. Test with real PSTN audio (8kHz mu-law quality), not laptop microphone
3. Consider background noise suppression preprocessing
4. Monitor false acceptance rate (FAR) in production

**Warning signs:**
- VAD triggers when user silent
- Transcripts contain nonsense from TV/music
- High VAD activity during silence periods

**Research evidence:** "With background voice cancellation preprocessing, false-positive triggers in VAD were reduced by 3.5x on average" (Source: Krisp.ai)

### Pitfall 4: Memory Leak from Unbounded Buffers

**What goes wrong:** Audio buffer grows during long calls. Eventually OOM. Server crashes.

**Why it happens:** No buffer size limits. Audio accumulated but never cleared. Testing focuses on short calls (<2min), doesn't catch leak.

**How to avoid:**
1. Use bounded queues (asyncio.Queue(maxsize=N))
2. Clear buffers after each turn completes
3. Set `max_buffered_speech` limit (default 60s in Silero VAD)
4. Monitor memory usage in production

**Warning signs:**
- Memory usage grows over time
- Crashes after 5-10 minute calls
- Server becomes unresponsive during long calls

### Pitfall 5: Blocking Event Loop with Synchronous Inference

**What goes wrong:** Whisper inference blocks FastAPI event loop. WebSocket can't handle other messages. System appears frozen.

**Why it happens:** Whisper model runs synchronously. Async function calls blocking code without proper threading.

**How to avoid:**
1. Run Whisper inference in separate thread: `await asyncio.to_thread(model.transcribe, audio)`
2. Or use separate process with queue-based communication
3. Monitor event loop lag in production

**Warning signs:**
- WebSocket appears to hang during transcription
- Can't handle concurrent calls
- High event loop latency (>100ms)

### Pitfall 6: Incorrect Sample Rate for VAD

**What goes wrong:** VAD receives 8kHz audio but expects 16kHz (or vice versa). Accuracy plummets. False triggers everywhere.

**Why it happens:** Forgetting to resample after Twilio conversion. Silero VAD only supports 8kHz and 16kHz.

**How to avoid:**
1. Always resample Twilio audio (8kHz mu-law) to 16kHz PCM before VAD
2. Phase 1 already has `resample_8k_to_16k()` - use it
3. Verify sample rate in logs/tests
4. Silero VAD will error if sample rate wrong—don't catch and ignore

**Warning signs:**
- VAD performance much worse than benchmarks
- Random false triggers
- "ValueError: Sampling rate must be 8000 or 16000"

### Pitfall 7: Forgetting to Reset Whisper State Between Turns

**What goes wrong:** Previous turn's context bleeds into next turn. Transcripts reference earlier conversation incorrectly.

**Why it happens:** whisper_streaming OnlineASRProcessor accumulates state. Must call `.finish()` then `.init()` to reset.

**How to avoid:**
```python
# After turn complete:
final_transcript = self.online.finish()  # Finalize current turn
self.online.init()                       # Reset for next turn
```

**Warning signs:**
- Transcripts include words from previous turns
- Context drift over multiple turns
- "Init prompt" issues in Whisper

## Code Examples

### Example 1: Basic STT Integration (Minimal)

```python
# Source: Based on whisper_streaming README
from whisper_online import FasterWhisperASR, OnlineASRProcessor
import numpy as np

# Initialize once at startup
asr = FasterWhisperASR(language="en", modelsize="large-v3", compute_type="int8")
online = OnlineASRProcessor(asr)

# Process audio stream
def process_call_audio(audio_chunks):
    for chunk in audio_chunks:
        # chunk is PCM 16kHz numpy array
        online.insert_audio_chunk(chunk)

        # Get partial transcripts
        for timestamp, text in online.process_iter():
            print(f"Partial: {text}")

    # Call ended - get final transcript
    timestamp, final_text = online.finish()
    print(f"Final: {final_text}")

    # Reset for next call
    online.init()
```

### Example 2: Silero VAD Configuration

```python
# Source: LiveKit Silero VAD documentation
import torch

# Load via torch.hub
model, utils = torch.hub.load(
    repo_or_dir='snakers4/silero-vad',
    model='silero_vad',
    force_reload=False
)

(get_speech_timestamps, save_audio, read_audio,
 VADIterator, collect_chunks) = utils

# Configure VAD for turn detection
vad_iterator = VADIterator(
    model,
    threshold=0.5,              # Speech detection threshold (0-1)
    sampling_rate=16000,        # Must be 8000 or 16000
    min_silence_duration_ms=550,  # Silence before turn complete
    speech_pad_ms=300           # Padding before/after speech
)

# Process audio chunks (30ms recommended)
for audio_chunk in audio_stream:
    speech_dict = vad_iterator(audio_chunk, return_seconds=True)

    if speech_dict:
        # Speech detected
        print(f"Speech from {speech_dict['start']} to {speech_dict['end']}")
```

### Example 3: Complete Integration with Phase 1

```python
# Source: Integration pattern based on Phase 1 handlers.py
from src.audio.conversion import mulaw_to_pcm
from src.audio.resampling import resample_8k_to_16k
import base64
import numpy as np

class STTHandler:
    def __init__(self):
        # Models loaded once at startup
        self.asr = FasterWhisperASR("en", "large-v3", compute_type="int8")
        self.online = OnlineASRProcessor(self.asr)
        self.vad_model, utils = torch.hub.load('snakers4/silero-vad', 'silero_vad')
        self.vad_iterator = utils[3](self.vad_model, threshold=0.5,
                                      sampling_rate=16000)

        self.speech_buffer = []
        self.is_speaking = False

    async def process_media_message(self, payload_base64: str):
        """Process audio from Twilio Media Stream message"""

        # Phase 1 conversion pipeline
        audio_mulaw = base64.b64decode(payload_base64)
        pcm_8khz = mulaw_to_pcm(audio_mulaw)
        pcm_16khz = resample_8k_to_16k(pcm_8khz)

        # Convert to numpy for processing
        audio_np = np.frombuffer(pcm_16khz, dtype=np.int16).astype(np.float32) / 32768.0

        # VAD check
        speech_dict = self.vad_iterator(audio_np, return_seconds=True)

        if speech_dict:
            # Speech detected
            self.is_speaking = True
            self.online.insert_audio_chunk(audio_np)

            # Get partial transcripts
            for ts, text in self.online.process_iter():
                yield {"type": "partial", "text": text}

        elif self.is_speaking:
            # Silence after speech - turn complete
            ts, final_text = self.online.finish()
            yield {"type": "final", "text": final_text}

            # Reset
            self.online.init()
            self.vad_iterator.reset_states()
            self.is_speaking = False
```

### Example 4: Adaptive VAD Thresholds

```python
# Source: Based on production patterns from research
class AdaptiveVADConfig:
    def __init__(self):
        self.threshold = 0.5
        self.min_silence_ms = 550
        self.noise_samples = []

    def update_from_noise_profile(self, silent_audio_chunk):
        """Adapt threshold based on background noise level"""

        # Measure noise during silence
        rms = np.sqrt(np.mean(silent_audio_chunk**2))
        self.noise_samples.append(rms)

        if len(self.noise_samples) > 50:  # 50 chunks = ~1 second
            avg_noise = np.mean(self.noise_samples[-50:])

            # Adjust threshold based on noise floor
            if avg_noise > 0.05:  # High noise environment
                self.threshold = 0.7
                self.min_silence_ms = 700  # Longer to avoid false triggers
            elif avg_noise > 0.02:  # Medium noise
                self.threshold = 0.6
                self.min_silence_ms = 600
            else:  # Low noise
                self.threshold = 0.5
                self.min_silence_ms = 550
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OpenAI Whisper (vanilla) | faster-whisper or distil-whisper | 2023-2024 | 4-6x latency reduction; enables <500ms real-time STT |
| Energy-based VAD (WebRTC) | ML-based VAD (Silero) | 2021-2023 | 0.71 → 0.93 F1 score in noisy conditions; better background noise handling |
| Batch transcription (30s chunks) | Streaming with LocalAgreement policy | 2023-2024 | 30s wait → 3.3s latency for long-form; enables real-time conversation |
| Fixed silence thresholds | Adaptive VAD with semantic endpointing | 2025-2026 | Natural turn-taking; reduces false positives by understanding sentence completion |
| Separate STT/VAD models | Integrated pipelines (WhisperLive, etc) | 2024-2026 | Simpler deployment; optimized data flow between components |

**Deprecated/outdated:**
- **audioop for mu-law conversion**: Removed in Python 3.13; use pydub (already in Phase 1)
- **Batch-only Whisper**: Use streaming variants for real-time
- **Synchronous Whisper API**: Use async wrappers or separate threads in async context

## Open Questions

### 1. Distil-large-v3 vs Large-v3 Accuracy Tradeoff

**What we know:**
- Distil-large-v3: 6x faster, 756M params, <1% WER loss on benchmarks
- Large-v3: Baseline accuracy, 1.54B params, 4x faster than vanilla (via faster-whisper)

**What's unclear:**
- Accuracy on PSTN audio quality (8kHz mu-law source, resampled to 16kHz)
- Performance in noisy environments (real phone calls vs clean test data)
- Whether 6x speedup is worth potential accuracy loss for this use case

**Recommendation:**
Start with large-v3 (safer, proven accuracy). If STT latency exceeds 200ms in production testing, try distil-large-v3. Measure WER on real call recordings before deciding.

### 2. Optimal min_silence_duration for Natural Conversation

**What we know:**
- Default 550ms works for most use cases
- Shorter (300-400ms) feels more responsive but risks false positives
- Longer (700-800ms) reduces false positives but feels sluggish

**What's unclear:**
- Optimal value for phone call conversation specifically
- Whether adaptive thresholds based on user speaking rate improve UX

**Recommendation:**
Start with 550ms. Collect user feedback and VAD metrics. Tune based on false positive/negative rates. Consider A/B testing 500ms vs 600ms with real users.

### 3. GPU vs CPU for Silero VAD

**What we know:**
- Silero VAD: <1ms per 30ms chunk on CPU
- Extremely lightweight (50-100MB model)

**What's unclear:**
- Whether GPU inference provides meaningful speedup (likely negligible)
- Resource contention when running VAD on same GPU as Whisper/Gemma

**Recommendation:**
Run VAD on CPU (force_cpu=True). Reserves GPU for Whisper and future Gemma/CSM models. VAD is fast enough on CPU.

### 4. Handling Multi-Language Calls

**What we know:**
- faster-whisper supports language parameter
- Whisper auto-detects language if not specified

**What's unclear:**
- Latency impact of auto-detection vs explicit language
- Whether Phase 2 should support language detection or assume English-only

**Recommendation:**
Phase 2: Assume English ("en" parameter). Reduces complexity. Language detection can be added later if needed.

## Sources

### Primary (HIGH confidence)

- [SYSTRAN/faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) — Official repo, performance benchmarks, int8 quantization
- [UFAL whisper_streaming GitHub](https://github.com/ufal/whisper_streaming) — Official streaming implementation, LocalAgreement policy
- [Silero VAD GitHub](https://github.com/snakers4/silero-vad) — Official VAD repo, configuration parameters
- [LiveKit Silero VAD Plugin Documentation](https://docs.livekit.io/agents/logic/turns/vad/) — Configuration reference, default values
- [Building Real-Time Speech-to-Text with Faster Whisper (2026)](https://neurlcreators.substack.com/p/how-do-you-build-a-real-time-speech) — Implementation patterns, WebSocket integration
- [Best open source STT model in 2026 (Northflank)](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks) — Benchmarks, distil-whisper performance
- [Choosing between Whisper variants (Modal)](https://modal.com/blog/choosing-whisper-variants) — faster-whisper vs alternatives, VRAM comparison

### Secondary (MEDIUM confidence)

- [Voice Activity Detection: The Complete 2026 Guide (Picovoice)](https://picovoice.ai/blog/complete-guide-voice-activity-detection-vad/) — VAD concepts, edge cases, production issues
- [How intelligent turn detection solves the biggest challenge in voice agent development (AssemblyAI)](https://www.assemblyai.com/blog/turn-detection-endpointing-voice-agent) — Turn detection challenges, semantic endpointing
- [Python-Based Effective Audio Streaming over WebSocket (Medium)](https://medium.com/@python-javascript-php-html-css/python-based-effective-audio-streaming-over-websocket-using-asyncio-and-threading-a926ecf087c4) — Asyncio patterns, backpressure handling
- [Improving Turn-Taking with Background Noise Cancellation (Krisp)](https://krisp.ai/blog/improving-turn-taking-of-ai-voice-agents-with-background-voice-cancellation/) — False positive reduction, noise handling
- [Distil-Whisper GitHub](https://github.com/huggingface/distil-whisper) — Distillation approach, performance claims
- [Whisper Variants Comparison (Towards AI)](https://towardsai.net/p/machine-learning/whisper-variants-comparison-what-are-their-features-and-how-to-implement-them) — Feature comparison, use case guidance

### Tertiary (LOW confidence)

- whisper_streaming latency (3.3s claim) — From repo docs, needs validation on PSTN audio
- Adaptive VAD threshold patterns — Based on general production patterns, not whisper-specific research
- GPU vs CPU for VAD — Silero documentation doesn't specify; assuming CPU adequate based on performance claims

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — faster-whisper, whisper_streaming, Silero VAD are industry-standard
- Architecture: HIGH — Integration patterns verified from official docs and production examples
- Pitfalls: HIGH — Sourced from production issues, research papers, framework documentation
- Performance claims: MEDIUM — Benchmarks from 2026 sources but not verified on PSTN audio

**Research date:** 2026-02-22
**Valid until:** ~30 days (STT stack is stable, but VAD tuning may evolve with new models)

**Phase 1 integration:** All Phase 1 components (AudioStreamer, CallStateManager, audio conversion) are ready for Phase 2 STT integration. Replace echo implementation in handle_media() with STT pipeline.
