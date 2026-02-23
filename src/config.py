from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    twilio_account_sid: str = Field(..., env="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(..., env="TWILIO_AUTH_TOKEN")
    twilio_phone_number: str = Field(..., env="TWILIO_PHONE_NUMBER")
    server_host: str = Field(default="0.0.0.0", env="SERVER_HOST")
    server_port: int = Field(default=8000, env="SERVER_PORT")

    # LLM Configuration (vLLM / RunPod)
    llm_base_url: str = Field(default="http://localhost:8000/v1", env="LLM_BASE_URL")
    llm_api_key: str = Field(default="EMPTY", env="LLM_API_KEY")
    llm_model: str = Field(default="google/gemma-3-27b-it", env="LLM_MODEL")
    llm_max_tokens: int = Field(default=256, env="LLM_MAX_TOKENS")
    llm_temperature: float = Field(default=0.7, env="LLM_TEMPERATURE")

    # TTS Configuration
    tts_engine: str = Field(default="edge", env="TTS_ENGINE")
    tts_voice: str = Field(default="en-US-AriaNeural", env="TTS_VOICE")
    tts_rate: str = Field(default="+0%", env="TTS_RATE")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Allow extra fields in .env without raising errors


settings = Settings()
