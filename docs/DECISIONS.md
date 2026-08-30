# Cedeon — Architecture Decision Records

Format: short. Context → Decision → Consequences. Newest decisions may supersede
older ones; mark superseded ADRs rather than deleting them.

| ADR | Title | Status |
| --- | --- | --- |
| 0001 | Monorepo, single repository | Accepted |
| 0002 | FastAPI is the one backend (no NestJS, no second language) | Accepted |
| 0003 | PydanticAI (v2) as the single agent framework | Accepted |
| 0004 | Single public origin: browser → Next.js → FastAPI (private) | Accepted |
| 0005 | Document parsing behind `DocumentParser`; PyMuPDF first, Docling in worker | Accepted |
| 0006 | Retrieval on PostgreSQL + pgvector (halfvec/HNSW) + FTS hybrid; no vector DB | Accepted |
| 0007 | Defer Temporal; MVP uses Procrastinate + entity state machines | Accepted |
| 0008 | Cedeon canonical model; ACORD GRLC as a future adapter | Accepted |
| 0009 | Money: `Decimal` / `NUMERIC(20,2)` + `Money` value object; no FX in MVP | Accepted |
| 0010 | Deterministic, versioned calculation engine; zero AI in that module | Accepted |
| 0011 | Provenance-first extraction; human validation gates executable state | Accepted |
| 0012 | Immutable `TreatyVersion` + immutable `RecoveryCalculation`; append-only audit | Accepted |
| 0013 | REST + generated TypeScript client; no GraphQL | Accepted |
| 0014 | No Kubernetes / Kafka / microservices for MVP | Accepted |
| 0015 | Parse and chunk in one job; embeddings split out in Phase 3 | Accepted |
| 0016 | Defer hybrid retrieval / embeddings to Phase 7 | Accepted |
| 0017 | Loss import is a deterministic mapping pipeline; no AI | Accepted |

---

## ADR-0001 — Monorepo, single repository

**Context.** One product, two deployables (web, api) plus a worker, sharing types and
fixtures. Cross-repo coordination is overhead we don't need.

**Decision.** One Git repository. `apps/api`, `apps/web`, `packages/fixtures`,
`infra/`, `docs/`, `scripts/`.

**Consequences.** Atomic changes across API + client; one CI; simple local dev.
No package-registry publishing. Revisit only if a component needs an independent
release cadence.

## ADR-0002 — FastAPI is the one backend

**Context.** The core work — parsing, extraction, retrieval, calculations, agents,
evals — is Python. A second backend (e.g. NestJS) would duplicate types, business
logic, and deployment, and add cross-language orchestration.

**Decision.** FastAPI is the sole backend. Next.js calls it through a generated typed
client. A second backend service requires explicit written justification before it is
introduced.

**Consequences.** Fewer moving parts; OpenAPI is the single contract. Next.js is a
presentation + BFF layer, not a business-logic tier.

## ADR-0003 — PydanticAI (v2) as the single agent framework

**Context.** We need typed structured extraction and one bounded read-only agent with
typed tools, plus provider portability and eval support. Options: PydanticAI,
LangGraph, OpenAI Agents SDK, direct provider APIs, custom.

**Decision.** PydanticAI v2. One framework, no second. Extraction uses `output_type`
(no tool loop); the Recovery Investigator uses `@agent.tool` + `deps_type`.

**Consequences.** AI output types are Pydantic models shared with API/domain.
Provider-portable via model strings. v2 API (`output_type`, `instructions`). If a
future need (e.g. complex multi-step orchestration) outgrows it, that is a new ADR —
not a second framework bolted on.

## ADR-0004 — Single public origin

**Context.** Browser → FastAPI directly means CORS, cross-site cookies, and a
publicly exposed API. For a pilot this is avoidable complexity and attack surface.

**Decision.** Next.js is the only public origin. A runtime catch-all route handler
(`src/app/api/[...path]/route.ts`) proxies `/api/*` to FastAPI, reading the target
URL from env at request time (a build-time `next.config` rewrite bakes the URL into
the image and cannot be re-pointed per deploy). FastAPI is not publicly exposed in
production. Session cookie is `HttpOnly` `Secure` `SameSite=Lax` on that one origin;
the proxy forwards `Set-Cookie` verbatim. The generated client targets same-origin
`/api`; server components read the session by calling the API directly.

