# Backr four-part implementation plan

This plan is ordered so each part leaves a deployable and testable boundary.
The parts can be worked on by separate owners after the shared interfaces are
merged, but the dependency order remains important.

## Part 1: identity, athlete profile, plans, campaigns, publication

### Deliverables

- Supabase migration for roles, athlete profiles, plans, campaigns, goals,
  reward tiers, and publication intents.
- SQLAlchemy mirrors and ownership queries.
- Exact USDC parser/formatter and campaign validation module.
- Profile and athlete activation routes.
- Plan CRUD and publication routes.
- Campaign draft/list/detail/update/cancel routes.
- Canonical snapshot and SHA-256 hash.
- Anchor `initialize_campaign` state and instruction.
- Python PDA and Borsh instruction builder.
- Web campaign directory, detail page, athlete authoring workspace, and
  wallet-confirmed publication flow.

### Implementation sequence

1. Apply migration and mirror every column/index/constraint in
   `services/api/app/platform_models.py`.
2. Write red tests for amount precision, date/goal invariants, snapshot
   stability, ownership, and publication payload encoding.
3. Implement domain validators and schemas.
4. Implement profile, plan, and campaign routes with database ownership checks.
5. Implement publication intent creation and confirmation. Store the exact
   unsigned transaction, blockhash, simulation logs, nonce, and snapshot hash.
6. Implement Anchor campaign state and initialization instruction.
7. Implement web authoring, review, and publication flow.
8. Apply migration to a disposable local database and run API, web, and chain
   tests.

### Part 1 acceptance tests

- invalid decimal precision returns 422;
- a published plan cannot be edited;
- a campaign with a decreasing stretch goal is rejected;
- a campaign owned by another athlete returns 404/403;
- repeated athlete activation returns the same profile;
- repeated publication returns the existing intent;
- the snapshot hash changes if any financial term changes;
- the publish transaction is unsigned until the browser signs it;
- public listing excludes drafts and cancelled campaigns.

## Part 2: purchase, escrow, settlement, Support Points

### Deliverables

- Anchor purchase instruction with checked SPL-token transfer.
- Campaign supporter position PDA.
- Settlement instruction family for success/failure.
- Python purchase instruction builder and transaction preparation route.
- Pure purchase allocation and settlement rules.
- Contributions, subscriptions, Support Point accounts, and ledger projections.
- Anchor event decoder for initialization and purchase events.
- Idempotent contribution projection keyed by signature.
- Web purchase page, wallet signing, confirmation, and points view.

### Implementation sequence

1. Write red tests for first-unit immediate allocation, additional pending
   allocation, active-unit limits, success promotion, failure refund, bonus
   rounding, and vesting remainder handling.
2. Implement the pure domain functions in
   `services/api/app/domain/settlement.py`.
3. Implement Anchor state, position PDA, checked transfer CPI, and events.
4. Implement the Python builder and purchase preparation route. Require mint,
   PDA, token-account, and wallet validation before simulation.
5. Extend the indexer parser with event discriminators and raw-event rows.
6. Project a purchase in one DB transaction: contribution, subscription,
   point balances, point ledger, and campaign raised amount.
7. Add creator settlement intent and on-chain success/failure instructions.
8. Add settlement projector: promote/refund pending balances exactly once.
9. Add web purchase and confirmation states.

### Part 2 acceptance tests

- purchased units and atomic amount match on-chain event fields;
- source and escrow token accounts are never accepted from an unvalidated
  malformed address;
- a missing USDC mint prevents transaction creation;
- one purchase with three units records one immediate and two pending;
- replaying a signature changes no balance or ledger count;
- success awards the configured bonus once;
- failure refunds pending units and removes pending points only;
- the browser never sends a private key to the API.

## Part 3: rewards, store, and fulfillment

### Deliverables

- Tier eligibility engine with cumulative/non-cumulative behavior.
- Entitlement projector and fulfillment state machine.
- Platform cosmetic catalog and redemption transaction.
- Athlete reward offer authoring.
- Athlete reward order reservation and fulfillment workflow.
- Inventory/per-user locking and unique source keys.
- Store and Support Points web views.

### Implementation sequence

1. Write red tests for cumulative eligibility, highest non-cumulative tier,
   inventory exhaustion, per-user limits, insufficient points, and duplicate
   redemption.
