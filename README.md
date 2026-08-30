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

## Status

- **Phase 0 — Architecture review:** complete. Verdict *partially agree* (one material change — Temporal deferred; see [ADR-0007](docs/DECISIONS.md)).
- **Phase 1 — Foundation:** complete (2026-08-30). Monorepo, FastAPI + async SQLAlchemy + Alembic, org/user/membership/session auth, append-only audit, the `Money` value object with golden + property tests, Next.js 15 app (animated landing, authed dashboard), Docker Compose, CI. **No AI yet.**
- **Phase 2 — Document pipeline:** complete (2026-08-30). Object storage (`ObjectStore`: filesystem / S3+MinIO), `DocumentParser` interface + `PyMuPDFParser`, heading-aware chunking, `documents`/`document_parses`/`document_pages`/`document_chunks` (migration 0002), a Procrastinate `parse_document` job, upload + viewer UI. Verified end-to-end through the containerized stack.
- **Next:** Phase 3 — treaty extraction + human validation workspace. See [docs/ROADMAP.md](docs/ROADMAP.md).

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
  fixtures/   Synthetic treaty + loss + golden-recovery fixtures (shared by tests)
infra/        docker-compose, Dockerfiles, deployment config
docs/         Architecture & product documentation
scripts/      Dev + CI helper scripts
```
