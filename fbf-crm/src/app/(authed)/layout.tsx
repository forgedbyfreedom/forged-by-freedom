import { createClient } from "@/lib/supabase/server";
import { Sidebar } from "@/components/sidebar";
import { RealtimeRefresher } from "@/components/realtime-refresher";

export default async function AuthedLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return (
    <div className="flex min-h-screen flex-col bg-background md:flex-row">
      <RealtimeRefresher />
      <Sidebar email={user?.email} />
      <main className="flex-1 p-5 md:p-10">{children}</main>
    </div>
  );
}
