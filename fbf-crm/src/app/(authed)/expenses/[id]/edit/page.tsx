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
import { updateExpense } from "../../actions";

export default async function EditExpensePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ error?: string }>;
}) {
  const { id } = await params;
  const { error: errorParam } = await searchParams;

  const supabase = createAdminClient();
  const { data: expense } = await supabase
    .from("crm_expenses")
    .select("id, incurred_at, category, vendor, amount_cents, note")
    .eq("id", id)
    .maybeSingle();

  if (!expense) notFound();

  const dollars = (cents: number) => (cents / 100).toFixed(2);

  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Edit Expense</div>
        <h1 className="text-3xl font-black tracking-tight">
          {expense.note?.split(".")[0] || expense.category || "Expense"}
        </h1>
      </header>

      <ErrorBanner message={errorParam} />

      <div className="fbf-card">
        <form action={updateExpense} className="grid gap-4 md:grid-cols-2">
          <input type="hidden" name="id" value={expense.id} />

          <Field label="Date" required>
            <Input
              name="incurred_at"
              type="date"
              defaultValue={expense.incurred_at}
              required
            />
          </Field>
          <Field label="Amount (USD)">
            <Input
              name="amount"
              inputMode="decimal"
              defaultValue={dollars(expense.amount_cents)}
            />
          </Field>
          <Field label="Category">
            <Select name="category" defaultValue={expense.category || "supplies"}>
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
            <Input name="vendor" defaultValue={expense.vendor || ""} />
          </Field>
          <Field label="Note" className="md:col-span-2">
            <Textarea name="note" defaultValue={expense.note || ""} />
          </Field>

          <div className="flex items-center gap-3 md:col-span-2">
            <SubmitButton>Save Changes</SubmitButton>
            <Link
              href="/expenses"
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
