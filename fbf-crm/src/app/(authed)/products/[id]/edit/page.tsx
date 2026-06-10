import Link from "next/link";
import { notFound } from "next/navigation";
import { createAdminClient } from "@/lib/supabase/admin";
import {
  ErrorBanner,
  Field,
  Input,
  Select,
  SubmitButton,
} from "@/components/ui/form-primitives";
import { updateProduct } from "../../actions";

export default async function EditProductPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ error?: string }>;
}) {
  const { id } = await params;
  const { error: errorParam } = await searchParams;

  const supabase = createAdminClient();
  const { data: product } = await supabase
    .from("crm_products")
    .select("id, name, sku, category, unit, sell_price_cents, current_cost_cents, active")
    .eq("id", id)
    .maybeSingle();

  if (!product) notFound();

  const dollars = (cents: number) => (cents / 100).toFixed(2);

  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Edit Product</div>
        <h1 className="text-3xl font-black tracking-tight">{product.name}</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Update sell price, cost, or anything else. Changes apply to future orders; past order
          totals stay frozen.
        </p>
      </header>

      <ErrorBanner message={errorParam} />

      <div className="fbf-card">
        <form action={updateProduct} className="grid gap-4 md:grid-cols-2">
          <input type="hidden" name="id" value={product.id} />

          <Field label="Name" required className="md:col-span-2">
            <Input name="name" required defaultValue={product.name} />
          </Field>
          <Field label="SKU">
            <Input name="sku" defaultValue={product.sku || ""} />
          </Field>
          <Field label="Category">
            <Select name="category" defaultValue={product.category || "peptide"}>
              <option value="peptide">Peptide</option>
              <option value="research_chemical">Research Chemical</option>
              <option value="supplement">Supplement</option>
              <option value="other">Other</option>
            </Select>
          </Field>
          <Field label="Unit">
            <Select name="unit" defaultValue={product.unit}>
              <option value="vial">Vial</option>
              <option value="bottle">Bottle</option>
              <option value="kit">Kit</option>
              <option value="mg">Milligram</option>
              <option value="unit">Unit</option>
            </Select>
          </Field>
          <Field label="Sell Price (USD)">
            <Input
              name="sell_price"
              inputMode="decimal"
              defaultValue={dollars(product.sell_price_cents)}
            />
          </Field>
          <Field label="Current Cost (USD)">
            <Input
              name="current_cost"
              inputMode="decimal"
              defaultValue={dollars(product.current_cost_cents)}
            />
          </Field>
          <label className="flex items-center gap-2 text-sm md:col-span-2">
            <input
              type="checkbox"
              name="active"
              defaultChecked={product.active}
              className="h-4 w-4 rounded border border-border bg-surface-2 accent-[#ff6a00]"
            />
            <span>Active (show in dropdowns and order entry)</span>
          </label>
          <div className="flex items-center gap-3 md:col-span-2">
            <SubmitButton>Save Changes</SubmitButton>
            <Link
              href="/products"
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
