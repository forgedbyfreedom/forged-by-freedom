# FBF onboarding system — Phase 2B handoff brief

**Audience:** Claude Code, running locally on Bryan's PC against the `forged-by-freedom` and `fbf-client-app` repos.

**Date of audit:** 2026-05-02
**Production state at handoff:** Stable. All Phase 2A database fixes deployed. Drive sync active. Phase 2B (this document) covers the remaining application-code work.

---

## Read this section before doing anything

Two repos in scope:
- `forged-by-freedom` — Bryan's Render-hosted API server. Hosts the form handlers, the AI program generator, and email notification logic.
- `fbf-client-app` — Bryan's Vercel-hosted client/admin dashboard. Hosts the program review UI, the approve/reject flow, and the client-facing program view.

There is a duplicate Vercel project `fbf-client-app-a31c` that should be confirmed orphan and deleted.

**Production database:** Supabase project `sdrsoccfingecvlzrlym` (FBF-Dashboard).

**Critical principle:** every change you make to the application code must align with the database changes already deployed. Where there's tension, the DB is the source of truth and the code conforms — not the reverse. The DB has new gating triggers and constraints that will *block* writes that don't conform. Loud failure is by design.

---

## What's already done in production (don't redo this work)

### Database migrations applied to `sdrsoccfingecvlzrlym`

1. `phase2a_01_add_archive_and_recon_tables` — created `archive_objects`, `reconciliation_findings`, `audit_snapshots`
2. `phase2a_02_audit_triggers_for_programs` — `program_change_log` now auto-populates on every `generated_programs` and `program_reviews` change
3. `phase2a_03_backfill_archive_objects_v2` — backfilled 72 storage objects into `archive_objects` with stage classification
4. `phase2a_04_intake_unification` — added `client_id`, `source`, `notes_internal`, `waiver_accepted_at`, `waiver_ip`, `completed_at` columns to `client_intakes` (plural). Backfilled 13 rows from `client_intake` (singular). The singular table still exists but is deprecated. App code that reads from `client_intake` (singular) needs to be migrated to read from `client_intakes` (plural).
5. `phase2a_05_gate_program_delivery` — replaced `sync_delivered_program_to_client` trigger with a gated version. **Critical behavior change:** any UPDATE that sets `generated_programs.status = 'delivered'` without `approved_at IS NOT NULL` AND a corresponding `program_reviews.status = 'approved'` row will: (a) write the row, but (b) NOT sync to `clients.workout_program`, and (c) write a CRITICAL row to `reconciliation_findings`. Application code MUST stop writing `delivered` directly and use the new RPC instead.
6. `phase2a_06_retroactive_review_and_check_constraint` — created `program_retroactive_review` table with 6 flagged programs. Added CHECK constraint `delivered_implies_approved` (NOT VALID — grandfathers existing violators).
7. `phase2a_07_reconciliation_function` — `public.run_reconciliation_scan()` scans for 7 failure modes and writes to `reconciliation_findings`. Should be scheduled hourly.
8. `phase2a5_01_validation_function_and_rpc` — `validate_program_for_delivery(uuid)` and `mark_program_delivered(uuid, uuid, text)`. **App code must use these.**
9. `phase2a5_02_dashboard_views_and_trigger_fix` — three dashboard views, plus actor-identity capture in the gate trigger.
10. `phase2a5_03_pg_cron_pg_net_for_drive_sync` — pg_cron and pg_net installed.
11. `phase2c_01a_pgvector_table_only` and `phase2c_01b_match_chunks_function` — pgvector + `fbf_reference_chunks` table for RAG (currently empty, may not be used if Pinecone migration completes locally).

### Drive sync infrastructure (operational)

- Edge function `fbf-drive-sync` deployed.
- Supabase Vault contains `service_role_key` secret used by the cron helper.
- `public.invoke_drive_sync()` calls the edge function with auth.
- pg_cron job `fbf-drive-sync-every-5min` runs every 5 minutes.
- All 72 backfilled archive objects synced to Bryan's Drive at `/FBF-Archive/{LastName_FirstName_clientId8}/{stage}/{timestamp}_{filename}`.

### Retroactive review

6 programs flagged in `program_retroactive_review`:
- Tony Stines (2 active programs, no review rows on either) — HIGHEST PRIORITY
- Codee Goff (PED protocol delivered without baseline bloodwork)
- John Such (program generated against `intake_id = NULL`)
- Michelle Roger (same as John Such)
- Test Client Demo (test data — should be deleted)

---

## What needs to be done in application code (Phase 2B)

### Priority 1 — Stop bypassing the gate

The trigger now blocks ungated deliveries from reaching the client app, but the recon table will fill with critical findings until callers are fixed.

