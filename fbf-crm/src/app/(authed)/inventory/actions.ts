"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createAdminClient } from "@/lib/supabase/admin";
import { requireSession } from "@/lib/auth";
import { notifyInventory } from "@/lib/sms";
import { int, moneyCents, str } from "@/lib/forms";

function fail(msg: string, returnTo = "/inventory"): never {
  redirect(`${returnTo}?error=${encodeURIComponent(msg)}`);
}

async function productName(
  supabase: ReturnType<typeof createAdminClient>,
  productId: string,
): Promise<string> {
  const { data } = await supabase
    .from("crm_products")
    .select("name")
    .eq("id", productId)
    .maybeSingle();
  return data?.name || "(unknown product)";
}

export async function addLot(formData: FormData) {
  await requireSession("/inventory");
  const product_id = str(formData, "product_id");
  if (!product_id) fail("Product is required");

  const qty_on_hand = int(formData, "qty_on_hand");
  const qty_on_order = int(formData, "qty_on_order");

  const supabase = createAdminClient();
  const { error } = await supabase.from("crm_inventory_lots").insert({
    product_id,
    lot_number: str(formData, "lot_number"),
    supplier: str(formData, "supplier"),
    unit_cost_cents: moneyCents(formData, "unit_cost"),
    qty_on_hand,
    qty_on_order,
    tracking_number: str(formData, "tracking_number"),
    carrier: str(formData, "carrier"),
    status: str(formData, "status") || "ordered",
    ordered_at: str(formData, "ordered_at") || null,
    received_at: str(formData, "received_at") || null,
    expires_at: str(formData, "expires_at") || null,
    notes: str(formData, "notes"),
  });

  if (error) fail(error.message);
  notifyInventory(
    `New lot added: ${await productName(supabase, product_id)} (+${qty_on_hand} on hand, ${qty_on_order} on order)`,
  );
  revalidatePath("/inventory");
  revalidatePath("/products");
  revalidatePath("/dashboard");
}

export async function updateLot(formData: FormData) {
  await requireSession("/inventory");
  const id = str(formData, "id");
  if (!id) fail("Lot id required");

  const supabase = createAdminClient();
  const { error } = await supabase
    .from("crm_inventory_lots")
    .update({
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
    })
    .eq("id", id);

  if (error) fail(error.message, `/inventory/${id}/edit`);
  revalidatePath("/inventory");
  revalidatePath("/products");
  redirect("/inventory");
}

export async function receiveLot(formData: FormData) {
  await requireSession("/inventory");
  const id = str(formData, "id");
  if (!id) fail("Lot id required");

  const supabase = createAdminClient();
  const { data: lot, error: readErr } = await supabase
    .from("crm_inventory_lots")
    .select("qty_on_hand, qty_on_order, product_id")
    .eq("id", id)
    .single();
  if (readErr || !lot) fail(readErr?.message || "Lot not found");

  const newOnHand = (lot.qty_on_hand || 0) + (lot.qty_on_order || 0);
  const arrived = lot.qty_on_order || 0;

  const { error } = await supabase
    .from("crm_inventory_lots")
    .update({
      qty_on_hand: newOnHand,
      qty_on_order: 0,
      status: "received",
      received_at: new Date().toISOString(),
    })
    .eq("id", id);

  if (error) fail(error.message);
  notifyInventory(
    `Received: ${await productName(supabase, lot.product_id)} (+${arrived}, now ${newOnHand} on hand)`,
  );
  revalidatePath("/inventory");
  revalidatePath("/products");
}

export async function withdrawLot(formData: FormData) {
  await requireSession("/inventory");
  const id = str(formData, "id");
  if (!id) fail("Lot id required");
  const qty = int(formData, "qty");
  if (qty <= 0) fail("Quantity must be at least 1");

  const supabase = createAdminClient();
  const { data: lot, error: readErr } = await supabase
    .from("crm_inventory_lots")
    .select("qty_on_hand, product_id")
    .eq("id", id)
    .single();
  if (readErr || !lot) fail(readErr?.message || "Lot not found");

  if (qty > (lot.qty_on_hand || 0)) {
    fail(`Only ${lot.qty_on_hand || 0} on hand — can't withdraw ${qty}.`);
  }

  const newOnHand = (lot.qty_on_hand || 0) - qty;
  const { error } = await supabase
    .from("crm_inventory_lots")
    .update({ qty_on_hand: newOnHand })
    .eq("id", id);

  if (error) fail(error.message);
  notifyInventory(
    `Withdrew ${qty}× ${await productName(supabase, lot.product_id)} — ${newOnHand} left on hand${
      newOnHand <= 5 ? " ⚠️ LOW" : ""
    }`,
  );
  revalidatePath("/inventory");
  revalidatePath("/products");
  revalidatePath("/dashboard");
}

export async function deleteLot(formData: FormData) {
  await requireSession("/inventory");
  const id = str(formData, "id");
  if (!id) fail("Lot id required");

  const supabase = createAdminClient();
  const { data: lot } = await supabase
    .from("crm_inventory_lots")
    .select("product_id, qty_on_hand")
    .eq("id", id)
    .maybeSingle();

  const { error } = await supabase.from("crm_inventory_lots").delete().eq("id", id);
  if (error) {
    if (error.message.includes("violates foreign key")) {
      fail(
        "Can't delete — past order line items reference this lot. Set qty to 0 instead to mark it depleted.",
      );
    }
    fail(error.message);
  }
  if (lot) {
    notifyInventory(
      `Lot deleted: ${await productName(supabase, lot.product_id)} (was ${lot.qty_on_hand} on hand)`,
    );
  }
  revalidatePath("/inventory");
  revalidatePath("/products");
}
