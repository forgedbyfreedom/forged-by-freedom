# Phase 2B Audit Report

**Note:** `PHASE_2B_BRIEF.md` did not exist in `C:\WINDOWS\system32` or anywhere under `C:\Users\Antonelli` at the time of audit (2026-05-03). Audit performed against the 5 specific questions only. Two codebases were searched: `C:/Users/Antonelli/forged-by-freedom` (Express scraper+API, primary backend) and `C:/Users/Antonelli/fbf-dashboard` (Next.js dashboard).

This file is the read-only audit output that informed the Phase 2B implementation. It documents the *pre-fix* state of the codebase. Cross-reference with `phase_2B_brief.md` for the requirement spec.

---

## 1. Writes of `generated_programs.status = 'delivered'` (pre-fix)

All three sites were in `forged-by-freedom/index.js`. None in the dashboard.

| File:line (pre-fix) | Trigger | Notes |
|---|---|---|
| `forged-by-freedom/index.js:5323-5325` | Coach approval handler, **Stripe-not-configured branch** | Direct manual delivery: `payment_status:'paid', delivered_at, status:'delivered'` |
| `forged-by-freedom/index.js:5714-5720` | `/api/programs/:id/payment-success` (manual return-from-Stripe poll) | Sets paid + delivered after `stripe.checkout.sessions.retrieve` returns `paid` |
| `forged-by-freedom/index.js:5882-5888` | Stripe webhook `checkout.session.completed` | Standard webhook path |

All three were swapped to `mark_program_delivered(...)` RPC in the Phase 2B commit. Line numbers post-fix differ due to added helpers.

---

## 2. Code paths that triggered program generation (pre-fix)

Four call sites of `generateProgramFromApplication` / `generateProgram`, all in `forged-by-freedom/index.js`:

| File:line | Route / context | Active? |
|---|---|---|
| `forged-by-freedom/index.js:1613` | Inside `POST /api/leads` handler | **DEAD CODE** — wrapped in `if (false)` at line 1610. Comment at 1607-1609 explicitly disables it: *"Programs are only generated after the client completes the intake form via POST /api/intake."* |
| `forged-by-freedom/index.js:1903` | `POST /api/intake` (legacy intake endpoint) | Active. Fire-and-forget IIFE after response sent (line 1898) |
| `forged-by-freedom/index.js:5051` | `POST /api/intake/generate-program` (admin/manual re-trigger by `intake_id`, gated by `ADMIN_KEY`) | Active |
| `forged-by-freedom/index.js:5977` | `POST /api/intake-with-program` (newer combined endpoint) | Active. Synchronous — awaits before responding |

Function definitions: `generateProgramFromApplication` at index.js:4072, `generateProgram` at index.js:4280.

---

## 3. Per-path validation that a `client_intakes` row exists and is "completed" (pre-fix)

**No path checked an explicit "completed" flag.** None of the routes inspected `intake.status`, `intake.completed`, `intake.completed_at`, or similar. Validation was structural (row-exists / lead-approved), not semantic.

| Path | Lead validation | Intake validation | Verdict |
|---|---|---|---|
| **1613 (dead)** | n/a | n/a | dead code |
| **1903 — `/api/intake`** | `leads.id` exists AND `lead.status === 'approved'` (lines 1862-1871) | INSERTed `client_intakes` at 1873, then generated from `fields` at 1903. Row guaranteed post-insert; no completed-flag check. Used in-memory `fields` payload, not a re-read of the row. | Implicit only |
| **5051 — `/api/intake/generate-program`** | `leads` lookup is `.maybeSingle()` and result optional (line 5047-5048) | SELECTed `client_intakes` by `intake_id` (5015-5016); on miss fell back to dashboard `client_intake` by id (5021-5022) then by `client_id` (5036-5037); returned 404 only if all three missed (5044). **Did not check any completion / status field on the intake row.** | Existence only |
| **5977 — `/api/intake-with-program`** | `leads.id` exists AND `lead.status === 'approved'` (5914-5918) | INSERTed `client_intakes` at 5948-5949, awaited insert success, then generated from the returned `intake` at 5977. No completed-flag check. | Implicit only |

