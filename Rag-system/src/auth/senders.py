import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from auth.config import AuthSettings

logger = logging.getLogger("uvicorn.error")


class DeliveryError(Exception):
    pass


class ConsoleSender:
    """Development only: the code is printed in the server log."""

    def send(self, to: str, subject: str, body: str) -> None:

        logger.warning("[AUTH DEV] message to %s | %s | %s", to, subject, body.replace("\n", " / "))


class SMTPSender:
    """Email through any SMTP server (Gmail needs an App Password)."""

    def __init__(self, settings: AuthSettings):

        if not (settings.SMTP_HOST and settings.SMTP_FROM):
            raise DeliveryError("SMTP_HOST and SMTP_FROM must be set for email delivery.")

        self.settings = settings

    def send(self, to: str, subject: str, body: str) -> None:

        s = self.settings

        message = EmailMessage()
        message["From"] = s.SMTP_FROM
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=15) as server:

                if s.SMTP_STARTTLS:
                    server.starttls()

                if s.SMTP_USER:
                    server.login(s.SMTP_USER, s.SMTP_PASSWORD or "")

                server.send_message(message)

        except (OSError, smtplib.SMTPException) as exc:
            raise DeliveryError(f"SMTP delivery failed: {type(exc).__name__}")


class TwilioSMSSender:
    """SMS through Twilio's REST API."""

    def __init__(self, settings: AuthSettings, transport=None):

        if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER):
            raise DeliveryError("TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER must be set.")

        self.settings = settings
        self.transport = transport      # only for tests

    def send(self, to: str, subject: str, body: str) -> None:

        import httpx

        s = self.settings

        try:
            with httpx.Client(timeout=15, transport=self.transport) as client:
                response = client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{s.TWILIO_ACCOUNT_SID}/Messages.json",
                    auth=(s.TWILIO_ACCOUNT_SID, s.TWILIO_AUTH_TOKEN),
                    data={"To": to, "From": s.TWILIO_FROM_NUMBER, "Body": body},
                )
        except httpx.HTTPError as exc:
            raise DeliveryError(f"SMS delivery failed: {type(exc).__name__}")

        if response.status_code >= 300:
            raise DeliveryError(f"SMS provider answered {response.status_code}")


def build_senders(settings: AuthSettings) -> dict:
    """{"email": sender, "phone": sender} chosen by the settings."""

    email = (settings.AUTH_EMAIL_DELIVERY or "console").lower()
    sms = (settings.AUTH_SMS_DELIVERY or "console").lower()

    if email not in ("console", "smtp"):
        raise DeliveryError("AUTH_EMAIL_DELIVERY must be console or smtp.")

    if sms not in ("console", "twilio"):
        raise DeliveryError("AUTH_SMS_DELIVERY must be console or twilio.")

    return {
        "email": SMTPSender(settings) if email == "smtp" else ConsoleSender(),
        "phone": TwilioSMSSender(settings) if sms == "twilio" else ConsoleSender(),
    }
