import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { formatMoney } from "@/lib/utils";

type LotRow = {
  product_id: string;
  qty_on_hand: number;
  unit_cost_cents: number;
};

type ProductRow = {
  id: string;
  name: string;
  sell_price_cents: number;
  active: boolean;
};

type LatestOrder = {
  id: string;
  ordered_at: string;
  source: string;
  status: string;
  total_cents: number;
  crm_clients: { name: string } | null;
};

const SOURCE_LABEL: Record<string, string> = {
  manual: "Manual",
  venmo: "Venmo",
  cashapp: "CashApp",
  stripe: "Stripe",
};

export default async function DashboardPage() {
  const supabase = await createClient();

  const [totalsRes, lotsRes, productsRes, latestRes] = await Promise.all([
    supabase
      .from("crm_orders")
      .select("total_cents, ordered_at")
      .neq("status", "refunded"),
    supabase.from("crm_inventory_lots").select("product_id, qty_on_hand, unit_cost_cents"),
    supabase.from("crm_products").select("id, name, sell_price_cents, active"),
    supabase
      .from("crm_orders")
      .select("id, ordered_at, source, status, total_cents, crm_clients(name)")
      .order("ordered_at", { ascending: false })
      .limit(5),
  ]);

  // ── MTD revenue + order count ──────────────────────────────
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  let mtdRev = 0;
  let mtdCount = 0;
  for (const o of totalsRes.data || []) {
    if (new Date(o.ordered_at) >= monthStart) {
      mtdRev += o.total_cents || 0;
      mtdCount++;
    }
  }

  // ── Inventory at cost + at resale ──────────────────────────
  const lots = (lotsRes.data || []) as LotRow[];
  const products = (productsRes.data || []) as ProductRow[];
  const sellPriceById = new Map(products.map((p) => [p.id, p.sell_price_cents]));

  const onHandByProduct = new Map<string, number>();
  let invCost = 0;
  for (const l of lots) {
    const qty = l.qty_on_hand || 0;
    invCost += qty * (l.unit_cost_cents || 0);
    onHandByProduct.set(l.product_id, (onHandByProduct.get(l.product_id) || 0) + qty);
  }
  let invResale = 0;
  for (const [pid, qty] of onHandByProduct) {
    invResale += qty * (sellPriceById.get(pid) || 0);
  }

  // ── Low-stock alerts: active products with on_hand <= 5 ────
  const lowStock = products
    .filter((p) => p.active)
    .map((p) => ({ ...p, on_hand: onHandByProduct.get(p.id) || 0 }))
    .filter((p) => p.on_hand <= 5)
    .sort((a, b) => a.on_hand - b.on_hand)
    .slice(0, 8);

  const latest = (latestRes.data || []) as unknown as LatestOrder[];
  const monthLabel = now.toLocaleString("en-US", { month: "long" });

  return (
    <div className="space-y-8">
      <header>
        <div className="fbf-eyebrow mb-2">Overview</div>
        <h1 className="text-3xl font-black tracking-tight">Dashboard</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {monthLabel} {now.getFullYear()} so far.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">Revenue (MTD)</div>
          <div className="fbf-stat-num text-2xl font-black">{formatMoney(mtdRev)}</div>
          <div className="mt-1 text-xs text-subtle">
            {mtdCount} order{mtdCount === 1 ? "" : "s"} this month
          </div>
        </div>
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">Orders (MTD)</div>
          <div className="fbf-stat-num text-2xl font-black tabular-nums">{mtdCount}</div>
          <div className="mt-1 text-xs text-subtle">
            Across {(totalsRes.data || []).length.toLocaleString()} all-time
          </div>
        </div>
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">Inventory @ Cost</div>
          <div className="fbf-stat-num text-2xl font-black">{formatMoney(invCost)}</div>
          <div className="mt-1 text-xs text-subtle">On-hand × unit cost</div>
        </div>
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">Inventory @ Resale</div>
          <div className="fbf-stat-num text-2xl font-black">{formatMoney(invResale)}</div>
          <div className="mt-1 text-xs text-subtle">On-hand × sell price</div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="fbf-card !p-0 overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div className="fbf-eyebrow">Low-Stock Alerts</div>
            <Link href="/inventory" className="text-xs text-muted-foreground hover:text-primary">
              View inventory →
            </Link>
          </div>
          {lowStock.length === 0 ? (
            <div className="p-6 text-sm text-muted-foreground">
              No active products are running low. Threshold: 5 or fewer on hand.
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {lowStock.map((p) => (
                <li
                  key={p.id}
                  className="flex items-center justify-between px-5 py-3 transition-colors hover:bg-surface-2"
                >
                  <div>
                    <div className="font-semibold">{p.name}</div>
                    <div className="text-xs text-subtle">
                      Sell {formatMoney(p.sell_price_cents)}
                    </div>
                  </div>
                  <span
                    className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${
                      p.on_hand === 0
                        ? "border-destructive/40 bg-destructive/10 text-destructive"
                        : "border-info/40 bg-info/10 text-info"
                    }`}
                  >
                    {p.on_hand === 0 ? "Depleted" : `${p.on_hand} on hand`}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="fbf-card !p-0 overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div className="fbf-eyebrow">Latest Orders</div>
            <Link href="/orders" className="text-xs text-muted-foreground hover:text-primary">
              View all →
            </Link>
          </div>
          {latest.length === 0 ? (
            <div className="p-6 text-sm text-muted-foreground">
              No orders yet. Add one on the Orders page or import a Venmo/CashApp CSV.
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {latest.map((o) => (
                <li
                  key={o.id}
                  className="flex items-center justify-between gap-3 px-5 py-3 transition-colors hover:bg-surface-2"
                >
                  <div className="min-w-0">
                    <div className="truncate font-semibold">
                      {o.crm_clients?.name || (
                        <span className="text-subtle">(no client)</span>
                      )}
                    </div>
                    <div className="text-xs text-subtle">
                      {new Date(o.ordered_at).toLocaleDateString()} ·{" "}
                      {SOURCE_LABEL[o.source] || o.source} · {o.status}
                    </div>
                  </div>
                  <div className="font-semibold tabular-nums">{formatMoney(o.total_cents)}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
