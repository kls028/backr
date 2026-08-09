# Backr product requirements and system design

Status: implementation handoff

Backr is an athlete-support platform built around recurring USDC campaign
subscriptions. Athletes publish a campaign with a funding threshold and reward
tiers. Supporters purchase subscription units from a wallet. The chain owns
token movement, campaign progress, and settlement; the API owns authenticated
workflow orchestration and a replayable read model; the web app presents the
campaign, wallet, points, and fulfillment experiences.

This document is split into four delivery parts. Each part has a usable
boundary, explicit dependencies, and acceptance criteria.

## Product principles

1. The Anchor program is authoritative for value-bearing state.
2. The backend never holds or signs for a user wallet.
3. A wallet signs an unsigned transaction assembled and simulated by the API.
4. Every chain projection is idempotent and replayable from raw transactions.
5. Amounts are integers in USDC atomic units at every persistence and chain
   boundary. Decimal strings are used only at user-facing API boundaries.
6. Pending value is visible, but never spendable or represented as settled.
7. Configuration is immutable after publication unless an explicit versioned
   migration is introduced.
8. Rewards and fulfillment are separate from campaign funding and may not
   change the campaign's financial truth.

## Source requirements and decisions

The supplied on-chain architecture describes these required behaviors:

- athlete wallet profiles and campaign configuration;
- a monthly USDC subscription unit;
- minimum success threshold, main goal, stretch goals, and individual reward
  tiers;
- one immediately activated unit per supporter for a campaign, with additional
  purchased units pending in escrow;
- 100 Support Points per subscription unit, separated into pending and
  confirmed balances;
- success releases pending units, unlocks rewards, and awards a success bonus;
- failure refunds pending units while retaining the immediate unit;
- non-transferable Support Points with a platform cosmetic store and athlete
  reward store;
- off-chain metadata with on-chain hashes and core terms;
- indexed off-chain projections reconstructed from chain events;
- standard monthly vesting and immediate campaign settlement paths.

Product decisions made to make those requirements implementable:

- USDC uses six decimals and rejects values with more than six decimal places.
- Campaign configuration is versioned by a canonical JSON snapshot and SHA-256
  hash before publication.
- The default success bonus is configuration-driven and represented in basis
  points, with a default of 2,000 bps.
- A default active subscription limit of twelve units/month is configuration,
  not a frontend assumption.
- Reward inventory, maximum per supporter, fulfillment type, and metadata are
  recorded before redemption.
- A campaign may be scheduled, active, funded, successful, unsuccessful, or
  cancelled. Drafts exist only in the off-chain authoring workflow.

## Roles and permissions

### Supporter

- connect a Solana wallet and complete SIWS authentication;
- browse published campaigns;
- build, sign, and submit a purchase transaction;
- see immediate and pending units;
- see available and pending Support Points;
- redeem a platform cosmetic or an eligible athlete reward;
- see reward and fulfillment status.

### Athlete

- activate an athlete profile;
- create and publish one subscription plan at a time;
- create a campaign draft;
- add goals and reward tiers;
- review the immutable snapshot and publish it on-chain;
- create athlete reward offers;
- view campaign funding and payout vesting status;
- update fulfillment state for athlete rewards.

### Operator

- run indexer reconciliation;
- inspect webhook, RPC, database, and projection health;
- retry failed fulfillment workflows;
- mark operational failures without changing chain-derived truth;
- never edit a chain-derived balance directly.

## Part 1: identity, athlete profile, plan, and campaign publication

### User story

As an athlete, I can turn my wallet into a public profile, define a monthly
subscription plan, create a campaign, review its funding terms and rewards,
and publish an immutable version on-chain.

### Functional requirements

- SIWS authentication creates or resolves a profile and a supporter role.
- An athlete profile has display name, sport, bio, and optional avatar URI.
- Athlete activation is idempotent and cannot create duplicate profiles.
- A plan has a positive six-decimal USDC unit price and benefits text.
- Only one draft or published plan may be open for an athlete.
- Campaigns reference a published plan and copy its unit price at creation.
- Campaign configuration validates:
  - start and end timestamps contain a timezone;
  - end is after start;
  - threshold is positive;
  - main goal, when present, is at least the threshold;
  - stretch goals are strictly increasing and bounded;
  - reward tiers are unique by required units and bounded;
  - inventory limits are positive and internally consistent.
