# Cedeon web (Next.js, standalone output). Mirrors the monorepo layout so the
# standalone server path is stable: /repo/apps/web/.next/standalone/apps/web/server.js
FROM node:22-slim AS base
ENV PNPM_HOME=/pnpm PATH="/pnpm:$PATH" NEXT_TELEMETRY_DISABLED=1
RUN corepack enable

FROM base AS deps
WORKDIR /repo/apps/web
COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile

FROM base AS build
WORKDIR /repo/apps/web
COPY --from=deps /repo/apps/web/node_modules ./node_modules
COPY packages/openapi /repo/packages/openapi
COPY apps/web/ ./
RUN pnpm gen:client && pnpm build

FROM base AS run
WORKDIR /repo
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
RUN useradd -m nextjs
COPY --from=build --chown=nextjs:nextjs /repo/apps/web/.next/standalone ./
COPY --from=build --chown=nextjs:nextjs /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=nextjs:nextjs /repo/apps/web/public ./apps/web/public
USER nextjs
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
