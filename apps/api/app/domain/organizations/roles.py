"""Membership roles and the authorization rank order.

    viewer  < member < admin < owner

* viewer — read only
* member — can perform reviews / approvals and day-to-day work
* admin  — can also manage members
* owner  — full control, cannot be removed by a non-owner
"""

from __future__ import annotations

from enum import StrEnum

_RANK: dict[str, int] = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}


class Role(StrEnum):
    OWNER = "owner"
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
