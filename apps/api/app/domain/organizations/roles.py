"""Organization roles and the authorization rank order.

    viewer  <  member  <  admin

* viewer — read-only. Reserved for a future auditor / executive persona; not
  assigned anywhere in the product today, but every consequential mutation is
  gated at ``member`` so the boundary is real when it is.
* member — day-to-day reinsurance work: upload, validate, review, approve.
* admin  — everything a member can do, plus manage the organization and its
  people (invite, remove, change roles, rename the organization).

There is deliberately **no ``owner``**. An organization must always keep at least
one admin (enforced in ``MembershipService``); that rule replaces a single
immutable owner and keeps a clean path to SSO / SCIM deprovisioning later
(docs/DECISIONS.md ADR-0026).
"""

from __future__ import annotations

from enum import StrEnum

_RANK: dict[str, int] = {"viewer": 0, "member": 1, "admin": 2}


class Role(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"

    @property
    def rank(self) -> int:
        return _RANK[self.value]

    def satisfies(self, minimum: Role) -> bool:
        """True if this role is at least ``minimum``."""
        return self.rank >= minimum.rank

    @property
    def can_manage_members(self) -> bool:
        return self.satisfies(Role.ADMIN)

    @property
    def can_write(self) -> bool:
        return self.satisfies(Role.MEMBER)


# Roles an admin may assign through the invitation / role-change flows.
ASSIGNABLE_ROLES: tuple[Role, ...] = (Role.ADMIN, Role.MEMBER)
