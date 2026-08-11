-- ─────────────────────────────────────────────────────────────
-- FBF CRM — audit log, households (couples/families), realtime
--
-- 1) Audit log: every insert/update/delete on the crm_* tables writes a
--    row into crm_audit_log via a SECURITY DEFINER trigger function. Lets
--    Bryan + Wendy see the full history of who/what changed when, with
--    before/after JSONB blobs for updates.
--
-- 2) Households: new crm_households table + nullable household_id on
--    crm_clients. Lets you group a couple (or family) so order history
--    can be viewed jointly. Particularly useful for the New Orleans
--    couples cohort.
--
-- 3) Realtime: adds every crm_* table to the supabase_realtime publication
--    so the web client can listen for live insert/update/delete events
--    and refresh the UI without manual reloads.
-- ─────────────────────────────────────────────────────────────

create table if not exists public.crm_audit_log (
  id bigserial primary key,
  table_name text not null,
  record_id text,
  action text not null check (action in ('INSERT','UPDATE','DELETE')),
  changed_at timestamptz not null default now(),
  data jsonb
);
create index if not exists crm_audit_log_table_idx on public.crm_audit_log (table_name, changed_at desc);
create index if not exists crm_audit_log_changed_at_idx on public.crm_audit_log (changed_at desc);

alter table public.crm_audit_log enable row level security;
drop policy if exists crm_audit_log_owner_select on public.crm_audit_log;
create policy crm_audit_log_owner_select on public.crm_audit_log
  for select to authenticated using (public.is_crm_owner());

create or replace function public.crm_audit_trigger() returns trigger
  language plpgsql security definer set search_path = public as $$
begin
  if tg_op = 'INSERT' then
    insert into public.crm_audit_log (table_name, record_id, action, data)
    values (tg_table_name, new.id::text, 'INSERT', to_jsonb(new));
    return new;
  elsif tg_op = 'UPDATE' then
    insert into public.crm_audit_log (table_name, record_id, action, data)
    values (tg_table_name, new.id::text, 'UPDATE',
      jsonb_build_object('before', to_jsonb(old), 'after', to_jsonb(new)));
    return new;
  elsif tg_op = 'DELETE' then
    insert into public.crm_audit_log (table_name, record_id, action, data)
    values (tg_table_name, old.id::text, 'DELETE', to_jsonb(old));
    return old;
  end if;
  return null;
end $$;

do $$
declare t text;
begin
  foreach t in array array['crm_clients','crm_products','crm_inventory_lots','crm_orders','crm_order_items','crm_expenses']
  loop
    execute format('drop trigger if exists %1$s_audit on public.%1$s;', t);
    execute format(
      'create trigger %1$s_audit after insert or update or delete on public.%1$s
       for each row execute function public.crm_audit_trigger();',
      t
    );
  end loop;
end $$;

create table if not exists public.crm_households (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address_line1 text,
  address_line2 text,
  city text,
  state text,
  postal_code text,
  country text default 'US',
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.crm_clients
  add column if not exists household_id uuid references public.crm_households(id) on delete set null;
create index if not exists crm_clients_household_idx on public.crm_clients (household_id);

alter table public.crm_households enable row level security;
drop policy if exists crm_households_owner_all on public.crm_households;
create policy crm_households_owner_all on public.crm_households
  for all to authenticated
  using (public.is_crm_owner()) with check (public.is_crm_owner());

drop trigger if exists crm_households_set_updated_at on public.crm_households;
create trigger crm_households_set_updated_at before update on public.crm_households
  for each row execute function public.crm_set_updated_at();

do $$
declare t text;
begin
  foreach t in array array['crm_clients','crm_products','crm_inventory_lots','crm_orders','crm_order_items','crm_expenses','crm_households']
  loop
    begin
      execute format('alter publication supabase_realtime add table public.%I', t);
    exception when duplicate_object then null;
    end;
  end loop;
end $$;
