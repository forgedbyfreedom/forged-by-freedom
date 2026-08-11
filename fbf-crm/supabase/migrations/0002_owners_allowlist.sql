-- ─────────────────────────────────────────────────────────────
-- FBF CRM — owner allowlist (replaces hardcoded-email RLS helper)
--
-- The original is_crm_owner() in 0001 compared auth.jwt() ->> 'email' to a
-- hardcoded string. That was brittle:
--   - SECURITY DEFINER on the helper interacted poorly with auth.jwt()
--     under @supabase/ssr cookie-based sessions and silently returned false.
--   - Hardcoding an email means re-creating the user (or adding another
--     owner) requires editing SQL.
--
-- New design: an explicit allowlist table keyed by auth user_id. Adding an
-- owner is `insert into crm_owners (user_id) values ('<uuid>')`. The helper
-- becomes a plain STABLE sql function over auth.uid().
-- ─────────────────────────────────────────────────────────────

create table if not exists public.crm_owners (
  user_id uuid primary key references auth.users(id) on delete cascade,
  added_at timestamptz not null default now(),
  note text
);

insert into public.crm_owners (user_id, note)
select id, 'Bryan + Wendy shared owner account'
from auth.users
where lower(email) = 'forgedbyfreedom@gmail.com'
on conflict (user_id) do nothing;

create or replace function public.is_crm_owner() returns boolean
  language sql stable as $$
  select exists (
    select 1 from public.crm_owners o where o.user_id = auth.uid()
  )
$$;

alter table public.crm_owners enable row level security;
drop policy if exists crm_owners_self_read on public.crm_owners;
create policy crm_owners_self_read on public.crm_owners
  for select to authenticated using (user_id = auth.uid());

do $$
declare t text;
begin
  foreach t in array array['crm_clients','crm_products','crm_inventory_lots','crm_orders','crm_order_items','crm_expenses']
  loop
    execute format('drop policy if exists %1$s_owner_all on public.%1$s;', t);
    execute format(
      'create policy %1$s_owner_all on public.%1$s
       for all to authenticated
       using (public.is_crm_owner()) with check (public.is_crm_owner());',
      t
    );
  end loop;
end $$;
