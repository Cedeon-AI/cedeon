"""Recovery domain: the deterministic calculation engine and its result types.

DO NOT USE AI IN THIS PACKAGE. Pure functions, `Decimal` money, versioned,
exhaustively tested (docs/DECISIONS.md ADR-0010)."""

from app.domain.recoveries.calculations import (
    ENGINE_VERSION,
    ParticipantAllocation,
    Participation,
    RecoveryCalculation,
    XolRecoveryResult,
    allocate_recovery,
    calculate_recovery,
    calculate_xol_recovery,
)
from app.domain.recoveries.candidate import RecoveryCandidateStatus, recovery_input_hash
from app.domain.recoveries.notice import (
    NoticeContext,
    NoticeInputs,
    NoticeKind,
    NoticeParticipant,
    NoticeRecipient,
    NoticeStatus,
    build_notice_context,
)
from app.domain.recoveries.packet import (
    PacketContent,
    PacketInputs,
    PacketStatementClass,
    PacketVersionStatus,
    assemble_packet,
)
from app.domain.recoveries.packet_html import render_packet_html

__all__ = [
    "ENGINE_VERSION",
    "NoticeContext",
    "NoticeInputs",
    "NoticeKind",
    "NoticeParticipant",
    "NoticeRecipient",
    "NoticeStatus",
    "PacketContent",
    "PacketInputs",
    "PacketStatementClass",
    "PacketVersionStatus",
    "ParticipantAllocation",
    "Participation",
    "RecoveryCalculation",
    "RecoveryCandidateStatus",
    "XolRecoveryResult",
    "allocate_recovery",
    "assemble_packet",
    "build_notice_context",
    "calculate_recovery",
    "calculate_xol_recovery",
    "recovery_input_hash",
    "render_packet_html",
]
