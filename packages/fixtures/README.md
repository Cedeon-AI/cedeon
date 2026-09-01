# Demo fixtures

Synthetic, clearly-fake reinsurance data for walking Cedeon end to end. Regenerate with:

```bash
cd apps/api && uv run python ../../packages/fixtures/generate_fixtures.py
```

| File | What it is |
| --- | --- |
| `treaty-2027-property-cat-xol.pdf` | Minimal 3-page wording. The exact text extraction is tuned and tested against — use this for a **guaranteed-clean** run. |
| `reinsurance-contract-2027.pdf` | A fuller 5-page contract (definitions, hours clause, reinstatement, exclusions, currency, schedule of reinsurers). More realistic; better for showing off extraction + the investigator. Same key terms. |
| `hurricane-demo-2027-claims.csv` | 10 hurricane claims, all USD, gross incurred sums to **58,700,000.00**. Header row uses non-canonical names so you exercise column mapping. |
| `messy-claims-example.csv` | 7 rows that trip every validation rule (duplicate claim id, unparseable date, negative amount, missing incurred, `$`/comma formatting, a second currency, reported-before-loss). Use it to see the validation report. |

## The golden numbers

```
Layer:            USD 20,000,000 excess of USD 50,000,000
Reinsurers:       Alpha 50%  ·  Beta 30%  ·  Gamma 20%
Event:            HURR-DEMO-2027, gross incurred 58,700,000.00
Layer recovery:   min(58,700,000 - 50,000,000, 20,000,000) = 8,700,000.00
Allocation:       Alpha 4,350,000.00  ·  Beta 2,610,000.00  ·  Gamma 1,740,000.00
```

## The fastest way in

`just up`, then `just seed-demo`. Sign in as `founder@demo-specialty.example` /
`cedeon-demo-password`. **Home** opens on a populated worklist — a notice deadline, a
recovery to review, an overdue recoverable — with the golden `$8.7M` recovery, its
`4.35 / 2.61 / 1.74M` split, and three reinsurer legs already tracked. No AI key needed.

## End-to-end walkthrough (build it yourself)

Start from a fresh org at `/register`, then:

1. **Set up a treaty** (Home → *Set up a treaty*, or `/treaties/new`) → upload
   `treaty-2027-property-cat-xol.pdf` → cedent "Demo Specialty Insurance Co." and
   programme "2027 Property Cat Program" inline → **Create & extract**. Extraction runs
   on the worker (needs `ANTHROPIC_API_KEY` + `ANTHROPIC_WORKSPACE_ID` in `.env`).
2. In the **validation workspace**, confirm `attachment` (50,000,000), `limit`
   (20,000,000) and each participation, then **Validate treaty**.
3. On **Treaty detail**, fill in the **Notice provision** — e.g. 30 days from *date of
   knowledge*, calendar — so Cedeon can compute the notice deadline.
4. **Start a recovery** (Home → *Start a recovery*) → name the event "Hurricane Demo
   2027", peril + hours clause → drop `hurricane-demo-2027-claims.csv`, map the columns
   (the guesser gets most of them), **Validate rows**, **Commit** → pick the validated
   treaty → **Calculate**. You should see **8,700,000.00** with the split.
5. In the recovery workspace: **Investigate** (the read-only AI agent), then **Confirm**.
   The **Notice** section now shows the computed deadline.
6. **Packet** → Generate, review the classified statements, **Approve**.
7. **Notice** → Draft an initial loss advice, review, **Approve**. Cedeon never sends it.
8. **Collection** → Start tracking, then move each reinsurer leg toward collected.

Commit more claims into the same event and watch the recovery **drift** back onto the
queue. Everything is on the audit trail — see **Audit log**.

### Going further with the same fixtures

- **Multi-layer** — on Treaty detail (before validating), use the **Layer stack**
  editor to enter e.g. `$5M xs $50M` / `$20M xs $55M` / `$25M xs $75M`, then give the
  top layer its own **panel** and the whole tower a **reinstatement** rate. One
  Hurricane Demo commit opens a recovery on every pierced layer, grouped as a
  *programme* on the Recoveries list, with the reinstatement premium on the workspace.
- **Endorsement** — on a validated treaty, **New version** with a source document
  re-runs extraction; the validation workspace shows a **term diff**.
- **Hours clause** — on the loss event, set a 72-hour clause and import claims that
  span more than three days to see the **occurrence proposal** split the event.
- **Statements** — under Recoveries → **Statements**, enter a reinsurer's stated
  agreed / paid figures below what Cedeon calculated and watch the discrepancy land on
  the queue.
