# Cedeon — Roadmap

When choosing between "build more framework" and "get treaty → validated terms →
deterministic recovery working," choose the latter.

**Positioning vs. scope.** The long-term thesis (PRODUCT.md §1) is that Cedeon is an
independent reinsurance financial-intelligence layer surfacing many financially
material exception types. This roadmap is **unchanged** by that: the MVP is exactly
the pipeline below — treaty → parsed document → AI-extracted terms with provenance →
human validation → executable XOL treaty → loss ingestion → deterministic
`RecoveryCalculation` → `RecoveryCandidate` → Recovery Investigator → Recovery
Packet → human review → notice draft. No generalised financial-exception model,
no genericising `RecoveryCandidate` (ARCHITECTURE.md §9).

---

## Status board

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Architecture review + docs | ✅ **Complete** — verdict *Partially agree* (Temporal deferred) |
| 1 | Foundation (monorepo, API, web, DB, auth, CI) — **no AI** | ✅ **Complete** (2026-08-30) |
| 2 | Document pipeline (upload → storage → parse → pages/chunks → viewer) | ✅ **Complete** (2026-08-30) |
| 3 | Treaty extraction + human validation workspace | ✅ **Complete** (2026-08-30) — live extraction verified end-to-end against Anthropic (`pytest -m live`, `claude-opus-5`) |
| 4 | Executable XOL model + deterministic calculation engine | ✅ **Complete** (2026-08-30) |
| 5 | Loss import (CSV → mapping → validation → underlying losses) | ✅ **Complete** (2026-08-30) — **no AI** |
| 6 | Recovery Candidate (validated treaty + loss event → calc → candidate + queue UI) | ✅ **Complete** (2026-08-30) — **no AI** |
| 7 | Recovery Investigator (one bounded read-only agent + evals) | ✅ **Complete** (2026-08-30) — live-verified |
| 8 | Recovery Packet + human review / approval flow | ✅ **Complete** (2026-08-30) — **no AI** |
| 9 | Notice draft (draft only, human approval, never auto-sent) | ✅ **Complete** (2026-08-30) — live-verified |
| 10 | Durability + observability hardening (evaluate Temporal *here*) | ✅ **Complete** (2026-08-30) — Temporal **not adopted** |
| — | UI refresh — design system, marketing site, app shell (no backend change) | ✅ **Complete** (2026-08-30) — ADR-0023; trust-class language unchanged |
| — | Post-MVP UX — reframe (A), recovery workspace (B), collection tracking (C) + portfolio screen, occurrence basis (finding 8) | ✅ **Complete** (2026-08-31) — ADR-0024; migrations 0010–0011 |

**The 10-phase MVP is complete.** Full pipeline: treaty → parsed document → AI-extracted
terms with provenance → human validation → executable XOL treaty → loss ingestion →
deterministic `RecoveryCalculation` → `RecoveryCandidate` → Recovery Investigator →
Recovery Packet → human review → notice draft — all built, tested (219 backend + 4 live
evals), and running through the containerized stack.

**First meaningful success criterion:** a reinsurance professional uploads a
real-shaped XOL treaty + loss dataset, validates Cedeon's extracted terms, and Cedeon
correctly identifies and explains a potential recovery using exact treaty citations
and deterministic calculations.

**Post-MVP UX direction.** [docs/UX_STUDY.md](UX_STUDY.md) studies the in-app workflow
from the ceded-reinsurance analyst's chair and proposes a re-framed IA (Home worklist ·
Reinsurance program · Recoveries · Audit log), two guided wizards, and a single-page
recovery workspace — **no domain-model change**. Order: **A** reframe · **B** recovery
workspace · **C** collection tracking (new phase) · **D** multi-layer programmes.

