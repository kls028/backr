# Profile and Campaign Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build wallet-authenticated athlete profiles, immutable subscription plans, campaign authoring, and verified on-chain campaign publication for the first product slice.

**Architecture:** Extend the existing Supabase/SIWS identity boundary with role and athlete-profile records, store campaign configuration in Postgres as the off-chain read model, and initialize a compact Anchor `Campaign` account from an unsigned transaction built by FastAPI. The browser wallet signs and submits the transaction; webhook and reconciliation logic verifies the chain account before changing a campaign from draft to scheduled or active.

**Tech Stack:** React 19, Vite, React Router, TypeScript, shadcn/ui, Solana Wallet Adapter, Supabase Auth, Supabase Postgres, FastAPI, Pydantic, SQLAlchemy async, Python 3.12, Anchor, Rust 1.89, Solana RPC, Helius webhook, pytest, cargo test.

## Global Constraints

- The program owns financial truth; Postgres is a derived read model and configuration store.
- The backend never holds a user key; it only builds and simulates unsigned transactions.
- Every ingest and confirmation write is idempotent.
- `supabase/migrations` is the only schema authority; SQLAlchemy models mirror it by hand.
- Authentication and webhook writes fail closed.
- USDC values use integer base units with six decimal places; no floating-point arithmetic is permitted for money.
- The campaign supports one minimum threshold, one optional main goal, and up to eight ordered stretch goals.
- A published campaign's price, schedule, thresholds, goals, reward tiers, metadata URI, and metadata hash are immutable.
- This plan does not implement USDC transfers, escrow, Support Points, settlement, payouts, vesting, or reward fulfillment.
- Existing local commands remain authoritative: `pnpm chain:build`, `pnpm idl:sync`, `pnpm typecheck`, `cd services/api && uv run pytest`, `cd services/api && uv run ruff check . && uv run mypy app`, and `cd onchain && cargo test`.

---

## File map

### Database and API

- Create `supabase/migrations/20260809000001_campaign_foundation.sql` for roles, athlete profiles, plans, campaigns, goals, tiers, and publish intents.
- Modify `services/api/app/models.py` to mirror every migration table and enum.
- Create `services/api/app/domain/money.py` for exact USDC conversion and formatting.
- Create `services/api/app/domain/campaigns.py` for cross-field validation, canonical snapshots, and lifecycle transitions.
- Create `services/api/app/schemas/profiles.py` for athlete-profile request/response models.
- Create `services/api/app/schemas/plans.py` for subscription-plan request/response models.
- Create `services/api/app/schemas/campaigns.py` for campaign, goal, tier, publish, and confirmation contracts.
- Modify `services/api/app/routers/profiles.py` to add athlete-role activation and athlete-profile fields.
- Create `services/api/app/routers/plans.py` for plan CRUD and publish/archive transitions.
- Create `services/api/app/routers/campaigns.py` for public reads and athlete-owned draft mutations.
- Create `services/api/app/routers/campaign_publication.py` for publish intent and signature confirmation.
- Create `services/api/app/solana/campaign.py` for PDA derivation, instruction serialization, and unsigned transaction arguments.
- Modify `services/api/app/main.py` to include the new routers and lifecycle dependencies.
- Create `services/api/tests/test_money.py`, `services/api/tests/test_campaign_domain.py`, `services/api/tests/test_plans.py`, `services/api/tests/test_campaigns.py`, `services/api/tests/test_campaign_publication.py`, and `services/api/tests/test_campaign_indexing.py`.

### On-chain

- Replace the counter-only surface in `onchain/programs/sss_core/src/lib.rs` with campaign initialization while retaining no counter routes in the new domain.
- Modify `onchain/programs/sss_core/src/constants.rs` with campaign seeds, bounds, and metadata limits.
- Create `onchain/programs/sss_core/src/state/campaign.rs` with `Campaign`, `CampaignStatus`, and bounded goal representation.
- Modify `onchain/programs/sss_core/src/state.rs` to export campaign state.
- Create `onchain/programs/sss_core/src/instructions/initialize_campaign.rs` with account constraints and validation.
- Modify `onchain/programs/sss_core/src/instructions.rs` and `onchain/programs/sss_core/src/lib.rs` to expose the instruction.
- Modify `onchain/programs/sss_core/src/error.rs` with campaign validation errors.
- Create `onchain/programs/sss_core/tests/test_initialize_campaign.rs` with valid and invalid initialization cases.

### Indexer and shared IDL

