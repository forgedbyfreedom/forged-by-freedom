"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createAdminClient } from "@/lib/supabase/admin";
import { requireSession } from "@/lib/auth";
import { moneyCents, str } from "@/lib/forms";

function fail(msg: string): never {
  redirect(`/expenses?error=${encodeURIComponent(msg)}`);
}

export async function addExpense(formData: FormData) {
  await requireSession("/expenses");
  const amount = moneyCents(formData, "amount");
  if (!amount) fail("Amount is required");

  const supabase = createAdminClient();
  const { error } = await supabase.from("crm_expenses").insert({
    incurred_at: str(formData, "incurred_at") || new Date().toISOString().slice(0, 10),
    category: str(formData, "category"),
    vendor: str(formData, "vendor"),
    amount_cents: amount,
    note: str(formData, "note"),
  });

  if (error) fail(error.message);
  revalidatePath("/expenses");
  revalidatePath("/reports");
}