- **A · Reframe — ✅ done (frontend only).**
  - *A1 · nav + rename + Home worklist* — ✅ done. Four-area sidebar (Home · Reinsurance
    program · Losses · Recoveries · Oversight); "recovery candidate" → *recovery*,
    "treaty library" → *treaties*, "loss imports" → *import claims*, "underlying losses"
    → *claims*, "activity" → *audit log*; Home is a "needs your attention" queue (terms
    to validate, recoveries to review) over counts. URLs unchanged.
  - *A2 · guided wizards* — ✅ done & e2e-verified (both walk end-to-end against the
    live stack; no new endpoints).
    - "Set up a treaty" (`/treaties/new`) — upload wording → parse → program/cedent/
      name inline → extract → hands off to the existing validation workspace.
    - "Start a recovery" (`/recovery-candidates/new`) — loss event (leads with an
      occurrence-basis reminder) → claims (upload + guessed mapping + validate +
      commit, with an escape hatch to the full import screen) → responding treaty →
      calculate → the recovery detail page.
    - `components/ui/stepper.tsx`; the bare inline create forms on Treaties and
      Recoveries are retired for "Set up" / "Start" buttons.
  - *A3 · fold the nav* — ✅ done. "Documents" and "Import claims" are gone from the
    top nav: treaty detail links its parsed wording from a "Source document" card,
    the loss-events list and each loss-event detail page carry an "Import claims"
    action, and "Recoverables" (the Phase-C portfolio screen) joins the Recoveries
    group. `/documents` and `/loss-imports` remain as full screens, link-reachable
    and each with a BackLink to its parent.

- **B · Recovery workspace — ✅ done & e2e-verified (frontend only, no new endpoints).**
  `/recovery-candidates/[id]` is one page with a left rail — **Loss basis ·
  Calculation · Investigation · Packet · Notice · Collection** — each section opens
  in place via `?section=`; done sections show a check, Notice is locked until the
  recovery is confirmed, Collection is locked (Phase C). `recovery-packet-view` /
  `recovery-notices-view` gained an `embedded` prop; `/[id]/packet` and `/[id]/notices`
  are now redirects to `?section=`. Verified by the new **golden-path e2e**
  (`e2e/golden-path.spec.ts`, gated behind `CEDEON_LIVE_E2E` since it calls the real
  Anthropic API) — the full slice: register → set up treaty → validate → start
  recovery → import claims → the deterministic `$8,700,000.00` and its
  `4.35M / 2.61M / 1.74M` split → the workspace rail. This is the "Golden
  end-to-end test" below, finally realised.

- **C · Collection tracking — ✅ done (ADR-0024, migration 0010).** A first-class
  `recoverables` table, one row per `(recovery, reinsurer)`, materialised from the
  confirmed calculation's allocations. `expected_amount` is a fact; `status`
  (pending → notified → agreed → billed → collected, + disputed / written_off),
  `agreed` / `billed` / `collected` / `due_date` / `note` are human facts on the
  audit trail; aging is derived. `GET|POST /recoverables*` + the workspace's
  **Collection** section + a Home "Open recoverable" figure. Pure — no AI.
  - **Portfolio screen — ✅ done (frontend only).** `/recoverables` serves the head
    of ceded reinsurance: open / collected / overdue stats, an aging bar chart, and
    the legs table filterable by status or "overdue", worst-overdue first, each row
    linking into its recovery's Collection section.

- **Finding 8 · occurrence basis — ✅ done (migration 0011).** `loss_events` gains
  `peril` and `hours_clause_hours` — human facts the recovery wizard already asked
  for and now records. Informational only; the engine does not yet apply an hours
  clause.

**Recovery-control build (from the Aug-2026 audit — make Cedeon *watch*, not just
calculate).** The verdict: the spine is right, the posture is wrong. Move the centre
of gravity from "start a recovery" to "here is what needs you today."

- **Now — ① Recovery Work Queue — ✅ done.** `app/domain/worklist.py` (pure, deterministic,
  explainable ranking — every urgency contribution is a named term) + `WorklistService`
  (unions term-validation, recovery-review, packet-approval, overdue-recoverable signals;
  notice-due / drift / suggested hooks stubbed for ②③⑤) + `GET /worklist`. Home is
  rebuilt around it: one ranked "Needs you" list (icon by kind, countdown / age, amount,
  deep link) + four at-a-glance figures (open recoverable, overdue, largest open recovery,
  count). 15 new tests (249 total).
