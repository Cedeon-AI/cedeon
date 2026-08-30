"""The notice draft: a communication drafted from a **whitelist of approved
values only**, for human review before it is ever sent.

The drafter (docs/AI_ARCHITECTURE.md §2c) runs only after a human confirms the
recovery candidate, receives the ``NoticeContext`` below and nothing else — no raw
document text, no unvalidated AI output — and produces a draft. **Cedeon never
sends anything.** There is no send action anywhere in the codebase; the terminal
state of a notice is APPROVED, and a human takes it from there.

Pure: standard library only."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class NoticeKind(StrEnum):
    INITIAL_LOSS_ADVICE = "initial_loss_advice"
    REINSURER_NOTIFICATION = "reinsurer_notification"


class NoticeStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


_KIND_TITLE = {
    NoticeKind.INITIAL_LOSS_ADVICE: "Initial Loss Advice",
    NoticeKind.REINSURER_NOTIFICATION: "Reinsurer Notification of Loss",
}


@dataclass(frozen=True, slots=True)
class NoticeRecipient:
    name: str
    organisation: str
    role: str = ""
    email: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "organisation": self.organisation,
            "role": self.role,
            "email": self.email,
        }


@dataclass(frozen=True, slots=True)
class NoticeParticipant:
    name: str
    share_percent: str
    allocated_recovery: str


@dataclass(slots=True)
class NoticeContext:
    """Every value the drafter is allowed to use. Assembled by deterministic code
    from confirmed / validated state only."""

    kind: NoticeKind
    cedent_name: str
    treaty_name: str
    program_name: str
    currency: str
    attachment: str
    limit: str
    loss_event_name: str
    catastrophe_code: str | None
    date_of_loss_from: str | None
    date_of_loss_to: str | None
    gross_event_incurred: str
    layer_recovery: str
    engine_version: str
    participants: list[NoticeParticipant]
    notice_provision: str | None
    packet_approved: bool
    recipient: NoticeRecipient
    generated_on: str

    @property
    def title(self) -> str:
        return _KIND_TITLE[self.kind]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "cedent_name": self.cedent_name,
            "treaty_name": self.treaty_name,
            "program_name": self.program_name,
            "currency": self.currency,
            "attachment": self.attachment,
            "limit": self.limit,
            "loss_event_name": self.loss_event_name,
            "catastrophe_code": self.catastrophe_code,
            "date_of_loss_from": self.date_of_loss_from,
            "date_of_loss_to": self.date_of_loss_to,
            "gross_event_incurred": self.gross_event_incurred,
            "layer_recovery": self.layer_recovery,
            "engine_version": self.engine_version,
            "participants": [
                {
                    "name": p.name,
                    "share_percent": p.share_percent,
                    "allocated_recovery": p.allocated_recovery,
                }
                for p in self.participants
            ],
            "notice_provision": self.notice_provision,
            "packet_approved": self.packet_approved,
            "recipient": self.recipient.to_dict(),
            "generated_on": self.generated_on,
        }

    def to_prompt(self) -> str:
        lines = [
            f"NOTICE TYPE: {self.title}",
            f"CEDING COMPANY (the sender's principal): {self.cedent_name}",
            f"REINSURANCE PROGRAMME: {self.program_name}",
            f"TREATY: {self.treaty_name}",
            f"LAYER: {self.currency} {self.limit} excess of {self.currency} {self.attachment} "
            "each and every loss occurrence",
            f"LOSS EVENT: {self.loss_event_name}"
            + (f" (catastrophe code {self.catastrophe_code})" if self.catastrophe_code else ""),
        ]
        if self.date_of_loss_from:
            span = self.date_of_loss_from
            if self.date_of_loss_to and self.date_of_loss_to != self.date_of_loss_from:
                span += f" to {self.date_of_loss_to}"
            lines.append(f"DATE(S) OF LOSS: {span}")
        lines += [
            f"GROSS EVENT INCURRED (ceding company, {self.currency}): {self.gross_event_incurred}",
            f"INDICATED LAYER RECOVERY ({self.currency}, Cedeon deterministic engine "
            f"{self.engine_version}): {self.layer_recovery}",
            "PARTICIPATING REINSURERS AND THEIR INDICATED SHARE OF THE RECOVERY:",
        ]
        for p in self.participants:
            lines.append(
                f"  - {p.name}: {p.share_percent} → {self.currency} {p.allocated_recovery}"
            )
        if self.notice_provision:
            lines.append(f"TREATY NOTICE PROVISION (validated): {self.notice_provision}")
        lines.append(
            "PACKET STATUS: "
            + (
                "a human-approved recovery packet supports this notice."
                if self.packet_approved
                else "no approved recovery packet yet — this notice is preliminary."
            )
        )
        lines.append(
            f"ADDRESSEE: {self.recipient.name}"
            + (f", {self.recipient.role}" if self.recipient.role else "")
            + f", {self.recipient.organisation}"
        )
        lines.append(f"DATE OF THIS NOTICE: {self.generated_on}")
        return "\n".join(lines)


@dataclass(slots=True)
class NoticeInputs:
    kind: NoticeKind
    recipient: NoticeRecipient
    cedent_name: str
    treaty_name: str
    program_name: str
    currency: str
    attachment: str
    limit: str
    loss_event_name: str
    catastrophe_code: str | None
    date_of_loss_from: str | None
    date_of_loss_to: str | None
    gross_event_incurred: str
    layer_recovery: str
    engine_version: str
    participants: list[NoticeParticipant] = field(default_factory=list)
    notice_provision: str | None = None
    packet_approved: bool = False
    generated_on: str = ""


def build_notice_context(inputs: NoticeInputs) -> NoticeContext:
    return NoticeContext(
        kind=inputs.kind,
        cedent_name=inputs.cedent_name,
        treaty_name=inputs.treaty_name,
        program_name=inputs.program_name,
        currency=inputs.currency,
        attachment=inputs.attachment,
        limit=inputs.limit,
        loss_event_name=inputs.loss_event_name,
        catastrophe_code=inputs.catastrophe_code,
        date_of_loss_from=inputs.date_of_loss_from,
        date_of_loss_to=inputs.date_of_loss_to,
        gross_event_incurred=inputs.gross_event_incurred,
        layer_recovery=inputs.layer_recovery,
        engine_version=inputs.engine_version,
        participants=list(inputs.participants),
        notice_provision=inputs.notice_provision,
        packet_approved=inputs.packet_approved,
        recipient=inputs.recipient,
        generated_on=inputs.generated_on,
    )
