# Cedeon — Roadmap

When choosing between "build more framework" and "get treaty → validated terms →
deterministic recovery working," choose the latter.

---

## Status board

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Architecture review + docs | ✅ **Complete** — verdict *Partially agree* (Temporal deferred) |
| 1 | Foundation (monorepo, API, web, DB, auth, CI) — **no AI** | ✅ **Complete** (2026-08-30) |
| 2 | Document pipeline (upload → storage → parse → pages/chunks → viewer) | ✅ **Complete** (2026-08-30) |
| 3 | Treaty extraction + human validation workspace | ⏭️ **Next** |
| 4 | Executable XOL model + deterministic calculation engine | ⬜ |
| 5 | Loss import (CSV → mapping → validation → underlying losses) | ⬜ |
| 6 | Recovery Candidate (validated treaty + loss event → calc → candidate + queue UI) | ⬜ |
| 7 | Recovery Investigator (one bounded read-only agent + evals) | ⬜ |
| 8 | Recovery Packet + human review / approval flow | ⬜ |
| 9 | Notice draft (draft only, human approval, never auto-sent) | ⬜ |
| 10 | Durability + observability hardening (evaluate Temporal *here*) | ⬜ |

**First meaningful success criterion:** a reinsurance professional uploads a
real-shaped XOL treaty + loss dataset, validates Cedeon's extracted terms, and Cedeon
correctly identifies and explains a potential recovery using exact treaty citations
and deterministic calculations.

---

## The first vertical slice

The slice that proves the product spans Phases 2→6 (add 7→8 for the full experience).
Build it thin end-to-end before widening any layer.

```
synthetic treaty PDF ─▶ parse ─▶ chunks ─▶ AI extraction ─▶ validation workspace
   ─▶ CONFIRM attachment/limit/participation ─▶ executable TreatyVersion (VALIDATED)
synthetic loss CSV ─▶ map columns ─▶ validate ─▶ commit underlying_losses
   ─▶ attach to "Hurricane Demo" loss event
create RecoveryCandidate(treaty_version, layer, event)
   ─▶ deterministic calc: 58,700,000 gross → 8,700,000 layer recovery
   ─▶ allocations: Alpha 4,350,000 / Beta 2,610,000 / Gamma 1,740,000
   ─▶ RecoveryCandidate = NEEDS_REVIEW
```

### Golden end-to-end test (CI)

`apps/api/tests/e2e/test_vertical_slice.py`, driven by `packages/fixtures/`:

1. Seed org + user + cedent + program.
2. Upload the synthetic treaty; run parse job inline; assert pages + clause-aware
   chunks exist with page numbers.
3. Run extraction (recorded fixture / cheap model); assert `attachment` candidate =
   `{amount:"50000000.00", currency:"USD"}` with a citation resolving to the retention
   article, and `limit` = `20000000.00`.
4. Programmatically confirm attachment, limit, currency, and the three participations;
   `POST /treaties/{id}/validate`; assert `TreatyVersion.status = VALIDATED` and
   `treaty_layers` / `treaty_participations` populated.
5. Upload loss CSV, map columns, validate (assert import report), commit; attach to
   `Hurricane Demo`; assert `Σ gross_incurred = 58,700,000.00`.
6. Create RecoveryCandidate; assert `layer_recovery == Decimal("8700000.00")`,
   allocations exactly `4,350,000 / 2,610,000 / 1,740,000`, `Σ allocations ==
   layer_recovery`, `engine_version` recorded, `status == NEEDS_REVIEW`.
7. (Phase 7+) Run investigator; assert every finding has a resolvable citation and no
   finding asserts a recovery number ≠ 8,700,000.
8. Assert an `audit_events` row exists for each transition.

The numeric assertions in steps 5–6 are **frozen golden values**.

---

## Phase 1 — Foundation (detailed plan)

**Goal:** a running monorepo — web ⇄ API ⇄ Postgres — with organizations, users,
memberships, sessions, health checks, generated API client, CI green. **No AI, no
documents, no treaties yet.**

### 1.1 Repo & tooling
- `justfile` (up, down, migrate, revision, test, lint, typecheck, gen-client,
  seed-demo), root `README` pointers, `.editorconfig`.
- `infra/docker-compose.yml`: `postgres` (16 + pgvector image), `minio`, `api`,
  `worker`, `web`. `.env.example`.
- CI (GitHub Actions): `api` job (ruff, mypy, pytest w/ testcontainers Postgres,
  import-linter), `web` job (typecheck, biome, vitest, `build`), `client-drift` job
  (regenerate API client, `git diff --exit-code`).

### 1.2 API skeleton — `apps/api`
- `uv` project; deps: fastapi, uvicorn, pydantic, pydantic-settings, sqlalchemy,
  asyncpg, alembic, argon2-cffi, structlog, opentelemetry-sdk + instrumentation,
  procrastinate, pytest, pytest-asyncio, httpx, hypothesis, testcontainers.
