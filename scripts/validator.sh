#!/usr/bin/env bash
# Run the local validator natively, with the Anchor program preloaded.
#
# Native rather than containerised on purpose: under x86_64 emulation the
# container serves RPC reads but silently drops every submitted transaction, so
# nothing can confirm against it. See README > Running the validator.
#
# Preloading with --bpf-program matters beyond convenience: it installs the
# program at the address in declare_id! without needing the program keypair. The
# canonical keypair is not in the repo, so `solana program deploy` cannot place
# the program at the committed ID on a fresh machine — preloading can.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"

[ -f .env ] && { set -a; . ./.env; set +a; }

PROGRAM_SO="onchain/target/deploy/sss_core.so"
LEDGER="${VALIDATOR_LEDGER:-.localnet/test-ledger}"

# solana-test-validator will not create intermediate directories.
mkdir -p "$(dirname "$LEDGER")"

ARGS=(--reset --ledger "$LEDGER")

if [ -f "$PROGRAM_SO" ] && [ -n "${PROGRAM_ID:-}" ]; then
  echo "Preloading $PROGRAM_ID from $PROGRAM_SO"
  ARGS+=(--bpf-program "$PROGRAM_ID" "$PROGRAM_SO")
else
  echo "No program to preload (need $PROGRAM_SO and PROGRAM_ID in .env)."
  echo "Run 'pnpm chain:build' first, or instructions will fail with ProgramAccountNotFound."
fi

echo
echo "After the validator is up, seed a local USDC mint:  pnpm chain:usdc"
echo

exec solana-test-validator "${ARGS[@]}"
