import pytest

from app.core.config import get_settings
from app.notifications import ConsoleEmailSender, SesEmailSender, build_email_sender
from app.notifications.email import EmailMessage


def _settings(**overrides: object):
    return get_settings().model_copy(update=overrides)


def test_build_returns_console_by_default() -> None:
    assert isinstance(build_email_sender(_settings(email_sender="console")), ConsoleEmailSender)


def test_build_returns_ses_when_selected() -> None:
    sender = build_email_sender(_settings(email_sender="ses", ses_region="eu-west-1"))
    assert isinstance(sender, SesEmailSender)


def test_build_rejects_unknown_sender() -> None:
    with pytest.raises(ValueError, match="unknown email_sender"):
        build_email_sender(_settings(email_sender="carrier-pigeon"))


async def test_ses_sender_builds_a_sesv2_send_email_call() -> None:
    """The SES sender translates an EmailMessage into the SESv2 wire shape without a
    real AWS call — a stub session captures the kwargs."""
    calls: list[dict] = []

    class _StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def send_email(self, **kwargs: object) -> None:
            calls.append(kwargs)

    class _StubSession:
        def client(self, service: str, **kw: object):
            assert service == "sesv2"
            return _StubClient()

    sender = SesEmailSender("us-east-1", session=_StubSession())  # type: ignore[arg-type]
    await sender.send(
        EmailMessage(
            to="ops@cedeon.ai",
            subject="new workspace",
            text_body="Acme Re signed up.",
            from_addr="Cedeon <no-reply@cedeon.ai>",
        )
    )

    assert calls == [
        {
            "FromEmailAddress": "Cedeon <no-reply@cedeon.ai>",
            "Destination": {"ToAddresses": ["ops@cedeon.ai"]},
            "Content": {
                "Simple": {
                    "Subject": {"Data": "new workspace", "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": "Acme Re signed up.", "Charset": "UTF-8"}},
                }
            },
        }
    ]