Phase 2B fix: site 5051 now requires `completed_at`, `disclaimer_acknowledged`, `waiver_signature` (or `waiver_accepted_at`); returns 422 with structured `missing` array on failure.

---

## 4. Storage uploads to `client-documents` and writes to `archive_objects` (pre-fix)

Three upload sites total. **Zero of them wrote to `archive_objects`.**

| File:line | Bucket | Path scheme (pre-fix) | Wrote `archive_objects`? |
|---|---|---|---|
| `forged-by-freedom/index.js:1492-1497` (`/api/upload`) | `client-documents` | `${category}/${lead_id}/${ts}-${rand}.${ext}` | No |
| `fbf-dashboard/app/api/clients/[id]/documents/route.ts:32-37` | `client-documents` | `${clientId}/${Date.now()}.${ext}` | No |
| `fbf-dashboard/app/api/profile/avatar/route.ts:34-39` | `avatars` (not client-documents) | — | No |
| `fbf-dashboard/app/api/upload/route.ts:49-54` | `avatars` (not client-documents) | — | No |
| `fbf-dashboard/app/api/reports/generate/route.ts:78-83` | `reports` (not client-documents) | — | No |

`archive_objects` table was not referenced anywhere in source code at audit time. Phase 2B fix: forged-by-freedom `/api/upload` rewired through new `uploadAndArchive()` helper that writes to bucket + inserts archive row in one operation. Dashboard documents route updated separately to accept `stage` param and write archive rows.

---

## 5. Bloodwork upload handler — `leads.id` vs `clients.id` (pre-fix)

Two distinct bloodwork upload flows existed, on opposite sides of the lead→client conversion:

**Dashboard flow (existing client):** `clients.id`-keyed
- UI: `fbf-dashboard/components/dashboard/BloodworkUpload.tsx:87` POSTs to `/api/clients/${clientId}/documents`
- Handler: `fbf-dashboard/app/api/clients/[id]/documents/route.ts:25` builds path as `${clientId}/${Date.now()}.${ext}` — **`clientId` is `clients.id`** (route param `[id]` under `/clients/`)
- After upload, `BloodworkUpload.tsx:129` POSTs the parsed markers to `/api/clients/${clientId}/bloodwork` which writes `bloodwork_results.client_id = clientId`

**Public intake flow (pre-conversion):** `leads.id`-keyed
- Handler: `forged-by-freedom/index.js:1481-1514` (`POST /api/upload`) — required `lead_id` in form body, built path as `${category}/${lead_id}/${ts}-${rand}.${ext}`
- Used during `/api/intake-with-program` flow; resulting URL stored in `client_intakes.bloodwork_file_urls` (column listed at index.js:5941, defined in `migration-003-file-uploads-body-scans.sql`)

Phase 2B fix: forged-by-freedom `/api/upload` now resolves `client_id` from `leads.email` lookup and refuses to file under `lead_id` (returns 409 with explicit error message). Path scheme changed to `${stage}/${clientId}/${ts}-${rand}.${ext}`. Same pattern check applied to body_scan paths.

---

## Summary of risks visible at audit time

- Three independent `status='delivered'` writers (one direct, one polling, one webhook) — race conditions / double-delivery possible if more than one fires for the same program. **Closed in Phase 2B by routing all three through `mark_program_delivered` RPC.**
- `/api/intake/generate-program` (5051) checked only that an intake row existed; an empty/draft intake row would generate a program. **Closed in Phase 2B by requiring `completed_at` + disclaimer + waiver.**
- `archive_objects` was referenced nowhere in source — uploads silently did not produce archive rows. **Closed in Phase 2B with `uploadAndArchive()` helper.**
- Bloodwork file URLs lived under two different identifier namespaces (`leads.id` during intake, `clients.id` post-conversion) with no observed migration step that re-keyed or copies storage objects on lead→client promotion. **Closed in Phase 2B by forcing client-id resolution in `/api/upload`.**