2. Implement pure reward and point reservation functions.
3. Add fulfillment tables, RLS, and SQLAlchemy mirrors.
4. Implement catalog/read routes and locked redemption transactions.
5. Implement entitlement generation on successful settlement.
6. Implement athlete offer routes and protected fulfillment transitions.
7. Add store UI with available/pending point context and explicit redemption
   result states.
8. Add operator retry and audit fields before staging rollout.

### Part 3 acceptance tests

- pending units cannot unlock tiers;
- cumulative tiers unlock as a set;
- a non-cumulative group exposes only the highest tier;
- two concurrent redemptions cannot oversell inventory;
- a duplicate cosmetic redemption does not spend points twice;
- reward orders do not modify campaign raised amount;
- fulfillment details are not visible to unrelated users;
- every spend has a negative point ledger entry and source key.

## Part 4: payouts, vesting, indexing, operations, launch

### Deliverables

- Payout fee and vesting calculations.
- Payout vesting entries and release worker.
- Campaign success/failure lifecycle worker.
- Raw transaction retention and reconciliation cursor.
- Webhook and RPC event processing with retry state.
- Diagnostics for database, RPC, indexer, and payout dependencies.
- Launch runbook, alerts, and rollback/replay procedure.

### Implementation sequence

1. Write red tests for fee basis points, exact vesting totals, monthly date
   boundaries, duplicate release, and failed-release retry.
2. Implement payout calculations and persisted vesting rows.
3. Add lifecycle detection for ended campaigns and settlement intents.
4. Add worker locks, bounded retries, and confirmed transaction recording.
5. Add raw event retention and reconciliation from cursor.
6. Add metrics, structured logs, and diagnostic checks.
7. Run a local failure drill: drop webhook, replay RPC, fail simulation, retry
   payout, and confirm no duplicate points or transfers.
8. Deploy to staging with a non-production mint and verify all acceptance
   criteria before production configuration.

### Part 4 acceptance tests

- all payout components sum exactly to the source atomic amount;
- a due vesting entry is claimed by only one worker;
- a failed payout remains retryable and is not marked released;
- webhook and reconciliation produce identical projection rows;
- malformed events remain in raw storage with an actionable error;
- readiness is not green when RPC, database, or required secrets are absent;
- production logs contain no private keys, JWTs, or full PII payloads.

## Shared file map

### Backend

- `services/api/app/domain/`: pure financial, campaign, reward, and payout
  rules;
- `services/api/app/schemas/`: request and response contracts;
- `services/api/app/routers/`: authenticated workflow and read routes;
- `services/api/app/indexer/`: raw ingest, event decode, projection, and
  reconciliation;
- `services/api/app/solana/`: PDA and unsigned transaction builders;
- `services/api/app/platform_models.py`: database mirror;
- `services/api/tests/`: unit and contract tests.

### Chain

- `onchain/programs/sss_core/src/state.rs`: authoritative accounts;
- `onchain/programs/sss_core/src/instructions/`: instruction contexts and
  handlers;
- `onchain/programs/sss_core/src/error.rs`: explicit program errors;
- `packages/idl/`: generated client types after chain build.

### Frontend

- `apps/web/src/routes/`: directory, campaign, athlete, points, and store
  surfaces;
- `apps/web/src/lib/api.ts`: typed API boundary;
- `apps/web/src/lib/solana.ts`: deserialize/sign/submit/confirm only;
- `apps/web/src/providers/`: wallet and SIWS session providers.

## Verification matrix

| Layer | Command | Required result |
| --- | --- | --- |
| API unit | `uv run pytest` | all tests pass |
| API lint | `uv run ruff check services/api/app services/api/tests` | no errors |
| API types | `uv run mypy services/api/app` | no errors |
| Web types | `pnpm --filter web exec tsc -b` | no errors |
| Web build | `pnpm --filter web build` | Vite production bundle |
| Chain | `anchor build` | program and IDL build |
| Chain tests | `cargo test` | unit/integration tests pass |
| Database | `supabase db reset` | migrations apply cleanly |
| Browser | Playwright affected flows | no console/network errors |
| Security | secret/config audit | no secrets or insecure fallback |

## Delivery order and dependencies

```text
Part 1 identity/config
        |
        v
Part 2 purchase/settlement/points
        |
        +--------------+
        v              v
Part 3 rewards     Part 4 payouts/indexer operations
        \              /
         \            /
          v          v
             staging launch
```

The shared contract is the immutable campaign snapshot, PDA derivation,
integer amount representation, event discriminator, and source-key strategy.
Changes to those contracts require coordinated updates to Anchor, Python, SQL,
the frontend, and tests.
