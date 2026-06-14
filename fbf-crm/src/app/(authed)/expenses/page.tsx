import Link from "next/link";
import { Pencil, Trash2 } from "lucide-react";
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
import { addExpense, deleteExpense } from "./actions";

export default async function ExpensesPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error: errorParam } = await searchParams;
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("crm_expenses")
    .select("id, incurred_at, category, vendor, amount_cents, note")
    .order("incurred_at", { ascending: false })
    .limit(500);

  const rows = data || [];
  const total = rows.reduce((s, e) => s + (e.amount_cents || 0), 0);

  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const yearStart = new Date(now.getFullYear(), 0, 1);
  let mtdTotal = 0;
  let ytdTotal = 0;
  for (const e of rows) {
    const d = new Date(e.incurred_at);
    if (d >= yearStart) ytdTotal += e.amount_cents || 0;
    if (d >= monthStart) mtdTotal += e.amount_cents || 0;
  }
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Outflows</div>
        <h1 className="text-3xl font-black tracking-tight">Expenses</h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Recurring and one-off business expenses for accurate monthly P&L.
        </p>
      </header>

      <ErrorBanner message={errorParam} />

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">This Month</div>
          <div className="fbf-stat-num text-2xl font-black">{formatMoney(mtdTotal)}</div>
        </div>
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">This Year</div>
          <div className="fbf-stat-num text-2xl font-black">{formatMoney(ytdTotal)}</div>
        </div>
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-2 !text-muted-foreground">All Time</div>
          <div className="fbf-stat-num text-2xl font-black">{formatMoney(total)}</div>
        </div>
      </div>

      <AddNewSection title="Add New Expense" defaultOpen>
        <form action={addExpense} className="grid gap-4 md:grid-cols-2">
          <Field label="Date" required>
            <Input name="incurred_at" type="date" defaultValue={today} required />
          </Field>
          <Field label="Amount (USD)" hint="Leave 0 if amount is TBD; you can edit later">
            <Input name="amount" inputMode="decimal" placeholder="42.00" />
          </Field>
          <Field label="Category">
            <Select name="category" defaultValue="supplies">
              <option value="supplies">Supplies</option>
              <option value="equipment">Equipment</option>
              <option value="shipping">Shipping</option>
              <option value="software">Software</option>
              <option value="fees">Fees</option>
              <option value="marketing">Marketing</option>
              <option value="travel">Travel</option>
              <option value="payroll">Payroll</option>
              <option value="other">Other</option>
            </Select>
          </Field>
          <Field label="Vendor">
            <Input name="vendor" placeholder="Who you paid" />
          </Field>
          <Field label="Note" className="md:col-span-2">
            <Textarea name="note" placeholder="What it was for, trip details, etc." />
          </Field>
          <div className="md:col-span-2">
            <SubmitButton>Add Expense</SubmitButton>
          </div>
        </form>
      </AddNewSection>

      {error ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error.message}
        </div>
      ) : (
        <div className="fbf-card !p-0 overflow-hidden">
          {rows.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No expenses yet — add your first one above.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-surface-2 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                    <th className="px-5 py-3 font-semibold">Date</th>
                    <th className="px-5 py-3 font-semibold">Category</th>
                    <th className="px-5 py-3 font-semibold">Vendor</th>
                    <th className="px-5 py-3 font-semibold">Note</th>
                    <th className="px-5 py-3 text-right font-semibold">Amount</th>
                    <th className="px-5 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((e) => {
                    const isPlaceholder = (e.amount_cents || 0) === 0;
                    return (
                      <tr
                        key={e.id}
                        className={`border-b border-border/60 transition-colors hover:bg-surface-2 ${
                          isPlaceholder ? "bg-primary/[0.04]" : ""
                        }`}
                      >
                        <td className="px-5 py-3 tabular-nums">{e.incurred_at}</td>
                        <td className="px-5 py-3 text-muted-foreground">{e.category || "—"}</td>
                        <td className="px-5 py-3 text-muted-foreground">{e.vendor || "—"}</td>
                        <td className="max-w-md px-5 py-3 text-muted-foreground">
                          {e.note || "—"}
                        </td>
                        <td className="px-5 py-3 text-right">
                          {isPlaceholder ? (
                            <Link
                              href={`/expenses/${e.id}/edit`}
                              className="inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-xs font-semibold uppercase tracking-wider text-primary hover:bg-primary/20"
                              title="Add receipt amount"
                            >
                              Pending Receipt
                            </Link>
                          ) : (
                            <span className="font-semibold tabular-nums">
                              {formatMoney(e.amount_cents)}
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex items-center justify-end gap-2">
                            <Link
                              href={`/expenses/${e.id}/edit`}
                              aria-label="Edit expense"
                              title="Edit"
                              className="grid h-8 w-8 place-items-center rounded-md border border-border bg-surface-2 text-muted-foreground transition-colors hover:border-primary hover:text-primary"
                            >
                              <Pencil className="h-4 w-4" />
                            </Link>
                            <form action={deleteExpense}>
                              <input type="hidden" name="id" value={e.id} />
                              <button
                                type="submit"
                                aria-label="Delete expense"
                                title="Delete"
                                className="grid h-8 w-8 place-items-center rounded-md border border-border bg-surface-2 text-muted-foreground transition-colors hover:border-destructive hover:text-destructive"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </form>
                          </div>
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
