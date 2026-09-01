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
| 0018 | Recovery candidate ↔ calculation split; content hash gates recompute | Accepted |
| 0019 | Investigator retrieval is lexical (Postgres FTS); vector arm deferred | Accepted |
| 0020 | Recovery Packet: classified statements, immutable versions, edit = regenerate | Accepted |
| 0021 | Notice drafter: whitelist of approved facts in, draft out, no send action | Accepted |
| 0022 | Observability = `agent_runs` + `audit_events` + job hardening; OTel optional | Accepted |

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

**Status (2026-08-30) — the Phase 10 decision point: Temporal is NOT adopted.**
After building all ten phases, no long-running, multi-party, compensating workflow
exists. Every job is short (parse / extract / calculate / investigate / draft) or a
human waiting on an entity `status`. The three MVP "sequences" (document → treaty,
loss import → recovery, candidate → packet → notice) are each a straight line of
short steps with a human gate, fully modelled by entity state machines + one
`audit_events` row per transition. Procrastinate + state machines stay. Phase 10
hardened this path instead: `RetryStrategy` on the AI/parse jobs, an in-flight guard
(`AgentRunRepository.has_active_run`) so retries and double-submits can't double-run,
and an observability surface (ADR-0022). Revisit only if a genuine saga appears
(settlement reconciliation across weeks, reinsurer-acknowledgement chains with
rollback) — the job interface is still the seam.

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

## ADR-0018 — Recovery candidate ↔ calculation split; a content hash gates recompute

**Context.** A recovery figure is reviewed, then acted on. The reviewed object is
mutable (its status changes; a human confirms it) but the *number* must be a frozen,
auditable artifact tied to exact inputs. Inputs can also legitimately change after a
candidate exists — Phase 5 lets a second loss import commit into the same loss
event — and a stale confirmation must not silently stand.

**Decision.** Two entities. `recovery_candidates` is the mutable review object, one
per `(treaty_version, treaty_layer, loss_event)` (re-`POST` returns the existing
row). Every run of the deterministic engine writes an **immutable**
`recovery_calculations` row (+ `recovery_allocations`) with the full input set,
`trace`, and a `recovery_input_hash` — a pure SHA-256 over engine version, the
version/layer/event ids, gross/attachment/limit, and the sorted participations
(scale-insensitive so `50000000` and `50000000.00` agree).
`current_calculation_id` points at the live one. `POST /{id}/recalculate` recomputes
the hash from current inputs: unchanged → no-op; changed → a new calculation row,
`current_calculation_id` moves, and a `CONFIRMED` candidate reverts to
`NEEDS_REVIEW`. Gross event incurred is `Σ gross_incurred` over the event's losses
**in the layer currency only** (ADR-0009 — no FX); any other-currency loss sets
`currency_mismatch` and is excluded. No AI in this path (ADR-0010).

**Consequences.** Full calculation history per candidate; a confirmation can never
outlive the inputs it was based on. The candidate is pinned to one *executable
version* — a re-validated treaty is a new version and would need a new candidate,
which is correct. `recalculate` is explicit (a button), not automatic on loss
commit; a background "mark candidates stale" pass can be added later without schema
change since the hash is already stored.

## ADR-0019 — Investigator retrieval is lexical (Postgres FTS); the vector arm is deferred

**Context.** ADR-0016 deferred hybrid retrieval / embeddings to Phase 7, where the
Recovery Investigator needs to find treaty wording. Building the vector arm now means
choosing an embeddings vendor (Anthropic has none — Voyage, OpenAI, or a self-hosted
model), adding a `halfvec` column + HNSW index + an `embed_chunks` job, and carrying
that cost and vendor relationship. The MVP treaty is a few pages of clause-aware
chunks; early real treaties are dozens of pages.

**Decision.** `search_treaty` ranks the already-stored `document_chunks` by Postgres
full-text search (`ts_rank(to_tsvector('english', text), plainto_tsquery(query))`),
falling back to the opening chunks when a query has no lexical hits. No `vector`
extension, no `embedding` column, no embed job, no embeddings vendor. The tool
signature — `search_treaty(query, k) -> list[Passage]` — is the seam: a vector arm
(and RRF fusion) can be added behind it without touching the agent or its callers.

