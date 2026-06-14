import Link from "next/link";
import { Download } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { formatMoney } from "@/lib/utils";

type OrderRow = {
  ordered_at: string;
  total_cents: number;
  status: string;
  crm_order_items: { qty: number; unit_cost_cents: number }[];
};

type ExpenseRow = {
  incurred_at: string;
  amount_cents: number;
  category: string | null;
};

function monthKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
function monthLabel(key: string) {
  const [y, m] = key.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleString("en-US", { month: "short", year: "numeric" });
}

export default async function ReportsPage() {
  const supabase = await createClient();

  const [ordersRes, expensesRes] = await Promise.all([
    supabase
      .from("crm_orders")
      .select("ordered_at, total_cents, status, crm_order_items(qty, unit_cost_cents)")
      .neq("status", "refunded")
      .order("ordered_at", { ascending: false }),
    supabase.from("crm_expenses").select("incurred_at, amount_cents, category"),
  ]);

  const orders = (ordersRes.data || []) as unknown as OrderRow[];
  const expenses = (expensesRes.data || []) as ExpenseRow[];

  type Bucket = {
    revenue: number;
    cogs: number;
    expenses: number;
    orderCount: number;
  };
  const byMonth = new Map<string, Bucket>();
  const byYear = new Map<string, Bucket>();
  const ensure = (m: Map<string, Bucket>, k: string): Bucket => {
    let b = m.get(k);
    if (!b) {
      b = { revenue: 0, cogs: 0, expenses: 0, orderCount: 0 };
      m.set(k, b);
    }
    return b;
  };

  for (const o of orders) {
    const d = new Date(o.ordered_at);
    const mk = monthKey(d);
    const yk = String(d.getFullYear());
    const mb = ensure(byMonth, mk);
    const yb = ensure(byYear, yk);
    mb.revenue += o.total_cents || 0;
    yb.revenue += o.total_cents || 0;
    mb.orderCount += 1;
    yb.orderCount += 1;
    for (const it of o.crm_order_items || []) {
      const c = (it.qty || 0) * (it.unit_cost_cents || 0);
      mb.cogs += c;
      yb.cogs += c;
    }
  }
  for (const e of expenses) {
    const d = new Date(e.incurred_at);
    const mk = monthKey(d);
    const yk = String(d.getFullYear());
    ensure(byMonth, mk).expenses += e.amount_cents || 0;
    ensure(byYear, yk).expenses += e.amount_cents || 0;
  }

  const monthsSorted = Array.from(byMonth.keys()).sort().reverse();
  const yearsSorted = Array.from(byYear.keys()).sort().reverse();

  // Lifetime totals
  let lifeRev = 0;
  let lifeCogs = 0;
  let lifeExp = 0;
  for (const b of byMonth.values()) {
    lifeRev += b.revenue;
    lifeCogs += b.cogs;
    lifeExp += b.expenses;
  }
  const lifeGross = lifeRev - lifeCogs;
  const lifeNet = lifeGross - lifeExp;

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="fbf-eyebrow mb-2">Analytics</div>
          <h1 className="text-3xl font-black tracking-tight">P&amp;L Reports</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Revenue, cost of goods sold, expenses, and net profit by month and by year. Refunded
            orders are excluded.
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/api/export/orders.csv"
            className="inline-flex items-center gap-2 rounded-md border border-border bg-surface-2 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-foreground transition-colors hover:border-primary hover:text-primary"
          >
            <Download className="h-4 w-4" /> Orders CSV
          </Link>
          <Link
            href="/api/export/expenses.csv"
            className="inline-flex items-center gap-2 rounded-md border border-border bg-surface-2 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-foreground transition-colors hover:border-primary hover:text-primary"
          >
            <Download className="h-4 w-4" /> Expenses CSV
          </Link>
        </div>
      </header>

      {/* Lifetime summary */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">Lifetime Revenue</div>
          <div className="fbf-stat-num text-2xl font-black">{formatMoney(lifeRev)}</div>
        </div>
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">Lifetime COGS</div>
          <div className="text-2xl font-black tabular-nums">{formatMoney(lifeCogs)}</div>
        </div>
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">Lifetime Expenses</div>
          <div className="text-2xl font-black tabular-nums">{formatMoney(lifeExp)}</div>
        </div>
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">Lifetime Net Profit</div>
          <div
            className={`text-2xl font-black tabular-nums ${
              lifeNet >= 0 ? "fbf-stat-num" : "text-destructive"
            }`}
          >
            {formatMoney(lifeNet)}
          </div>
        </div>
      </div>

      {/* Yearly */}
      <div className="fbf-card !p-0 overflow-hidden">
        <div className="border-b border-border px-5 py-4">
          <div className="fbf-eyebrow">By Year</div>
        </div>
        <PLTable
          rows={yearsSorted.map((y) => ({
            label: y,
            ...byYear.get(y)!,
          }))}
        />
      </div>

      {/* Monthly */}
      <div className="fbf-card !p-0 overflow-hidden">
        <div className="border-b border-border px-5 py-4">
          <div className="fbf-eyebrow">By Month</div>
        </div>
        <PLTable
          rows={monthsSorted.map((m) => ({
            label: monthLabel(m),
            ...byMonth.get(m)!,
          }))}
        />
      </div>
    </div>
  );
}

function PLTable({
  rows,
}: {
  rows: { label: string; revenue: number; cogs: number; expenses: number; orderCount: number }[];
}) {
  if (rows.length === 0) {
    return (
      <div className="p-8 text-center text-sm text-muted-foreground">
        No data yet — record orders and expenses to populate.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-2 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
            <th className="px-5 py-3 font-semibold">Period</th>
            <th className="px-5 py-3 text-right font-semibold">Orders</th>
            <th className="px-5 py-3 text-right font-semibold">Revenue</th>
            <th className="px-5 py-3 text-right font-semibold">COGS</th>
            <th className="px-5 py-3 text-right font-semibold">Gross</th>
            <th className="px-5 py-3 text-right font-semibold">Expenses</th>
            <th className="px-5 py-3 text-right font-semibold">Net</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const gross = r.revenue - r.cogs;
            const net = gross - r.expenses;
            return (
              <tr
                key={r.label}
                className="border-b border-border/60 transition-colors hover:bg-surface-2"
              >
                <td className="px-5 py-3 font-semibold">{r.label}</td>
                <td className="px-5 py-3 text-right tabular-nums text-muted-foreground">
                  {r.orderCount}
                </td>
                <td className="px-5 py-3 text-right tabular-nums">{formatMoney(r.revenue)}</td>
                <td className="px-5 py-3 text-right tabular-nums text-muted-foreground">
                  {formatMoney(r.cogs)}
                </td>
                <td className="px-5 py-3 text-right tabular-nums">{formatMoney(gross)}</td>
                <td className="px-5 py-3 text-right tabular-nums text-muted-foreground">
                  {formatMoney(r.expenses)}
                </td>
                <td
                  className={`px-5 py-3 text-right font-semibold tabular-nums ${
                    net >= 0 ? "fbf-stat-num" : "text-destructive"
                  }`}
                >
                  {formatMoney(net)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
