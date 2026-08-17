#!/usr/bin/env bash
# Create a USDC-like mint on the local validator and wire it into .env.
#
# Purchases are denominated in USDC, so without a mint the purchase route
# returns 503 ("Campaign escrow is not configured") and nothing downstream can
# be exercised locally. Real USDC only exists on mainnet/devnet, so localnet
# needs its own 6-decimal stand-in.
#
# The validator wipes its ledger on restart, so re-run this after `pnpm dev:up`
# recreates the validator. It rewrites USDC_MINT in .env each time.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"

RPC="${SOLANA_RPC_LOCAL:-http://127.0.0.1:8899}"
DECIMALS=6          # must match USDC_DECIMALS in the Anchor program
SUPPLY="${USDC_SUPPLY:-1000000}"

if ! curl -s -m 5 -X POST "$RPC" -H 'Content-Type: application/json' \
     -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}' >/dev/null 2>&1; then
  echo "No validator at $RPC. Start the stack first: pnpm dev:up" >&2
  exit 1
fi

echo "Using validator at $RPC"
solana config set --url "$RPC" >/dev/null

if [ ! -f "$HOME/.config/solana/id.json" ]; then
  solana-keygen new --no-bip39-passphrase -s -o "$HOME/.config/solana/id.json" >/dev/null
fi

WALLET="$(solana address)"
# Braces are required: a multibyte character straight after $WALLET makes bash
# read the variable name as "WALLET…" and fail under `set -u`.
echo "Funding ${WALLET}…"
solana airdrop 100 >/dev/null 2>&1 || true

BALANCE_SOL="$(solana balance 2>/dev/null | awk '{print $1}')"
if [ "${BALANCE_SOL%%.*}" = "0" ] || [ -z "${BALANCE_SOL:-}" ]; then
  cat >&2 <<'MSG'

The validator accepted the airdrop request but the transaction never landed.

That is the signature of the *containerised* validator: under x86_64 emulation it
serves RPC reads but silently drops submitted transactions, so no purchase,
settlement or mint can ever confirm against it.

Run the validator natively instead — it is the supported path on Apple Silicon:

  1. in .env, clear the profile so compose skips the validator container:
       COMPOSE_PROFILES=
       SOLANA_RPC_URL=http://host.docker.internal:8899
  2. pnpm dev:restart
  3. pnpm chain:validator        # native, separate terminal
  4. re-run this script

MSG
  exit 1
fi
echo "Balance: $(solana balance)"

echo "Creating a ${DECIMALS}-decimal mint…"
MINT="$(spl-token create-token --decimals "$DECIMALS" --output json | sed -n 's/.*"commandOutput".*"address": *"\([^"]*\)".*/\1/p')"
# Older/newer CLI versions shape --output json differently; fall back to plain text.
if [ -z "${MINT:-}" ]; then
  MINT="$(spl-token create-token --decimals "$DECIMALS" | sed -n 's/^Address: *//p' | head -1)"
fi
if [ -z "${MINT:-}" ]; then
  echo "Could not determine the new mint address." >&2
  exit 1
fi

echo "Mint: $MINT"
spl-token create-account "$MINT" >/dev/null
spl-token mint "$MINT" "$SUPPLY" >/dev/null
echo "Minted $SUPPLY to $(spl-token address --token "$MINT" --verbose 2>/dev/null | sed -n 's/^Associated token address: *//p' | head -1)"

# Rewrite USDC_MINT in .env, appending the key if it is absent. awk rather than
# sed so a base58 value containing no special characters stays literal either way.
if grep -q '^USDC_MINT=' .env 2>/dev/null; then
  awk -v m="$MINT" '/^USDC_MINT=/ { print "USDC_MINT=" m; next } { print }' .env > .env.tmp
  mv .env.tmp .env
else
  printf '\n# Local 6-decimal USDC stand-in, created by scripts/setup-localnet-usdc.sh\nUSDC_MINT=%s\n' "$MINT" >> .env
fi

echo
echo "Wrote USDC_MINT=$MINT to .env"
echo "Restart the API so it picks up the new value:  pnpm dev:restart"
