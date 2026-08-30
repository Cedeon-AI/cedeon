"""Reference data (cedents, reinsurers) and reinsurance programs."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.dependencies.context import AuthedContext, DbSession
from app.api.schemas.reinsurance import (
    CedentCreate,
    CedentList,
    CedentOut,
    ProgramCreate,
    ProgramList,
    ProgramOut,
    ReinsurerCreate,
    ReinsurerList,
    ReinsurerOut,
)
from app.db.models.reinsurance import ReinsuranceProgram
from app.services.reinsurance import ProgramService, ReferenceDataService

router = APIRouter(tags=["reinsurance"])


@router.get("/cedents", response_model=CedentList, operation_id="listCedents")
async def list_cedents(context: AuthedContext, session: DbSession) -> CedentList:
    cedents = await ReferenceDataService(session).list_cedents(context)
    return CedentList(cedents=[CedentOut(id=c.id, name=c.name) for c in cedents])


@router.post(
    "/cedents",
    response_model=CedentOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="createCedent",
)
async def create_cedent(
    payload: CedentCreate, context: AuthedContext, session: DbSession
) -> CedentOut:
    cedent = await ReferenceDataService(session).create_cedent(context, name=payload.name)
    return CedentOut(id=cedent.id, name=cedent.name)


@router.get("/reinsurers", response_model=ReinsurerList, operation_id="listReinsurers")
async def list_reinsurers(context: AuthedContext, session: DbSession) -> ReinsurerList:
    reinsurers = await ReferenceDataService(session).list_reinsurers(context)
    return ReinsurerList(reinsurers=[ReinsurerOut(id=r.id, name=r.name) for r in reinsurers])


@router.post(
    "/reinsurers",
    response_model=ReinsurerOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="createReinsurer",
)
async def create_reinsurer(
    payload: ReinsurerCreate, context: AuthedContext, session: DbSession
) -> ReinsurerOut:
    reinsurer = await ReferenceDataService(session).create_reinsurer(context, name=payload.name)
    return ReinsurerOut(id=reinsurer.id, name=reinsurer.name)


def _program_out(program: ReinsuranceProgram, treaty_count: int) -> ProgramOut:
    return ProgramOut(
        id=program.id,
        name=program.name,
        treaty_year=program.treaty_year,
        description=program.description,
        cedent_id=program.cedent_id,
        cedent_name=program.cedent.name,
        treaty_count=treaty_count,
    )


@router.get("/programs", response_model=ProgramList, operation_id="listPrograms")
async def list_programs(context: AuthedContext, session: DbSession) -> ProgramList:
    programs, counts = await ProgramService(session).list_programs(context)
    return ProgramList(programs=[_program_out(p, counts.get(p.id, 0)) for p in programs])


@router.post(
    "/programs",
    response_model=ProgramOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="createProgram",
)
async def create_program(
    payload: ProgramCreate, context: AuthedContext, session: DbSession
) -> ProgramOut:
    program = await ProgramService(session).create_program(
        context,
        cedent_id=payload.cedent_id,
        name=payload.name,
        treaty_year=payload.treaty_year,
        description=payload.description,
    )
    return _program_out(program, 0)
