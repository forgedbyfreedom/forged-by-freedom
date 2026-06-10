"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createAdminClient } from "@/lib/supabase/admin";
import { requireSession } from "@/lib/auth";
import { int, moneyCents, str } from "@/lib/forms";

function fail(msg: string): never {
  redirect(`/inventory?error=${encodeURIComponent(msg)}`);
}

export async function addLot(formData: FormData) {
  await requireSession("/inventory");
  const product_id = str(formData, "product_id");
  if (!product_id) fail("Product is required");

  const supabase = createAdminClient();
  const { error } = await supabase.from("crm_inventory_lots").insert({
    product_id,
    lot_number: str(formData, "lot_number"),
    supplier: str(formData, "supplier"),
    unit_cost_cents: moneyCents(formData, "unit_cost"),
    qty_on_hand: int(formData, "qty_on_hand"),
    qty_on_order: int(formData, "qty_on_order"),
    tracking_number: str(formData, "tracking_number"),
    carrier: str(formData, "carrier"),
    status: str(formData, "status") || "ordered",
    ordered_at: str(formData, "ordered_at") || null,
    received_at: str(formData, "received_at") || null,
    expires_at: str(formData, "expires_at") || null,
    notes: str(formData, "notes"),
  });

  if (error) fail(error.message);
  revalidatePath("/inventory");
  revalidatePath("/dashboard");
}

export async function receiveLot(formData: FormData) {
  await requireSession("/inventory");
  const id = str(formData, "id");
  if (!id) fail("Lot id required");

  const supabase = createAdminClient();
  const { data: lot, error: readErr } = await supabase
    .from("crm_inventory_lots")
    .select("qty_on_hand, qty_on_order")
    .eq("id", id)
    .single();
  if (readErr || !lot) fail(readErr?.message || "Lot not found");

  const { error } = await supabase
    .from("crm_inventory_lots")
    .update({
      qty_on_hand: (lot.qty_on_hand || 0) + (lot.qty_on_order || 0),
      qty_on_order: 0,
      status: "received",
      received_at: new Date().toISOString(),
    })
    .eq("id", id);

  if (error) fail(error.message);
  revalidatePath("/inventory");
}