- `app/main.py`: app factory, lifespan (engine, procrastinate), OTel + structlog +
  correlation-ID middleware, `problem+json` exception handlers, `/healthz`
  (liveness) + `/readyz` (DB check).
- `app/core/config.py` (pydantic-settings), `app/core/money.py` (**`Money` VO +
  rounding + `allocate` largest-remainder helper — with its unit tests, even though
  the calc engine lands in Phase 4**), `app/core/security/` (argon2, session tokens),
  `app/core/logging.py`, `app/core/telemetry.py`.
- `app/db/`: async engine/session, `Base`, UUIDv7 default, `TIMESTAMPTZ` mixins,
  Alembic wired to models.
- `app/domain/organizations/`: `Organization`, `User`, `Membership`, `Session`,
  `Role` — domain models + invariants.
- `app/db/models/`: ORM for the above. **Migration 0001.**
- `app/repositories/`: `OrganizationRepo`, `UserRepo`, `MembershipRepo`,
  `SessionRepo` — all org-scoped where applicable.
- `app/services/`: `AuthService` (register org+owner, login, logout, session
  lifecycle), `MembershipService` (invite/list).
- `app/api/dependencies/context.py`: `current_context` → `(user, org, membership,
  role)`; `require_role(...)`.
- `app/api/routes/`: `auth` (`POST /auth/register`, `/auth/login`, `/auth/logout`,
  `GET /auth/me`), `organizations` (`GET /organizations/current`), `memberships`
  (`POST /memberships`, `GET /memberships`). Tag OpenAPI operations with stable
  `operation_id`s for clean client generation.
- `app/jobs/`: procrastinate app + one trivial `ping` task to prove the worker path.
- `app/domain/audit/` + `app/repositories/audit.py`: `AuditRecord` + `AuditRepository.record()`;
  `audit_events` table + append-only trigger (in **migration 0001**). Auth/membership events write audit rows.

### 1.3 Web skeleton — `apps/web`
- Next.js 15 App Router, TS strict, Tailwind v4, hand-rolled shadcn-style primitives,
  Biome, Vitest, Playwright config.
- Route groups `(marketing)` and `(app)`. `(marketing)/page.tsx`: a first-pass
  animated landing page (hero, the "contract → recovery" line, how-it-works, the four
  trust classes FACT/CALCULATION/AI/HUMAN) using `motion` — polish continues, but it
  exists now.
- `(app)`: login page, minimal authenticated shell (nav, org name, sign-out),
  placeholder Dashboard reading `GET /auth/me` + `/organizations/current`.
- `src/lib/api/generated/` via `@hey-api/openapi-ts`; `just gen-client` script;
  same-origin `/api` base; runtime proxy route handler `/api/[...path]` → API URL.
- `src/lib/session.ts`: server-side `getSession()`; `(app)/layout.tsx` route guard.
- TanStack Query provider; one real query (`/auth/me`) wired through the generated
  client.

### 1.4 Tests (Phase 1)
- `tests/domain/test_money.py`: `Money` construction, currency-mismatch raises,
  rounding policy, `allocate` sums exactly (incl. 1/3 residual cases). *(Highest
  priority in this phase.)*
- `tests/api/test_auth.py`: register → login → `/auth/me` → logout; tenant scoping
  (user A cannot read org B); role enforcement.
- `tests/api/test_health.py`; `web` — one Vitest render + one Playwright
  login-happy-path.

### 1.5 Phase 1 exit checklist — ✅ all met (2026-08-30)
- [x] `docker compose up` → web on :3000, API on :8000, both healthy; worker running
- [x] Register org → dashboard → sign out → `/login` (verified via Playwright against the built stack)
- [x] Alembic `upgrade head` clean from empty DB; up/down/up verified; `alembic check` = no drift
- [x] `pytest` green — 50 passed (money golden + Hypothesis, auth, tenancy, roles, audit trigger, contract)
- [x] `pnpm test` green — 6 passed; `pnpm build` green; motion **not** in the app bundle (`/dashboard` 115 kB vs `/` 145 kB)
- [x] mypy clean; ruff clean; `lint-imports` — `domain` imports nothing upward (2 contracts kept); biome clean
- [x] `packages/openapi/openapi.json` committed; CI `contract` job diffs it
- [x] `audit_events` UPDATE/DELETE rejected by DB trigger; `organization.registered` / `auth.login` / `auth.logout` / `membership.added` audited
- [x] Landing page renders with `motion` scroll/entrance animations, light + dark tokens
- [x] Docs updated (status board, summary below, next step)

### What shipped in Phase 1

