import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Mail, Phone, MapPin, Clock } from "lucide-react";
import { createAdminClient } from "@/lib/supabase/admin";
import { formatMoney } from "@/lib/utils";

type OrderWithItems = {
  id: string;
  ordered_at: string;
  source: string;
  status: string;
  total_cents: number;
  subtotal_cents: number;
  shipping_cents: number;
  tax_cents: number;
  tracking_number: string | null;
  carrier: string | null;
  notes: string | null;
  crm_order_items: {
    qty: number;
    unit_price_cents: number;
    line_total_cents: number;
    crm_products: { id: string; name: string; sku: string | null } | null;
  }[];
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

export default async function ClientDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = createAdminClient();

  const { data: client } = await supabase
    .from("crm_clients")
    .select(
      "id, name, email, phone, address_line1, address_line2, city, state, postal_code, country, notes, last_contact_at, created_at",
    )
    .eq("id", id)
    .maybeSingle();

  if (!client) notFound();

  const { data: ordersData } = await supabase
    .from("crm_orders")
    .select(
      "id, ordered_at, source, status, total_cents, subtotal_cents, shipping_cents, tax_cents, tracking_number, carrier, notes, crm_order_items(qty, unit_price_cents, line_total_cents, crm_products(id, name, sku))",
    )
    .eq("client_id", id)
    .order("ordered_at", { ascending: false });

  const orders = (ordersData || []) as unknown as OrderWithItems[];

  // Aggregate stats (also computed by the view, but recompute here so the page
  // works for clients with no orders too).
  const nonRefunded = orders.filter((o) => o.status !== "refunded");
  const orderCount = nonRefunded.length;
  const lifetime = nonRefunded.reduce((s, o) => s + (o.total_cents || 0), 0);
  const largest = nonRefunded.reduce((m, o) => Math.max(m, o.total_cents || 0), 0);
  const avg = orderCount > 0 ? Math.round(lifetime / orderCount) : 0;
  const lastOrder = orders[0]?.ordered_at;

  // Per-product totals so they can see at a glance what this client buys.
  const productTotals = new Map<
    string,
    { name: string; sku: string | null; qty: number; revenue_cents: number }
  >();
  for (const o of nonRefunded) {
    for (const it of o.crm_order_items) {
      if (!it.crm_products) continue;
      const key = it.crm_products.id;
      const prev = productTotals.get(key) || {
        name: it.crm_products.name,
        sku: it.crm_products.sku,
        qty: 0,
        revenue_cents: 0,
      };
      prev.qty += it.qty;
      prev.revenue_cents += it.line_total_cents;
      productTotals.set(key, prev);
    }
  }
  const topProducts = Array.from(productTotals.values()).sort(
    (a, b) => b.revenue_cents - a.revenue_cents,
  );

  const addressLines = [
    client.address_line1,
    client.address_line2,
    [client.city, client.state, client.postal_code].filter(Boolean).join(", "),
    client.country,
  ].filter(Boolean);

  return (
    <div className="space-y-8">
      <div>
        <Link
          href="/clients"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary"
        >
          <ArrowLeft className="h-3 w-3" /> All clients
        </Link>
        <div className="fbf-eyebrow mt-3 mb-2">Client</div>
        <h1 className="text-3xl font-black tracking-tight">{client.name}</h1>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Contact card */}
        <div className="fbf-card lg:col-span-1">
          <div className="fbf-eyebrow mb-4">Contact</div>
          <div className="space-y-3 text-sm">
            {client.email && (
              <div className="flex items-start gap-2">
                <Mail className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <a
                  href={`mailto:${client.email}`}
                  className="break-all hover:text-primary"
                >
                  {client.email}
                </a>
              </div>
            )}
            {client.phone && (
              <div className="flex items-start gap-2">
                <Phone className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <a href={`tel:${client.phone}`} className="hover:text-primary">
                  {client.phone}
                </a>
              </div>
            )}
            {addressLines.length > 0 && (
              <div className="flex items-start gap-2">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="text-muted-foreground">
                  {addressLines.map((l, i) => (
                    <div key={i}>{l}</div>
                  ))}
                </div>
              </div>
            )}
            {client.last_contact_at && (
              <div className="flex items-start gap-2">
                <Clock className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="text-muted-foreground">
                  Last contact:{" "}
                  {new Date(client.last_contact_at).toLocaleDateString()}
                </div>
              </div>
            )}
            {!client.email && !client.phone && addressLines.length === 0 && (
              <div className="text-sm text-muted-foreground">
                No contact details on file.
              </div>
            )}
          </div>
          {client.notes && (
            <div className="mt-5 border-t border-border pt-4">
              <div className="fbf-eyebrow mb-2 text-xs">Notes</div>
              <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                {client.notes}
              </p>
            </div>
          )}
        </div>

        {/* Lifetime stats */}
        <div className="lg:col-span-2 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="fbf-card">
            <div className="fbf-eyebrow mb-2 !text-muted-foreground">Orders</div>
            <div className="fbf-stat-num text-2xl font-black tabular-nums">{orderCount}</div>
          </div>
          <div className="fbf-card">
            <div className="fbf-eyebrow mb-2 !text-muted-foreground">Lifetime</div>
            <div className="fbf-stat-num text-2xl font-black">{formatMoney(lifetime)}</div>
          </div>
          <div className="fbf-card">
            <div className="fbf-eyebrow mb-2 !text-muted-foreground">Avg Order</div>
            <div className="fbf-stat-num text-2xl font-black">{formatMoney(avg)}</div>
          </div>
          <div className="fbf-card">
            <div className="fbf-eyebrow mb-2 !text-muted-foreground">Largest</div>
            <div className="fbf-stat-num text-2xl font-black">{formatMoney(largest)}</div>
          </div>
          {lastOrder && (
            <div className="fbf-card sm:col-span-2 lg:col-span-4">
              <div className="fbf-eyebrow mb-2 !text-muted-foreground">Last Order</div>
              <div className="text-base font-semibold">
                {new Date(lastOrder).toLocaleDateString(undefined, {
                  weekday: "short",
                  month: "long",
                  day: "numeric",
                  year: "numeric",
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* What they buy */}
      {topProducts.length > 0 && (
        <div className="fbf-card !p-0 overflow-hidden">
          <div className="border-b border-border px-5 py-4">
            <div className="fbf-eyebrow">What They Buy</div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-2 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="px-5 py-3 font-semibold">Product</th>
                  <th className="px-5 py-3 font-semibold">SKU</th>
                  <th className="px-5 py-3 text-right font-semibold">Qty (lifetime)</th>
                  <th className="px-5 py-3 text-right font-semibold">Revenue</th>
                </tr>
              </thead>
              <tbody>
                {topProducts.map((p) => (
                  <tr
                    key={p.name + (p.sku || "")}
                    className="border-b border-border/60 transition-colors hover:bg-surface-2"
                  >
                    <td className="px-5 py-3 font-semibold">{p.name}</td>
                    <td className="px-5 py-3 text-muted-foreground">{p.sku || "—"}</td>
                    <td className="px-5 py-3 text-right tabular-nums">{p.qty}</td>
                    <td className="px-5 py-3 text-right tabular-nums">
                      {formatMoney(p.revenue_cents)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Order history */}
      <div className="fbf-card !p-0 overflow-hidden">
        <div className="border-b border-border px-5 py-4">
          <div className="fbf-eyebrow">Order History</div>
        </div>
        {orders.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            No orders for this client yet.
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {orders.map((o) => (
              <li key={o.id} className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-base font-semibold">
                      {new Date(o.ordered_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span>{SOURCE_LABEL[o.source] || o.source}</span>
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 ${
                          STATUS_STYLE[o.status] ||
                          "border-border bg-surface-2 text-muted-foreground"
                        }`}
                      >
                        {o.status}
                      </span>
                      {o.tracking_number && (
                        <span>
                          {o.carrier || "Tracking"}: {o.tracking_number}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xl font-black tabular-nums">
                      {formatMoney(o.total_cents)}
                    </div>
                    {o.shipping_cents + o.tax_cents > 0 && (
                      <div className="text-xs text-subtle">
                        Sub {formatMoney(o.subtotal_cents)} · Ship{" "}
                        {formatMoney(o.shipping_cents)} · Tax {formatMoney(o.tax_cents)}
                      </div>
                    )}
                  </div>
                </div>
                {o.crm_order_items.length > 0 && (
                  <ul className="mt-3 space-y-1 text-sm">
                    {o.crm_order_items.map((it, i) => (
                      <li
                        key={i}
                        className="flex items-center justify-between rounded-md border border-border bg-surface-2/50 px-3 py-2"
                      >
                        <span>
                          <span className="font-semibold tabular-nums">{it.qty}×</span>{" "}
                          {it.crm_products?.name || "(deleted product)"}
                          {it.crm_products?.sku && (
                            <span className="ml-2 text-xs text-subtle">{it.crm_products.sku}</span>
                          )}
                        </span>
                        <span className="text-muted-foreground tabular-nums">
                          {formatMoney(it.unit_price_cents)} ea ·{" "}
                          <span className="text-foreground">
                            {formatMoney(it.line_total_cents)}
                          </span>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                {o.notes && (
                  <div className="mt-3 text-xs text-subtle">{o.notes}</div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
