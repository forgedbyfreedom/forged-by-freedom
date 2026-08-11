"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { SupabaseClient } from "@supabase/supabase-js";
import { createAdminClient } from "@/lib/supabase/admin";
import { requireSession } from "@/lib/auth";
import { ints, moneyCents, moneyCentsAll, str, strs } from "@/lib/forms";
import { notifyInventory } from "@/lib/sms";

function fail(msg: string): never {
  redirect(`/orders?error=${encodeURIComponent(msg)}`);
}

// Deduct `qty` from the available inventory for `productId` FIFO
// (oldest received_at first, then oldest created_at). Returns the first
// lot id touched (recorded on the order_item for traceability + refunds)
// and whether stock fully covered the order.
async function deductInventoryFifo(
  supabase: SupabaseClient,
  productId: string,
  qty: number,
): Promise<{ firstLotId: string | null; shortBy: number }> {
  const { data: lots } = await supabase
    .from("crm_inventory_lots")
    .select("id, qty_on_hand")
    .eq("product_id", productId)
    .gt("qty_on_hand", 0)
    .order("received_at", { ascending: true, nullsFirst: true })
    .order("created_at", { ascending: true });

  let remaining = qty;
  let firstLotId: string | null = null;
  for (const lot of lots || []) {
    if (remaining <= 0) break;
    const take = Math.min(lot.qty_on_hand, remaining);
    await supabase
      .from("crm_inventory_lots")
      .update({ qty_on_hand: lot.qty_on_hand - take })
      .eq("id", lot.id);
    if (!firstLotId) firstLotId = lot.id;
    remaining -= take;
  }
  return { firstLotId, shortBy: remaining };
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

  // Snapshot current product costs so future cost changes don't rewrite history.
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

  const userNotes = str(formData, "notes") || "";

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
      notes: userNotes,
    })
    .select("id")
    .single();

  if (orderErr || !order) fail(orderErr?.message || "Failed to create order");

  // Deduct inventory FIFO, recording the first lot touched on each item.
  const shortItems: { name: string; shortBy: number }[] = [];
  const itemRows: {
    order_id: string;
    product_id: string;
    lot_id: string | null;
    qty: number;
    unit_price_cents: number;
    unit_cost_cents: number;
    line_total_cents: number;
  }[] = [];

  for (const it of items) {
    const { firstLotId, shortBy } = await deductInventoryFifo(supabase, it.product_id, it.qty);
    if (shortBy > 0) {
      const prodName =
        (prods || []).find((p) => p.id === it.product_id)?.current_cost_cents !== undefined
          ? "(product " + it.product_id.slice(0, 8) + ")"
          : "(product)";
      shortItems.push({ name: prodName, shortBy });
    }
    itemRows.push({
      order_id: order.id,
      product_id: it.product_id,
      lot_id: firstLotId,
      qty: it.qty,
      unit_price_cents: it.unit_price_cents,
      unit_cost_cents: costMap.get(it.product_id) || 0,
      line_total_cents: it.qty * it.unit_price_cents,
    });
  }

  const { error: itemsErr } = await supabase.from("crm_order_items").insert(itemRows);
  if (itemsErr) fail(itemsErr.message);

  // If any items couldn't be fully sourced from stock, append a note to the
  // order so it's visible later (instead of silently going negative).
  if (shortItems.length > 0) {
    const shortNote = shortItems
      .map((s) => `${s.name} short by ${s.shortBy}`)
      .join("; ");
    await supabase
      .from("crm_orders")
      .update({
        notes: [userNotes, `[stock shortfall: ${shortNote}]`].filter(Boolean).join(" "),
      })
      .eq("id", order.id);
  }

  const clientId = str(formData, "client_id");
  if (clientId) {
    await supabase
      .from("crm_clients")
      .update({ last_contact_at: new Date().toISOString() })
      .eq("id", clientId);
  }

  // SMS: one summary line per manual order.
  const itemSummary = items.map((it) => it.qty).reduce((a, b) => a + b, 0);
  notifyInventory(
    `Order recorded: ${itemSummary} item(s), $${(total / 100).toFixed(2)} total${
      shortItems.length > 0 ? " — STOCK SHORTFALL" : ""
    }`,
  );

  revalidatePath("/orders");
  revalidatePath("/clients");
  revalidatePath("/inventory");
  revalidatePath("/products");
  revalidatePath("/dashboard");
  revalidatePath("/reports");
}

export async function updateOrder(formData: FormData) {
  await requireSession("/orders");
  const id = str(formData, "id");
  if (!id) fail("Order id required");

  const supabase = createAdminClient();
  const { error } = await supabase
    .from("crm_orders")
    .update({
      client_id: str(formData, "client_id"),
      ordered_at: str(formData, "ordered_at") || new Date().toISOString(),
      status: str(formData, "status") || "paid",
      shipping_cents: moneyCents(formData, "shipping"),
      tax_cents: moneyCents(formData, "tax"),
      tracking_number: str(formData, "tracking_number"),
      carrier: str(formData, "carrier"),
      notes: str(formData, "notes"),
    })
    .eq("id", id);

  if (error) fail(error.message, `/orders/${id}/edit`);

  // Recalculate total in case shipping/tax changed (subtotal stays — line
  // items aren't editable from this form to avoid messy inventory reshuffles).
  const { data: order } = await supabase
    .from("crm_orders")
    .select("subtotal_cents, shipping_cents, tax_cents")
    .eq("id", id)
    .single();
  if (order) {
    await supabase
      .from("crm_orders")
      .update({
        total_cents:
          (order.subtotal_cents || 0) +
          (order.shipping_cents || 0) +
          (order.tax_cents || 0),
      })
      .eq("id", id);
  }

  revalidatePath("/orders");
  revalidatePath("/clients");
  revalidatePath("/dashboard");
  revalidatePath("/reports");
  redirect("/orders");
}

export async function markShipped(formData: FormData) {
  await requireSession("/orders");
  const id = str(formData, "id");
  if (!id) fail("Order id required");
  const carrier = str(formData, "carrier");
  const tracking = str(formData, "tracking_number");

  const supabase = createAdminClient();
  const { error } = await supabase
    .from("crm_orders")
    .update({
      status: "shipped",
      carrier: carrier || undefined,
      tracking_number: tracking || undefined,
    })
    .eq("id", id);

  if (error) fail(error.message);
  revalidatePath("/orders");
  revalidatePath("/dashboard");
}

export async function deleteOrder(formData: FormData) {
  await requireSession("/orders");
  const id = str(formData, "id");
  if (!id) fail("Order id required");

  const supabase = createAdminClient();

  // Refund inventory back to the originating lots before we cascade-delete
  // the items. If a lot was deleted in the meantime, skip silently.
  const { data: items } = await supabase
    .from("crm_order_items")
    .select("lot_id, qty")
    .eq("order_id", id);

  for (const it of items || []) {
    if (!it.lot_id) continue;
    const { data: lot } = await supabase
      .from("crm_inventory_lots")
      .select("qty_on_hand")
      .eq("id", it.lot_id)
      .maybeSingle();
    if (!lot) continue;
    await supabase
      .from("crm_inventory_lots")
      .update({ qty_on_hand: (lot.qty_on_hand || 0) + (it.qty || 0) })
      .eq("id", it.lot_id);
  }

  const { error } = await supabase.from("crm_orders").delete().eq("id", id);
  if (error) fail(error.message);

  revalidatePath("/orders");
  revalidatePath("/clients");
  revalidatePath("/inventory");
  revalidatePath("/products");
  revalidatePath("/dashboard");
  revalidatePath("/reports");
}