- Publication creates a canonical snapshot, hash, nonce, campaign PDA, and
  unsigned `initialize_campaign` transaction.
- The API simulates the transaction before returning it.
- The browser signs and submits the transaction, then confirms the signature.
- The confirmed campaign is visible to public readers; the draft is not.
- A published campaign is immutable. A correction requires a new campaign or a
  future explicit versioning feature.

### UX states

1. Signed out: campaign directory is public; authoring and purchase actions
   request wallet authentication.
2. Profile setup: display name and optional athlete details are editable.
3. Plan draft: price and benefits are editable until published.
4. Campaign draft: title, description, dates, goals, tiers, and metadata are
   editable until publication intent is created.
5. Review: show exact USDC values, UTC-equivalent dates, goals, tiers, metadata
   URI, and snapshot hash.
6. Wallet signing: show pending state and preserve form data.
7. Simulation failure: show API error and simulation logs; do not open the
   wallet popup.
8. Confirmation pending: show signature and block confirmation state.
9. Published: show campaign PDA and immutable terms.

### Part 1 API

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/profiles/me` | signed-in profile |
| POST | `/profiles/me/athlete` | idempotent athlete activation |
| GET | `/profiles/me/roles` | identity capabilities |
| GET | `/subscription-plans/me` | current athlete plan |
| POST | `/subscription-plans` | create draft plan |
| PATCH | `/subscription-plans/{id}` | edit draft plan |
| POST | `/subscription-plans/{id}/publish` | publish plan |
| GET | `/campaigns` | public campaign directory |
| GET | `/campaigns/{id}` | public campaign detail |
| GET | `/athlete/campaigns` | athlete-owned campaigns |
| POST | `/athlete/campaigns` | create draft |
| PATCH | `/athlete/campaigns/{id}` | edit draft |
| POST | `/athlete/campaigns/{id}/publish` | build and simulate chain tx |
| POST | `/athlete/campaigns/{id}/publish/confirm` | confirm user signature |

### Part 1 data model

- `profiles`: wallet identity from the existing auth migration.
- `profile_roles`: supporter and athlete capabilities.
- `athlete_profiles`: public athlete details.
- `subscription_plans`: price, benefits, and publication state.
- `campaigns`: copied terms, lifecycle, PDA, snapshot hash, and raised total.
- `campaign_stretch_goals`: ordered amount/benefit rows.
- `campaign_reward_tiers`: ordered unlock rules and inventory limits.
- `campaign_publish_intents`: nonce, hash, unsigned transaction, blockhash,
  simulation output, and confirmation signature.

### Part 1 chain design

Campaign PDA seeds:

```text
["campaign", creator_wallet, nonce_16_bytes]
```

The initialized account stores creator, USDC mint, unit price, threshold, main
goal, dates, metadata URI/hash, stretch goals, raised atomic amount, unit
aggregates, and lifecycle status. The `initialize_campaign` instruction is
creator-signed and receives the deployment's USDC mint as an account.

## Part 2: subscription purchase, escrow, settlement, and Support Points

### User story

As a supporter, I can buy one or more campaign subscription units from my
wallet. The first unit is immediately active, additional units are pending, and
I can see exactly what happens if the campaign succeeds or fails.

### Functional requirements

- Purchase amount is `unit_price_atomic * purchased_units` with checked
  arithmetic.
- The program performs the checked SPL-token transfer into campaign escrow.
- A supporter position is a PDA keyed by campaign and supporter.
- The first unit for a campaign is immediate; additional units are pending.
- A position records active units, pending units, and contributed atomic amount.
- A campaign records raised amount and aggregate active/pending units.
- Every confirmed purchase produces a contribution projection keyed by chain
  signature.
- Every purchased unit grants 100 base Support Points.
- Immediate-unit points are available; pending-unit points are pending.
- Success promotes pending units and pending points, then awards the configured
  bonus exactly once.
- Failure refunds pending units from escrow, removes pending points, and keeps
  the immediate unit and its confirmed points.
- A supporter cannot purchase a campaign outside its active time window.
- A duplicate signature is a no-op in the indexer and does not duplicate points.

### Part 2 chain design

Position PDA seeds:

```text
["position", campaign_pda, supporter_wallet]
```

`purchase_subscription` accepts the campaign, position, supporter, source token
account, escrow token account, USDC mint, token program, and system program. It
uses SPL Token `TransferChecked` with six decimals, then updates both position
and campaign aggregates in the same transaction.

The settlement instruction family must be creator-authorized, time-aware, and
idempotent per position. Successful settlement promotes pending units. Failed
settlement transfers the pending amount back to the supporter using the
campaign PDA as escrow authority. A future batch settlement instruction may
optimize this without changing the state machine.

### Part 2 API

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/campaigns/{id}/purchase` | build and simulate purchase tx |
| GET | `/supporter/points` | current balances |
| GET | `/supporter/points/ledger` | immutable point history |
| GET | `/supporter/contributions` | contribution history |
| POST | `/athlete/campaigns/{id}/settle` | operator/creator settlement intent |

