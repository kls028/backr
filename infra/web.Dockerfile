# syntax=docker/dockerfile:1.7

# Vite dev server. Development only — this is not how you ship the frontend.
# For production build the SPA (`pnpm --filter web build`) and serve dist/ from
# a CDN or static host; there is no Node runtime in production.
FROM node:22-slim

RUN corepack enable

# Dependencies install into named volumes at runtime rather than being baked in,
# so the bind-mounted source and the installed tree stay consistent when you
# add a package without rebuilding the image.
WORKDIR /workspace

EXPOSE 5273

# --host 0.0.0.0 overrides the `host: 'localhost'` in vite.config.ts, which is
# correct for a container: Vite must listen on all interfaces for the published
# port to reach it. This does NOT change how you open the app — still use
# http://localhost:5273, because SIWS rejects a bare IP as its domain.
#
# --store-dir keeps pnpm's content-addressable store on a named volume. Without
# it pnpm puts the store next to node_modules, and because node_modules here is
# a volume on a different filesystem from the bind-mounted source, it lands in
# /workspace — i.e. a 380 MB .pnpm-store directory inside your git repo.
CMD ["sh", "-c", "pnpm install --frozen-lockfile --store-dir /pnpm-store && pnpm --filter web dev --host 0.0.0.0"]
