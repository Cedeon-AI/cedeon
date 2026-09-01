"""Reference-data + treaty use-cases (structural; extraction lives in app/ai)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_correlation_id
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
from app.domain.audit import ActorType, AuditRecord
from app.domain.documents import DocumentStatus
from app.domain.treaties import TreatyType, TreatyVersionStatus
from app.repositories.audit import AuditRepository
from app.repositories.documents import DocumentRepository
from app.repositories.reinsurance import (
    CedentRepository,
    ProgramRepository,
    ReinsurerRepository,
    TreatyRepository,
    TreatyVersionRepository,
)
from app.services.auth import AuthenticatedContext
from app.services.errors import ConflictError, NotFoundError, ValidationError


class ReferenceDataService:
    """Cedents and reinsurers — small org-scoped reference tables."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cedents = CedentRepository(session)
        self._reinsurers = ReinsurerRepository(session)
        self._audit = AuditRepository(session)

    async def list_cedents(self, context: AuthenticatedContext) -> list[Cedent]:
        return await self._cedents.list(context.organization.id)

    async def create_cedent(self, context: AuthenticatedContext, *, name: str) -> Cedent:
        name = name.strip()
        if not name:
            raise ValidationError("cedent name is required")
        if await self._cedents.get_by_name(context.organization.id, name):
            raise ConflictError("a cedent with that name already exists")
        cedent = Cedent(organization_id=context.organization.id, name=name)
        self._cedents.add(cedent)
        await self._commit(
            context, "cedent.created", "cedent", cedent.id, f"created cedent {name!r}"
        )
        return cedent

    async def list_reinsurers(self, context: AuthenticatedContext) -> list[Reinsurer]:
        return await self._reinsurers.list(context.organization.id)

    async def create_reinsurer(self, context: AuthenticatedContext, *, name: str) -> Reinsurer:
        name = name.strip()
        if not name:
            raise ValidationError("reinsurer name is required")
        if await self._reinsurers.get_by_name(context.organization.id, name):
            raise ConflictError("a reinsurer with that name already exists")
        reinsurer = Reinsurer(organization_id=context.organization.id, name=name)
        self._reinsurers.add(reinsurer)
        await self._commit(
            context, "reinsurer.created", "reinsurer", reinsurer.id, f"created reinsurer {name!r}"
        )
        return reinsurer

    async def get_or_create_reinsurer(
        self, context: AuthenticatedContext, *, name: str
    ) -> Reinsurer:
        existing = await self._reinsurers.get_by_name(context.organization.id, name.strip())
        if existing:
            return existing
        return await self.create_reinsurer(context, name=name)

    async def _commit(
        self,
        context: AuthenticatedContext,
        action: str,
        entity_type: str,
        entity_id: UUID,
        summary: str,
    ) -> None:
        await self._session.flush()
        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                summary=f"{context.user.email} {summary}",
                correlation_id=get_correlation_id(),
            )
        )
        try:
            await self._session.commit()
        except IntegrityError as exc:  # pragma: no cover - unique race
            await self._session.rollback()
            raise ConflictError("that record already exists") from exc


class ProgramService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._programs = ProgramRepository(session)
        self._cedents = CedentRepository(session)
        self._audit = AuditRepository(session)

    async def list_programs(
        self, context: AuthenticatedContext
    ) -> tuple[list[ReinsuranceProgram], dict[UUID, int]]:
        programs = await self._programs.list(context.organization.id)
        counts = await self._programs.treaty_counts(context.organization.id)
        return programs, counts

    async def create_program(
        self,
        context: AuthenticatedContext,
        *,
        cedent_id: UUID,
        name: str,
        treaty_year: int,
        description: str | None,
    ) -> ReinsuranceProgram:
        name = name.strip()
        if not name:
            raise ValidationError("program name is required")
        if not (1900 <= treaty_year <= 2100):
            raise ValidationError("treaty_year is out of range")
        cedent = await self._cedents.get(context.organization.id, cedent_id)
        if cedent is None:
            raise NotFoundError("cedent not found")

        program = ReinsuranceProgram(
            organization_id=context.organization.id,
            cedent_id=cedent.id,
            name=name,
            treaty_year=treaty_year,
            description=(description or None),
        )
        self._programs.add(program)
        await self._session.flush()
        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="program.created",
                entity_type="reinsurance_program",
                entity_id=program.id,
                summary=f"{context.user.email} created program {name!r} ({treaty_year})",
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        return await self._require_program(context, program.id)

    async def _require_program(
        self, context: AuthenticatedContext, program_id: UUID
    ) -> ReinsuranceProgram:
        program = await self._programs.get(context.organization.id, program_id)
        if program is None:
            raise NotFoundError("program not found")
        return program


