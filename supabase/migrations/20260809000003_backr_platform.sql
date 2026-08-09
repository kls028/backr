-- Backr domain schema.
-- The chain remains authoritative for token movement, campaign progress, and
-- settlement. These tables hold configuration, indexed read models, and
-- fulfillment workflows that can be reconstructed from chain events.

-- ---------------------------------------------------------------------------
-- Identity capabilities and athlete profiles
-- ---------------------------------------------------------------------------
create table public.profile_roles (
  profile_id uuid not null references public.profiles(id) on delete cascade,
  role text not null check (role in ('supporter', 'athlete')),
  created_at timestamptz not null default now(),
  primary key (profile_id, role)
);

create table public.athlete_profiles (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null unique references public.profiles(id) on delete cascade,
  display_name text not null check (char_length(display_name) between 1 and 80),
  sport text check (sport is null or char_length(sport) <= 80),
  bio text check (bio is null or char_length(bio) <= 2000),
  avatar_uri text check (avatar_uri is null or char_length(avatar_uri) <= 500),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger athlete_profiles_set_updated_at
  before update on public.athlete_profiles
  for each row execute function public.set_updated_at();

-- Add the supporter capability to profiles created after this migration. The
-- existing profile trigger is intentionally replaced after the role table is
-- present so future Web3 users receive the capability atomically.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  profile_id uuid := new.id;
begin
  insert into public.profiles (id, wallet)
  values (profile_id, new.raw_user_meta_data -> 'custom_claims' ->> 'address')
  on conflict (id) do nothing;
  insert into public.profile_roles (profile_id, role)
  values (profile_id, 'supporter')
  on conflict do nothing;
  return new;
end;
$$;

-- Existing local users are repaired idempotently.
insert into public.profile_roles (profile_id, role)
select id, 'supporter' from public.profiles
on conflict do nothing;

-- ---------------------------------------------------------------------------
-- Plans and campaign configuration
-- ---------------------------------------------------------------------------
create table public.subscription_plans (
  id uuid primary key default gen_random_uuid(),
  athlete_profile_id uuid not null references public.athlete_profiles(id) on delete restrict,
  unit_price_atomic bigint not null check (unit_price_atomic > 0),
  benefits text not null check (char_length(benefits) between 1 and 4000),
  status text not null default 'draft' check (status in ('draft', 'published', 'archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index subscription_plans_one_open_per_athlete
  on public.subscription_plans (athlete_profile_id)
  where status in ('draft', 'published');

create trigger subscription_plans_set_updated_at
  before update on public.subscription_plans
  for each row execute function public.set_updated_at();

create table public.campaigns (
  id uuid primary key default gen_random_uuid(),
  athlete_profile_id uuid not null references public.athlete_profiles(id) on delete restrict,
  plan_id uuid not null references public.subscription_plans(id) on delete restrict,
  title text not null check (char_length(title) between 1 and 160),
  description text not null check (char_length(description) between 1 and 10000),
  unit_price_atomic bigint not null check (unit_price_atomic > 0),
  minimum_success_threshold_atomic bigint not null check (minimum_success_threshold_atomic > 0),
  main_goal_atomic bigint,
  start_at timestamptz not null,
  end_at timestamptz not null,
  metadata_uri text check (metadata_uri is null or char_length(metadata_uri) <= 500),
  metadata_hash bytea,
  status text not null default 'draft'
    check (status in ('draft', 'scheduled', 'active', 'funded', 'successful', 'unsuccessful', 'cancelled')),
  campaign_pda text unique,
  escrow_token_account text unique,
  chain_signature text unique,
  nonce bytea unique,
  publish_snapshot jsonb,
  raised_amount_atomic bigint not null default 0 check (raised_amount_atomic >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_at > start_at),
  check (main_goal_atomic is null or main_goal_atomic >= minimum_success_threshold_atomic)
);

create index campaigns_public_listing_idx
  on public.campaigns (status, start_at, end_at desc, id desc);
create index campaigns_athlete_idx on public.campaigns (athlete_profile_id, created_at desc);

create trigger campaigns_set_updated_at
  before update on public.campaigns
  for each row execute function public.set_updated_at();

create table public.campaign_stretch_goals (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  position smallint not null check (position between 0 and 7),
  amount_atomic bigint not null check (amount_atomic > 0),
  benefit text not null check (char_length(benefit) between 1 and 2000),
  created_at timestamptz not null default now(),
  unique (campaign_id, position),
  unique (campaign_id, amount_atomic)
);

create table public.campaign_reward_tiers (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  position smallint not null check (position between 0 and 31),
  required_units bigint not null check (required_units > 0),
  benefit text not null check (char_length(benefit) between 1 and 2000),
  is_cumulative boolean not null default true,
  max_supply bigint check (max_supply is null or max_supply > 0),
  max_per_supporter bigint check (max_per_supporter is null or max_per_supporter > 0),
  uri text check (uri is null or char_length(uri) <= 500),
  created_at timestamptz not null default now(),
  unique (campaign_id, position),
  unique (campaign_id, required_units),
  check (max_per_supporter is null or max_supply is null or max_per_supporter <= max_supply)
);

create table public.campaign_publish_intents (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null unique references public.campaigns(id) on delete cascade,
  campaign_pda text not null unique,
  nonce bytea not null unique,
  snapshot_hash bytea not null,
  unsigned_transaction text not null,
  blockhash text not null,
  last_valid_block_height bigint not null,
  simulation_logs jsonb not null default '[]'::jsonb,
  confirmation_signature text unique,
  confirmed_at timestamptz,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Contributions, subscriptions, and settlement projections
-- ---------------------------------------------------------------------------
create table public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  supporter_profile_id uuid not null references public.profiles(id) on delete restrict,
  athlete_profile_id uuid not null references public.athlete_profiles(id) on delete restrict,
  campaign_id uuid not null references public.campaigns(id) on delete restrict,
  active_units bigint not null default 0 check (active_units >= 0),
  active_until timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (supporter_profile_id, athlete_profile_id, campaign_id)
);

create trigger subscriptions_set_updated_at
  before update on public.subscriptions
  for each row execute function public.set_updated_at();

create table public.contributions (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete restrict,
  supporter_profile_id uuid not null references public.profiles(id) on delete restrict,
  transaction_signature text not null unique,
  purchased_units bigint not null check (purchased_units > 0),
  contributed_amount_atomic bigint not null check (contributed_amount_atomic > 0),
  immediate_units bigint not null default 0 check (immediate_units >= 0),
  pending_units bigint not null default 0 check (pending_units >= 0),
  status text not null default 'pending'
    check (status in ('pending', 'confirmed', 'refunded', 'reversed')),
  base_points_confirmed bigint not null default 0 check (base_points_confirmed >= 0),
  base_points_pending bigint not null default 0 check (base_points_pending >= 0),
  success_bonus_points bigint not null default 0 check (success_bonus_points >= 0),
  success_bonus_awarded boolean not null default false,
  highest_reward_tier_id uuid references public.campaign_reward_tiers(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (campaign_id, supporter_profile_id, transaction_signature)
);

create index contributions_campaign_idx on public.contributions (campaign_id, created_at desc);
create index contributions_supporter_idx on public.contributions (supporter_profile_id, created_at desc);

create trigger contributions_set_updated_at
  before update on public.contributions
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Support Points and rewards
-- ---------------------------------------------------------------------------
create table public.support_point_accounts (
  profile_id uuid primary key references public.profiles(id) on delete cascade,
  available_points bigint not null default 0 check (available_points >= 0),
  pending_points bigint not null default 0 check (pending_points >= 0),
  updated_at timestamptz not null default now()
);

create table public.support_point_ledger (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete restrict,
  operation_type text not null
    check (operation_type in ('earned', 'success_bonus', 'redeemed', 'refunded', 'revoked', 'pending', 'confirmed')),
  delta_points bigint not null check (delta_points <> 0),
  available_balance_after bigint not null check (available_balance_after >= 0),
  pending_balance_after bigint not null check (pending_balance_after >= 0),
  campaign_id uuid references public.campaigns(id) on delete restrict,
  contribution_id uuid references public.contributions(id) on delete restrict,
  reward_order_id uuid,
  source_key text not null unique,
  transaction_reference text,
  created_at timestamptz not null default now()
);

create table public.campaign_reward_entitlements (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete restrict,
  contribution_id uuid not null references public.contributions(id) on delete restrict,
  reward_tier_id uuid references public.campaign_reward_tiers(id) on delete restrict,
  benefit text not null,
  fulfillment_type text not null default 'digital'
    check (fulfillment_type in ('digital', 'physical', 'session')),
  status text not null default 'locked'
    check (status in ('locked', 'unlocked', 'in_progress', 'fulfilled', 'cancelled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.platform_cosmetic_items (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 1 and 120),
  description text not null check (char_length(description) between 1 and 2000),
  support_points_price bigint not null check (support_points_price > 0),
  metadata_uri text,
  available_quantity bigint check (available_quantity is null or available_quantity >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.supporter_cosmetics (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  cosmetic_item_id uuid not null references public.platform_cosmetic_items(id) on delete restrict,
  acquired_at timestamptz not null default now(),
  unique (profile_id, cosmetic_item_id)
);

create table public.athlete_reward_offers (
  id uuid primary key default gen_random_uuid(),
  athlete_profile_id uuid not null references public.athlete_profiles(id) on delete restrict,
  reward_name text not null check (char_length(reward_name) between 1 and 160),
  description text not null check (char_length(description) between 1 and 4000),
  support_points_price bigint not null check (support_points_price > 0),
  available_quantity bigint check (available_quantity is null or available_quantity >= 0),
  maximum_per_user bigint check (maximum_per_user is null or maximum_per_user > 0),
  availability_start timestamptz,
  availability_end timestamptz,
  fulfillment_type text not null default 'digital'
    check (fulfillment_type in ('digital', 'physical', 'session')),
  metadata_uri text,
  status text not null default 'active' check (status in ('draft', 'active', 'archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (availability_end is null or availability_start is null or availability_end > availability_start)
);

create table public.athlete_reward_orders (
  id uuid primary key default gen_random_uuid(),
  offer_id uuid not null references public.athlete_reward_offers(id) on delete restrict,
  supporter_profile_id uuid not null references public.profiles(id) on delete restrict,
  points_spent bigint not null check (points_spent > 0),
  status text not null default 'reserved'
    check (status in ('reserved', 'awaiting_details', 'in_progress', 'shipped', 'scheduled', 'fulfilled', 'refunded', 'cancelled')),
  fulfillment_details jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.support_point_ledger
  add constraint support_point_ledger_order_fk
  foreign key (reward_order_id) references public.athlete_reward_orders(id) on delete restrict;

-- ---------------------------------------------------------------------------
-- Payout and vesting projections
-- ---------------------------------------------------------------------------
create table public.payout_vesting_entries (
  id uuid primary key default gen_random_uuid(),
  contribution_id uuid references public.contributions(id) on delete restrict,
  athlete_profile_id uuid not null references public.athlete_profiles(id) on delete restrict,
  amount_atomic bigint not null check (amount_atomic > 0),
  release_at timestamptz not null,
  kind text not null check (kind in ('standard_monthly', 'campaign_release')),
  status text not null default 'scheduled'
    check (status in ('scheduled', 'released', 'refunded', 'failed')),
  transaction_signature text unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  released_at timestamptz
);

create trigger support_point_accounts_set_updated_at
  before update on public.support_point_accounts
  for each row execute function public.set_updated_at();
create trigger campaign_reward_entitlements_set_updated_at
  before update on public.campaign_reward_entitlements
  for each row execute function public.set_updated_at();
create trigger platform_cosmetic_items_set_updated_at
  before update on public.platform_cosmetic_items
  for each row execute function public.set_updated_at();
create trigger athlete_reward_offers_set_updated_at
  before update on public.athlete_reward_offers
  for each row execute function public.set_updated_at();
create trigger athlete_reward_orders_set_updated_at
  before update on public.athlete_reward_orders
  for each row execute function public.set_updated_at();
create trigger payout_vesting_entries_set_updated_at
  before update on public.payout_vesting_entries
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS: service role writes projections; users read/update owned profile data,
-- and public users read only confirmed campaign content.
-- ---------------------------------------------------------------------------
alter table public.profile_roles enable row level security;
alter table public.athlete_profiles enable row level security;
alter table public.subscription_plans enable row level security;
alter table public.campaigns enable row level security;
alter table public.campaign_stretch_goals enable row level security;
alter table public.campaign_reward_tiers enable row level security;
alter table public.subscriptions enable row level security;
alter table public.contributions enable row level security;
alter table public.support_point_accounts enable row level security;
alter table public.support_point_ledger enable row level security;
alter table public.campaign_reward_entitlements enable row level security;
alter table public.platform_cosmetic_items enable row level security;
alter table public.supporter_cosmetics enable row level security;
alter table public.athlete_reward_offers enable row level security;
alter table public.athlete_reward_orders enable row level security;
alter table public.payout_vesting_entries enable row level security;

create policy profile_roles_own_read on public.profile_roles
  for select to authenticated using (profile_id = auth.uid());
create policy athlete_profiles_public_read on public.athlete_profiles
  for select to anon, authenticated using (true);
create policy subscription_plans_public_read on public.subscription_plans
  for select to anon, authenticated using (status = 'published');
create policy campaigns_public_read on public.campaigns
  for select to anon, authenticated using (status in ('scheduled', 'active', 'funded', 'successful', 'unsuccessful'));
create policy campaigns_owner_read on public.campaigns
  for select to authenticated using (
    athlete_profile_id in (select id from public.athlete_profiles where profile_id = auth.uid())
  );
create policy subscriptions_own_read on public.subscriptions
  for select to authenticated using (supporter_profile_id = auth.uid());
create policy contributions_own_read on public.contributions
  for select to authenticated using (supporter_profile_id = auth.uid());
create policy support_points_own_read on public.support_point_accounts
  for select to authenticated using (profile_id = auth.uid());
create policy support_point_ledger_own_read on public.support_point_ledger
  for select to authenticated using (profile_id = auth.uid());
create policy platform_cosmetics_public_read on public.platform_cosmetic_items
  for select to anon, authenticated using (true);
create policy athlete_offers_public_read on public.athlete_reward_offers
  for select to anon, authenticated using (status = 'active');
create policy reward_orders_own_read on public.athlete_reward_orders
  for select to authenticated using (supporter_profile_id = auth.uid());

-- ---------------------------------------------------------------------------
-- Campaign event projection
-- ---------------------------------------------------------------------------
create table public.campaign_chain_events (
  id                  bigint generated always as identity primary key,
  signature           text not null references public.indexed_transactions(signature)
                      on delete cascade,
  event_index         smallint not null,
  event_type          text not null check (event_type in ('campaign_initialized', 'subscription_purchased', 'campaign_settled')),
  campaign            text not null,
  supporter           text,
  amount_atomic       bigint not null default 0,
  purchased_units     bigint not null default 0,
  immediate_units     bigint not null default 0,
  pending_units       bigint not null default 0,
  successful          boolean,
  slot                bigint not null,
  block_time          timestamptz,
  created_at          timestamptz not null default now(),
  unique (signature, event_index)
);

create index campaign_chain_events_campaign_idx
  on public.campaign_chain_events (campaign, slot desc);

alter table public.campaign_chain_events enable row level security;

create policy campaign_chain_events_public_read
  on public.campaign_chain_events for select
  to anon, authenticated using (true);
