# Pitfalls Research

**Domain:** Real-time AI voice calling systems
**Researched:** 2026-02-22
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Context Drift from Interruption Misalignment

**What goes wrong:**
When users interrupt the AI mid-response, the LLM has already generated and queued words the user never heard. The system's internal context assumes the full message was delivered, but the user only heard part of it. This difference compounds over multiple turns, causing the system's understanding to drift from the user's actual experience. AI models' success rates drop from 90% on single prompts to approximately 65% in multi-turn dialogues.

**Why it happens:**
Modern LLMs generate output faster than real-time—they produce complete responses before the TTS finishes speaking. Standard implementations don't track which tokens were actually played to the user versus which were only generated internally. Without proper interruption handling, the conversation context becomes corrupted.

**How to avoid:**
1. Implement cancellable pipelines across all components (STT, LLM, TTS)
2. Use the conversation.item.truncate event pattern (like OpenAI's Realtime API) to signal the model exactly where it was interrupted
3. Implement token-by-token TTS that can stop immediately when interrupted
4. Track "generated tokens" separately from "spoken tokens" in conversation state
5. On interruption, truncate the conversation history to only include what the user actually heard

**Warning signs:**
- User says "I already told you that" or repeats themselves
- AI responds to information it never actually spoke aloud
- Conversation coherence degrades after 3-4 interruptions
- Testing shows >10% context drift in multi-turn scenarios

**Phase to address:**
Phase 1 (Core pipeline) and Phase 3 (Interruption handling) — critical architecture decision that can't be retrofitted easily.

---

### Pitfall 2: Latency Budget Exhausted by Audio Format Conversion

**What goes wrong:**
Provider APIs accept various audio formats but silently convert them to the format models expect. Each conversion adds 20-50ms latency and can degrade quality. With Twilio's mu-law 8kHz → Whisper's 16kHz PCM → LLM processing → CSM's expected format → Twilio's mu-law again, you've spent 100-200ms of your 500ms budget on resampling alone. If resampling is done naively (without proper DSP), voice sounds "underwater."

**Why it happens:**
Developers focus on getting data flowing between services without measuring the cost of each conversion. Twilio uses 8-bit PCM mono uLaw at 8kHz (telephony standard), but ML models expect 16kHz+ PCM with specific bit depths. Each boundary introduces silent format negotiation.

**How to avoid:**
1. Map the exact audio format at every pipeline stage before writing code
2. Use proper DSP libraries (sox, ffmpeg, or specialized audio libs) for resampling, not naive upsample/downsample
3. Minimize conversions—ideally convert once on input, process in native format, convert once on output
4. Measure latency contribution of each audio processing step in isolation
5. Consider using Twilio's WebRTC mode (Opus codec) instead of PSTN (mu-law) for higher quality input

**Warning signs:**
- Total latency exceeds budget but model inference times look reasonable
- Audio quality degrades (tinny, underwater, artifacts)
- CPU usage spikes during audio handling
- Profiling shows 15%+ of time in resampling functions

**Phase to address:**
Phase 1 (Core pipeline) — format decisions lock in early. Changing audio formats after integration requires reworking the entire pipeline.

---

### Pitfall 3: Endpointing Threshold Creates Response Delay Paradox

**What goes wrong:**
Voice Activity Detection (VAD) requires a silence threshold to detect when the user finished speaking. Set it too low (100ms) and you get false positives from natural pauses, causing the AI to interrupt the user. Set it too high (800ms+) and users experience awkward delays before the AI responds. The 300-500ms "natural conversation pause" window is extremely narrow, and production environments with background noise make this worse. VAD accuracy drops from 0.93 F1 in clean conditions to 0.71 with street noise.

**Why it happens:**
There's an inherent tradeoff between accuracy and latency. Smaller 10ms VAD frames detect speech onset faster but misclassify more in noisy environments. Larger 30ms windows improve accuracy but add detection delay. Developers test in quiet offices, then deploy to real-world phone calls with background noise, crosstalk, and poor audio quality.

**How to avoid:**
1. Use production-grade VAD models (Silero VAD, Picovoice Cobra) instead of simple energy thresholds
2. Test VAD tuning with real phone call audio, not laptop microphone samples
3. Implement adaptive thresholds that adjust based on background noise levels
4. Consider conversational context—longer threshold during AI's turn, shorter when user is expected to speak
5. Plan for 200-250ms detection latency in your overall budget
6. Test across diverse conditions: street noise, cafes, car environments, poor connections

**Warning signs:**
- Users complain the AI "talks over them"
- Long awkward pauses before AI responds
- VAD performance varies wildly between test calls
- False positives from background noise (TV, traffic, other speakers)
- Works perfectly in dev environment, fails in production

**Phase to address:**
Phase 2 (STT streaming) — VAD tuning requires real audio data to calibrate properly. Leave time for iteration based on real call recordings.

---

### Pitfall 4: GPU Memory Fragmentation from Concurrent Model Loading

**What goes wrong:**
Running Whisper, Gemma 3 27B, and CSM concurrently on the same GPU causes memory fragmentation. Each model loads separately and allocates static memory for weights plus dynamic memory for KV cache (LLM) or processing buffers (STT/TTS). KV cache dominates production memory, often exceeding parameter memory by 2-3×. Without proper allocation strategy, you get out-of-memory errors despite having enough total VRAM, or you over-provision expensive GPUs (paying for A100 80GB when A100 40GB would work with better allocation).

**Why it happens:**
Developers calculate memory requirements per model in isolation (Gemma 27B FP16 ≈ 54GB, Whisper ≈ 5GB, CSM ≈ 4GB), then assume they add linearly. They don't account for KV cache growth during long conversations, batch processing overhead, or fragmentation from separate allocations. vLLM and similar frameworks dynamically allocate KV cache but require configuration.

**How to avoid:**
1. Use vLLM's PagedAttention to eliminate 60-80% memory waste from KV cache fragmentation
2. Configure explicit memory limits per model with monitoring
3. Load models sequentially and measure actual VRAM usage, not just parameter counts
4. For Gemma 27B: calculate KV cache as (batch_size × context_length × layers × hidden_size × 2 × precision)
5. Use INT8 quantization for Whisper (drops from 11.3GB to 3.1GB with minimal accuracy loss)
6. Consider multi-GPU setups with model sharding if single GPU memory is insufficient
7. Monitor GPU memory in production—alert when >85% utilized

**Warning signs:**
- OOM errors despite VRAM calculations showing sufficient memory
- Successful single-call tests but failures under concurrent load
- Memory usage grows over time (KV cache leak)
- GPU utilization <70% despite full memory usage (fragmentation)
- Different behavior between development (single call) and production (concurrent)

**Phase to address:**
Phase 1 (Core pipeline) and Phase 5 (Cloud GPU deployment) — memory architecture decisions made early. GPU selection depends on accurate memory requirements.

---

### Pitfall 5: Streaming Text Chunks Break Prosody and Natural Speech

**What goes wrong:**
To minimize latency, developers chunk LLM output (send first sentence to TTS while generating the rest) and immediately stream audio back. But TTS models need sentence context to generate proper prosody, intonation, and rhythm. Chunking by punctuation produces unnatural speech with robotic pauses, weird emphasis, and monotone delivery. The AI sounds artificial despite using a high-quality TTS model. Research shows that five open-source TTS systems fail to produce acoustic signals that accurately convey prosodic boundaries when given only punctuation cues.

**Why it happens:**
Latency pressure drives aggressive chunking strategies. Developers optimize for "time to first audio" without measuring subjective quality. They send 20-40ms frames to start playback quickly, but this disrupts the TTS model's ability to plan prosody across longer utterances. Cross-utterance context is lost when each sentence is synthesized independently.

**How to avoid:**
1. Chunk at natural phrase boundaries, not just punctuation—use linguistic parsing
2. Send 100-200 tokens of look-ahead context to TTS even when streaming
3. Use TTS models designed for streaming with incremental synthesis (newer Deepgram Aura, CartesiaAI)
4. Balance latency vs. naturalness: optimize for P90 latency, not minimum possible
5. Test subjective quality with real users—"does this sound human?" not just "how fast?"
6. Consider sentence-level chunking for critical first response, then switch to smarter chunking
7. For CSM specifically: provide full semantic context as model cannot compensate for missing prosodic information

**Warning signs:**
- TTS output sounds robotic despite using quality model
- Unnatural pauses between chunks
- Flat intonation that doesn't match sentence meaning
- Users describe AI as "reading from a script"
- Emphasis on wrong words in sentences
- First sentence sounds great, but subsequent sentences sound mechanical

**Phase to address:**
Phase 4 (TTS streaming) — prosody optimization requires iteration after basic streaming works. Plan for quality refinement time.

---

### Pitfall 6: Network Latency Multipliers from Regional Distribution

**What goes wrong:**
To save costs, developers deploy STT in Virginia (cheap), LLM in London (good GPU availability), and TTS in Tokyo (quota available). Each regional boundary adds 100-150ms of network latency plus overhead for jitter buffers and potential packet loss. Three regional hops = 300-450ms consumed entirely by network transmission, leaving almost no budget for actual AI processing. Even if advertised latency is 600ms, production latency becomes 800-1,000ms with real traffic.

**Why it happens:**
Cloud providers charge different rates by region and have different GPU availability. Developers optimize for cost and availability without measuring round-trip time. They test with low-latency lab networks, not real phone connections over PSTN or mobile networks. Each network boundary introduces encode, decode, and jitter buffer overhead that's invisible in localhost testing.

**How to avoid:**
1. Co-locate all pipeline components in same region, ideally same availability zone
2. Prioritize latency over cost—latency determines product viability
3. Measure actual round-trip latency from real phone networks to your services
4. Use Twilio Edge Locations close to your AI infrastructure
5. Test during peak hours on mobile networks and PSTN, not just WiFi/office networks
6. Budget for 50-100ms network overhead even with co-location
7. Monitor P95 and P99 latency, not just averages—tail latency destroys conversational feel

**Warning signs:**
- High variance in latency (P50: 400ms, P99: 1,200ms)
- Works great on WiFi, terrible on mobile
- Latency correlates with user geography
- Network monitoring shows high inter-region traffic
- Profiling shows >30% of time in network calls

**Phase to address:**
Phase 5 (Cloud deployment) — architecture decision affecting infrastructure costs and performance. Regional decisions are hard to change after deployment.

---

### Pitfall 7: Whisper Vanilla Implementation Yields 1-5s Latency

**What goes wrong:**
Using OpenAI's vanilla Whisper implementation directly yields 1-5 second latency on typical audio segments. This blows the entire latency budget before any LLM or TTS processing begins. The model processes audio in 30-second chunks by default, requires significant VRAM (11.3GB for base model), and doesn't support true streaming—it needs complete utterances before starting transcription.

**Why it happens:**
Developers see "Whisper" in requirements, install `pip install openai-whisper`, and integrate directly without researching optimized implementations. The vanilla model was designed for batch transcription accuracy, not real-time streaming. Latency bottlenecks include audio buffering (250ms chunks), model processing (100-300ms), and endpointing detection (200-500ms).

**How to avoid:**
1. Use faster-whisper (CTranslate2-based) for 4× speedup with same accuracy
2. Consider distil-whisper for 6× speedup with <1% WER degradation
3. Use INT8 quantization to reduce memory from 11.3GB → 3.1GB
4. For true streaming, use whisper_streaming or similar projects designed for real-time
5. Consider commercial alternatives with <300ms P50 latency (AssemblyAI Universal-Streaming, Together AI)
6. Budget 100-200ms for optimized Whisper variants, not 1-5s for vanilla
7. Test with continuous speech, not just short isolated phrases

**Warning signs:**
- STT latency dominates total pipeline time
- VRAM usage is unexpectedly high for STT
- Transcription starts only after user finishes entire sentence
- Works for short phrases, fails for longer utterances
- CPU/GPU utilization spikes during STT processing

**Phase to address:**
Phase 2 (STT streaming) — implementation choice made during initial integration. Swapping STT engines later requires significant rework.

---

### Pitfall 8: Jitter Buffer Misconfiguration Creates Sluggish Responses

**What goes wrong:**
Jitter buffers smooth out network packet timing variations, but oversized buffers make the AI feel sluggish. Developers use default jitter buffer settings (often 50-100ms or adaptive with high ceiling) without tuning for their latency target. Production voice AI systems need tiny buffers (3-4 packets, ~15-20ms) to feel responsive, but this makes them more sensitive to network conditions.

**Why it happens:**
Jitter buffers are typically tuned for audio quality (minimize dropouts) rather than latency. Telecom defaults prioritize zero packet loss over responsiveness. Adaptive jitter buffers grow to accommodate worst-case jitter, then stay large. Developers test on stable networks where jitter is low, so buffer size doesn't matter much.

**How to avoid:**
1. Configure minimal static jitter buffer (3-4 packets, 15-20ms) for voice AI use case
2. If using adaptive jitter buffer, set aggressive shrink parameters and low maximum
3. Use WebRTC instead of PSTN when possible—better jitter handling and lower latency codecs
4. Monitor jitter buffer depth in production—alert if consistently >50ms
5. Balance against packet loss—if >2% loss, consider slightly larger buffer
6. Test on varied network conditions: WiFi, LTE, poor cellular coverage
7. Implement audio repair for dropped packets rather than oversized buffers

**Warning signs:**
- Consistent "delay feeling" even when processing times are good
- 100-150ms orchestration latency that doesn't correlate with distance
- Profiling shows time spent in network/audio buffering
- Latency improves dramatically on local network vs. real calls
- Users describe AI as "pausing before responding"

**Phase to address:**
Phase 1 (Core pipeline) — jitter buffer configuration is part of initial Twilio integration. Review and tune during initial testing.

---

### Pitfall 9: WebSocket Backpressure Causes Audio Stalls and Buffer Overflow

**What goes wrong:**
When the TTS generates audio faster than the network can transmit it (or faster than Twilio can consume it), WebSocket buffers fill up. Without backpressure handling, either the buffer overflows (dropped audio), the application crashes (OOM), or the TTS keeps generating into the void while the user experiences stalls. Audio arrives in bursts instead of smooth streams.

**Why it happens:**
WebSocket doesn't automatically slow down producers when consumers can't keep up. TTS models generate at max speed (often >10× real-time), and developers assume network sockets will just handle it. Testing on localhost shows no issues because latency is microseconds. Production networks have variable bandwidth, Twilio's audio ingestion has rate limits, and buffer management requires explicit handling.

**How to avoid:**
1. Implement flow control: monitor WebSocket buffer depth and pause TTS generation when buffers are >70% full
2. Use RTWebSocket or similar for per-flow management with acknowledgments
3. Chunk audio into time-appropriate segments (20-40ms frames) matching real-time playback rate
4. Implement bounded buffering with explicit producer slowdown strategy
5. Use asyncio with proper backpressure handling (await on send operations)
6. Monitor WebSocket send buffer size and alert on consistent fullness
7. Test with bandwidth throttling to simulate mobile networks

**Warning signs:**
- Audio plays in bursts with silence between
- WebSocket buffer memory usage grows over time
- Successful test calls but production calls fail after 30-60 seconds
- Network monitoring shows bursty traffic pattern instead of smooth stream
- Dropped frames or audio artifacts under load
- Memory leaks in WebSocket handling code

**Phase to address:**
Phase 4 (TTS streaming) — backpressure becomes visible when integrating TTS streaming. Requires proper async I/O architecture.

---

### Pitfall 10: LLM Token Generation Latency Underestimated for Conversation Quality

**What goes wrong:**
Developers calculate that Gemma 3 27B generates 34 tokens/second, so a 20-token response should take ~600ms. They assume this is acceptable for the 500ms budget since "the first few tokens start streaming immediately." But time-to-first-token (TTFT) is 800ms, and at 34 tok/s, the AI sounds like it's "thinking slowly" compared to natural conversation. Users perceive this as hesitation, not human-like response.

**Why it happens:**
Latency benchmarks focus on throughput (tokens/second) rather than TTFT or perceived responsiveness. Gemma 3 27B is "notably slow" compared to commercial APIs (GPT-4, Claude). The model size creates inherent latency that conflicts with conversational AI requirements. Developers optimize for cost (open-weight model) without validating conversational quality.

**How to avoid:**
1. Prioritize TTFT and token generation speed over model size for conversational use
2. Consider smaller models (Gemma 3 9B or commercial APIs) if latency testing shows degraded experience
3. Use streaming with immediate TTS synthesis of partial responses (first 5-10 tokens while rest generates)
4. Optimize inference with TensorRT-LLM instead of vLLM if targeting minimum latency (TensorRT: ~100ms TTFT, 10K+ tok/s)
5. Test subjective conversation quality, not just objective latency numbers
6. Use response length limits to keep total generation time predictable
7. Consider that perceived latency = TTFT + (response_length / tok_per_sec)

**Warning signs:**
- Users describe AI as "slow to respond" despite meeting technical latency budget
- Noticeable pause before AI starts speaking
- TTFT consistently >500ms in production
- Conversation feels unnatural even when working correctly
- Model selection optimized for cost, not conversational feel

**Phase to address:**
Phase 3 (LLM streaming) — model selection and inference optimization. Changing LLM later requires re-benchmarking entire pipeline.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip proper VAD, use fixed silence threshold | Fast integration, simple | Poor production quality, user complaints, can't handle varied environments | Never—VAD quality determines conversation feel |
| Use vanilla Whisper instead of optimized variant | Easy pip install, familiar | 3-5× latency overhead, can't hit sub-500ms target | Never for production real-time use |
| Single GPU without load balancing | Lower cost, simpler setup | Can't scale beyond ~10 concurrent calls, no redundancy | Acceptable for MVP testing, not production |
| Disable interruption handling initially | Fewer edge cases to handle | Users can't naturally interrupt AI, feels robotic | Acceptable for Phase 1-2 testing only |
| Default jitter buffer sizes | Works out of box | Adds 50-100ms hidden latency | Never—tune buffers for your use case |
| Co-locate with Twilio edge, not co-locate components | Faster to deploy separately | Regional latency kills budget | Acceptable only if all components in same region |
| Skip audio format optimization | Minimal code, "it works" | Silent 100-200ms latency tax from conversions | Never—formats should be explicit and optimized |
| Use synchronous API calls instead of streaming | Simpler code flow | Adds full request latency to each stage | Never for STT/LLM/TTS—streaming is mandatory |
| Test on WiFi/office networks only | Convenient, consistent results | Doesn't reflect real phone network conditions | Never—test on PSTN and mobile networks |
| Skip prosody tuning for TTS chunks | Faster latency, simpler chunking | Robotic speech quality, users notice immediately | Never—natural speech is core value prop |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Twilio Media Streams | Assuming linear audio flow without measuring round-trip | Measure actual RTT from Twilio → your service → back, including jitter buffers. Test on real PSTN calls, not just WebRTC. |
| vLLM Inference Server | Configuring max_model_len without accounting for KV cache memory growth | Calculate: (batch_size × max_context × layers × hidden_dim × 2 × bytes_per_param). Monitor VRAM usage in production. Use PagedAttention. |
| Faster-Whisper Streaming | Using default chunk sizes (30s) for real-time | Set chunk_size=100-125ms. Enable streaming mode. Test with continuous speech, not isolated phrases. |
| CSM TTS Deployment | Treating CSM as drop-in replacement for traditional TTS | CSM is audio generation model, not multimodal LLM. Requires separate text generation. Needs full semantic context for prosody. |
| RunPod GPU Instances | Assuming spot instances are reliable for production | Spot pods can be interrupted mid-call with little warning. Use on-demand for production. Plan for H100 scarcity during peak hours. Monitor cold start latency (>30s). |
| WebSocket Audio Streaming | Sending audio as fast as generated without flow control | Implement backpressure monitoring. Chunk at 20-40ms intervals. Use bounded buffers with explicit slowdown. |
| Audio Format Conversion | Letting libraries handle conversion automatically | Explicitly control format at every boundary. Use proper DSP libs (sox, ffmpeg). Measure latency of each conversion. Minimize conversion count. |
| VAD Configuration | Using default thresholds from documentation | Tune with real phone call audio from target environment. Test with background noise, varying SNR. Expect 0.93 → 0.71 F1 drop in noisy conditions. |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Sequential pipeline stages without streaming | First call works fine, latency is acceptable | Implement streaming at every stage (STT, LLM, TTS). Use async/await properly. Pipeline stages should run concurrently. | Immediately—sequential adds all latencies, easily >2s total |
| Single GPU for all models | Development testing succeeds | Load test with concurrent calls. Plan for 2-3 calls per A100 80GB depending on model config. Consider multi-GPU or model sharding. | ~5-10 concurrent calls (depends on VRAM) |
| In-memory conversation state without persistence | Calls work great | Use Redis or similar for conversation state. Plan for pod restarts. Implement state serialization. | First pod restart—all active calls lose context |
| Underprovisioned network bandwidth | Test calls are perfect | Monitor network utilization. Plan for 64-128 kbps per concurrent call (bidirectional). Provision headroom for burst traffic. | 50-100 concurrent calls on 10Mbps connection |
| Synchronous error handling | Errors stop one call | Implement circuit breakers. Isolate call failures. Use async error handling with retry budgets. One failure shouldn't cascade. | First production error cascade—all calls fail |
| Static KV cache allocation | Single call uses reasonable memory | Use vLLM's dynamic KV cache allocation. Monitor cache growth. Set max_context appropriately. Clear cache between calls. | 3-5 concurrent long conversations |
| No rate limiting on inference endpoints | Each call gets full GPU resources | Implement request queueing with max concurrency. Return 503 when overloaded. Use vLLM's built-in batching. | When concurrent requests exceed GPU capacity |
| Audio buffer bloat over time | First minute of call is responsive | Implement buffer size monitoring with alerts. Use bounded buffers. Clear completed audio chunks. Detect memory leaks. | After 2-5 minutes of continuous call |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Recording phone calls without consent notifications | Legal liability, privacy violations in many jurisdictions | Implement call recording consent flow. Store consent logs. Respect regional regulations (GDPR, CCPA, etc.). Disable recording by default. |
| Exposing LLM prompts/system messages in API responses | Competitors copy your prompts, users manipulate system behavior | Keep system prompts server-side only. Never return full conversation context to client. Log prompts securely. |
| No authentication on WebSocket audio streams | Anyone can stream audio to your inference pipeline, run up GPU costs | Implement token-based WebSocket authentication. Validate tokens on connection. Rate limit per token. Expire tokens after reasonable duration. |
| Storing audio/transcripts without encryption | Privacy violation, compliance risk | Encrypt audio at rest (AES-256). Encrypt transcripts in database. Use short retention periods. Implement right-to-deletion. |
| No rate limiting on phone number endpoints | Malicious actors run up Twilio costs, DDoS inference | Rate limit calls per phone number per time window. Implement CAPTCHA for outbound number input. Monitor cost spikes. Set budget alerts. |
| Allowing unlimited conversation length | Memory exhaustion, runaway costs, context window overflow | Implement max conversation length (tokens or duration). Gracefully handle context window limits. Summarize old context or end call. |
| No validation on TTS input text | Prompt injection via crafted responses, SSRF via embedded commands | Sanitize LLM output before TTS. Strip SSML tags unless explicitly supported. Validate text length. Filter control characters. |
| Exposing real-time metrics endpoints publicly | Information disclosure about system capacity, active users | Require authentication for metrics. Use internal network for monitoring. Aggregate metrics before exposing externally. |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| AI doesn't acknowledge interruptions | User feels ignored, has to repeat themselves, conversation feels broken | Detect interruption, stop speaking immediately, acknowledge with "yes?" or "go ahead" before processing new input |
| No indication when AI is "thinking" | Dead air feels like call dropped, users say "hello?" repeatedly | Generate thinking sounds ("uh", "hmm") during TTFT latency >500ms, or say "let me think about that..." |
| Robotic timing between sentences | AI sounds like reading a script, lacks conversational flow | Add micro-pauses based on semantic content. Vary response timing slightly. Use prosody models that understand context. |
| AI talks over user during natural pauses | Frustrating interruptions destroy conversation flow | Tune VAD conservatively—prefer slight delay over false positives. Consider turn-taking models that understand conversational context. |
| No recovery from STT errors | Misheard words lead to nonsensical responses, user confused | Implement confidence scoring. Ask for clarification on low-confidence transcriptions. "Did you say [X]?" |
| Identical response patterns | AI feels scripted, not conversational | Vary response phrasing. Use temperature >0.7 for conversational variety. Avoid template-heavy responses. |
| No call termination signal | Calls end abruptly without closure, feels rude | Implement goodbye detection. AI should acknowledge end of call: "Thanks for calling, goodbye!" before hangup. |
| Audio quality issues not surfaced | User doesn't know their audio is garbled, conversation fails | Detect low audio quality (high noise, low SNR). AI says "I'm having trouble hearing you, could you speak up?" |
| Long responses without breathing room | User can't interject, feels like monologue | Chunk responses with natural pause points. Enable interruption throughout response, not just at end. |
| No ambient presence | Silence during processing feels like disconnection | Use subtle background tone or periodic sound to indicate call is active during processing gaps. |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **STT Streaming:** Often missing VAD tuning for production environments — verify F1 score >0.85 on real phone recordings with background noise, not just clean lab audio
- [ ] **LLM Streaming:** Often missing TTFT optimization — verify P95 TTFT <600ms under production load (concurrent calls), not just single-request benchmarks
- [ ] **TTS Streaming:** Often missing prosody validation — verify subjective naturalness with blind A/B testing against human speech, not just WER/MOS metrics
- [ ] **Interruption Handling:** Often missing context truncation — verify conversation state only includes audio user actually heard, test with 5+ interruptions per call
- [ ] **Audio Pipeline:** Often missing format conversion measurement — verify total conversion latency <50ms by profiling each boundary separately
- [ ] **GPU Deployment:** Often missing concurrent load testing — verify memory doesn't leak over 10+ minute calls, test with 3× expected concurrent load
- [ ] **Error Recovery:** Often missing graceful degradation — verify system recovers from STT timeout, LLM timeout, TTS timeout without dropping call
- [ ] **Network Resilience:** Often missing packet loss handling — verify quality with 2-5% packet loss, test on throttled mobile networks
- [ ] **Latency Budget:** Often missing P99 measurement — verify P99 latency <800ms, not just P50 or averages (tail latency destroys conversational feel)
- [ ] **Production Validation:** Often missing real PSTN testing — verify quality on actual phone calls from mobile networks, not just VoIP/WebRTC clients

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Context drift from interruption | MEDIUM | 1. Log conversation history on drift detection. 2. Implement conversation reset: "Let me confirm what we've discussed...". 3. Ask user to clarify: "I want to make sure I understood correctly..." |
| Audio format latency overhead | HIGH | 1. Profile entire pipeline to locate conversion bottlenecks. 2. Refactor to minimize conversions (consolidate at boundaries). 3. Replace naive resamplers with proper DSP libs. May require pipeline rework. |
| VAD false positives/negatives | LOW | 1. Collect production audio samples with ground truth. 2. Retune thresholds offline. 3. Deploy updated config. 4. Monitor F1 score improvement. Iterate until >0.85. |
| GPU OOM from memory fragmentation | MEDIUM | 1. Upgrade to larger GPU short-term. 2. Implement proper memory management (vLLM PagedAttention). 3. Add memory monitoring and alerts. 4. May require model reloading strategy. |
| TTS prosody sounds robotic | MEDIUM | 1. A/B test chunk sizes to find naturalness threshold. 2. Implement look-ahead context. 3. Consider commercial TTS with better streaming. 4. User testing validates improvement. |
| Regional latency killing budget | HIGH | 1. Migrate all services to single region (downtime required). 2. Test latency improvement. 3. Update routing/DNS. 4. Significant infrastructure change with deployment risk. |
| Whisper vanilla latency | LOW | 1. Swap to faster-whisper (code changes minimal). 2. Test accuracy maintained. 3. Deploy with rollback plan. 4. Monitor latency improvement (should see 3-4× speedup). |
| Jitter buffer sluggishness | LOW | 1. Reduce buffer size in config. 2. Test on varied networks. 3. Monitor packet loss increase. 4. Find optimal balance. Quick iteration cycle. |
| WebSocket backpressure | MEDIUM | 1. Add buffer monitoring. 2. Implement flow control (pause TTS). 3. Test with bandwidth throttling. 4. Requires async architecture refactor if not present. |
| LLM generation too slow | HIGH | 1. Swap to faster model (Gemma 9B or commercial API). 2. Or implement TensorRT-LLM optimization. 3. Re-benchmark entire pipeline. 4. May sacrifice quality for speed. |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Context drift from interruption | Phase 1 (Core pipeline) & Phase 3 (Interruption handling) | Test with 10 calls containing 5+ interruptions each. Verify context accuracy >95% after interruptions. |
| Audio format conversion latency | Phase 1 (Core pipeline) | Profile audio conversions. Total conversion latency <50ms. Document format at each boundary. |
| VAD threshold paradox | Phase 2 (STT streaming) | VAD F1 score >0.85 on real phone recordings with background noise. Test across diverse environments. |
| GPU memory fragmentation | Phase 1 (Core pipeline) & Phase 5 (Cloud GPU deployment) | Run 3× expected concurrent load for 30 minutes. No OOM errors. Memory usage <85% sustained. |
| TTS prosody chunking | Phase 4 (TTS streaming) | Blind A/B test: users rate naturalness >4/5. Compare chunked vs. full-sentence synthesis. |
| Regional network latency | Phase 5 (Cloud GPU deployment) | Measure RTT from Twilio edge → services → back. Total network latency <100ms. All components same region. |
| Whisper vanilla latency | Phase 2 (STT streaming) | STT latency P95 <200ms. Use faster-whisper or distil-whisper, not vanilla. Benchmark with continuous speech. |
| Jitter buffer misconfiguration | Phase 1 (Core pipeline) | Configure buffer to 3-4 packets (15-20ms). Test packet loss <2%. Users describe responses as "immediate." |
| WebSocket backpressure | Phase 4 (TTS streaming) | Monitor WebSocket buffer depth. <70% full during peak generation. No audio stalls in 30-minute test calls. |
| LLM generation latency | Phase 3 (LLM streaming) | TTFT P95 <600ms. Token generation >50 tok/s. Test subjective conversation quality with users. |
| Sequential pipeline (not streaming) | Phase 1 (Core pipeline) | All stages stream concurrently. Total latency = max(stage_latencies) + network, not sum(stage_latencies). |
| Single GPU scaling | Phase 5 (Cloud GPU deployment) | Load test with 3× expected concurrent calls. Plan GPU scaling strategy. Monitor GPU utilization. |
| No call authentication | Phase 6 (Error handling & production hardening) | All WebSocket connections require valid tokens. Rate limiting per token/number. Test unauthorized access blocked. |
| No interruption acknowledgment | Phase 3 (Interruption handling) | AI stops speaking within 200ms of user interruption. Acknowledges with "yes?" or similar. User testing validates feel. |

## Sources

- [Core Latency in AI Voice Agents (Twilio)](https://www.twilio.com/en-us/blog/developers/best-practices/guide-core-latency-ai-voice-agents)
- [The 300ms rule: Why latency makes or breaks voice AI applications (AssemblyAI)](https://www.assemblyai.com/blog/low-latency-voice-ai)
- [Why real-time voice AI is harder than it sounds (SiliconANGLE)](https://siliconangle.com/2026/02/20/real-time-voice-ai-harder-sounds/)
- [Interruption Handling in Conversational AI (Zoice)](https://zoice.ai/blog/interruption-handling-in-conversational-ai/)
- [Why Interruptions Break Voice AI Systems (Medium)](https://medium.com/@raghavgarg.work/why-interruptions-break-voice-ai-systems-5bde68ed60f5)
- [How context drift impacts conversational coherence in AI systems (Maxim)](https://www.getmaxim.ai/articles/how-context-drift-impacts-conversational-coherence-in-ai-systems/)
- [The Hidden Risk of Drift in Prolonged AI Conversations (Psychology Today)](https://www.psychologytoday.com/us/blog/urban-survival/202602/the-hidden-risk-of-drift-in-prolonged-ai-conversations)
- [Voice Activity Detection: The Complete 2026 Guide (Picovoice)](https://picovoice.ai/blog/complete-guide-voice-activity-detection-vad/)
- [Best open source speech-to-text (STT) model in 2026 (Northflank)](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks)
- [Whisper Variants Comparison (Towards AI)](https://towardsai.net/p/machine-learning/whisper-variants-comparison-what-are-their-features-and-how-to-implement-them)
- [Choosing between Whisper variants (Modal)](https://modal.com/blog/choosing-whisper-variants)
- [Text Chunking for TTS REST Optimization (Deepgram)](https://developers.deepgram.com/docs/text-chunking-for-tts-optimization)
- [Generating Consistent Prosodic Patterns from Open-Source TTS Systems (ISCA)](https://www.isca-archive.org/interspeech_2025/shim25_interspeech.html)
- [vLLM vs TensorRT-LLM: Key differences and performance (Northflank)](https://northflank.com/blog/vllm-vs-tensorrt-llm-and-how-to-run-them)
- [Mind the Memory Gap: Unveiling GPU Bottlenecks in Large-Batch LLM Inference (arXiv)](https://arxiv.org/html/2503.08311v2)
- [What is GPU Memory and Why it Matters for LLM Inference (BentoML)](https://www.bentoml.com/blog/what-is-gpu-memory-and-why-it-matters-for-llm-inference)
- [Backpressure in WebSocket Streams (Skyline Codes)](https://skylinecodes.substack.com/p/backpressure-in-websocket-streams)
- [Understanding Backpressure in Real-Time Streaming with WebSockets (Medium)](https://apuravchauhan.medium.com/understanding-backpressure-in-real-time-streaming-with-websockets-20f504c2d248)
- [Node.js Voice AI: Production Implementation Guide 2026 (Deepgram)](https://deepgram.com/learn/nodejs-voice-ai-production-guide)
- [Cloud GPU Mistakes to Avoid (RunPod)](https://www.runpod.io/articles/guides/cloud-gpu-mistakes-to-avoid)
- [Gemma 3 27B Performance Analysis (Artificial Analysis)](https://artificialanalysis.ai/models/gemma-3-27b)
- [Crossing the uncanny valley of conversational voice (Sesame)](https://www.sesame.com/research/crossing_the_uncanny_valley_of_voice)
- [Evaluating AI agents: Real-world lessons from Amazon (AWS)](https://aws.amazon.com/blogs/machine-learning/evaluating-ai-agents-real-world-lessons-from-building-agentic-systems-at-amazon/)
- [OpenAI Realtime API Twilio Integration Guide (Skywork AI)](https://skywork.ai/blog/agent/openai-realtime-api-twilio-integration-complete-guide/)
- [Twilio Audio Codec Support](https://help.twilio.com/articles/13527980995355-Twilio-Voice-SDKs-Supported-Audio-Codecs-)

---
*Pitfalls research for: Real-time AI voice calling systems (Twilio + Whisper + Gemma 3 27B + CSM)*
*Researched: 2026-02-22*
