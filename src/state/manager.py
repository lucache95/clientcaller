"""
Call state management for tracking conversation lifecycle.

States:
- IDLE: No active call
- CONNECTING: WebSocket accepted, waiting for 'start' message
- ACTIVE: Call in progress, audio flowing
- STOPPING: Received 'stop' message, cleaning up
- ERROR: Abnormal termination
"""
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)

class CallState(Enum):
    """Call lifecycle states"""
    IDLE = "idle"
    CONNECTING = "connecting"
    ACTIVE = "active"
    STOPPING = "stopping"
    ERROR = "error"

@dataclass
class CallContext:
    """
    Context for a single call.

    Tracks state, identifiers, and metadata throughout call lifecycle.
    """
    state: CallState
    call_sid: Optional[str] = None
    stream_sid: Optional[str] = None
    websocket: Optional[WebSocket] = None
    connected_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Audio tracking
    audio_received_count: int = 0
    audio_sent_count: int = 0

class CallStateManager:
    """
    Manages call state transitions and context.

    Prevents race conditions by serializing state changes.
    """

    def __init__(self):
        self.calls: Dict[str, CallContext] = {}
        # Temporary storage for calls before we have call_sid
        self.pending_connections: Dict[int, CallContext] = {}

    async def on_connected(self, websocket: WebSocket) -> tuple[int, CallContext]:
        """
        Handle WebSocket connection.

        Returns:
            Tuple of (temp_id, CallContext) for tracking until call_sid arrives
        """
        ctx = CallContext(
            state=CallState.CONNECTING,
            websocket=websocket
        )

        # Temporarily store by websocket id until we get call_sid
        temp_id = id(websocket)
        self.pending_connections[temp_id] = ctx

        logger.info(f"WebSocket connection pending (temp_id: {temp_id})")
        return temp_id, ctx

    async def on_start(self, temp_id: int, call_sid: str, stream_sid: str) -> CallContext:
        """
        Handle stream start message.

        Moves call from pending to active with proper identifiers.

        Args:
            temp_id: Temporary ID from on_connected
            call_sid: Twilio call identifier
            stream_sid: Twilio stream identifier

        Returns:
            CallContext now tracked by call_sid
        """
        # Get pending context
        ctx = self.pending_connections.pop(temp_id, None)

        if not ctx:
            # Shouldn't happen, but handle gracefully
            logger.warning(f"No pending connection for temp_id: {temp_id}, creating new context")
            ctx = CallContext(state=CallState.CONNECTING)

        # Update context with identifiers
        ctx.call_sid = call_sid
        ctx.stream_sid = stream_sid
        ctx.state = CallState.ACTIVE
        ctx.connected_at = datetime.now()

        # Store by call_sid
        self.calls[call_sid] = ctx

        logger.info(f"Call started: {call_sid}, State: {ctx.state.value}")
        return ctx

    async def on_stop(self, call_sid: str) -> Optional[CallContext]:
        """
        Handle stream stop message.

        Transitions to STOPPING state. Actual cleanup happens in cleanup().

        Args:
            call_sid: Twilio call identifier

        Returns:
            CallContext if found, None otherwise
        """
        ctx = self.calls.get(call_sid)

        if ctx:
            ctx.state = CallState.STOPPING
            logger.info(f"Call stopping: {call_sid}")
        else:
            logger.warning(f"Attempted to stop unknown call: {call_sid}")

        return ctx

    async def on_error(self, call_sid: str, error_message: str) -> Optional[CallContext]:
        """
        Handle error during call.

        Transitions to ERROR state.

        Args:
            call_sid: Twilio call identifier
            error_message: Error description

        Returns:
            CallContext if found, None otherwise
        """
        ctx = self.calls.get(call_sid)

        if ctx:
            ctx.state = CallState.ERROR
            ctx.error_message = error_message
            logger.error(f"Call error: {call_sid}, Error: {error_message}")
        else:
            logger.error(f"Error for unknown call: {call_sid}, Error: {error_message}")

        return ctx

    async def cleanup(self, call_sid: str):
        """
        Remove call from tracking.

        Should be called in finally block of WebSocket handler.

        Args:
            call_sid: Twilio call identifier
        """
        ctx = self.calls.pop(call_sid, None)

        if ctx:
            duration = None
            if ctx.connected_at:
                duration = (datetime.now() - ctx.connected_at).total_seconds()

            logger.info(
                f"Call cleanup: {call_sid}, "
                f"Duration: {duration:.1f}s, "
                f"Audio received: {ctx.audio_received_count}, "
                f"Audio sent: {ctx.audio_sent_count}"
            )
        else:
            logger.warning(f"Cleanup for unknown call: {call_sid}")

    def get_context(self, call_sid: str) -> Optional[CallContext]:
        """Get call context by call_sid"""
        return self.calls.get(call_sid)

    def get_active_calls(self) -> Dict[str, CallContext]:
        """Get all active calls"""
        return {
            call_sid: ctx
            for call_sid, ctx in self.calls.items()
            if ctx.state == CallState.ACTIVE
        }

    def get_call_count(self) -> int:
        """Get total number of tracked calls"""
        return len(self.calls)
