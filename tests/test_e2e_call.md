# End-to-End Call Testing Checklist

## Prerequisites

- [ ] Server running: `python -m src.main`
- [ ] ngrok tunnel active: `ngrok http 8000`
- [ ] Twilio phone number configured with ngrok URL
- [ ] Valid Twilio credentials in `.env`

## Test 1: Inbound Call - Basic Connection

**Objective:** Verify system accepts inbound calls and maintains connection.

**Steps:**
1. Call your Twilio number from your phone
2. Wait for call to connect (2-3 seconds)
3. Listen for any audio/tone
4. Stay on call for 30 seconds
5. Hang up

**Expected Results:**
- [ ] Call connects successfully
- [ ] Server logs show: `connected` → `start` → `media` events
- [ ] Call remains stable for full 30 seconds
- [ ] Logs show `stop` event on hangup
- [ ] No error messages in server logs
- [ ] Health endpoint shows `active_connections: 0` after hangup

**Server Logs to Verify:**
```
INFO - WebSocket connected to Twilio
INFO - Stream started: MZ..., Call: CA...
INFO - Connection accepted for call: CA...
DEBUG - Received audio chunk: 160 bytes
...
INFO - Stream stopped: CA...
INFO - Call cleanup: CA..., Duration: 30.2s
```

## Test 2: Inbound Call - Audio Echo

**Objective:** Verify bidirectional audio streaming works.

**Steps:**
1. Call your Twilio number
2. Wait for connection
3. Say "Hello, testing one two three"
4. Listen for echo response
5. Speak several more sentences
6. Stay on call for 1 minute
7. Hang up

**Expected Results:**
- [ ] You hear your own voice echoed back
- [ ] Echo has slight delay (expected network latency)
- [ ] Audio quality is clear (not garbled or distorted)
- [ ] Echo works consistently for entire call
- [ ] Logs show `audio_received_count` and `audio_sent_count` increasing
- [ ] No queue overflow warnings

**Audio Quality Checks:**
- [ ] Voice is recognizable
- [ ] No crackling or distortion
- [ ] No robotic artifacts (would indicate mu-law conversion issues)
- [ ] Volume is appropriate (not too quiet/loud)

## Test 3: Inbound Call - Connection Stability

**Objective:** Verify system handles longer calls without issues.

**Steps:**
1. Call your Twilio number
2. Stay on call for 2-3 minutes
3. Speak intermittently (every 15-20 seconds)
4. Monitor server logs during call
5. Hang up

**Expected Results:**
- [ ] Call remains connected for full duration
- [ ] No WebSocket disconnects
- [ ] Audio continues working throughout
- [ ] Memory usage stable (no leaks)
- [ ] Queue depth remains bounded (< 50)
- [ ] Cleanup happens correctly on hangup

**Monitor Logs For:**
- No "WebSocket disconnected" before intentional hangup
- No "Audio queue full" warnings
- No "Error handling message" logs
- Steady stream of "Received audio chunk" logs

## Test 4: Outbound Call

**Objective:** Verify system can initiate outbound calls.

**Prerequisites:**
- [ ] Have a phone number you can call (your personal phone)

**Steps:**
1. Ensure server and ngrok running
2. Make outbound call API request:
   ```bash
   curl -X POST "http://localhost:8000/call/outbound?to_number=+1YOUR_PHONE&websocket_url=wss://YOUR_NGROK_URL/ws"
   ```
3. Answer the incoming call on your phone
4. Speak and listen for echo
5. Stay on call for 30 seconds
6. Hang up

**Expected Results:**
- [ ] API returns call_sid and status
- [ ] Your phone rings within 3-5 seconds
- [ ] Call connects when answered
- [ ] Audio echo works (same as inbound test)
- [ ] Call remains stable
- [ ] Logs show same message flow as inbound

**API Response to Verify:**
```json
{
  "call_sid": "CA...",
  "status": "queued",
  "to": "+1...",
  "from": "+1...",
  "direction": "outbound-api"
}
```

## Test 5: Multiple Concurrent Calls (Optional)

**Objective:** Verify system can handle multiple simultaneous calls.

**Steps:**
1. Call Twilio number from Phone 1
2. While connected, call from Phone 2 (or use outbound API)
3. Both calls should echo audio
4. Hang up Phone 1, verify Phone 2 still works
5. Hang up Phone 2

**Expected Results:**
- [ ] Both calls connect successfully
- [ ] Each call has independent audio echo
- [ ] Logs show two separate call_sids
- [ ] Health endpoint shows `active_connections: 2`
- [ ] Hanging up one call doesn't affect the other
- [ ] State manager tracks both calls correctly

## Test 6: Error Handling

**Objective:** Verify graceful handling of abnormal conditions.

**Test 6a: Server Restart During Call**
1. Establish call
2. Kill server (Ctrl+C)
3. Verify call disconnects gracefully

Expected:
- [ ] Call drops (expected behavior)
- [ ] No errors in terminal
- [ ] Can restart server without issues

**Test 6b: ngrok Tunnel Expires**
1. Establish call
2. Stop ngrok (Ctrl+C in ngrok terminal)
3. Observe behavior

Expected:
- [ ] Call may disconnect or freeze
- [ ] Server logs show WebSocket disconnect
- [ ] Server continues running (doesn't crash)

**Test 6c: Invalid Twilio Credentials**
1. Put invalid credentials in `.env`
2. Try to start server or make outbound call

Expected:
- [ ] Outbound call fails with authentication error
- [ ] Error message is clear and logged
- [ ] Server doesn't crash

## Common Issues and Solutions

### Issue: No echo heard

**Check:**
- Logs show "Received audio chunk" messages?
- Logs show "Queued audio chunk" messages?
- AudioStreamer started successfully?

**Solution:**
- Verify audio conversion tests pass
- Check queue depth isn't maxed out (50)
- Restart server and try again

### Issue: Garbled audio

**Possible causes:**
- Mu-law conversion error
- Sample rate mismatch
- Buffer overflow

**Solution:**
- Run audio conversion tests
- Check for queue warnings in logs
- Verify FFmpeg is installed correctly

### Issue: Call connects but no media events

**Check:**
- Twilio Voice URL configured with correct ngrok URL?
- ngrok URL is HTTPS (wss:// for WebSocket)?
- /twiml endpoint returns valid XML?

**Solution:**
```bash
# Test TwiML endpoint
curl http://localhost:8000/twiml

# Should return XML with <Stream> tag
```

## Success Criteria

Phase 1 is complete when:

- [x] All Test 1-4 pass consistently
- [x] Audio echo works clearly
- [x] Calls remain stable for 2+ minutes
- [x] Both inbound and outbound calls work
- [x] State management tracks calls correctly
- [x] No memory leaks or resource issues
- [x] Documentation is complete and accurate

## Next Phase Preview

Phase 2 will replace the echo with speech-to-text:
- User speaks → Whisper transcribes → logs show transcript
- No echo anymore, just transcription
- Prepares for LLM integration in Phase 3
