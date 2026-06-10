import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { formatMoney } from "@/lib/utils";
import { AddNewSection, ErrorBanner } from "@/components/ui/form-primitives";
import { OrderForm } from "./order-form";

type Order = {
  id: string;
  ordered_at: string;
  source: string;
  status: string;
  total_cents: number;
  tracking_number: string | null;
  crm_clients: { name: string } | null;
  crm_order_items: { qty: number; crm_products: { name: string } | null }[];
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
  searchParams: Promise<{ error?: string }>;
}) {
  const { error: errorParam } = await searchParams;
  const supabase = await createClient();
  const [clientsRes, productsRes, ordersRes] = await Promise.all([
    supabase.from("crm_clients").select("id, name").order("name"),
    supabase
      .from("crm_products")
      .select("id, name, sell_price_cents")
      .eq("active", true)
      .order("name"),
    supabase
      .from("crm_orders")
      .select(
        "id, ordered_at, source, status, total_cents, tracking_number, crm_clients(name), crm_order_items(qty, crm_products(name))",
      )
      .order("ordered_at", { ascending: false })
      .limit(100),
  ]);

  const clients = clientsRes.data || [];
  const products = productsRes.data || [];
  const orders = (ordersRes.data || []) as unknown as Order[];

  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Sales</div>
        <h1 className="text-3xl font-black tracking-tight">Orders</h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Manual order entry. Stripe auto-import lands in a later session.
        </p>
      </header>

      <ErrorBanner message={errorParam} />

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
                <tr className="border-b border-border bg-surface-2 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="px-5 py-3 font-semibold">Date</th>
                  <th className="px-5 py-3 font-semibold">Client</th>
                  <th className="px-5 py-3 font-semibold">Items</th>
                  <th className="px-5 py-3 font-semibold">Source</th>
                  <th className="px-5 py-3 font-semibold">Tracking</th>
                  <th className="px-5 py-3 font-semibold">Status</th>
                  <th className="px-5 py-3 text-right font-semibold">Total</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id} className="border-b border-border/60 transition-colors hover:bg-surface-2">
                    <td className="px-5 py-3 tabular-nums">
                      {new Date(o.ordered_at).toLocaleDateString()}
                    </td>
                    <td className="px-5 py-3 font-semibold">
                      {o.crm_clients?.name || <span className="text-subtle">—</span>}
                    </td>
                    <td className="px-5 py-3 text-muted-foreground">
                      {o.crm_order_items
                        .map((it) => `${it.qty}× ${it.crm_products?.name ?? "?"}`)
                        .join(", ")}
                    </td>
                    <td className="px-5 py-3 text-xs text-muted-foreground">{o.source}</td>
                    <td className="px-5 py-3 text-xs text-muted-foreground">
                      {o.tracking_number || "—"}
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
