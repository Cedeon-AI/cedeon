"""Loss imports (CSV → column mapping → validation → commit) and the loss
events those committed losses roll up into. No AI anywhere in this module."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.dependencies.context import (
    AuthedContext,
    LossEventServiceDep,
    LossImportServiceDep,
)
from app.api.schemas.losses import (
    CanonicalFieldList,
    CanonicalFieldOut,
    ColumnMappingIn,
    CommitImportIn,
    CommitResultOut,
    ImportReportOut,
    ImportRowOut,
    LossEventCreate,
    LossEventCurrencyTotal,
    LossEventDetail,
    LossEventList,
    LossEventOut,
    LossImportDetail,
    LossImportList,
    LossImportOut,
    RowIssueOut,
    UnderlyingLossOut,
)
from app.db.models.losses import LossEvent, LossImport, LossImportRow, UnderlyingLoss
from app.domain.losses import FIELD_SPECS

imports_router = APIRouter(prefix="/loss-imports", tags=["loss-imports"])
events_router = APIRouter(prefix="/loss-events", tags=["loss-events"])

_ROW_SAMPLE_LIMIT = 500


def _report_out(report: dict | None) -> ImportReportOut | None:
    if report is None:
        return None
    return ImportReportOut(
        total_rows=report["total_rows"],
        ok=report["ok"],
        warnings=report["warnings"],
        errors=report["errors"],
        committable=report["committable"],
        currencies=report["currencies"],
        distinct_events=report["distinct_events"],
        gross_incurred_by_currency=report["gross_incurred_by_currency"],
        issues=[
            RowIssueOut(
                row_number=i["row_number"],
                level=i["level"],
                field=i["field"],
                message=i["message"],
            )
            for i in report["issues"]
        ],
    )


def _import_out(loss_import: LossImport) -> LossImportOut:
    return LossImportOut(
        id=loss_import.id,
        original_filename=loss_import.original_filename,
        content_type=loss_import.content_type,
        row_count=loss_import.row_count,
        status=loss_import.status,
        header_columns=list(loss_import.header_columns),
        column_mapping=dict(loss_import.column_mapping),
        report=_report_out(loss_import.report),
        created_at=loss_import.created_at,
        committed_at=loss_import.committed_at,
    )


def _row_out(row: LossImportRow) -> ImportRowOut:
    return ImportRowOut(
        row_number=row.row_number,
        status=row.status,
        raw=dict(row.raw),
        parsed=dict(row.parsed) if row.parsed is not None else None,
        issues=[
            RowIssueOut(
                row_number=i["row_number"],
                level=i["level"],
                field=i["field"],
                message=i["message"],
            )
            for i in row.issues
        ],
    )


def _event_out(
    event: LossEvent, totals: dict[str, tuple[int, Decimal]] | None = None
) -> LossEventOut:
    totals = totals or {}
    return LossEventOut(
        id=event.id,
        name=event.name,
        event_identifier=event.event_identifier,
        catastrophe_code=event.catastrophe_code,
        currency=event.currency,
        date_of_loss_from=event.date_of_loss_from,
        date_of_loss_to=event.date_of_loss_to,
        description=event.description,
        peril=event.peril,
        hours_clause_hours=event.hours_clause_hours,
        created_at=event.created_at,
        totals=[
            LossEventCurrencyTotal(
                currency=currency,
                claim_count=count,
                gross_incurred=str(incurred),
            )
            for currency, (count, incurred) in sorted(totals.items())
        ],
    )


def _loss_out(loss: UnderlyingLoss) -> UnderlyingLossOut:
    return UnderlyingLossOut(
        id=loss.id,
        claim_id=loss.claim_id,
        date_of_loss=loss.date_of_loss,
        reported_date=loss.reported_date,
        gross_incurred=loss.gross_incurred,
        gross_paid=loss.gross_paid,
        gross_case_reserve=loss.gross_case_reserve,
        currency=loss.currency,
        status=loss.status,
        cause_of_loss=loss.cause_of_loss,
        location=loss.location,
        description=loss.description,
        loss_import_id=loss.loss_import_id,
    )


# --- loss imports -------------------------------------------------


@imports_router.get(
    "/fields",
    response_model=CanonicalFieldList,
    summary="The canonical loss fields a CSV column can map onto",
    operation_id="listLossFields",
)
async def list_loss_fields() -> CanonicalFieldList:
    return CanonicalFieldList(
        fields=[
            CanonicalFieldOut(
                field=spec.field.value,
                label=spec.label,
                kind=spec.kind,
                required=spec.required,
                hint=spec.hint,
            )
            for spec in FIELD_SPECS
        ]
    )


@imports_router.post(
    "",
    response_model=LossImportOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a loss CSV; the raw file and every row are kept",
    operation_id="uploadLossImport",
)
async def upload_loss_import(
    context: AuthedContext,
    service: LossImportServiceDep,
    file: Annotated[UploadFile, File()],
) -> LossImportOut:
    data = await file.read()
    loss_import = await service.upload(
        context,
        filename=file.filename or "losses.csv",
        content_type=file.content_type or "text/csv",
        data=data,
    )
    return _import_out(loss_import)


@imports_router.get("", response_model=LossImportList, operation_id="listLossImports")
async def list_loss_imports(
    context: AuthedContext, service: LossImportServiceDep
) -> LossImportList:
    imports = await service.list_imports(context)
    return LossImportList(imports=[_import_out(i) for i in imports])


@imports_router.get("/{import_id}", response_model=LossImportDetail, operation_id="getLossImport")
async def get_loss_import(
    import_id: UUID, context: AuthedContext, service: LossImportServiceDep
) -> LossImportDetail:
    loss_import, rows = await service.get_import(context, import_id)
    return LossImportDetail(
        loss_import=_import_out(loss_import),
        rows=[_row_out(r) for r in rows[:_ROW_SAMPLE_LIMIT]],
    )


@imports_router.post(
    "/{import_id}/mapping",
    response_model=LossImportDetail,
    summary="Set the column mapping and re-run validation",
    operation_id="setLossImportMapping",
)
async def set_loss_import_mapping(
    import_id: UUID,
    payload: ColumnMappingIn,
    context: AuthedContext,
    service: LossImportServiceDep,
) -> LossImportDetail:
    await service.set_mapping(context, import_id, payload.mapping)
    loss_import, rows = await service.get_import(context, import_id)
    return LossImportDetail(
        loss_import=_import_out(loss_import),
        rows=[_row_out(r) for r in rows[:_ROW_SAMPLE_LIMIT]],
    )


@imports_router.post(
    "/{import_id}/commit",
    response_model=CommitResultOut,
    summary="Commit valid rows to immutable underlying losses, grouped into events",
    operation_id="commitLossImport",
)
async def commit_loss_import(
    import_id: UUID,
    payload: CommitImportIn,
    context: AuthedContext,
    service: LossImportServiceDep,
) -> CommitResultOut:
    result = await service.commit(
        context,
        import_id,
        loss_event_id=payload.loss_event_id,
        default_event_name=payload.event_name,
    )
    return CommitResultOut(
        committed=result.committed,
        skipped=result.skipped,
        events_created=result.events_created,
        loss_event_ids=result.loss_event_ids,
        recoveries_drifted=result.recoveries_drifted,
    )


@imports_router.get(
    "/{import_id}/content",
    summary="Stream the original uploaded CSV (auth-checked)",
    operation_id="getLossImportContent",
    response_class=StreamingResponse,
)
async def get_loss_import_content(
    import_id: UUID, context: AuthedContext, service: LossImportServiceDep
) -> StreamingResponse:
    loss_import, stream = await service.stream_content(context, import_id)
    return StreamingResponse(
        stream,
        media_type=loss_import.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{loss_import.original_filename}"',
            "Cache-Control": "private, no-store",
        },
    )


# --- loss events -------------------------------------------------


@events_router.get("", response_model=LossEventList, operation_id="listLossEvents")
async def list_loss_events(context: AuthedContext, service: LossEventServiceDep) -> LossEventList:
    events, aggregates = await service.list_events(context)
    return LossEventList(events=[_event_out(e, aggregates.get(e.id)) for e in events])


@events_router.post(
    "",
    response_model=LossEventOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="createLossEvent",
)
async def create_loss_event(
    payload: LossEventCreate, context: AuthedContext, service: LossEventServiceDep
) -> LossEventOut:
    event = await service.create_event(
        context,
        name=payload.name,
        catastrophe_code=payload.catastrophe_code,
        description=payload.description,
        peril=payload.peril,
        hours_clause_hours=payload.hours_clause_hours,
    )
    return _event_out(event)


@events_router.get("/{event_id}", response_model=LossEventDetail, operation_id="getLossEvent")
async def get_loss_event(
    event_id: UUID, context: AuthedContext, service: LossEventServiceDep
) -> LossEventDetail:
    event, losses = await service.get_event(context, event_id)
    totals: dict[str, tuple[int, Decimal]] = {}
    for loss in losses:
        count, incurred = totals.get(loss.currency, (0, Decimal("0")))
        totals[loss.currency] = (count + 1, incurred + loss.gross_incurred)
    return LossEventDetail(
        event=_event_out(event, totals),
        losses=[_loss_out(loss) for loss in losses],
    )
