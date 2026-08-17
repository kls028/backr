# Backr

A Solana web3 service. Anchor program on-chain, Supabase Postgres off-chain,
FastAPI between them, React + shadcn on the front.

Product requirements, design, and the four-part implementation handoff are in
[`docs/backr-prd-and-design.md`](docs/backr-prd-and-design.md) and
[`docs/backr-implementation-plan.md`](docs/backr-implementation-plan.md).

Part 1 repository flow is implemented across the athlete profile, subscription
plan, campaign draft/review, unsigned publication, and public campaign routes.
The browser records a submitted publication as pending; only verified indexer
data changes the campaign to `scheduled` or `active`.

```
apps/web        React SPA (Vite, shadcn)
services/api    FastAPI — tx building, Helius ingest, read APIs
  app/indexer   reconciliation worker
onchain         Anchor workspace
supabase        migrations + config (authoritative for schema)
infra           docker-compose
```

## Prerequisites

| Tool | Notes |
| --- | --- |
| Node 20+ and pnpm | `corepack enable` |
| Docker Desktop | must be running |
| Rust + Anchor 1.x | via `avm` |
| Agave CLI 2.x+ | `solana --version` must report 2.x or newer |
| Supabase CLI | `brew install supabase/tap/supabase` |

`uv` is optional — only needed to run the Python tests/linters outside Docker.

## Setup (one-time)

```bash
pnpm install
pnpm chain:build     # compile the program so the validator can preload it
```

## Running

```bash
pnpm chain:validator   # terminal 1 — local validator, runs natively
pnpm dev:up            # terminal 2 — Supabase, api, worker, web
pnpm chain:usdc        # once the validator is up: seed a local USDC mint
```

> **The validator runs natively, not in Docker.** Under x86_64 emulation on
> Apple Silicon the containerised validator serves RPC reads but silently drops
> every submitted transaction, so no purchase or settlement can confirm. The
> compose service still exists for x86_64 Linux hosts — enable it by setting
> `COMPOSE_PROFILES=chain` and pointing `SOLANA_RPC_URL` at `validator:8899`.

Re-run `pnpm chain:usdc` after each validator restart: the ledger is wiped on
boot, so the previous mint disappears and purchases start returning 503.

Then open **http://localhost:5273** — use `localhost`, not `127.0.0.1`, or
wallet sign-in fails.

| Command | What it does |
| --- | --- |
| `pnpm dev:up` | start the whole stack (~50s cold) |
| `pnpm dev:down` | stop everything |
| `pnpm dev:restart` | stop + start |
| `pnpm dev:logs` | follow logs from all containers |
| `pnpm dev:ps` | what's running |
| `pnpm doctor` | toolchain / env / port preflight |

Scripts are namespaced `dev:*` because `pnpm up` is a built-in alias for
`pnpm update` and would shadow a script named `up`.

## URLs

| | |
| --- | --- |
| App | http://localhost:5273 |
| API docs | http://localhost:8010/docs |
| Health checks | http://localhost:8010/diagnostics |
| Supabase Studio | http://127.0.0.1:54423 |
| Solana RPC | http://localhost:8899 |

## Part 1 workflow

1. Connect a wallet and complete `/athlete/setup`.
2. Create and publish a plan at `/athlete/plan`.
3. Create or resume a campaign at `/athlete/campaigns/new`.
4. Review and publish it at `/athlete/campaigns/:campaign_id/review`.
5. Browse confirmed campaigns at `/campaigns` and inspect a campaign at
   `/campaigns/:campaign_id`.

Publication requires the configured Supabase auth/database, USDC mint, Solana
RPC/indexer, deployed program, and a wallet signature. The API builds only
unsigned transactions and does not require or accept a private key.

## Common tasks

```bash
# after changing the Rust program — restart is required, the validator
# preloads the program at genesis
pnpm chain:build && pnpm dev:restart && pnpm idl:sync

# database schema (supabase/migrations is the only source of truth)
pnpm db:diff -f describe_your_change
pnpm db:reset

# tests
pnpm typecheck
cd services/api && uv run pytest
cd onchain && anchor build && cargo test
```

## When something breaks

```bash
curl -s localhost:8010/diagnostics | jq
```
