#!/usr/bin/env bash
# Post a fake Helius payload at the local ingest endpoint.
#
# Helius needs a publicly reachable URL, which you will not have on localhost
# without a tunnel. This lets you develop and test the ingest path without one.
# When you do want the real thing, run `cloudflared tunnel --url http://localhost:8010`
# and point the Helius webhook at the resulting hostname.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$ROOT/.env" ] && { set -a; . "$ROOT/.env"; set +a; }

API="${API_URL:-http://localhost:8010}"
SECRET="${HELIUS_WEBHOOK_SECRET:-}"

if [ -z "$SECRET" ]; then
  echo "HELIUS_WEBHOOK_SECRET is not set in .env — the endpoint will reject this." >&2
  echo "Generate one with: openssl rand -hex 32" >&2
  exit 1
fi

# A signature must be unique per call or the ingest will correctly dedupe it.
SIGNATURE="mock$(date +%s)$(head -c4 /dev/urandom | od -An -tx1 | tr -d ' \n')"
COUNTER_PDA="${COUNTER_PDA:-3nJLd6Vi1FvBv5Ndb9zeFrqZnwWvfsTjWEnAgUvA2Fkq}"
AUTHORITY="${AUTHORITY:-7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU}"
COUNT="${COUNT:-1}"

read -r -d '' PAYLOAD <<EOF || true
[{
  "signature": "$SIGNATURE",
  "slot": $(date +%s),
  "timestamp": $(date +%s),
  "transaction": {
    "message": {
      "accountKeys": ["$AUTHORITY", "$COUNTER_PDA", "11111111111111111111111111111111"]
    }
  },
  "meta": {
    "logMessages": [
      "Program ${PROGRAM_ID:-5dzttAFNMi3JNtBcBQzJWcyXwou4rN2z6KX5DitDSDHe} invoke [1]",
      "Program log: Hello, world! Counter is now $COUNT",
      "Program ${PROGRAM_ID:-5dzttAFNMi3JNtBcBQzJWcyXwou4rN2z6KX5DitDSDHe} success"
    ]
  }
}]
EOF

echo "POST $API/webhooks/helius  (signature $SIGNATURE)"
curl -sS -X POST "$API/webhooks/helius" \
  -H "Content-Type: application/json" \
  -H "Authorization: $SECRET" \
  -d "$PAYLOAD"
echo
