"""Seed a synthetic demo organization so you can sign in immediately.

Clearly-synthetic data only. The full demo (treaty, losses, golden recovery)
lands with the phases that build those features.
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.db.session import dispose_engine, get_sessionmaker, init_engine
from app.services.auth import AuthService
from app.services.errors import ConflictError

DEMO_ORG_NAME = "Demo Specialty Insurance Co."
DEMO_EMAIL = "founder@demo-specialty.example"
DEMO_USER_NAME = "Demo Founder"
DEMO_PASSWORD = "cedeon-demo-password"  # noqa: S105 - synthetic local demo credential


async def _run() -> None:
    init_engine()
    settings = get_settings()
    async with get_sessionmaker()() as session:
        auth = AuthService(session, settings)
        try:
            await auth.register_organization(
                organization_name=DEMO_ORG_NAME,
                email=DEMO_EMAIL,
                name=DEMO_USER_NAME,
                password=DEMO_PASSWORD,
            )
        except ConflictError:
            print(f"demo organization already present — sign in as {DEMO_EMAIL}")
        else:
            print(f"created {DEMO_ORG_NAME!r}")
            print(f"  sign in:  {DEMO_EMAIL}  /  {DEMO_PASSWORD}")
    await dispose_engine()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
