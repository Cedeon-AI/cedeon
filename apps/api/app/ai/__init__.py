"""AI layer.

Rule (docs/AI_ARCHITECTURE.md): LLMs interpret, deterministic code calculates,
humans approve. Extraction is a single typed structured-output call — no tools,
no loop. This package holds the LLM calls and their typed outputs; persistence
and audit (`agent_runs`) live in the service layer.
"""
