"""Deterministic single-file HTML rendering of a packet. Pure; standard library
only. The four statement classes are visually distinct (docs/ARCHITECTURE.md §7)."""

from __future__ import annotations

from html import escape

from app.domain.recoveries.packet import (
    PacketContent,
    PacketStatement,
    PacketStatementClass,
)

_CLASS_META: dict[PacketStatementClass, tuple[str, str]] = {
    PacketStatementClass.FACT: ("FACT", "#2563eb"),
    PacketStatementClass.CALCULATION: ("CALCULATION", "#0f766e"),
    PacketStatementClass.AI_INTERPRETATION: ("AI INTERPRETATION", "#b45309"),
    PacketStatementClass.HUMAN_DECISION: ("HUMAN DECISION", "#7c3aed"),
}

_STYLE = """
  :root { color-scheme: light; }
  body { font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         color: #1c1c1c; background: #fafafa; margin: 0; padding: 2rem; }
  .packet { max-width: 46rem; margin: 0 auto; background: #fff; border: 1px solid #e5e5e5;
            border-radius: 10px; padding: 2rem 2.25rem; }
  h1 { font-size: 1.4rem; margin: 0 0 .25rem; }
  .subtitle { color: #666; margin: 0 0 .25rem; }
  .meta { color: #999; font-size: .8rem; margin: 0 0 1.5rem; }
  h2 { font-size: 1rem; margin: 1.75rem 0 .5rem; border-bottom: 1px solid #eee;
       padding-bottom: .3rem; }
  .stmt { border-left: 3px solid var(--c); padding: .5rem .75rem; margin: .5rem 0;
          background: color-mix(in srgb, var(--c) 5%, #fff); border-radius: 0 4px 4px 0; }
  .badge { display: inline-block; font-size: .62rem; font-weight: 700; letter-spacing: .04em;
           color: var(--c); border: 1px solid var(--c); border-radius: 3px; padding: 0 .3rem;
           margin-right: .4rem; vertical-align: 1px; }
  .edited { font-size: .62rem; color: #7c3aed; font-weight: 700; margin-left: .3rem; }
  .cite { margin-top: .35rem; font-size: .8rem; color: #555; border-left: 2px solid #ccc;
          padding-left: .5rem; }
  .cite em { display: block; color: #333; }
  .legend { display: flex; flex-wrap: wrap; gap: .5rem; margin-bottom: 1rem; }
  .legend span { font-size: .7rem; padding: .1rem .4rem; border-radius: 3px; }
"""


def _statement_html(s: PacketStatement) -> str:
    label, color = _CLASS_META[s.statement_class]
    parts = [
        f'<div class="stmt" style="--c:{color}">',
        f'<span class="badge">{escape(label)}</span>',
        escape(s.text),
    ]
    if s.edited_by_human:
        parts.append('<span class="edited">✎ edited by a human</span>')
    quote = s.citation.quoted_text if s.citation else None
    if s.citation and quote:
        loc: list[str] = []
        if s.citation.page_number:
            loc.append(f"p.{s.citation.page_number}")
        if s.citation.section:
            loc.append(escape(s.citation.section))
        parts.append(f'<div class="cite">{" · ".join(loc)}<em>“{escape(quote)}”</em></div>')
    parts.append("</div>")
    return "".join(parts)


def render_packet_html(content: PacketContent) -> str:
    legend = "".join(
        f'<span style="border-left:3px solid {c};padding-left:.3rem">{escape(label)}</span>'
        for label, c in _CLASS_META.values()
    )
    body = []
    for section in content.sections:
        body.append(f"<h2>{escape(section.title)}</h2>")
        body.extend(_statement_html(s) for s in section.statements)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(content.title)}</title><style>{_STYLE}</style></head><body>"
        '<div class="packet">'
        f"<h1>{escape(content.title)}</h1>"
        f'<p class="subtitle">{escape(content.subtitle)}</p>'
        f'<p class="meta">Generated {escape(content.generated_at)} · '
        f"engine {escape(content.engine_version)} · "
        "every statement below is classified; AI statements carry their citation.</p>"
        f'<div class="legend">{legend}</div>' + "".join(body) + "</div></body></html>"
    )
