"""Regression eval datasets for the AI surfaces (docs/AI_ARCHITECTURE.md §5).

These hit the real provider, so they are run on demand — ``pytest -m eval`` or
``python -m app.ai.evals.run`` — not in the default CI job. They are datasets +
graders, not vibes: exact value / citation-resolvability / guardrail-flag checks.
"""