**Consequences.** One fewer vendor decision and no new infra for Phase 7. Lexical
search misses pure paraphrase ("catastrophe" vs "cat event") — acceptable on
clause-headed chunks at this scale, and the grounding gate (ADR-0011) catches a
finding that cites the wrong passage regardless. Revisit when a real treaty is large
enough that FTS recall visibly costs the investigator a citation.

## ADR-0020 — Recovery Packet: classified statements, immutable versions, edit = regenerate

**Context.** The packet is the artifact a reinsurance professional acts on and an
auditor later reads. It must (a) never blur a computed number, an AI reading, a
contract fact, and a human decision; (b) be reproducible — "what did the packet say
when it was approved on the 3rd?"; (c) let a human correct wording without
destroying that history or silently overriding the deterministic figure.

**Decision.** `assemble_packet` is a pure function that arranges already-produced
material into `PacketStatement`s, each carrying one of four classes — **FACT**
(validated term / record), **CALCULATION** (engine output + trace, ADR-0010),
**AI_INTERPRETATION** (an investigator finding, with its citation), **HUMAN_DECISION**
(a review or edit). It never computes or interprets. `recovery_packet_versions` are
**immutable**; `POST .../packet` always writes a new version and supersedes the
prior one. A human edit does not mutate a version: it records a `reviews` row with
before/after, stores `{text, reason, by}` on `recovery_packets.human_overrides`
keyed by the statement, and regenerates — the new version shows the edited text
flagged `edited_by_human` with the original preserved in `detail.original_text`, and
a HUMAN_DECISION statement noting the edit. `rendered_html` is a deterministic
single-file render stored alongside `content` for printing / archiving.

**Consequences.** Every packet the reviewer ever saw is retrievable; an approval is
tied to an exact immutable version. Editing the layer-recovery *text* is possible
(and audited) but it is cosmetic — the CALCULATION class and the underlying
`recovery_calculations` row are unchanged, so a reader can always see it was a human
wording change, not a recomputation. Overrides accumulate on the packet, so a
regenerate after a new investigation keeps prior human wording. Statement keys are
stable strings; renaming one in `assemble_packet` orphans its overrides (acceptable
— overrides are advisory text, not data).

## ADR-0021 — Notice drafter: a whitelist of approved facts in, a draft out, no send action

**Context.** The last step of the recovery flow is telling the broker / reinsurer.
That is external-facing correspondence stating a money figure — the highest-stakes
place for the model to invent a party, a date, a policy number, or a number, or to
imply that something has been agreed or paid. The SECURITY principles forbid
autonomous notice sending outright.

**Decision.** The notice drafter (`app/ai/notice/`) is a **single `output_type`
call with no tools** — the same shape as extraction, not the tool-loop investigator.
It receives a `NoticeContext`: a fixed whitelist assembled by deterministic code
from confirmed / validated state only (cedent, treaty, layer, loss event, the
deterministic recovery figure, the validated notice provision, the participants,
the caller-supplied recipient). It gets **no raw document text and no unvalidated
AI output**. The prompt tells it to use only those facts, to copy figures verbatim,
to present the recovery as *indicative, subject to the reinsurer's review and the
treaty terms*, and never to state that anything is agreed, paid, or accepted; the
schema carries a `used_only_provided_facts` self-attestation the eval checks.
It runs only after the candidate is `CONFIRMED`. Output is a `DRAFT` that a human
edits (in place, with `reviews` before/after) and approves. **There is no send
endpoint, service method, job, or tool anywhere** — a notice's terminal state is
`APPROVED`; a test asserts no `send` operation exists in the OpenAPI document.

