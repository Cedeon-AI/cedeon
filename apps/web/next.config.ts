import type { NextConfig } from "next";

// Single public origin (ADR-0004): the browser only ever talks to Next.js.
// `/api/*` is proxied to FastAPI at runtime by src/app/api/[...path]/route.ts
// (a build-time rewrite cannot read per-deploy env).
const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  outputFileTracingRoot: `${import.meta.dirname}/../..`,
};

export default nextConfig;
