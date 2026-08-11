# FBF CRM

Internal admin app for Forged by Freedom — clients, inventory, orders, and P&L.

Stack: Next.js 15 (App Router, TypeScript), Tailwind, Supabase (Postgres + Auth + RLS).
Owners: Bryan and Wendy, sharing one login (`forgedbyfreedom@gmail.com`).

---

## First-time setup

### 1. Install dependencies

```bash
cd fbf-crm
npm install
```

### 2. Configure environment

Copy `.env.example` to `.env.local` and fill in `NEXT_PUBLIC_SUPABASE_ANON_KEY`
(get it from Supabase → Project Settings → API → `anon public` key).

The Supabase project is **FBF-Dashboard** (`sdrsoccfingecvlzrlym`).

### 3. Apply the database migration

Open the Supabase SQL Editor for the FBF-Dashboard project and run the contents
of `supabase/migrations/0001_init_crm_schema.sql`. This creates all `crm_*`
tables, the `crm_clients_with_stats` view, and Row-Level Security policies that
only allow the owner email to read/write.

### 4. Create the owner auth user

Start the dev server:

```bash
npm run dev
```

Visit http://localhost:3000 → you'll be redirected to `/login`. Click
"First time? Create the owner account", enter `forgedbyfreedom@gmail.com` and a
password. After that, both you and Wendy sign in with that one shared account.

If Supabase has email confirmations enabled, you'll need to confirm the email
first (check inbox) or disable email confirmations in Supabase → Auth →
Providers → Email for the first sign-up.

---

## Daily use

```bash
npm run dev     # local development
npm run build   # production build
npm run start   # run production build locally
```

---

## Deploying to Vercel

1. In Vercel, **Add New Project** → import this GitHub repo (`forged-by-freedom`).
2. In the project settings, set **Root Directory** to `fbf-crm`.
3. Framework preset will auto-detect as Next.js.
4. Add the same env vars from `.env.local` (Supabase URL + anon key + owner email).
5. Deploy.

Once deployed, both owners can log in from PC, Mac laptop, or iPhone Safari — the
UI is responsive.

---

## Project layout

```
fbf-crm/
├── src/
│   ├── app/
│   │   ├── login/               # public login + signup
│   │   ├── auth/signout/        # POST → clears session
│   │   └── (authed)/            # everything behind login
│   │       ├── dashboard/
│   │       ├── clients/
│   │       ├── products/
│   │       ├── inventory/
│   │       ├── orders/
│   │       ├── expenses/
│   │       └── reports/
│   ├── components/sidebar.tsx
│   └── lib/supabase/            # browser + server + middleware Supabase clients
├── middleware.ts                # gates /(authed) routes
└── supabase/migrations/         # schema SQL
```

---

## Status

Foundation only. The Clients page reads from Supabase to prove the auth + RLS
chain works end-to-end; all other pages are routed placeholders. Next sessions
will build: products CRUD, inventory lots + receive-shipment flow, manual order
entry, Stripe webhook auto-import, expenses CRUD, monthly P&L report.
