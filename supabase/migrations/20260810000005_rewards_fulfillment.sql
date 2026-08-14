-- Reward entitlements, the platform cosmetic catalog, and fulfillment audit.
-- An entitlement is derived state: a row exists only once a supporter's
-- confirmed units have unlocked the tier, so pending units can never grant a
-- reward. Entitlements are keyed per supporter rather than per contribution,
-- which makes the grant idempotent across repeat purchases and lets a supporter
-- read their own rows. Fulfillment transitions append to an immutable event log
-- so an operator can reconstruct who changed what, when, and against which
-- external reference.

-- ---------------------------------------------------------------------------
-- Reward tier grouping
-- ---------------------------------------------------------------------------
alter table public.campaign_reward_tiers
  add column reward_group text
    check (reward_group is null or char_length(reward_group) between 1 and 40);

comment on column public.campaign_reward_tiers.reward_group is
  'Non-cumulative tiers compete within a group; null is the shared default group.';

-- ---------------------------------------------------------------------------
-- Entitlements are granted per supporter, not per contribution
-- ---------------------------------------------------------------------------
alter table public.campaign_reward_entitlements
  add column supporter_profile_id uuid references public.profiles(id) on delete restrict;

-- Existing rows, if any, derive their supporter from the unlocking contribution.
update public.campaign_reward_entitlements e
   set supporter_profile_id = c.supporter_profile_id
  from public.contributions c
 where c.id = e.contribution_id and e.supporter_profile_id is null;

-- reward_tier_id must be not null: null values are distinct in a unique index,
-- which would silently defeat the on-conflict grant in the projector.
alter table public.campaign_reward_entitlements
  alter column supporter_profile_id set not null,
  alter column reward_tier_id set not null;

alter table public.campaign_reward_entitlements
  add constraint campaign_reward_entitlements_unique_grant
  unique (campaign_id, supporter_profile_id, reward_tier_id);

create index campaign_reward_entitlements_supporter_idx
  on public.campaign_reward_entitlements (supporter_profile_id, created_at desc, id desc);
create index campaign_reward_entitlements_campaign_idx
  on public.campaign_reward_entitlements (campaign_id, created_at desc, id desc);

-- The projector counts live grants per tier to enforce max_supply.
create index campaign_reward_entitlements_tier_idx
  on public.campaign_reward_entitlements (reward_tier_id)
  where status <> 'cancelled';

-- ---------------------------------------------------------------------------
-- Fulfillment audit log
-- ---------------------------------------------------------------------------
-- Append-only, so no updated_at and no trigger. A null from_status marks row
-- creation; a null actor_profile_id marks a system transition.
create table public.reward_fulfillment_events (
  id uuid primary key default gen_random_uuid(),
  subject_type text not null check (subject_type in ('entitlement', 'order')),
  entitlement_id uuid references public.campaign_reward_entitlements(id) on delete cascade,
  order_id uuid references public.athlete_reward_orders(id) on delete cascade,
  from_status text,
  to_status text not null,
  actor_profile_id uuid references public.profiles(id) on delete set null,
  fulfillment_reference text
    check (fulfillment_reference is null or char_length(fulfillment_reference) <= 200),
  note text check (note is null or char_length(note) <= 1000),
  created_at timestamptz not null default now(),
  check (
    (subject_type = 'entitlement' and entitlement_id is not null and order_id is null)
    or (subject_type = 'order' and order_id is not null and entitlement_id is null)
  ),
  check (
    (subject_type = 'entitlement'
      and (from_status is null
           or from_status in ('locked', 'unlocked', 'in_progress', 'fulfilled', 'cancelled'))
      and to_status in ('locked', 'unlocked', 'in_progress', 'fulfilled', 'cancelled'))
    or (subject_type = 'order'
      and (from_status is null
           or from_status in ('reserved', 'awaiting_details', 'in_progress', 'shipped', 'scheduled', 'fulfilled', 'refunded', 'cancelled'))
      and to_status in ('reserved', 'awaiting_details', 'in_progress', 'shipped', 'scheduled', 'fulfilled', 'refunded', 'cancelled'))
  )
);

