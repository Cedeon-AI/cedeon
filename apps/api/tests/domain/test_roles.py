from __future__ import annotations

from app.domain.organizations import Role


def test_rank_order() -> None:
    assert Role.VIEWER.rank < Role.MEMBER.rank < Role.ADMIN.rank < Role.OWNER.rank


def test_satisfies() -> None:
    assert Role.OWNER.satisfies(Role.ADMIN)
    assert Role.ADMIN.satisfies(Role.ADMIN)
    assert not Role.MEMBER.satisfies(Role.ADMIN)
    assert not Role.VIEWER.satisfies(Role.MEMBER)


def test_capability_helpers() -> None:
    assert Role.OWNER.can_manage_members
    assert Role.ADMIN.can_manage_members
    assert not Role.MEMBER.can_manage_members
    assert Role.MEMBER.can_write
    assert not Role.VIEWER.can_write


def test_role_is_string_valued() -> None:
    assert Role.OWNER == "owner"
    assert Role("admin") is Role.ADMIN
