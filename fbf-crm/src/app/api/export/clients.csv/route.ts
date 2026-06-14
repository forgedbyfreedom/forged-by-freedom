import { createAdminClient } from "@/lib/supabase/admin";
import { requireSession } from "@/lib/auth";
import { csvResponse, csvRow, moneyDollars } from "@/lib/csv-export";

export async function GET() {
  await requireSession("/clients");
  const supabase = createAdminClient();

  const { data } = await supabase
    .from("crm_clients_with_stats")
    .select(
      "id, name, email, phone, address_line1, address_line2, city, state, postal_code, country, last_contact_at, order_count, lifetime_revenue_cents, avg_order_cents, largest_order_cents, last_order_at, notes",
    )
    .order("name");

  const headers = [
    "id",
    "name",
    "email",
    "phone",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "postal_code",
    "country",
    "last_contact_at",
    "orders",
    "lifetime_usd",
    "avg_order_usd",
    "largest_order_usd",
    "last_order_at",
    "notes",
  ];
  const lines = [csvRow(headers)];

  for (const c of data || []) {
    lines.push(
      csvRow([
        c.id,
        c.name,
        c.email || "",
        c.phone || "",
        c.address_line1 || "",
        c.address_line2 || "",
        c.city || "",
        c.state || "",
        c.postal_code || "",
        c.country || "",
        c.last_contact_at || "",
        c.order_count || 0,
        moneyDollars(c.lifetime_revenue_cents),
        moneyDollars(c.avg_order_cents),
        moneyDollars(c.largest_order_cents),
        c.last_order_at || "",
        c.notes || "",
      ]),
    );
  }

  const today = new Date().toISOString().slice(0, 10);
  return csvResponse(`fbf-clients-${today}.csv`, lines.join("\n"));
}
