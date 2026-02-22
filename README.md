# Client Caller - Real-Time AI Phone Calling System

A real-time AI phone calling system powered by Twilio, featuring natural conversation with sub-500ms latency.

## Current Status

**Phase 1: Telephony Foundation & Audio Pipeline** ✅ (In Testing)

- [x] FastAPI WebSocket server for Twilio Media Streams
- [x] Audio format conversion (mu-law ↔ PCM, 8kHz ↔ 16kHz)
- [x] Bidirectional streaming with backpressure handling
- [x] Call state management and lifecycle tracking
- [x] Outbound call initiation via Twilio SDK
- [ ] End-to-end testing with real calls

## Prerequisites

### System Requirements

- Python 3.10+ (3.12 recommended)
- FFmpeg (for audio processing)
- Twilio account with phone number
- ngrok account (for local development)

### Install System Dependencies

**macOS:**
```bash
brew install ffmpeg
brew install ngrok
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
# Install ngrok: https://ngrok.com/download
```

## Installation

### 1. Clone and Setup Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` with your Twilio credentials:
```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

Get your Twilio credentials from: https://console.twilio.com/

### 3. Start ngrok Tunnel

In a separate terminal:
```bash
ngrok http 8000
```

Copy the `Forwarding` URL (looks like `https://abc123.ngrok.io`)

## Running the Server

### Development Mode

```bash
# Activate virtual environment if not already active
source venv/bin/activate

# Run server
python -m src.main
```

Server will start on http://localhost:8000

**Endpoints:**
- `/health` - Health check
- `/ws` - WebSocket endpoint for Twilio Media Streams
- `/twiml` - TwiML configuration endpoint
- `/call/outbound` - API to initiate outbound calls

### Configure Twilio Phone Number

1. Go to https://console.twilio.com/us1/develop/phone-numbers/manage/active
2. Click on your phone number
3. Under "Voice Configuration":
   - **A CALL COMES IN**: Webhook
   - **URL**: `https://YOUR-NGROK-URL/twiml` (e.g., https://abc123.ngrok.io/twiml)
   - **HTTP**: POST
4. Click "Save"

## Testing

### Quick Test: Health Check

```bash
curl http://localhost:8000/health
```

Expected output:
```json
{"status": "healthy", "active_connections": 0}
```

### End-to-End Call Test

See [tests/test_e2e_call.md](tests/test_e2e_call.md) for detailed testing checklist.

**Quick test:**
1. Start server: `python -m src.main`
2. Start ngrok: `ngrok http 8000`
3. Configure Twilio number with ngrok URL
4. Call your Twilio number from your phone
5. Speak into the phone - you should hear your voice echoed back

**Expected behavior:**
- Call connects within 2-3 seconds
- Audio is echoed back (you hear yourself with slight delay)
- Connection remains stable for duration of call
- Logs show message types: connected → start → media → stop

### Unit Tests

```bash
pytest tests/ -v
```

### Outbound Call Test

```bash
curl -X POST "http://localhost:8000/call/outbound?to_number=+15551234567&websocket_url=wss://YOUR-NGROK-URL/ws"
```

Replace `+15551234567` with a phone number you have access to.

## Architecture

```
┌─────────────┐
│   Twilio    │◄──────────────┐
│   (PSTN)    │               │
└──────┬──────┘               │
       │ WebSocket            │
       │ (mulaw/8kHz)         │
┌──────▼──────────────────────┴───┐
│  FastAPI Server (localhost:8000)│
│  - WebSocket handler (/ws)      │
│  - TwiML endpoint (/twiml)      │
│  - Audio conversion pipeline    │
│  - State management             │
└─────────────────────────────────┘
```

## Project Structure

```
src/
├── main.py                 # FastAPI application
├── config.py              # Configuration management
├── twilio/
│   ├── models.py          # Pydantic models for messages
│   ├── handlers.py        # WebSocket message handlers
│   └── client.py          # Twilio API client
├── audio/
│   ├── conversion.py      # Mu-law ↔ PCM conversion
│   ├── resampling.py      # 8kHz ↔ 16kHz resampling
│   └── buffers.py         # Bidirectional streaming
└── state/
    └── manager.py         # Call state machine

tests/
├── test_audio_conversion.py   # Audio pipeline tests
└── test_e2e_call.md           # E2E testing checklist
```

## Troubleshooting

### Server won't start

**Error:** `ModuleNotFoundError`
- Solution: Activate virtual environment: `source venv/bin/activate`

**Error:** `pydub.exceptions.CouldntDecodeError`
- Solution: Install FFmpeg (see Prerequisites)

### No audio in call

**Check:**
1. Logs show "media" events being received
2. ngrok tunnel is running and URL matches Twilio config
3. Audio conversion tests pass: `pytest tests/test_audio_conversion.py -v`

### Call doesn't connect

**Check:**
1. Twilio phone number Voice URL configured correctly
2. ngrok URL is HTTPS (not HTTP)
3. Server is running and health endpoint responds
4. Twilio account has sufficient balance

### WebSocket disconnects

**Check logs for:**
- "WebSocket disconnected" message with call_sid
- Any error messages before disconnect
- Audio queue depth warnings (should not exceed 50)

## Next Steps

Phase 1 focuses on telephony foundation. Next phases will add:

- **Phase 2:** Speech-to-Text with streaming (Whisper)
- **Phase 3:** Language Model with streaming (Gemma 3 27B)
- **Phase 4:** Text-to-Speech with streaming (CSM)
- **Phase 5:** Interruption handling & polish
- **Phase 6:** Cloud GPU deployment

## License

[Your License]

## Support

For issues or questions, see project documentation.
