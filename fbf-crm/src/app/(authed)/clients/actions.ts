"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { str } from "@/lib/forms";

function fail(msg: string): never {
  redirect(`/clients?error=${encodeURIComponent(msg)}`);
}

export async function addClient(formData: FormData) {
  const name = str(formData, "name");
  if (!name) fail("Name is required");

  const supabase = await createClient();
  const { error } = await supabase.from("crm_clients").insert({
    name,
    email: str(formData, "email"),
    phone: str(formData, "phone"),
    address_line1: str(formData, "address_line1"),
    address_line2: str(formData, "address_line2"),
    city: str(formData, "city"),
    state: str(formData, "state"),
    postal_code: str(formData, "postal_code"),
    country: str(formData, "country") || "US",
    notes: str(formData, "notes"),
    last_contact_at: str(formData, "last_contact_at") || null,
  });

  if (error) fail(error.message);
  revalidatePath("/clients");
}
