"""Endorsements open a new treaty version: the frozen state copies forward, the
old version is superseded, and open recoveries against it surface for re-review."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from tests.support.extraction import golden_extraction, run_extraction
from tests.support.scenario import committed_hurricane_event, validated_golden_treaty

pytestmark = pytest.mark.db


class TestNewVersion:
    async def test_copies_forward_and_supersedes(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)

        resp = await client.post(
            f"/treaties/{golden.treaty_id}/versions",
            json={"note": "Endorsement 3 — revised occurrence limit"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()

        versions = {v["version_no"]: v for v in body["versions"]}
        assert versions[1]["status"] == "superseded"
        assert versions[2]["status"] == "needs_validation"
        assert body["treaty"]["current_version"]["version_no"] == 2

        v2 = body["current_version"]
        assert [(x["attachment"], x["limit"]) for x in v2["layers"]] == [
            ("50000000.00", "20000000.00")
        ]
        assert {p["reinsurer_name"] for p in v2["participations"]} == {
            "Reinsurer Alpha",
            "Reinsurer Beta",
            "Reinsurer Gamma",
        }

    async def test_the_new_version_can_be_edited_and_revalidated(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        v2 = (
            await client.post(
                f"/treaties/{golden.treaty_id}/versions", json={"note": "Endorsement 4"}
            )
        ).json()["current_version"]

        # the endorsement raised the attachment
        await client.put(
            f"/treaties/{golden.treaty_id}/versions/{v2['id']}/layers",
            json={"currency": "USD", "layers": [{"attachment": "60000000", "limit": "20000000"}]},
        )
        validated = await client.post(f"/treaties/{golden.treaty_id}/versions/{v2['id']}/validate")
        assert validated.status_code == 200
        detail = (await client.get(f"/treaties/{golden.treaty_id}")).json()
        assert detail["current_version"]["status"] == "validated"
        assert detail["current_version"]["layers"][0]["attachment"] == "60000000.00"

    async def test_rejects_a_new_version_before_the_current_is_validated(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session, layers=[("5", "5")])
        # open v2 (needs_validation), then try to open v3 on top of it
        await client.post(f"/treaties/{golden.treaty_id}/versions", json={"note": "e1"})
        resp = await client.post(f"/treaties/{golden.treaty_id}/versions", json={"note": "e2"})
        assert resp.status_code == 409

    async def test_requires_a_note(self, client: AsyncClient, object_store, session) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        resp = await client.post(f"/treaties/{golden.treaty_id}/versions", json={"note": "  "})
        assert resp.status_code == 422


class TestContractChangeOnWorklist:
    async def test_a_recovery_on_a_superseded_version_surfaces_as_contract_change(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        event_id = await committed_hurricane_event(client)
        candidate = (
            await client.post(
                "/recovery-candidates",
                json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
            )
        ).json()

        await client.post(f"/treaties/{golden.treaty_id}/versions", json={"note": "Endorsement 5"})

        items = (await client.get("/worklist")).json()["items"]
        change = [i for i in items if i["kind"] == "contract_change"]
        assert len(change) == 1
        assert change[0]["category"] == "contract"
        assert change[0]["href"] == f"/recovery-candidates/{candidate['id']}?section=calculation"
        assert change[0]["amount"] == "8700000.00"


class TestTermDiff:
    async def test_re_extraction_of_an_endorsement_surfaces_the_changed_term(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        detail = (await client.get(f"/treaties/{golden.treaty_id}")).json()
        source_doc = detail["current_version"]["source_document_id"]

        v2 = (
            await client.post(
                f"/treaties/{golden.treaty_id}/versions",
                json={"note": "Endorsement 7 — limit cut", "source_document_id": source_doc},
            )
        ).json()
        v2_id = v2["current_version"]["id"]

        # the endorsement document extracts a lower limit; everything else the same
        endorsed = golden_extraction()
        for term in endorsed.terms:
            if term.key == "limit":
                term.value = "15000000.00"
        await run_extraction(session, get_settings(), golden.org_id, v2_id, extraction=endorsed)

        diff = (
            await client.get(f"/treaties/{golden.treaty_id}/versions/{v2_id}/term-diff")
        ).json()["entries"]
        by_key = {e["key"]: e for e in diff}
        assert by_key["limit"]["carried_value"] == "20000000.00"
        assert by_key["limit"]["extracted_value"] == "15000000.00"
        assert by_key["limit"]["change"] == "changed"
        assert by_key["limit"]["extracted_candidate_id"] is not None
        assert by_key["attachment"]["change"] == "unchanged"
        # notice_provision was never confirmed on v1, so re-extraction surfaces it fresh
        assert by_key["notice_provision"]["change"] == "new"

    async def test_a_version_with_no_endorsement_document_has_no_extracted_side(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        v2 = (
            await client.post(
                f"/treaties/{golden.treaty_id}/versions", json={"note": "Endorsement 8"}
            )
        ).json()
        v2_id = v2["current_version"]["id"]

        diff = (
            await client.get(f"/treaties/{golden.treaty_id}/versions/{v2_id}/term-diff")
        ).json()["entries"]
        assert diff  # the carried-forward terms are listed
        assert all(e["change"] == "not_extracted" for e in diff)
        assert all(e["extracted_value"] is None for e in diff)