- Modify `services/api/app/indexer/parser.py` to parse campaign initialization data and enforce the program discriminator.
- Modify `services/api/app/indexer/reconcile.py` to verify publish intents and transition campaigns only after chain confirmation.
- Modify `services/api/app/routers/events.py` or create `services/api/app/routers/campaign_events.py` for verified campaign reads if the existing event route boundary becomes too domain-specific.
- Run `pnpm chain:build && pnpm idl:sync` to regenerate the ignored IDL output after Anchor changes.

### Web

- Modify `apps/web/src/lib/api.ts` with typed profile, plan, campaign, publish-intent, and confirmation contracts.
- Create `apps/web/src/routes/CampaignDirectoryPage.tsx`.
- Create `apps/web/src/routes/CampaignDetailPage.tsx`.
- Create `apps/web/src/routes/AthleteSetupPage.tsx`.
- Create `apps/web/src/routes/SubscriptionPlanPage.tsx`.
- Create `apps/web/src/routes/CampaignEditorPage.tsx`.
- Create `apps/web/src/routes/CampaignReviewPage.tsx`.
- Create `apps/web/src/components/campaign/CampaignForm.tsx`, `CampaignSummary.tsx`, `GoalEditor.tsx`, `RewardTierEditor.tsx`, and `CampaignStatusBadge.tsx`.
- Modify `apps/web/src/App.tsx` and `apps/web/src/components/SiteHeader.tsx` with routes and navigation.
- Modify `apps/web/src/lib/solana.ts` only if the existing `signAndSend` helper needs a typed confirmation callback; keep transaction signing client-side.
- Modify `apps/web/src/index.css` only for small layout/token additions that are needed by the new forms.

---

## Task 1: Add exact money and campaign-domain validation

**Files:**

- Create: `services/api/app/domain/money.py`
- Create: `services/api/app/domain/campaigns.py`
- Test: `services/api/tests/test_money.py`
- Test: `services/api/tests/test_campaign_domain.py`

**Interfaces:**

- `parse_usdc_amount(value: str) -> int`: accept a decimal string and return six-decimal atomic units.
- `format_usdc_amount(atomic: int) -> str`: return a non-exponential decimal string with up to six fractional digits.
- `CampaignDraftInput`: typed domain input containing plan price, start/end timestamps, minimum threshold, optional main goal, stretch goals, and reward tiers.
- `validate_campaign_draft(input: CampaignDraftInput) -> None`: raise a domain validation error with field-level issues.
- `canonical_campaign_snapshot(input: CampaignDraftInput, campaign_id: UUID, nonce: bytes) -> bytes`: return deterministic UTF-8 JSON with sorted keys and normalized values.
- `campaign_snapshot_hash(snapshot: bytes) -> bytes`: return a 32-byte SHA-256 digest.
- `CampaignStatus`: `draft | scheduled | active | funded | successful | unsuccessful | cancelled`.
- `CampaignEvent`: `publish_verified | cancel_requested | settlement_funded | settlement_successful | settlement_unsuccessful`.
- `transition_campaign(current: CampaignStatus, event: CampaignEvent) -> CampaignStatus`: permit only the state transitions in the design document.

- [ ] **Step 1: Write failing money tests**

```python
def test_parse_usdc_amount_uses_six_decimals() -> None:
    assert parse_usdc_amount("25") == 25_000_000
    assert parse_usdc_amount("25.125") == 25_125_000


def test_parse_usdc_amount_rejects_over_precision() -> None:
    with pytest.raises(MoneyValidationError, match="at most 6 decimal places"):
        parse_usdc_amount("1.0000001")


def test_format_usdc_amount_round_trips_without_float() -> None:
    assert format_usdc_amount(25_125_000) == "25.125"
    assert format_usdc_amount(1) == "0.000001"
```

- [ ] **Step 2: Run the focused tests and verify they fail for missing symbols**

Run:

```bash
cd services/api && uv run pytest tests/test_money.py -q
```

Expected: collection fails because `app.domain.money` does not yet exist.

- [ ] **Step 3: Implement integer-only money conversion**

Use `decimal.Decimal` constructed from the input string, reject non-finite values, reject negative values where the caller requests a positive amount, quantize only after checking that the input has no more than six fractional digits, and convert to an integer with `Decimal("1000000")`. Never use `float`.

- [ ] **Step 4: Add failing campaign validation tests**

