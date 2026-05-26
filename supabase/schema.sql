create extension if not exists pgcrypto;

create table if not exists scenarios (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  description text,
  config jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists runs (
  id uuid primary key default gen_random_uuid(),
  scenario_id uuid references scenarios(id) on delete set null,
  status text not null check (status in ('success', 'failed')),
  metrics jsonb not null default '{}'::jsonb,
  result_table jsonb not null default '[]'::jsonb,
  report_text text,
  error_message text,
  created_at timestamptz not null default now()
);

create index if not exists runs_created_at_idx on runs (created_at desc);
create index if not exists runs_scenario_id_idx on runs (scenario_id);

alter table scenarios enable row level security;
alter table runs enable row level security;

drop policy if exists "allow demo insert scenarios" on scenarios;
drop policy if exists "allow demo read scenarios" on scenarios;
drop policy if exists "allow demo insert runs" on runs;
drop policy if exists "allow demo read runs" on runs;

create policy "allow demo insert scenarios"
on scenarios for insert
to anon
with check (true);

create policy "allow demo read scenarios"
on scenarios for select
to anon
using (true);

create policy "allow demo insert runs"
on runs for insert
to anon
with check (true);

create policy "allow demo read runs"
on runs for select
to anon
using (true);
