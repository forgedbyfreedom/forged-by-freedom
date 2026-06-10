import { cookies } from "next/headers";
import { redirect } from "next/navigation";

// Cookie-presence auth check for server actions. The Supabase auth cookie
// is named sb-<project_ref>-auth-token. If it's absent, the user can't have
// passed middleware to reach the page that hosts this action — so we treat
// it as a session loss and bounce to login.
//
// We deliberately don't use supabase.auth.getUser() inside server actions
// because the @supabase/ssr cookie adapter exhibits a known quirk where it
// reports "Auth session missing!" even when the request carries valid auth
// cookies, on certain Next.js 15 paths.
const PROJECT_REF = (process.env.NEXT_PUBLIC_SUPABASE_URL || "")
  .replace(/^https?:\/\//, "")
  .split(".")[0];

export async function requireSession(returnTo: string) {
  const store = await cookies();
  const authCookieName = `sb-${PROJECT_REF}-auth-token`;
  const has =
    store.get(authCookieName) ||
    // Some Supabase setups chunk large cookies into .0/.1 suffixes.
    store.get(`${authCookieName}.0`);
  if (!has) {
    redirect(`/login?error=${encodeURIComponent("Session expired — sign in again")}&next=${returnTo}`);
  }
}
