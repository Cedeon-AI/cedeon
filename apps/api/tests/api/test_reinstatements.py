"""A layer with reinstatement terms: a confirmed recovery triggers a deterministic
reinstatement premium, shown on the recovery and owed on the worklist."""

from __future__ import annotations

import csv
import io

import pytest
from httpx import AsyncClient

from tests.support.scenario import committed_hurricane_event, validated_golden_treaty

pytestmark = pytest.mark.db

_LAYER = [("50000000", "20000000")]  # $20M xs $50M — the golden layer
_TERMS = {1: {"deposit_premium": "2000000", "rates": ["1", "1"], "basis": "flat"}}


async def _confirmed_golden_recovery(client: AsyncClient, object_store, session):
    golden = await validated_golden_treaty(
        client, object_store, session, layers=_LAYER, reinstatement_terms=_TERMS
    )
    event_id = await committed_hurricane_event(client)
    candidate = (
        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
        )
    ).json()
    await client.post(
        f"/recovery-candidates/{candidate['id']}/review", json={"decision": "confirm"}
    )
    return golden, candidate["id"]


class TestReinstatementOnRecovery:
    async def test_the_layer_carries_the_terms(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(
            client, object_store, session, layers=_LAYER, reinstatement_terms=_TERMS
        )
        layer = (await client.get(f"/treaties/{golden.treaty_id}")).json()["current_version"][
            "layers"
        ][0]
        assert layer["deposit_premium"] == "2000000.00"
        assert layer["reinstatement_rates"] == ["1", "1"]
        assert layer["reinstatement_basis"] == "flat"

    async def test_a_confirmed_recovery_computes_the_reinstatement_premium(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _golden, candidate_id = await _confirmed_golden_recovery(client, object_store, session)
        detail = (await client.get(f"/recovery-candidates/{candidate_id}")).json()
        r = detail["reinstatement"]
        assert r is not None
        # $8.7M recovery / $20M limit x $2M deposit x 100% = $870,000
        assert r["premium_due"] == "870000.00"
        assert r["prior_erosion"] == "0.00"
        assert r["this_loss_to_layer"] == "8700000.00"
        assert [c["order"] for c in r["charges"]] == [1]
        assert not r["cover_exhausted"]
        assert r["trace"]

    async def test_the_premium_is_owed_on_the_worklist(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _golden, candidate_id = await _confirmed_golden_recovery(client, object_store, session)
        items = (await client.get("/worklist")).json()["items"]
        due = [i for i in items if i["kind"] == "reinstatement_due"]
        assert len(due) == 1
        assert due[0]["category"] == "obligation"
        assert due[0]["amount"] == "870000.00"
        assert due[0]["href"] == f"/recovery-candidates/{candidate_id}?section=calculation"

    async def test_no_terms_means_no_reinstatement_block(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session, layers=_LAYER)
        event_id = await committed_hurricane_event(client)
        candidate = (
            await client.post(
                "/recovery-candidates",
                json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
            )
        ).json()
        detail = (await client.get(f"/recovery-candidates/{candidate['id']}")).json()
        assert detail["reinstatement"] is None

    async def test_a_prior_event_erodes_the_layer_so_the_next_loss_charges_less_of_band_one(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(
            client, object_store, session, layers=_LAYER, reinstatement_terms=_TERMS
        )
        # an earlier, smaller event: $56M gross → $6M to the layer
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Claim Ref", "Event", "Loss Date", "Incurred", "Ccy"])
        w.writerow(["E-1", "EARLY", "2027-02-01", "56000000.00", "USD"])
        uploaded = (
            await client.post(
                "/loss-imports", files={"file": ("e.csv", buf.getvalue().encode(), "text/csv")}
            )
        ).json()
        await client.post(
            f"/loss-imports/{uploaded['id']}/mapping",
            json={
                "mapping": {
                    "claim_id": "Claim Ref",
                    "loss_event_identifier": "Event",
                    "date_of_loss": "Loss Date",
                    "gross_incurred": "Incurred",
                    "currency": "Ccy",
                }
            },
        )
        early = (
            await client.post(
                f"/loss-imports/{uploaded['id']}/commit", json={"event_name": "Early"}
            )
        ).json()["loss_event_ids"][0]
        early_candidate = (
            await client.post(
                "/recovery-candidates",
                json={"treaty_id": golden.treaty_id, "loss_event_id": early},
            )
        ).json()
        await client.post(
            f"/recovery-candidates/{early_candidate['id']}/review", json={"decision": "confirm"}
        )

        # then the golden Hurricane Demo (2027, later) → $8.7M to the layer
        event_id = await committed_hurricane_event(client)
        later = (
            await client.post(
                "/recovery-candidates",
                json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
            )
        ).json()
        detail = (await client.get(f"/recovery-candidates/{later['id']}")).json()["reinstatement"]
        # prior erosion $6M; this loss $8.7M → total $14.7M, still all in band 1
        assert detail["prior_erosion"] == "6000000.00"
        assert detail["this_loss_to_layer"] == "8700000.00"
        assert detail["premium_due"] == "870000.00"  # 8.7M / 20M x 2M
