"""Reinsurer statements — reconcile a batch of reinsurer-stated figures against
what Cedeon holds."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies.context import AuthedContext, DbSession
from app.api.schemas.statements import (
    CreateStatementRequest,
    StatementFindingOut,
    StatementLineOut,
    StatementList,
    StatementOut,
    StatementSummary,
)
from app.db.models.recoveries import ReinsurerStatement, ReinsurerStatementLine
from app.services.errors import ValidationError
from app.services.statements import ReinsurerStatementService, StatementLineInput

router = APIRouter(prefix="/reinsurer-statements", tags=["reinsurer-statements"])


def _amount(raw: str | None, field: str) -> Decimal | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return Decimal(raw.replace(",", "").replace("$", "").strip())
    except InvalidOperation as exc:
        raise ValidationError(f"{field} is not a valid amount") from exc


def _line_out(line: ReinsurerStatementLine) -> StatementLineOut:
    return StatementLineOut(
        row_number=line.row_number,
        reinsurer_name=line.reinsurer_name,
        reference=line.reference,
        currency=line.currency,
        their_agreed=str(line.their_agreed) if line.their_agreed is not None else None,
        their_paid=str(line.their_paid) if line.their_paid is not None else None,
        matched_recoverable_id=line.matched_recoverable_id,
        findings=[
            StatementFindingOut(
                kind=f["kind"], text=f["text"], ours=f.get("ours"), theirs=f.get("theirs")
            )
            for f in line.findings
        ],
        resolved=line.resolved,
    )


def _open_discrepancies(statement: ReinsurerStatement) -> int:
    return sum(1 for x in statement.lines if not x.resolved)


def _statement_out(statement: ReinsurerStatement) -> StatementOut:
    return StatementOut(
        id=statement.id,
        label=statement.label,
        currency=statement.currency,
        statement_date=statement.statement_date,
        created_at=statement.created_at,
        line_count=len(statement.lines),
        open_discrepancies=_open_discrepancies(statement),
        lines=[_line_out(x) for x in statement.lines],
    )


@router.get("", response_model=StatementList, operation_id="listReinsurerStatements")
async def list_statements(context: AuthedContext, session: DbSession) -> StatementList:
    statements = await ReinsurerStatementService(session).list_statements(context)
    return StatementList(
        statements=[
            StatementSummary(
                id=s.id,
                label=s.label,
                currency=s.currency,
                statement_date=s.statement_date,
                created_at=s.created_at,
                line_count=len(s.lines),
                open_discrepancies=_open_discrepancies(s),
            )
            for s in statements
        ]
    )


@router.post(
    "",
    response_model=StatementOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a reinsurer's stated figures; Cedeon reconciles each line",
    operation_id="createReinsurerStatement",
)
async def create_statement(
    payload: CreateStatementRequest, context: AuthedContext, session: DbSession
) -> StatementOut:
    lines = [
        StatementLineInput(
            reinsurer_name=row.reinsurer_name,
            currency=row.currency or payload.currency,
            reference=row.reference,
            their_agreed=_amount(row.their_agreed, f"line {i} agreed"),
            their_paid=_amount(row.their_paid, f"line {i} paid"),
        )
        for i, row in enumerate(payload.lines, start=1)
    ]
    statement = await ReinsurerStatementService(session).create(
        context,
        label=payload.label,
        currency=payload.currency,
        statement_date=payload.statement_date,
        lines=lines,
    )
    return _statement_out(statement)


@router.get("/{statement_id}", response_model=StatementOut, operation_id="getReinsurerStatement")
async def get_statement(
    statement_id: UUID, context: AuthedContext, session: DbSession
) -> StatementOut:
    statement = await ReinsurerStatementService(session).get_statement(context, statement_id)
    return _statement_out(statement)


@router.post(
    "/{statement_id}/lines/{row_number}/resolve",
    response_model=StatementOut,
    summary="Mark one reconciled line as handled",
    operation_id="resolveStatementLine",
)
async def resolve_line(
    statement_id: UUID, row_number: int, context: AuthedContext, session: DbSession
) -> StatementOut:
    statement = await ReinsurerStatementService(session).resolve_line(
        context, statement_id, row_number
    )
    return _statement_out(statement)
