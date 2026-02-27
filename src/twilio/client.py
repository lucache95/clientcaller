"""
Twilio API client for outbound call initiation.

Provides functions to create calls programmatically using Twilio SDK.
"""
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from src.config import settings
import logging

logger = logging.getLogger(__name__)

def get_twilio_client() -> Client:
    """
    Get authenticated Twilio client.

    Returns:
        Configured Twilio client instance

    Raises:
        ValueError: If credentials not configured
    """
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise ValueError("Twilio credentials not configured in environment")

    return Client(settings.twilio_account_sid, settings.twilio_auth_token)

def generate_twiml(websocket_url: str) -> str:
    """
    Generate TwiML for Media Streams connection.

    Args:
        websocket_url: Full WSS URL for Twilio to connect to (e.g., wss://your-domain.com/ws)

    Returns:
        TwiML XML string
    """
    response = VoiceResponse()
    # Say greeting first to establish audio path before streaming
    response.say("Hello, how can I help you today?", voice="Polly.Amy")
    connect = Connect()
    stream = Stream(url=websocket_url, track="inbound_track")
    connect.append(stream)
    response.append(connect)

    twiml_str = str(response)
    logger.info(f"Generated TwiML: {twiml_str}")
    return twiml_str

async def create_outbound_call(
    to_number: str,
    websocket_url: str,
    from_number: str = None
) -> dict:
    """
    Initiate an outbound call via Twilio.

    Args:
        to_number: Phone number to call (E.164 format, e.g., +15551234567)
        websocket_url: Full WSS URL for Media Streams connection
        from_number: Optional caller ID (defaults to configured Twilio number)

    Returns:
        Dict with call details (call_sid, status, etc.)

    Raises:
        Exception: If call creation fails
    """
    if not from_number:
        from_number = settings.twilio_phone_number

    if not from_number:
        raise ValueError("from_number must be specified or TWILIO_PHONE_NUMBER configured")

    try:
        client = get_twilio_client()

        # Generate TwiML for this call
        twiml = generate_twiml(websocket_url)

        # Create call
        call = client.calls.create(
            to=to_number,
            from_=from_number,
            twiml=twiml
        )

        logger.info(
            f"Outbound call created: {call.sid}, "
            f"To: {to_number}, From: {from_number}, Status: {call.status}"
        )

        return {
            "call_sid": call.sid,
            "status": call.status,
            "to": to_number,
            "from": from_number,
            "direction": "outbound-api"
        }

    except Exception as e:
        logger.error(f"Failed to create outbound call to {to_number}: {e}", exc_info=True)
        raise
