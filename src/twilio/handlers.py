import json
import base64
import logging
import asyncio
from typing import Dict, Optional
from fastapi import WebSocket
from src.audio.buffers import AudioStreamer
from src.state.manager import CallStateManager
from src.stt.processor import STTProcessor
from src.vad.detector import VADDetector
from src.audio.conversion import mulaw_to_pcm
from src.audio.resampling import resample_8k_to_16k

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.streamers: Dict[str, AudioStreamer] = {}
        self.state_managers: Dict[str, CallStateManager] = {}

        # NEW: STT and VAD processors (shared across calls for model reuse)
        self.stt_processor = None  # Initialized once on first call

        # NEW: VAD instances per call (need separate state per caller)
        self.vad_detectors: Dict[str, VADDetector] = {}

    def get_stt_processor(self):
        """Get or create shared STT processor"""
        if self.stt_processor is None:
            self.stt_processor = STTProcessor(
                model_size="distil-large-v3",
                language="en"
            )
        return self.stt_processor

    def get_vad_detector(self, stream_sid: str) -> VADDetector:
        """Get or create VAD detector for this call"""
        if stream_sid not in self.vad_detectors:
            self.vad_detectors[stream_sid] = VADDetector(
                threshold=0.5,
                min_silence_ms=550,
                min_speech_ms=250
            )
        return self.vad_detectors[stream_sid]

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
    """
    Process incoming audio through STT + VAD pipeline.

    Flow:
    1. Decode base64 mu-law from Twilio
    2. Convert mu-law → PCM 8kHz
    3. Resample 8kHz → 16kHz for STT/VAD
    4. Run VAD to detect speech/silence
    5. Feed audio to STT if speech detected
    6. Finalize transcript on turn complete
    """
    media_data = data.get("media", {})
    payload = media_data.get("payload")
    stream_sid = data.get("streamSid")

    if not payload:
        logger.warning("Received media event with no payload")
        return

    # Decode Twilio audio
    audio_mulaw = base64.b64decode(payload)

    # Phase 1 conversion pipeline
    pcm_8khz = mulaw_to_pcm(audio_mulaw)
    pcm_16khz = resample_8k_to_16k(pcm_8khz)

    # Get processors
    stt_processor = manager.get_stt_processor()
    vad_detector = manager.get_vad_detector(stream_sid)

    # Run VAD on chunk
    vad_result = vad_detector.process_chunk(pcm_16khz)

    if vad_result["is_speech"]:
        # Speech detected - feed to STT
        # Use asyncio.to_thread to avoid blocking event loop (per 02-RESEARCH.md Anti-Pattern 5)
        async def process_stt():
            partials = []
            for partial in stt_processor.process_audio_chunk(pcm_16khz):
                partials.append(partial)
            return partials

        partials = await asyncio.to_thread(process_stt)
        for partial in partials:
            if partial["type"] == "partial":
                logger.info(f"[{stream_sid}] Partial: {partial['text']}")

    # Check for turn complete
    if vad_result["turn_complete"]:
        logger.info(f"[{stream_sid}] Turn complete after {vad_result['silence_duration_ms']}ms silence")

        # Finalize transcript
        final = await asyncio.to_thread(stt_processor.finalize_turn)
        logger.info(f"[{stream_sid}] Final: {final['text']}")

        # Update call state
        # (future: send to LLM in Phase 3)
        logger.info(f"[{stream_sid}] User said: {final['text']}")

        # Reset VAD for next turn
        vad_detector.reset()


async def handle_stop(websocket: WebSocket, data: dict):
    """Handle 'stop' event - stream ending"""
    stop_data = data.get("stop", {})
    call_sid = stop_data.get("callSid")
    stream_sid = stop_data.get("streamSid")

    # Update state
    await state_manager.on_stop(call_sid)

    logger.info(f"Stream stopped: {call_sid}")

    if call_sid:
        await manager.disconnect(call_sid)
        await state_manager.cleanup(call_sid)

    # NEW: Remove VAD detector
    if stream_sid and stream_sid in manager.vad_detectors:
        del manager.vad_detectors[stream_sid]


# Message router
MESSAGE_HANDLERS = {
    "connected": handle_connected,
    "start": handle_start,
    "media": handle_media,
    "stop": handle_stop,
    # mark and dtmf events are optional, can be added later
}
