from pydantic import BaseModel, Field
from typing import Optional, Literal


class MediaFormat(BaseModel):
    encoding: str  # "audio/x-mulaw"
    sampleRate: int  # 8000
    channels: int  # 1


class StartMessage(BaseModel):
    streamSid: str
    callSid: str
    tracks: list[str]
    mediaFormat: MediaFormat


class MediaPayload(BaseModel):
    payload: str  # base64-encoded audio


class TwilioMessage(BaseModel):
    event: Literal["connected", "start", "media", "stop", "mark", "dtmf"]
    streamSid: Optional[str] = None
    start: Optional[StartMessage] = None
    media: Optional[MediaPayload] = None
    sequenceNumber: Optional[int] = None
