"use client";

import { useState } from "react";
import { Trash2 } from "lucide-react";
import {
  Field,
  Input,
  Select,
  SubmitButton,
  Textarea,
} from "@/components/ui/form-primitives";
import { addOrder } from "./actions";

type Product = { id: string; name: string; sell_price_cents: number };
type Client = { id: string; name: string };

export function OrderForm({ clients, products }: { clients: Client[]; products: Product[] }) {
  const today = new Date().toISOString().slice(0, 10);
  const [rows, setRows] = useState<{ key: number; productId: string; qty: number; price: string }[]>([
    { key: Date.now(), productId: "", qty: 1, price: "" },
  ]);

  const updateRow = (key: number, patch: Partial<(typeof rows)[number]>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  const addRow = () =>
    setRows((rs) => [...rs, { key: Date.now() + Math.random(), productId: "", qty: 1, price: "" }]);

  const removeRow = (key: number) =>
    setRows((rs) => (rs.length > 1 ? rs.filter((r) => r.key !== key) : rs));

  const subtotal = rows.reduce(
    (s, r) => s + (parseFloat(r.price) || 0) * (r.qty || 0),
    0,
  );

  return (
    <form action={addOrder} className="grid gap-4 md:grid-cols-2">
      <Field label="Client">
        <Select name="client_id" defaultValue="">
          <option value="">(No client linked)</option>
          {clients.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Order Date" required>
        <Input name="ordered_at" type="date" defaultValue={today} required />
      </Field>

      {/* Line items */}
      <div className="md:col-span-2">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Line Items <span className="text-primary">*</span>
          </span>
          <button
            type="button"
            onClick={addRow}
            className="rounded-md border border-border bg-surface-2 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-foreground transition-colors hover:border-primary hover:text-primary"
          >
            + Add Row
          </button>
        </div>
        <div className="space-y-2">
          {rows.map((row) => (
            <div
              key={row.key}
              className="grid items-end gap-2 rounded-md border border-border bg-surface p-3 md:grid-cols-[1fr_90px_120px_40px]"
            >
              <Select
                name="item_product_id"
                value={row.productId}
                onChange={(e) => {
                  const pid = e.target.value;
                  const p = products.find((p) => p.id === pid);
                  updateRow(row.key, {
                    productId: pid,
                    price: p && !row.price ? (p.sell_price_cents / 100).toFixed(2) : row.price,
                  });
                }}
              >
                <option value="">Select product…</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
              <Input
                name="item_qty"
                type="number"
                min={1}
                value={row.qty}
                onChange={(e) => updateRow(row.key, { qty: parseInt(e.target.value, 10) || 0 })}
                placeholder="Qty"
              />
              <Input
                name="item_unit_price"
                inputMode="decimal"
                value={row.price}
                onChange={(e) => updateRow(row.key, { price: e.target.value })}
                placeholder="Price"
              />
              <button
                type="button"
                onClick={() => removeRow(row.key)}
                aria-label="Remove row"
                className="grid h-9 w-9 place-items-center rounded-md border border-border bg-surface-2 text-muted-foreground transition-colors hover:border-destructive hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
        <div className="mt-2 text-right text-sm text-muted-foreground">
          Subtotal:{" "}
          <span className="font-semibold text-foreground tabular-nums">
            ${subtotal.toFixed(2)}
          </span>
        </div>
      </div>

      <Field label="Shipping (USD)">
        <Input name="shipping" inputMode="decimal" placeholder="0.00" />
      </Field>
      <Field label="Tax (USD)">
        <Input name="tax" inputMode="decimal" placeholder="0.00" />
      </Field>
      <Field label="Status">
        <Select name="status" defaultValue="paid">
          <option value="pending">Pending</option>
          <option value="paid">Paid</option>
          <option value="shipped">Shipped</option>
          <option value="refunded">Refunded</option>
        </Select>
      </Field>
      <Field label="Tracking #">
        <Input name="tracking_number" />
      </Field>
      <Field label="Carrier">
        <Input name="carrier" placeholder="USPS / UPS / FedEx" />
      </Field>
      <Field label="Notes" className="md:col-span-2">
        <Textarea name="notes" />
      </Field>
      <div className="md:col-span-2">
        <SubmitButton>Add Order</SubmitButton>
      </div>
    </form>
  );
}
