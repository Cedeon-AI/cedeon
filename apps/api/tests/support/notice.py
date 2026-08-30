"""A canned notice draft — exercises the persist / review / audit flow without a model."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.ai.notice.runner import NoticeDraftResult
from app.ai.notice.schema import NoticeDraft
from app.domain.recoveries import NoticeContext, NoticeKind


def golden_draft(context: NoticeContext) -> NoticeDraft:
    body = (
        f"Dear {context.recipient.name},\n\n"
        f"**{context.title} — {context.treaty_name}**\n\n"
        f"We write on behalf of {context.cedent_name} to advise you of a loss under the "
        f"above treaty arising from {context.loss_event_name}.\n\n"
        f"- Layer: {context.currency} {context.limit} excess of {context.currency} "
        f"{context.attachment} each and every loss occurrence.\n"
        f"- Gross event incurred (ceding company): {context.currency} "
        f"{context.gross_event_incurred}.\n"
        f"- Indicated layer recovery: {context.currency} {context.layer_recovery}.\n\n"
        "These figures are Cedeon's indicative calculation and are subject to your own "
        "review and to the terms and conditions of the treaty. This notice is given "
        "without admission or waiver of any rights or defences and does not constitute "
        "agreement that any amount is due or payable.\n\n"
        "Yours faithfully,\nCeded Reinsurance"
    )
    return NoticeDraft(
        subject=f"{context.title} — {context.loss_event_name}",
        body_markdown=body,
        key_figures={
            "layer_recovery": context.layer_recovery,
            "gross_event_incurred": context.gross_event_incurred,
            "attachment": context.attachment,
            "limit": context.limit,
        },
        caveats=[
            "Indicative calculation, subject to the reinsurer's review and the treaty terms.",
            "Given without admission or waiver of rights; no agreement that any amount is due.",
        ],
        used_only_provided_facts=True,
        notes_for_reviewer="Add the internal claim reference and confirm the exact addressee.",
    )


def golden_result(context: NoticeContext) -> NoticeDraftResult:
    draft = golden_draft(context)
    return NoticeDraftResult(
        draft=draft,
        provider="anthropic",
        model="anthropic:claude-opus-5",
        prompt_version="notice-drafter/v1",
        input_tokens=900,
        output_tokens=500,
        cost_usd=Decimal("0.014000"),
        latency_ms=4200,
        output=draft.model_dump(mode="json"),
    )


async def run_notice_draft(
    session: object,
    settings: object,
    org_id: object,
    candidate_id: object,
    *,
    kind: NoticeKind = NoticeKind.INITIAL_LOSS_ADVICE,
    recipient: dict[str, str] | None = None,
):
    from app.services.notice import NoticeService

    async def _fake(*, notice_context: NoticeContext, **_kw: Any) -> NoticeDraftResult:
        return golden_result(notice_context)

    service = NoticeService(session, settings, drafter=_fake)  # type: ignore[arg-type]
    return await service.draft(
        org_id,  # type: ignore[arg-type]
        candidate_id,  # type: ignore[arg-type]
        kind=kind,
        recipient=recipient
        or {"name": "Jane Underwriter", "organisation": "Reinsurer Alpha", "role": "Claims"},
    )
