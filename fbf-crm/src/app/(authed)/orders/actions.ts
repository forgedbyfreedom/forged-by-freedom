"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createAdminClient } from "@/lib/supabase/admin";
import { requireSession } from "@/lib/auth";
import { ints, moneyCents, moneyCentsAll, str, strs } from "@/lib/forms";

function fail(msg: string): never {
  redirect(`/orders?error=${encodeURIComponent(msg)}`);
}

export async function addOrder(formData: FormData) {
  await requireSession("/orders");

  const productIds = strs(formData, "item_product_id");
  const qtys = ints(formData, "item_qty");
  const unitPrices = moneyCentsAll(formData, "item_unit_price");

  const items = productIds
    .map((pid, i) => ({ product_id: pid, qty: qtys[i] || 0, unit_price_cents: unitPrices[i] || 0 }))
    .filter((it) => it.product_id && it.qty > 0);

  if (items.length === 0) fail("At least one line item is required");

  const supabase = createAdminClient();

  const { data: prods, error: prodErr } = await supabase
    .from("crm_products")
    .select("id, current_cost_cents")
    .in("id", items.map((it) => it.product_id));
  if (prodErr) fail(prodErr.message);
  const costMap = new Map((prods || []).map((p) => [p.id, p.current_cost_cents || 0]));

  const subtotal = items.reduce((s, it) => s + it.qty * it.unit_price_cents, 0);
  const shipping = moneyCents(formData, "shipping");
  const tax = moneyCents(formData, "tax");
  const total = subtotal + shipping + tax;

  const { data: order, error: orderErr } = await supabase
    .from("crm_orders")
    .insert({
      client_id: str(formData, "client_id"),
      ordered_at: str(formData, "ordered_at") || new Date().toISOString(),
      source: "manual",
      subtotal_cents: subtotal,
      shipping_cents: shipping,
      tax_cents: tax,
      total_cents: total,
      status: str(formData, "status") || "paid",
      tracking_number: str(formData, "tracking_number"),
      carrier: str(formData, "carrier"),
      notes: str(formData, "notes"),
    })
    .select("id")
    .single();

  if (orderErr || !order) fail(orderErr?.message || "Failed to create order");

  const itemRows = items.map((it) => ({
    order_id: order.id,
    product_id: it.product_id,
    qty: it.qty,
    unit_price_cents: it.unit_price_cents,
    unit_cost_cents: costMap.get(it.product_id) || 0,
    line_total_cents: it.qty * it.unit_price_cents,
  }));

  const { error: itemsErr } = await supabase.from("crm_order_items").insert(itemRows);
  if (itemsErr) fail(itemsErr.message);

  const clientId = str(formData, "client_id");
  if (clientId) {
    await supabase
      .from("crm_clients")
      .update({ last_contact_at: new Date().toISOString() })
      .eq("id", clientId);
  }

  revalidatePath("/orders");
  revalidatePath("/clients");
  revalidatePath("/dashboard");
  revalidatePath("/reports");
}

export async function deleteOrder(formData: FormData) {
  await requireSession("/orders");
  const id = str(formData, "id");
  if (!id) fail("Order id required");
  const supabase = createAdminClient();
  const { error } = await supabase.from("crm_orders").delete().eq("id", id);
  if (error) fail(error.message);
  revalidatePath("/orders");
  revalidatePath("/clients");
  revalidatePath("/dashboard");
  revalidatePath("/reports");
}
