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

__all__ = [
    "ENGINE_VERSION",
    "ParticipantAllocation",
    "Participation",
    "RecoveryCalculation",
    "XolRecoveryResult",
    "allocate_recovery",
    "calculate_recovery",
    "calculate_xol_recovery",
]
