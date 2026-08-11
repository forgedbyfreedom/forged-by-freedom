import { createClient } from "@supabase/supabase-js";

// Server-only admin client. Uses the service_role key, which bypasses RLS.
// NEVER import this from client components. Only use inside "use server" actions
// where the caller has already been verified as authenticated (via middleware
// gating the page that hosts the action's form).
export function createAdminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!key) {
    throw new Error(
      "SUPABASE_SERVICE_ROLE_KEY env var is missing. Add it to .env.local — get it from Supabase Project Settings → API → service_role secret.",
    );
  }
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