**Consequences.** The generated text is bounded to facts a human already validated,
and the human is unavoidably in the loop before anything leaves Cedeon (sending
happens in the user's own mail / broker system). Adding a real send integration
later is a deliberate new decision with its own ADR and its own approval gate — it
is not a small extension of this phase.

## ADR-0022 — Observability is `agent_runs` + `audit_events` + job hardening; OTel is optional

**Context.** Phase 10 asked for "OTel dashboards, AI cost/latency views, audit
views". Standing up a self-hosted trace/metrics stack (Grafana/Tempo/Loki) for a
pilot is disproportionate ops, and it would make the *primary* record of what
happened live in an external system with its own retention and access model —
wrong for a product whose value is auditability.

**Decision.** The first-class record is in Postgres, already written on every path:
`agent_runs` (provider, model, prompt version, token counts, `cost_usd`, latency,
status, error, correlation id) + `tool_calls` + the append-only `audit_events`
(one row per state transition, `BEFORE UPDATE OR DELETE` trigger). Phase 10 surfaces
it: `app/repositories/activity.py` / `app/services/activity.py` and
`GET /activity/{agent-runs,audit,ai-spend}`, plus an **Activity** screen. Durability
on the same path: a `RetryStrategy` (backoff) on the parse + AI jobs for transient
provider/storage failures, and `AgentRunRepository.has_active_run` — a non-stale
`RUNNING` run for the same subject makes a second attempt a `ConflictError` (which
the job logs and returns, rather than retrying). `/readyz` also probes the object
store. OpenTelemetry stays wired but **off by default** (`CEDEON_OTEL_ENABLED` +
an OTLP endpoint) — an add-on for teams that already run a collector, never a
dependency; the DB tables are complete without it.

**Consequences.** Zero new infra; the audit trail and AI-cost view work the moment
the app is up, with the same backup and tenant-isolation story as everything else.
`ai-spend` is exact per-org accounting from `response.usage`, not sampled traces.
If trace-level latency breakdowns or cross-service spans are ever needed, flip OTel
on — no code change to the recorded model.

## ADR-0023 — Frontend design system: Tailwind v4 tokens + Radix/lucide primitives; no CSS-in-JS, no component framework

**Context.** The MVP UI worked but read as a scaffold: one flat card style, ad-hoc
`<svg>` marks, a single-section landing page, an undifferentiated sidebar. A design
pass was asked for, benchmarked against a modern SaaS marketing site. The question
was how much library to take on.

**Decision.** Stay on the stack already chosen (Next 15 App Router, Tailwind v4,
hand-rolled shadcn-style primitives) and close the gap with **design execution and
content breadth**, not a framework. Concretely:

- **Tokens.** `globals.css` `@theme` gains elevation (`--shadow-xs..lg`, `--shadow-glow`),
  gradient/glow utilities (`.hero-glow`, `.text-gradient`, `.dot-backdrop`), a
  `--border-strong` / `--elevated` surface pair, and a fuller radius scale — all
  theme-aware (light / `prefers-color-scheme` / `[data-theme]`). **The four trust
  colours (`fact` / `calculation` / `ai` / `human`) are unchanged and remain the
  product's primary visual signature** (ADR-0020).
- **Theme.** Light is the default — the audience works beside light treaty PDFs and
  bordereaux, dense financial tables read better light, and the Recovery Packet
  artifact is light. A `ThemeToggle` (System / Light / Dark, `lucide` icons) in the
  app top bar, the marketing footer and the auth panel persists to
  `localStorage["cedeon-theme"]`; a tiny inline script in the root layout stamps
  `data-theme` before first paint so there is no flash. "System" (the default) leaves
  the attribute off and follows the OS. Dark-first was considered and rejected: it
  would mean re-tuning the trust-colour tints for a dark ground and re-shooting the
  marketing screenshots, and it cuts against the institutional "sits beside the
  document" positioning.
- **Primitives.** Add `@radix-ui/react-{accordion,tabs,slot,dialog}` (accessible
  FAQ / tabs / `asChild` / mobile sheet), `lucide-react` (line icons, replacing
  emoji and ad-hoc SVG), and `clsx` + `tailwind-merge` (`cn` now merges conflicting
  classes). `components/ui/` gains `Accordion`, `Tabs`, `PageHeader`, `Stat`,
  `EmptyState`, `Section`/`Container`/`SectionHeading`, `Separator`, `Skeleton`;
  `Button`/`Badge`/`Card`/`Field` get richer variants. No CSS-in-JS, no MUI/Chakra/
  Mantine, no Tailwind plugin beyond `@tailwindcss/postcss`.
- **Marketing.** The `(marketing)` route group becomes a real site: sticky nav +
  4-column footer, a hero with a self-contained HTML product mockup (the Recovery
  Packet, showing the four trust classes), and sections for how-it-works, platform,
  who-it's-for, a comparison table (Cedeon vs manual bordereau review vs generic AI
  assistant), the worked `$20M xs $50M / $58.7M / $8.7M` example with the engine
  trace, security, "what Cedeon is not", and an FAQ accordion — plus `/security`
  and `/about` pages. `motion` stays confined here.
