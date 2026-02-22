"""
Bidirectional audio streaming with backpressure handling.

Prevents buffer overflow when TTS generates audio faster than network can transmit.
Uses bounded queues with timeout to detect stalls.
"""
import asyncio
import json
import logging
from asyncio import Queue
from typing import Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class AudioStreamer:
    """
    Manages bidirectional audio streaming for a single call.

    Implements backpressure: if outbound queue is full, blocks producer
    to prevent memory overflow.
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
            # This blocks if queue is full (backpressure)
            await asyncio.wait_for(
                self.outbound_queue.put(audio_payload),
                timeout=1.0  # Fail if can't queue within 1 second
            )
            logger.debug(f"Queued audio chunk, queue depth: {self.outbound_queue.qsize()}")

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
        Background task to send queued audio to Twilio.

        Sends at real-time rate (~20ms per chunk) to match playback speed
        and prevent sending faster than Twilio can play.
        """
        while self.running:
            try:
                # Get next audio chunk (blocks if empty)
                payload = await self.outbound_queue.get()

                # Send to Twilio
                message = {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {
                        "payload": payload
                    }
                }
                await self.websocket.send_text(json.dumps(message))

                # Small delay to match real-time playback rate
                # Prevents sending faster than Twilio can play
                # 20ms per chunk is typical for 8kHz audio
                await asyncio.sleep(0.020)

            except asyncio.CancelledError:
                logger.info("Send loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error sending audio: {e}", exc_info=True)
                break

        logger.info("Send loop exited")
