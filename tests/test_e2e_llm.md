# Phase 3: Language Model E2E Testing

**Goal:** Verify LLM generates contextual responses to user speech during phone calls.

**Prerequisites:**
- Phase 2 STT/VAD working
- vLLM server running with Gemma 3 27B (RunPod or local)
- LLM_BASE_URL and LLM_API_KEY configured in .env
- Server logs accessible

## Test 1: Basic Response Generation

**Steps:**
1. Start server: `uvicorn src.main:app --log-level=info`
2. Call Twilio number
3. Speak: "Hello, how are you?"
4. Wait for turn complete + LLM response in logs

**Pass Criteria:**
- [ ] Turn complete triggers LLM generation
- [ ] AI response logged (contextually relevant greeting)
- [ ] Response generated within 2 seconds of turn complete
- [ ] No crashes or errors

**Fail Signals:**
- LLM error logged (check LLM_BASE_URL config)
- No response generated after turn complete
- Server crashes

## Test 2: Multi-Turn Conversation (3+ turns)

**Steps:**
1. Call Twilio number
2. Turn 1: "Hello" -> wait for AI response log
3. Turn 2: "What can you help me with?" -> wait for AI response log
4. Turn 3: "Tell me a joke" -> wait for AI response log

**Pass Criteria:**
- [ ] All 3 turns generate separate responses
- [ ] Responses are contextually relevant
- [ ] Conversation history maintained (AI knows previous context)
- [ ] Turn count logged correctly (Turn 1, Turn 2, Turn 3)

**Fail Signals:**
- Second or third turn gets no response
- AI responses are generic/don't reference previous turns

## Test 3: Context Retention

**Steps:**
1. Call Twilio number
2. Say: "My name is Alex"
3. Wait for response
4. Say: "What's my name?"

**Pass Criteria:**
- [ ] AI remembers the name from previous turn
- [ ] Response references "Alex"

**Fail Signals:**
- AI doesn't remember the name
- Context lost between turns

## Test 4: LLM Error Handling

**Steps:**
1. Set LLM_BASE_URL to invalid endpoint in .env
2. Start server and make a call
3. Speak and trigger turn complete

**Pass Criteria:**
- [ ] Error logged but call doesn't crash
- [ ] WebSocket stays connected
- [ ] Subsequent turns still attempt LLM generation

**Fail Signals:**
- Server crashes on LLM error
- WebSocket disconnects

## Expected Logs

**Successful call logs:**
```
INFO: [abc123] User said: Hello, how are you?
INFO: [abc123] AI response: Hi there! I'm doing great, thanks for calling! How can I help you today?
INFO: [abc123] Turn 1: User='Hello, how are you?' AI='Hi there! I'm doing great...'
```

## Known Limitations (Phase 3)
- AI responds in text logs only (no audio playback — Phase 4: TTS)
- No interruption handling (Phase 5)
- Latency depends on vLLM/RunPod configuration
- Requires running vLLM server with Gemma 3 27B