- **App shell.** Grouped icon sidebar (Overview / Contracts / Losses / Recovery /
  Oversight) with a Radix-dialog mobile sheet; a sticky top bar with an avatar
  monogram. All 17 app views take a consistent polish pass: `PageHeader` /
  `BackLink`, `EmptyState` for empty lists, the `Select` / `Textarea` / `FilterTabs`
  primitives in place of ad-hoc markup. The investigation panel is retinted to the
  `ai` (purple) trust colour, since its summary and findings *are* AI interpretation.

**Consequences.** ~+7 small runtime deps, all tree-shakeable; marketing `/` first-load
JS ≈ 161 kB. `motion` still never enters the `(app)` bundle. No visual regression to
the trust-class language or the validation workspace. The copy in the new marketing
sections restates existing doc positions (PRODUCT §1/§1a, the non-goals) — it does
**not** expand product scope, and no `FinancialException`/generic-finding abstraction
is implied.

## ADR-0024 — Collection tracking: a recoverable per reinsurer, human facts on an audit trail

**Context.** Phase B made the recovery workspace whole *except* for the last stage:
what happens after a notice is drafted. The ceded-reinsurance desk's job does not
end at "notice approved" — it ends at cash in the bank, often a year later, after
chasing overdue balances across a dozen reinsurers (docs/UX_STUDY.md finding 7).
Nothing in Cedeon tracked that.

**Decision.** A first-class `recoverables` table (migration 0010), one row per
`(recovery_candidate, reinsurer)`, materialised from the confirmed recovery's
**current immutable calculation**:

- `expected_amount` is a **fact** carried from `recovery_allocations.allocated_recovery`
  — it is never edited; a `recovery_calculation_id` FK (RESTRICT) makes it traceable.
- `status` walks `pending → notified → agreed → billed → collected`, with `disputed`
  and `written_off` as explicit side moves. Status stamps (`notified_at`, `agreed_at`,
  `billed_at`, `settled_at`) are set on first entry.
- `agreed_amount` / `billed_amount` / `collected_amount` / `due_date` / `note` are
  **human-entered facts**, mutable and corrected over time. Every change writes an
  `audit_events` row (`recovery.recoverable_updated`).
- **Aging is derived, never stored**: `days_overdue` and an aging bucket
  (`current` / `1–30` / `31–60` / `61–90` / `90+`) are computed from `due_date` and
  today. Portfolio roll-ups (`summarize_recoverables`) are a pure function.
- **Single currency, no FX** — a recoverable in a currency other than the summary's is
  ignored in the roll-up, mirroring the calculation engine (ADR-0018).

**No AI.** The domain module (`app/domain/recoveries/collection.py`) is pure standard
library; the service is deterministic; the figures are facts and human decisions. The
import-linter "domain is pure" contract still holds.

**Endpoints.** `POST /recovery-candidates/{id}/recoverables` (materialise, idempotent),
`GET /recovery-candidates/{id}/recoverables`, `GET /recoverables` (portfolio, filter by
status), `GET /recoverables/summary` (org roll-up — feeds the Home "Open recoverable"
figure), `POST /recoverables/{id}` (the human update). UI: the workspace's **Collection**
rail section, unlocked once the recovery is confirmed.

