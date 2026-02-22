# Architecture Patterns

**Domain:** Real-time AI voice calling systems
**Researched:** 2026-02-22
**Confidence:** HIGH

## Recommended Architecture

Real-time AI voice calling systems use a **cascaded streaming pipeline** architecture connecting telephony → STT → LLM → TTS → telephony in a bidirectional flow. Each component operates as an independent processing unit with asynchronous communication via event streams, state machines, and message queues.

```
┌─────────────┐
│   Twilio    │◄──────────────┐
│   (PSTN)    │               │
└──────┬──────┘               │
       │ WebSocket            │
       │ (mulaw/8kHz)         │
┌──────▼──────────────────────┴───┐
│  Orchestrator / Event Loop      │
│  - State machine (idle/listen/  │
│    process/speak)               │
│  - Audio buffering              │
│  - Turn detection (VAD)         │
│  - Interruption handling        │
└──┬────┬────────────────┬────────┘
   │    │                │
   ▼    ▼                ▼
┌──────┐ ┌────────┐  ┌────────┐
│Whisper│ │ Gemma  │  │  CSM   │
│ STT   │ │  27B   │  │  TTS   │
│(GPU)  │ │ (GPU)  │  │ (GPU)  │
└───────┘ └────────┘  └────────┘
```

### Component Boundaries

| Component | Responsibility | Communicates With | Interface |
|-----------|---------------|-------------------|-----------|
| **Twilio Telephony** | PSTN bridge, WebSocket audio streaming, call routing | Orchestrator only | WebSocket (bidirectional stream) |
| **Orchestrator** | Event routing, state management, audio buffering, turn detection, interruption handling | All components | Async message queues, event loop |
| **Whisper STT** | Streaming speech-to-text with chunked inference | Orchestrator | Audio frames in → text chunks out |
| **Gemma 27B LLM** | Conversational reasoning with streaming token generation | Orchestrator | Text prompt in → token stream out |
| **CSM TTS** | Natural speech synthesis from text tokens | Orchestrator | Text chunks in → audio frames out |
| **VAD (Voice Activity Detection)** | Silence detection, turn detection, interruption detection | Orchestrator | Audio frames → speech probability |

### Data Flow

**Inbound path (user speaks):**
1. Twilio receives PSTN audio → sends mulaw/8kHz WebSocket frames
2. Orchestrator buffers frames → feeds to Whisper in chunks
3. Whisper streams partial transcripts → Orchestrator accumulates text
4. VAD detects silence → Orchestrator triggers "turn complete" event
5. Orchestrator sends accumulated transcript to Gemma 27B

