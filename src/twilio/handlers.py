import json
import base64
import logging
from typing import Dict, Optional
from fastapi import WebSocket
from src.audio.buffers import AudioStreamer
from src.state.manager import CallStateManager

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.streamers: Dict[str, AudioStreamer] = {}

    async def connect(self, call_sid: str, stream_sid: str, websocket: WebSocket):
        # Updated signature to accept stream_sid
        await websocket.accept()
        self.active_connections[call_sid] = websocket

        # Create and start AudioStreamer
        streamer = AudioStreamer(websocket, stream_sid)
        await streamer.start()
        self.streamers[call_sid] = streamer

        logger.info(f"Connection accepted for call: {call_sid}, stream: {stream_sid}")

    async def disconnect(self, call_sid: str):
        # Stop streamer
        streamer = self.streamers.pop(call_sid, None)
        if streamer:
            await streamer.stop()

        self.active_connections.pop(call_sid, None)
        logger.info(f"Connection removed for call: {call_sid}")

    def get(self, call_sid: str) -> WebSocket:
        return self.active_connections.get(call_sid)

    def get_streamer(self, call_sid: str) -> Optional[AudioStreamer]:
        return self.streamers.get(call_sid)


manager = ConnectionManager()

# Create global state manager instance
state_manager = CallStateManager()


async def handle_connected(websocket: WebSocket, data: dict):
    """Handle 'connected' event from Twilio"""
    logger.info("WebSocket connected to Twilio")
    temp_id, ctx = await state_manager.on_connected(websocket)
    # Store temp_id for later retrieval in handle_start
    websocket.state.temp_id = temp_id  # Store on websocket for access


async def handle_start(websocket: WebSocket, data: dict):
    """Handle 'start' event - extract call metadata"""
    start_data = data.get("start", {})
    call_sid = start_data.get("callSid")
    stream_sid = start_data.get("streamSid")
    media_format = start_data.get("mediaFormat", {})

    # Get temp_id from websocket state
    temp_id = getattr(websocket.state, 'temp_id', id(websocket))

    # Update state manager
    ctx = await state_manager.on_start(temp_id, call_sid, stream_sid)

    logger.info(f"Stream started: {stream_sid}, Call: {call_sid}, State: {ctx.state.value}")
    logger.info(f"Media format: {media_format}")

    # Store connection with streamer
    await manager.connect(call_sid, stream_sid, websocket)


async def handle_media(websocket: WebSocket, data: dict):
    """Handle 'media' event - receive audio from Twilio"""
    media_data = data.get("media", {})
    payload = media_data.get("payload")

    if not payload:
        logger.warning("Received media event with no payload")
        return

    # Decode base64 audio
    audio_bytes = base64.b64decode(payload)

    # TODO: Process audio (convert mu-law → PCM, send to STT)
    # For now, just log receipt
    logger.debug(f"Received audio chunk: {len(audio_bytes)} bytes")

    # Echo audio back for testing (simple passthrough)
    response = {
        "event": "media",
        "streamSid": data.get("streamSid"),
        "media": {
            "payload": payload  # Echo back same audio
        }
    }
    await websocket.send_text(json.dumps(response))


async def handle_stop(websocket: WebSocket, data: dict):
    """Handle 'stop' event - stream ending"""
    stop_data = data.get("stop", {})
    call_sid = stop_data.get("callSid")

    # Update state
    await state_manager.on_stop(call_sid)

    logger.info(f"Stream stopped: {call_sid}")

    if call_sid:
        await manager.disconnect(call_sid)
        await state_manager.cleanup(call_sid)


# Message router
MESSAGE_HANDLERS = {
    "connected": handle_connected,
    "start": handle_start,
    "media": handle_media,
    "stop": handle_stop,
    # mark and dtmf events are optional, can be added later
}
