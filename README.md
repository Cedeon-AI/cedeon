# Cedeon

**Reinsurance intelligence from contract to recovery.**

Cedeon is the intelligence system for ceded reinsurance. It takes two inputs a
ceded-reinsurance team already has — the **treaty wording** (as PDFs) and the
**loss data** (as claim schedules) — turns the contracts into executable terms,
watches the losses against them, and opens the desk on one ranked queue: recoveries
to review, notices coming due, treaty changes, reinstatement premium owed, figures
that moved, and what doesn't reconcile — each backed by a citation, a deterministic
calculation, and a human decision. Recovery identification is the wedge; the
recovery is then tracked all the way to cash collected.

It sits beside your claims, reinsurance-administration and accounting systems; it
does not replace any of them.

## What it does

```
  treaty PDF ──▶ parse ──▶ AI proposes terms (cited) ──▶ human validates ──▶ executable layer  ┐
  loss CSV   ──▶ map & validate ──▶ immutable claims ──▶ loss event                            ┘
                                                                                               │
                                                                                               ▼
   deterministic recovery ──▶ bounded AI investigation ──▶ evidence-backed packet ──▶ notice draft
                                                                                               │
                                                                                               ▼
                                          collection tracking:  notified ─▶ agreed ─▶ billed ─▶ collected
```

1. **Ingest the contract.** Upload the wording. Cedeon parses it with page, section
   and clause structure intact; an AI pass proposes each term — attachment, limit,
   the notice provision, participations — with an **exact citation** and a confidence
   score. Operational terms a human enters directly (the layer stack, per-layer
   panels, reinstatement rates) never touch a model.
2. **Validate.** A person confirms each term against the wording in a two-pane
   workspace. Only confirmed terms become an executable treaty layer. Nothing an
   LLM produced is trusted until a human signs it.
3. **Ingest the losses.** Map a claims CSV to canonical fields; deterministic
   validation (dates, currency, duplicates, derived incurred); committed rows
   become immutable claim records grouped into a loss event.
4. **Calculate.** A versioned, unit-tested excess-of-loss engine computes the layer
   recovery and each reinsurer's share — exact decimal arithmetic, a full trace,
   re-run when inputs change. **No LLM touches the math.**
5. **Investigate.** A bounded, read-only AI agent explains whether the treaty
   responds and cites the wording — relevant clauses, missing evidence, notice
   obligations. It is handed the deterministic figure as a fact and can never
   emit a rival number.
6. **Package.** An immutable, versioned recovery packet where every line is
   classified `FACT` / `CALCULATION` / `AI INTERPRETATION` / `HUMAN DECISION`,
   printable as a self-contained artifact.
7. **Notify.** A draft initial loss advice, assembled from approved facts only.
   Cedeon stops at *draft* — there is deliberately no send action anywhere.
8. **Collect.** Track each reinsurer's leg from notified → agreed → billed →
   collected, with derived aging and a portfolio view of what is outstanding.

Every state transition, agent run, tool call, token and human decision is on an
append-only audit trail.

### What it watches

Steps 1–8 are the vertical thread. On top of it, Cedeon keeps deriving *what needs a
person today* and groups it on Home:

- **Notice deadlines** — from a validated, structured notice provision, the deadline
  in calendar or business days, counted down. The model never sets a date.
- **Recalculation & drift** — every committed loss re-runs the affected recoveries; a
  figure that moves without a person reverts a confirmed recovery to review.
- **Suggested recoveries** — each validated treaty layer screened against each loss
  event; a recovery proposed where none exists.
- **Aged recoverables** — each leg tracked to cash, aging derived, a deterministic
  next action (chase an acknowledgement, issue the bill, chase payment) per open leg.
- **Contract changes** — an endorsement opens a new treaty version (terms, layers,
  panels copied forward, re-extracted for a term diff); recoveries on the superseded
  version are flagged.
- **Multi-layer programmes & per-layer panels** — a treaty version is a stack of XOL
  layers, each with its own reinsurer panel; a loss opens a recovery on every layer
  it pierces.
- **Reinstatement premium** — deterministic: when a loss erodes a layer, the premium
  due from the deposit premium, the rate per reinstatement, and prior erosion.
- **Hours-clause occurrence view** — an *assistive* grouping of a loss event's claims
  into occurrence windows; the cedent chooses each window's start.
- **Reconciliation** — expected vs agreed vs billed vs collected on a leg, and what a
  reinsurer states vs what Cedeon holds — the material gaps, with the evidence.

Each check is deterministic and concrete. The queue (`app/domain/worklist.py`) is a
*derived read-model* over those objects — not a stored generic "finding".

## Architectural non-negotiables

