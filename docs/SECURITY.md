# Cedeon — Security & Data Handling

Design correctly from day one **without claiming certifications we do not hold.**
Cedeon has **no** SOC 2 / HIPAA / ISO / PCI attestation. Do not state or imply
otherwise in product, marketing, or docs.

---

## 1. Tenancy & isolation

- Every domain row below `organizations` carries a non-null `organization_id`.
- **Tenant scope is derived from the authenticated session, server-side. Never from a
  request body, query parameter, header, or JWT claim the client can set.**
- A single FastAPI dependency (`current_context`) resolves `(user, organization,
  membership, role)` from the session cookie. Every route depends on it.
- The repository layer takes `organization_id` from that context and adds it to every
  query. A repository method that can run without an org filter is a bug; an
  import-linter / lint rule and code review enforce this.
- Cross-tenant reference is structurally impossible: child creation validates that
  every referenced parent belongs to the same org.
- **Defense in depth (Phase 10+, not MVP):** PostgreSQL Row-Level Security with a
  per-request `SET LOCAL app.org_id`. App-layer scoping is the MVP primary control.

## 2. AuthN / AuthZ

- Email + password. Hash with **argon2id** (vetted library, no hand-rolled crypto).
- **Server-side sessions** in Postgres (`sessions.token_hash`, `expires_at`,
  `revoked_at`); opaque token in an `HttpOnly`, `Secure`, `SameSite=Lax` cookie on
  the single public origin. No JWT for session state in MVP.
- Rotation on privilege change; explicit logout revokes; idle + absolute expiry.
- Authorization: role check (`owner` / `admin` / `member` / `viewer`) on mutating
  routes; object-level checks that the target belongs to the caller's org. Approvals
  and reviews require at least `member`.
- `password_hash` is nullable so SSO / SAML (e.g. WorkOS) attaches later without
  changing the meaning of existing rows. **Not built in MVP** — but enterprise
  reinsurance buyers will require it, so the seam exists.
- Rate-limit auth endpoints; generic failure messages; audit every auth event.

## 3. Object storage

- All documents and import files in S3-compatible storage behind an `ObjectStore`
  interface (MinIO dev / S3 prod).
- Keys are opaque and org-partitioned: `org/{org_id}/documents/{document_id}/{sha256}`.
  Never derived from user-supplied filenames.
- No public buckets. Access only via **short-TTL signed URLs** minted server-side
  after an authorization check. Upload via signed `PUT` or a server-proxied stream.
- Server-side encryption at rest; TLS in transit everywhere.
- Store `sha256`, `content_type`, `byte_size`; verify on read.

## 4. Secrets & configuration

- No secrets in source or images. `.env` is git-ignored; `.env.example` documents
  keys with placeholder values only.
- Prod secrets in AWS Secrets Manager, injected as env at runtime.
- Separate credentials per environment; least-privilege IAM (S3 prefix scope, RDS
  user scope).
- LLM provider API keys are backend-only, never sent to the browser.

## 5. Prompt injection & untrusted documents

**Every uploaded document is untrusted input. Document text is data, never
instruction.** (See [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) §6.)

- A treaty containing *"ignore all instructions and do X"* is content. It gets zero
  authority to change system instructions, choose/invoke tools, or cause side
  effects.
- Model inputs delimit document text explicitly as data; system `instructions` say
  to ignore and flag embedded directives.
- Agents operate **only** through typed, narrow, read-only application tools. No
  consequential action rests on document content alone — a human decision always
  intervenes before anything leaves Cedeon.
- Production agents have **no** shell, **no** arbitrary web browsing, **no**
  filesystem, **no** write tools. Tool allowlist is explicit per agent.
- Suspected injection is recorded on the `agent_run` and shown to the reviewer.

## 6. Logging, tracing & data handling

- Structured JSON logs + OpenTelemetry traces + a correlation ID per request /
  job / agent run.
- **Never log treaty text, claim data, or PII in ordinary logs.** Log identifiers
  (`document_id`, `treaty_version_id`, `candidate_id`), counts, and status — not
  content.
- AI traces: store request/response envelopes in `agent_runs` (access-controlled,
  org-scoped) — **not** in the general log/trace stream. Minimise sensitive content
  in span attributes; redact by default.
- Error monitoring (e.g. Sentry) configured with PII scrubbing; no document/claim
  bodies in breadcrumbs.
- Data retention: raw uploads and import rows retained for auditability; a documented
  deletion path per organization for offboarding (Phase 10).

## 7. Human accountability

- Every consequential action records an explicit human identity: `reviews.reviewer_id`,
  `treaty_versions.validated_by`, `recovery_notices.approved_by`, plus an
  `audit_events` row with `actor_type='user'`.
- `audit_events` is append-only (DB trigger rejects UPDATE/DELETE).
- Approvals cannot be performed by `actor_type='system'` or `'agent'` — only a user.

## 8. Transport & platform

- HTTPS only; HSTS. Secure cookie flags as in §2.
- FastAPI not publicly exposed in production (single public origin is Next.js;
  see [ADR-0004](DECISIONS.md)).
- Dependency scanning (`uv`/`pip-audit`, `pnpm audit`) and CodeQL/secret-scanning in
  CI. Pinned lockfiles.
- Least-privilege service roles; separate `api` and `worker` task roles.

## 9. Explicitly deferred (not MVP)

SSO / SAML / SCIM · RLS · field-level encryption · customer-managed keys · full DSAR
tooling · pen-test / SOC 2 program · IP allow-listing · anomaly detection. The
architecture leaves room for each; none is built now, and none is claimed.