- **Now — ② structured notice terms + computed deadlines — ✅ done (migration 0012).**
  `app/domain/recoveries/obligations.py` (pure) — `NoticeTermSpec {days, trigger, basis}`,
  `notice_deadline()` with calendar / business-day math. `ObligationService` reads the
  validated `notice_provision` term, picks the reference date its trigger points at
  (loss date / `recovery_candidates.knowledge_date` / first claim advice) and computes
  the deadline — the AI never sets a date. `PUT /treaties/{id}/versions/{vid}/notice-term`
  (operational metadata, editable post-validation, audited), `POST
  /recovery-candidates/{id}/knowledge-date`, `notice_obligation` on the candidate detail,
  a `notice_due` item on the worklist that clears when a notice is approved. Web: a
  notice-provision editor on treaty detail, a "Notice obligation" card + rail countdown
  on the recovery workspace. 16 new tests.
- **Now — ③ auto-recalc on loss commit + drift alerts — ✅ done (migration 0013).**
  Committing a claims import now recomputes every non-rejected recovery on the touched
  events (`RecoveryCandidateService.recalculate_for_events`, reuses the existing
  `input_hash` guard so it is idempotent). A figure that moves without a human is
  *drift*: `recovery_candidates.drifted_at` + `pre_drift_recovery` are stamped, a
  confirmed candidate reverts to needs-review, a `system` audit row is written, and a
  `recovery_drift` worklist item shows the before → after until the next human review
  clears it. Web: a "number moved" banner on the workspace Calculation section.
  `commitLossImport` returns `recoveries_drifted`. 4 new tests.
- **Now — ④ golden demo seed + walkthrough refresh — ✅ done.** `just seed-demo` now
  builds the whole golden desk deterministically (no AI): a validated `$20M xs $50M`
  treaty with a structured notice term, the committed Hurricane Demo event (10 claims,
  `$58.7M`), a confirmed recovery with its calculation + `4.35 / 2.61 / 1.74M` split,
  and three recoverables — one notified, one billed-and-overdue, one collected. A first
  run and every demo now open on a populated Home worklist instead of an empty app.
  `packages/fixtures/README.md` walkthrough refreshed for the post-A3 navigation.
- **Next — ⑤ system-suggested recovery candidates — ✅ done.**
  `app/domain/recoveries/suggestions.py` (pure) screens each validated treaty layer
  against each loss event — currency, the treaty window, gross above the attachment —
  and proposes opening a recovery where none exists. `SuggestionService` +
  `GET /recovery-candidates/suggestions` (`?loss_event_id=`) + a `suggested_recovery`
  worklist item + a "Treaties that may respond" card on loss-event detail. Cedeon
  *proposes*; the analyst promotes it through the normal create flow, which suppresses
  the suggestion. No AI. 17 new tests.
- **Next — ⑦ aged-recoverable intelligence — ✅ done.** `app/domain/recoveries/chasing.py`
  (pure) — from a leg's status, days in that status (`entered_status_on` picks the right
  stamp), and how overdue it is, a deterministic `NextAction` + human text + urgent flag:
  *send the notice · chase an acknowledgement · issue the bill · chase payment · resolve
  the dispute*. Every `RecoverableOut` now carries `days_in_status` + `next_action*`; the
  recoverables portfolio and the workspace Collection section show a "Next" column, and
  the `recoverable_overdue` worklist item's detail is the recommendation. No AI. 10 new
  tests.
- **Next — ⑥ multi-layer programmes — ✅ done (v1, no migration).** A treaty version
  carries a *stack* of XOL layers. `PUT /treaties/{id}/versions/{vid}/layers` (bottom-to-top,
  editable until validation) + a layer-stack editor on treaty detail; `validate_version`
  freezes the stack (or builds one layer from the terms, as before). `POST /recovery-candidates`
  opens a candidate on **every layer the event pierces** (per-layer deterministic calc), the
  bottom one returned; suggestions screen every layer. `RecoveryCandidateService.create` now
  returns `list[RecoveryCandidate]`. Treaty detail shows the tower. 8 new tests, 290 backend.
  *Deferred:* per-layer participations (shared across the tower for now), a grouped
  "programme" view of the sibling candidates, multi-layer recovery-preview.
