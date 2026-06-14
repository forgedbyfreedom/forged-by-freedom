import { createAdminClient } from "@/lib/supabase/admin";
import { requireSession } from "@/lib/auth";
import { csvResponse, csvRow, moneyDollars } from "@/lib/csv-export";

export async function GET() {
  await requireSession("/reports");
  const supabase = createAdminClient();

  const { data } = await supabase
    .from("crm_orders")
    .select(
      "id, ordered_at, source, status, total_cents, subtotal_cents, shipping_cents, tax_cents, tracking_number, carrier, notes, external_id, crm_clients(name, email), crm_order_items(qty, unit_price_cents, unit_cost_cents, line_total_cents, crm_products(name, sku))",
    )
    .order("ordered_at", { ascending: false });

  const headers = [
    "order_id",
    "date",
    "source",
    "status",
    "client_name",
    "client_email",
    "subtotal_usd",
    "shipping_usd",
    "tax_usd",
    "total_usd",
    "items",
    "cogs_usd",
    "gross_profit_usd",
    "tracking_number",
    "carrier",
    "external_id",
    "notes",
  ];
  const lines = [csvRow(headers)];

  for (const o of data || []) {
    const client = (o.crm_clients as unknown as { name: string; email: string | null } | null);
    const items = ((o.crm_order_items as unknown as {
      qty: number;
      unit_price_cents: number;
      unit_cost_cents: number;
      line_total_cents: number;
      crm_products: { name: string; sku: string | null } | null;
    }[]) || []);

    const itemSummary = items
      .map((it) => `${it.qty}x ${it.crm_products?.name || "?"}`)
      .join("; ");
    const cogs = items.reduce((s, it) => s + (it.qty || 0) * (it.unit_cost_cents || 0), 0);
    const gross = (o.total_cents || 0) - cogs;

    lines.push(
      csvRow([
        o.id,
        o.ordered_at,
        o.source,
        o.status,
        client?.name || "",
        client?.email || "",
        moneyDollars(o.subtotal_cents),
        moneyDollars(o.shipping_cents),
        moneyDollars(o.tax_cents),
        moneyDollars(o.total_cents),
        itemSummary,
        moneyDollars(cogs),
        moneyDollars(gross),
        o.tracking_number || "",
        o.carrier || "",
        o.external_id || "",
        o.notes || "",
      ]),
    );
  }

  const today = new Date().toISOString().slice(0, 10);
  return csvResponse(`fbf-orders-${today}.csv`, lines.join("\n"));
}
