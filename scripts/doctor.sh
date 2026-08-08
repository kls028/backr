#!/usr/bin/env bash
# Preflight check for a working dev environment.
# Exits non-zero if something will definitely break, warns if it merely might.
set -uo pipefail

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; WARNINGS=$((WARNINGS + 1)); }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; FAILURES=$((FAILURES + 1)); }

WARNINGS=0
FAILURES=0

echo "toolchain"

for tool in node pnpm docker cargo; do
  if command -v "$tool" >/dev/null 2>&1; then
    ok "$tool $("$tool" --version 2>&1 | head -1)"
  else
    bad "$tool not found"
  fi
done

# --- Solana CLI --------------------------------------------------------------
# Anchor 1.x expects the Agave 2.x+ toolchain. An old solana binary earlier in
# PATH is the single most common cause of confusing build failures here, and it
# is easy to have several installed at once.
if command -v solana >/dev/null 2>&1; then
  SOLANA_VERSION="$(solana --version | awk '{print $2}')"
  SOLANA_MAJOR="${SOLANA_VERSION%%.*}"
  if [ "$SOLANA_MAJOR" -ge 2 ] 2>/dev/null; then
    ok "solana $SOLANA_VERSION ($(command -v solana))"
  else
    bad "solana $SOLANA_VERSION is too old for Anchor 1.x — need Agave 2.x+"
    echo "      active binary: $(command -v solana)"
    if command -v agave-install >/dev/null 2>&1; then
      echo "      you already have: $(agave-install list 2>/dev/null | tr '\n' ' ')"
      echo "      fix by putting the agave bin dir first in PATH:"
      echo "        export PATH=\"\$HOME/.local/share/solana/install/active_release/bin:\$PATH\""
    fi
  fi

  DUPLICATES="$(command -v -a solana 2>/dev/null | sort -u | wc -l | tr -d ' ')"
  if [ "$DUPLICATES" -gt 1 ]; then
    warn "$DUPLICATES solana binaries on PATH — the first one wins:"
    command -v -a solana | sort -u | sed 's/^/      /'
  fi
else
  bad "solana not found"
fi

if command -v anchor >/dev/null 2>&1; then
  ok "anchor $(anchor --version | awk '{print $2}')"
else
  bad "anchor not found — install via avm"
fi

if command -v supabase >/dev/null 2>&1; then
  ok "supabase $(supabase --version)"
else
  bad "supabase CLI not found"
fi

echo
echo "environment"

if [ -f .env ]; then
  ok ".env present"
  # shellcheck disable=SC1091
  set -a; . ./.env; set +a
  [ -n "${VITE_SUPABASE_ANON_KEY:-}" ] || warn "VITE_SUPABASE_ANON_KEY is empty — run 'supabase start' and copy the anon key"
  [ -n "${HELIUS_WEBHOOK_SECRET:-}" ] || warn "HELIUS_WEBHOOK_SECRET is empty — the webhook route will refuse all requests"
else
  bad ".env missing — cp .env.example .env"
fi

echo
echo "ports"

# This project deliberately runs Supabase on 5442x. Check nothing else took them.
for port in 54421 54422 54423 8010 5273; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    OWNER="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -F c 2>/dev/null | grep '^c' | head -1 | cut -c2-)"
    warn "port $port already in use (${OWNER:-unknown})"
  else
    ok "port $port free"
  fi
done

echo
if [ "$FAILURES" -gt 0 ]; then
  printf '\033[31m%d failure(s)\033[0m, %d warning(s)\n' "$FAILURES" "$WARNINGS"
  exit 1
fi
printf '\033[32mready\033[0m — %d warning(s)\n' "$WARNINGS"
