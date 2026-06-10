"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createAdminClient } from "@/lib/supabase/admin";
import { requireSession } from "@/lib/auth";
import { int, moneyCents, str } from "@/lib/forms";

function fail(msg: string): never {
  redirect(`/products?error=${encodeURIComponent(msg)}`);
}

export async function addProduct(formData: FormData) {
  await requireSession("/products");

  const name = str(formData, "name");
  if (!name) fail("Name is required");

  const supabase = createAdminClient();
  const { data: product, error } = await supabase
    .from("crm_products")
    .insert({
      name,
      sku: str(formData, "sku"),
      category: str(formData, "category"),
      unit: str(formData, "unit") || "vial",
      sell_price_cents: moneyCents(formData, "sell_price"),
      current_cost_cents: moneyCents(formData, "current_cost"),
      active: formData.get("active") === "on",
    })
    .select("id")
    .single();

  if (error || !product) fail(error?.message || "Insert failed");

  const initialQty = int(formData, "initial_qty");
  if (initialQty > 0) {
    const initialCost =
      moneyCents(formData, "initial_unit_cost") || moneyCents(formData, "current_cost");
    const { error: lotErr } = await supabase.from("crm_inventory_lots").insert({
      product_id: product.id,
      qty_on_hand: initialQty,
      unit_cost_cents: initialCost,
      status: "received",
      received_at: new Date().toISOString(),
      notes: "Initial stock — created with product",
    });
    if (lotErr) fail(`Product added, but initial stock failed: ${lotErr.message}`);
  }

  revalidatePath("/products");
  revalidatePath("/inventory");
  revalidatePath("/orders");
}
