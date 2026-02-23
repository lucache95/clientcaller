# E2E TTS Integration Testing Checklist

## Prerequisites
- [ ] Server running: `uvicorn src.main:app --reload`
- [ ] ngrok tunnel active: `ngrok http 8000`
- [ ] Twilio phone number configured with ngrok URL
- [ ] LLM endpoint accessible (vLLM/RunPod or local)
- [ ] Internet access for edge-tts (Microsoft TTS service)

## Test Scenarios

### 1. Basic Conversation Loop
- [ ] Call the Twilio number
- [ ] Say "Hello, how are you?"
- [ ] **Verify:** Hear AI speak a natural response back
- [ ] **Verify:** Response is audible and clear (not garbled)
- [ ] **Verify:** Response content is contextually appropriate

### 2. Multi-Turn Conversation
- [ ] After first response, say "Tell me more about that"
- [ ] **Verify:** AI responds with context from previous turn
- [ ] Continue for 3+ exchanges
- [ ] **Verify:** Conversation remains coherent throughout

### 3. Latency Measurement
- [ ] Time from end of user speech to start of AI audio
- [ ] **Target:** < 500ms total (STT + LLM + TTS + network)
- [ ] **Breakdown:** Note individual component times from logs
  - STT finalization: should be < 200ms
  - LLM first token: should be < 200ms
  - TTS first audio: should be < 300ms

### 4. Audio Quality
- [ ] **Verify:** AI voice sounds natural (not robotic)
- [ ] **Verify:** Words are clearly articulated
- [ ] **Verify:** No audio artifacts (clicks, pops, gaps)
- [ ] **Verify:** Volume level is comfortable

### 5. Long Response Handling
- [ ] Ask a question that generates a long response (e.g., "Explain quantum computing")
- [ ] **Verify:** Full response plays without cutoff
- [ ] **Verify:** No buffer overflow warnings in logs
- [ ] **Verify:** Audio streams continuously (no long pauses mid-sentence)

### 6. Error Recovery
- [ ] **Verify:** If LLM fails, call doesn't hang
- [ ] **Verify:** If TTS fails, error is logged and call continues
- [ ] **Verify:** Empty/whitespace user speech doesn't trigger TTS

## Log Verification
Check server logs for:
- [ ] `User said: <transcript>` — STT working
- [ ] `AI response: <text>` — LLM generating
- [ ] No TTS errors in logs
- [ ] `Turn N: User='...' AI='...'` — Full loop completing
