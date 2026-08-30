# Cedeon — Product

**Reinsurance intelligence from contract to recovery.**

---

## 1. Vision (context, not backlog)

Cedeon is an AI-native reinsurance intelligence and workflow platform. Over time the
reinsurance lifecycle it can serve is:

```
PLACEMENT → CONTRACT → CLAIMS → RECOVERY → SETTLEMENT → RENEWAL → (PLACEMENT)
```

We are **not** building the whole lifecycle now. The vision exists to keep the MVP's
data model and boundaries honest, not to expand scope.

## 2. Initial product — Cedeon Recovery Intelligence

**Value proposition**

> Upload your reinsurance treaties and loss data. Cedeon understands the contracts,
> monitors the losses, identifies potential recoveries, explains why the treaty
> responds, and prepares an evidence-backed recovery package for human review.

**Positioning**

> Cedeon turns reinsurance contracts into executable intelligence and continuously
> identifies the recoveries they create.

Cedeon sits **above and beside** existing systems (claims, reinsurance admin,
accounting, spreadsheets, documents). It does not replace them. It is an
intelligence / control layer that produces **recovery findings + evidence + human
decisions + workflow**.

## 3. Who it is for (MVP)

A P&C carrier with ceded reinsurance and enough treaty / claim complexity that
recoveries, notices, reconciliations, or contract interpretation involve meaningful
manual work.

Likely buyers / users:

- Head of Ceded Reinsurance
- Reinsurance Claims Manager
- Reinsurance Operations Manager
- Reinsurance Accounting leader
- Chief Reinsurance Officer

The exact ICP is a discovery question. **Carrier size is not encoded anywhere in the
architecture.**

## 4. The problem

Reinsurance information is scattered across treaty PDFs, slips, endorsements,
spreadsheets, claims systems, accounting systems, bordereaux, broker correspondence,
email, and institutional memory. The legally operative wording stays trapped in a
document. Operators manually decide: which treaty applies, which layer, whether a
loss attaches, what participation applies, whether notice is required, what evidence
is needed, what recovery is expected, whether it has been collected.

Cedeon makes that information **structured, citation-backed, auditable, deterministic
where money is involved, and continuously actionable.**

## 5. The fundamental principle (non-negotiable)

> **LLMs interpret. Deterministic code calculates. Humans approve material
> interpretations and actions.**

- An LLM may *extract*: "Limit appears to be USD 25,000,000" — with document, page,
  clause, supporting span, confidence, and model/version.
- A human *validates* that interpretation.
- Only then does deterministic state hold `limit = Decimal("25000000.00"), currency = USD`.
- All calculations use validated values only, in versioned, unit-tested,
  deterministic code. Never binary floating point for money.

Calculations that must be deterministic code (never AI): attachment, exhaustion,
amount above attachment, layer recovery, ceded share, reinsurer participation,
allocation, remaining limit, reinstatement premium, reconciliation.

## 6. First end-to-end user flow (the vertical slice)

```
Treaty document
  → parsed structure (pages / sections / chunks, provenance preserved)
  → AI-extracted term candidates (with citations + confidence)
  → human validation  ── only CONFIRMED terms proceed ──▶
  → executable treaty representation (deterministic: attachment, limit, participation)
  → loss CSV import → column mapping → validation → underlying losses
  → loss event (manual / imported identifier)
  → DETERMINISTIC treaty evaluation → Recovery Calculation
  → Recovery Candidate (NEEDS_REVIEW)
  → Recovery Investigator (bounded, read-only AI agent — investigates, does not calculate)
  → Recovery Packet (FACT / CALCULATION / AI INTERPRETATION / HUMAN DECISION, all cited)
  → human review (confirm / edit / reject / request info)
  → notice draft (draft only, never auto-sent, human approval required)
```

Screen-by-screen and API detail: [ARCHITECTURE.md](ARCHITECTURE.md) §7–8.

### Treaty lifecycle (kept deliberately small)

