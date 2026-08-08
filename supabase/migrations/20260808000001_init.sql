-- Core identity tables.
--
-- Auth model: wallets sign in through Supabase's native Sign-In-With-Solana
-- (`[auth.web3.solana]` in config.toml). Supabase creates the row in auth.users;
-- this migration mirrors it into public.profiles so we have a place to hang
-- application data without touching the auth schema.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- updated_at helper
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- profiles
-- ---------------------------------------------------------------------------
create table public.profiles (
  id           uuid primary key references auth.users (id) on delete cascade,
  wallet       text unique,
  display_name text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),

  -- Base58 Solana addresses are 32-44 chars and exclude 0, O, I, l.
  constraint profiles_wallet_format
    check (wallet is null or wallet ~ '^[1-9A-HJ-NP-Za-km-z]{32,44}$')
);

create index profiles_wallet_idx on public.profiles (wallet);

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Wallet extraction from the JWT
--
-- Verified against a real Sign-In-With-Solana against GoTrue. The claim shape is:
--
--   user_metadata: {
--     sub: "web3:solana:<address>",
--     custom_claims: { address: "<address>", chain: "solana", domain, network, statement },
--     email_verified: false, phone_verified: false
--   }
--
-- So the address is at user_metadata.custom_claims.address, and nowhere else in
-- bare form. Note that user_metadata.sub is NOT the address -- it is prefixed
-- with "web3:solana:", and using it here would store a value that fails the
-- base58 CHECK constraint on profiles.wallet.
-- ---------------------------------------------------------------------------
create or replace function public.current_wallet()
returns text
language sql
stable
as $$
  select auth.jwt() -> 'user_metadata' -> 'custom_claims' ->> 'address';
$$;

-- ---------------------------------------------------------------------------
-- Auto-provision a profile whenever Supabase Auth creates a user.
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  -- Same shape as current_wallet() reads out of the JWT: auth.users stores the
  -- provider payload in raw_user_meta_data, so the address is one level down
  -- inside custom_claims.
  insert into public.profiles (id, wallet)
  values (new.id, new.raw_user_meta_data -> 'custom_claims' ->> 'address')
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- RLS: a user may only read and edit their own profile.
-- The service role (used by FastAPI) bypasses RLS entirely.
-- ---------------------------------------------------------------------------
alter table public.profiles enable row level security;

create policy profiles_select_own
  on public.profiles for select
  to authenticated
  using (id = auth.uid());

create policy profiles_update_own
  on public.profiles for update
  to authenticated
  using (id = auth.uid())
  with check (id = auth.uid());

-- No insert/delete policy: profiles are created by the trigger above and
-- removed by the cascade from auth.users.
