# Cedeon — Architecture

Status: Phase 0 review complete. This document is the source of truth for structure
and stack. Decisions with meaningful trade-offs are recorded in
[DECISIONS.md](DECISIONS.md).

---

## 1. Architecture verdict

**PARTIALLY AGREE.**

The proposed product and architecture are unusually well-considered. ~85% is adopted
as-is. The core principles — *LLM interprets / code calculates / humans approve*,
provenance-first extraction, `Decimal`/`NUMERIC` money, monorepo, FastAPI as the one
backend (no NestJS), pgvector instead of a separate vector DB, REST + generated TS
client (no GraphQL), Postgres as system of record with selective JSONB, no
Kubernetes / Kafka / microservices, one agent framework — are all **correct for this
domain and adopted**.

### The one material change: defer Temporal

**Do not run Temporal in the MVP.** For Phases 1–9 the "workflows" are either short
(parse a document, run an extraction, run a calculation) or they are a *human waiting*
(`treaty.status = NEEDS_VALIDATION`). A durable execution engine is not needed to
model "a row stays in state X until a person changes it" — that is a database state
plus a UI queue plus an append-only audit trail.

Temporal's real cost: a stateful service (or Temporal Cloud dependency + billing +
auth), a separate worker deployment, workflow-versioning discipline, and a
non-trivial programming model — paid up front for benefits we will not use yet.

**MVP replacement:**

1. **Explicit state machines on domain entities** (`TreatyVersion.status`,
   `LossImport.status`, `RecoveryCandidate.status`) with one `AuditEvent` per
   transition. This *is* the workflow, and it is debuggable SQL.
