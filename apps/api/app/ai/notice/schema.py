"""Typed output of the notice drafter.

The drafter gets a fixed whitelist of approved facts (``NoticeContext``) and
nothing else. It writes correspondence; it does not decide, agree, or send
(docs/AI_ARCHITECTURE.md §2c)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NoticeDraft(BaseModel):
    subject: str = Field(description="a concise subject line for the notice")
    body_markdown: str = Field(
        description="the full notice as markdown — professional reinsurance correspondence, "
        "addressed to the named recipient, presenting the recovery as Cedeon's indicative "
        "calculation subject to the reinsurer's review and the treaty terms"
    )
    key_figures: dict[str, str] = Field(
        default_factory=dict,
        description="the figures you used, echoed back verbatim from the facts provided "
        "(e.g. {'layer_recovery': '8700000.00'}) — for the reviewer to check against",
    )
    caveats: list[str] = Field(
        default_factory=list,
        description="the qualifications stated in the body (indicative only, subject to review, "
        "no admission of liability, etc.)",
    )
    used_only_provided_facts: bool = Field(
        description="true if every party, date, figure, and clause in the notice came from the "
        "facts provided — no outside knowledge, no invented policy numbers or contacts"
    )
    notes_for_reviewer: str = Field(
        default="",
        description="anything the human should check or supply before sending (e.g. claim "
        "reference, exact addressee, attachments)",
    )
