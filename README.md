# Cedeon

**Reinsurance intelligence from contract to recovery.**

Cedeon is an AI-native reinsurance intelligence and workflow platform. The initial
product is **Cedeon Recovery Intelligence**:

> Upload your reinsurance treaties and loss data. Cedeon understands the contracts,
> monitors the losses, identifies potential recoveries, explains why the treaty
> responds, and prepares an evidence-backed recovery package for human review.

## Architectural non-negotiables

1. **LLMs interpret. Deterministic code calculates. Humans approve material interpretations and actions.**
2. An LLM is **never** the source of truth for a financial figure. Every extracted term carries provenance (document, page, clause, span, confidence, model) and is human-validated before it can feed a calculation.
3. Money is `Decimal` in Python and `NUMERIC` in PostgreSQL. Never binary floating point. Currency is always explicit.
4. Every uploaded document is **untrusted input**. Document text is data, never instruction.
5. Every financially material output is traceable to `FACT` / `CALCULATION` / `AI INTERPRETATION` / `HUMAN DECISION`.

## Documentation

| Doc | Purpose |
| --- | --- |
| [docs/PRODUCT.md](docs/PRODUCT.md) | Product vision, MVP scope, users, non-goals, first success criterion |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architecture verdict, stack, repo layout, runtime topology |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | Domain model, ERD, versioning & immutability rules |
| [docs/AI_ARCHITECTURE.md](docs/AI_ARCHITECTURE.md) | Extraction, retrieval, the Recovery Investigator agent, evals, provider strategy |
| [docs/SECURITY.md](docs/SECURITY.md) | Tenancy, authz, prompt-injection defense, secrets, data handling |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phased plan, current status, the first vertical slice, golden E2E test |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Architecture Decision Records |
| [docs/UX_STUDY.md](docs/UX_STUDY.md) | The ceded-reinsurance-desk workflow study — findings, proposed IA, phasing |
| [packages/fixtures/](packages/fixtures/) | Synthetic treaty PDFs + claim CSVs for an end-to-end walkthrough |

## Status

