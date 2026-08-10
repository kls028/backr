-- Keep wallet submission separate from indexer verification. The API records a
-- submitted signature as pending; only verified chain data may update the
-- campaign read model.
alter table public.campaign_publish_intents
  add column confirmation_status text not null default 'pending'
    check (confirmation_status in ('pending', 'verified', 'rejected'));

alter table public.campaign_publish_intents
  add column confirmation_error text;

create index campaign_publish_intents_pending_idx
  on public.campaign_publish_intents (confirmation_status)
  where confirmation_status = 'pending';
