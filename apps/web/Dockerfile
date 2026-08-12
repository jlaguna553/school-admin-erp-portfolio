# syntax=docker/dockerfile:1
#
# Build context is the **repository root**, not apps/web -- the pnpm workspace
# needs the root manifests and packages/api-types to resolve @erp/api-types.

# ---------------------------------------------------------------------------
# Base: node + pnpm via corepack.
# ---------------------------------------------------------------------------
FROM node:20-alpine AS base

ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH \
    NEXT_TELEMETRY_DISABLED=1

RUN corepack enable

WORKDIR /repo

# ---------------------------------------------------------------------------
# Dependencies: only the manifests, so a source edit does not reinstall.
# ---------------------------------------------------------------------------
FROM base AS deps

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
COPY packages/api-types/package.json packages/api-types/

# --frozen-lockfile makes the lockfile authoritative: the build fails rather
# than silently resolving different versions than local development uses.
RUN pnpm install --frozen-lockfile

# ---------------------------------------------------------------------------
# Development: hot reload. Source arrives via a compose bind mount.
# ---------------------------------------------------------------------------
FROM deps AS dev

COPY . .

EXPOSE 3000
WORKDIR /repo/apps/web
CMD ["pnpm", "dev"]

# ---------------------------------------------------------------------------
# Builder: produce the standalone production bundle.
# ---------------------------------------------------------------------------
FROM deps AS builder

COPY . .

# NEXT_PUBLIC_* values are inlined into the client bundle at build time. Only
# the API's port is needed: the hostname is read from window.location at runtime,
# so a single build serves every school from its own host.
ARG NEXT_PUBLIC_API_PORT=8000
ENV NEXT_PUBLIC_API_PORT=$NEXT_PUBLIC_API_PORT

# Where /api is proxied. This has to be present at *build* time: Next evaluates
# `rewrites()` during the build and bakes the result into the route manifest, so
# setting it only at runtime silently produces an image with no proxy.
ARG API_PROXY_TARGET=""
ENV API_PROXY_TARGET=$API_PROXY_TARGET

ENV NEXT_OUTPUT=standalone

WORKDIR /repo/apps/web
RUN pnpm build

# ---------------------------------------------------------------------------
# Runner: minimal image containing only the standalone output.
# ---------------------------------------------------------------------------
FROM node:20-alpine AS prod

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

WORKDIR /app

# `output: standalone` emits a self-contained tree with a pruned node_modules
# and its own server.js, so pnpm is not needed in the runtime image.
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/public ./apps/web/public

USER nextjs
EXPOSE 3000

CMD ["node", "apps/web/server.js"]
