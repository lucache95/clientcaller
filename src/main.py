import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from src.config import settings
from src.twilio.handlers import MESSAGE_HANDLERS, manager, state_manager
from src.twilio.client import generate_twiml, create_outbound_call

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Client Caller - Telephony Server")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_connections": len(manager.active_connections)
    }


@app.get("/twiml")
async def twiml_endpoint():
    """
    Serve TwiML to establish Media Stream.

    This endpoint can be configured as the Voice URL for a Twilio phone number
    to handle inbound calls.

    For local development, use ngrok URL (e.g., https://abc123.ngrok.io/twiml)
    """
    # Construct WebSocket URL from current request
    # In production, use actual domain; for dev, use ngrok
    # For now, use placeholder - will be replaced in testing plan
    websocket_url = f"wss://{settings.server_host}/ws"

    # Note: This is a placeholder. In practice, you'd configure this via
    # environment variable or derive from request headers.
    # Example: websocket_url = f"wss://{request.headers.get('host')}/ws"

    twiml = generate_twiml(websocket_url)
    return Response(content=twiml, media_type="application/xml")


@app.post("/call/outbound")
async def initiate_outbound_call(to_number: str, websocket_url: str):
    """
    API endpoint to initiate an outbound call.

    Args:
        to_number: Phone number to call (E.164 format)
        websocket_url: WebSocket URL for Media Streams (typically ngrok URL for dev)

    Returns:
        Call details including call_sid

    Example:
        POST /call/outbound?to_number=+15551234567&websocket_url=wss://abc123.ngrok.io/ws
    """
    try:
        result = await create_outbound_call(to_number, websocket_url)
        return result
    except Exception as e:
        return {"error": str(e)}, 500


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams.

    Handles bidirectional audio streaming with message-based protocol.
    """
    await websocket.accept()
    call_sid = None

    try:
        async for message in websocket.iter_text():
            try:
                data = json.loads(message)
                event = data.get("event")

                if not event:
                    logger.warning(f"Received message without event type: {message[:100]}")
                    continue

                # Track call_sid from start message for cleanup
                if event == "start":
                    call_sid = data.get("start", {}).get("callSid")

                # Route to appropriate handler
                handler = MESSAGE_HANDLERS.get(event)
                if handler:
                    await handler(websocket, data)
                else:
                    logger.warning(f"No handler for event type: {event}")

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON message: {e}")
            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {call_sid}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Cleanup on disconnect
        if call_sid:
            await manager.disconnect(call_sid)
            await state_manager.cleanup(call_sid)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=True,
        log_level="info"
    )
