import asyncio
import json
import logging
import signal
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from src.config import settings
from src.twilio.handlers import MESSAGE_HANDLERS, manager, state_manager
from src.twilio.client import generate_twiml, create_outbound_call

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Call metrics for /metrics endpoint
class CallMetrics:
    def __init__(self):
        self.total_calls: int = 0
        self.total_errors: int = 0
        self.total_latency_ms: float = 0.0
        self.call_start_times: dict[str, float] = {}

    def on_call_start(self, call_sid: str):
        self.total_calls += 1
        self.call_start_times[call_sid] = time.monotonic()

    def on_call_end(self, call_sid: str):
        start = self.call_start_times.pop(call_sid, None)
        if start:
            self.total_latency_ms += (time.monotonic() - start) * 1000

    def on_error(self):
        self.total_errors += 1

    @property
    def avg_call_duration_ms(self) -> float:
        completed = self.total_calls - len(self.call_start_times)
        if completed <= 0:
            return 0.0
        return self.total_latency_ms / completed


metrics = CallMetrics()

# Graceful shutdown state
_shutdown_event = asyncio.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info(
        f"Client Caller starting: gpu={settings.use_gpu}, "
        f"tts={settings.tts_engine}, max_calls={settings.max_concurrent_calls}"
    )

    # Pre-load models so first call doesn't wait for downloads
    logger.info("Pre-loading STT model (faster-whisper)...")
    await asyncio.to_thread(manager.get_stt_processor)
    logger.info("STT model loaded")

    logger.info("Pre-loading VAD model (Silero)...")
    await asyncio.to_thread(lambda: manager.get_vad_detector("__warmup__"))
    manager.vad_detectors.pop("__warmup__", None)
    logger.info("VAD model loaded")

    # Register SIGTERM handler for graceful shutdown
    loop = asyncio.get_event_loop()

    def _signal_handler():
        logger.info("SIGTERM received — initiating graceful shutdown")
        _shutdown_event.set()

    loop.add_signal_handler(signal.SIGTERM, _signal_handler)

    yield

    # Shutdown: wait for active calls to finish (up to 30s)
    active = manager.get_active_call_count()
    if active > 0:
        logger.info(f"Graceful shutdown: waiting for {active} active call(s)")
        for _ in range(30):
            if manager.get_active_call_count() == 0:
                break
            await asyncio.sleep(1)
    logger.info("Client Caller shut down")


app = FastAPI(title="Client Caller - Telephony Server", lifespan=lifespan)


@app.get("/health")
async def health_check():
    """Health check with model status and call count."""
    active = manager.get_active_call_count()
    return {
        "status": "healthy",
        "active_calls": active,
        "max_concurrent_calls": settings.max_concurrent_calls,
        "tts_engine": settings.tts_engine,
        "gpu_enabled": settings.use_gpu,
        "stt_loaded": manager.stt_processor is not None,
        "tts_loaded": manager.tts_stream is not None,
    }


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus-compatible metrics."""
    active = manager.get_active_call_count()
    lines = [
        f"# HELP client_caller_calls_total Total calls handled",
        f"# TYPE client_caller_calls_total counter",
        f"client_caller_calls_total {metrics.total_calls}",
        f"# HELP client_caller_calls_active Currently active calls",
        f"# TYPE client_caller_calls_active gauge",
        f"client_caller_calls_active {active}",
        f"# HELP client_caller_errors_total Total errors",
        f"# TYPE client_caller_errors_total counter",
        f"client_caller_errors_total {metrics.total_errors}",
        f"# HELP client_caller_avg_call_duration_ms Average call duration",
        f"# TYPE client_caller_avg_call_duration_ms gauge",
        f"client_caller_avg_call_duration_ms {metrics.avg_call_duration_ms:.1f}",
    ]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")


@app.get("/twiml")
async def twiml_endpoint(request: Request):
    """Serve TwiML to establish Media Stream."""
    host = request.headers.get("host", settings.server_host)
    websocket_url = f"wss://{host}/ws"
    twiml = generate_twiml(websocket_url)
    return Response(content=twiml, media_type="application/xml")


@app.post("/call/outbound")
async def initiate_outbound_call(to_number: str, websocket_url: str):
    """Initiate an outbound call."""
    try:
        result = await create_outbound_call(to_number, websocket_url)
        return result
    except Exception as e:
        return {"error": str(e)}, 500


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for Twilio Media Streams."""
    # Connection limiting: reject if at capacity
    if manager.get_active_call_count() >= settings.max_concurrent_calls:
        logger.warning(
            f"Connection rejected: at capacity "
            f"({settings.max_concurrent_calls} concurrent calls)"
        )
        await websocket.close(code=1013)  # 1013 = Try Again Later
        return

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

                # Track call_sid from start message for cleanup and metrics
                if event == "start":
                    call_sid = data.get("start", {}).get("callSid")
                    if call_sid:
                        metrics.on_call_start(call_sid)

                # Route to appropriate handler
                handler = MESSAGE_HANDLERS.get(event)
                if handler:
                    await handler(websocket, data)
                else:
                    logger.warning(f"No handler for event type: {event}")

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON message: {e}")
                metrics.on_error()
            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)
                metrics.on_error()

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {call_sid}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        metrics.on_error()
    finally:
        # Cleanup on disconnect
        if call_sid:
            metrics.on_call_end(call_sid)
            await manager.disconnect(call_sid)
            await state_manager.cleanup(call_sid)


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", settings.server_port))
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