The implementation currently exposes the purchase builder and read models. The
creator settlement intent is the next chain/API extension after the current
purchase instruction is deployed.

### Failure handling

- RPC failure: return a gateway error, leave the database unchanged.
- Simulation error: return structured error and logs, do not return a wallet
  transaction.
- Wallet rejection: browser keeps the campaign page and allows retry.
- Signature confirmation timeout: keep the signature and let reconciliation
  resolve it; do not apply points from the client.
- Duplicate webhook: raw ingest and contribution projection remain unchanged.
- Malformed event: retain the raw transaction, mark processing failure, alert
  operations, and make reconciliation retryable.

## Part 3: reward tiers, platform store, athlete rewards, and fulfillment

### User story

As a supporter, I can see which campaign rewards my confirmed units unlock and
redeem Support Points for platform cosmetics or athlete-created offers. As an
athlete, I can publish offers with inventory and fulfillment rules and process
redemptions without touching campaign funds.

### Functional requirements

- Campaign reward tiers become eligible only from confirmed/activated units.
- Cumulative tiers unlock together.
- Non-cumulative tiers expose only the highest unlocked tier in that group.
- Inventory and per-supporter limits are enforced in one transaction.
- Entitlement status moves from locked to unlocked to fulfillment states.
- Platform cosmetics are public catalog items redeemed once per supporter.
- Athlete offers contain price, description, inventory, per-user limit, date
  window, fulfillment type, and optional metadata URI.
- Point redemption locks the point account and catalog row before decrementing.
- Point ledger entries have a unique source key and negative delta for spends.
- Reward orders do not move USDC and cannot change campaign status or balances.
- Physical/session fulfillment stores only the minimum details required and
  remains operator/athlete protected.

### Part 3 data model

- `campaign_reward_entitlements`: campaign tier unlock and fulfillment state.
- `platform_cosmetic_items`: platform catalog.
- `supporter_cosmetics`: unique supporter ownership.
- `athlete_reward_offers`: athlete catalog and inventory.
- `athlete_reward_orders`: point reservation and fulfillment state.
- `support_point_ledger`: immutable earning, promotion, refund, and redemption
  entries.

### Part 3 API

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/store/cosmetics` | platform catalog |
| POST | `/store/cosmetics/{id}/redeem` | redeem cosmetic atomically |
| GET | `/reward-offers` | active athlete offers |
| GET | `/athlete/reward-offers` | athlete-owned offers |
| POST | `/athlete/reward-offers` | create offer |
| POST | `/reward-offers/{id}/redeem` | reserve points and inventory |

### Fulfillment state machine

```text
locked -> unlocked -> in_progress -> fulfilled
             |             |
             +-----------> cancelled
```

Orders use a separate state machine:

```text
reserved -> awaiting_details -> in_progress -> shipped/scheduled -> fulfilled
     |                                                       |
     +-----------------------> refunded <------------------+