**Backend** — FastAPI app factory with structlog + OTel + correlation-id middleware +
RFC 9457 errors; `Settings` (pydantic-settings); async SQLAlchemy 2 + Alembic
(`0001_identity_and_audit`); `organizations` / `users` / `memberships` / `sessions` /
`audit_events`; argon2id passwords + HMAC'd server-side session tokens (unknown-user
timing guard); `AuthService` (register / login / logout / authenticate) and
`MembershipService`; repositories with mandatory org-scoping; `current_context` +
`require_role` dependencies; `/healthz` `/readyz` `/auth/*` `/organizations/current`
`/memberships`; **`app/domain/money.py`** — `Money` VO (whole-cent invariant,
currency-checked ops, explicit rounding) + `allocate()` largest-remainder penny
distribution, with golden + property tests; Procrastinate app + `ping` task.

**Frontend** — Next.js 15 App Router, React 19, Tailwind v4 token system (light/dark),
TanStack Query; `(marketing)` animated landing (`motion`, route-group isolated) +
`(app)` authed shell with server-side `getSession()` guard; `/login` + `/register`;
generated typed client (`@hey-api/openapi-ts` from `packages/openapi/openapi.json`);
runtime `/api/[...path]` reverse proxy (ADR-0004); Vitest + Playwright.

**Infra / CI** — `docker-compose` (postgres+pgvector · minio · api · worker · web);
`api.Dockerfile` (uv, also the worker image) + `web.Dockerfile` (Next standalone);
`justfile`; GitHub Actions `ci.yml` (api · web · contract) + `e2e.yml` (compose + Playwright).

**Known follow-ups** (not blocking): `@hey-api/client-fetch@0.10` is deprecated —
bump `@hey-api/openapi-ts` + client when convenient; role/actor enums are VARCHAR
without a DB `CHECK` (app is sole writer; `native_enum` CHECKs don't round-trip
`alembic check`); OTLP export is wired but off by default.

---

## Later phases (adjusted for the Temporal deferral)

- **P2:** ✅ **Complete (2026-08-30).** `ObjectStore` interface (`FilesystemObjectStore`
  dev/test, `S3ObjectStore` MinIO/S3). `DocumentParser` interface + `PyMuPDFParser`
  (pages, blocks, bbox, font-size heading heuristic); `DoclingParser` is a documented
  stub behind the `docling` extra + `CEDEON_DOCUMENT_PARSER` switch. Pure
  `chunk_document` (heading-aware, section paths, exact char offsets). Migration 0002:
  `documents` (immutable, sha256-deduped) · `document_parses` (state machine,
  supersede-on-reparse) · `document_pages` · `document_chunks`. Procrastinate
  `parse_document` job (parse + chunk in one transaction; embedding split comes in
  P3). `POST /documents` (multipart) + list/detail/pages/chunks/content endpoints.
  Web: Documents library (upload, status polling) + two-pane viewer (page text |
  chunks). 26 new tests (chunker, PyMuPDF, filesystem store, document API + tenant
  isolation + audit). **Follow-up:** implement + verify `DoclingParser` and add its
  ML deps to a dedicated worker image (it cannot run in CI).
- **P3:** Extraction as a structured-output call (PydanticAI `output_type`). Hybrid
  retrieval (FTS + `halfvec`/HNSW + RRF). `treaty_term_candidates` + provenance.
  Two-panel validation workspace. `treaty_versions` freeze on `VALIDATED`. First
  Pydantic Evals dataset (incl. injection fixture).
- **P4:** `domain/recoveries/calculations/` — pure `calculate_xol_recovery` +
  `allocate_recovery`, `ENGINE_VERSION`, golden table + Hypothesis properties.
  `treaty_layers` / `treaty_participations` from validated terms.
- **P5:** `loss_imports` → `loss_import_rows` (raw JSONB) → column mapping →
  validation report → `underlying_losses`. Keep raw file + mapping + rows forever.
- **P6:** `RecoveryCandidate` from `(treaty_version, layer, loss_event)`;
  immutable `recovery_calculations` + `recovery_allocations`; currency-mismatch flag;
  queue + detail UI.
- **P7:** Recovery Investigator (PydanticAI agent, typed read-only tools, bounded,
  `agent_runs` / `tool_calls`), structured `RecoveryInvestigation` + normalised
  findings with citations. Investigator eval suite.
- **P8:** `recovery_packet_versions` with statement classification
  (FACT / CALCULATION / AI INTERPRETATION / HUMAN DECISION); `reviews` flow
  (confirm/edit/reject/request-info) with before/after + reason. HTML packet.
- **P9:** Notice drafter — approved-values whitelist in, draft out, human approval to
  send, never auto-sent.
- **P10:** OTel dashboards, AI cost/latency views, calculation-trace viewer, audit
  views. **Decision point:** adopt Temporal only if real long-running multi-party
  compensating workflows have emerged; otherwise keep Procrastinate + state machines.

## End-of-phase ritual (every phase)

Summarize what changed · list files created/modified · run tests, typecheck, lint,
build · report failures honestly · update this status board · name the next smallest
vertical step.
