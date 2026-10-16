from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    """
    Settings of the auth package. They are read from the same .env file as
    the rest of the app (src/.env), so helpers/config.py does not change.
    """

    # false = routes are open again (handy while developing)
    AUTH_ENABLED: bool = True

    # SQLite by default. Any SQLAlchemy URL works, e.g.
    # postgresql+psycopg2://user:password@host:5432/db
    AUTH_DATABASE_URL: str = "sqlite:///assets/database/auth.db"

    # ---- JWT ----
    # If empty, a random key is created in assets/database/.jwt.key
    JWT_SECRET_KEY: Optional[str] = None
    JWT_ACCESS_MINUTES: int = 15
    JWT_REFRESH_DAYS: int = 14
    JWT_ISSUER: str = "mini-rag"

    # ---- one-time codes ----
    AUTH_OTP_LENGTH: int = 6
    AUTH_OTP_MINUTES: int = 10
    AUTH_OTP_MAX_ATTEMPTS: int = 5
    AUTH_OTP_RESEND_SECONDS: int = 60
    AUTH_OTP_MAX_PER_HOUR: int = 5

    # ---- accounts ----
    AUTH_PASSWORD_MIN_LENGTH: int = 8
    AUTH_MAX_FAILED_LOGINS: int = 5
    AUTH_LOCK_MINUTES: int = 15
    # comma separated; whoever registers (and verifies) one of these becomes admin
    AUTH_ADMIN_IDENTIFIERS: str = ""
    # region used to read phone numbers written without a country code
    AUTH_DEFAULT_REGION: str = "EG"
    # requests per minute per IP on the auth endpoints
    AUTH_RATE_LIMIT_PER_MINUTE: int = 30

    # ---- how codes are delivered ----
    # console: printed in the server log (development ONLY)
    AUTH_EMAIL_DELIVERY: str = "console"   # console | smtp
    AUTH_SMS_DELIVERY: str = "console"     # console | twilio

    # SMTP (Gmail: smtp.gmail.com, 587, an App Password, not the real password)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_STARTTLS: bool = True

    # Twilio SMS
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM_NUMBER: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_auth_settings() -> AuthSettings:
    return AuthSettings()