2. **[Procrastinate](https://procrastinate.readthedocs.io/)** for background jobs
   (document parse, chunk, embed, extract, investigate, render packet). Postgres-backed
   — no Redis, no broker, no new infra. Jobs enqueue transactionally with domain
   writes; `LISTEN/NOTIFY` + `FOR UPDATE SKIP LOCKED` for dispatch; built-in retries,
   backoff, and a job table for visibility. (`arq` was the other candidate but is now
   maintenance-only.)
3. **Idempotency** on every job (keyed by entity + input hash) so retries are safe.

Revisit Temporal at **Phase 10**, and only if genuinely long, multi-party,
compensating workflows appear (settlement reconciliation across weeks, notice chains
with reinsurer acknowledgements, saga-style rollback). The job interface is defined so
this swap does not touch domain or API code. See [ADR-0007](DECISIONS.md).

### Other refinements (not disagreements)

| # | Area | Refinement |
| --- | --- | --- |
| 1 | **Docling** | Adopt behind `DocumentParser`, but run it **only in the worker** (heavy VLM deps — Granite-Docling, PyTorch). Pre-bake models into the worker image; never download at runtime. Ship a cheap `PyMuPDFParser` (digital-text PDFs, page map) as the fallback and as the *first* parser to prove the loop in Phase 2; add Docling within Phase 2. OCR via `ocrmypdf`/Tesseract behind the same interface; never OCR a document that already has a reliable text layer. See [ADR-0005](DECISIONS.md). |
| 2 | **Retrieval** | pgvector with `halfvec` + HNSW. Add **hybrid** retrieval early (Postgres FTS + vector, reciprocal-rank fusion) because citation quality is the product. This is a Phase 3 concern, not Phase 1. See [ADR-0006](DECISIONS.md). |
| 3 | **Extraction ≠ agent** | Treaty term extraction is a **single typed structured-output call** (PydanticAI `output_type`), not a tool-loop agent. The agent/tool abstraction is reserved for the Recovery Investigator. Keeps extraction cheap, deterministic in shape, and easy to eval. |
| 4 | **Single public origin** | The browser talks only to Next.js. A runtime catch-all route handler (`app/api/[...path]/route.ts`) proxies `/api/*` to FastAPI over the private network — runtime, not a build-time rewrite, so one image works across environments. FastAPI is not publicly exposed in production. One origin → simple `SameSite=Lax` httpOnly session cookies, no CORS, no cross-site cookie pain. The generated TS client points at same-origin `/api`; server components call the API directly via `getSession()`. See [ADR-0004](DECISIONS.md). |
| 5 | **Money value object** | A `Money(amount: Decimal, currency: str)` value object; a bare `Decimal` never crosses a domain boundary as money. Currency mismatch is a hard error in MVP (no FX). Allocations use largest-remainder penny distribution so participant shares sum **exactly** to the layer recovery. |
| 6 | **Auth** | Email + password (`argon2id`) + server-side sessions in Postgres. No hand-rolled crypto, no external IdP yet. `User.password_hash` is nullable so SSO/SAML (WorkOS) links in later without a migration of meaning. Enterprise reinsurance buyers *will* require SSO — the model allows it, we don't build it now. |
| 7 | **Observability** | OpenTelemetry + structured JSON logs + correlation IDs from **Phase 1** (cheap early, painful to retrofit). Export to a hosted backend (or Sentry + logs) — do not self-host Grafana/Tempo for MVP. AI cost/latency/tokens are just columns on `agent_runs` (Phase 3). |
| 8 | **Calc engine tests** | Golden tables **and** property-based tests (Hypothesis): recovery ∈ `[0, limit]`; recovery is monotonic non-decreasing in gross loss; allocations sum to layer recovery exactly; zero/negative inputs rejected. See [DATA_MODEL.md](DATA_MODEL.md) §6. |

---

## 2. Stack (decided)

### Backend — `apps/api`

| Concern | Choice | Notes |
| --- | --- | --- |
| Language | Python 3.12+ | `uv` for env + deps + lockfile |
| Web framework | FastAPI | The **one** backend. OpenAPI is the frontend contract. |
| Models / validation | Pydantic v2 | Shared between API I/O, AI outputs, domain DTOs |
| ORM | SQLAlchemy 2.x (async, `asyncpg`) | Thin repositories; domain layer is ORM-agnostic |
| Migrations | Alembic | From commit 1. No manual DDL, ever. |
| Background jobs | Procrastinate | Postgres-backed. See §1. |
| AI framework | PydanticAI (v2) | `output_type`, `instructions`, `@agent.tool`, `deps_type`/`RunContext`, provider strings. One framework only. See [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md). |
| AI evals | Pydantic Evals | Regression datasets, not vibes. |
| Documents | Docling (worker) + PyMuPDF fallback + `ocrmypdf` | Behind `DocumentParser`. |
| Lint / format | Ruff | |
| Types | mypy (`--strict` on `domain/`, pragmatic elsewhere) | |
| Tests | pytest, pytest-asyncio, httpx, Hypothesis, testcontainers (Postgres) | |

### Frontend — `apps/web`

| Concern | Choice | Notes |
| --- | --- | --- |
| Framework | Next.js 15 (App Router), React 19, TypeScript strict | Next 16 acceptable; 15 is the conservative default. |
| Styling | Tailwind CSS + shadcn/ui | |
| Server state | TanStack Query | Against same-origin `/api` |
| Forms | React Hook Form + Zod | |
| API client | `@hey-api/openapi-ts` (types + TanStack Query hooks) | Generated from FastAPI OpenAPI. **No hand-written DTOs.** |
| Animation | `motion` (Framer Motion) — **marketing route group only** | Kept out of the app bundle via `(marketing)` / `(app)` route groups |
| Lint / format | Biome (or ESLint + Prettier if preferred) | |
| Tests | Vitest + React Testing Library; Playwright for E2E | |
| Package manager | pnpm | |

### Data & infra

| Concern | Choice |
| --- | --- |
| Database | PostgreSQL 16+ with `pgvector` (`halfvec`, HNSW) + `pg_trgm` / FTS |
| Object storage | S3-compatible behind an `ObjectStore` interface — MinIO in dev, AWS S3 in prod. Signed URLs only. |
| Local dev | Docker Compose: `postgres`, `minio`, `api`, `worker`, `web` |
| Secrets | Env provider locally; AWS Secrets Manager in prod. Never in source. |

### Production (initial — no Kubernetes)

| Component | Target |
| --- | --- |
| Web (Next.js) | Vercel **or** ECS/Fargate (see [ADR-0004](DECISIONS.md)); single public origin |
| API + worker | AWS ECS/Fargate (two services, one image or two) |
| Database | AWS RDS for PostgreSQL |
| Files | AWS S3 |
| Secrets | AWS Secrets Manager |
| Durable workflows | *None for MVP.* Temporal Cloud considered at Phase 10. |

---

## 3. Repository layout

One repository. `apps/` for deployables, `packages/` for shared cross-language
fixtures, everything else supporting.

```
/
├── apps/
│   ├── api/
│   │   ├── app/
│   │   │   ├── main.py                 # FastAPI app factory, lifespan, OTel wiring
│   │   │   ├── api/
│   │   │   │   ├── routes/             # thin HTTP handlers, one module per resource
│   │   │   │   ├── dependencies/       # auth, current org/user, db session, pagination
│   │   │   │   └── errors.py           # problem+json error model
│   │   │   ├── core/
│   │   │   │   ├── config.py           # pydantic-settings
│   │   │   │   ├── ids.py              # UUIDv7
│   │   │   │   ├── security/           # argon2 password hashing, session tokens
│   │   │   │   ├── logging.py          # structlog + correlation ids
│   │   │   │   └── telemetry.py        # OpenTelemetry setup
│   │   │   ├── domain/                 # PURE. no FastAPI, no SQLAlchemy, no AI, no HTTP.
│   │   │   │   ├── money.py            # Money value object + exact allocation
│   │   │   │   ├── organizations/      # Role enum + authz rank
│   │   │   │   ├── audit/              # ActorType, AuditRecord
│   │   │   │   ├── documents/          # parsed-doc types · heading-aware chunk_document()
│   │   │   │   ├── treaties/           # (Phase 3)
│   │   │   │   ├── losses/             # (Phase 5)
│   │   │   │   ├── recoveries/
│   │   │   │   │   └── calculations/   # XOL engine — pure functions, ENGINE_VERSION (Phase 4)
│   │   │   │   └── reviews/            # (Phase 8)
│   │   │   ├── services/               # orchestration; e.g. document_pipeline (parse→chunk)
│   │   │   ├── repositories/           # SQLAlchemy queries; every query org-scoped
│   │   │   ├── ai/                     # (Phase 3+) agents · extraction · tools · prompts · evals
│   │   │   ├── parsing/                # DocumentParser: PyMuPDFParser (+ Docling stub, OCR later)
│   │   │   ├── storage/                # ObjectStore: FilesystemObjectStore (dev) · S3ObjectStore
│   │   │   ├── jobs/                   # Procrastinate app + tasks (ping · parse_document)
│   │   │   ├── scripts/                # export_openapi, seed_demo
│   │   │   ├── integrations/           # (later) future external adapters, ACORD
│   │   │   └── db/
│   │   │       ├── models/             # SQLAlchemy ORM models
│   │   │       ├── base.py · session.py
│   │   │       └── migrations/         # Alembic (0001 identity+audit · 0002 documents)
│   │   ├── tests/
│   │   │   ├── domain/                 # money + chunking (+ Phase 4 calc golden/property)
│   │   │   ├── parsing/ · storage/     # PyMuPDF parser · filesystem object store
│   │   │   ├── api/                    # auth, tenancy, roles, audit, contract, documents
│   │   │   └── e2e/                    # (Phase 6) the vertical-slice golden test
│   │   ├── pyproject.toml · uv.lock
│   │   └── alembic.ini
│   └── web/
│       ├── src/
│       │   ├── app/
│       │   │   ├── (marketing)/        # landing page — animation (`motion`) lives here only
│       │   │   ├── (app)/              # authenticated product (server auth guard in layout)
│       │   │   │   └── dashboard/      # + programs/ treaties/ loss-imports/ recovery-candidates/ (Phase 2+)
│       │   │   ├── login/ · register/
│       │   │   ├── api/[...path]/      # runtime reverse proxy → FastAPI (ADR-0004)
│       │   │   └── globals.css         # Tailwind v4 tokens (light + dark)
│       │   ├── components/             # ui/ · auth/ · app/ · marketing/
│       │   └── lib/
│       │       ├── api/generated/      # generated client — do not edit, git-ignored
│       │       ├── api/index.ts · runtime-config.ts
│       │       ├── session.ts          # server-side getSession()
│       │       └── utils.ts
│       ├── tests/ · e2e/
│       ├── openapi-ts.config.ts · biome.json · next.config.ts
│       └── package.json · pnpm-lock.yaml
├── packages/
│   ├── openapi/openapi.json            # committed contract snapshot (drift-checked in CI)
│   └── fixtures/                       # (Phase 3+) synthetic treaty, loss CSVs, golden JSON
├── infra/
│   ├── docker-compose.yml              # postgres · minio · api · worker · web
│   ├── api.Dockerfile                  # also the worker image (ML deps added in Phase 2)
│   └── web.Dockerfile                  # Next standalone
├── .github/workflows/                  # ci.yml (api · web · contract) · e2e.yml
├── docs/
├── justfile                            # up · migrate · test · lint · typecheck · gen-client · ci
└── README.md
```

**Layering rule (pragmatic, not dogmatic Clean Architecture):**

```
api/routes  →  services  →  domain            (domain never imports up)
                 │            ↑
             repositories ────┘  (repositories return/accept domain objects)
                 │
             db/models (SQLAlchemy)

ai/, parsing/, storage/, jobs/  are infrastructure: services depend on their
interfaces, domain does not depend on them at all.
```

`domain/` — and especially `domain/recoveries/calculations/` — imports **only** the
standard library, `decimal`, and Pydantic. No FastAPI, no SQLAlchemy, no PydanticAI,
no HTTP. Enforced by an import-linter contract in CI.

---

## 4. Runtime topology (MVP)

```
                    ┌────────────────────────────────────────────┐
   Browser  ──────▶ │  Next.js (single public origin)            │
                    │   (marketing)  +  (app)                    │
                    │   proxies /api/* ──────────┐               │
                    └────────────────────────────┼───────────────┘
                                                 │ private network
                    ┌────────────────────────────▼───────────────┐
                    │  FastAPI  (ECS service: api)               │
                    │   auth · CRUD · enqueue jobs · read models │
                    └───┬───────────────┬───────────────┬────────┘
                        │               │               │
              ┌─────────▼───┐   ┌───────▼────────┐  ┌────▼─────────┐
              │ PostgreSQL  │   │ Object store   │  │ Procrastinate│
              │ + pgvector  │   │ (S3 / MinIO)   │  │ job table    │
              └─────────▲───┘   └───────▲────────┘  └────┬─────────┘
                        │               │               │ LISTEN/NOTIFY
                    ┌───┴───────────────┴───────────────▼────────┐
                    │  Worker (ECS service: worker)              │
                    │   Docling parse · chunk · embed ·          │
                    │   treaty extraction · Recovery Investigator│
                    │   · packet render                          │
                    │   └─▶ LLM providers (Anthropic/OpenAI/Google)│
                    └───────────────────────────────────────────┘
```

Two deployables from largely one codebase: `api` (lean image) and `worker` (api +
ML deps + pre-baked models). Both share `apps/api/app`.

---

## 5. API strategy

- **REST**, resource-oriented. FastAPI's OpenAPI document is the contract.
- TypeScript types + TanStack Query hooks generated by `@hey-api/openapi-ts`
  (`just gen-client`). CI fails if generated output is stale.
- Errors: RFC 9457 `application/problem+json` with a stable `type` slug.
- Every mutating endpoint accepts an `Idempotency-Key` header where a retry could
  double-write (imports, calculations, notice drafts).
- No GraphQL.
- Tenant scope comes from the **session**, never from a request body or query param.

Resource sketch (semantics finalised per phase):

```
POST   /auth/login · /auth/logout · GET /auth/me
GET    /organizations/current · POST /memberships (invite)
CRUD   /cedents · /programs · /reinsurers · /brokers
POST   /treaties                          create shell
POST   /treaties/{id}/documents           upload → parse job
GET    /treaties/{id}                     overview + status
GET    /treaties/{id}/document            pages/chunks for the viewer
GET    /treaties/{id}/term-candidates     AI output for validation workspace
POST   /treaties/{id}/term-candidates/{cid}/review   confirm|edit|reject|ambiguous
POST   /treaties/{id}/validate            NEEDS_VALIDATION → VALIDATED (guard: all material terms resolved)
GET    /treaties/{id}/terms · /layers · /participations   validated, executable
POST   /loss-imports                      upload CSV
POST   /loss-imports/{id}/mapping         customer col → canonical field
POST   /loss-imports/{id}/validate        → import report
POST   /loss-imports/{id}/commit          → underlying_losses
CRUD   /loss-events ;  POST /loss-events/{id}/losses  (attach)
POST   /recovery-candidates               (treaty, loss_event) → deterministic calc → candidate   [Phase 6]
GET    /recovery-candidates?status=needs_review                                                   [Phase 6]
GET    /recovery-candidates/{id}          calc + allocations + calculation/review history          [Phase 6]
POST   /recovery-candidates/{id}/recalculate      re-run engine; new immutable calc iff inputs changed  [Phase 6]
POST   /recovery-candidates/{id}/review           confirm|reject|request_info                      [Phase 6]
POST   /recovery-candidates/{id}/investigate     enqueue Recovery Investigator                     [Phase 7]
GET    /recovery-candidates/{id}/packet ; POST .../packet (regenerate)
POST   /recovery-packets/{id}/versions/{v}/review
POST   /recovery-candidates/{id}/notices           draft only
GET    /audit-events?entity_type=&entity_id=
```

---

## 6. Financial calculation module

Location: `apps/api/app/domain/recoveries/calculations/`.

- Pure functions and frozen dataclasses / Pydantic models. No I/O, no AI, no ORM.
- `ENGINE_VERSION` semver constant. Bumped on any behavioural change.
- Public surface for MVP:

```python
def calculate_xol_recovery(
    gross_loss: Money, attachment: Money, limit: Money
) -> XolRecoveryResult: ...

def allocate_recovery(
    layer_recovery: Money, participations: Sequence[Participation]
) -> list[Allocation]: ...   # penny-allocated; sum == layer_recovery exactly
```

- Every `RecoveryCalculation` persisted row stores: `engine_version`,
  `treaty_version_id`, `treaty_layer_id`, all inputs, all intermediate steps
  (`trace` JSONB), an `input_hash`, and `created_at`. Recalculation = **new row**,
  never mutation.
- Mandatory tests: loss below / at / inside / exactly exhausting / above the layer;
  zero values; negative values rejected; participation sums validated; rounding;
  allocation sum-exactness; Hypothesis properties.

**No AI in this module. Ever.**

---

## 7. Frontend screens (MVP)

| # | Screen | Purpose |
| --- | --- | --- |
| 0 | **Marketing / landing** | `(marketing)` route group. Visually rich, animated (`motion`). The only place animation libs load. |
| 1 | Dashboard | Treaties, active programs, loss events, recovery candidates, needs-review queue, outstanding notices |
| 2 | Programs | List / manage reinsurance programs |
| 3 | Treaty Library | Treaty · version · effective dates · status · validation state |
| 4 | Treaty Detail | Overview · Validated Terms · Document · Participants · Layers · Evidence · Audit |
| 5 | **Treaty Validation Workspace** | **The critical screen.** Left: treaty page. Right: term candidate (value, confidence, page, clause, exact evidence span). Actions: Confirm / Edit / Reject / Ambiguous. Only confirmed terms feed calculations. |
| 6 | Loss Imports | CSV upload · column mapping · validation report |
| 7 | Loss Events | Aggregated underlying losses |
| 8 | Recovery Candidates | Queue by status (Needs Review / Confirmed / Rejected / Notice Drafted) |
| 9 | Recovery Candidate Detail | Deterministic calculation · treaty/layer · underlying losses · AI investigation · citations · missing evidence · notice obligations · human decision |
| 10 | Recovery Packet | Audit-friendly artifact. HTML first; PDF export later. FACT / CALCULATION / AI INTERPRETATION / HUMAN DECISION visually distinct. |
| 11 | AI / Audit Detail | What model ran · prompt version · tools invoked · evidence · AI output · human edits. Enough to explain a decision — **not** an AgentOps product. |

Design language: calm, dense, and legible — this is a review tool for financial
professionals. Every AI-authored statement in the UI is visually badged and carries
its citation. Light and dark themes.

---

## 8. ACORD

Cedeon has its **own canonical domain model**. ACORD GRLC interoperability is a
**future adapter** (`app/integrations/acord/`), not an internal schema. We do not
implement the full standard, and we do not copy ACORD's external schema into domain
entities. Key entities carry an optional `external_refs` JSONB for later mapping
(bordereaux IDs, ACORD IDs, broker system keys) without schema churn. See
[ADR-0008](DECISIONS.md).

---

## 9. What we explicitly are NOT doing in MVP

Kubernetes · Kafka / event bus · microservices · a second backend language · GraphQL ·
a separate vector database · Temporal (deferred to Phase 10) · Celery · multiple agent
frameworks · a model gateway · autonomous financial decisions · autonomous notice
sending · speculative caching · multi-currency / FX · multi-region.

If implementation starts drifting toward any of these: **stop.**