create index reward_fulfillment_events_entitlement_idx
  on public.reward_fulfillment_events (entitlement_id, created_at desc)
  where entitlement_id is not null;
create index reward_fulfillment_events_order_idx
  on public.reward_fulfillment_events (order_id, created_at desc)
  where order_id is not null;

-- ---------------------------------------------------------------------------
-- Reward order replay safety and read paths
-- ---------------------------------------------------------------------------
alter table public.athlete_reward_orders
  add column idempotency_key text
    check (idempotency_key is null or char_length(idempotency_key) between 8 and 100);

-- Partial, because a null key means "no replay guard requested" and must not
-- collide with any other order.
create unique index athlete_reward_orders_idempotency_idx
  on public.athlete_reward_orders (offer_id, supporter_profile_id, idempotency_key)
  where idempotency_key is not null;

create index athlete_reward_orders_supporter_idx
  on public.athlete_reward_orders (supporter_profile_id, created_at desc, id desc);
create index athlete_reward_orders_offer_idx
  on public.athlete_reward_orders (offer_id, created_at desc, id desc);

create index athlete_reward_offers_athlete_idx
  on public.athlete_reward_offers (athlete_profile_id, created_at desc, id desc);

create index support_point_ledger_profile_idx
  on public.support_point_ledger (profile_id, created_at desc, id desc);

create index supporter_cosmetics_profile_idx
  on public.supporter_cosmetics (profile_id, acquired_at desc, id desc);

-- ---------------------------------------------------------------------------
-- Cosmetic catalog identity and a starter set
-- ---------------------------------------------------------------------------
-- The unique constraint must precede the insert so on conflict has a target.
alter table public.platform_cosmetic_items
  add constraint platform_cosmetic_items_name_key unique (name);

insert into public.platform_cosmetic_items
  (name, description, support_points_price, available_quantity)
values
  ('Supporter Badge', 'A profile badge shown next to your name across Backr.', 100, null),
  ('Campaign Confetti', 'A celebration animation on every campaign you have backed.', 250, null),
  ('Season One Emote Pack', 'A set of emotes usable on athlete campaign pages.', 300, 2500),
  ('Founding Backer Frame', 'An avatar frame reserved for early platform supporters.', 500, 1000),
  ('Gold Nameplate', 'A gold nameplate beside your name on supporter lists.', 1000, null),
  ('Legacy Supporter Mark', 'A permanent mark on your public profile.', 2500, 250)
on conflict (name) do nothing;

-- ---------------------------------------------------------------------------
-- RLS. The API holds a service-role credential and bypasses every policy here;
-- these govern the browser's direct supabase-js path only.
-- ---------------------------------------------------------------------------
-- Both of these are deliberately policy-free: publish intents carry unsigned
-- transactions and nonces, and fulfillment events carry operator notes. Neither
-- should ever be reachable from a browser session.
alter table public.campaign_publish_intents enable row level security;
alter table public.reward_fulfillment_events enable row level security;

create policy campaign_reward_entitlements_own_read on public.campaign_reward_entitlements
  for select to authenticated using (supporter_profile_id = auth.uid());
create policy supporter_cosmetics_own_read on public.supporter_cosmetics
  for select to authenticated using (profile_id = auth.uid());
create policy campaign_reward_tiers_public_read on public.campaign_reward_tiers
  for select to anon, authenticated using (
    campaign_id in (
      select id from public.campaigns
       where status in ('scheduled', 'active', 'funded', 'successful', 'unsuccessful')
    )
  );
create policy campaign_stretch_goals_public_read on public.campaign_stretch_goals
  for select to anon, authenticated using (
    campaign_id in (
      select id from public.campaigns
       where status in ('scheduled', 'active', 'funded', 'successful', 'unsuccessful')
    )
  );