- **Next — ⑧ real extraction/investigator eval datasets.**
- **Later — ⑨ endorsement change intelligence · ⑩ reinstatement premium math ·
  ⑪ expected-vs-billed-vs-collected reconciliation · ⑫ CAT/event intelligence.**

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

### Golden end-to-end test

**Realised as `apps/web/e2e/golden-path.spec.ts`** (Playwright, driven by
`packages/fixtures/`) — it walks the whole slice through the real UI: register →
"Set up a treaty" wizard → **live** Anthropic extraction → validate every term →
"Start a recovery" wizard → import the claims CSV → the deterministic
`$8,700,000.00` with its `4,350,000 / 2,610,000 / 1,740,000` split → the recovery
workspace and its section rail. Gated behind `CEDEON_LIVE_E2E` (real API cost), so
the default `pnpm test:e2e` and the CI e2e job skip it; run it with
`CEDEON_LIVE_E2E=1 pnpm test:e2e golden-path`.

The original spec below was for an API-level `tests/e2e/test_vertical_slice.py` with
a recorded/cheap model — still worth adding for CI coverage without the live cost,
but the UI-level test is the one that exists and is green.

Original spec — `apps/api/tests/e2e/test_vertical_slice.py`, driven by `packages/fixtures/`:

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
- **P3:** ✅ **Complete (2026-08-30).** Reinsurance structure (migration 0003:
  `cedents` · `reinsurers` · `reinsurance_programs` · `treaties` · `treaty_versions`
  with the DRAFT→…→VALIDATED lifecycle · `treaty_layers` · `treaty_participations` ·
  `treaty_terms`). Migration 0004: `agent_runs` · `prompt_versions` · `citations` ·
  `treaty_term_candidates` · append-only `reviews`. Extraction is a single PydanticAI
  `output_type` call (`app/ai/extraction`, `anthropic:claude-opus-5` default, provider
  registry in `app/ai/models`), run by the `extract_treaty` Procrastinate job;
  material money terms without a citation are auto-downgraded to `ambiguous`
  (ADR-0011). `ValidationService`: review each candidate (confirm/edit/reject/
  ambiguous → `reviews` + audit), then `validate_version` freezes the executable
  `$limit xs $attachment` layer + participations. Web: Programs, Treaty Library,
  Treaty Detail, and the two-panel **validation workspace** (document ∣ candidates
  with confidence + exact citation, jump-to-page). 14 new tests drive the full
  golden path with the model call faked; `tests/ai/test_extraction_live.py`
  (`-m live`) hits the real API and is verified once a workspace-scoped key is set.
  **Scope note:** hybrid retrieval (FTS + `halfvec`/HNSW + RRF) and embeddings are
  **deferred to Phase 7** — treaties are small enough to pass all chunks to
  extraction, and targeted retrieval is what the Recovery Investigator needs. See
  ADR-0016.
- **P4:** ✅ **Complete (2026-08-30).** `app/domain/recoveries/calculations/xol.py`
  — pure `calculate_xol_recovery` (`max(gross − attachment, 0)` then `min(·, limit)`,
  currency-checked, negatives/zero-limit rejected, step `trace`) + `allocate_recovery`
  (each participant `layer_recovery × share`, penny-exact via the `Money.allocate`
  largest-remainder split, cedent retention on partial placement) + `calculate_recovery`.
  `ENGINE_VERSION = "1.0.0"`. **28 tests**: the golden `$20M xs $50M` table
  (30/50/50.01/55/58.7/70/70.01/100 M), boundary + invalid-input cases, the
  `8.7M → 4.35/2.61/1.74` allocation, and Hypothesis properties (recovery ∈
  `[0, limit]`, monotonic in gross loss, allocations sum exactly). A 4th import-linter
  contract forbids the engine from importing anything but `Money` (ADR-0010).
  Read-only `POST /treaties/{id}/recovery-preview` runs the engine against a
  *validated* treaty (no persistence — Phase 6 owns `RecoveryCandidate`); shown as a
  "what-if" card on Treaty Detail with the calculation trace visible.
