import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from src.config import settings
from src.twilio.handlers import MESSAGE_HANDLERS, manager

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
            manager.disconnect(call_sid)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=True,
        log_level="info"
    )
