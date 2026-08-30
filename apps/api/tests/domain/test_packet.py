"""Deterministic packet assembly + HTML rendering. No AI, no I/O."""

from __future__ import annotations

from app.domain.recoveries import PacketStatementClass, assemble_packet, render_packet_html
from app.domain.recoveries.packet import PacketInputs


def _inputs(**overrides: object) -> PacketInputs:
    base = dict(  # noqa: C408 — kwargs form reads better for this fixture
        treaty_name="2027 Property Cat XOL",
        cedent_name="Demo Specialty Insurance Co.",
        program_name="2027 Property Catastrophe Program",
        layer_attachment="50000000.00",
        layer_limit="20000000.00",
        currency="USD",
        validated_terms=[
            {
                "key": "attachment",
                "label": "Attachment (retention)",
                "value": "USD 50000000.00",
                "citation": {
                    "document_id": "doc-1",
                    "page_number": 2,
                    "section": "ARTICLE IV",
                    "quoted_text": "a retention of USD 50,000,000",
                },
            },
            {"key": "limit", "label": "Limit", "value": "USD 20000000.00", "citation": None},
        ],
        calculation={
            "gross_event_incurred": "58700000.00",
            "attachment": "50000000.00",
            "limit": "20000000.00",
            "amount_above_attachment": "8700000.00",
            "layer_recovery": "8700000.00",
            "cedent_retention": "0.00",
            "total_ceded": "8700000.00",
            "engine_version": "1.0.0",
            "trace": [
                {
                    "label": "amount above attachment",
                    "expression": "max(58700000.00 - 50000000.00, 0)",
                    "result": "8700000.00",
                },
                {
                    "label": "layer recovery",
                    "expression": "min(8700000.00, 20000000.00)",
                    "result": "8700000.00",
                },
            ],
            "allocations": [
                {
                    "reinsurer_name": "Reinsurer Alpha",
                    "participation_share": "50%",
                    "allocated_recovery": "4350000.00",
                },
                {
                    "reinsurer_name": "Reinsurer Beta",
                    "participation_share": "30%",
                    "allocated_recovery": "2610000.00",
                },
                {
                    "reinsurer_name": "Reinsurer Gamma",
                    "participation_share": "20%",
                    "allocated_recovery": "1740000.00",
                },
            ],
        },
        loss_event={
            "name": "Hurricane Demo 2027",
            "catastrophe_code": "HURR-DEMO-2027",
            "date_from": "2027-09-14",
            "date_to": "2027-09-16",
            "totals": [{"currency": "USD", "claim_count": 10, "gross_incurred": "58700000.00"}],
        },
        loss_count=10,
        investigation={
            "summary": "The layer responds.",
            "applicability": "supported",
            "findings": [
                {
                    "kind": "relevant_clause",
                    "text": "Article IV sets the retention and limit.",
                    "citation": {
                        "document_id": "doc-1",
                        "page_number": 2,
                        "section": "ARTICLE IV",
                        "quoted_text": "a retention of USD 50,000,000",
                    },
                }
            ],
            "unresolved_questions": ["Any claim still developing?"],
        },
        reviews=[
            {"kind": "candidate", "decision": "confirm", "reason": "checks out", "at": "2027-10-01"}
        ],
        human_overrides={},
        generated_at="2027-10-01T12:00:00",
    )
    base.update(overrides)
    return PacketInputs(**base)  # type: ignore[arg-type]


def test_assembly_uses_all_four_statement_classes() -> None:
    content = assemble_packet(_inputs())
    assert content.classes_present() == {
        PacketStatementClass.FACT,
        PacketStatementClass.CALCULATION,
        PacketStatementClass.AI_INTERPRETATION,
        PacketStatementClass.HUMAN_DECISION,
    }
    keys = {s.key for s in content.statements()}
    assert "calc.layer_recovery" in keys
    assert "inv.finding.0" in keys
    assert any(k.startswith("term.") for k in keys)


def test_calculation_statements_are_classed_calculation() -> None:
    content = assemble_packet(_inputs())
    layer = content.statement("calc.layer_recovery")
    assert layer is not None
    assert layer.statement_class is PacketStatementClass.CALCULATION
    assert "8700000.00" in layer.text


def test_investigation_findings_keep_their_citation() -> None:
    content = assemble_packet(_inputs())
    finding = content.statement("inv.finding.0")
    assert finding is not None
    assert finding.statement_class is PacketStatementClass.AI_INTERPRETATION
    assert finding.citation is not None
    assert finding.citation.page_number == 2


def test_no_investigation_yields_a_placeholder_ai_statement() -> None:
    content = assemble_packet(_inputs(investigation=None))
    placeholder = content.statement("inv.none")
    assert placeholder is not None
    assert placeholder.statement_class is PacketStatementClass.AI_INTERPRETATION


def test_human_override_replaces_text_and_flags_the_statement() -> None:
    content = assemble_packet(
        _inputs(
            human_overrides={
                "calc.layer_recovery": {
                    "text": "Layer recovery: USD 8,700,000.00 (agreed with the broker).",
                    "reason": "wording",
                    "by": "vp@carrier.example",
                }
            }
        )
    )
    layer = content.statement("calc.layer_recovery")
    assert layer is not None
    assert layer.edited_by_human is True
    assert "agreed with the broker" in layer.text
    assert layer.detail["original_text"].startswith("Layer recovery: USD 8700000.00")
    assert content.statement("edit.calc.layer_recovery") is not None


def test_render_html_shows_every_class_and_the_figure() -> None:
    html = render_packet_html(assemble_packet(_inputs()))
    for label in ("FACT", "CALCULATION", "AI INTERPRETATION", "HUMAN DECISION"):
        assert label in html
    assert "8700000.00" in html
    assert "Reinsurer Alpha" in html
    assert "a retention of USD 50,000,000" in html  # citation quote rendered
    assert html.startswith("<!doctype html>")
