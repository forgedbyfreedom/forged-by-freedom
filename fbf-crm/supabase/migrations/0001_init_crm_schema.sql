-- ─────────────────────────────────────────────────────────────
-- FBF CRM — initial schema
-- Tables: clients, products, inventory_lots, orders, order_items, expenses
-- Auth model: single shared owner email (both Bryan and Wendy use it).
-- RLS: every CRM row is gated on auth.email() = the owner email.
-- Money: stored as integer cents to avoid float drift.
-- ─────────────────────────────────────────────────────────────

create extension if not exists "pgcrypto";

-- ─── Helper: is current user the owner? ──────────────────────
create or replace function public.is_crm_owner() returns boolean
  language sql stable security definer set search_path = public as $$
  select coalesce(lower((auth.jwt() ->> 'email')), '') = 'forgedbyfreedom@gmail.com'
$$;

-- ─── Clients ─────────────────────────────────────────────────
create table if not exists public.crm_clients (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email text,
  phone text,
  address_line1 text,
  address_line2 text,
  city text,
  state text,
  postal_code text,
  country text default 'US',
  notes text,
  last_contact_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists crm_clients_email_idx on public.crm_clients (lower(email));
create index if not exists crm_clients_last_contact_idx on public.crm_clients (last_contact_at desc nulls last);

-- ─── Products ────────────────────────────────────────────────
create table if not exists public.crm_products (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  sku text unique,
  category text,             -- 'peptide' | 'research_chemical' | other
  unit text not null default 'vial',  -- vial / bottle / mg / unit
  sell_price_cents integer not null default 0,
  current_cost_cents integer not null default 0,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ─── Inventory lots ──────────────────────────────────────────
-- One row per batch/shipment. on_hand is reduced when items are sold;
-- on_order is reduced (and on_hand increased) when a shipment is received.
create table if not exists public.crm_inventory_lots (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references public.crm_products(id) on delete restrict,
  lot_number text,
  supplier text,
  unit_cost_cents integer not null default 0,
  qty_on_hand integer not null default 0,
  qty_on_order integer not null default 0,
  tracking_number text,
  carrier text,
  status text not null default 'ordered',  -- ordered | in_transit | received | depleted
  ordered_at timestamptz,
  received_at timestamptz,
  expires_at date,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists crm_inventory_lots_product_idx on public.crm_inventory_lots (product_id);
create index if not exists crm_inventory_lots_status_idx on public.crm_inventory_lots (status);

-- ─── Orders ──────────────────────────────────────────────────
create table if not exists public.crm_orders (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references public.crm_clients(id) on delete set null,
  ordered_at timestamptz not null default now(),
  source text not null default 'manual',   -- manual | stripe | other
  external_id text,                        -- e.g. Stripe payment intent
  subtotal_cents integer not null default 0,
  shipping_cents integer not null default 0,
  tax_cents integer not null default 0,
  total_cents integer not null default 0,
  status text not null default 'paid',     -- pending | paid | shipped | refunded
  tracking_number text,
  carrier text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists crm_orders_external_id_uidx
  on public.crm_orders (source, external_id) where external_id is not null;
create index if not exists crm_orders_client_idx on public.crm_orders (client_id);
create index if not exists crm_orders_ordered_at_idx on public.crm_orders (ordered_at desc);

create table if not exists public.crm_order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.crm_orders(id) on delete cascade,
  product_id uuid not null references public.crm_products(id) on delete restrict,
  lot_id uuid references public.crm_inventory_lots(id) on delete set null,
  qty integer not null check (qty > 0),
  unit_price_cents integer not null default 0,
  unit_cost_cents integer not null default 0,    -- snapshot for COGS history
  line_total_cents integer not null default 0
);
create index if not exists crm_order_items_order_idx on public.crm_order_items (order_id);
create index if not exists crm_order_items_product_idx on public.crm_order_items (product_id);

-- ─── Expenses ────────────────────────────────────────────────
create table if not exists public.crm_expenses (
  id uuid primary key default gen_random_uuid(),
  incurred_at date not null default current_date,
  category text,                            -- supplies, software, fees, shipping, etc.
  vendor text,
  amount_cents integer not null,
  note text,
  created_at timestamptz not null default now()
);
create index if not exists crm_expenses_incurred_at_idx on public.crm_expenses (incurred_at desc);

-- ─── updated_at triggers ─────────────────────────────────────
create or replace function public.crm_set_updated_at() returns trigger
  language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

do $$
declare t text;
begin
  foreach t in array array['crm_clients','crm_products','crm_inventory_lots','crm_orders']
  loop
    execute format(
      'drop trigger if exists %1$s_set_updated_at on public.%1$s;
       create trigger %1$s_set_updated_at before update on public.%1$s
       for each row execute function public.crm_set_updated_at();',
      t
    );
  end loop;
end $$;

-- ─── Per-client rollup view (consumed by clients page) ───────
create or replace view public.crm_clients_with_stats as
  select
    c.*,
    coalesce(stats.order_count, 0) as order_count,
    coalesce(stats.lifetime_revenue_cents, 0) as lifetime_revenue_cents,
    stats.largest_order_cents,
    stats.last_order_at,
    case when coalesce(stats.order_count, 0) > 0
      then stats.lifetime_revenue_cents / stats.order_count
      else 0 end as avg_order_cents
  from public.crm_clients c
  left join lateral (
    select
      count(*) as order_count,
      sum(total_cents) as lifetime_revenue_cents,
      max(total_cents) as largest_order_cents,
      max(ordered_at) as last_order_at
    from public.crm_orders o
    where o.client_id = c.id and o.status <> 'refunded'
  ) stats on true;

-- ─── Row-Level Security: only the owner email may read/write ─
alter table public.crm_clients         enable row level security;
alter table public.crm_products        enable row level security;
alter table public.crm_inventory_lots  enable row level security;
alter table public.crm_orders          enable row level security;
alter table public.crm_order_items     enable row level security;
alter table public.crm_expenses        enable row level security;

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