```python
def test_campaign_requires_monotonic_goals() -> None:
    draft = valid_campaign_input(
        minimum_success_threshold=800,
        main_goal=700,
        stretch_goals=[900],
    )
    with pytest.raises(CampaignValidationError) as error:
        validate_campaign_draft(draft)
    assert error.value.field_errors["main_goal"] == "must be at least the minimum threshold"


def test_campaign_rejects_non_increasing_stretch_goals() -> None:
    draft = valid_campaign_input(stretch_goals=[900, 900])
    with pytest.raises(CampaignValidationError, match="strictly increasing"):
        validate_campaign_draft(draft)


def test_snapshot_hash_is_stable_for_equivalent_inputs() -> None:
    first = canonical_campaign_snapshot(valid_campaign_input(), UUID("00000000-0000-0000-0000-000000000001"), b"nonce-16-bytes!!")
    second = canonical_campaign_snapshot(valid_campaign_input(), UUID("00000000-0000-0000-0000-000000000001"), b"nonce-16-bytes!!")
    assert campaign_snapshot_hash(first) == campaign_snapshot_hash(second)
```

- [ ] **Step 5: Implement validation, canonical snapshot, and transition matrix**

Validate positive atomic amounts, timezone-aware ordered timestamps, minimum/main/stretch order, maximum eight stretch goals, strictly increasing reward-unit thresholds, non-empty benefit text, positive quantities, and `max_per_supporter <= max_supply` when both are set. Normalize timestamps to UTC and sort object keys in the snapshot.

- [ ] **Step 6: Run the focused domain tests**

Run:

```bash
cd services/api && uv run pytest tests/test_money.py tests/test_campaign_domain.py -q
```

Expected: all focused tests pass.

- [ ] **Step 7: Commit the domain boundary**

```bash
git add services/api/app/domain services/api/tests/test_money.py services/api/tests/test_campaign_domain.py
git commit -m "feat: add campaign money and validation domain"
```

## Task 2: Add roles, athlete profiles, plans, and campaign schema

**Files:**

- Create: `supabase/migrations/20260809000001_campaign_foundation.sql`
- Modify: `services/api/app/models.py`
- Create: `services/api/app/schemas/profiles.py`
- Create: `services/api/app/schemas/plans.py`
- Create: `services/api/app/schemas/campaigns.py`
- Test: `services/api/tests/test_plans.py`

**Interfaces:**

- `ProfileRole`: `supporter | athlete`.
- `PlanStatus`: `draft | published | archived`.
- `CampaignStatus`: `draft | scheduled | active | funded | successful | unsuccessful | cancelled`.
- `ProfileRoleRow`, `AthleteProfile`, `SubscriptionPlan`, `Campaign`, `CampaignStretchGoal`, `CampaignRewardTier`, and `CampaignPublishIntent` SQLAlchemy models mirroring SQL exactly.
- `AthleteProfileUpdate`, `SubscriptionPlanCreate`, `SubscriptionPlanUpdate`, `SubscriptionPlanOut`, `CampaignCreate`, `CampaignUpdate`, `CampaignOut`, `CampaignGoalOut`, `CampaignRewardTierIn`, and `CampaignRewardTierOut` Pydantic models.

- [ ] **Step 1: Write the migration with database-level invariants**

Create the enum types and tables described in the file map. Use UUID primary keys generated with `gen_random_uuid()`, foreign keys to `profiles`, `subscription_plans`, and `campaigns`, `timestamptz` for all lifecycle times, `bigint` for atomic USDC values, and `bytea` or a fixed-length-compatible representation for the 32-byte snapshot hash. Add unique constraints for `(profile_id, role)`, one active plan per athlete, one campaign PDA, one publish intent per campaign, and one chain signature.

Use checks for positive price/thresholds, `end_at > start_at`, bounded metadata URI length, and maximum stretch-goal/tier counts. Use triggers for `updated_at`, matching the existing `public.set_updated_at()` helper. Add RLS policies for owner reads/writes and public read policies that permit only `scheduled`, `active`, and later public statuses.

- [ ] **Step 2: Add SQLAlchemy mirrors**

Mirror enum names and SQL column types exactly. Keep the migration authoritative; do not add Alembic. Add relationships only where they reduce query mistakes, and use explicit `select` statements in route code for owner checks.

- [ ] **Step 3: Add Pydantic schemas with precise money boundaries**

Expose `unit_price_usdc` as a decimal string for form/API usability and `unit_price_usdc_atomic` as a read-only integer in responses. Use `extra="forbid"` on authoring inputs. Validate string lengths, URI length, reward limits, and timezone-aware timestamps before calling the domain validator.

- [ ] **Step 4: Add plan tests before route implementation**

```python
def test_plan_input_rejects_more_than_six_fractional_digits() -> None:
    with pytest.raises(ValidationError):
        SubscriptionPlanCreate(unit_price_usdc="1.0000001", benefits="Access")


def test_campaign_response_exposes_price_snapshot() -> None:
    result = CampaignOut.model_validate(campaign_fixture())
    assert result.unit_price_usdc_atomic == 25_000_000
```

