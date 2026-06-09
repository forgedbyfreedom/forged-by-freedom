"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { moneyCents, str } from "@/lib/forms";

export async function addProduct(formData: FormData) {
  const name = str(formData, "name");
  if (!name) return { error: "Name is required" };

  const supabase = await createClient();
  const { error } = await supabase.from("crm_products").insert({
    name,
    sku: str(formData, "sku"),
    category: str(formData, "category"),
    unit: str(formData, "unit") || "vial",
    sell_price_cents: moneyCents(formData, "sell_price"),
    current_cost_cents: moneyCents(formData, "current_cost"),
    active: formData.get("active") === "on",
  });

  if (error) return { error: error.message };
  revalidatePath("/products");
  revalidatePath("/inventory");
  revalidatePath("/orders");
  return { ok: true };
}