- **P5:** ✅ **Complete (2026-08-30). No AI in this pipeline.** Migration `0005`:
  `loss_imports` (raw file in object storage + sha256 dedupe + `header_columns` +
  `column_mapping` + `report` JSONB), `loss_import_rows` (immutable `raw` JSONB per
  row + `parsed` + `status` + `issues`), `loss_events`, `underlying_losses`
  (immutable snapshot of a committed row; `NUMERIC(20,2)` money, `gross_incurred >= 0`
  CHECK, `UNIQUE(loss_import_row_id)`, `RESTRICT` on the import/row FKs so provenance
  can't be deleted out from under a loss). `app/domain/losses/` is pure: a
  `CanonicalField` schema (`FIELD_SPECS`, required = claim_id / date_of_loss /
  currency) plus `validate_rows` — deterministic parsing (6 date formats, `$`/comma
  stripping, `HALF_EVEN` cents), duplicate-claim detection flagged on *every*
  offending row, `gross_incurred` derived from paid + case reserve when absent,
  a tolerance warning when incurred ≠ paid + reserve, and per-currency incurred
  totals that exclude errored rows. Flow: `POST /loss-imports` (multipart CSV,
  stdlib `csv`) → `POST /loss-imports/{id}/mapping` (re-runs validation, returns the
  report) → `POST /loss-imports/{id}/commit` (valid rows → `underlying_losses`,
  grouped into a find-or-create `LossEvent` by the `loss_event_identifier` column or
  a supplied `loss_event_id`; event date range + currency recomputed; errored rows
  skipped and left on the import). `GET /loss-events`, `POST /loss-events`,
  `GET /loss-events/{id}` (claim schedule + per-currency totals). Every step writes an
  `audit_events` row. **27 new tests** (148 total): pure-validation unit tests and an
  API slice that uploads the synthetic 10-claim hurricane CSV, maps it, and commits
  losses summing to exactly **USD 58,700,000.00** in one event — the gross loss the
  Phase 4 engine turns into the `$8.7M` layer recovery. Web: `/loss-imports` (list +
  upload), `/loss-imports/{id}` (column-mapping workspace with header-name
  auto-guess, validation report, row preview, commit), `/loss-events` (+ manual
  create), `/loss-events/{id}` (claim schedule). Nav items enabled.
- **P6:** ✅ **Complete (2026-08-30). No AI (ADR-0010/0018).** Migration `0006`:
  `recovery_candidates` (mutable review object, one per
  `(treaty_version, treaty_layer, loss_event)` — `UNIQUE`, re-POST returns the
  existing one; `status`, `currency`, `gross_event_incurred`, `currency_mismatch`,
  `current_calculation_id`), immutable `recovery_calculations` (`engine_version`,
  frozen `inputs` JSONB, every engine output + `trace` + `input_hash`) and
  immutable `recovery_allocations` (penny-exact per-participant share). All FKs to
  executable truth are `RESTRICT`; the candidate↔calculation circular FK is added
  post-`create_table` so `alembic check` stays clean.
  `app/domain/recoveries/candidate.py` adds `RecoveryCandidateStatus` and the pure
  `recovery_input_hash` (SHA-256 over engine version + version/layer/event ids +
  gross/attachment/limit + sorted participations; scale-insensitive). Flow:
  `POST /recovery-candidates {treaty_id, loss_event_id}` → validated version + its
  layer, deterministic gross = Σ `gross_incurred` of the event's losses **in the
  layer currency** (others flagged, excluded — no FX), `calculate_recovery(...)`,
  persist, `status = NEEDS_REVIEW`. `POST /{id}/recalculate` re-runs the engine and
  stores a **new** calculation row only when `input_hash` changed (a later import
  committed into the event), reverting a `CONFIRMED` candidate to `NEEDS_REVIEW`.
  `POST /{id}/review` — `confirm` | `reject` | `request_info`, each an append-only
  `reviews` row + `audit_events`. **19 new tests** (167 total): the input-hash unit
  suite and an API slice where the golden validated treaty + the Hurricane Demo
  event produce `layer_recovery = 8,700,000.00`, allocations
  `4.35M / 2.61M / 1.74M`, `Σ == layer_recovery`; plus recalc-on-new-loss
  (`60.7M → 10.7M`, capped at the 20M limit) and the currency-mismatch path. Web:
  `/recovery-candidates` (queue, status filter, create form) and
  `/recovery-candidates/{id}` (calculation + trace + allocations, review actions,
  recalculate, calculation & review history). Nav enabled.
- **P7:** ✅ **Complete (2026-08-30). First AI agent — bounded, read-only.** Migration
  `0007`: `tool_calls` (per-invocation telemetry on an `agent_run`),
  `recovery_investigations` (immutable per run; newest non-superseded is current) and
  `recovery_investigation_findings` (normalised, optional `citation_id`).
  `app/ai/investigator/`: a PydanticAI agent with `output_type=RecoveryInvestigation`
  and **six typed read-only tools** — `get_recovery_calculation`,
  `get_validated_terms`, `get_participants`, `get_loss_event`,
  `list_underlying_losses`, `search_treaty` (Postgres FTS `ts_rank` over the
  clause-aware chunks — lexical for now, ADR-0019). No write tools. Bounded by
  `UsageLimits` (request / tool-call / token caps) + a wall-clock timeout, all
  configurable. The deterministic recovery figure is handed in as a fact to explain
  — a `recomputed_a_different_number` flag surfaces disagreement, it never emits a
  rival number. `InvestigationService` runs it (or a fake in tests), records the
  `agent_run` + `tool_calls`, and **grounds every finding**: a must-cite finding
  whose quote is not actually on the cited page loses its citation and is downgraded
  to an ambiguity (ADR-0011). `POST /recovery-candidates/{id}/investigate` enqueues
  the `investigate_recovery_candidate` job; the candidate detail carries the
  investigations. **12 new tests** (179 + 2 live): schema/grounding units, an API
  slice (persist → ground → supersede → audit → tool-call log), and a **live eval**
  (`pytest -m live`, `claude-opus-5`) asserting every citation resolves to real page
  text, the agent used its tools, and it did not change the `8,700,000.00` figure.
  Web: an "AI investigation" panel on the candidate detail — applicability badge,
  cited findings badged *AI interpretation*, injection flag, poll-while-running.
- **P8:** ✅ **Complete (2026-08-30). No AI — deterministic assembly.** Migration
  `0008`: `recovery_packets` (one per candidate; mutable only for
  `current_version_id` + `human_overrides`) and immutable `recovery_packet_versions`
  (`version_no`, `status` draft/approved/rejected/superseded, `content` JSONB,
  `rendered_html`, `calculation_id` `RESTRICT`, `investigation_id` `SET NULL`,
  approver + timestamps; candidate↔version circular FK hand-split for
  `alembic check`). `app/domain/recoveries/packet.py` is pure: `assemble_packet`
  arranges validated terms (FACT), the engine's calculation + trace + allocations
  (CALCULATION), the investigator's findings with their citations
  (AI_INTERPRETATION), and the review decisions + human edits (HUMAN_DECISION) into
  classified `PacketStatement`s; `render_packet_html` emits a single self-contained
  HTML file with the four classes visually distinct. `POST /recovery-candidates/{id}/packet`
  generates a new immutable version each time and supersedes the rest;
  `POST /recovery-packets/{pid}/versions/{vid}/review` is `confirm` | `reject` |
  `request_info` | `edit` — an `edit` records a `reviews` row with before/after,
  stores the override on the packet, and regenerates a new version with the
  statement replaced and flagged `edited_by_human`. `GET .../html` streams the
  rendered artifact. **17 new tests** (196 + 2 live): pure assembly/HTML units and an
  API slice (4 classes present, the `8,700,000.00` figure + `4.35/2.61/1.74M`
  allocations as CALCULATION, cited findings as AI_INTERPRETATION, approve → Review
  + audit, regenerate supersedes, edit → before/after + new version). Web:
  `/recovery-candidates/{id}/packet` — the classified packet, review actions,
  inline statement editing, version list, "open printable HTML".
- **P9:** ✅ **Complete (2026-08-30). Live-verified.** Migration `0009`:
  `recovery_notices` (per candidate; mutable while `DRAFT`, frozen on approval;
  re-drafting supersedes the prior notice of the same kind). `app/domain/recoveries/notice.py`
  is pure: `NoticeContext` is the **whitelist of approved values** the drafter may
  use — cedent / treaty / layer / loss-event / the deterministic recovery figure /
  the validated notice provision / the participants — and `to_prompt()` is its
  deterministic serialization. **No raw document text, no unvalidated AI output.**
  `app/ai/notice/`: one PydanticAI `output_type=NoticeDraft` call — **no tools**,
  timeout-bounded. The drafter runs only after the candidate is `CONFIRMED`
  (`NoticeService.draft`, via the `draft_recovery_notice` job), records an
  `agent_run`, and the candidate advances to `NOTICE_DRAFTED`. Review is
  `confirm` (freeze) | `reject` | `request_info` | `edit` (in-place on the draft,
  before/after in `reviews`). `POST /recovery-candidates/{id}/notices`,
  `GET .../notices`, `GET /recovery-notices/{id}`, `POST /recovery-notices/{id}/review`
  — and **deliberately no send action anywhere**: a notice's terminal state is
  `APPROVED` and a human takes it from there. **16 new tests** (208 + 3 live): the
  context-whitelist unit suite, an API slice (draft from confirmed candidate →
  body carries the `8,700,000.00` figure + treaty + recipient, `used_only_provided_facts`,
  candidate → notice_drafted, agent_run + audit; edit before/after; approve freezes;
  can't draft an unconfirmed candidate; a test asserting *no* `send` operation
  exists), and a **live eval** (`pytest -m live`, `claude-opus-5`) checking the
  draft uses only provided facts, keeps the figure unchanged, stays indicative
  (no admission / agreement / payment), and invents no email address. Web:
  `/recovery-candidates/{id}/notices` — draft form, the rendered notice, edit /
  approve / reject, history.
- **P10:** ✅ **Complete (2026-08-30).**
  **The Temporal decision point:** the evaluation found **no** long-running,
  multi-party, compensating workflows — every job is short (parse / extract /
  calculate / investigate / draft) or a human waiting on a status. **Temporal is
  not adopted**; Procrastinate + entity state machines + the append-only audit log
  remain (ADR-0007 status updated, ADR-0022).
  **Durability:** the four AI/parse jobs now carry a `RetryStrategy` (exponential /
  linear backoff) for transient provider / storage failures; `AgentRunRepository.has_active_run`
  gives each AI service an in-flight guard so a double click plus a job retry
  racing cannot start a second run (a non-stale `RUNNING` `agent_run` for the same
  subject → `ConflictError`, which the job treats as a no-op, not a retry).
  `/readyz` now also probes the object store.
  **Observability:** `app/repositories/activity.py` + `app/services/activity.py` +
  `GET /activity/agent-runs` (+ `/{id}` with tool calls + structured output),
  `GET /activity/audit` (filterable feed of the append-only log), and
  `GET /activity/ai-spend` (per-agent + per-day token / cost / failure rollup).
  Web: an **Activity** screen (AI runs · Audit log · AI spend — screen 11).
  **11 new tests** (219 total): the activity API slice, the in-flight guard + stale
  fallback, and a retry-strategy check. OpenTelemetry stays wired-but-off
  (`CEDEON_OTEL_ENABLED`) — the `agent_runs` / `audit_events` tables are the
  first-class record; OTLP export is the optional add-on, not a dependency.

## End-of-phase ritual (every phase)

Summarize what changed · list files created/modified · run tests, typecheck, lint,
build · report failures honestly · update this status board · name the next smallest
vertical step.
