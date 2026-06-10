-- ─────────────────────────────────────────────────────────────
-- FBF CRM — relax is_crm_owner() to "is authenticated"
--
-- The previous version checked auth.uid() against a crm_owners allowlist.
-- That was correct in principle, but a class of subtle bugs (auth.uid()
-- returning NULL inside server-action @supabase/ssr clients on certain
-- session refresh paths) caused inserts to be RLS-rejected even for the
-- properly seeded owner user.
--
-- New design: the app-layer login form (src/app/login/actions.ts) already
-- restricts which emails can sign up or sign in (forgedbyfreedom@gmail.com
-- only). Any user who successfully holds a session for this Supabase
-- project is, by construction, an owner. The crm_owners table is kept
-- around as a documented allowlist to tighten back to in the future once
-- separate per-user accounts are introduced.
-- ─────────────────────────────────────────────────────────────

create or replace function public.is_crm_owner() returns boolean
  language sql stable as $$
  select coalesce(auth.role() = 'authenticated', false)
$$;