# (organization_id, treaty_version_id) -> None
ExtractEnqueuer = Callable[[UUID, UUID], Awaitable[None]]


async def _no_enqueue(_organization_id: UUID, _treaty_version_id: UUID) -> None:
    return None


class TreatyService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        enqueue_extract: ExtractEnqueuer = _no_enqueue,
    ) -> None:
        self._session = session
        self._enqueue_extract = enqueue_extract
        self._treaties = TreatyRepository(session)
        self._versions = TreatyVersionRepository(session)
        self._programs = ProgramRepository(session)
        self._documents = DocumentRepository(session)
        self._audit = AuditRepository(session)

    async def list_treaties(self, context: AuthenticatedContext) -> list[Treaty]:
        return await self._treaties.list(context.organization.id)

    async def get_treaty(self, context: AuthenticatedContext, treaty_id: UUID) -> Treaty:
        treaty = await self._treaties.get(context.organization.id, treaty_id)
        if treaty is None:
            raise NotFoundError("treaty not found")
        return treaty

    async def get_current_version(
        self, context: AuthenticatedContext, treaty: Treaty
    ) -> TreatyVersion | None:
        if treaty.current_version_id is None:
            return None
        return await self._versions.get(context.organization.id, treaty.current_version_id)

    async def create_treaty(
        self,
        context: AuthenticatedContext,
        *,
        program_id: UUID,
        name: str,
        source_document_id: UUID | None,
    ) -> Treaty:
        name = name.strip()
        if not name:
            raise ValidationError("treaty name is required")
        program = await self._programs.get(context.organization.id, program_id)
        if program is None:
            raise NotFoundError("program not found")

        source_document = None
        if source_document_id is not None:
            source_document = await self._documents.get(context.organization.id, source_document_id)
            if source_document is None:
                raise NotFoundError("source document not found")

        treaty = Treaty(
            organization_id=context.organization.id,
            program_id=program.id,
            name=name,
            treaty_type=TreatyType.PER_OCCURRENCE_XOL,
        )
        self._treaties.add(treaty)
        await self._session.flush()

        doc_parsed = source_document is not None and source_document.status == DocumentStatus.PARSED
        version = TreatyVersion(
            organization_id=context.organization.id,
            treaty_id=treaty.id,
            version_no=1,
            source_document_id=source_document.id if source_document else None,
            status=(
                TreatyVersionStatus.EXTRACTING
                if doc_parsed
                else TreatyVersionStatus.PARSING
                if source_document
                else TreatyVersionStatus.DRAFT
            ),
        )
        self._versions.add(version)
        await self._session.flush()

        treaty.current_version_id = version.id
        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="treaty.created",
                entity_type="treaty",
                entity_id=treaty.id,
                summary=f"{context.user.email} created treaty {name!r}",
                payload={"treaty_version_id": str(version.id)},
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        if doc_parsed:
            await self._enqueue_extract(context.organization.id, version.id)
        return await self.get_treaty(context, treaty.id)

    async def rerun_extraction(self, context: AuthenticatedContext, treaty_id: UUID) -> Treaty:
        treaty = await self.get_treaty(context, treaty_id)
        version = await self.get_current_version(context, treaty)
        if version is None or version.source_document_id is None:
            raise ValidationError("this treaty has no source document to extract from")
        if version.status is TreatyVersionStatus.VALIDATED:
            raise ConflictError("this treaty version is already validated")
        version.status = TreatyVersionStatus.EXTRACTING
        await self._session.commit()
        await self._enqueue_extract(context.organization.id, version.id)
        return await self.get_treaty(context, treaty_id)

    async def create_new_version(
        self,
        context: AuthenticatedContext,
        treaty_id: UUID,
        *,
        source_document_id: UUID | None,
        note: str,
    ) -> Treaty:
        """Supersede the current validated version with a fresh one — the path an
        endorsement takes. The new version is a full copy of the frozen state
        (layers, participations, terms) at status ``NEEDS_VALIDATION``, so the
        analyst edits only what the endorsement changed and re-validates. The old
        version is retained as ``SUPERSEDED``; open recoveries against it surface
        on the worklist as contract-change items."""
        org_id = context.organization.id
        note = note.strip()
        if not note:
            raise ValidationError(
                "say what changed (e.g. 'Endorsement 3 — revised occurrence limit')"
            )

        treaty = await self.get_treaty(context, treaty_id)
        if treaty.current_version_id is None:
            raise ConflictError("this treaty has no current version to supersede")
        current = await self._versions.get(org_id, treaty.current_version_id)
        if current is None:
            raise NotFoundError("the current treaty version no longer exists")
        if current.status not in (TreatyVersionStatus.VALIDATED, TreatyVersionStatus.ACTIVE):
            raise ConflictError(
                "only a validated treaty version can be superseded — validate the current one first"
            )

        source_document_id = await self._resolve_source_document(org_id, source_document_id)

        new_version = TreatyVersion(
            organization_id=org_id,
            version_no=current.version_no + 1,
            source_document_id=source_document_id,
            status=TreatyVersionStatus.NEEDS_VALIDATION,
            effective_date=current.effective_date,
            expiration_date=current.expiration_date,
            currency=current.currency,
        )
        new_version.treaty = treaty  # back-populates treaty.versions in memory
        for layer in current.layers:
            new_version.layers.append(
                TreatyLayer(
                    organization_id=org_id,
                    layer_no=layer.layer_no,
                    attachment=layer.attachment,
                    limit=layer.limit,
                    currency=layer.currency,
                    reinstatements=layer.reinstatements,
                    description=layer.description,
                )
            )
        for part in current.participations:
            new_version.participations.append(
                TreatyParticipation(
                    organization_id=org_id,
                    reinsurer_id=part.reinsurer_id,
                    placed_share=part.placed_share,
                    signed_share=part.signed_share,
                    broker_name=part.broker_name,
                )
            )
        for term in current.terms:
            new_version.terms.append(
                TreatyTerm(
                    organization_id=org_id,
                    key=term.key,
                    value=dict(term.value),
                    currency=term.currency,
                    status=term.status,
                    derived_from_candidate_id=term.derived_from_candidate_id,
                    review_id=term.review_id,
                )
            )

        self._versions.add(new_version)
        current.status = TreatyVersionStatus.SUPERSEDED
        await self._session.flush()
        treaty.current_version_id = new_version.id

        self._audit.record(
            AuditRecord(
                organization_id=org_id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="treaty_version.superseded",
                entity_type="treaty",
                entity_id=treaty.id,
                summary=(
                    f"{context.user.email} opened treaty version {new_version.version_no} — {note}"
                ),
                payload={
                    "note": note,
                    "from_version_id": str(current.id),
                    "to_version_id": str(new_version.id),
                    "version_no": new_version.version_no,
                    "source_document_id": (str(source_document_id) if source_document_id else None),
                },
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        return await self.get_treaty(context, treaty_id)

    async def _resolve_source_document(
        self, organization_id: UUID, source_document_id: UUID | None
    ) -> UUID | None:
        if source_document_id is None:
            return None
        document = await self._documents.get(organization_id, source_document_id)
        if document is None:
            raise NotFoundError("source document not found")
        return source_document_id
