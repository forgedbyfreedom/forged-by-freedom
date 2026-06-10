"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { findHeaderRowIndex, parseCsv, parseSignedMoneyCents } from "@/lib/csv";

type ImportRow = {
  external_id: string;
  source: "venmo" | "cashapp";
  ordered_at: string; // ISO
  amount_cents: number; // already signed
  counterparty: string;
  note: string;
};

function fail(msg: string): never {
  redirect(`/import?error=${encodeURIComponent(msg)}`);
}

function ok(summary: string): never {
  redirect(`/import?ok=${encodeURIComponent(summary)}`);
}

function parseVenmo(rows: string[][]): ImportRow[] {
  const headerIdx = findHeaderRowIndex(rows, ["Datetime", "Note", "From", "To"]);
  if (headerIdx < 0) return [];
  const headers = rows[headerIdx].map((h) => h.trim());
  const col = (name: string) =>
    headers.findIndex((h) => h.toLowerCase() === name.toLowerCase());

  const cId = col("ID");
  const cDate = col("Datetime");
  const cType = col("Type");
  const cStatus = col("Status");
  const cNote = col("Note");
  const cFrom = col("From");
  const cTo = col("To");
  const cAmount = col("Amount (total)");

  const out: ImportRow[] = [];
  for (let i = headerIdx + 1; i < rows.length; i++) {
    const r = rows[i];
    const id = r[cId]?.trim();
    if (!id) continue;
    const status = (r[cStatus] || "").toLowerCase();
    if (status && status !== "complete") continue;
    const amount = parseSignedMoneyCents(r[cAmount] || "");
    if (amount <= 0) continue; // only inbound payments
    const date = r[cDate]?.trim() || "";
    const isoDate = (() => {
      const d = new Date(date);
      return Number.isNaN(d.getTime()) ? new Date().toISOString() : d.toISOString();
    })();
    out.push({
      external_id: id,
      source: "venmo",
      ordered_at: isoDate,
      amount_cents: amount,
      counterparty: r[cFrom]?.trim() || "Unknown",
      note: [r[cType], r[cNote]].filter(Boolean).join(" — ").trim(),
    });
  }
  return out;
}

function parseCashapp(rows: string[][]): ImportRow[] {
  const headerIdx = findHeaderRowIndex(rows, ["Transaction ID", "Date"]);
  if (headerIdx < 0) return [];
  const headers = rows[headerIdx].map((h) => h.trim());
  const col = (name: string) =>
    headers.findIndex((h) => h.toLowerCase() === name.toLowerCase());

  const cId = col("Transaction ID");
  const cDate = col("Date");
  const cType = col("Transaction Type");
  const cNet = col("Net Amount");
  const cAmount = col("Amount");
  const cName = col("Name of sender/receiver") >= 0
    ? col("Name of sender/receiver")
    : col("Name");
  const cNotes = col("Notes");
  const cStatus = col("Status");

  const out: ImportRow[] = [];
  for (let i = headerIdx + 1; i < rows.length; i++) {
    const r = rows[i];
    const id = r[cId]?.trim();
    if (!id) continue;
    const status = (r[cStatus] || "").toLowerCase();
    if (status && !/(complete|success|paid)/i.test(status)) continue;

    const amountRaw = r[cNet] || r[cAmount] || "";
    const amount = parseSignedMoneyCents(amountRaw);
    if (amount <= 0) continue;

    const isoDate = (() => {
      const d = new Date(r[cDate] || "");
      return Number.isNaN(d.getTime()) ? new Date().toISOString() : d.toISOString();
    })();

    out.push({
      external_id: id,
      source: "cashapp",
      ordered_at: isoDate,
      amount_cents: amount,
      counterparty: r[cName]?.trim() || "Unknown",
      note: [r[cType], r[cNotes]].filter(Boolean).join(" — ").trim(),
    });
  }
  return out;
}

