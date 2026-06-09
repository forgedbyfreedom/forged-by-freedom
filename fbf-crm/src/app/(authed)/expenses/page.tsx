export default function ExpensesPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Expenses</h1>
        <p className="text-sm text-muted-foreground">
          Recurring and one-off business expenses for accurate monthly P&L.
        </p>
      </header>
      <div className="rounded-lg border bg-card p-6 text-sm text-muted-foreground">
        Coming next session: expense entry (date, category, amount, note).
      </div>
    </div>
  );
}
