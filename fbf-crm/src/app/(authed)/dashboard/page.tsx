export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Overview will land here: month-to-date revenue, low-stock alerts, latest orders.
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Revenue (this month)", value: "—" },
          { label: "Orders (this month)", value: "—" },
          { label: "Inventory @ cost", value: "—" },
          { label: "Inventory @ resale", value: "—" },
        ].map((card) => (
          <div key={card.label} className="rounded-lg border bg-card p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">{card.label}</div>
            <div className="mt-1 text-2xl font-semibold">{card.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
