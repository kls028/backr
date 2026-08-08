# sss-project

Solana service. Anchor program on-chain, Supabase Postgres off-chain, FastAPI
between them, React SPA on top. Read `README.md` for the architecture diagram
and setup steps.

## Non-negotiables

These are the invariants the design rests on. Breaking one is a design change,
not a refactor — raise it before doing it.

1. **The program owns truth.** Postgres is a derived read model. Never make a
   balance, ownership or permission decision from a database row. Every row must
   be reconstructible by replaying the chain.
2. **The backend never holds a user key.** `services/api` builds *unsigned*
   transactions; the wallet signs in the browser. Do not add a code path that
   signs on behalf of a user.
3. **Every ingest write is idempotent.** Webhook delivery is at-least-once and
   the reconciliation worker replays deliberately. New projection tables need a
   natural unique key and `ON CONFLICT DO NOTHING`.
4. **`supabase/migrations` is the only schema authority.** `app/models.py`
   mirrors it by hand. Do not introduce Alembic.
5. **Auth fails closed.** The webhook route 503s when its secret is unset rather
   than accepting anonymous writes. Keep that shape for anything new.

## Environment quirks on this machine

* **Every port is shifted off its default**, because other projects here already
  hold them: `benched`'s Supabase stack owns 54321–54327, the
  `playerscout-backend-dev` container owns 8000, another dev server owns 5173.
  So: Supabase 54421–54429, FastAPI on host 8010 (still 8000 inside the
  container), Vite 5273. Defined in `supabase/config.toml`,
  `infra/docker-compose.yml`, `apps/web/vite.config.ts`, `app/config.py` and
  `.env.example` — change them together.
* **Multiple `solana` binaries are on PATH.** `/Users/kls028/solana-suite/bin/solana`
  is v1.18.26 and shadows the Agave 3.1.5 install that Anchor 1.x needs. Fix by
  putting the agave bin dir first:
  ```
  export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
  ```
  `pnpm doctor` checks for this.
* `uv` is not installed globally. CI uses `astral-sh/setup-uv`; install it
  locally with `curl -LsSf https://astral.sh/uv/install.sh | sh`.
* **The containerised validator is pinned to Agave 2.3.13, not 3.x.** Anza ships
  no arm64 Linux binaries, so it runs under x86_64 emulation, and Agave 3.x
  asserts `io_uring_supported()` at startup — unavailable under emulation, so it
  panics before the RPC comes up. Do not bump it without testing.
  Related: `solana-test-validator` rejects `--bind-address 0.0.0.0` in Agave 3.x
  (`UnspecifiedIpAddr`), so the entrypoint resolves the container IP instead.

## Commands

```bash
pnpm dev:up          # Supabase + validator + api + worker + web. One command.
pnpm dev:logs        # follow logs
pnpm dev:down        # stop everything
pnpm dev:restart     # required after `pnpm chain:build` — see below
pnpm doctor          # toolchain / env / port preflight
pnpm chain:build && pnpm idl:sync
pnpm webhook:mock    # exercise ingest without a public tunnel
```

Scripts are namespaced `dev:*` because **`pnpm up` is a built-in alias for
`pnpm update`** and silently shadows a script named `up`. Do not rename them.

The validator preloads the program at genesis (`--bpf-program`), so there is no
deploy step — but genesis is fixed at boot, so a rebuilt program needs
`pnpm dev:restart` to take effect.

Checks, all of which CI runs:

```bash
pnpm --filter web exec tsc -b
cd services/api && uv run ruff check . && uv run mypy app && uv run pytest
cd onchain && anchor build && cargo clippy --all-targets -- -D warnings && cargo test
```

`anchor build` must come first: the litesvm tests `include_bytes!` the compiled
`.so`, so both `cargo test` and `cargo clippy --all-targets` fail without it.

## Conventions

* **Python** — 3.12, `from __future__ import annotations` everywhere, ruff
  (100 cols) and mypy strict. Async all the way down; no sync DB calls.
* **TypeScript** — the Vite template sets `erasableSyntaxOnly`, so constructor
  parameter properties and enums are unavailable. Declare fields explicitly.
  Import via the `@/` alias.
* **Rust** — pinned to 1.89.0 by `onchain/rust-toolchain.toml`. Program tests
  run on litesvm, so they need no validator — but they do need `anchor build`
  to have produced `target/deploy/sss_core.so`.
* Account order in a Python instruction builder must match the Anchor
  `#[derive(Accounts)]` struct exactly — Anchor resolves positionally, and a
  mismatch surfaces as an opaque constraint error.

## Supabase Web3 auth — verified facts

Confirmed by performing a real Sign-In-With-Solana against local GoTrue:

* The wallet address is at **`user_metadata.custom_claims.address`**. Read by
  `public.current_wallet()`, the `handle_new_user` trigger, and
  `_extract_wallet()` in `app/auth.py`. Keep those three in sync.
* `user_metadata.sub` is `web3:solana:<address>` — prefixed, not a bare address.
  Storing it violates the base58 CHECK on `profiles.wallet`. `test_auth.py`
  guards against this regression.
* **Use `http://localhost:5273`, never `127.0.0.1`.** GoTrue rejects a bare IP as
  the SIWS domain, and supabase-js takes that domain from `window.location`.
  Vite sets `host: 'localhost'` deliberately — do not "fix" it to `0.0.0.0`
  without also adding a hostname.
* The SIWS signature is **base64**, unlike every other Solana signature.
* **`additional_redirect_urls` must contain `/**` globs.** The message URI is the
  full `window.location.href`, and GoTrue demands an exact match against the
  allowed list — `/status` and even a trailing slash are rejected with
  `"message was signed for another app"`. Any new environment needs its own
  globs added, or auth breaks on first deploy.
* **One button, not two.** `WalletAuthButton` owns the whole flow; `AuthProvider`
  auto-prompts for the signature once per pubkey after connect (guarded by a
  ref), and stops prompting if the user rejects. Do not reintroduce a separate
  `WalletMultiButton` — connect-then-sign is one intent.
