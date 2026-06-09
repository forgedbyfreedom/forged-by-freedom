"use server";

import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

const OWNER_EMAIL = (process.env.NEXT_PUBLIC_OWNER_EMAIL || "").toLowerCase().trim();

export async function login(formData: FormData) {
  const email = String(formData.get("email") || "").toLowerCase().trim();
  const password = String(formData.get("password") || "");

  if (OWNER_EMAIL && email !== OWNER_EMAIL) {
    return redirect("/login?error=not_authorized");
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) {
    return redirect(`/login?error=${encodeURIComponent(error.message)}`);
  }
  redirect("/dashboard");
}

export async function signup(formData: FormData) {
  const email = String(formData.get("email") || "").toLowerCase().trim();
  const password = String(formData.get("password") || "");

  if (OWNER_EMAIL && email !== OWNER_EMAIL) {
    return redirect("/login?error=not_authorized");
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.signUp({ email, password });
  if (error) {
    return redirect(`/login?error=${encodeURIComponent(error.message)}`);
  }
  redirect("/dashboard");
}
