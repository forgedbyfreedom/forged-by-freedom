import { createClient } from "@/lib/supabase/server";

export default async function ClientsPage() {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("crm_clients_with_stats")
    .select("id, name, email, last_contact_at, lifetime_revenue_cents, order_count")
    .order("last_contact_at", { ascending: false, nullsFirst: false })
    .limit(50);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Clients</h1>
        <p className="text-sm text-muted-foreground">
          Client list, search, and per-client product history will live here.
        </p>
      </header>
      {error ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error.message}
        </div>
      ) : (
        <div className="rounded-lg border bg-card">
          {(data?.length || 0) === 0 ? (
            <div className="p-6 text-sm text-muted-foreground">No clients yet.</div>
          ) : (
            <ul className="divide-y">
              {data!.map((c) => (
                <li key={c.id} className="p-4">
                  <div className="font-medium">{c.name}</div>
                  <div className="text-xs text-muted-foreground">{c.email}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
