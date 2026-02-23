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
from src.llm.client import LLMClient
from src.llm.conversation import ConversationManager
from src.tts.stream import TTSStream
from src.audio.conversion import mulaw_to_pcm
from src.audio.resampling import resample_8k_to_16k

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.streamers: Dict[str, AudioStreamer] = {}
        self.state_managers: Dict[str, CallStateManager] = {}

        # STT processor (shared across calls for model reuse)
        self.stt_processor = None

        # VAD instances per call (need separate state per caller)
        self.vad_detectors: Dict[str, VADDetector] = {}

        # LLM client (shared, stateless connection pool)
        self.llm_client = None

        # Conversation managers per call (per-call state)
        self.conversations: Dict[str, ConversationManager] = {}

        # TTS stream (shared, stateless)
        self.tts_stream = None

        # stream_sid → call_sid mapping for media handler lookups
        self.stream_to_call: Dict[str, str] = {}

        # Per-call interrupt infrastructure
        self.interrupt_events: Dict[str, asyncio.Event] = {}
        self.is_responding: Dict[str, bool] = {}
        self.response_tasks: Dict[str, asyncio.Task] = {}

    def get_stt_processor(self):
        """Get or create shared STT processor"""
        if self.stt_processor is None:
            self.stt_processor = STTProcessor(
                model_size="distil-large-v3",
                language="en"
            )
        return self.stt_processor

    def get_llm_client(self) -> LLMClient:
        """Get or create shared LLM client"""
        if self.llm_client is None:
            self.llm_client = LLMClient()
        return self.llm_client

    def get_conversation(self, stream_sid: str) -> ConversationManager:
        """Get or create conversation manager for this call"""
        if stream_sid not in self.conversations:
            self.conversations[stream_sid] = ConversationManager()
        return self.conversations[stream_sid]

    def get_vad_detector(self, stream_sid: str) -> VADDetector:
        """Get or create VAD detector for this call"""
        if stream_sid not in self.vad_detectors:
            self.vad_detectors[stream_sid] = VADDetector(
                threshold=0.5,
                min_silence_ms=550,
                min_speech_ms=250
            )
        return self.vad_detectors[stream_sid]

    def get_tts_stream(self) -> TTSStream:
        """Get or create shared TTS stream"""
        if self.tts_stream is None:
            self.tts_stream = TTSStream()
        return self.tts_stream

    def get_interrupt_event(self, stream_sid: str) -> asyncio.Event:
        """Get or create interrupt event for this call"""
        if stream_sid not in self.interrupt_events:
            self.interrupt_events[stream_sid] = asyncio.Event()
        return self.interrupt_events[stream_sid]

    def set_responding(self, stream_sid: str, responding: bool):
        """Mark whether AI is actively responding for this call"""
        self.is_responding[stream_sid] = responding

    async def connect(self, call_sid: str, stream_sid: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[call_sid] = websocket

        # Create and start AudioStreamer
        streamer = AudioStreamer(websocket, stream_sid)
        await streamer.start()
        self.streamers[call_sid] = streamer

        # Map stream_sid → call_sid for media handler lookups
        self.stream_to_call[stream_sid] = call_sid

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
    websocket.state.temp_id = temp_id


async def handle_start(websocket: WebSocket, data: dict):
    """Handle 'start' event - extract call metadata"""
    start_data = data.get("start", {})
    call_sid = start_data.get("callSid")
    stream_sid = start_data.get("streamSid")
    media_format = start_data.get("mediaFormat", {})

    temp_id = getattr(websocket.state, 'temp_id', id(websocket))
    ctx = await state_manager.on_start(temp_id, call_sid, stream_sid)

    logger.info(f"Stream started: {stream_sid}, Call: {call_sid}, State: {ctx.state.value}")
    logger.info(f"Media format: {media_format}")

    await manager.connect(call_sid, stream_sid, websocket)


async def _generate_response(stream_sid: str, user_text: str):
    """
    Generate AI response (LLM → TTS → audio queue) as a cancellable task.

    Sets is_responding=True while active. On cancellation, cleans up gracefully.
    Returns the (response_text, spoken_index) for context tracking.
    """
    conversation = manager.get_conversation(stream_sid)
    llm_client = manager.get_llm_client()
    messages = conversation.get_messages()

    response_tokens = []
    spoken_index = 0

    manager.set_responding(stream_sid, True)
    try:
        # Collect LLM tokens
        async for token in llm_client.generate_streaming(messages):
            response_tokens.append(token)

        response_text = "".join(response_tokens)
        logger.info(f"[{stream_sid}] AI response: {response_text}")

        # Stream response through TTS to caller
        call_sid = manager.stream_to_call.get(stream_sid)
        streamer = manager.get_streamer(call_sid) if call_sid else None
        if streamer and response_text.strip():
            tts_stream = manager.get_tts_stream()
            async for audio_payload in tts_stream.generate(response_text):
                await streamer.queue_audio(audio_payload)
            # All audio sent successfully — full response was spoken
            spoken_index = len(response_text)

        # Add full response to conversation history
        conversation.add_assistant_message(response_text)

        logger.info(
            f"[{stream_sid}] Turn {conversation.get_turn_count()}: "
            f"User='{user_text[:50]}' AI='{response_text[:50]}'"
        )

    except asyncio.CancelledError:
        # Barge-in interrupted us — save only what was spoken
        response_text = "".join(response_tokens)
        spoken_text = response_text[:spoken_index] if response_text else ""
        logger.info(
            f"[{stream_sid}] Response cancelled (barge-in). "
            f"Generated {len(response_text)} chars, spoke {spoken_index} chars"
        )
        if spoken_text.strip():
            conversation.add_assistant_message(spoken_text)
    except Exception as e:
        logger.error(f"[{stream_sid}] LLM/TTS error: {e}")
    finally:
        manager.set_responding(stream_sid, False)
        manager.response_tasks.pop(stream_sid, None)


async def _handle_interrupt(websocket: WebSocket, stream_sid: str):
    """
    Handle a barge-in interrupt: cancel in-flight generation, clear audio, resume listening.

    1. Cancel the active response task (LLM + TTS)
    2. Clear the outbound audio queue
    3. Send Twilio 'clear' message to flush server-side audio buffer
    4. Reset interrupt event and responding flag
    """
    # Cancel the active response task
    task = manager.response_tasks.get(stream_sid)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Clear the audio queue
    call_sid = manager.stream_to_call.get(stream_sid)
    streamer = manager.get_streamer(call_sid) if call_sid else None
    if streamer:
        await streamer.clear_queue()

    # Send Twilio 'clear' message to flush server-side audio buffer
    try:
        clear_msg = json.dumps({"event": "clear", "streamSid": stream_sid})
        await websocket.send_text(clear_msg)
    except Exception as e:
        logger.warning(f"[{stream_sid}] Failed to send clear message: {e}")

    # Reset interrupt state
    interrupt_event = manager.get_interrupt_event(stream_sid)
    interrupt_event.clear()
    manager.set_responding(stream_sid, False)

    # Reset VAD for the new utterance
    vad_detector = manager.get_vad_detector(stream_sid)
    vad_detector.reset()

    logger.info(f"[{stream_sid}] Interrupt handled — cleared queue, cancelled generation")


async def handle_media(websocket: WebSocket, data: dict):
    """
    Process incoming audio through full conversation pipeline.

    Flow:
    1. Decode base64 mu-law from Twilio
    2. Convert mu-law → PCM 8kHz → 16kHz for STT/VAD
    3. Run VAD to detect speech/silence
    4. If speech during AI response → barge-in detected
    5. Feed audio to STT if speech detected
    6. On turn complete: spawn cancellable LLM → TTS response task
    """
    media_data = data.get("media", {})
    payload = media_data.get("payload")
    stream_sid = data.get("streamSid")

    if not payload:
        logger.warning("Received media event with no payload")
        return

    # Decode Twilio audio
    audio_mulaw = base64.b64decode(payload)

    # Audio conversion pipeline
    pcm_8khz = mulaw_to_pcm(audio_mulaw)
    pcm_16khz = resample_8k_to_16k(pcm_8khz)

    # Get processors
    stt_processor = manager.get_stt_processor()
    vad_detector = manager.get_vad_detector(stream_sid)

    # Run VAD on chunk
    vad_result = vad_detector.process_chunk(pcm_16khz)

    # Barge-in detection: user speaking while AI is responding
    if vad_result["is_speech"] and manager.is_responding.get(stream_sid, False):
        interrupt_event = manager.get_interrupt_event(stream_sid)
        if not interrupt_event.is_set():
            interrupt_event.set()
            logger.info(f"[{stream_sid}] Barge-in detected — user interrupting AI")
            await _handle_interrupt(websocket, stream_sid)

    if vad_result["is_speech"]:
        # Speech detected - feed to STT
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

        # Finalize STT transcript
        final = await asyncio.to_thread(stt_processor.finalize_turn)
        user_text = final["text"]
        logger.info(f"[{stream_sid}] User said: {user_text}")

        if user_text and user_text.strip():
            conversation = manager.get_conversation(stream_sid)
            conversation.add_user_message(user_text)

            # Spawn response as cancellable task
            task = asyncio.create_task(_generate_response(stream_sid, user_text))
            manager.response_tasks[stream_sid] = task

        # Reset VAD for next turn
        vad_detector.reset()


async def handle_stop(websocket: WebSocket, data: dict):
    """Handle 'stop' event - stream ending"""
    stop_data = data.get("stop", {})
    call_sid = stop_data.get("callSid")
    stream_sid = stop_data.get("streamSid")

    # Cancel any in-flight response task
    if stream_sid:
        task = manager.response_tasks.pop(stream_sid, None)
        if task and not task.done():
            task.cancel()

    # Update state
    await state_manager.on_stop(call_sid)
    logger.info(f"Stream stopped: {call_sid}")

    if call_sid:
        await manager.disconnect(call_sid)
        await state_manager.cleanup(call_sid)

    # Cleanup per-call state
    if stream_sid:
        manager.vad_detectors.pop(stream_sid, None)
        manager.conversations.pop(stream_sid, None)
        manager.stream_to_call.pop(stream_sid, None)
        manager.interrupt_events.pop(stream_sid, None)
        manager.is_responding.pop(stream_sid, None)
        manager.response_tasks.pop(stream_sid, None)


# Message router
MESSAGE_HANDLERS = {
    "connected": handle_connected,
    "start": handle_start,
    "media": handle_media,
    "stop": handle_stop,
}
