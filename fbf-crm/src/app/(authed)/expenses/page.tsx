import { createClient } from "@/lib/supabase/server";
import { formatMoney } from "@/lib/utils";
import {
  AddNewSection,
  Field,
  Input,
  Select,
  SubmitButton,
  Textarea,
} from "@/components/ui/form-primitives";
import { addExpense } from "./actions";

export default async function ExpensesPage() {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("crm_expenses")
    .select("id, incurred_at, category, vendor, amount_cents, note")
    .order("incurred_at", { ascending: false })
    .limit(200);

  const total = (data || []).reduce((s, e) => s + (e.amount_cents || 0), 0);
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

      <div className="fbf-card sm:max-w-xs">
        <div className="fbf-eyebrow mb-2 !text-muted-foreground">Total Logged</div>
        <div className="fbf-stat-num text-2xl font-black">{formatMoney(total)}</div>
      </div>

      <AddNewSection title="Add New Expense">
        <form action={addExpense} className="grid gap-4 md:grid-cols-2">
          <Field label="Date" required>
            <Input name="incurred_at" type="date" defaultValue={today} required />
          </Field>
          <Field label="Amount (USD)" required>
            <Input name="amount" inputMode="decimal" placeholder="42.00" required />
          </Field>
          <Field label="Category">
            <Select name="category" defaultValue="supplies">
              <option value="supplies">Supplies</option>
              <option value="shipping">Shipping</option>
              <option value="software">Software</option>
              <option value="fees">Fees</option>
              <option value="marketing">Marketing</option>
              <option value="payroll">Payroll</option>
              <option value="other">Other</option>
            </Select>
          </Field>
          <Field label="Vendor">
            <Input name="vendor" placeholder="Who you paid" />
          </Field>
          <Field label="Note" className="md:col-span-2">
            <Textarea name="note" />
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
          {(data?.length || 0) === 0 ? (
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
                  </tr>
                </thead>
                <tbody>
                  {data!.map((e) => (
                    <tr key={e.id} className="border-b border-border/60 transition-colors hover:bg-surface-2">
                      <td className="px-5 py-3 tabular-nums">{e.incurred_at}</td>
                      <td className="px-5 py-3 text-muted-foreground">{e.category || "—"}</td>
                      <td className="px-5 py-3 text-muted-foreground">{e.vendor || "—"}</td>
                      <td className="px-5 py-3 text-muted-foreground">{e.note || "—"}</td>
                      <td className="px-5 py-3 text-right tabular-nums">
                        {formatMoney(e.amount_cents)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