- **Phase 0 — Architecture review:** complete. Verdict *partially agree* (one material change — Temporal deferred; see [ADR-0007](docs/DECISIONS.md)).
- **Phase 1 — Foundation:** complete (2026-08-30). Monorepo, FastAPI + async SQLAlchemy + Alembic, org/user/membership/session auth, append-only audit, the `Money` value object with golden + property tests, Next.js 15 app (animated landing, authed dashboard), Docker Compose, CI. **No AI yet.**
- **Phase 2 — Document pipeline:** complete (2026-08-30). Object storage (`ObjectStore`: filesystem / S3+MinIO), `DocumentParser` interface + `PyMuPDFParser`, heading-aware chunking, `documents`/`document_parses`/`document_pages`/`document_chunks` (migration 0002), a Procrastinate `parse_document` job, upload + viewer UI. Verified end-to-end through the containerized stack.
- **Phase 3 — Treaty extraction + validation:** complete (2026-08-30). Reinsurance structure + `treaty_versions` lifecycle (migration 0003); `agent_runs` / `citations` / `treaty_term_candidates` / append-only `reviews` (migration 0004); PydanticAI structured extraction (`app/ai`, Anthropic, provider registry); `extract_treaty` job; `ValidationService` (review → confirm → freeze executable layer + participations); Programs / Treaty Library / Treaty Detail / **validation workspace** UI. The full golden path is test-verified with the model call faked, and the live extraction is verified end-to-end against Anthropic (`pytest -m live`, `claude-opus-5`) — attachment `50,000,000.00` / limit `20,000,000.00` / three participations, each with a resolving citation. Retrieval/embeddings deferred to Phase 7 ([ADR-0016](docs/DECISIONS.md)).
- **Phase 4 — XOL calculation engine:** complete (2026-08-30). `app/domain/recoveries/calculations/` — pure `calculate_xol_recovery` + `allocate_recovery` + `calculate_recovery`, `ENGINE_VERSION`, **28 tests** (golden `$20M xs $50M` table, boundaries, Hypothesis properties). Engine may import only `Money` (4th import-linter contract). Read-only `/recovery-preview` endpoint + "what-if" card on Treaty Detail. **Zero AI.**
- **Phase 5 — Loss import:** complete (2026-08-30). `loss_imports` / `loss_import_rows` / `loss_events` / immutable `underlying_losses` (migration 0005); a pure canonical-field schema + deterministic `validate_rows` (multi-format dates, money parsing, duplicate-claim and derived-incurred handling); `POST /loss-imports` → `/mapping` → `/commit` grouping valid rows into find-or-create loss events; `/loss-events` screens; column-mapping workspace with header auto-guess. The synthetic 10-claim hurricane CSV commits to exactly **USD 58,700,000.00** in one event. **148 tests. No AI in this pipeline.**
- **Phase 6 — Recovery Candidate:** complete (2026-08-30). `recovery_candidates` (one per treaty-version/layer/loss-event) + immutable `recovery_calculations` / `recovery_allocations` (migration 0006); a pure `recovery_input_hash` that gates recompute; `POST /recovery-candidates` runs the deterministic engine, `/recalculate` writes a new calculation only when inputs changed (reverting a confirmed candidate), `/review` is confirm/reject/request_info with an append-only trail. The golden validated treaty + Hurricane Demo event yields **8,700,000.00** layer recovery, allocations **4.35M / 2.61M / 1.74M**. `/recovery-candidates` queue + detail UI. **167 tests. No AI (ADR-0010/0018).**
- **Phase 7 — Recovery Investigator:** complete (2026-08-30). The first AI agent — bounded, read-only. Migration 0007: `tool_calls`, immutable `recovery_investigations` + `recovery_investigation_findings`. A PydanticAI agent with `output_type=RecoveryInvestigation` and six typed read-only tools (incl. lexical `search_treaty`, ADR-0019); `UsageLimits` + timeout bound it; it's handed the deterministic recovery as a fact and never emits a rival number. `InvestigationService` grounds every must-cite finding against real page text (ADR-0011) and records the run + tool calls. `POST /recovery-candidates/{id}/investigate`; investigation panel on the candidate detail. **179 tests + a live eval** (`pytest -m live`, `claude-opus-5`) asserting citations resolve and the `8,700,000.00` figure is untouched.
- **Phase 8 — Recovery Packet:** complete (2026-08-30). Migration 0008: `recovery_packets` + immutable `recovery_packet_versions`. Pure `assemble_packet` classifies every statement **FACT / CALCULATION / AI INTERPRETATION / HUMAN DECISION**, `render_packet_html` emits a self-contained artifact. `POST /recovery-candidates/{id}/packet` writes a new immutable version each time; `/versions/{v}/review` is confirm/reject/request_info/**edit** — an edit records before/after, stores an override, and regenerates (ADR-0020). `/html` streams the printable packet. `/recovery-candidates/{id}/packet` screen with the four classes visually distinct, inline editing, version list. **196 tests + 2 live. No AI (ADR-0010/0020).**
- **Phase 9 — Notice drafter:** complete (2026-08-30). Migration 0009: `recovery_notices`. One `output_type=NoticeDraft` call — **no tools** — fed a `NoticeContext` whitelist of approved facts (no raw document text). Runs only after the candidate is `CONFIRMED`; review is confirm/reject/request_info/**edit** (in place on the draft). **There is deliberately no send action anywhere** (ADR-0021) — a notice's terminal state is `APPROVED`; a test asserts no `send` operation in the OpenAPI doc. `/recovery-candidates/{id}/notices` screen. **208 tests + a live eval** (`pytest -m live`, `claude-opus-5`) checking the draft uses only provided facts, keeps the `8,700,000` figure, stays indicative, and invents no contact.
- **Phase 10 — Durability + observability:** complete (2026-08-30). **Temporal is not adopted** — no long-running multi-party compensating workflow exists; Procrastinate + state machines + the audit log stay (ADR-0007 status, ADR-0022). AI/parse jobs carry a `RetryStrategy`; an in-flight guard (`has_active_run`) stops retries + double-submits double-running; `/readyz` also probes the object store. New `GET /activity/{agent-runs,audit,ai-spend}` + an **Activity** screen (AI runs · audit log · per-agent/per-day AI spend). **219 tests + 4 live evals.** OTel stays wired-but-off — the `agent_runs` / `audit_events` tables are the record.

**The 10-phase MVP is complete** — the full pipeline runs end to end through the containerized stack.

- **UI refresh** (2026-08-30). A design-system and content pass on `apps/web` with no backend change ([ADR-0023](docs/DECISIONS.md)): Tailwind v4 token additions (elevation, gradients), Radix + `lucide-react` primitives, a real multi-section marketing site (`/`, `/security`, `/about`) with a comparison table and the worked `$8.7M` example, and a grouped icon sidebar for the app shell. The FACT / CALCULATION / AI INTERPRETATION / HUMAN DECISION visual language is unchanged.

## Quickstart

Prereqs: Docker, `uv`, `pnpm`, and [`just`](https://github.com/casey/just)
(`brew install just`). Every `just` recipe is a thin wrapper — `just --list`.

```bash
cp .env.example .env
just bootstrap        # uv sync + pnpm install
just up               # docker compose: postgres, minio, api, worker, web
just seed-demo        # optional: a synthetic org you can sign in to
# web  → http://localhost:3000       api → http://localhost:8000/docs
just test             # api (pytest) + web (vitest)
just ci               # lint · typecheck · test · build
```

Without `just`: `cd apps/api && uv sync && uv run pytest` and
`cd apps/web && pnpm install && pnpm test run && pnpm build`.

## Repository layout

```
apps/
  api/        FastAPI backend — domain, services, AI, workers
  web/        Next.js frontend — app + marketing
packages/
  fixtures/   Synthetic treaty PDFs + claim CSVs + generator — the end-to-end demo data
  openapi/    The generated OpenAPI document (the frontend contract)
infra/        docker-compose, Dockerfiles, deployment config
docs/         Architecture & product documentation
scripts/      Dev + CI helper scripts
```
