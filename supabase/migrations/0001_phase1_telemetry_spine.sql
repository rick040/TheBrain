-- Phase 1 telemetry spine, per docs/02-data-structure-and-flow.md §6.
-- Already applied to the live "TheBrain" Supabase project (oavyzzvvlhgyxkagzmza)
-- via the Supabase MCP connector. Kept here so the schema is reproducible
-- as code (docs/03-engineering-build-spec.md §13) and portable to the
-- self-hosted NAS Postgres later (docs/00-PLAN.md).

create extension if not exists vector;

create table if not exists events (
  id          bigint generated always as identity primary key,
  user_id     uuid not null default auth.uid(),
  ts          timestamptz not null,
  kind        text not null,     -- steps|sleep|location|hr|time_entry|habit_tick|lift|txn
  value       numeric,
  meta        jsonb,
  source      text,
  created_at  timestamptz not null default now()
);
create index if not exists idx_events_kind_ts on events(kind, ts);
create index if not exists idx_events_user on events(user_id);

create table if not exists insights (
  id          bigint generated always as identity primary key,
  user_id     uuid not null default auth.uid(),
  ts          timestamptz,
  about       text,
  statement   text,
  confidence  numeric,
  evidence    jsonb,
  wrote_to    text,
  created_at  timestamptz not null default now()
);
create index if not exists idx_insights_user on insights(user_id);

create table if not exists embeddings (
  ref         text primary key,
  user_id     uuid not null default auth.uid(),
  vec         vector(768),
  kind        text,
  updated     timestamptz not null default now()
);
create index if not exists idx_embeddings_user on embeddings(user_id);
create index if not exists idx_embeddings_vec on embeddings using ivfflat (vec vector_cosine_ops);

-- RLS on from day one (docs/02-data-structure-and-flow.md §6). The
-- backend (app/common/db.py) connects with the service role key and
-- bypasses this, tagging rows with a fixed THEBRAIN_USER_ID — RLS is
-- defense-in-depth for if these tables are ever queried through a
-- client/anon key.
alter table events enable row level security;
alter table insights enable row level security;
alter table embeddings enable row level security;

drop policy if exists "owner_all_events" on events;
create policy "owner_all_events" on events
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "owner_all_insights" on insights;
create policy "owner_all_insights" on insights
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "owner_all_embeddings" on embeddings;
create policy "owner_all_embeddings" on embeddings
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
