#!/usr/bin/env bash
# Bring the whole stack up with one command.
#
# Supabase is started through its own CLI (it manages ten containers and owns
# migrations); everything else comes from infra/docker-compose.yml. The two are
# sequenced here so you never have to think about the ordering, and the anon key
# Supabase mints on first boot is copied into .env automatically -- that manual
# copy/paste step was the most common way to end up with a half-working app.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose --env-file .env -f infra/docker-compose.yml)

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
dim()  { printf '\033[2m%s\033[0m\n' "$1"; }

# --- .env ------------------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  dim "Created .env from .env.example"
fi

# --- Supabase --------------------------------------------------------------
bold "Starting Supabase…"
if supabase status >/dev/null 2>&1; then
  dim "already running"
else
  supabase start >/dev/null
fi

# --- Wire the anon key -----------------------------------------------------
# Supabase mints these per project on first boot, so they cannot live in
# .env.example. Read them back and patch .env if it is still blank.
ANON_KEY="$(supabase status -o json 2>/dev/null | sed -n 's/.*"ANON_KEY" *: *"\([^"]*\)".*/\1/p' | head -1)"

if [ -n "$ANON_KEY" ]; then
  CURRENT="$(sed -n 's/^VITE_SUPABASE_ANON_KEY=//p' .env | head -1)"
  if [ "$CURRENT" != "$ANON_KEY" ]; then
    # A literal & or | in the key would break sed's replacement, so build the
    # file with awk instead of trying to escape it.
    awk -v key="$ANON_KEY" '
      /^VITE_SUPABASE_ANON_KEY=/ { print "VITE_SUPABASE_ANON_KEY=" key; next }
      { print }
    ' .env > .env.tmp && mv .env.tmp .env
    dim "Wrote VITE_SUPABASE_ANON_KEY into .env"
  fi
else
  dim "Could not read ANON_KEY from supabase status — set it in .env by hand"
fi

# --- Warn about an unbuilt program -----------------------------------------
if [ ! -f onchain/target/deploy/sss_core.so ]; then
  printf '\033[33m!\033[0m %s\n' "onchain/target/deploy/sss_core.so is missing — the validator will start"
  printf '  %s\n' "without a program. Run 'pnpm chain:build' then 'pnpm dev:restart' to preload it."
fi

# --- Everything else -------------------------------------------------------
bold "Starting validator, api, worker and web…"
"${COMPOSE[@]}" up -d --build

echo
"${COMPOSE[@]}" ps --format 'table {{.Name}}\t{{.Status}}'

cat <<'EOF'

  App        http://localhost:5273     <- open this one, not 127.0.0.1
  API docs   http://localhost:8010/docs
  Health     http://localhost:8010/diagnostics
  Studio     http://127.0.0.1:54423
  RPC        http://localhost:8899

  pnpm dev:logs  follow logs     pnpm dev:down  stop everything

EOF
