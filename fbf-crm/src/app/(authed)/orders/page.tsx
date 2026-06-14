import Link from "next/link";
import { Pencil, Trash2, Truck, Download } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { formatMoney } from "@/lib/utils";
import { AddNewSection, ErrorBanner } from "@/components/ui/form-primitives";
import { SortHeader, parseSort } from "@/components/ui/sort-header";
import { OrderForm } from "./order-form";
import { deleteOrder, markShipped } from "./actions";

type OrderSortKey = "ordered_at" | "source" | "status" | "total_cents";
const ORDER_SORT_KEYS: Record<OrderSortKey, true> = {
  ordered_at: true,
  source: true,
  status: true,
  total_cents: true,
};

type Order = {
  id: string;
  ordered_at: string;
  source: string;
  status: string;
  total_cents: number;
  tracking_number: string | null;
  notes: string | null;
  crm_clients: { id: string; name: string } | null;
  crm_order_items: { qty: number; crm_products: { name: string } | null }[];
};

const SOURCE_LABEL: Record<string, string> = {
  manual: "Manual",
  venmo: "Venmo",
  cashapp: "CashApp",
  stripe: "Stripe",
};

const STATUS_STYLE: Record<string, string> = {
  pending: "border-info/40 bg-info/10 text-info",
  paid: "border-success/40 bg-success/10 text-success",
  shipped: "border-success/40 bg-success/10 text-success",
  refunded: "border-destructive/40 bg-destructive/10 text-destructive",
};

