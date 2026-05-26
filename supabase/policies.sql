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
