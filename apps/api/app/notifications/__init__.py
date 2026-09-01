"""Outbound notifications. Today: transactional email for team invitations.

``EmailSender`` is the seam. ``ConsoleEmailSender`` logs the message (dev, and any
environment without a provider configured) — it never claims a real send. A hosted
provider (SES / Resend / Postmark) slots in behind the same protocol; not wired
without credentials.
"""

from app.notifications.email import (
    ConsoleEmailSender,
    EmailMessage,
    EmailSender,
    SesEmailSender,
    build_email_sender,
)

__all__ = [
    "ConsoleEmailSender",
    "EmailMessage",
    "EmailSender",
    "SesEmailSender",
    "build_email_sender",
]
