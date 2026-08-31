"""Loss import use-cases: upload CSV → map columns → validate → commit to
immutable underlying_losses, grouped into loss events."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_correlation_id
from app.db.models.losses import (
    LossEvent,
    LossImport,
    LossImportRow,
    UnderlyingLoss,
)
from app.domain.audit import ActorType, AuditRecord
from app.domain.losses import (
    CANONICAL_FIELDS,
    CanonicalField,
    LossImportStatus,
    LossRowStatus,
    validate_rows,
)
from app.repositories.audit import AuditRepository
from app.repositories.losses import (
    LossEventRepository,
    LossImportRepository,
    UnderlyingLossRepository,
)
from app.services.auth import AuthenticatedContext
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.recoveries import RecoveryCandidateService
from app.storage.base import ObjectNotFoundError, ObjectStore

_MAX_ROWS = 100_000


@dataclass(slots=True)
class CommitResult:
    committed: int
    skipped: int
    events_created: int
    loss_event_ids: list[UUID]
    recoveries_drifted: int = 0


class LossImportService:
    def __init__(
        self,
        session: AsyncSession,
        store: ObjectStore,
        *,
        max_upload_bytes: int,
    ) -> None:
        self._session = session
        self._store = store
        self._max_upload_bytes = max_upload_bytes
        self._imports = LossImportRepository(session)
        self._events = LossEventRepository(session)
        self._losses = UnderlyingLossRepository(session)
        self._audit = AuditRepository(session)

    # --- upload ------------------------------------------------------

    async def upload(
        self,
        context: AuthenticatedContext,
        *,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> LossImport:
        if not data:
            raise ValidationError("the uploaded file is empty")
        if len(data) > self._max_upload_bytes:
            raise ValidationError(
                f"file exceeds the {self._max_upload_bytes // (1024 * 1024)} MB limit"
            )

        header, rows = _parse_csv(data)
        if not header:
            raise ValidationError("the CSV has no header row")
        if not rows:
            raise ValidationError("the CSV has a header but no data rows")
        if len(rows) > _MAX_ROWS:
            raise ValidationError(f"at most {_MAX_ROWS:,} rows per import")

        org_id = context.organization.id
        sha256 = hashlib.sha256(data).hexdigest()
        existing = await self._imports.get_by_sha256(org_id, sha256)
        if existing is not None:
            return existing

        loss_import = LossImport(
            organization_id=org_id,
            original_filename=filename[:500],
            content_type=content_type or "text/csv",
            storage_key="",
            sha256=sha256,
            row_count=len(rows),
            header_columns=header,
            status=LossImportStatus.UPLOADED,
            uploaded_by=context.user.id,
        )
        self._imports.add(loss_import)
        await self._session.flush()

        loss_import.storage_key = f"org/{org_id}/loss-imports/{loss_import.id}/{sha256}"
        await self._store.put(loss_import.storage_key, data, content_type=loss_import.content_type)

        for index, raw in enumerate(rows):
            self._imports.add(
                LossImportRow(
                    organization_id=org_id,
                    loss_import_id=loss_import.id,
                    row_number=index + 1,
                    raw=raw,
                    status=LossRowStatus.OK,
                )
            )

        self._audit.record(
            AuditRecord(
                organization_id=org_id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="loss_import.uploaded",
                entity_type="loss_import",
                entity_id=loss_import.id,
                summary=f"{context.user.email} uploaded {filename!r} ({len(rows)} rows)",
                payload={"rows": len(rows), "columns": header},
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        return loss_import

    # --- mapping + validation --------------------------------------

    async def set_mapping(
        self,
        context: AuthenticatedContext,
        import_id: UUID,
        mapping_in: dict[str, str],
    ) -> LossImport:
        loss_import = await self._require_import(context, import_id)
        if loss_import.status is LossImportStatus.COMMITTED:
            raise ConflictError("this import is already committed")

        mapping = _clean_mapping(mapping_in, loss_import.header_columns)

        rows = await self._imports.rows(import_id)
        raw_rows = [row.raw for row in rows]
        validated, report = validate_rows(raw_rows, mapping)

        by_number = {row.row_number: row for row in rows}
        for vr in validated:
            row = by_number[vr.row_number]
            row.parsed = vr.parsed
            row.status = LossRowStatus(vr.status)
            row.issues = [
                {
                    "row_number": i.row_number,
                    "level": i.level,
                    "field": i.field,
                    "message": i.message,
                }
                for i in vr.issues
            ]

        loss_import.column_mapping = {k.value: v for k, v in mapping.items()}
        loss_import.report = report.to_dict()
        loss_import.status = LossImportStatus.VALIDATED

        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="loss_import.mapped",
                entity_type="loss_import",
                entity_id=loss_import.id,
                summary=(
                    f"{context.user.email} mapped columns — "
                    f"{report.committable} of {report.total_rows} rows valid"
                ),
                payload={"committable": report.committable, "errors": report.errors},
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        return loss_import

    # --- commit -----------------------------------------------------

    async def commit(
        self,
        context: AuthenticatedContext,
        import_id: UUID,
        *,
        loss_event_id: UUID | None = None,
        default_event_name: str | None = None,
    ) -> CommitResult:
        loss_import = await self._require_import(context, import_id)
        if loss_import.status is LossImportStatus.COMMITTED:
            raise ConflictError("this import is already committed")
        if loss_import.status is not LossImportStatus.VALIDATED:
            raise ConflictError("map the columns and validate before committing")

        org_id = context.organization.id
        target_event: LossEvent | None = None
        if loss_event_id is not None:
            target_event = await self._events.get(org_id, loss_event_id)
            if target_event is None:
                raise NotFoundError("loss event not found")

        rows = await self._imports.rows(import_id)
        committable = [r for r in rows if r.status in (LossRowStatus.OK, LossRowStatus.WARNING)]
        skipped = len(rows) - len(committable)

        distinct_identifiers = {
            i for r in committable if (i := (r.parsed or {}).get("loss_event_identifier"))
        }
        # A caller-supplied name only makes sense when the whole import lands in one event.
        naming_hint = default_event_name if len(distinct_identifiers) == 1 else None

        events_by_identifier: dict[str, LossEvent] = {}
        events_created = 0

        for row in committable:
            parsed = row.parsed or {}
            event = target_event
            if event is None:
                identifier = parsed.get("loss_event_identifier")
                if identifier:
                    event = events_by_identifier.get(identifier)
                    if event is None:
                        event = await self._events.get_by_identifier(org_id, identifier)
                    if event is None:
                        event = LossEvent(
                            organization_id=org_id,
                            name=naming_hint or identifier,
                            event_identifier=identifier,
                        )
                        self._events.add(event)
                        events_created += 1
                    events_by_identifier[identifier] = event

            self._losses.add(
                UnderlyingLoss(
                    organization_id=org_id,
                    loss_event=event,
                    loss_import_id=loss_import.id,
                    loss_import_row_id=row.id,
                    claim_id=str(parsed["claim_id"]),
                    date_of_loss=dt.date.fromisoformat(parsed["date_of_loss"]),
                    reported_date=(
                        dt.date.fromisoformat(parsed["reported_date"])
                        if parsed.get("reported_date")
                        else None
                    ),
                    gross_incurred=Decimal(parsed["gross_incurred"]),
                    gross_paid=(
                        Decimal(parsed["gross_paid"]) if parsed.get("gross_paid") else None
                    ),
                    gross_case_reserve=(
                        Decimal(parsed["gross_case_reserve"])
                        if parsed.get("gross_case_reserve")
                        else None
                    ),
                    currency=parsed["currency"],
                    status=parsed.get("status"),
                    cause_of_loss=parsed.get("cause_of_loss"),
                    location=parsed.get("location"),
                    description=parsed.get("description"),
                )
            )

        await self._session.flush()

        touched = list(events_by_identifier.values())
        if target_event is not None:
            touched.append(target_event)
        for event in touched:
            await self._recompute_event(org_id, event)

        loss_import.status = LossImportStatus.COMMITTED
        loss_import.committed_at = dt.datetime.now(dt.UTC)

        event_ids = [e.id for e in touched]

        # A claims import can move a recovery figure. Recompute every recovery on
        # the touched events; a figure that moves without a human is drift.
        drifted = await RecoveryCandidateService(self._session).recalculate_for_events(
            context, set(event_ids)
        )
        self._audit.record(
            AuditRecord(
                organization_id=org_id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="loss_import.committed",
                entity_type="loss_import",
                entity_id=loss_import.id,
                summary=(
                    f"{context.user.email} committed {len(committable)} losses "
                    f"({skipped} skipped) into {len(event_ids)} event(s)"
                ),
                payload={
                    "committed": len(committable),
                    "skipped": skipped,
                    "loss_event_ids": [str(i) for i in event_ids],
                },
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        return CommitResult(
            committed=len(committable),
            skipped=skipped,
            events_created=events_created,
            loss_event_ids=event_ids,
            recoveries_drifted=len(drifted),
        )

    # --- reading --------------------------------------------------

    async def list_imports(self, context: AuthenticatedContext) -> list[LossImport]:
        return await self._imports.list_for_org(context.organization.id)

    async def get_import(
        self, context: AuthenticatedContext, import_id: UUID
    ) -> tuple[LossImport, list[LossImportRow]]:
        loss_import = await self._require_import(context, import_id)
        rows = await self._imports.rows(import_id)
        return loss_import, rows

    async def stream_content(
        self, context: AuthenticatedContext, import_id: UUID
    ) -> tuple[LossImport, AsyncIterator[bytes]]:
        loss_import = await self._require_import(context, import_id)
        try:
            return loss_import, self._store.stream(loss_import.storage_key)
        except ObjectNotFoundError as exc:
            raise NotFoundError("import file is missing from storage") from exc

    # --- helpers ------------------------------------------------

    async def _require_import(self, context: AuthenticatedContext, import_id: UUID) -> LossImport:
        loss_import = await self._imports.get(context.organization.id, import_id)
        if loss_import is None:
            raise NotFoundError("loss import not found")
        return loss_import

    async def _recompute_event(self, organization_id: UUID, event: LossEvent) -> None:
        losses = await self._losses.for_event(organization_id, event.id)
        if not losses:
            return
        dates = [loss_row.date_of_loss for loss_row in losses]
        event.date_of_loss_from = min(dates)
        event.date_of_loss_to = max(dates)
        currencies = {loss_row.currency for loss_row in losses}
        event.currency = next(iter(currencies)) if len(currencies) == 1 else None


class LossEventService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._events = LossEventRepository(session)
        self._losses = UnderlyingLossRepository(session)
        self._audit = AuditRepository(session)

    async def list_events(
        self, context: AuthenticatedContext
    ) -> tuple[list[LossEvent], dict[UUID, dict[str, tuple[int, Decimal]]]]:
        events = await self._events.list_for_org(context.organization.id)
        aggregates = await self._events.aggregates(context.organization.id)
        return events, aggregates

    async def get_event(
        self, context: AuthenticatedContext, event_id: UUID
    ) -> tuple[LossEvent, list[UnderlyingLoss]]:
        event = await self._events.get(context.organization.id, event_id)
        if event is None:
            raise NotFoundError("loss event not found")
        losses = await self._losses.for_event(context.organization.id, event_id)
        return event, losses

    async def create_event(
        self,
        context: AuthenticatedContext,
        *,
        name: str,
        catastrophe_code: str | None = None,
        description: str | None = None,
        peril: str | None = None,
        hours_clause_hours: int | None = None,
    ) -> LossEvent:
        name = name.strip()
        if not name:
            raise ValidationError("loss event name is required")
        event = LossEvent(
            organization_id=context.organization.id,
            name=name,
            catastrophe_code=catastrophe_code or None,
            description=description or None,
            peril=(peril or "").strip() or None,
            hours_clause_hours=hours_clause_hours,
        )
        self._events.add(event)
        await self._session.flush()
        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="loss_event.created",
                entity_type="loss_event",
                entity_id=event.id,
                summary=f"{context.user.email} created loss event {name!r}",
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        return event


def _parse_csv(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    header = [h.strip() for h in (reader.fieldnames or []) if h and h.strip()]
    rows: list[dict[str, str]] = []
    for raw in reader:
        rows.append(
            {
                (k.strip() if k else ""): ("" if v is None else str(v).strip())
                for k, v in raw.items()
                if k
            }
        )
    return header, rows


def _clean_mapping(
    mapping_in: dict[str, str], header_columns: list[str]
) -> dict[CanonicalField, str]:
    valid_fields = {f.value: f for f in CANONICAL_FIELDS}
    headers = set(header_columns)
    cleaned: dict[CanonicalField, str] = {}
    for key, column in mapping_in.items():
        if not column:
            continue
        field = valid_fields.get(key)
        if field is None:
            raise ValidationError(f"unknown canonical field {key!r}")
        if column not in headers:
            raise ValidationError(f"column {column!r} is not in the CSV header")
        cleaned[field] = column
    return cleaned