**Outbound path (AI responds):**
6. Gemma 27B streams tokens → Orchestrator buffers sentences
7. Complete sentences → sent to CSM TTS immediately (don't wait for full response)
8. CSM generates audio frames → Orchestrator sends to Twilio WebSocket
9. Twilio plays audio on PSTN call

**Interruption handling:**
- VAD continuously monitors incoming audio even during AI speech
- Speech detected during playback → Orchestrator sends "clear" message to Twilio
- LLM and TTS generation cancelled → system returns to listening state

## Patterns to Follow

### Pattern 1: Streaming at Every Stage
**What:** Never wait for complete outputs. Stream audio chunks, text tokens, and synthesized audio as soon as they're available.

**Why:** Latency compounds across sequential stages. Streaming reduces end-to-end latency from ~3-5s to sub-500ms.

**Implementation:**
```python
# BAD: Wait for full transcript
def process_audio(audio_stream):
    full_transcript = whisper.transcribe(audio_stream)  # Blocks until complete
    llm_response = llm.generate(full_transcript)        # Waits for transcript
    audio = tts.synthesize(llm_response)                # Waits for LLM
    return audio                                        # Total latency: 2-5s

# GOOD: Stream everything
async def process_audio_streaming(audio_stream):
    async for transcript_chunk in whisper.stream(audio_stream):
        orchestrator.accumulate(transcript_chunk)

        if vad.is_turn_complete():
            async for token in llm.stream(orchestrator.get_text()):
                sentence_buffer.add(token)

                if sentence_buffer.is_complete():
                    async for audio_frame in tts.stream(sentence_buffer.text):
                        yield audio_frame  # Latency: 200-500ms
```

### Pattern 2: Event-Driven State Machine
**What:** Use finite state machine to track conversation state and prevent race conditions.

**Why:** Concurrent audio streams create race conditions (e.g., new user speech during AI response). State machines serialize events and prevent overlapping actions.

**States:**
- **IDLE**: No active call
- **LISTENING**: User can speak, STT active, buffering audio
- **PROCESSING**: Turn complete, LLM generating response
- **SPEAKING**: TTS playing audio, monitoring for interruptions
- **INTERRUPTED**: User spoke during SPEAKING, cancelling AI response

**Transitions:**
```
IDLE → LISTENING (call connected)
LISTENING → PROCESSING (VAD detects turn complete)
PROCESSING → SPEAKING (first audio frame from TTS ready)
SPEAKING → LISTENING (TTS complete)
SPEAKING → INTERRUPTED (VAD detects speech)
INTERRUPTED → LISTENING (audio cleared, ready for user)
```

### Pattern 3: Intelligent Buffering
**What:** Use small buffers (100-300ms) for smoothing, not large queues.

**Why:** Large buffers increase latency. Small buffers smooth jitter from variable GPU inference times without adding perceptible delay.

**Implementation:**
```python
class AudioBuffer:
    def __init__(self, target_ms=200):
        self.target_frames = ms_to_frames(target_ms)
        self.buffer = []

    async def add_and_maybe_play(self, frame):
        self.buffer.append(frame)

        # Start playback once minimum buffer accumulated
        if len(self.buffer) >= self.target_frames:
            frame_to_play = self.buffer.pop(0)
            await twilio.send_audio(frame_to_play)
```

### Pattern 4: VAD-Based Turn Detection
**What:** Use Voice Activity Detection (VAD) to determine when user finished speaking, not fixed silence timeouts.

**Why:** Fixed timeouts create unnatural pauses (too short = cuts off user, too long = awkward silence). VAD adapts to speaking patterns.

**Configuration:**
```python
vad_config = {
    "threshold": 0.5,              # Speech probability 0-1 (higher = require louder audio)
    "silence_duration_ms": 700,    # How long silence before turn complete
    "prefix_padding_ms": 300,      # Include audio before VAD triggered
    "min_speech_duration_ms": 250, # Ignore very short sounds
    "frame_size_ms": 30            # VAD evaluation window
}
```

**Tuning guidance:**
- Noisy environments: Increase `threshold` to 0.6-0.7
- Fast-paced conversation: Decrease `silence_duration_ms` to 500-600ms
- Thoughtful speakers: Increase `silence_duration_ms` to 1000-1200ms

### Pattern 5: Concurrent GPU Inference
**What:** Run Whisper, Gemma, and CSM on the same GPU(s) with memory-efficient scheduling.

**Why:** Running models on separate GPUs wastes money. Proper scheduling allows concurrent inference on shared hardware.

**Memory budget (A100 80GB example):**
```
Whisper Large-v3 (faster-whisper, int8):  ~3GB
Gemma 3 27B (4-bit quantized):           ~16GB
CSM 1B + Mimi decoder:                    ~4GB
PyTorch CUDA overhead:                    ~3GB
Inference buffers:                        ~4GB
──────────────────────────────────────────
Total:                                   ~30GB
Available for batching:                  ~50GB
```

**Scheduling strategy:**
- Whisper: Continuous inference (low VRAM, high priority)
- Gemma: Triggered on turn completion (high VRAM, medium priority)
- CSM: Streaming synthesis (medium VRAM, high priority for first chunk)

**Implementation pattern:**
```python
# Use separate process/queue per model to prevent blocking
whisper_queue = asyncio.Queue()
llm_queue = asyncio.Queue()
tts_queue = asyncio.Queue()

async def whisper_worker():
    async for audio_chunk in whisper_queue:
        result = await whisper_model.transcribe(audio_chunk)
        orchestrator.on_transcript(result)

async def llm_worker():
    async for prompt in llm_queue:
        async for token in llm_model.generate_stream(prompt):
            orchestrator.on_token(token)

async def tts_worker():
    async for text in tts_queue:
        async for audio_frame in tts_model.synthesize_stream(text):
            orchestrator.on_audio(audio_frame)
```

### Pattern 6: Graceful Interruption Handling
**What:** Detect user speech during AI playback and immediately stop TTS, clear audio buffer, return to listening.

**Why:** Humans interrupt naturally. Forcing users to wait destroys conversational feel.

**Critical implementation details:**
```python
async def on_speaking_state():
    """AI is speaking, but monitor for interruptions"""

    # Play audio while monitoring VAD
    async for audio_frame in tts_stream:
        # Check VAD on incoming audio even during playback
        if vad.detect_speech(incoming_audio):
            # IMMEDIATE actions (< 50ms):
            await tts_stream.cancel()           # Stop generating new audio
            await twilio.send_clear()           # Clear Twilio's playback buffer
            orchestrator.clear_response_text()  # Discard partial LLM response
            orchestrator.state = State.INTERRUPTED
            break

        await twilio.send_audio(audio_frame)

    # If completed without interruption
    if orchestrator.state == State.SPEAKING:
        orchestrator.state = State.LISTENING
```

**Key requirement:** Client-side audio playout must stop within milliseconds of interrupt detection. This requires Twilio's `<Clear>` message support in bidirectional streams.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Sequential Pipeline Blocking
**What:** Waiting for each stage to fully complete before starting the next.

**Why bad:** Adds 2-5s latency. Whisper finishes → wait → LLM finishes → wait → TTS finishes. Each stage adds hundreds of milliseconds.

**Instead:** Stream outputs immediately. Start TTS as soon as first sentence from LLM is ready, not after full response.

**Symptoms:** "The AI works but feels slow and robotic."

### Anti-Pattern 2: Fixed Silence Timeouts
**What:** Using `time.sleep(1.0)` or similar to decide when user finished speaking.

**Why bad:** Too short cuts off slow speakers. Too long creates awkward pauses. Can't adapt to different speaking styles.

**Instead:** Use VAD with tunable silence duration (700-1000ms typical) that measures actual audio energy, not just time.

**Symptoms:** "The AI interrupts me" or "There's a weird pause before it responds."

### Anti-Pattern 3: Large Audio Buffers for "Smoothness"
**What:** Buffering 1-2 seconds of audio "to prevent stuttering."

**Why bad:** Adds 1-2s latency, defeating the purpose of streaming inference. Hides infrastructure problems instead of fixing them.

**Instead:** Use small buffers (100-300ms) and fix the root cause of jitter (GPU scheduling, network issues).

**Symptoms:** "Latency is good in tests but feels slow in production."

### Anti-Pattern 4: Separate Services in Different Regions
**What:** Running STT, LLM, and TTS on different cloud providers or regions "for best pricing."

**Why bad:** Network latency between services adds 50-200ms per hop. 3 hops = 150-600ms wasted.

**Instead:** Colocate all GPU inference in same datacenter. Inter-service latency should be < 10ms.

**Symptoms:** "Individual components are fast but end-to-end is slow."

### Anti-Pattern 5: No Interruption Handling
**What:** Playing full AI response even if user starts speaking.

**Why bad:** Feels robotic and frustrating. Users expect to interrupt like in human conversation.

**Instead:** Monitor VAD during playback. Cancel TTS and clear buffers immediately on user speech.

**Symptoms:** "The AI talks over me."

### Anti-Pattern 6: Loading Full Models Per Request
**What:** Loading Whisper/Gemma/CSM when call starts, unloading when call ends.

**Why bad:** Model loading takes 5-30 seconds and wastes GPU memory with duplicate loads.

**Instead:** Load models once at startup. Use queuing and batching for concurrent requests.

**Symptoms:** "First response is super slow" or "Can't handle multiple calls."

## Scalability Considerations

| Concern | At 1 concurrent call | At 10 concurrent calls | At 100 concurrent calls |
|---------|---------------------|----------------------|------------------------|
| **GPU resources** | Single A100 80GB sufficient | Batching on 1-2 A100s with request queuing | Multiple GPU nodes with load balancer |
| **Whisper inference** | Real-time per call | Batch inference (up to 8 calls per A100) | Dedicated Whisper GPU pool |
| **Gemma inference** | Sequential per call | Queue-based scheduling, 4-bit quant | Multi-GPU with tensor parallelism (vLLM) |
| **CSM inference** | Real-time per call | Batching where possible | Dedicated TTS GPU pool |
| **WebSocket connections** | Single process handles easily | Load balance across 2-4 orchestrator instances | Horizontal scaling with session affinity |
| **State management** | In-memory dict | Redis for shared state | Redis cluster with sharding by call_id |
| **Audio buffering** | Per-call in-memory | Monitor memory usage, set limits | Streaming with minimal buffering |
| **Network bandwidth** | ~64 kbps per call | ~640 kbps (negligible) | ~6.4 Mbps (monitor egress costs) |

### Scaling Strategy

**Phase 1 (MVP, 1-5 calls):**
- Single A100 80GB GPU instance (RunPod/Lambda Labs)
- All models loaded once at startup
- Single Python process with async event loop
- In-memory state management
- Cost: ~$2-3/hour GPU + Twilio per-minute charges

**Phase 2 (10-50 calls):**
- 2-4 A100 GPUs with load balancing
- Separate Whisper, Gemma, CSM processes
- Redis for shared state across instances
- Request queuing with priority (new calls > ongoing)
- Cost: ~$8-12/hour GPU + Twilio charges

**Phase 3 (100+ calls):**
- Multi-GPU inference with vLLM for Gemma (tensor parallelism)
- Dedicated GPU pools per model type
- Kubernetes orchestration
- Auto-scaling based on queue depth
- CDN for static resources if web UI added
- Cost: Variable based on utilization

### Build Order Dependencies

Based on component coupling and testing requirements:

**Phase 1: Telephony + Audio Pipeline (Foundation)**
- Twilio integration (WebSocket server)
- Audio format conversion (mulaw ↔ PCM)
- Basic state machine (idle/listening/speaking)
- Test with pre-recorded audio playback

**Phase 2: Speech-to-Text (Input)**
- Whisper integration with streaming
- Audio buffering and chunking
- VAD for turn detection
- Test: Call in, speak, see transcript

**Phase 3: Text-to-Speech (Output)**
- CSM integration with streaming
- Audio encoding for Twilio
- Playback synchronization
- Test: Send text, hear AI speak

**Phase 4: LLM Integration (Intelligence)**
- Gemma 27B via vLLM
- Streaming token generation
- Sentence detection for TTS chunking
- Test: Full conversation loop works

**Phase 5: Interruption Handling (Polish)**
- VAD during playback
- TTS cancellation
- Buffer clearing
- Test: Interrupt AI mid-sentence

**Phase 6: Optimization (Production-Ready)**
- Latency measurement and tuning
- Concurrent call handling
- GPU memory optimization
- Error recovery and fallbacks

**Rationale for ordering:**
- Telephony first: Hard to test anything without call connectivity
- STT before TTS: Easier to debug with visual transcript output
- TTS before LLM: Can test with static responses, simpler than LLM streaming
- LLM integration: Combines STT + TTS, easier when both work independently
- Interruption last: Requires all other components working correctly
- Optimization last: Premature optimization wastes time, optimize after it works

## Sources

### Architecture Patterns
- [Voice AI Architecture Guide: Cascaded vs Speech-to-Speech in 2026](https://www.teamday.ai/blog/voice-ai-architecture-guide-2026)
- [The voice AI stack for building agents in 2026](https://www.assemblyai.com/blog/the-voice-ai-stack-for-building-agents)
- [Event-Driven Voice-to-Voice Architecture for Low-Latency AI Agents](https://www.askdonna.com/blog/how-to-built-an-event-driven-voice-to-voice-architecture-for-low-latency-ai-agents)

### Twilio Integration
- [Media Streams Overview](https://www.twilio.com/docs/voice/media-streams)
- [Media Streams - WebSocket Messages](https://www.twilio.com/docs/voice/media-streams/websocket-messages)
- [TwiML Voice: Stream](https://www.twilio.com/docs/voice/twiml/stream)

### Streaming Inference
- [vLLM Streaming Requests & Realtime API](https://blog.vllm.ai/2026/01/31/streaming-realtime.html)
- [Toward Low-Latency End-to-End Voice Agents](https://arxiv.org/html/2508.04721v1)

### VAD and Turn Detection
- [Voice Activity Detection: The Complete 2026 Guide](https://picovoice.ai/blog/complete-guide-voice-activity-detection-vad/)
- [Turn detection and interruptions](https://docs.livekit.io/agents/build/turns/)
- [Tackling Turn Detection in Voice AI](https://www.notch.cx/post/turn-detection-in-voice-ai)

### Latency Optimization
- [The 300ms rule: Why latency makes or breaks voice AI](https://www.assemblyai.com/blog/low-latency-voice-ai)
- [How to build the lowest latency voice agent](https://www.assemblyai.com/blog/how-to-build-lowest-latency-voice-agent-vapi)

### Whisper Optimization
- [Whisper Streaming (UFAL)](https://github.com/ufal/whisper_streaming)
- [Faster Whisper with CTranslate2](https://github.com/SYSTRAN/faster-whisper)
- [Building Real-Time Speech-to-Text with Faster Whisper](https://neurlcreators.substack.com/p/how-do-you-build-a-real-time-speech)

### CSM (Conversational Speech Model)
- [Sesame CSM GitHub](https://github.com/SesameAILabs/csm)
- [Deploying Sesame CSM](https://www.cerebrium.ai/articles/deploying-sesame-csm-the-most-realistic-voice-model)

### Framework Comparisons
- [RealTime AI Agents frameworks comparison: LiveKit, Pipecat and TEN](https://medium.com/@ggarciabernardo/realtime-ai-agents-frameworks-bb466ccb2a09)
- [Difference Between LiveKit vs PipeCat](https://www.f22labs.com/blogs/difference-between-livekit-vs-pipecat-voice-ai-platforms/)

### GPU Optimization
- [Faster Whisper transcription with CTranslate2](https://github.com/SYSTRAN/faster-whisper)
- [The $0 Scalability Fix: How Whisper Microservice Saved Us from GPU OOM](https://medium.com/@patelhet04/the-0-scalability-fix-how-whisper-microservice-saved-us-from-gpu-oom-65dfd41a2180)