```
DRAFT → PARSING → EXTRACTION_COMPLETE → NEEDS_VALIDATION → VALIDATED → ACTIVE
                                                     └────────────────┐
                          (post-validation change → new TreatyVersion) ┘
```

### Recovery Candidate lifecycle

```
DRAFT → NEEDS_REVIEW → IN_REVIEW → CONFIRMED → NOTICE_DRAFTED
                              └──▶ REJECTED
(inputs change → recalculation → new immutable RecoveryCalculation; candidate may revert to NEEDS_REVIEW)
```

## 7. MVP scope — the one treaty structure

**Simple per-occurrence Excess of Loss (XOL): `$X limit excess of $Y attachment`.**

Example: `$20M xs $50M` → `attachment = 50,000,000`, `limit = 20,000,000`.

```
amount_above_attachment = max(gross_event_loss - attachment, 0)
layer_recovery          = min(amount_above_attachment, limit)
participant_recovery[i]  = round(layer_recovery × validated_share[i])   (penny-allocated to sum exactly)
```

**Explicitly deferred** (design so they can be added without a rewrite; do **not**
build them): quota share / surplus / prop treaties, aggregate XOL, aggregate
deductibles, inuring reinsurance and inuring order, top-and-drop, ECO/XPL, index
clauses, reinstatement waterfalls, hours-clause event clustering, catastrophe event
grouping, commutation / sunset, multi-treaty optimisation, retrocession chains,
multi-currency / FX conversion.

MVP currency rule: **treaty currency must equal loss currency** or the candidate is
flagged `CURRENCY_MISMATCH` and no calculation runs.

## 8. MVP non-goals (stop if drifting toward these)

Marketplace · broker portal · reinsurer portal · automated placement · quote
negotiation · full reinsurance administration · full premium accounting · Schedule F ·
assumed reinsurance · retrocession · collateral management · cat modeling · automated
settlement / payment · autonomous notice sending · portfolio optimisation · dozens of
treaty structures · many-agent systems · Kubernetes · Kafka · microservices · a
generalised MCP ecosystem · multi-region deployment.

## 9. Future products (conceptual only — do not build)

| Name | Scope |
| --- | --- |
| Cedeon Recover | Recovery identification, notification, tracking (this is the MVP's home) |
| Cedeon Treaty | Contract / treaty intelligence and comparison |
| Cedeon Renew | Renewal intelligence from historical contract + recovery performance |
| Cedeon Place | Placement preparation and quote intelligence |
| Cedeon Market | Reinsurer appetite / behaviour intelligence |

Rough sequence: (1) Treaty + Recovery Intelligence → (2) Recovery Operations →
(3) Event / Notice Intelligence → (4) Renewal Intelligence → (5) Placement Copilot →
(6) Private Market Intelligence → (7) *maybe* connectivity / marketplace. Cedeon does
not have to become a marketplace; a software / intelligence business may be superior.

## 10. First meaningful success criterion

> A reinsurance professional can upload a real-shaped XOL treaty and loss dataset,
> validate Cedeon's extracted terms, and Cedeon correctly identifies and explains a
> potential recovery using exact treaty citations and deterministic calculations.

Not "we built an agent platform." Everything optimises toward the sentence above.

## 11. Synthetic demo / golden data

Clearly synthetic until real customer data exists. Lives in `packages/fixtures/` and
drives an automated end-to-end test.

| Item | Value |
| --- | --- |
| Cedent | Demo Specialty Insurance Co. |
| Program | 2027 Property Cat Program |
| Treaty | `$20M xs $50M` per-occurrence XOL, USD |
| Participation | Reinsurer Alpha 50% · Reinsurer Beta 30% · Reinsurer Gamma 20% |
| Loss event | Hurricane Demo (2027) |
| Gross event incurred | `58,700,000.00` |
| **Layer recovery (deterministic)** | **`8,700,000.00`** |
| Allocation | Alpha `4,350,000.00` · Beta `2,610,000.00` · Gamma `1,740,000.00` |

The synthetic treaty fixture contains declarations, dates, retention, limit, covered
business/perils, event definition, notice provision, and participation — enough for a
realistic extraction + validation exercise.
