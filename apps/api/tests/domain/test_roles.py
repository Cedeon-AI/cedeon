from __future__ import annotations

from app.domain.organizations import ASSIGNABLE_ROLES, Role


def test_rank_order() -> None:
    assert Role.VIEWER.rank < Role.MEMBER.rank < Role.ADMIN.rank


def test_satisfies() -> None:
    assert Role.ADMIN.satisfies(Role.ADMIN)
    assert Role.ADMIN.satisfies(Role.MEMBER)
    assert not Role.MEMBER.satisfies(Role.ADMIN)
    assert not Role.VIEWER.satisfies(Role.MEMBER)


def test_capability_helpers() -> None:
    assert Role.ADMIN.can_manage_members
    assert not Role.MEMBER.can_manage_members
    assert Role.ADMIN.can_write
    assert Role.MEMBER.can_write
    assert not Role.VIEWER.can_write


def test_role_is_string_valued() -> None:
    assert Role.ADMIN == "admin"
    assert Role("member") is Role.MEMBER


def test_assignable_roles_excludes_viewer() -> None:
    assert set(ASSIGNABLE_ROLES) == {Role.ADMIN, Role.MEMBER}
