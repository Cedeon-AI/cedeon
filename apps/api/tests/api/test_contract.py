"""Guardrails on the OpenAPI contract that the web client is generated from."""

from __future__ import annotations


def test_every_operation_has_a_stable_operation_id(app) -> None:
    schema = app.openapi()
    missing = [
        f"{method.upper()} {path}"
        for path, methods in schema["paths"].items()
        for method, operation in methods.items()
        if "operationId" not in operation
    ]
    assert not missing, f"operations without operationId: {missing}"


def test_expected_paths_are_present(app) -> None:
    paths = set(app.openapi()["paths"])
    assert {
        "/healthz",
        "/readyz",
        "/auth/register",
        "/auth/login",
        "/auth/logout",
        "/auth/me",
        "/organizations/current",
        "/memberships",
    } <= paths
