#!/usr/bin/env bash
# Stop everything this project started, and nothing else.
#
# Deliberately scoped: `docker compose down` only touches services in this
# project's compose file, and `supabase stop` only this project's Supabase
# stack. Other projects' containers on this machine are left alone.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Stopping validator, api, worker and web…"
docker compose --env-file .env -f infra/docker-compose.yml down

echo "Stopping Supabase…"
supabase stop

echo
echo "All stopped. Database contents are kept in a docker volume;"
echo "'supabase db reset' replays migrations from scratch when you want a clean slate."
