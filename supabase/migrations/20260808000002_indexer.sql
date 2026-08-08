-- Off-chain read model derived from on-chain state.
--
-- Rule: nothing in here is authoritative. The Anchor program owns truth for
-- anything involving value. These tables exist so the app can do fast list
-- views, historical queries and analytics that RPC cannot serve cheaply.
-- Every row must be reconstructible by replaying the chain.

-- ---------------------------------------------------------------------------
-- Raw ingest ledger. One row per transaction we have seen, whatever the source
-- (Helius webhook or the reconciliation worker). Deliberately dumb: store the
-- payload, mark it processed later. This makes ingestion idempotent and lets us
-- re-derive projections without re-fetching from RPC.
-- ---------------------------------------------------------------------------
create type public.ingest_status as enum ('pending', 'processed', 'failed', 'skipped');

create table public.indexed_transactions (
  signature    text primary key,
  slot         bigint      not null,
  block_time   timestamptz,
  program_id   text        not null,
  source       text        not null default 'webhook',
  status       public.ingest_status not null default 'pending',
  error        text,
  raw          jsonb       not null,
  received_at  timestamptz not null default now(),
  processed_at timestamptz
);

create index indexed_transactions_slot_idx
  on public.indexed_transactions (slot desc);

-- Partial index: the worker only ever scans for work still to do.
create index indexed_transactions_pending_idx
  on public.indexed_transactions (received_at)
  where status = 'pending';

-- ---------------------------------------------------------------------------
-- Example projection, derived from the counter program. Replace this with your
-- real domain tables — it is here to show the shape.
-- ---------------------------------------------------------------------------
create table public.counter_events (
  id          bigint generated always as identity primary key,
  signature   text        not null references public.indexed_transactions (signature) on delete cascade,
  counter     text        not null,
  authority   text        not null,
  count       bigint      not null,
  slot        bigint      not null,
  block_time  timestamptz,
  created_at  timestamptz not null default now(),

  -- One projection row per (transaction, account). Makes replay idempotent.
  unique (signature, counter)
);

create index counter_events_counter_idx on public.counter_events (counter, slot desc);
create index counter_events_authority_idx on public.counter_events (authority, slot desc);

-- ---------------------------------------------------------------------------
-- Reconciliation cursor. The worker walks backwards from the newest signature
-- it has not seen, so a dropped webhook eventually gets picked up.
-- ---------------------------------------------------------------------------
create table public.indexer_cursors (
  program_id          text primary key,
  last_signature      text,
  last_slot           bigint,
  last_run_at         timestamptz,
  backfill_complete   boolean not null default false
);

-- ---------------------------------------------------------------------------
-- RLS
--
-- indexed_transactions / indexer_cursors: service-role only. RLS is enabled
-- with zero policies, which denies every anon and authenticated request.
-- counter_events: world-readable. It is public chain data; hiding it would be
-- theatre. Writes are service-role only.
-- ---------------------------------------------------------------------------
alter table public.indexed_transactions enable row level security;
alter table public.indexer_cursors      enable row level security;
alter table public.counter_events       enable row level security;

create policy counter_events_public_read
  on public.counter_events for select
  to anon, authenticated
  using (true);