**Consequences.** Cedeon now spans the desk's whole job — contract to cash. Left for
their own work (not folded in here): multi-currency settlement. *(Reinstatement
premium and reinsurer-statement reconciliation were later built as their own modules —
ADR-0025.)*

---

## ADR-0025 — Scope expansion: reinstatements and hours-clause grouping become supported; each exception check stays concrete

**Context.** The MVP deliberately modelled **one treaty structure** (per-occurrence
XOL) and kept a long do-not-build list (PRODUCT.md §7): aggregate covers, reinstatement
waterfalls, hours-clause event clustering, and more. After the recovery-control build
(①–⑧), the intelligence-system reframe (⑨, ⑪), and the marketing refresh, the user
restored Anthropic credits and directed: **build the whole deferred backlog** — the
⑥ follow-ups (per-layer participations, a grouped programme view), ⑨ re-extraction +
term diff, ⑩ reinstatement premium math, ⑫ hours-clause grouping, and the larger
reinsurer-statement reconciliation module.

Three of those sat on the §7 do-not-build list. Per the standing guardrail protocol,
the conflict was surfaced with alternatives and a recommendation before any code; the
user confirmed the expansion.

**Decision.**

1. **Reinstatements and hours-clause grouping move from "do not build" to
   "supported v1"** (PRODUCT.md §7 rewritten). The *LLMs interpret / code calculates /
   humans approve* line is untouched:
   - **Reinstatement premium** is deterministic arithmetic (`app/domain/recoveries/
     reinstatements.py`, migration 0015): reinstatement *k* restores the erosion band
     `[(k-1)·limit, k·limit]`; premium = `deposit_premium × (amount this loss reinstates
     / limit) × rate(k) × time_factor` (1 for flat, unexpired-period fraction for
     pro-rata-as-to-time). The deposit premium and rates are **human-entered layer
     terms**, never extracted. Prior erosion in the period = Σ current `layer_recovery`
     of earlier confirmed recoveries on the same layer; computed on read, not stored.
   - **Hours-clause grouping is *assistive*** (`app/domain/losses/occurrences.py`): a
     greedy anchored grouping of a loss event's claims into rolling windows
     (`ceil(hours/24)` days) that Cedeon **proposes** for a human to accept or
     re-anchor. It never auto-decides an occurrence, never splits an event, adds no
     persistence. `GET /loss-events/{id}/occurrence-proposal`.

2. **Still deferred:** aggregate XOL / aggregate deductibles, quota share / surplus,
   inuring order, FX, retrocession, automated catastrophe-event modelling, and a
   bordereau/statement **file** importer (statement lines are entered directly).

3. **No generalised finding model, even now that several exception types exist.**
   Internal reconciliation (`ReconcileFinding`), reinsurer-statement reconciliation
   (`StatementFinding`, migration 0016), suggested recoveries, notice deadlines,
   contract-change alerts, aged-recoverable chasing — **each stays a concrete check**.
   Findings persist as typed rows or JSONB on the concrete parent
   (`recoverables`, `reinsurer_statement_lines`), never in a `FinancialException`
   table. The **only** generalisation is `app/domain/worklist.py` — a *derived
   read-model* carrying an `AttentionCategory` (recovery / obligation / contract /
   exception). A shared domain abstraction is still deferred until the real
   customer-validated shapes converge (PRODUCT.md §1a).

**Consequences.** Migrations 0014 (per-layer participations), 0015 (reinstatement
terms), 0016 (reinsurer statements). The engine still models per-occurrence XOL plus a
stack of such layers — reinstatements are a premium calculation *on* a layer, not a new
structure. The import-linter "domain is pure" and "calc engine imports only Money"
contracts still hold (the new pure modules are `app/domain/recoveries/` and
`app/domain/losses/`, standard-library only). PRODUCT.md §1a, §2a, §5, §7 and
ARCHITECTURE.md §9 updated; DATA_MODEL.md §4/§7 updated.
