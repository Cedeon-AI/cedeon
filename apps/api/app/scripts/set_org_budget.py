"""Set (or lift) an organization's monthly AI budget (docs/DECISIONS.md ADR-0028).

    just set-org-budget acme-re 100      # $100 / calendar month
    just set-org-budget acme-re unlimited

Org admins cannot change their own budget — only the operator, with DB access.
"""

from __future__ import annotations

import argparse
import asyncio
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from app.db.models.identity import Organization
from app.db.session import dispose_engine, get_sessionmaker, init_engine


async def _set(slug: str, budget: Decimal | None) -> None:
    init_engine()
    async with get_sessionmaker()() as session:
        org = (
            await session.execute(select(Organization).where(Organization.slug == slug))
        ).scalar_one_or_none()
        if org is None:
            raise SystemExit(f"no organization with slug {slug!r}")
        org.ai_budget_usd = budget
        org.ai_budget_notified_at = None  # let the alert fire again under the new cap
        await session.commit()
        shown = "unlimited" if budget is None else f"${budget}/month"
        print(f"{org.name} ({org.slug}) AI budget → {shown}")
    await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description="Set an organization's monthly AI budget.")
    parser.add_argument("slug", help="the organization slug")
    parser.add_argument("budget", help="USD amount, or 'unlimited'")
    args = parser.parse_args()

    if args.budget.lower() in ("unlimited", "none", "off"):
        budget: Decimal | None = None
    else:
        try:
            budget = Decimal(args.budget)
        except InvalidOperation:
            parser.error("budget must be a number or 'unlimited'")
        if budget <= 0:
            parser.error("budget must be positive")

    asyncio.run(_set(args.slug, budget))


if __name__ == "__main__":
    main()
