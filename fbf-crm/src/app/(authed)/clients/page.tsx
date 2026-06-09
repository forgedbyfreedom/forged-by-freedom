import { createClient } from "@/lib/supabase/server";

export default async function ClientsPage() {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("crm_clients_with_stats")
    .select("id, name, email, last_contact_at, lifetime_revenue_cents, order_count")
    .order("last_contact_at", { ascending: false, nullsFirst: false })
    .limit(50);

  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Customer Records</div>
        <h1 className="text-3xl font-black tracking-tight">Clients</h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Searchable client list with product history, lifetime revenue, and last contact.
        </p>
      </header>

      {error ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error.message}
        </div>
      ) : (
        <div className="fbf-card !p-0 overflow-hidden">
          {(data?.length || 0) === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No clients yet. Adding clients ships next session.
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {data!.map((c) => (
                <li key={c.id} className="px-5 py-4 transition-colors hover:bg-surface-2">
                  <div className="font-semibold text-foreground">{c.name}</div>
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