1. **LLMs interpret. Deterministic code calculates. Humans approve material interpretations and actions.**
2. An LLM is **never** the source of truth for a financial figure. Every extracted term carries provenance (document, page, clause, span, confidence, model) and is human-validated before it can feed a calculation.
3. Money is `Decimal` in Python and `NUMERIC` in PostgreSQL. Never binary floating point. Currency is always explicit.
4. Every uploaded document is **untrusted input**. Document text is data, never instruction.
5. Every financially material output is traceable to `FACT` / `CALCULATION` / `AI INTERPRETATION` / `HUMAN DECISION`.

## Quickstart

Prereqs: Docker, [`uv`](https://docs.astral.sh/uv/), [`pnpm`](https://pnpm.io/), and
[`just`](https://github.com/casey/just) (`brew install just`). Every `just` recipe is
a thin wrapper — run `just --list`.

```bash
cp .env.example .env
just bootstrap        # deps + generate the typed API client
just up               # docker compose: postgres, minio, api, worker, web
just seed-demo        # optional: a synthetic org — sign in, Home opens on a populated queue
# web → http://localhost:3000     api → http://localhost:8000/docs
# (override CEDEON_WEB_PORT / CEDEON_API_PORT in .env if 3000/8000 are taken)
just ci               # lint · typecheck · test · build (the merge gate)
```

To run the AI extraction, add `ANTHROPIC_API_KEY` (and `ANTHROPIC_WORKSPACE_ID` if
your key is workspace-scoped) to `.env`.

**Walk it end to end** with the synthetic data in [`packages/fixtures/`](packages/fixtures/) —
a `$20M xs $50M` treaty and a `$58.7M` hurricane event that yields an
`$8,700,000.00` recovery (`4.35M / 2.61M / 1.74M` split). Step-by-step in
[`packages/fixtures/README.md`](packages/fixtures/README.md); the same path is the
gated `apps/web/e2e/golden-path.spec.ts`.

Without `just`: `cd apps/api && uv sync && uv run pytest`, and
`cd apps/web && pnpm install && pnpm gen:client && pnpm test run && pnpm build`.

## Built with

| | |
| --- | --- |
| **Backend** | FastAPI · SQLAlchemy 2 (async) + Alembic · PostgreSQL + pgvector · Procrastinate (Postgres job queue) · PydanticAI + Anthropic · S3-compatible object storage |
| **Frontend** | Next.js 15 (App Router) · React 19 · TypeScript · Tailwind CSS v4 · TanStack Query · a generated OpenAPI client |
| **Infra** | Docker Compose · GitHub Actions (`ci.yml`, `e2e.yml`) |

The reasoning behind each choice — and the one place the plan changed — is in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/DECISIONS.md](docs/DECISIONS.md).

## Repository layout

```
apps/
  api/        FastAPI backend — domain (pure) · services · repositories · AI · workers
  web/        Next.js frontend — the app + the marketing site
packages/
  fixtures/   Synthetic treaty PDFs + claim CSVs + generator — the end-to-end demo data
  openapi/    The generated OpenAPI document (the frontend contract; CI fails if stale)
infra/        docker-compose, Dockerfiles, deployment config
docs/         Architecture & product documentation
```

The `api/domain` layer is framework-free and dependency-checked (import-linter):
domain ← services ← api, and the calculation engine may import only the `Money`
value object.

## Documentation

| Doc | Purpose |
| --- | --- |
| [docs/PRODUCT.md](docs/PRODUCT.md) | Product vision, scope, users, non-goals, the long-term positioning |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Stack verdict, repo layout, runtime topology, the screen list |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | Entity catalogue, ERD, versioning & immutability rules |
| [docs/AI_ARCHITECTURE.md](docs/AI_ARCHITECTURE.md) | Extraction, retrieval, the Recovery Investigator agent, evals, provider strategy |
| [docs/SECURITY.md](docs/SECURITY.md) | Tenancy, authz, prompt-injection defense, secrets, data handling |
| [docs/UX_STUDY.md](docs/UX_STUDY.md) | The ceded-reinsurance-desk workflow study — findings, the re-framed IA, phasing |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phased build history, current status, what's next |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Architecture Decision Records (ADR-0001 … ADR-0025) |

## Status

The MVP is complete and runs end to end through the containerized stack: treaty →
validated terms → deterministic recovery → AI investigation → evidence-backed
packet → notice draft → collection tracking. On top of it: the attention queue,
multi-layer programmes with per-layer panels, notice deadlines, drift detection,
system-suggested recoveries, aged-recoverable chasing, endorsement re-versioning
with re-extraction + a term diff, reinstatement premium math, an assistive
hours-clause occurrence view, and reconciliation (internal + against reinsurer
statements). **358 backend tests** + `pytest -m eval` extraction & investigator
datasets, a live golden-path e2e, all CI gates green; migrations 0001–0016. What's
next is in [docs/ROADMAP.md](docs/ROADMAP.md); the build history is there and in
`git log`.

## License

Proprietary — see [LICENSE](LICENSE). All rights reserved.
