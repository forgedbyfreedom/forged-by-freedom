"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { int, moneyCents, str } from "@/lib/forms";

function fail(msg: string): never {
  redirect(`/products?error=${encodeURIComponent(msg)}`);
}

export async function addProduct(formData: FormData) {
  const name = str(formData, "name");
  if (!name) fail("Name is required");

  const supabase = await createClient();

  // Diagnostic: confirm the action sees the user. If this is null, the
  // session cookie isn't reaching the server-action's Supabase client and
  // RLS will reject everything — auth fix needed, not data fix.
  const { data: userData, error: userErr } = await supabase.auth.getUser();
  if (userErr) fail(`Auth check failed: ${userErr.message}`);
  if (!userData.user) {
    fail("Server action sees no authenticated user — sign out and back in.");
  }

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

  if (error || !product) {
    fail(
      `(auth user: ${userData.user.email} / ${userData.user.id}) ${
        error?.message || "Insert failed"
      }`,
    );
  }

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
    if (lotErr) {
      fail(`Product added, but initial stock failed: ${lotErr.message}`);
    }
  }

  revalidatePath("/products");
  revalidatePath("/inventory");
  revalidatePath("/orders");
}
