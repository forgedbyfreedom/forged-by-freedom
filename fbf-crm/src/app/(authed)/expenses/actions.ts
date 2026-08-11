"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createAdminClient } from "@/lib/supabase/admin";
import { requireSession } from "@/lib/auth";
import { moneyCents, str } from "@/lib/forms";

function fail(msg: string, returnTo = "/expenses"): never {
  redirect(`${returnTo}?error=${encodeURIComponent(msg)}`);
}

export async function addExpense(formData: FormData) {
  await requireSession("/expenses");
  const amount = moneyCents(formData, "amount");
  // Allow $0 expenses — useful for placeholders (e.g. travel) you'll fill in later.
  if (amount < 0) fail("Amount can't be negative");

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
  revalidatePath("/dashboard");
}

export async function updateExpense(formData: FormData) {
  await requireSession("/expenses");
  const id = str(formData, "id");
  if (!id) fail("Expense id required");
  const amount = moneyCents(formData, "amount");
  if (amount < 0) fail("Amount can't be negative");

  const supabase = createAdminClient();
  const { error } = await supabase
    .from("crm_expenses")
    .update({
      incurred_at: str(formData, "incurred_at") || new Date().toISOString().slice(0, 10),
      category: str(formData, "category"),
      vendor: str(formData, "vendor"),
      amount_cents: amount,
      note: str(formData, "note"),
    })
    .eq("id", id);

  if (error) fail(error.message, `/expenses/${id}/edit`);
  revalidatePath("/expenses");
  revalidatePath("/reports");
  revalidatePath("/dashboard");
  redirect("/expenses");
}

export async function deleteExpense(formData: FormData) {
  await requireSession("/expenses");
  const id = str(formData, "id");
  if (!id) fail("Expense id required");
  const supabase = createAdminClient();
  const { error } = await supabase.from("crm_expenses").delete().eq("id", id);
  if (error) fail(error.message);
  revalidatePath("/expenses");
  revalidatePath("/reports");
  revalidatePath("/dashboard");
}
