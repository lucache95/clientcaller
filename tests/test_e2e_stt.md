# Phase 2: Speech-to-Text End-to-End Testing

**Goal:** Verify real-time speech transcription with turn detection on live phone calls.

## Prerequisites
- Phase 1 telephony infrastructure operational (Railway deployment or ngrok)
- Phase 2 STT/VAD modules installed
- Twilio phone number configured
- Server logs accessible

## Test 1: Basic Speech Transcription

**Steps:**
1. Start server with logging enabled: `uvicorn src.main:app --log-level=info`
2. Call Twilio number from phone
3. Wait for connection (should hear silence, no echo)
4. Speak clearly: "Hello, this is a test"
5. Pause for 2 seconds (silence)

**Pass Criteria:**
- [ ] Server logs show "Partial: Hello" (within 1 second of speaking)
- [ ] Server logs show "Partial: Hello, this is a test" (real-time updates)
- [ ] Server logs show "Turn complete" after 550-700ms silence
- [ ] Server logs show "Final: Hello, this is a test" with >80% accuracy
- [ ] No crashes or errors

**Fail Signals:**
- Transcripts are gibberish or empty
- Turn complete never triggers
- Turn complete triggers mid-sentence (premature cutoff)
- Server crashes with ImportError or model loading error

## Test 2: Turn Detection Timing

**Steps:**
1. Call Twilio number
2. Speak: "Testing turn detection"
3. Stop speaking and measure time until turn complete log

**Pass Criteria:**
- [ ] Turn complete triggers within 300-700ms of silence
- [ ] VAD doesn't trigger during mid-sentence pauses
- [ ] Turn complete logged with silence duration

**Fail Signals:**
- Turn complete takes >1 second (too slow)
- Turn complete triggers during natural pauses (false positive)

## Test 3: Natural Pauses (No Premature Cutoff)

**Steps:**
1. Call Twilio number
2. Speak with deliberate pauses: "I need to... um... schedule an appointment"
3. Check if turn completes prematurely

**Pass Criteria:**
- [ ] Turn complete only triggers after final word "appointment"
- [ ] Partial transcripts include "um" and pauses
- [ ] Final transcript is complete sentence

**Fail Signals:**
- Turn complete triggers after "to..." or "um..."
- Transcript cuts off mid-sentence

## Test 4: Accuracy on PSTN Audio Quality

**Steps:**
1. Call from different phone types (cell phone, landline if available)
2. Speak clearly with no background noise
3. Test phrases: "Can you hear me clearly", "The quick brown fox jumps"

**Pass Criteria:**
- [ ] Transcripts >80% accurate on clear speech
- [ ] Common words transcribed correctly ("the", "can", "you")
- [ ] Proper nouns may be inaccurate (acceptable for Phase 2)

**Fail Signals:**
- Transcripts <50% accurate on clear speech
- Simple words consistently wrong

## Test 5: Multiple Turns in One Call

**Steps:**
1. Call Twilio number
2. Speak first sentence: "Hello"
3. Wait for turn complete
4. Speak second sentence: "How are you"
5. Wait for turn complete
6. Hang up

**Pass Criteria:**
- [ ] Both turns detected separately
- [ ] Final transcripts for both turns logged
- [ ] VAD resets between turns (no context bleed)

**Fail Signals:**
- Second turn doesn't trigger turn complete
- Transcripts merge across turns

## Test 6: Background Noise Handling

**Steps:**
1. Call from noisy environment (traffic, TV, music)
2. Speak clearly: "This is a test"
3. Check transcripts and VAD behavior

**Pass Criteria:**
- [ ] VAD doesn't trigger on background noise alone
- [ ] Speech transcripts reasonably accurate despite noise
- [ ] Turn detection still works

**Fail Signals:**
- VAD triggers constantly on background noise
- Transcripts are nonsense from background sounds
- Turn detection fails in noisy environment

**Note:** If Test 6 fails, may need to increase VAD threshold from 0.5 to 0.6-0.7 in src/twilio/handlers.py per 02-RESEARCH.md recommendations.

## Expected Logs

**Successful call logs:**
```
INFO: [abc123] Partial: Hello
INFO: [abc123] Partial: Hello, this
INFO: [abc123] Partial: Hello, this is a test
INFO: [abc123] Turn complete after 620ms silence
INFO: [abc123] Final: Hello, this is a test
INFO: [abc123] User said: Hello, this is a test
```

## Known Limitations (Phase 2)

- System only transcribes, doesn't respond yet (Phase 3: LLM)
- No audio playback to caller (Phase 4: TTS)
- No interruption handling (Phase 5)
- VAD thresholds are fixed (may need tuning based on testing)

## Troubleshooting

**No transcripts appearing:**
- Check model downloaded: `ls ~/.cache/huggingface/hub/` should show distil-whisper model
- Check imports: `python -c "from src.stt import STTProcessor"`

**Turn complete never triggers:**
- VAD may be too sensitive. Try increasing min_silence_ms to 800-1000ms
- Check audio reaching VAD: Add logging in handle_media()

**Premature turn complete (cuts off mid-sentence):**
- VAD min_silence_ms too low. Increase from 550ms to 700-800ms
- Check for PSTN audio quality issues

**Poor transcription accuracy:**
- PSTN audio is 8kHz mu-law (low quality). 70-80% accuracy is normal.
- Try speaking more clearly and slowly
- Check if background noise is interfering
