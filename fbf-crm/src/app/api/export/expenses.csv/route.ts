import { createAdminClient } from "@/lib/supabase/admin";
import { requireSession } from "@/lib/auth";
import { csvResponse, csvRow, moneyDollars } from "@/lib/csv-export";

export async function GET() {
  await requireSession("/expenses");
  const supabase = createAdminClient();

  const { data } = await supabase
    .from("crm_expenses")
    .select("id, incurred_at, category, vendor, amount_cents, note")
    .order("incurred_at", { ascending: false });

  const headers = ["id", "date", "category", "vendor", "amount_usd", "note"];
  const lines = [csvRow(headers)];

  for (const e of data || []) {
    lines.push(
      csvRow([
        e.id,
        e.incurred_at,
        e.category || "",
        e.vendor || "",
        moneyDollars(e.amount_cents),
        e.note || "",
      ]),
    );
  }

  const today = new Date().toISOString().slice(0, 10);
  return csvResponse(`fbf-expenses-${today}.csv`, lines.join("\n"));
}
