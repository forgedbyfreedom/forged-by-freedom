import Link from "next/link";
import { Pencil, Trash2, Minus } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { formatMoney } from "@/lib/utils";
import {
  AddNewSection,
  ErrorBanner,
  Field,
  Input,
  Select,
  SubmitButton,
  Textarea,
} from "@/components/ui/form-primitives";
import { SortHeader, parseSort } from "@/components/ui/sort-header";
import { addLot, deleteLot, receiveLot, withdrawLot } from "./actions";

type LotSortKey =
  | "ordered_at"
  | "received_at"
  | "expires_at"
  | "qty_on_hand"
  | "qty_on_order"
  | "unit_cost_cents"
  | "status"
  | "supplier";
const LOT_SORT_KEYS: Record<LotSortKey, true> = {
  ordered_at: true,
  received_at: true,
  expires_at: true,
  qty_on_hand: true,
  qty_on_order: true,
  unit_cost_cents: true,
  status: true,
  supplier: true,
};

type Lot = {
  id: string;
  lot_number: string | null;
  supplier: string | null;
  unit_cost_cents: number;
  qty_on_hand: number;
  qty_on_order: number;
  tracking_number: string | null;
  carrier: string | null;
  status: string;
  ordered_at: string | null;
  expires_at: string | null;
  crm_products: { id: string; name: string; sell_price_cents: number } | null;
};

const STATUS_STYLE: Record<string, string> = {
  ordered: "border-info/40 bg-info/10 text-info",
  in_transit: "border-info/40 bg-info/10 text-info",
  received: "border-success/40 bg-success/10 text-success",
  depleted: "border-border bg-surface-2 text-subtle",
};