```

Every transition is authorized by the owning athlete or operator and recorded
with actor, timestamp, and optional fulfillment reference.

## Part 4: payouts, vesting, indexing, operations, and launch

### User story

As an athlete, I can see when successful campaign value becomes withdrawable.
As an operator, I can reconcile webhook and RPC data, replay projections, and
diagnose stuck settlements without editing authoritative state.

### Functional requirements

- Successful campaign value is separated into platform fee, campaign release,
  and athlete vesting entries according to configured basis points.
- Standard units produce monthly vesting entries.
- Immediate campaign release entries are distinct from standard monthly entries.
- Each vesting entry has amount, release time, kind, status, and transaction
  signature.
- A release worker claims rows with a lock, builds/simulates a transaction,
  submits through an authorized payout wallet or configured custody boundary,
  and marks the row only after confirmation.
- The payout signer is isolated from supporter and athlete wallet signing.
- The indexer stores raw transactions before parsing them.
- Anchor event discriminators are decoded from `Program data` logs.
- Unique `(signature, event_index)` and contribution signature constraints make
  replay idempotent.
- Reconciliation walks RPC signatures from a cursor and replays missing events.
- Webhook authorization fails closed when its secret is missing.
- Readiness remains degraded until database, RPC, and required configuration
  are available.

### Part 4 operational routes and jobs

- webhook ingest: authenticate, persist raw transaction, enqueue processing;
- indexer worker: parse known events and update read models;
- reconciliation worker: compare RPC signatures and retry pending raw rows;
- settlement worker: detect ended campaigns, build settlement intents, and
  await creator/operator authorization as required by the program;
- vesting worker: release due entries and reconcile confirmations;
- fulfillment worker: notify or expose orders requiring human action;
- diagnostics: database, RPC, ingest backlog, cursor, and worker health.

### Observability

Required structured fields:

```text
request_id, signature, campaign_pda, campaign_id, wallet, event_type,
source_key, worker_run_id, retry_count, status, latency_ms
```

Metrics:

- indexed transaction lag;
- raw rows pending/failed;
- projection replay count and duplicate count;
- purchase simulation failures;
- settlement age;
- vesting rows due/failed;
- reward redemption conflict rate;
- RPC latency and error rate.

## Cross-part architecture

```text
Wallet
  | SIWS / signed transactions
Web React SPA
  | authenticated JSON / unsigned tx
FastAPI API -------------------- Supabase Auth
  | DB transactions
Supabase Postgres read model
  ^ raw ingest + idempotent projections
Indexer / reconciliation -------- Solana RPC / Helius
  | simulated instructions
Anchor program ------------------- SPL Token escrow
```

### Trust boundaries

- Browser: untrusted input and wallet-controlled signing.
- API: trusted orchestration but not a source of financial truth.
- Supabase: protected read model and workflow state.
- Indexer: replayable translator, not authority.
- Anchor program: authority for campaign and token state.
- Payout signer: isolated operational authority with explicit policy.

### Security requirements

- verify JWT issuer, audience, expiry, and wallet claim;
- authorize every athlete-owned route by database ownership;
- never accept client-provided points, balances, status, price, or completion
  state as truth;
- use integer arithmetic and checked on-chain arithmetic;
- verify exact mint, token program, PDA, and transaction signature shape;
- bind publish intent to campaign ID, nonce, snapshot hash, and creator wallet;
- use idempotency/source keys for every external event and point operation;
- protect service-role credentials and payout signing keys server-side;
- keep PII out of public metadata and logs;
- rate-limit webhook, purchase preparation, and redemption routes.

## End-to-end acceptance criteria

1. A wallet can authenticate and see its profile.
2. An athlete can activate a profile, publish a plan, create a campaign, and
   publish an immutable snapshot.
3. A supporter can prepare and sign a purchase with exact six-decimal USDC.
4. The program transfers tokens and records immediate/pending units.
5. Replaying the same transaction does not duplicate contributions or points.
6. Success and failure produce the expected unit, escrow, and points outcomes.
7. Eligible reward tiers and stores enforce inventory and point balances.
8. Payout rows sum exactly to their source atomic amount and release on schedule.
9. Indexer recovery from raw transactions produces the same projection as live
   webhook processing.
10. Local, staging, and production environments fail closed when required
    dependencies or secrets are absent.

## Non-goals for the first production slice

- fiat payments or card subscriptions;
- transferable points or a points token;
- secondary markets;
- arbitrary supporter-to-supporter transfers;
- anonymous physical fulfillment data;
- automatic financial advice or tax calculations;
- editable on-chain campaign terms after publication.
