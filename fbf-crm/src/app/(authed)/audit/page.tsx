import { createAdminClient } from "@/lib/supabase/admin";

type AuditRow = {
  id: number;
  table_name: string;
  record_id: string | null;
  action: "INSERT" | "UPDATE" | "DELETE";
  changed_at: string;
  data: Record<string, unknown> | null;
};

const ACTION_STYLE: Record<string, string> = {
  INSERT: "border-success/40 bg-success/10 text-success",
  UPDATE: "border-info/40 bg-info/10 text-info",
  DELETE: "border-destructive/40 bg-destructive/10 text-destructive",
};

const TABLE_LABEL: Record<string, string> = {
  crm_clients: "Client",
  crm_products: "Product",
  crm_inventory_lots: "Lot",
  crm_orders: "Order",
  crm_order_items: "Order item",
  crm_expenses: "Expense",
  crm_households: "Household",
};

function summarize(row: AuditRow): string {
  if (!row.data) return "";
  const d = row.data as Record<string, unknown>;
  // Updates store { before, after } — fall back to before for label.
  const subject = (d.after as Record<string, unknown>) || (d.before as Record<string, unknown>) || d;
  const name = subject?.name;
  if (typeof name === "string" && name.length > 0) return name;
  const note = subject?.note;
  if (typeof note === "string" && note.length > 0) return note.slice(0, 80);
  const total = subject?.total_cents;
  if (typeof total === "number") return `$${(total / 100).toFixed(2)}`;
  const amount = subject?.amount_cents;
  if (typeof amount === "number") return `$${(amount / 100).toFixed(2)}`;
  const qty = subject?.qty_on_hand;
  if (typeof qty === "number") return `qty ${qty}`;
  return row.record_id?.slice(0, 8) || "";
}

export default async function AuditPage() {
  const supabase = createAdminClient();
  const { data } = await supabase
    .from("crm_audit_log")
    .select("id, table_name, record_id, action, changed_at, data")
    .order("changed_at", { ascending: false })
    .limit(200);

  const rows = (data || []) as AuditRow[];

  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">History</div>
        <h1 className="text-3xl font-black tracking-tight">Audit Log</h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Every insert, update, and delete across all CRM tables. Last 200 events.
        </p>
      </header>

      <div className="fbf-card !p-0 overflow-hidden">
        {rows.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            No activity recorded yet.
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {rows.map((r) => (
              <li
                key={r.id}
                className="flex items-start justify-between gap-3 px-5 py-3 transition-colors hover:bg-surface-2"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${
                        ACTION_STYLE[r.action] || "border-border bg-surface-2"
                      }`}
                    >
                      {r.action}
                    </span>
                    <span className="font-semibold">
                      {TABLE_LABEL[r.table_name] || r.table_name}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      {summarize(r)}
                    </span>
                  </div>
                </div>
                <div className="shrink-0 text-xs text-subtle">
                  {new Date(r.changed_at).toLocaleString()}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
