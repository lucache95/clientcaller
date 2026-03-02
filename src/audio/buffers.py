"""
Bidirectional audio streaming with backpressure handling.

Prevents buffer overflow when TTS generates audio faster than network can transmit.
Uses bounded queues with timeout to detect stalls.
Always transmits at 20ms intervals — silence when idle, TTS audio when available.
This keeps the Twilio media path established (both sides must send for RTP to flow).
"""
import asyncio
import base64
import json
import logging
from asyncio import Queue
from typing import Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)

# 160 bytes of 0xFF mulaw = 20ms of silence at 8kHz mono
_SILENCE_PAYLOAD = base64.b64encode(b'\xff' * 160).decode('utf-8')


class AudioStreamer:
    """
    Manages bidirectional audio streaming for a single call.

    Always transmits at 20ms intervals to keep the Twilio media path alive.
    Sends TTS audio from the queue when available, silence otherwise.
    """

    def __init__(self, websocket: WebSocket, stream_sid: str):
        self.websocket = websocket
        self.stream_sid = stream_sid
        # ~1 second buffer at 20ms per chunk = 50 chunks max
        self.outbound_queue: Queue[str] = Queue(maxsize=50)
        self.running = False
        self._send_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start background task to send queued audio to Twilio"""
        self.running = True
        self._send_task = asyncio.create_task(self._send_loop())
        logger.info(f"AudioStreamer started for stream: {self.stream_sid}")

    async def stop(self):
        """Stop background sending and cleanup"""
        self.running = False
        if self._send_task:
            self._send_task.cancel()
            try:
                await self._send_task
            except asyncio.CancelledError:
                pass
        logger.info(f"AudioStreamer stopped for stream: {self.stream_sid}")

    async def queue_audio(self, audio_payload: str):
        """
        Queue audio for sending to Twilio.

        Implements backpressure: if queue is full, this will block
        until space is available, preventing memory overflow.

        Args:
            audio_payload: Base64-encoded mu-law audio

        Raises:
            asyncio.TimeoutError: If can't queue within 1 second (stall detected)
        """
        try:
            await asyncio.wait_for(
                self.outbound_queue.put(audio_payload),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Audio queue full for stream {self.stream_sid}, dropping packet. "
                f"Queue size: {self.outbound_queue.qsize()}/{self.outbound_queue.maxsize}"
            )
            raise

    async def clear_queue(self):
        """Clear all queued audio (used for interruptions)"""
        while not self.outbound_queue.empty():
            try:
                self.outbound_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        logger.info(f"Cleared audio queue for stream: {self.stream_sid}")

    async def _send_loop(self):
        """
        Background task: always transmit at 20ms intervals.

        Sends TTS audio from the queue when available, silence otherwise.
        Continuous transmission keeps the Twilio bidirectional media path
        established — without it, inbound audio arrives as all-silence.
        """
        while self.running:
            try:
                # Send TTS audio if available, otherwise silence
                try:
                    payload = self.outbound_queue.get_nowait()
                except asyncio.QueueEmpty:
                    payload = _SILENCE_PAYLOAD

                message = {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {
                        "payload": payload
                    }
                }
                await self.websocket.send_text(json.dumps(message))
                await asyncio.sleep(0.020)

            except asyncio.CancelledError:
                logger.info("Send loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error sending audio: {e}", exc_info=True)
                break

        logger.info("Send loop exited")