export default async function InventoryPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; sort?: string; dir?: string }>;
}) {
  const { error: errorParam, sort, dir } = await searchParams;
  const { sort: sortKey, dir: sortDir } = parseSort<LotSortKey>(sort, dir, LOT_SORT_KEYS, {
    sort: "ordered_at",
    dir: "desc",
  });
  const supabase = await createClient();
  const [productsRes, lotsRes] = await Promise.all([
    supabase.from("crm_products").select("id, name").eq("active", true).order("name"),
    supabase
      .from("crm_inventory_lots")
      .select(
        "id, lot_number, supplier, unit_cost_cents, qty_on_hand, qty_on_order, tracking_number, carrier, status, ordered_at, expires_at, crm_products!inner(id, name, sell_price_cents)",
      )
      .order(sortKey, { ascending: sortDir === "asc", nullsFirst: false })
      .limit(200),
  ]);

  const products = productsRes.data || [];
  const lots = (lotsRes.data || []) as unknown as Lot[];

  const totalCost = lots.reduce(
    (s, l) => s + (l.unit_cost_cents || 0) * (l.qty_on_hand || 0),
    0,
  );
  const totalResale = lots.reduce(
    (s, l) => s + (l.crm_products?.sell_price_cents || 0) * (l.qty_on_hand || 0),
    0,
  );

  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Stock Control</div>
        <h1 className="text-3xl font-black tracking-tight">Inventory</h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Lots per product — stock on hand, on order, suppliers, tracking, and expirations.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">On-Hand @ Cost</div>
          <div className="fbf-stat-num text-2xl font-black">{formatMoney(totalCost)}</div>
        </div>
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">On-Hand @ Resale</div>
          <div className="fbf-stat-num text-2xl font-black">{formatMoney(totalResale)}</div>
        </div>
      </div>

      <ErrorBanner message={errorParam} />

      {products.length === 0 ? (
        <div className="fbf-card text-sm text-muted-foreground">
          You need to add a{" "}
          <Link href="/products" className="text-primary underline">
            product
          </Link>{" "}
          before you can add inventory lots.
        </div>
      ) : (
        <AddNewSection title="Add New Inventory Lot" defaultOpen={!!errorParam}>
          <form action={addLot} className="grid gap-4 md:grid-cols-2">
            <Field label="Product" required>
              <Select name="product_id" required defaultValue="">
                <option value="" disabled>
                  Select a product…
                </option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Status">
              <Select name="status" defaultValue="ordered">
                <option value="ordered">Ordered</option>
                <option value="in_transit">In Transit</option>
                <option value="received">Received</option>
                <option value="depleted">Depleted</option>
              </Select>
            </Field>
            <Field label="Lot / Batch #">
              <Input name="lot_number" placeholder="e.g. 240601-A" />
            </Field>
            <Field label="Supplier">
              <Input name="supplier" />
            </Field>
            <Field label="Qty On Hand" hint="Already received and in stock">
              <Input name="qty_on_hand" type="number" min={0} defaultValue={0} />
            </Field>
            <Field label="Qty On Order" hint="Inbound, not yet arrived">
              <Input name="qty_on_order" type="number" min={0} defaultValue={0} />
            </Field>
            <Field label="Unit Cost (USD)">
              <Input name="unit_cost" inputMode="decimal" placeholder="18.50" />
            </Field>
            <Field label="Expires">
              <Input name="expires_at" type="date" />
            </Field>
            <Field label="Tracking #">
              <Input name="tracking_number" />
            </Field>
            <Field label="Carrier">
              <Input name="carrier" placeholder="USPS / UPS / FedEx" />
            </Field>
            <Field label="Ordered Date">
              <Input name="ordered_at" type="date" />
            </Field>
            <Field label="Received Date">
              <Input name="received_at" type="date" />
            </Field>
            <Field label="Notes" className="md:col-span-2">
              <Textarea name="notes" />
            </Field>
            <div className="md:col-span-2">
              <SubmitButton>Add Lot</SubmitButton>
            </div>
          </form>
        </AddNewSection>
      )}

      <div className="fbf-card !p-0 overflow-hidden">
        {lots.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            No inventory lots yet — add your first one above.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-2 text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="px-5 py-3 text-left font-semibold">Product</th>
                  <SortHeader label="Lot / Supplier" k="supplier" activeKey={sortKey} activeDir={sortDir} basePath="/inventory" />
                  <SortHeader label="On Hand" k="qty_on_hand" activeKey={sortKey} activeDir={sortDir} basePath="/inventory" align="right" />
                  <SortHeader label="On Order" k="qty_on_order" activeKey={sortKey} activeDir={sortDir} basePath="/inventory" align="right" />
                  <SortHeader label="Unit Cost" k="unit_cost_cents" activeKey={sortKey} activeDir={sortDir} basePath="/inventory" align="right" />
                  <th className="px-5 py-3 text-left font-semibold">Tracking</th>
                  <SortHeader label="Expires" k="expires_at" activeKey={sortKey} activeDir={sortDir} basePath="/inventory" />
                  <SortHeader label="Status" k="status" activeKey={sortKey} activeDir={sortDir} basePath="/inventory" />
                  <th className="px-5 py-3 text-left font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {lots.map((l) => (
                  <tr key={l.id} className="border-b border-border/60 transition-colors hover:bg-surface-2">
                    <td className="px-5 py-3 font-semibold">{l.crm_products?.name}</td>
                    <td className="px-5 py-3 text-muted-foreground">
                      <div>{l.lot_number || "—"}</div>
                      <div className="text-xs text-subtle">{l.supplier || ""}</div>
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums">{l.qty_on_hand}</td>
                    <td className="px-5 py-3 text-right tabular-nums text-muted-foreground">
                      {l.qty_on_order || "—"}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums">
                      {formatMoney(l.unit_cost_cents)}
                    </td>
                    <td className="px-5 py-3 text-xs text-muted-foreground">
                      {l.tracking_number ? (
                        <>
                          <div>{l.tracking_number}</div>
                          <div className="text-subtle">{l.carrier}</div>
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-5 py-3 text-xs text-muted-foreground">
                      {l.expires_at ? new Date(l.expires_at).toLocaleDateString() : "—"}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${
                          STATUS_STYLE[l.status] || "border-border bg-surface-2 text-muted-foreground"
                        }`}
                      >
                        {l.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {l.qty_on_order > 0 && l.status !== "received" && (
                          <form action={receiveLot}>
                            <input type="hidden" name="id" value={l.id} />
                            <button
                              type="submit"
                              className="rounded-md border border-border bg-surface-2 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-foreground transition-colors hover:border-primary hover:text-primary"
                              title="Move all on-order qty to on-hand"
                            >
                              Receive
                            </button>
                          </form>
                        )}
                        {l.qty_on_hand > 0 && (
                          <form action={withdrawLot} className="flex items-center gap-1">
                            <input type="hidden" name="id" value={l.id} />
                            <input
                              name="qty"
                              type="number"
                              min={1}
                              max={l.qty_on_hand}
                              defaultValue={1}
                              className="h-7 w-14 rounded-md border border-border bg-surface-2 px-2 text-xs text-foreground outline-none focus:border-primary"
                              title="How many to remove"
                            />
                            <button
                              type="submit"
                              aria-label="Withdraw from this lot"
                              title="Withdraw (personal use, sample, breakage)"
                              className="grid h-7 w-7 place-items-center rounded-md border border-border bg-surface-2 text-muted-foreground transition-colors hover:border-primary hover:text-primary"
                            >
                              <Minus className="h-3.5 w-3.5" />
                            </button>
                          </form>
                        )}
                        <Link
                          href={`/inventory/${l.id}/edit`}
                          aria-label="Edit lot"
                          title="Edit"
                          className="grid h-7 w-7 place-items-center rounded-md border border-border bg-surface-2 text-muted-foreground transition-colors hover:border-primary hover:text-primary"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Link>
                        <form action={deleteLot}>
                          <input type="hidden" name="id" value={l.id} />
                          <button
                            type="submit"
                            aria-label="Delete lot"
                            title="Delete lot"
                            className="grid h-7 w-7 place-items-center rounded-md border border-border bg-surface-2 text-muted-foreground transition-colors hover:border-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </form>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
