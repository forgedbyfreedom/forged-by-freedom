export default function ExpensesPage() {
  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Outflows</div>
        <h1 className="text-3xl font-black tracking-tight">Expenses</h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Recurring and one-off business expenses, for accurate monthly P&L.
        </p>
      </header>
      <div className="fbf-card text-sm text-muted-foreground">
        Coming next session: expense entry (date, category, vendor, amount, note).
      </div>
    </div>
  );
}
