"""Transactional email — protocol, a console implementation, and Amazon SES.

The seam (ADR-0026). ``ConsoleEmailSender`` logs the message and never claims a
send — it is the default and the only option that needs no credentials.
``SesEmailSender`` is the hosted path (ADR-0027): it uses the ambient AWS
credential chain (``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` env vars, or an
instance role), so it is inert until those are set and a sending domain is verified.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import aioboto3

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    text_body: str
    from_addr: str


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Logs the email instead of sending it. Used in development and wherever no
    provider is configured. Deliberately does not pretend a message was delivered."""

    async def send(self, message: EmailMessage) -> None:
        log.info(
            "email.console",
            to=message.to,
            subject=message.subject,
            body=message.text_body,
            delivered=False,
        )


class SesEmailSender:
    """Amazon SES (SESv2). Credentials come from the ambient AWS chain."""

    def __init__(self, region: str, *, session: aioboto3.Session | None = None) -> None:
        self._region = region
        self._session = session or aioboto3.Session()

    async def send(self, message: EmailMessage) -> None:
        async with self._session.client("sesv2", region_name=self._region) as client:
            await client.send_email(
                FromEmailAddress=message.from_addr,
                Destination={"ToAddresses": [message.to]},
                Content={
                    "Simple": {
                        "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                        "Body": {"Text": {"Data": message.text_body, "Charset": "UTF-8"}},
                    }
                },
            )
        log.info("email.ses", to=message.to, subject=message.subject, delivered=True)


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.email_sender == "console":
        return ConsoleEmailSender()
    if settings.email_sender == "ses":
        return SesEmailSender(settings.ses_region)
    raise ValueError(f"unknown email_sender: {settings.email_sender!r}")