function detectAndParse(text: string): ImportRow[] {
  const rows = parseCsv(text);
  if (rows.length === 0) return [];
  // Try Venmo first (more specific columns), then CashApp.
  const venmo = parseVenmo(rows);
  if (venmo.length) return venmo;
  return parseCashapp(rows);
}

export async function importStatements(formData: FormData) {
  const files = formData.getAll("files").filter((f): f is File => f instanceof File);
  if (files.length === 0) fail("No files uploaded");

  const supabase = await createClient();

  // 1. Parse all uploaded files
  const all: ImportRow[] = [];
  let skippedFiles = 0;
  for (const file of files) {
    const text = await file.text();
    const parsed = detectAndParse(text);
    if (parsed.length === 0) skippedFiles++;
    all.push(...parsed);
  }
  if (all.length === 0) {
    fail(
      `No importable transactions found across ${files.length} file(s). Make sure these are Venmo or CashApp CSV exports.`,
    );
  }

  // 2. Resolve clients — match existing by case-insensitive name, otherwise insert new.
  const uniqueNames = Array.from(
    new Set(all.map((r) => r.counterparty.trim()).filter(Boolean)),
  );
  const { data: existing, error: clientReadErr } = await supabase
    .from("crm_clients")
    .select("id, name");
  if (clientReadErr) fail(`Could not read clients: ${clientReadErr.message}`);

  const nameToId = new Map<string, string>();
  for (const c of existing || []) {
    nameToId.set(c.name.trim().toLowerCase(), c.id);
  }

  const newNames = uniqueNames.filter(
    (n) => !nameToId.has(n.toLowerCase()),
  );
  let newClientsCreated = 0;
  if (newNames.length > 0) {
    const { data: inserted, error: insertErr } = await supabase
      .from("crm_clients")
      .insert(newNames.map((name) => ({ name, notes: "Imported from CashApp/Venmo" })))
      .select("id, name");
    if (insertErr) fail(`Could not create new clients: ${insertErr.message}`);
    for (const c of inserted || []) {
      nameToId.set(c.name.trim().toLowerCase(), c.id);
    }
    newClientsCreated = inserted?.length || 0;
  }

  // 3. Find which transactions are already imported (avoid duplicates).
  const externalIds = all.map((r) => r.external_id);
  const { data: dupes } = await supabase
    .from("crm_orders")
    .select("external_id, source")
    .in("external_id", externalIds);

  const dupeKey = new Set(
    (dupes || []).map((d) => `${d.source}::${d.external_id}`),
  );

  const toInsert = all
    .filter((r) => !dupeKey.has(`${r.source}::${r.external_id}`))
    .map((r) => ({
      client_id: nameToId.get(r.counterparty.toLowerCase()) || null,
      ordered_at: r.ordered_at,
      source: r.source,
      external_id: r.external_id,
      subtotal_cents: r.amount_cents,
      shipping_cents: 0,
      tax_cents: 0,
      total_cents: r.amount_cents,
      status: "paid",
      notes: r.note,
    }));

  let inserted = 0;
  if (toInsert.length > 0) {
    const { error: ordersErr } = await supabase.from("crm_orders").insert(toInsert);
    if (ordersErr) fail(`Could not insert orders: ${ordersErr.message}`);
    inserted = toInsert.length;
  }

  revalidatePath("/orders");
  revalidatePath("/clients");
  revalidatePath("/dashboard");
  revalidatePath("/reports");

  ok(
    `Imported ${inserted} order(s) across ${files.length - skippedFiles} file(s). ${
      newClientsCreated > 0 ? `${newClientsCreated} new client(s) created. ` : ""
    }${all.length - inserted > 0 ? `${all.length - inserted} duplicate(s) skipped.` : ""}${
      skippedFiles > 0 ? ` ${skippedFiles} file(s) skipped (unrecognized format).` : ""
    }`.trim(),
  );
}