**Consequences.** No CORS, simple cookies, smaller attack surface, one image per
environment. Next.js must be reachable to the API network (same VPC / service mesh).
The proxy adds one hop for browser traffic — acceptable at MVP scale. If we later
need direct programmatic API access for customers, that's a separate authenticated
API surface (token auth), decided then.

## ADR-0005 — Document parsing: interface first, PyMuPDF then Docling

**Context.** Docling gives excellent structure + provenance but is heavy (Granite-
Docling VLM, PyTorch, large image, slow cold start, memory-hungry). We also need a
fast path for digital-text PDFs and an OCR path for scans.

**Decision.** A `DocumentParser` interface. `PyMuPDFParser` (page map + text blocks)
ships first and proves the pipeline in Phase 2. `DoclingParser` follows within
Phase 2, running **only in the worker**, with models pre-baked into the worker image
(no runtime download). OCR (`ocrmypdf`/Tesseract) behind the same interface;
never OCR a document that already has a reliable text layer. Do not add a third
parser or over-generalise the interface until a real second implementation exists.
Cloud parsers (Textract / Azure DI / Google Doc AI) are future adapters.

**Consequences.** API image stays lean. Worker image is large — acceptable, isolated,
deployed independently. Interface stays minimal (2–3 methods) until proven otherwise.

**Status (2026-08-30).** Interface + `PyMuPDFParser` shipped and running in Phase 2.
`DoclingParser` is a documented stub (raises, with the implementation contract in its
docstring) behind the `docling` optional extra and `CEDEON_DOCUMENT_PARSER=docling`.
Implementing and verifying it — plus a dedicated worker image with pre-baked models —
is a tracked follow-up; it cannot run in CI.

## ADR-0006 — Retrieval on PostgreSQL

**Context.** MVP scale is dozens of treaties / thousands of chunks. A dedicated
vector DB adds infra, sync, and cost for no benefit at this scale.

**Decision.** `pgvector` with `halfvec` + HNSW for embeddings, Postgres FTS
(`tsvector` / `pg_trgm`) for lexical, fused with reciprocal-rank fusion, filtered by
`treaty_version_id` / `section_path`. No Pinecone / Weaviate / Qdrant. Phase 1 needs
no retrieval; hybrid lands in Phase 3.

**Consequences.** One datastore, transactional consistency between chunks and domain
rows, one backup story. Revisit only at a scale (millions of chunks, strict latency
SLOs) we are far from.

**Status (2026-08-30).** The datastore choice stands. Timing changed: retrieval /
embeddings move from Phase 3 to **Phase 7** (Recovery Investigator) — see ADR-0016.
Phase 3 extraction passes all chunks for a treaty, no vector search.

## ADR-0007 — Defer Temporal; MVP uses Procrastinate + state machines

**Context.** The proposal recommends Temporal for durable, human-in-the-loop
workflows. In Phases 1–9 the actual work is either short (parse, extract, calculate)
or a human waiting (`status = NEEDS_VALIDATION`). Temporal's cost — a stateful
service or Temporal Cloud dependency + billing, a separate worker/versioning model —
is paid now for benefits used later.

**Decision.** No Temporal in the MVP. Instead:
1. Explicit state machines on domain entities (`TreatyVersion.status`,
   `LossImport.status`, `RecoveryCandidate.status`) with one `audit_events` row per
   transition — this is the workflow.
2. **Procrastinate** (Postgres-backed job queue: transactional enqueue,
   `LISTEN/NOTIFY` + `FOR UPDATE SKIP LOCKED`, retries/backoff, visible job table) for
   async work. No Redis, no broker. (`arq` rejected: maintenance-only.)
3. Idempotent jobs keyed by entity + input hash.
The job interface is isolated so domain/API code does not change if Temporal is
adopted later.

**Decision point:** revisit at Phase 10, adopting Temporal **only if** genuinely
long, multi-party, compensating workflows have emerged (e.g. settlement
reconciliation across weeks, notice/acknowledgement chains, saga rollback).

**Consequences.** MVP infra = Postgres + object storage + api + worker + web.
Simpler ops, simpler local dev, faster to ship. If long workflows arrive, migrating
the handful of multi-step sequences into Temporal is a contained change. Do not use
Celery alongside Procrastinate.

## ADR-0008 — Cedeon canonical model; ACORD as a future adapter

**Context.** We want future interoperability with ACORD GRLC without coupling the
domain to an external schema or implementing the full standard now.

**Decision.** Cedeon has its own canonical domain model. ACORD mapping is a future
adapter in `app/integrations/acord/`. Key entities carry an optional `external_refs`
JSONB for later ID mapping (bordereaux, ACORD, broker keys). We do not copy ACORD's
schema into domain entities and do not implement the standard in MVP.

