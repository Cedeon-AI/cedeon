# Cedeon — Deployment

The demo runs on **Render** from [`infra/render.yaml`](../infra/render.yaml): `web`
(public) + `api` (private) + `worker` + managed Postgres, built from the existing
Dockerfiles. Object storage is **AWS S3**; email is **Amazon SES**. The rationale
and the AWS growth path are in [DECISIONS.md ADR-0027](DECISIONS.md).

Cedeon holds no SOC 2 / ISO / HIPAA attestation and none is claimed
([SECURITY.md](SECURITY.md)).

---

## One-time setup

### 1. AWS — S3 bucket + SES + one IAM user

- **S3**: create a private bucket (e.g. `cedeon-prod`, region `us-east-1`).
  Block all public access. Default encryption on (SSE-S3 or SSE-KMS).
- **SES**: verify the sending domain `cedeon.ai` (add the DKIM CNAMEs + the SPF
  TXT record to DNS). Request production access (out of the SES sandbox) — until
  then SES only sends to verified addresses. Set a verified `From` like
  `no-reply@cedeon.ai`.
- **IAM user** `cedeon-app` with an access key and a least-privilege policy:
  `s3:GetObject` / `PutObject` / `DeleteObject` / `ListBucket` on that bucket only,
  and `ses:SendEmail` (optionally scoped to the verified identity).

### 2. Render

1. **New → Blueprint**, point it at the repo. Render reads `infra/render.yaml` and
   proposes `cedeon-web`, `cedeon-api`, `cedeon-worker`, `cedeon-db`.
2. Fill the `sync: false` values it prompts for (they land in the `cedeon-core`
   env group, shared by api + worker):

   | Key | Value |
   |---|---|
   | `CEDEON_S3_BUCKET` | your bucket name |
   | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | the `cedeon-app` key |
   | `ANTHROPIC_API_KEY` | your key (+ `ANTHROPIC_WORKSPACE_ID` if workspace-scoped) |
   | `CEDEON_OPS_EMAIL` | where new-workspace + budget alerts go |

3. Apply. First deploy builds three images and runs `alembic upgrade head` in the
   api's `preDeployCommand`.
4. **Verify**: `https://cedeon-api…` is *not* public (it's a Private Service);
   `https://cedeon-web….onrender.com` loads; `…/api/healthz` returns ok; register
   is gated (`/register` asks for an access code).
5. Set an **Anthropic workspace spend limit** in the Anthropic console as the outer
   backstop; per-org caps (below) are the inner one.

### 3. Domain + TLS

Add `cedeon.ai` (and `www`) to the `cedeon-web` service in Render — it provisions
TLS automatically. Then **override `CEDEON_PUBLIC_BASE_URL`** on the `cedeon-api`
service to `https://cedeon.ai` so invitation links are correct. (`demo.cedeon.ai`
works the same way if you want to keep the apex for the marketing site initially.)

---

## Day-to-day

| Task | How |
|---|---|
| Let a prospect in | `just mint-code "Acme Re" --budget 50` (run against the prod DB, or `render` shell on `cedeon-api`) → send them the code |
| Change an org's AI budget | `just set-org-budget acme-re 100` (or `unlimited`) |
| Shut off all new signups | set `CEDEON_SIGNUP_MODE=closed` on `cedeon-api` |
| Kill all AI (incident) | set `CEDEON_AI_ENABLED=false` on api **and** worker |
| See spend | the app's **Activity → AI spend** tab, per org; ops email fires at 80% of budget |
| Ship a change | push to `main`; CI gates, then Render auto-deploys (`autoDeploy: true`) |

`mint-code` / `set-org-budget` need the prod `CEDEON_DATABASE_URL`. The simplest
path is Render's shell on the `cedeon-api` service: `alembic` and the scripts are on
`PATH` — `python -m app.scripts.mint_signup_code "Acme Re" --budget 50`.

---

## Known follow-ups (not blockers for a demo)

- **Sentry** on api + web (error tracking) — the code has no integration yet; add
  the SDK + `SENTRY_DSN` when it matters.
- **Rate-limiting** auth / invitation / register endpoints (SECURITY.md §2).
- **Postgres PITR** — enable it on `cedeon-db` before real customer data lands.
- **Migrations before scaling the api past one replica** — already handled
  (`preDeployCommand`), but confirm if you change the api's start command.
- **Docling** parser will make the worker image multi-GB — bump the worker plan
  then; PyMuPDF needs almost nothing today.

## Moving to AWS later

Same Docker images on ECS/Fargate (two services: api, worker), `pg_dump` → RDS
Postgres, the same S3 bucket, the same env-var names in Secrets Manager. The
codebase, the single-origin topology, tenancy, and auth do not change (ADR-0027).
