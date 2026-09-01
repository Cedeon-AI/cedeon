"""Signup-gating domain concepts.

A signup code is a coupon the operator mints (`just mint-code`) and hands to one
prospect. It gates ``AuthService.register_organization`` when ``signup_mode`` is
``"code"``: creating an organization requires redeeming one. A code carries a
usage cap, an optional expiry, and an optional AI-budget grant that is stamped
onto the new organization (docs/DECISIONS.md ADR-0028).
"""

from __future__ import annotations

import datetime as dt


def is_redeemable(
    *,
    revoked_at: dt.datetime | None,
    expires_at: dt.datetime | None,
    max_uses: int,
    redeemed_count: int,
    now: dt.datetime,
) -> bool:
    """True if this code can still be redeemed once more."""
    if revoked_at is not None:
        return False
    if expires_at is not None and expires_at <= now:
        return False
    return redeemed_count < max_uses
