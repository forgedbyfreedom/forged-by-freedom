import Link from "next/link";
import { notFound } from "next/navigation";
import { createAdminClient } from "@/lib/supabase/admin";
import {
  ErrorBanner,
  Field,
  Input,
  Select,
  SubmitButton,
  Textarea,
} from "@/components/ui/form-primitives";
import { updateLot } from "../../actions";

export default async function EditLotPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ error?: string }>;
}) {
  const { id } = await params;
  const { error: errorParam } = await searchParams;

  const supabase = createAdminClient();
  const { data: lot } = await supabase
    .from("crm_inventory_lots")
    .select(
      "id, lot_number, supplier, unit_cost_cents, qty_on_hand, qty_on_order, tracking_number, carrier, status, ordered_at, received_at, expires_at, notes, crm_products!inner(id, name)",
    )
    .eq("id", id)
    .maybeSingle();

  if (!lot) notFound();

  const dollars = (cents: number) => (cents / 100).toFixed(2);
  const dateOnly = (iso: string | null) => (iso ? iso.slice(0, 10) : "");

  const product = (lot.crm_products as unknown as { id: string; name: string } | null) || null;

  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Edit Lot</div>
        <h1 className="text-3xl font-black tracking-tight">{product?.name || "Inventory Lot"}</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Update supplier, cost, tracking, dates, or stock counts.
        </p>
      </header>

      <ErrorBanner message={errorParam} />

      <div className="fbf-card">
        <form action={updateLot} className="grid gap-4 md:grid-cols-2">
          <input type="hidden" name="id" value={lot.id} />

          <Field label="Status">
            <Select name="status" defaultValue={lot.status}>
              <option value="ordered">Ordered</option>
              <option value="in_transit">In Transit</option>
              <option value="received">Received</option>
              <option value="depleted">Depleted</option>
            </Select>
          </Field>
          <Field label="Lot / Batch #">
            <Input name="lot_number" defaultValue={lot.lot_number || ""} />
          </Field>
          <Field label="Supplier">
            <Input name="supplier" defaultValue={lot.supplier || ""} />
          </Field>
          <Field label="Unit Cost (USD)">
            <Input
              name="unit_cost"
              inputMode="decimal"
              defaultValue={dollars(lot.unit_cost_cents)}
            />
          </Field>
          <Field label="Qty On Hand">
            <Input name="qty_on_hand" type="number" min={0} defaultValue={lot.qty_on_hand} />
          </Field>
          <Field label="Qty On Order">
            <Input name="qty_on_order" type="number" min={0} defaultValue={lot.qty_on_order} />
          </Field>
          <Field label="Tracking #">
            <Input name="tracking_number" defaultValue={lot.tracking_number || ""} />
          </Field>
          <Field label="Carrier">
            <Input name="carrier" defaultValue={lot.carrier || ""} />
          </Field>
          <Field label="Ordered Date">
            <Input name="ordered_at" type="date" defaultValue={dateOnly(lot.ordered_at)} />
          </Field>
          <Field label="Received Date">
            <Input name="received_at" type="date" defaultValue={dateOnly(lot.received_at)} />
          </Field>
          <Field label="Expires">
            <Input name="expires_at" type="date" defaultValue={dateOnly(lot.expires_at)} />
          </Field>
          <Field label="Notes" className="md:col-span-2">
            <Textarea name="notes" defaultValue={lot.notes || ""} />
          </Field>

          <div className="flex items-center gap-3 md:col-span-2">
            <SubmitButton>Save Changes</SubmitButton>
            <Link
              href="/inventory"
              className="rounded-md border border-border bg-surface-2 px-4 py-2.5 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground"
            >
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
