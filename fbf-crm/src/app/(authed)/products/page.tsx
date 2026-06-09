import { createClient } from "@/lib/supabase/server";
import { formatMoney } from "@/lib/utils";
import {
  AddNewSection,
  Field,
  Input,
  Select,
  SubmitButton,
} from "@/components/ui/form-primitives";
import { addProduct } from "./actions";

export default async function ProductsPage() {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("crm_products")
    .select("id, name, sku, category, unit, sell_price_cents, current_cost_cents, active")
    .order("name", { ascending: true });

  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Catalog</div>
        <h1 className="text-3xl font-black tracking-tight">Products</h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Peptides and research chemicals you sell — sell price, current cost, and active status.
        </p>
      </header>

      <AddNewSection title="Add New Product">
        <form action={addProduct} className="grid gap-4 md:grid-cols-2">
          <Field label="Name" required className="md:col-span-2">
            <Input name="name" required placeholder="BPC-157 5mg" />
          </Field>
          <Field label="SKU" hint="Optional internal code">
            <Input name="sku" placeholder="BPC-157-5MG" />
          </Field>
          <Field label="Category">
            <Select name="category" defaultValue="peptide">
              <option value="peptide">Peptide</option>
              <option value="research_chemical">Research Chemical</option>
              <option value="supplement">Supplement</option>
              <option value="other">Other</option>
            </Select>
          </Field>
          <Field label="Unit">
            <Select name="unit" defaultValue="vial">
              <option value="vial">Vial</option>
              <option value="bottle">Bottle</option>
              <option value="kit">Kit</option>
              <option value="mg">Milligram</option>
              <option value="unit">Unit</option>
            </Select>
          </Field>
          <Field label="Sell Price (USD)" hint="Per unit, what the client pays">
            <Input name="sell_price" inputMode="decimal" placeholder="49.99" />
          </Field>
          <Field label="Current Cost (USD)" hint="Default cost; lots override this">
            <Input name="current_cost" inputMode="decimal" placeholder="18.50" />
          </Field>
          <label className="flex items-center gap-2 text-sm md:col-span-2">
            <input
              type="checkbox"
              name="active"
              defaultChecked
              className="h-4 w-4 rounded border border-border bg-surface-2 accent-[#ff6a00]"
            />
            <span>Active (show in dropdowns and order entry)</span>
          </label>
          <div className="md:col-span-2">
            <SubmitButton>Add Product</SubmitButton>
          </div>
        </form>
      </AddNewSection>

      {error ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error.message}
        </div>
      ) : (
        <div className="fbf-card !p-0 overflow-hidden">
          {(data?.length || 0) === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No products yet — add your first one above.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-surface-2 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                    <th className="px-5 py-3 font-semibold">Name</th>
                    <th className="px-5 py-3 font-semibold">SKU</th>
                    <th className="px-5 py-3 font-semibold">Category</th>
                    <th className="px-5 py-3 font-semibold">Unit</th>
                    <th className="px-5 py-3 text-right font-semibold">Sell</th>
                    <th className="px-5 py-3 text-right font-semibold">Cost</th>
                    <th className="px-5 py-3 text-right font-semibold">Margin</th>
                    <th className="px-5 py-3 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data!.map((p) => {
                    const margin =
                      p.sell_price_cents && p.current_cost_cents
                        ? p.sell_price_cents - p.current_cost_cents
                        : 0;
                    const marginPct =
                      p.sell_price_cents > 0 ? Math.round((margin / p.sell_price_cents) * 100) : 0;
                    return (
                      <tr key={p.id} className="border-b border-border/60 transition-colors hover:bg-surface-2">
                        <td className="px-5 py-3 font-semibold">{p.name}</td>
                        <td className="px-5 py-3 text-muted-foreground">{p.sku || "—"}</td>
                        <td className="px-5 py-3 text-muted-foreground">{p.category || "—"}</td>
                        <td className="px-5 py-3 text-muted-foreground">{p.unit}</td>
                        <td className="px-5 py-3 text-right tabular-nums">
                          {formatMoney(p.sell_price_cents)}
                        </td>
                        <td className="px-5 py-3 text-right tabular-nums text-muted-foreground">
                          {formatMoney(p.current_cost_cents)}
                        </td>
                        <td className="px-5 py-3 text-right tabular-nums">
                          {formatMoney(margin)}{" "}
                          <span className="text-xs text-subtle">({marginPct}%)</span>
                        </td>
                        <td className="px-5 py-3">
                          {p.active ? (
                            <span className="inline-flex items-center rounded-full border border-success/40 bg-success/10 px-2 py-0.5 text-xs text-success">
                              Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center rounded-full border border-border bg-surface-2 px-2 py-0.5 text-xs text-subtle">
                              Inactive
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
