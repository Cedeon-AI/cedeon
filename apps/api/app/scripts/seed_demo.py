"""Seed a synthetic demo organization with the full golden desk already populated:
a validated treaty, a committed loss event, a confirmed recovery with its
deterministic calculation and allocations, and three recoverables — one of them
overdue — plus a computed notice deadline.

Clearly-synthetic data only. No AI is involved: the treaty is written directly in
its validated state and every figure comes from the deterministic engine, exactly
as it would if a human had walked the wizard.

Idempotent: re-running detects the demo org and does nothing.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.passwords import hash_password
from app.db.models.identity import Membership, Organization, User
from app.db.models.losses import LossEvent, LossImport, LossImportRow, UnderlyingLoss
from app.db.models.recoveries import (
    Recoverable,
    RecoveryAllocation,
    RecoveryCalculation,
    RecoveryCandidate,
)
from app.db.models.reinsurance import (
    Cedent,
    ReinsuranceProgram,
    Reinsurer,
    Treaty,
    TreatyLayer,
    TreatyParticipation,
    TreatyTerm,
    TreatyVersion,
)
from app.db.session import dispose_engine, get_sessionmaker, init_engine
from app.domain.losses import LossImportStatus, LossRowStatus
from app.domain.money import Money
from app.domain.organizations import Role
from app.domain.recoveries import (
    ENGINE_VERSION,
    Participation,
    RecoverableStatus,
    RecoveryCandidateStatus,
    calculate_recovery,
)
from app.domain.treaties import TermStatus, TreatyType, TreatyVersionStatus

DEMO_ORG_NAME = "Demo Specialty Insurance Co."
DEMO_EMAIL = "founder@demo-specialty.example"
DEMO_USER_NAME = "Demo Founder"
DEMO_PASSWORD = "cedeon-demo-password"  # noqa: S105 - synthetic local demo credential

# 10 hurricane claims → USD 58,700,000.00 gross (the golden number).
_CLAIMS: tuple[tuple[str, str, str, str], ...] = (
    ("CLM-001", "2027-09-14", "15000000.00", "Miami-Dade, FL"),
    ("CLM-002", "2027-09-14", "10500000.00", "Broward, FL"),
    ("CLM-003", "2027-09-14", "6000000.00", "Collier, FL"),
    ("CLM-004", "2027-09-15", "5000000.00", "Lee, FL"),
    ("CLM-005", "2027-09-15", "3500000.00", "Charlotte, FL"),
    ("CLM-006", "2027-09-15", "3200000.00", "Sarasota, FL"),
    ("CLM-007", "2027-09-15", "7500000.00", "Hillsborough, FL"),
    ("CLM-008", "2027-09-16", "2000000.00", "Pinellas, FL"),
    ("CLM-009", "2027-09-16", "1000000.00", "Pasco, FL"),
    ("CLM-010", "2027-09-16", "5000000.00", "Manatee, FL"),
)


async def _seed(session: AsyncSession) -> None:
    now = dt.datetime.now(dt.UTC)
    org = Organization(name=DEMO_ORG_NAME, slug="demo-specialty")
    user = User(email=DEMO_EMAIL, name=DEMO_USER_NAME, password_hash=hash_password(DEMO_PASSWORD))
    session.add_all([org, user])
    await session.flush()
    session.add(Membership(organization_id=org.id, user_id=user.id, role=Role.ADMIN))

    cedent = Cedent(organization_id=org.id, name="Demo Specialty Insurance Co.")
    session.add(cedent)
    await session.flush()
    program = ReinsuranceProgram(
        organization_id=org.id,
        cedent_id=cedent.id,
        name="2027 Property Cat Program",
        treaty_year=2027,
    )
    session.add(program)
    reinsurers = {
        name: Reinsurer(organization_id=org.id, name=name)
        for name in ("Reinsurer Alpha", "Reinsurer Beta", "Reinsurer Gamma")
    }
    session.add_all(reinsurers.values())
    await session.flush()

    # --- the validated treaty (no extraction — written straight to executable) ---
    treaty = Treaty(
        organization_id=org.id,
        program_id=program.id,
        name="2027 Property Cat XOL",
        treaty_type=TreatyType.PER_OCCURRENCE_XOL,
    )
    session.add(treaty)
    await session.flush()
    version = TreatyVersion(
        organization_id=org.id,
        treaty_id=treaty.id,
        version_no=1,
        status=TreatyVersionStatus.VALIDATED,
        currency="USD",
        effective_date=dt.date(2027, 1, 1),
        expiration_date=dt.date(2027, 12, 31),
        validated_at=now,
        validated_by=user.id,
    )
    session.add(version)
    await session.flush()
    treaty.current_version_id = version.id
    layer = TreatyLayer(
        organization_id=org.id,
        treaty_version_id=version.id,
        layer_no=1,
        attachment=Decimal("50000000.00"),
        limit=Decimal("20000000.00"),
        currency="USD",
    )
    session.add(layer)
    await session.flush()
    shares = {
        "Reinsurer Alpha": "0.500000",
        "Reinsurer Beta": "0.300000",
        "Reinsurer Gamma": "0.200000",
    }
    for name, share in shares.items():
        session.add(
            TreatyParticipation(
                organization_id=org.id,
                treaty_version_id=version.id,
                reinsurer_id=reinsurers[name].id,
                placed_share=Decimal(share),
            )
        )
    session.add(
        TreatyTerm(
            organization_id=org.id,
            treaty_version_id=version.id,
            key="notice_provision",
            status=TermStatus.CONFIRMED,
            value={
                "value": "Notice within 30 days of the cedent's knowledge of a loss likely "
                "to involve the reinsurers.",
                "days": 30,
                "trigger": "knowledge_of_loss",
                "basis": "calendar",
            },
        )
    )
    session.add(
        TreatyTerm(
            organization_id=org.id,
            treaty_version_id=version.id,
            key="covered_perils",
            status=TermStatus.CONFIRMED,
            value={"value": "Windstorm, flood and related perils"},
        )
    )

    # --- the loss event + committed claims ---
    csv_bytes = b"synthetic-demo-claims"
    loss_import = LossImport(
        organization_id=org.id,
        original_filename="hurricane-demo-2027-claims.csv",
        content_type="text/csv",
        storage_key="seed/hurricane-demo-2027-claims.csv",
        sha256=hashlib.sha256(csv_bytes).hexdigest(),
        row_count=len(_CLAIMS),
        header_columns=["Claim Ref", "Loss Date", "Incurred", "Location"],
        column_mapping={
            "claim_id": "Claim Ref",
            "date_of_loss": "Loss Date",
            "gross_incurred": "Incurred",
            "location": "Location",
        },
        status=LossImportStatus.COMMITTED,
        committed_at=now,
        uploaded_by=user.id,
        report={"total_rows": len(_CLAIMS), "ok": len(_CLAIMS), "errors": 0},
    )
    session.add(loss_import)
    await session.flush()
    event = LossEvent(
        organization_id=org.id,
        program_id=program.id,
        name="Hurricane Demo 2027",
        event_identifier="HURR-DEMO-2027",
        catastrophe_code="PCS 2027-42",
        currency="USD",
        date_of_loss_from=dt.date(2027, 9, 14),
        date_of_loss_to=dt.date(2027, 9, 16),
        peril="Named windstorm",
        hours_clause_hours=168,
    )
    session.add(event)
    await session.flush()
    for i, (claim_id, dol, incurred, location) in enumerate(_CLAIMS, start=1):
        row = LossImportRow(
            organization_id=org.id,
            loss_import_id=loss_import.id,
            row_number=i,
            raw={
                "Claim Ref": claim_id,
                "Loss Date": dol,
                "Incurred": incurred,
                "Location": location,
            },
            parsed={"claim_id": claim_id, "date_of_loss": dol, "gross_incurred": incurred},
            status=LossRowStatus.OK,
        )
        session.add(row)
        await session.flush()
        session.add(
            UnderlyingLoss(
                organization_id=org.id,
                loss_event_id=event.id,
                loss_import_id=loss_import.id,
                loss_import_row_id=row.id,
                claim_id=claim_id,
                date_of_loss=dt.date.fromisoformat(dol),
                gross_incurred=Decimal(incurred),
                currency="USD",
                cause_of_loss="Wind",
                location=location,
            )
        )

    # --- the recovery: deterministic engine, confirmed ---
    participations = [
        Participation(key=str(reinsurers[n].id), label=n, share=Decimal(s))
        for n, s in shares.items()
    ]
    result = calculate_recovery(
        gross_loss=Money(Decimal("58700000.00"), "USD"),
        attachment=Money(Decimal("50000000.00"), "USD"),
        limit=Money(Decimal("20000000.00"), "USD"),
        participations=participations,
    )
    candidate = RecoveryCandidate(
        organization_id=org.id,
        treaty_id=treaty.id,
        treaty_version_id=version.id,
        treaty_layer_id=layer.id,
        loss_event_id=event.id,
        status=RecoveryCandidateStatus.CONFIRMED,
        currency="USD",
        gross_event_incurred=Decimal("58700000.00"),
        currency_mismatch=False,
        created_by=user.id,
        reviewed_at=now,
        reviewed_by=user.id,
        knowledge_date=dt.date(2027, 9, 18),
    )
    session.add(candidate)
    await session.flush()
    calc = RecoveryCalculation(
        organization_id=org.id,
        recovery_candidate_id=candidate.id,
        engine_version=ENGINE_VERSION,
        treaty_version_id=version.id,
        treaty_layer_id=layer.id,
        currency="USD",
        inputs={
            "gross_loss": "58700000.00",
            "attachment": "50000000.00",
            "limit": "20000000.00",
            "participations": [
                {"reinsurer_id": p.key, "reinsurer_name": p.label, "share": str(p.share)}
                for p in participations
            ],
        },
        gross_loss=result.xol.gross_loss.amount,
        attachment=result.xol.attachment.amount,
        amount_above_attachment=result.xol.amount_above_attachment.amount,
        layer_limit=result.xol.limit.amount,
        layer_recovery=result.xol.layer_recovery.amount,
        cedent_retention=result.cedent_retention.amount,
        total_ceded=result.total_ceded.amount,
        trace=[
            {"label": s.label, "expression": s.expression, "result": s.result}
            for s in result.xol.trace
        ],
        input_hash="seed-" + hashlib.sha256(b"golden").hexdigest()[:56],
    )
    session.add(calc)
    await session.flush()
    candidate.current_calculation_id = calc.id
    for alloc in result.allocations:
        session.add(
            RecoveryAllocation(
                organization_id=org.id,
                recovery_calculation_id=calc.id,
                reinsurer_id=uuid.UUID(alloc.key),
                participation_share=alloc.share,
                allocated_recovery=alloc.amount.amount,
            )
        )

    # --- recoverables: one notified, one overdue, one collected ---
    legs = [
        ("Reinsurer Alpha", RecoverableStatus.NOTIFIED, now - dt.timedelta(days=10), None),
        (
            "Reinsurer Beta",
            RecoverableStatus.BILLED,
            now - dt.timedelta(days=75),
            dt.date.today() - dt.timedelta(days=20),
        ),  # overdue
        ("Reinsurer Gamma", RecoverableStatus.COLLECTED, now - dt.timedelta(days=40), None),
    ]
    by_name = {a.label: a for a in result.allocations}
    for name, status, stamp, due in legs:
        amount = by_name[name].amount.amount
        session.add(
            Recoverable(
                organization_id=org.id,
                recovery_candidate_id=candidate.id,
                recovery_calculation_id=calc.id,
                reinsurer_id=reinsurers[name].id,
                currency="USD",
                status=status,
                expected_amount=amount,
                collected_amount=amount if status is RecoverableStatus.COLLECTED else Decimal("0"),
                due_date=due,
                notified_at=stamp,
                settled_at=stamp if status is RecoverableStatus.COLLECTED else None,
            )
        )

    await session.commit()


async def _run() -> None:
    init_engine()
    async with get_sessionmaker()() as session:
        existing = await session.execute(select(User).where(User.email == DEMO_EMAIL))
        if existing.scalar_one_or_none() is not None:
            print(f"demo organization already present — sign in as {DEMO_EMAIL}")
        else:
            await _seed(session)
            print(f"created {DEMO_ORG_NAME!r} with the golden desk populated")
            print(f"  sign in:  {DEMO_EMAIL}  /  {DEMO_PASSWORD}")
    await dispose_engine()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
