# Cedeon — Architecture

Status: the stack below is **built and running** (10-phase MVP + the intelligence
layers, migrations 0001–0016). This document is the source of truth for structure and
stack; §1 records the original Phase-0 verdict, everything since is in
[ROADMAP.md](ROADMAP.md). Decisions with meaningful trade-offs are in
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
| 6 | **Auth & team** | Email + password (`argon2id`) + server-side sessions in Postgres. `Organization ← Membership → User` (membership is first-class; a user has no `organization_id` and may hold more than one membership). Roles `admin` / `member` (`viewer` reserved). Adding people is an **email invitation** → accept (token HMAC'd, expiring, single-use, bound to the invited email). `User.password_hash` nullable so SSO/SAML links in later without a migration of meaning. Last-admin protection replaces a sacred owner. See ADR-0026. |
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
| Styling | Tailwind CSS v4 (`@theme` tokens, light + dark) + hand-rolled shadcn-style primitives in `components/ui/` | Tokens in `globals.css`: surfaces, elevation, gradients, the four trust colours (`fact`/`calculation`/`ai`/`human`). See ADR-0023. |
| Primitives | Radix UI (`@radix-ui/react-{accordion,tabs,slot,dialog}`), `lucide-react` icons, `clsx` + `tailwind-merge` (`cn`) | ADR-0023. |
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

### Deployment

The demo runs on **Render** from one committed blueprint; **AWS ECS/RDS/S3** is the
growth target — same Docker images, no topology change. See
[ADR-0027](DECISIONS.md), [`infra/render.yaml`](../infra/render.yaml), and the
runbook in [DEPLOYMENT.md](DEPLOYMENT.md).

| Component | Demo (Render) | Growth (AWS) |
| --- | --- | --- |
| Web (Next.js) — the single public origin | Render Web Service | ECS/Fargate |
| API + worker (private) | Render Private Service + Background Worker | ECS/Fargate (two services) |
| Database | Render Postgres | RDS for PostgreSQL |
| Files | AWS S3 (from day one) | AWS S3 |
| Email | Amazon SES (from day one) | Amazon SES |
| Secrets | Render env groups | AWS Secrets Manager |
| Durable workflows | *None for MVP.* Temporal Cloud considered at Phase 10. | |

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
POST   /auth/register · /auth/login · /auth/logout · GET /auth/me
GET    /organizations/current · PATCH /organizations/current (rename, admin)
GET    /memberships · PATCH /memberships/{user_id} (role) · DELETE /memberships/{user_id}   admin
POST   /invitations · GET /invitations · POST /invitations/{id}/{resend|revoke}             admin
GET    /auth/invitation/{token} (preview) · POST /auth/invitation/{token}/accept           public
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
POST   /recovery-candidates/{id}/investigate     enqueue Recovery Investigator (bounded, read-only)  [Phase 7]
GET    /recovery-candidates/{id}/agent-runs/{run}/tool-calls   investigator tool-call log            [Phase 7]
GET    /recovery-candidates/{id}/packet ; POST .../packet (regenerate)
POST   /recovery-packets/{id}/versions/{v}/review
POST   /recovery-candidates/{id}/notices           draft only
GET    /activity/agent-runs · /agent-runs/{id} · /audit · /ai-spend          observability   [Phase 10]

# --- the intelligence layers on top of the spine ---
GET    /worklist                                  the ceded-desk attention queue (derived, category-grouped)
GET    /recovery-candidates                        also returns programmes[] (multi-layer siblings grouped)
GET    /recovery-candidates/{id}                   also returns siblings[] + reinstatement (computed on read)
PUT    /treaties/{id}/versions/{v}/layers                       set the XOL layer stack (pre-validation)
PUT    /treaties/{id}/versions/{v}/layers/{n}/participations    a layer's own reinsurer panel
PUT    /treaties/{id}/versions/{v}/layers/{n}/reinstatement-terms   deposit premium · rates · basis
PUT    /treaties/{id}/versions/{v}/notice-term                  structured notice provision → computed deadline
POST   /treaties/{id}/versions                     open a new version from an endorsement doc → re-extraction
GET    /treaties/{id}/versions/{v}/term-diff        carried-forward vs re-extracted (unchanged/changed/new)
GET    /recoverables · POST /recovery-candidates/{id}/recoverables · POST /recoverables/{id}   collection tracking
GET    /loss-events/{id}/occurrence-proposal        assistive hours-clause grouping (proposes; human confirms)
GET|POST /reinsurer-statements · POST /{id}/lines/{n}/resolve   reconcile stated figures vs what Cedeon holds
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
| 0 | **Marketing / landing** | `(marketing)` route group: sticky nav + 4-column footer, a hero with an HTML product mockup (the attention queue), and sections for the queue's four categories, what Cedeon watches, how-it-works, platform, "recovery is module one" (the layer arc), who-it's-for, a Cedeon vs manual-review vs generic-assistant comparison, the worked `$8.7M` example, security, "what Cedeon is not", FAQ. Plus `/security` and `/about`. Animated (`motion`) — the only place animation libs load. |
| 1 | **Home** | The ceded-reinsurance desk's **attention queue** — one ranked "Needs you" list grouped by category (Recovery / Obligations / Contract / Exceptions), plus at-a-glance figures. A derived read-model over `GET /worklist`. |
| 2 | Programs | List / manage reinsurance programs |
| 3 | Treaties | Treaty · version · status · validation state |
| 4 | Treaty Detail | Layers (the XOL tower) · Participants · per-layer panels · reinstatement terms · notice provision editor · version history · Validated Terms · Source document |
| 5 | **Treaty Validation Workspace** | **The critical screen.** Left: treaty page. Right: term candidates (value, confidence, page, clause, exact span) + a "What the endorsement changed" term-diff card on a re-extracted version. Actions: Confirm / Edit / Reject / Ambiguous. Only confirmed terms feed calculations. |
| 6 | Loss Imports | CSV upload · column mapping · validation report |
| 7 | Loss Event Detail | Claim schedule · occurrence basis · "Treaties that may respond" · an assistive **hours-clause view** (proposed occurrence windows) |
| 8 | Recoveries | The queue by status, plus a **Programmes** card grouping the sibling layers a multi-layer loss opens |
| 9 | **Recovery Workspace** | One page, left rail — Loss basis · Calculation (+ reinstatement premium, drift banner) · Investigation · Packet · Notice · Collection — sections open in place via `?section=`. A "Layer N of M" strip links siblings. |
| 10 | Recovery Packet | Audit-friendly artifact (embedded in the workspace + a printable HTML). FACT / CALCULATION / AI INTERPRETATION / HUMAN DECISION visually distinct. |
| 11 | Recoverables | The head-of-ceded portfolio — open / collected / overdue, an aging chart, the legs table with a next-action per leg, a ⚠ where a leg doesn't reconcile |
| 12 | **Statements** | Enter a reinsurer's stated agreed / paid figures; Cedeon reconciles each line against what it holds and lists the gaps to resolve |
| 13 | **Activity** *(Phase 10)* | Three tabs: **AI runs** · **Audit log** · **AI spend**. Enough to explain a decision — **not** an AgentOps product. |
| 14 | **Settings → Organization / Members** | Rename the workspace; manage people — active members (role, remove), pending invitations (resend, cancel), invite by email. Reached from the top-bar gear. Home shows only an *actionable* "N invitations awaiting a reply" nudge, never a static roster. |
| — | **`/invite/{token}`** *(public)* | Accept-invitation page — shows the organization, inviter and role, then a mini-register (new user) or "sign in to accept" (existing account). |

Design language: calm, dense, and legible — this is a review tool for financial
professionals. Every AI-authored statement in the UI is visually badged and carries
its citation. Light and dark themes. The app shell is a grouped icon sidebar
(**Home** / Reinsurance program / Losses / **Recoveries** [Recoveries · Recoverables ·
Statements] / Oversight) with a mobile sheet; shared primitives (`Button`, `Badge`,
`Card`, `PageHeader`, `Stat`, `EmptyState`, `Tabs`, `Accordion`, `Stepper`) live in
`components/ui/`. See ADR-0023.

---

## 8. ACORD

Cedeon has its **own canonical domain model**. ACORD GRLC interoperability is a
**future adapter** (`app/integrations/acord/`), not an internal schema. We do not
implement the full standard, and we do not copy ACORD's external schema into domain
entities. Key entities carry an optional `external_refs` JSONB for later mapping
(bordereaux IDs, ACORD IDs, broker system keys) without schema churn. See
[ADR-0008](DECISIONS.md).

---

## 9. What we explicitly are NOT doing

Kubernetes · Kafka / event bus · microservices · a second backend language · GraphQL ·
a separate vector database · **Temporal** (evaluated at Phase 10 — *not adopted*, no
saga exists; Procrastinate + entity state machines + the append-only audit log stay,
ADR-0022) · Celery · multiple agent frameworks · a model gateway · autonomous
financial decisions · autonomous notice sending · speculative caching · multi-currency
/ FX · multi-region.

**Still not: a generalised financial-exception abstraction.** Cedeon now surfaces
several exception types — missed recoveries, notice deadlines, contract changes,
aged recoverables, internal reconciliation, reinsurer-statement reconciliation —
**each a concrete check** (`ReconcileFinding`, `StatementFinding`, `RecoveryCandidate`,
…). The **only** generalisation is the attention queue (`app/domain/worklist.py`), and
it is a *derived read-model* carrying an `AttentionCategory` — not a stored
`FinancialException` table. Do not add such a table; do not make `RecoveryCandidate`
generic. Resist a shared domain abstraction until the real customer-validated shapes
clearly converge (PRODUCT.md §1a).

If implementation starts drifting toward any of these: **stop.**
