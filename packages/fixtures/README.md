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

## End-to-end walkthrough (current app)

Stack up (`just up`), then sign in. Create an org at `/register`, or seed the demo org
(`just seed-demo` → `founder@demo-specialty.example` / `cedeon-demo-password`).

1. **Documents → Choose PDF** → upload `treaty-2027-property-cat-xol.pdf` (kind: *treaty*).
   Wait for status **parsed** (the page auto-refreshes).
2. **Programs** → *Add a cedent* → "Demo Specialty Insurance Co." → *Add a program* →
   cedent = that, name "2027 Property Catastrophe Programme", treaty year 2027.
3. **Treaty library → Create treaty** → program = the one above, name "2027 Property Cat XOL",
   source document = the parsed PDF. Extraction runs on the worker (needs `ANTHROPIC_API_KEY`
   and `ANTHROPIC_WORKSPACE_ID` in `.env`).
4. When the treaty shows **Validate**, open the **validation workspace**. Confirm
   `attachment` (50,000,000), `limit` (20,000,000) and each participation. Then **Validate treaty**.
5. **Loss imports → Choose CSV** → `hurricane-demo-2027-claims.csv`. Open it, map the columns
   (`Claim Ref → claim_id`, `Event → loss_event_identifier`, `Loss Date → date_of_loss`,
   `Paid → gross_paid`, `Reserve → gross_case_reserve`, `Incurred → gross_incurred`,
   `Ccy → currency`, `Peril → cause_of_loss`, `Location → location`), **Validate rows**,
   then **Commit losses** into a new event "Hurricane Demo 2027".
6. **Recovery candidates → New** → validated treaty + that loss event → **Create & calculate**.
   You should see **8,700,000.00** with the 4.35M / 2.61M / 1.74M split.
7. On the candidate: **Investigate** (the read-only AI agent), then **Confirm** the recovery.
8. **Recovery packet → Generate**, review the classified statements, **Approve**.
9. **Notices → Draft a notice** (initial loss advice), review, **Approve**. Cedeon never sends it.

Everything is on the audit trail — see **Activity**.
