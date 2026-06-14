import Link from "next/link";
import { notFound } from "next/navigation";
import { createAdminClient } from "@/lib/supabase/admin";
import { formatMoney } from "@/lib/utils";
import {
  ErrorBanner,
  Field,
  Input,
  Select,
  SubmitButton,
  Textarea,
} from "@/components/ui/form-primitives";
import { updateOrder } from "../../actions";

export default async function EditOrderPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ error?: string }>;
}) {
  const { id } = await params;
  const { error: errorParam } = await searchParams;

  const supabase = createAdminClient();
  const [orderRes, clientsRes] = await Promise.all([
    supabase
      .from("crm_orders")
      .select(
        "id, ordered_at, source, status, client_id, subtotal_cents, shipping_cents, tax_cents, total_cents, tracking_number, carrier, notes, crm_order_items(qty, unit_price_cents, line_total_cents, crm_products(name))",
      )
      .eq("id", id)
      .maybeSingle(),
    supabase.from("crm_clients").select("id, name").order("name"),
  ]);

  const order = orderRes.data;
  if (!order) notFound();
  const clients = clientsRes.data || [];

  const items = (order.crm_order_items as unknown as {
    qty: number;
    unit_price_cents: number;
    line_total_cents: number;
    crm_products: { name: string } | null;
  }[]) || [];

  const dollars = (c: number) => (c / 100).toFixed(2);
  const dateOnly = (iso: string) => iso.slice(0, 10);

  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Edit Order</div>
        <h1 className="text-3xl font-black tracking-tight">
          {formatMoney(order.total_cents)} ·{" "}
          {new Date(order.ordered_at).toLocaleDateString()}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Line items can&apos;t be edited from here (would require an inventory reshuffle).
          To change items, delete the order and re-add — inventory refunds back to the original
          lots automatically.
        </p>
      </header>

      <ErrorBanner message={errorParam} />

      <div className="fbf-card">
        <form action={updateOrder} className="grid gap-4 md:grid-cols-2">
          <input type="hidden" name="id" value={order.id} />

          <Field label="Client">
            <Select name="client_id" defaultValue={order.client_id || ""}>
              <option value="">(No client linked)</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Order Date">
            <Input
              name="ordered_at"
              type="date"
              defaultValue={dateOnly(order.ordered_at)}
            />
          </Field>
          <Field label="Status">
            <Select name="status" defaultValue={order.status}>
              <option value="pending">Pending</option>
              <option value="paid">Paid</option>
              <option value="shipped">Shipped</option>
              <option value="refunded">Refunded</option>
            </Select>
          </Field>
          <Field label="Tracking #">
            <Input name="tracking_number" defaultValue={order.tracking_number || ""} />
          </Field>
          <Field label="Carrier">
            <Input name="carrier" defaultValue={order.carrier || ""} />
          </Field>
          <Field label="Shipping (USD)">
            <Input
              name="shipping"
              inputMode="decimal"
              defaultValue={dollars(order.shipping_cents)}
            />
          </Field>
          <Field label="Tax (USD)">
            <Input name="tax" inputMode="decimal" defaultValue={dollars(order.tax_cents)} />
          </Field>
          <Field label="Notes" className="md:col-span-2">
            <Textarea name="notes" defaultValue={order.notes || ""} />
          </Field>

          <div className="flex items-center gap-3 md:col-span-2">
            <SubmitButton>Save Changes</SubmitButton>
            <Link
              href="/orders"
              className="rounded-md border border-border bg-surface-2 px-4 py-2.5 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground"
            >
              Cancel
            </Link>
          </div>
        </form>
      </div>

      {items.length > 0 && (
        <div className="fbf-card !p-0 overflow-hidden">
          <div className="border-b border-border px-5 py-4">
            <div className="fbf-eyebrow">Line Items (read-only)</div>
          </div>
          <ul className="divide-y divide-border">
            {items.map((it, i) => (
              <li key={i} className="flex items-center justify-between px-5 py-3 text-sm">
                <span>
                  <span className="font-semibold tabular-nums">{it.qty}×</span>{" "}
                  {it.crm_products?.name || "(deleted product)"}
                </span>
                <span className="text-muted-foreground tabular-nums">
                  {formatMoney(it.unit_price_cents)} ea ·{" "}
                  <span className="text-foreground">{formatMoney(it.line_total_cents)}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