- [ ] **Step 5: Reset the local database and verify the schema**

Run:

```bash
pnpm db:reset
```

Expected: migration applies without errors. Confirm the new enums, tables, unique indexes, and RLS policies exist in the local Supabase database before continuing.

- [ ] **Step 6: Commit the schema and contracts**

```bash
git add supabase/migrations/20260809000001_campaign_foundation.sql services/api/app/models.py services/api/app/schemas services/api/tests/test_plans.py
git commit -m "feat: add campaign foundation schema and contracts"
```

## Task 3: Implement profile roles and subscription-plan API

**Files:**

- Modify: `services/api/app/routers/profiles.py`
- Create: `services/api/app/routers/plans.py`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_plans.py`

**Interfaces:**

- `POST /profiles/me/athlete -> AthleteProfileOut`.
- `GET /profiles/me/roles -> list[ProfileRoleOut]`.
- `GET /subscription-plans/me -> SubscriptionPlanOut | null`.
- `POST /subscription-plans -> SubscriptionPlanOut`.
- `PATCH /subscription-plans/{plan_id} -> SubscriptionPlanOut`.
- `POST /subscription-plans/{plan_id}/publish -> SubscriptionPlanOut`.
- `POST /subscription-plans/{plan_id}/archive -> SubscriptionPlanOut`.

- [ ] **Step 1: Add failing authorization tests**

```python
async def test_supporter_cannot_create_plan(client, supporter_token) -> None:
    response = await client.post(
        "/subscription-plans",
        headers=auth_headers(supporter_token),
        json={"unit_price_usdc": "25", "benefits": "Access"},
    )
    assert response.status_code == 403


