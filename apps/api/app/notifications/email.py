"""Transactional email — protocol + a console implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

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


def build_email_sender(settings: Settings) -> EmailSender:
    # Only "console" is implemented. A hosted provider would branch here.
    if settings.email_sender == "console":
        return ConsoleEmailSender()
    raise ValueError(f"unknown email_sender: {settings.email_sender!r}")
