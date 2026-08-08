#!/usr/bin/env bash
# Start the test validator, preloading the Anchor program when one has been
# built. Preloading at genesis means `anchor deploy` is not needed for the
# common case — the program is simply there when the validator comes up.
set -euo pipefail

PROGRAM_SO="/programs/sss_core.so"
LEDGER="/ledger/test-ledger"

# Agave 3.x's gossip layer refuses an unspecified address: passing 0.0.0.0 dies
# with `UnspecifiedIpAddr(0.0.0.0)` before the RPC ever comes up. It wants a
# concrete IP, so resolve the container's own address on the compose network.
# Docker forwards published ports to exactly this interface, so the RPC is
# reachable from the host and from sibling containers.
BIND_ADDR="$(hostname -i | awk '{print $1}')"
echo "Binding validator to $BIND_ADDR"

# solana-test-validator has no --rpc-bind-address; that flag belongs to the
# full validator. --bind-address covers the RPC too.
ARGS=(
  --ledger "$LEDGER"
  --bind-address "$BIND_ADDR"
  --rpc-port 8899
  --limit-ledger-size 50000000
)

# --reset wipes the ledger on every boot. That is what you want in development:
# a preloaded program can only be swapped at genesis, so without it a rebuilt
# program would never take effect.
if [ "${VALIDATOR_RESET:-true}" = "true" ]; then
  ARGS+=(--reset)
fi

if [ -f "$PROGRAM_SO" ] && [ -n "${PROGRAM_ID:-}" ]; then
  echo "Preloading program $PROGRAM_ID from $PROGRAM_SO"
  ARGS+=(--bpf-program "$PROGRAM_ID" "$PROGRAM_SO")
else
  echo "No program to preload (looked for $PROGRAM_SO, PROGRAM_ID='${PROGRAM_ID:-unset}')."
  echo "Run 'pnpm chain:build' then restart, or deploy manually with 'pnpm chain:deploy'."
fi

exec solana-test-validator "${ARGS[@]}"