export default async function OrdersPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; sort?: string; dir?: string }>;
}) {
  const { error: errorParam, sort, dir } = await searchParams;
  const { sort: sortKey, dir: sortDir } = parseSort<OrderSortKey>(sort, dir, ORDER_SORT_KEYS, {
    sort: "ordered_at",
    dir: "desc",
  });
  const supabase = await createClient();
  const [clientsRes, productsRes, ordersRes, totalsRes] = await Promise.all([
    supabase.from("crm_clients").select("id, name").order("name"),
    supabase
      .from("crm_products")
      .select("id, name, sell_price_cents")
      .eq("active", true)
      .order("name"),
    supabase
      .from("crm_orders")
      .select(
        "id, ordered_at, source, status, total_cents, tracking_number, notes, crm_clients(id, name), crm_order_items(qty, crm_products(name))",
      )
      .order(sortKey, { ascending: sortDir === "asc", nullsFirst: false })
      .limit(200),
    // Lightweight pass over every non-refunded order for the stat cards.
    supabase
      .from("crm_orders")
      .select("total_cents, ordered_at")
      .neq("status", "refunded"),
  ]);

  const clients = clientsRes.data || [];
  const products = productsRes.data || [];
  const orders = (ordersRes.data || []) as unknown as Order[];

  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const yearStart = new Date(now.getFullYear(), 0, 1);
  let mtdRev = 0;
  let mtdCount = 0;
  let ytdRev = 0;
  let ytdCount = 0;
  let allRev = 0;
  let allCount = 0;
  for (const o of totalsRes.data || []) {
    const cents = o.total_cents || 0;
    const d = new Date(o.ordered_at);
    allRev += cents;
    allCount++;
    if (d >= yearStart) {
      ytdRev += cents;
      ytdCount++;
    }
    if (d >= monthStart) {
      mtdRev += cents;
      mtdCount++;
    }
  }
  const monthLabel = now.toLocaleString("en-US", { month: "long" });
  const yearLabel = now.getFullYear();

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="fbf-eyebrow mb-2">Sales</div>
          <h1 className="text-3xl font-black tracking-tight">Orders</h1>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            Manual entry + Venmo / CashApp imports. Click client name to see their history.
          </p>
        </div>
        <Link
          href="/api/export/orders.csv"
          className="inline-flex items-center gap-2 rounded-md border border-border bg-surface-2 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-foreground transition-colors hover:border-primary hover:text-primary"
        >
          <Download className="h-4 w-4" /> Export CSV
        </Link>
      </header>

      <ErrorBanner message={errorParam} />

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">
            {monthLabel} {yearLabel}
          </div>
          <div className="fbf-stat-num text-2xl font-black">{formatMoney(mtdRev)}</div>
          <div className="mt-1 text-xs text-subtle">
            {mtdCount} order{mtdCount === 1 ? "" : "s"} this month
          </div>
        </div>
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">Year {yearLabel}</div>
          <div className="fbf-stat-num text-2xl font-black">{formatMoney(ytdRev)}</div>
          <div className="mt-1 text-xs text-subtle">
            {ytdCount} order{ytdCount === 1 ? "" : "s"} YTD
          </div>
        </div>
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">Lifetime</div>
          <div className="fbf-stat-num text-2xl font-black">{formatMoney(allRev)}</div>
          <div className="mt-1 text-xs text-subtle">
            {allCount} order{allCount === 1 ? "" : "s"} total
          </div>
        </div>
      </div>

      {products.length === 0 ? (
        <div className="fbf-card text-sm text-muted-foreground">
          You need at least one{" "}
          <Link href="/products" className="text-primary underline">
            product
          </Link>{" "}
          before you can record an order.
        </div>
      ) : (
        <AddNewSection title="Add New Order" defaultOpen={!!errorParam}>
          <OrderForm clients={clients} products={products} />
        </AddNewSection>
      )}

      <div className="fbf-card !p-0 overflow-hidden">
        {orders.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            No orders yet — add your first one above.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-2 text-[11px] uppercase tracking-wider text-muted-foreground">
                  <SortHeader label="Date" k="ordered_at" activeKey={sortKey} activeDir={sortDir} basePath="/orders" />
                  <th className="px-5 py-3 text-left font-semibold">Client</th>
                  <th className="px-5 py-3 text-left font-semibold">Items / Note</th>
                  <SortHeader label="Source" k="source" activeKey={sortKey} activeDir={sortDir} basePath="/orders" />
                  <SortHeader label="Status" k="status" activeKey={sortKey} activeDir={sortDir} basePath="/orders" />
                  <SortHeader label="Total" k="total_cents" activeKey={sortKey} activeDir={sortDir} basePath="/orders" align="right" />
                  <th className="px-5 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => {
                  const itemSummary = o.crm_order_items
                    .map((it) => `${it.qty}× ${it.crm_products?.name ?? "?"}`)
                    .join(", ");
                  return (
                    <tr key={o.id} className="border-b border-border/60 transition-colors hover:bg-surface-2">
                      <td className="px-5 py-3 tabular-nums">
                        {new Date(o.ordered_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3 font-semibold">
                        {o.crm_clients ? (
                          <Link
                            href={`/clients/${o.crm_clients.id}`}
                            className="transition-colors hover:text-primary"
                          >
                            {o.crm_clients.name}
                          </Link>
                        ) : (
                          <span className="text-subtle">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-muted-foreground">
                        {itemSummary || (
                          <span className="text-xs italic text-subtle">{o.notes || "—"}</span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-xs text-muted-foreground">
                        {SOURCE_LABEL[o.source] || o.source}
                      </td>
                      <td className="px-5 py-3">
                        <span
                          className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${
                            STATUS_STYLE[o.status] || "border-border bg-surface-2 text-muted-foreground"
                          }`}
                        >
                          {o.status}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-right font-semibold tabular-nums">
                        {formatMoney(o.total_cents)}
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex items-center justify-end gap-2">
                          {o.status !== "shipped" && o.status !== "refunded" && (
                            <form action={markShipped}>
                              <input type="hidden" name="id" value={o.id} />
                              <button
                                type="submit"
                                aria-label="Mark shipped"
                                title="Mark as shipped"
                                className="grid h-8 w-8 place-items-center rounded-md border border-border bg-surface-2 text-muted-foreground transition-colors hover:border-success hover:text-success"
                              >
                                <Truck className="h-4 w-4" />
                              </button>
                            </form>
                          )}
                          <Link
                            href={`/orders/${o.id}/edit`}
                            aria-label="Edit order"
                            title="Edit"
                            className="grid h-8 w-8 place-items-center rounded-md border border-border bg-surface-2 text-muted-foreground transition-colors hover:border-primary hover:text-primary"
                          >
                            <Pencil className="h-4 w-4" />
                          </Link>
                          <form action={deleteOrder}>
                            <input type="hidden" name="id" value={o.id} />
                            <button
                              type="submit"
                              aria-label="Delete order"
                              title="Delete (refunds inventory)"
                              className="grid h-8 w-8 place-items-center rounded-md border border-border bg-surface-2 text-muted-foreground transition-colors hover:border-destructive hover:text-destructive"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </form>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