**Consequences.** Domain stays clean and product-shaped. ACORD support is additive
when a customer or partner needs it.

## ADR-0009 — Money representation

**Context.** Financial safety is a top objective. Binary floats are unacceptable for
money. Multi-currency FX is out of MVP scope.

**Decision.** Python `Decimal`; PostgreSQL `NUMERIC(20,2)` for amounts (whole-cent),
`NUMERIC(9,6)` for shares. A `Money(amount: Decimal, currency: str)` value object;
a bare `Decimal` never crosses a domain boundary as money. Operations on mismatched
currencies raise. No FX conversion — treaty currency must equal loss currency or the
recovery candidate is flagged `CURRENCY_MISMATCH` and no calculation runs. Rounding:
one documented policy (round-half-even to 2dp), applied only at persistence /
allocation boundaries; allocations use largest-remainder penny distribution so
participant shares sum **exactly** to the layer recovery.

**Consequences.** Deterministic, auditable arithmetic. Multi-currency is a deliberate
future feature with its own ADR.

## ADR-0010 — Deterministic versioned calculation engine, zero AI

**Context.** The non-negotiable principle: code calculates, not LLMs.

**Decision.** `app/domain/recoveries/calculations/` contains only pure functions and
frozen models — no FastAPI, SQLAlchemy, PydanticAI, HTTP, or I/O (enforced by
import-linter). An `ENGINE_VERSION` semver constant, bumped on any behavioural
change. Every persisted `recovery_calculations` row stores engine version, treaty
version, all inputs, an ordered step `trace`, and an `input_hash`. Recalculation
creates a new immutable row. Mandatory golden-table + Hypothesis property tests.

**Consequences.** Any recovery figure is reproducible and explainable. "Why did the
number change?" is always answerable from stored rows.

**Status (2026-08-30).** Built in Phase 4: `app/domain/recoveries/calculations/xol.py`
(`ENGINE_VERSION = "1.0.0"`), 28 tests (golden table + boundaries + Hypothesis
properties), and a 4th import-linter contract — the engine may import **only**
`app.domain.money`. Persistence of `recovery_calculations` rows (engine version,
inputs, `trace`, `input_hash`) lands with `RecoveryCandidate` in Phase 6; the Phase 4
`/recovery-preview` endpoint runs the engine read-only against a validated treaty.

## ADR-0011 — Provenance-first extraction; human validation gate

**Context.** An LLM must never be the source of truth for a material term.

**Decision.** Extraction produces `treaty_term_candidates` with
`status ∈ {extracted, not_found, ambiguous, conflicting}`, `confidence`, and — for
material terms — a `citation` resolvable to real page text (else downgraded to
`ambiguous`). Candidates never populate executable state. A human confirms / edits /
rejects / marks-ambiguous in the validation workspace; only confirmed terms populate
`treaty_terms` / `treaty_layers` / `treaty_participations`, and only after
`POST /treaties/{id}/validate` does the `TreatyVersion` become `VALIDATED`.

**Consequences.** Slower path to "executable treaty," deliberately. This is the
product's core trust mechanism.

## ADR-0012 — Immutability & audit

**Context.** Financially material workflows require traceability and reproducibility.

**Decision.** `TreatyVersion` is immutable once `VALIDATED` (changes → new version,
old → `SUPERSEDED`). `recovery_calculations` / `recovery_allocations`,
`recovery_investigations`, `recovery_packet_versions`, `agent_runs`, `documents`,
`underlying_losses` are immutable. `reviews` and `audit_events` are append-only
(`audit_events` enforced by a DB trigger rejecting UPDATE/DELETE). This is **not**
event sourcing — mutable current-state tables coexist with immutable snapshots and an
append-only log.

**Consequences.** Storage grows monotonically (acceptable; retention policy in
Phase 10). Every material state has a "who/when/why."

## ADR-0013 — REST + generated client, no GraphQL

**Context.** One backend, one frontend, typed contract needed. GraphQL adds a schema
layer, resolver complexity, and caching nuance we don't need.

**Decision.** Resource-oriented REST. FastAPI OpenAPI is the contract.
`@hey-api/openapi-ts` generates TS types + TanStack Query hooks. CI fails on client
drift. RFC 9457 `problem+json` errors. `Idempotency-Key` on retry-sensitive
mutations.

