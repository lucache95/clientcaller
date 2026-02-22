import json
import base64
import logging
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, call_sid: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[call_sid] = websocket
        logger.info(f"Connection accepted for call: {call_sid}")

    def disconnect(self, call_sid: str):
        self.active_connections.pop(call_sid, None)
        logger.info(f"Connection removed for call: {call_sid}")

    def get(self, call_sid: str) -> WebSocket:
        return self.active_connections.get(call_sid)


manager = ConnectionManager()


async def handle_connected(websocket: WebSocket, data: dict):
    """Handle 'connected' event from Twilio"""
    logger.info("WebSocket connected to Twilio")


async def handle_start(websocket: WebSocket, data: dict):
    """Handle 'start' event - extract call metadata"""
    start_data = data.get("start", {})
    call_sid = start_data.get("callSid")
    stream_sid = start_data.get("streamSid")
    media_format = start_data.get("mediaFormat", {})

    logger.info(f"Stream started: {stream_sid}, Call: {call_sid}")
    logger.info(f"Media format: {media_format}")

    # Store connection
    await manager.connect(call_sid, websocket)


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

    logger.info(f"Stream stopped: {call_sid}")

    if call_sid:
        manager.disconnect(call_sid)


# Message router
MESSAGE_HANDLERS = {
    "connected": handle_connected,
    "start": handle_start,
    "media": handle_media,
    "stop": handle_stop,
    # mark and dtmf events are optional, can be added later
}
