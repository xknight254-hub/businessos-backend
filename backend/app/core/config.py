from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "case_sensitive": True}

    APP_NAME: str = "BusinessOS API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = "postgresql+asyncpg://businessos:businessos@db:5432/businessos"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://businessos:businessos@db:5432/businessos"

    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    # M-Pesa Daraja
    MPESA_CONSUMER_KEY: Optional[str] = None
    MPESA_CONSUMER_SECRET: Optional[str] = None
    MPESA_PASSKEY: Optional[str] = None
    MPESA_SHORTCODE: Optional[str] = None
    MPESA_ENVIRONMENT: str = "sandbox"
    API_BASE_URL: str = "http://localhost:8000"

    # eTIMS
    ETIMS_API_URL: Optional[str] = None
    ETIMS_API_KEY: Optional[str] = None
    ETIMS_TIN: Optional[str] = None

    # OpenAI / AI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None

    # Omniroute AI model gateway (OpenAI-compatible /v1/chat/completions)
    OMNIROUTE_API_KEY: Optional[str] = None
    OMNIROUTE_BASE_URL: str = "http://178.105.198.217:20128/api/v1"

    # WhatsApp
    WHATSAPP_API_TOKEN: Optional[str] = None
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None

    # SMS (Africa's Talking)
    SMS_PROVIDER: str = "mock"  # "mock" | "africastalking"
    AFRICASTALKING_USERNAME: Optional[str] = None
    AFRICASTALKING_API_KEY: Optional[str] = None
    AFRICASTALKING_SENDER_ID: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "Settings":
        # Empty-string env values (e.g. "MPESA_CONSUMER_KEY=") must
        # behave as unset, so Optional credentials fall back to None and
        # mock-mode detection (is_mock) stays correct.
        for f in (
            "MPESA_CONSUMER_KEY", "MPESA_CONSUMER_SECRET", "MPESA_PASSKEY",
            "MPESA_SHORTCODE", "ETIMS_API_KEY", "ETIMS_TIN", "ETIMS_API_URL",
            "OPENAI_API_KEY", "OPENAI_BASE_URL", "OMNIROUTE_API_KEY",
            "WHATSAPP_API_TOKEN", "WHATSAPP_PHONE_NUMBER_ID",
            "AFRICASTALKING_USERNAME", "AFRICASTALKING_API_KEY",
            "AFRICASTALKING_SENDER_ID",
        ):
            if getattr(self, f) == "":
                setattr(self, f, None)
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY == "dev-secret-key-change-in-production":
                raise ValueError(
                    "SECRET_KEY must be set to a real secret in production "
                    "(not the dev default)."
                )
            if not self.DATABASE_URL.startswith("postgresql"):
                raise ValueError("DATABASE_URL must be a PostgreSQL connection string in production.")
            if not self.OPENAI_API_KEY:
                # AI features are optional but warned; not fatal.
                import logging
                logging.getLogger("businessos.config").warning(
                    "OPENAI_API_KEY not set; AI features will be unavailable."
                )
        return self


settings = Settings()
