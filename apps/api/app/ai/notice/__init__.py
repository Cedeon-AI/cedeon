"""Notice drafter — one typed structured-output call, no tools (docs/AI_ARCHITECTURE.md §2c).

Runs only after a human confirms the recovery candidate. Drafts from a whitelist
of approved facts; produces a draft for human review. Cedeon never sends anything.
"""

from __future__ import annotations

from app.ai.notice.runner import NoticeDraftResult, draft_notice
from app.ai.notice.schema import NoticeDraft

__all__ = ["NoticeDraft", "NoticeDraftResult", "draft_notice"]
