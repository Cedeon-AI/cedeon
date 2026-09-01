"""Mint a signup access code (docs/DECISIONS.md ADR-0028).

    just mint-code "Acme Re demo" --budget 50
    just mint-code "Design partner" --uses 3 --days 60 --unlimited

Only the code's HMAC is stored; the raw code is printed once. Hand it to one
prospect — redeeming it at /register creates their organization (and stamps the
AI budget). Requires DB access (CEDEON_DATABASE_URL), so only the operator can run it.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
from decimal import Decimal, InvalidOperation

from app.core.config import get_settings
from app.core.security import generate_session_token, hash_session_token
from app.db.models.identity import SignupCode
from app.db.session import dispose_engine, get_sessionmaker, init_engine


async def _mint(args: argparse.Namespace) -> None:
    settings = get_settings()
    raw = generate_session_token()
    code = SignupCode(
        code_hash=hash_session_token(raw, settings.session_secret),
        label=args.label.strip(),
        max_uses=args.uses,
        grant_ai_budget_usd=None if args.unlimited else Decimal(str(args.budget)),
        expires_at=(
            None if args.days <= 0 else dt.datetime.now(dt.UTC) + dt.timedelta(days=args.days)
        ),
        notes=args.notes,
    )
    init_engine()
    async with get_sessionmaker()() as session:
        session.add(code)
        await session.commit()
        budget = "unlimited" if code.grant_ai_budget_usd is None else f"${code.grant_ai_budget_usd}"
        expiry = "never" if code.expires_at is None else code.expires_at.date().isoformat()
        print(f"access code for {code.label!r}:\n")
        print(f"    {raw}\n")
        print(f"  uses: {code.max_uses}   expires: {expiry}   AI budget/org: {budget}")
    await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description="Mint a Cedeon signup access code.")
    parser.add_argument("label", help="who this code is for, e.g. 'Acme Re demo'")
    parser.add_argument(
        "--uses", type=int, default=1, help="how many orgs it may create (default 1)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="days until expiry (default: CEDEON_SIGNUP_CODE_TTL_DAYS)",
    )
    parser.add_argument(
        "--budget",
        type=str,
        default=None,
        help="monthly AI budget in USD stamped onto each org created with this code",
    )
    parser.add_argument("--unlimited", action="store_true", help="no AI budget cap (use sparingly)")
    parser.add_argument("--notes", type=str, default=None)
    args = parser.parse_args()

    if args.days is None:
        args.days = get_settings().signup_code_ttl_days
    if not args.unlimited:
        if args.budget is None:
            parser.error("pass --budget <usd> or --unlimited")
        try:
            if Decimal(str(args.budget)) <= 0:
                parser.error("--budget must be positive")
        except InvalidOperation:
            parser.error("--budget must be a number")

    asyncio.run(_mint(args))


if __name__ == "__main__":
    main()