**Find every place in `forged-by-freedom` that writes `status = 'delivered'` to `generated_programs`.**

```bash
grep -rn "status.*delivered" forged-by-freedom/
grep -rn "generated_programs" forged-by-freedom/
grep -rn "delivered_at" forged-by-freedom/
```

**Replace each direct UPDATE with a call to the new RPC:**

```typescript
// OLD (broken — bypasses gate)
await supabase
  .from('generated_programs')
  .update({ status: 'delivered', delivered_at: new Date().toISOString() })
  .eq('id', programId);

// NEW (gated)
const { data, error } = await supabase.rpc('mark_program_delivered', {
  p_program_id: programId,
  p_actor_id: currentUserId,
  p_actor_name: currentUserName
});

if (error) throw error;
const result = data[0];
if (!result.success) {
  // result.reasons is an array of strings explaining why
  throw new Error(`Cannot deliver program: ${result.reasons.join(', ')}`);
}
```

Common validation reasons returned:
- `no_intake_id` — program has NULL intake_id (architectural failure, see Priority 2)
- `no_review_row` — no `program_reviews` row exists for this intake
- `review_status_<X>` — review exists but not approved
- `review_approved_at_null` — review marked approved but timestamp missing
- `no_matching_client` — `client_email` doesn't match any client row
- `ped_protocol_requires_bloodwork_within_90d` — program has a PED section but no recent bloodwork

### Priority 2 — Block program generation when intake is incomplete

Root cause of the John Such / Michelle Roger pattern. The generator must refuse to run if:
- `client_intakes` row doesn't exist for the lead/client
- `client_intakes.completed_at IS NULL`
- `client_intakes.disclaimer_acknowledged IS FALSE OR NULL`
- `client_intakes.waiver_signature IS NULL` (or `waiver_accepted_at IS NULL` for migrated rows)

**Pseudocode:**

```typescript
async function generateProgramForLead(leadId: string) {
  const { data: intake } = await supabase
    .from('client_intakes')
    .select('id, completed_at, disclaimer_acknowledged, waiver_signature, waiver_accepted_at')
    .eq('lead_id', leadId)
    .order('created_at', { ascending: false })
    .limit(1)
    .single();

  if (!intake) throw new Error(`Cannot generate program: no intake for lead ${leadId}`);
  if (!intake.completed_at) throw new Error(`Cannot generate program: intake ${intake.id} not completed`);
  if (!intake.disclaimer_acknowledged) throw new Error(`Cannot generate program: disclaimer not acknowledged`);
  if (!intake.waiver_signature && !intake.waiver_accepted_at) throw new Error(`Cannot generate program: waiver not signed`);

  // CRITICAL: pass intake.id as intake_id when inserting into generated_programs
  // NEVER insert with intake_id = NULL
}
```

### Priority 3 — Archive every storage upload

Currently storage uploads happen but archive rows are not written by the application — only the one-time backfill populated them. Going forward, every storage upload from the app must also write an `archive_objects` row.

**Find every place that uploads to Supabase Storage:**

```bash
grep -rn "supabase.storage" forged-by-freedom/ fbf-client-app/
grep -rn "\.from('client-documents')" forged-by-freedom/ fbf-client-app/
grep -rn "\.upload(" forged-by-freedom/ fbf-client-app/
```

**Wrap each upload with a helper:**

```typescript
async function uploadAndArchive({
  bucket, path, file, contentType, clientId, leadId, intakeId, programId,
  stage, originalName, archivedBy
}) {
  const { error: uploadErr } = await supabase.storage
    .from(bucket).upload(path, file, { contentType, upsert: false });
  if (uploadErr) throw uploadErr;

  const arrayBuffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
  const sha256 = Array.from(new Uint8Array(hashBuffer))
    .map(b => b.toString(16).padStart(2, '0')).join('');

  const { error: archiveErr } = await supabase.from('archive_objects').insert({
    client_id: clientId, lead_id: leadId, intake_id: intakeId, program_id: programId,
    stage, bucket_id: bucket, storage_path: path, original_name: originalName,
    mime_type: contentType, size_bytes: arrayBuffer.byteLength, sha256,
    archived_by: archivedBy
  });

  if (archiveErr) throw new Error(`Storage upload succeeded but archive failed: ${archiveErr.message}`);
  return { path, sha256 };
}
```

Valid `stage` values: `lead_intake`, `second_stage_intake`, `nda`, `waiver`, `program_pdf`, `program_json`, `bloodwork`, `body_scan`, `progress_photo`, `lab_pdf`, `other`.

Drive sync picks up the archive row automatically within 5 minutes.

### Priority 4 — Fix the bloodwork upload that files under lead-id