**Consequences.** No hand-written DTOs. Frontend and backend types cannot silently
diverge.

## ADR-0014 — No Kubernetes / Kafka / microservices for MVP

**Context.** These are common premature-scaling choices. Cedeon MVP is one API, one
worker, one DB.

**Decision.** Deploy `api` and `worker` as ECS/Fargate services; Postgres on RDS;
files on S3. No Kubernetes, no Kafka/event bus, no microservice decomposition, no
speculative caching layer. If implementation drifts toward these, stop.

**Consequences.** A small team can operate the whole system. Re-evaluate individual
items against real, measured constraints — never speculatively.

## ADR-0015 — Parse and chunk in one job; embeddings split out later

**Context.** The Phase 2 roadmap sketched `parse_document → chunk_document` as two
jobs. Chunking needs the parser's block structure (headings), which is not persisted
— only page text is. Splitting the jobs would force either a `document_blocks` table
or re-deriving structure.

**Decision.** The `parse_document` Procrastinate job does parse **and** chunk in one
transaction, holding the `ParsedDocument` (with blocks) in memory. Chunks store
`char_start`/`char_end` offsets into the document's canonical full text
(`"\n\n".join(page.text)`), so `full_text[start:end] == chunk.text` exactly.

Embedding generation **will** be its own job in Phase 3 (it is slow, rate-limited,
and re-runnable independent of parsing) — `parse_document` will enqueue it. The
`vector` extension and the `embedding` column land then, sized to the chosen model.

**Consequences.** Fewer moving parts now; the expensive/independent step is isolated
when it actually exists. A future structure-only re-chunk (e.g. tuning chunk sizes
without re-OCR) would need block persistence — deferred until needed.

## ADR-0016 — Defer hybrid retrieval / embeddings to Phase 7

**Context.** The Phase 3 plan included hybrid retrieval (Postgres FTS + `pgvector`
`halfvec`/HNSW + RRF) to select treaty chunks for extraction. Real treaties in the
MVP are a handful of pages / dozens of chunks — small enough to pass in full to a
1M-context model. The place targeted retrieval genuinely earns its keep is the
Recovery Investigator (Phase 7) doing focused Q&A over a treaty.

**Decision.** Phase 3 extraction receives **all** chunks for the source document,
ordered. No `vector` extension, no `embedding` column, no embedding job yet. Add
`pgvector` (extension + `embedding halfvec(N)` sized to the chosen model + an
`embed_chunks` job + hybrid `retrieve_treaty_passages`) in **Phase 7**, where the
investigator needs it. This also keeps the embedding-provider question (Anthropic
has no embeddings API) out of Phase 3.

**Consequences.** Simpler Phase 3, one fewer vendor decision now. If a customer
brings a 200-page treaty before Phase 7, retrieval moves up — the chunk table and
`ParsedDocument` structure already support it.

## ADR-0017 — Loss import is a deterministic mapping pipeline; no AI

**Context.** Customer claim schedules arrive as CSV with idiosyncratic column names,
date formats, and money formatting. It is tempting to let an LLM "just read the
file". But underlying losses feed the calculation engine directly — an LLM
misreading `1,234` as `1234000` or guessing a date is exactly the class of error
ADR-0010 forbids from touching money.

**Decision.** The Phase 5 pipeline (`app/domain/losses/`, `app/services/losses.py`)
contains **zero AI**. `POST /loss-imports` stores the raw file (object storage,
`sha256`-deduped) and every row verbatim in `loss_import_rows.raw` (JSONB, never
mutated). The human maps CSV columns to `CanonicalField`s (a UI convenience guesses
from header names; the human confirms). `validate_rows` is pure and deterministic:
a fixed list of accepted date formats, explicit money parsing (`$`/comma strip,
`HALF_EVEN` to cents), duplicate-claim detection, and `gross_incurred` derived from
`gross_paid + gross_case_reserve` only by exact addition. Malformed rows are
**flagged, never dropped or "fixed"**. `commit` turns only OK/warning rows into
immutable `underlying_losses`; errored rows stay on the import for the human to
correct and re-upload. `loss_import_id` / `loss_import_row_id` are `RESTRICT` FKs so
a loss can always be traced to the exact source row.

**Consequences.** Onboarding a genuinely messy schedule is more manual than an
"AI import" would feel. That is the point — the number that reaches the engine is
one a human mapped and the code parsed, with the original a click away. If fuzzy
column-name suggestion ever needs a model, it stays advisory and on the *mapping*
step, never the values.
