"""The Recovery Packet: a deterministic assembly of already-produced material into
an audit-friendly artifact where every statement is one of four classes.

FACT              — a human-validated contract term or an objective record.
CALCULATION       — output of the deterministic engine (ADR-0010), with its trace.
AI_INTERPRETATION — a Recovery Investigator finding, each carrying its citation.
HUMAN_DECISION    — a review decision or a human edit, with before/after.

No AI here. This module only arranges and labels; it never interprets or computes
(docs/AI_ARCHITECTURE.md §7). Standard library only."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PacketStatementClass(StrEnum):
    FACT = "fact"
    CALCULATION = "calculation"
    AI_INTERPRETATION = "ai_interpretation"
    HUMAN_DECISION = "human_decision"


class PacketVersionStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class PacketCitation:
    document_id: str | None = None
    page_number: int | None = None
    section: str | None = None
    quoted_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "page_number": self.page_number,
            "section": self.section,
            "quoted_text": self.quoted_text,
        }


@dataclass(frozen=True, slots=True)
class PacketStatement:
    key: str
    statement_class: PacketStatementClass
    text: str
    citation: PacketCitation | None = None
    detail: dict[str, str] = field(default_factory=dict)
    edited_by_human: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "statement_class": self.statement_class.value,
            "text": self.text,
            "citation": self.citation.to_dict() if self.citation else None,
            "detail": dict(self.detail),
            "edited_by_human": self.edited_by_human,
        }


@dataclass(frozen=True, slots=True)
class PacketSection:
    key: str
    title: str
    statements: tuple[PacketStatement, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "statements": [s.to_dict() for s in self.statements],
        }


@dataclass(frozen=True, slots=True)
class PacketContent:
    title: str
    subtitle: str
    generated_at: str
    engine_version: str
    sections: tuple[PacketSection, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "generated_at": self.generated_at,
            "engine_version": self.engine_version,
            "sections": [s.to_dict() for s in self.sections],
        }

    def statements(self) -> list[PacketStatement]:
        return [s for section in self.sections for s in section.statements]

    def statement(self, key: str) -> PacketStatement | None:
        return next((s for s in self.statements() if s.key == key), None)

    def classes_present(self) -> set[PacketStatementClass]:
        return {s.statement_class for s in self.statements()}


# --- assembly ------------------------------------------------------


@dataclass(slots=True)
class PacketInputs:
    """All values are plain data, already produced by deterministic code or a
    validated human decision. This module labels and arranges; it does not compute."""

    treaty_name: str
    cedent_name: str
    program_name: str
    layer_attachment: str
    layer_limit: str
    currency: str
    # validated_terms: {key, label, value, citation?}
    validated_terms: list[dict[str, Any]]
    # calculation: gross_event_incurred, attachment, limit, amount_above_attachment,
    #   layer_recovery, cedent_retention, total_ceded, engine_version, trace[], allocations[]
    calculation: dict[str, Any]
    # loss_event: name, event_identifier?, catastrophe_code?, date_from?, date_to?, totals[]
    loss_event: dict[str, Any]
    loss_count: int
    # investigation: summary, applicability, findings[], unresolved_questions[]
    investigation: dict[str, Any] | None
    # reviews: {decision, reason?, at, kind}  where kind in {candidate, packet}
    reviews: list[dict[str, Any]]
    # human_overrides: statement_key -> {text, reason, by}
    human_overrides: dict[str, dict[str, str]]
    generated_at: str


def _apply_override(
    statement: PacketStatement, overrides: dict[str, dict[str, str]]
) -> PacketStatement:
    override = overrides.get(statement.key)
    if override is None:
        return statement
    detail = dict(statement.detail)
    detail["human_edit_reason"] = override.get("reason", "")
    detail["human_edit_by"] = override.get("by", "")
    detail["original_text"] = statement.text
    return PacketStatement(
        key=statement.key,
        statement_class=statement.statement_class,
        text=override.get("text", statement.text),
        citation=statement.citation,
        detail=detail,
        edited_by_human=True,
    )


def _citation_from(raw: dict[str, Any] | None) -> PacketCitation | None:
    if not raw:
        return None
    return PacketCitation(
        document_id=raw.get("document_id"),
        page_number=raw.get("page_number"),
        section=raw.get("section"),
        quoted_text=raw.get("quoted_text"),
    )


def assemble_packet(inputs: PacketInputs) -> PacketContent:
    o = inputs.human_overrides
    calc = inputs.calculation
    sections: list[PacketSection] = []

    def fact(key: str, text: str, citation: dict[str, Any] | None = None) -> PacketStatement:
        return _apply_override(
            PacketStatement(key, PacketStatementClass.FACT, text, _citation_from(citation)), o
        )

    def calculation(key: str, text: str, detail: dict[str, str] | None = None) -> PacketStatement:
        return _apply_override(
            PacketStatement(key, PacketStatementClass.CALCULATION, text, detail=detail or {}),
            o,
        )

    def ai(key: str, text: str, citation: dict[str, Any] | None = None) -> PacketStatement:
        return _apply_override(
            PacketStatement(
                key, PacketStatementClass.AI_INTERPRETATION, text, _citation_from(citation)
            ),
            o,
        )

    def human(key: str, text: str, detail: dict[str, str] | None = None) -> PacketStatement:
        return _apply_override(
            PacketStatement(key, PacketStatementClass.HUMAN_DECISION, text, detail=detail or {}),
            o,
        )

    # 1 — Summary
    summary_statements = [
        fact("summary.treaty", f"Treaty: {inputs.treaty_name} ({inputs.cedent_name})."),
        fact(
            "summary.layer",
            f"Layer: {inputs.currency} {inputs.layer_limit} excess of "
            f"{inputs.currency} {inputs.layer_attachment} each and every loss occurrence.",
        ),
        fact("summary.event", f"Loss event: {inputs.loss_event.get('name', '—')}."),
        calculation(
            "summary.recovery",
            f"Indicated layer recovery: {inputs.currency} {calc['layer_recovery']} "
            f"(deterministic engine {calc.get('engine_version', '')}).",
        ),
    ]
    if inputs.investigation:
        _appl = inputs.investigation["applicability"].replace("_", " ")
        summary_statements.append(ai("summary.applicability", f"Investigator assessment: {_appl}."))
    sections.append(PacketSection("summary", "Summary", tuple(summary_statements)))

    # 2 — The treaty (validated terms)
    term_statements = [
        fact(
            f"term.{t['key']}",
            f"{t.get('label', t['key'])}: {t['value']}.",
            t.get("citation"),
        )
        for t in inputs.validated_terms
    ]
    if term_statements:
        sections.append(PacketSection("treaty", "Validated treaty terms", tuple(term_statements)))

    # 3 — The loss event
    event = inputs.loss_event
    event_statements = [
        fact(
            "loss.event",
            f"{event.get('name', '—')}"
            + (f" · {event['catastrophe_code']}" if event.get("catastrophe_code") else "")
            + (f" · {event['date_from']} → {event['date_to']}" if event.get("date_from") else "")
            + ".",
        ),
        fact("loss.count", f"{inputs.loss_count} underlying losses committed to this event."),
    ]
    for total in event.get("totals", []):
        event_statements.append(
            calculation(
                f"loss.total.{total['currency']}",
                f"Gross incurred ({total['currency']}): {total['gross_incurred']} "
                f"across {total['claim_count']} claims.",
            )
        )
    sections.append(PacketSection("loss_event", "Loss event", tuple(event_statements)))

    # 4 — The calculation
    calc_statements: list[PacketStatement] = [
        calculation(
            "calc.gross",
            f"Gross event incurred: {inputs.currency} {calc['gross_event_incurred']}.",
        )
    ]
    for i, step in enumerate(calc.get("trace", [])):
        calc_statements.append(
            calculation(
                f"calc.trace.{i}",
                f"{step['label']}: {step['expression']} = {step['result']}.",
            )
        )
    calc_statements.append(
        calculation(
            "calc.layer_recovery",
            f"Layer recovery: {inputs.currency} {calc['layer_recovery']}.",
        )
    )
    if calc.get("cedent_retention") and calc["cedent_retention"] not in ("0", "0.00"):
        calc_statements.append(
            calculation(
                "calc.cedent_retention",
                f"Cedent retention (unplaced): {inputs.currency} {calc['cedent_retention']}.",
            )
        )
    for alloc in calc.get("allocations", []):
        calc_statements.append(
            calculation(
                f"calc.alloc.{alloc['reinsurer_name']}",
                f"{alloc['reinsurer_name']} ({alloc['participation_share']}): "
                f"{inputs.currency} {alloc['allocated_recovery']}.",
            )
        )
    sections.append(
        PacketSection("calculation", "Deterministic recovery calculation", tuple(calc_statements))
    )

    # 5 — AI investigation
    if inputs.investigation:
        inv = inputs.investigation
        inv_statements = [ai("inv.summary", inv["summary"])]
        for i, finding in enumerate(inv.get("findings", [])):
            inv_statements.append(
                ai(
                    f"inv.finding.{i}",
                    f"[{finding['kind'].replace('_', ' ')}] {finding['text']}",
                    finding.get("citation"),
                )
            )
        for i, question in enumerate(inv.get("unresolved_questions", [])):
            inv_statements.append(ai(f"inv.question.{i}", f"Unresolved: {question}"))
        sections.append(PacketSection("investigation", "AI investigation", tuple(inv_statements)))
    else:
        sections.append(
            PacketSection(
                "investigation",
                "AI investigation",
                (ai("inv.none", "This candidate has not been investigated yet."),),
            )
        )

    # 6 — Human decisions
    human_statements: list[PacketStatement] = []
    for i, review in enumerate(inputs.reviews):
        label = "Candidate" if review.get("kind") == "candidate" else "Packet"
        reason = f" — {review['reason']}" if review.get("reason") else ""
        decision = review["decision"].replace("_", " ")
        human_statements.append(
            human(f"decision.{i}", f"{label} {decision} on {review.get('at', '')}{reason}.")
        )
    for key, override in sorted(o.items()):
        human_statements.append(
            human(
                f"edit.{key}",
                f"Edited “{key}”: {override.get('reason', 'no reason given')}.",
                {"by": override.get("by", "")},
            )
        )
    if not human_statements:
        human_statements.append(
            human("decision.none", "No human decisions recorded on this packet yet.")
        )
    sections.append(PacketSection("human", "Human decisions", tuple(human_statements)))

    return PacketContent(
        title=f"Recovery packet — {inputs.treaty_name}",
        subtitle=f"{inputs.loss_event.get('name', 'loss event')} · {inputs.currency} "
        f"{calc['layer_recovery']} indicated",
        generated_at=inputs.generated_at,
        engine_version=str(calc.get("engine_version", "")),
        sections=tuple(sections),
    )