Found in audit: Jim Weldon's bloodwork PDFs are filed under his lead-id (`ae195ff8-...`) instead of his client-id (`8c695519-...`). Pattern in storage path: `bloodwork/{lead_uuid}/...`.

```typescript
// WRONG
const { data: lead } = await supabase.from('leads').select('id').eq('email', email).single();
const path = `bloodwork/${lead.id}/${filename}`;

// RIGHT
const { data: client } = await supabase.from('clients').select('id').eq('email', email).single();
if (!client) throw new Error(`No client record for ${email}`);
const path = `bloodwork/${client.id}/${filename}`;
```

Same pattern check for body_scan uploads. Also: any path like `bloodwork/unknown/` indicates a code path falling back to `"unknown"` — should refuse instead.

### Priority 5 — Fix OpenRouter env wiring (or remove entirely)

Render env currently has:
- `OPENROUTER_API_KEY` = an `sk-proj-` OpenAI key, not a valid OpenRouter key
- `OPENROUTER_EMBED_MODEL` = `text-embedding-3-large` (an OpenAI model name, not an OpenRouter slug)

Bryan's stated direction: drop OpenRouter, move to local Ollama (24GB GPU, models including `qwen2.5:32b`, `qwen2.5-coder:32b`, `gpt-oss:20b`, `nomic-embed-text`, `mxbai-embed-large`). Anthropic Claude API as fallback. Pinecone state in transition (currently in production, partial local migration in progress).

### Priority 6 — Migrate readers off `client_intake` (singular)

The singular table is deprecated. Find readers, switch to `client_intakes` (plural). Schemas don't match exactly; check `audit_snapshots` for original schema.

After all readers migrated, drop the singular table.

### Priority 7 — Reconciliation cron + daily digest email

`run_reconciliation_scan()` exists but isn't scheduled. Add cron similar to drive sync. Add email-digest endpoint that queries `v_open_recon_findings` and emails Bryan if critical findings unresolved past 24h.

### Priority 8 — Confirm no auto-approval path on lead intake

Bryan said he genuinely clicks approve on most leads, so gate-1 is working as a human gate. Verify by searching for any path that flips `leads.status = 'approved'` automatically. If found, fix.

---

## Operational items (lower priority but should happen)

### Test data cleanup

```sql
DELETE FROM public.clients WHERE email LIKE '%@fbf.test' OR email LIKE 'test_%' OR first_name = 'E2E';
DELETE FROM public.generated_programs WHERE client_email LIKE '%@fbf.test' OR client_email LIKE 'test_%';
DELETE FROM public.program_retroactive_review WHERE client_email = 'test_demo_delete@fbf.test';
```

### Duplicate Vercel project

Verify `fbf-client-app` vs `fbf-client-app-a31c`. Delete the orphan after confirming no production traffic.

### Tony Stines duplicate intake/programs

Bryan must decide which of Tony's two programs is canonical. Then mark the non-canonical:

```sql
UPDATE public.generated_programs SET status = 'superseded' WHERE id = '<the_one_to_kill>';
```

Same for Teresa Weldon's duplicates.

### Token cleanup

`intake_tokens` has 197 rows for ~25 actual intakes. Add cleanup cron:

```sql
DELETE FROM public.intake_tokens WHERE created_at < now() - interval '30 days';
```

---

## Schema cheat sheet

Tables you'll touch most:

- `client_intakes` — canonical intakes (use this, not `client_intake` singular)
- `generated_programs` — programs. Don't UPDATE status='delivered' directly; use `mark_program_delivered()` RPC.
- `program_reviews` — internal FBF reviews. Required step before delivery.
- `archive_objects` — file tracking. Write a row every time you upload to storage.
- `program_change_log` — populates automatically via triggers; don't write directly.
- `reconciliation_findings` — populates automatically; readable for dashboards.
- `program_retroactive_review` — Bryan's queue for the 6 flagged programs.
- `fbf_reference_chunks` — RAG storage (currently empty, pending Pinecone migration decision).

Functions/RPCs:

- `mark_program_delivered(p_program_id, p_actor_id, p_actor_name)` — gated delivery
- `validate_program_for_delivery(p_program_id)` — pre-check, returns (valid, reasons[])
- `run_reconciliation_scan()` — manual recon trigger
- `invoke_drive_sync()` — manual drive sync trigger (cron does this automatically)
- `match_chunks(query_embedding, count, source_filter, min_similarity)` — RAG retrieval (768-dim, nomic-embed-text)

Views:

- `v_pending_review_programs` — what the dashboard's "needs your approval" tab queries
- `v_retroactive_review_queue` — the 6 flagged programs
- `v_open_recon_findings` — anything broken
