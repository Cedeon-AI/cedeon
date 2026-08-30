"""The notice context — a whitelist of approved values, and its prompt rendering."""

from __future__ import annotations

from app.domain.recoveries import (
    NoticeInputs,
    NoticeKind,
    NoticeParticipant,
    NoticeRecipient,
    build_notice_context,
)


def _inputs(**over: object) -> NoticeInputs:
    base = NoticeInputs(
        kind=NoticeKind.INITIAL_LOSS_ADVICE,
        recipient=NoticeRecipient(name="Jane U.", organisation="Reinsurer Alpha", role="Claims"),
        cedent_name="Demo Specialty Insurance Co.",
        treaty_name="2027 Property Cat XOL",
        program_name="2027 Property Catastrophe Program",
        currency="USD",
        attachment="50000000.00",
        limit="20000000.00",
        loss_event_name="Hurricane Demo 2027",
        catastrophe_code="HURR-DEMO-2027",
        date_of_loss_from="2027-09-14",
        date_of_loss_to="2027-09-16",
        gross_event_incurred="58700000.00",
        layer_recovery="8700000.00",
        engine_version="1.0.0",
        participants=[
            NoticeParticipant("Reinsurer Alpha", "50%", "4350000.00"),
            NoticeParticipant("Reinsurer Beta", "30%", "2610000.00"),
        ],
        notice_provision="within 30 days of a reserve >= 50% of the retention",
        packet_approved=False,
        generated_on="2027-10-01",
    )
    for k, v in over.items():
        setattr(base, k, v)
    return base


def test_context_carries_only_the_provided_values() -> None:
    ctx = build_notice_context(_inputs())
    d = ctx.to_dict()
    assert d["layer_recovery"] == "8700000.00"
    assert d["cedent_name"] == "Demo Specialty Insurance Co."
    assert d["recipient"]["organisation"] == "Reinsurer Alpha"
    # no free-text document content anywhere in the context
    assert set(d) == {
        "kind",
        "cedent_name",
        "treaty_name",
        "program_name",
        "currency",
        "attachment",
        "limit",
        "loss_event_name",
        "catastrophe_code",
        "date_of_loss_from",
        "date_of_loss_to",
        "gross_event_incurred",
        "layer_recovery",
        "engine_version",
        "participants",
        "notice_provision",
        "packet_approved",
        "recipient",
        "generated_on",
    }


def test_prompt_is_deterministic_and_contains_the_figures() -> None:
    ctx = build_notice_context(_inputs())
    p1 = ctx.to_prompt()
    p2 = build_notice_context(_inputs()).to_prompt()
    assert p1 == p2
    assert "8700000.00" in p1
    assert "20000000.00 excess of USD 50000000.00" in p1
    assert "Reinsurer Alpha: 50% → USD 4350000.00" in p1
    assert "Initial Loss Advice" in p1
    assert "no approved recovery packet yet" in p1


def test_prompt_notes_an_approved_packet() -> None:
    p = build_notice_context(_inputs(packet_approved=True)).to_prompt()
    assert "human-approved recovery packet supports this notice" in p


def test_titles_per_kind() -> None:
    assert build_notice_context(_inputs()).title == "Initial Loss Advice"
    assert (
        build_notice_context(_inputs(kind=NoticeKind.REINSURER_NOTIFICATION)).title
        == "Reinsurer Notification of Loss"
    )
