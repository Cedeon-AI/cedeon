"""Document upload → parse pipeline → pages/chunks/content endpoints."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.audit import AuditEvent
from tests.support.auth import register
from tests.support.pdfs import build_treaty_pdf
from tests.support.pipeline import run_parse

pytestmark = pytest.mark.db


async def _setup(client: AsyncClient, *, email: str = "vp.ceded@atlantic.example") -> UUID:
    reg = await register(client, email=email)
    return UUID(reg["organization"]["id"])


async def _upload(client: AsyncClient, pdf: bytes, *, filename: str = "treaty.pdf") -> dict:
    resp = await client.post(
        "/documents",
        files={"file": (filename, pdf, "application/pdf")},
        data={"kind": "treaty"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestUpload:
    async def test_upload_stores_document_and_enqueues_parse(
        self, client: AsyncClient, parse_calls
    ) -> None:
        await _setup(client)
        pdf = build_treaty_pdf()
        body = await _upload(client, pdf)

        assert body["status"] == "uploaded"
        assert body["kind"] == "treaty"
        assert body["byte_size"] == len(pdf)
        assert len(parse_calls) == 1

        listed = (await client.get("/documents")).json()["documents"]
        assert [d["id"] for d in listed] == [body["id"]]

    async def test_identical_bytes_are_deduplicated(self, client: AsyncClient, parse_calls) -> None:
        await _setup(client)
        pdf = build_treaty_pdf()
        first = await _upload(client, pdf)
        second = await _upload(client, pdf, filename="treaty-copy.pdf")
        assert first["id"] == second["id"]
        assert len(parse_calls) == 1

    async def test_non_pdf_is_rejected(self, client: AsyncClient) -> None:
        await _setup(client)
        resp = await client.post(
            "/documents",
            files={"file": ("notes.txt", b"hello", "text/plain")},
            data={"kind": "correspondence"},
        )
        assert resp.status_code == 422

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/documents",
            files={"file": ("treaty.pdf", build_treaty_pdf(), "application/pdf")},
        )
        assert resp.status_code == 401

    async def test_content_streams_back_the_original_bytes(self, client: AsyncClient) -> None:
        await _setup(client)
        pdf = build_treaty_pdf()
        body = await _upload(client, pdf)
        resp = await client.get(f"/documents/{body['id']}/content")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/pdf")
        assert resp.content == pdf


class TestParsePipeline:
    async def test_parse_produces_pages_and_chunks(
        self, client: AsyncClient, object_store, session
    ) -> None:
        org_id = await _setup(client, email="ops@carrier.example")
        body = await _upload(client, build_treaty_pdf())
        document_id = UUID(body["id"])

        await run_parse(session, object_store, org_id, document_id)

        detail = (await client.get(f"/documents/{document_id}")).json()
        assert detail["document"]["status"] == "parsed"
        assert detail["current_parse"]["status"] == "succeeded"
        assert detail["current_parse"]["parser_name"] == "pymupdf"
        assert detail["current_parse"]["page_count"] == 3

        pages = (await client.get(f"/documents/{document_id}/pages")).json()["pages"]
        assert [p["page_number"] for p in pages] == [1, 2, 3]
        assert "USD 50,000,000" in " ".join(p["text"] for p in pages)

        chunks = (await client.get(f"/documents/{document_id}/chunks")).json()["chunks"]
        assert len(chunks) >= 4
        assert any("ARTICLE IV" in c["section_path"] for c in chunks)
        assert [c["ordinal"] for c in chunks] == list(range(len(chunks)))

    async def test_parse_failure_marks_document_failed(
        self, client: AsyncClient, object_store, session
    ) -> None:
        org_id = await _setup(client, email="fail@carrier.example")
        body = await _upload(client, b"%PDF-1.7 not really a valid pdf body")
        document_id = UUID(body["id"])

        with pytest.raises(Exception):  # noqa: B017
            await run_parse(session, object_store, org_id, document_id)

        detail = (await client.get(f"/documents/{document_id}")).json()
        assert detail["document"]["status"] == "parse_failed"
        assert detail["current_parse"] is None

    async def test_audit_trail(self, client: AsyncClient, object_store, session) -> None:
        org_id = await _setup(client, email="audit@carrier.example")
        body = await _upload(client, build_treaty_pdf())
        await run_parse(session, object_store, org_id, UUID(body["id"]))

        actions = {
            row.action for row in (await session.execute(select(AuditEvent))).scalars().all()
        }
        assert {"document.uploaded", "document.parsed"} <= actions


class TestTenantIsolation:
    async def test_other_org_cannot_read_the_document(self, client_factory) -> None:
        a = await client_factory()
        b = await client_factory()
        await register(a, org="Carrier A", email="a@a.example")
        await register(b, org="Carrier B", email="b@b.example")

        body = await _upload(a, build_treaty_pdf())

        assert (await b.get(f"/documents/{body['id']}")).status_code == 404
        assert (await b.get(f"/documents/{body['id']}/content")).status_code == 404
        assert (await b.get("/documents")).json()["documents"] == []
