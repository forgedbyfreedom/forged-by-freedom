"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createAdminClient } from "@/lib/supabase/admin";
import { requireSession } from "@/lib/auth";
import { int, moneyCents, str } from "@/lib/forms";

function fail(msg: string, returnTo = "/products"): never {
  redirect(`${returnTo}?error=${encodeURIComponent(msg)}`);
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

export async function updateProduct(formData: FormData) {
  await requireSession("/products");

  const id = str(formData, "id");
  if (!id) fail("Product id required");

  const name = str(formData, "name");
  if (!name) fail("Name is required", `/products/${id}/edit`);

  const supabase = createAdminClient();
  const { error } = await supabase
    .from("crm_products")
    .update({
      name,
      sku: str(formData, "sku"),
      category: str(formData, "category"),
      unit: str(formData, "unit") || "vial",
      sell_price_cents: moneyCents(formData, "sell_price"),
      current_cost_cents: moneyCents(formData, "current_cost"),
      active: formData.get("active") === "on",
    })
    .eq("id", id);

  if (error) fail(error.message, `/products/${id}/edit`);

  revalidatePath("/products");
  revalidatePath("/inventory");
  revalidatePath("/orders");
  redirect("/products");
}

export async function deleteProduct(formData: FormData) {
  await requireSession("/products");
  const id = str(formData, "id");
  if (!id) fail("Product id required");

  const supabase = createAdminClient();
  const { error } = await supabase.from("crm_products").delete().eq("id", id);
  if (error) {
    // Foreign-key violations are common here — lots or orders reference the
    // product. Translate the noisy SQL error into a clear suggestion.
    if (error.message.includes("violates foreign key")) {
      fail(
        "Can't delete — this product has inventory lots or past orders. Mark it Inactive instead, or delete those first.",
      );
    }
    fail(error.message);
  }
  revalidatePath("/products");
  revalidatePath("/inventory");
}
