/**
 * The server-side origin the Next.js `/api/*` proxy (and server components)
 * forward to (ADR-0004 — the browser never talks to it directly).
 *
 * Accepts a scheme-less value like Render's `host:port` and assumes http:// on
 * the private network.
 */
export function apiInternalUrl(): string {
  const raw = process.env.CEDEON_API_INTERNAL_URL ?? "http://localhost:8000";
  return /^https?:\/\//.test(raw) ? raw : `http://${raw}`;
}