async def test_athlete_activation_is_idempotent(client, athleteless_token) -> None:
    first = await client.post("/profiles/me/athlete", headers=auth_headers(athleteless_token), json={"display_name": "Athlete", "sport": "Tennis"})
    second = await client.post("/profiles/me/athlete", headers=auth_headers(athleteless_token), json={"display_name": "Athlete", "sport": "Tennis"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
```

- [ ] **Step 2: Implement athlete activation and role checks**

Resolve the caller from `CurrentUserDep`, load the profile by `user.id`, insert the `athlete` role with `ON CONFLICT DO NOTHING`, and upsert the athlete profile. Never accept a profile ID or wallet address from the request body. Add a small dependency such as `require_athlete(user, session)` for plan and campaign routes.

- [ ] **Step 3: Implement plan CRUD and status transitions**

Create exactly one draft plan per athlete. Permit edits only while `draft`. `publish` requires positive price and non-empty benefits, changes status to `published`, and returns the immutable price. `archive` changes `published` to `archived` only when no campaign publication intent depends on the plan. Return 409 for illegal transitions and 404 for another athlete's plan.

- [ ] **Step 4: Add API tests for ownership and immutability**

Cover create, read, update, publish, repeated publish, edit-after-publish rejection, archive, duplicate-draft rejection, missing athlete role, and another-user access. Assert that stored atomic price remains exact.

- [ ] **Step 5: Run API tests and static checks**

Run:

```bash
cd services/api && uv run pytest tests/test_auth.py tests/test_plans.py -q
cd services/api && uv run ruff check app tests && uv run mypy app
```

Expected: all selected tests pass and ruff/mypy exit with code 0.

- [ ] **Step 6: Commit profile and plan API**

```bash
git add services/api/app/routers/profiles.py services/api/app/routers/plans.py services/api/app/main.py services/api/tests/test_plans.py
git commit -m "feat: add athlete profiles and subscription plans"
```

## Task 4: Implement Anchor campaign account and initialization

**Files:**

- Modify: `onchain/programs/sss_core/src/lib.rs`
- Modify: `onchain/programs/sss_core/src/constants.rs`
- Modify: `onchain/programs/sss_core/src/state.rs`
- Create: `onchain/programs/sss_core/src/state/campaign.rs`
- Modify: `onchain/programs/sss_core/src/instructions.rs`
- Create: `onchain/programs/sss_core/src/instructions/initialize_campaign.rs`
- Modify: `onchain/programs/sss_core/src/error.rs`
- Create: `onchain/programs/sss_core/tests/test_initialize_campaign.rs`

**Interfaces:**

- `initialize_campaign(ctx: Context<InitializeCampaign>, args: InitializeCampaignArgs) -> Result<()>`.
- `InitializeCampaignArgs { nonce: [u8; 16], unit_price_atomic: u64, minimum_success_threshold_atomic: u64, main_goal_atomic: u64, stretch_goals_atomic: Vec<u64>, start_at: i64, end_at: i64, metadata_uri: String, metadata_hash: [u8; 32] }`.
- PDA: `Pubkey::find_program_address(&[b"campaign", creator.key().as_ref(), &args.nonce], program_id)`.
- `CampaignStatus::Draft` as the on-chain initialization status; the indexer maps verified time to public `scheduled` or `active`.

- [ ] **Step 1: Add failing Rust tests for valid account shape and invalid arguments**

```rust
#[test]
fn campaign_pda_uses_creator_and_nonce() {
    let creator = Pubkey::new_unique();
    let nonce = *b"0123456789abcdef";
    let (pda, bump) = Pubkey::find_program_address(
        &[b"campaign", creator.as_ref(), &nonce],
        &sss_core::ID,
    );
    assert_ne!(pda, Pubkey::default());
    assert!(bump <= u8::MAX);
}
```

Add integration cases that initialize valid data, reject zero price, reject threshold greater than main goal, reject non-increasing stretch goals, reject a ninth stretch goal, reject `end_at <= start_at`, and reject metadata over the bound.

- [ ] **Step 2: Define bounded state and constants**

Use a bounded `Vec<u64>` with `MAX_STRETCH_GOALS = 8`, `MAX_METADATA_URI_BYTES = 200`, and explicit account-space calculation. Define errors for invalid mint, invalid amount, invalid goal order, invalid schedule, too many goals, and metadata overflow. Do not include token transfer accounts in this instruction.

- [ ] **Step 3: Implement account constraints and handler**

Require a mutable creator signer, initialize the campaign PDA with the creator as payer, store all argument values exactly, set `raised_amount_atomic = 0`, set status to `Draft`, and persist the PDA bump. Validate all cross-field rules before writing state. The handler must not call a token program or move lamports beyond normal account initialization rent.

- [ ] **Step 4: Run Anchor formatting and build**

Run:

```bash
cd onchain && cargo fmt --check
cd .. && pnpm chain:build
```

Expected: formatting check passes and Anchor produces the updated IDL/build artifacts.

- [ ] **Step 5: Run the on-chain test suite**

Run:

```bash
cd onchain && cargo test
```

Expected: valid initialization and every invalid-argument test pass.

- [ ] **Step 6: Synchronize the shared IDL**

Run:

```bash
cd .. && pnpm idl:sync
```

Expected: the generated IDL is available to local builds and the sync script reports no program-ID drift.

- [ ] **Step 7: Commit the Anchor boundary**

```bash
git add onchain/programs/sss_core/src onchain/programs/sss_core/tests
git commit -m "feat: add on-chain campaign initialization"
```

## Task 5: Build unsigned campaign publication transactions

**Files:**

- Create: `services/api/app/solana/campaign.py`
- Create: `services/api/app/routers/campaign_publication.py`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_campaign_publication.py`

**Interfaces:**

- `campaign_pda(program_id: Pubkey, creator: Pubkey, nonce: bytes) -> tuple[Pubkey, int]`.
- `CampaignInitializationArgs`: Python dataclass with the same fields and serialization order as Anchor's `InitializeCampaignArgs`.
- `build_initialize_campaign_ix(program_id: Pubkey, creator: Pubkey, usdc_mint: Pubkey, args: CampaignInitializationArgs) -> Instruction`.
- `POST /athlete/campaigns/{campaign_id}/publish -> CampaignPublishOut`.
- `POST /athlete/campaigns/{campaign_id}/publish/confirm -> CampaignPublishConfirmOut`.

- [ ] **Step 1: Add failing instruction-builder tests**

```python
def test_campaign_instruction_uses_expected_seed_and_account_order() -> None:
    ix = build_initialize_campaign_ix(PROGRAM, CREATOR, USDC_MINT, valid_args())
    pda, _ = campaign_pda(PROGRAM, CREATOR, valid_args().nonce)
    assert ix.program_id == PROGRAM
    assert [meta.pubkey for meta in ix.accounts][:3] == [CREATOR, pda, USDC_MINT]
    assert ix.accounts[0].is_signer is True
    assert ix.accounts[1].is_writable is True


def test_publish_transaction_has_no_backend_signature() -> None:
    result = to_unsigned_transaction([build_initialize_campaign_ix(PROGRAM, CREATOR, USDC_MINT, valid_args())], CREATOR, BLOCKHASH)
    decoded = VersionedTransaction.from_bytes(base64.b64decode(result))
    assert decoded.signatures[0] == Signature.default()
```

- [ ] **Step 2: Implement PDA and Anchor serialization from the synced IDL**

Keep account order identical to the generated IDL. Serialize the 16-byte nonce, u64 values, i64 timestamps, bounded vector, URI, and 32-byte hash using the same little-endian/Borsh layout as Anchor. Include the configured USDC mint from `Settings`; reject a missing or malformed mint before building the transaction.

- [ ] **Step 3: Implement publish-intent creation**

Load the caller-owned draft with a row lock. Validate the full draft, require a published plan, create or reuse a 16-byte nonce, freeze the publication snapshot, compute the hash, derive the PDA, build and simulate the transaction, and insert one `campaign_publish_intents` row. If an intent already exists, return its stored transaction metadata without rebuilding a second intent.

- [ ] **Step 4: Implement signature confirmation**

Accept a base58 signature and expected PDA. Validate that the signature format is parseable and that it matches the current user's campaign publish intent. Store the signature as pending. Do not set campaign status, do not mark the campaign published, and do not trust a client-provided status.

- [ ] **Step 5: Add API tests**

Cover missing athlete role, non-owner campaign, unpublished plan, invalid draft, RPC simulation error, duplicate publish request, malformed signature, wrong PDA, and successful pending confirmation. Assert no endpoint returns a signed transaction.

- [ ] **Step 6: Run API tests and type checks**

Run:

```bash
cd services/api && uv run pytest tests/test_tx.py tests/test_campaign_publication.py -q
cd services/api && uv run ruff check app tests && uv run mypy app
```

Expected: all selected tests pass and static checks exit with code 0.

- [ ] **Step 7: Commit the publication transaction path**

```bash
git add services/api/app/solana/campaign.py services/api/app/routers/campaign_publication.py services/api/app/main.py services/api/tests/test_campaign_publication.py
git commit -m "feat: build unsigned campaign publication transactions"
```

## Task 6: Implement campaign authoring and public read APIs

**Files:**

- Create: `services/api/app/routers/campaigns.py`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_campaigns.py`

**Interfaces:**

- `GET /campaigns?status=scheduled|active&limit=50&before=... -> list[CampaignOut]`.
- `GET /campaigns/{campaign_id} -> CampaignOut`.
- `GET /athlete/campaigns -> list[CampaignOut]` including the caller's drafts.
- `POST /athlete/campaigns -> CampaignOut`.
- `PATCH /athlete/campaigns/{campaign_id} -> CampaignOut`.
- `POST /athlete/campaigns/{campaign_id}/cancel -> CampaignOut`.

- [ ] **Step 1: Add failing route tests**

```python
async def test_campaign_requires_published_plan(client, athlete_token) -> None:
    response = await client.post(
        "/athlete/campaigns",
        headers=auth_headers(athlete_token),
        json=valid_campaign_payload(plan_id=str(unpublished_plan.id)),
    )
    assert response.status_code == 409


async def test_public_listing_excludes_drafts(client, public_campaign, draft_campaign) -> None:
    response = await client.get("/campaigns")
    ids = {item["id"] for item in response.json()}
    assert str(public_campaign.id) in ids
    assert str(draft_campaign.id) not in ids
```

- [ ] **Step 2: Implement draft creation and updates**

Require the athlete role, verify the plan belongs to the caller and is published, copy `unit_price_usdc_atomic` into the campaign, validate the draft with the domain module, and persist child goals and tiers in one transaction. Update only drafts. Return 409 after publish intent exists.

- [ ] **Step 3: Implement owner and public reads**

Use keyset pagination ordered by `created_at DESC, id DESC`. Public reads return scheduled, active, and later public terminal statuses only; owner reads return the caller's drafts and publication state. Never use a client-supplied athlete ID for filtering.

- [ ] **Step 4: Implement cancellation**

Allow cancellation only for draft campaigns and scheduled campaigns whose publish intent has not been chain-confirmed as active or purchased. Return 409 for active campaigns or any campaign with later-slice activity. Keep the row and snapshot for auditability.

- [ ] **Step 5: Add regression tests**

Cover cross-field validation, price snapshot, child-row replacement on draft update, owner-only access, public filtering, keyset pagination, cancellation, and edit-after-publication rejection.

- [ ] **Step 6: Run API checks**

Run:

```bash
cd services/api && uv run pytest tests/test_campaigns.py -q
cd services/api && uv run ruff check app tests && uv run mypy app
```

Expected: all selected tests pass and static checks exit with code 0.

- [ ] **Step 7: Commit campaign API**

```bash
git add services/api/app/routers/campaigns.py services/api/app/main.py services/api/tests/test_campaigns.py
git commit -m "feat: add campaign authoring and public reads"
```

## Task 7: Verify campaign initialization in the indexer

**Files:**

- Modify: `services/api/app/indexer/parser.py`
- Modify: `services/api/app/indexer/reconcile.py`
- Create: `services/api/tests/test_campaign_indexing.py`

**Interfaces:**

- `parse_campaign_initialization(raw_transaction: dict[str, Any]) -> ParsedCampaignInitialization`.
- `verify_campaign_publish(intent: CampaignPublishIntent, parsed: ParsedCampaignInitialization) -> None`.
- `reconcile_campaign_publish(session: AsyncSession, parsed: ParsedCampaignInitialization) -> Campaign`.

- [ ] **Step 1: Add parser fixtures and failing tests**

```python
def test_parser_extracts_campaign_initialization() -> None:
    parsed = parse_campaign_initialization(valid_initialize_transaction())
    assert parsed.creator == CREATOR
    assert parsed.campaign_pda == CAMPAIGN_PDA
    assert parsed.unit_price_atomic == 25_000_000
    assert parsed.metadata_hash == SNAPSHOT_HASH


def test_parser_rejects_wrong_program() -> None:
    with pytest.raises(IndexerParseError, match="unexpected program"):
        parse_campaign_initialization(transaction_for_program("11111111111111111111111111111111"))
```

- [ ] **Step 2: Implement discriminator and account validation**

Match the synced Anchor discriminator, program ID, account order, creator signer, campaign PDA, and decoded argument bounds. Preserve the raw transaction in `indexed_transactions` for audit and debugging.

- [ ] **Step 3: Implement intent verification and lifecycle transition**

Look up the unique publish intent by PDA/signature, compare creator, mint, nonce, terms, URI, and hash to the immutable snapshot, and raise a durable ingest error on any mismatch. After verification, update the campaign chain signature, slot, observed timestamps, and status to `scheduled` or `active` based on `start_at`.

- [ ] **Step 4: Add idempotency tests**

Process the same signature twice and assert one campaign transition, one signature record, and no duplicate event. Process the same PDA with different terms and assert the campaign remains draft with a failed ingest record.

- [ ] **Step 5: Run API/indexer tests**

Run:

```bash
cd services/api && uv run pytest tests/test_campaign_indexing.py -q
```

Expected: valid transactions reconcile once; malformed, mismatched, and duplicate transactions are handled according to the tests.

- [ ] **Step 6: Commit verified campaign indexing**

```bash
git add services/api/app/indexer services/api/tests/test_campaign_indexing.py
git commit -m "feat: verify campaign publication in indexer"
```

## Task 8: Implement the web authoring and read experience

**Files:**

- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/components/SiteHeader.tsx`
- Create: `apps/web/src/routes/CampaignDirectoryPage.tsx`
- Create: `apps/web/src/routes/CampaignDetailPage.tsx`
- Create: `apps/web/src/routes/AthleteSetupPage.tsx`
- Create: `apps/web/src/routes/SubscriptionPlanPage.tsx`
- Create: `apps/web/src/routes/CampaignEditorPage.tsx`
- Create: `apps/web/src/routes/CampaignReviewPage.tsx`
- Create: `apps/web/src/components/campaign/CampaignForm.tsx`
- Create: `apps/web/src/components/campaign/CampaignSummary.tsx`
- Create: `apps/web/src/components/campaign/GoalEditor.tsx`
- Create: `apps/web/src/components/campaign/RewardTierEditor.tsx`
- Create: `apps/web/src/components/campaign/CampaignStatusBadge.tsx`

**Interfaces:**

- `api.athleteProfile()`, `api.activateAthleteProfile(input)`, `api.meRoles()`.
- `api.myPlan()`, `api.createPlan(input)`, `api.updatePlan(id, input)`, `api.publishPlan(id)`, `api.archivePlan(id)`.
- `api.campaigns(params)`, `api.campaign(id)`, `api.myCampaigns()`, `api.createCampaign(input)`, `api.updateCampaign(id, input)`, `api.publishCampaign(id)`, `api.confirmCampaignPublish(id, input)`, `api.cancelCampaign(id)`.
- `CampaignForm` emits validated `CampaignCreateInput` and autosaves only after a successful API response.

- [ ] **Step 1: Add API types and route definitions**

Extend `apps/web/src/lib/api.ts` with the response types and methods above. Keep the existing per-request Supabase session lookup so token refresh behavior remains unchanged. Add routes for public and athlete flows without changing the wallet/auth provider.

- [ ] **Step 2: Implement athlete setup and plan editor**

Use controlled inputs, preserve form values after errors, disable submit while a request is pending, and show read-only price/benefits after plan publication. Route unauthenticated users to the existing wallet sign-in state and show 403 responses as an athlete-activation prompt.

- [ ] **Step 3: Implement campaign editor**

Build the four-step form described in the design. Store date inputs as timezone-aware ISO strings, keep monetary inputs as strings until the API validates them, allow adding/removing up to eight stretch goals, and enforce strictly increasing reward thresholds in the UI before submission. Use the API response as the source of truth after each save.

- [ ] **Step 4: Implement review and publication**

Render all immutable terms from the server response. On publish, call the API, decode the returned unsigned transaction, sign it with `useWallet().signTransaction`, submit with the existing `signAndSend`, then call the confirmation endpoint with the resulting signature and PDA. Show `publish pending verification` until a refetched campaign becomes scheduled or active.

- [ ] **Step 5: Implement public directory and detail**

Show only server-provided public campaigns. Display price, threshold, goals, dates, reward tiers, cumulative behavior, availability, status, and chain verification. Do not display a purchase button or claim that subscription access has been granted.

- [ ] **Step 6: Run frontend checks**

Run:

```bash
pnpm typecheck
pnpm lint
pnpm build
```

Expected: TypeScript, oxlint, and Vite build exit with code 0.

- [ ] **Step 7: Commit the web experience**

```bash
git add apps/web/src
git commit -m "feat: add campaign authoring and public campaign views"
```

## Task 9: Run the end-to-end acceptance pass

**Files:**

- Modify: `README.md` with the new local flow and endpoint summary.
- Modify: `.env.example` with the configured USDC mint and metadata settings if not already present.
- Modify: `scripts/doctor.sh` with preflight checks for campaign dependencies.
- Test: existing API, Rust, and frontend checks.

- [ ] **Step 1: Build and sync the program**

Run:

```bash
pnpm chain:build
pnpm idl:sync
```

Expected: build succeeds, the declared program ID matches `.env.example`, and IDL sync completes.

- [ ] **Step 2: Reset and start the local stack**

Run:

```bash
pnpm db:reset
pnpm dev:up
```

Expected: Supabase, validator, API, worker, and web containers become healthy.

- [ ] **Step 3: Exercise the wallet-to-campaign path**

Using a local Solana wallet:

1. Open `http://localhost:5273`.
2. Connect and sign in.
3. Activate the athlete profile.
4. Create and publish a subscription plan at `25` USDC.
5. Create a campaign with threshold `800` USDC, main goal `1000` USDC, two increasing stretch goals, and three increasing reward tiers.
6. Review and publish the campaign.
7. Sign and submit the unsigned initialization transaction.
8. Confirm the signature and wait for reconciliation.
9. Verify the campaign is scheduled or active in the public directory.
10. Verify the campaign detail shows the exact price snapshot and all configured terms.

- [ ] **Step 4: Verify prohibited behavior is absent**

Confirm no USDC transfer occurs, no escrow account is created, no Support Points balance changes, no purchase CTA is reachable, and the API logs contain no wallet private-key material.

- [ ] **Step 5: Run the complete local verification suite**

Run:

```bash
pnpm typecheck
pnpm lint
pnpm build
cd services/api && uv run ruff check . && uv run mypy app && uv run pytest
cd ../../onchain && cargo fmt --check && cargo test
```

Expected: every command exits 0. Record any environment-only failures separately from code failures; do not call the slice complete when a modified-area check fails.

- [ ] **Step 6: Commit documentation and acceptance evidence**

```bash
git add README.md .env.example scripts/doctor.sh docs/superpowers/specs docs/superpowers/plans
git commit -m "docs: define profile and campaign foundation"
```

## Definition of done

- [ ] The migration is applied cleanly and mirrored by SQLAlchemy models.
- [ ] Money and campaign validation tests cover the domain rules.
- [ ] On-chain initialization stores exact immutable terms and rejects invalid input.
- [ ] FastAPI builds only unsigned publication transactions and enforces ownership/roles.
- [ ] Publish confirmation is idempotent and cannot bypass indexer verification.
- [ ] The indexer verifies program, PDA, creator, nonce, values, URI, and snapshot hash.
- [ ] The UI supports athlete setup, plan publishing, campaign drafting, review, publication, and public campaign reads.
- [ ] Focused API, Anchor, frontend, and end-to-end checks provide fresh evidence.
- [ ] The repository contains no implementation of payments, escrow, Support Points, settlement, payouts, or reward fulfillment in this slice.
