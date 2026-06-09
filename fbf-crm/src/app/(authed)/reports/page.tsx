export default function ReportsPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Reports</h1>
        <p className="text-sm text-muted-foreground">
          Monthly P&L (revenue − COGS − expenses), inventory at cost vs at resale, top clients.
        </p>
      </header>
      <div className="rounded-lg border bg-card p-6 text-sm text-muted-foreground">
        Coming next session: monthly P&L table, charts, CSV export.
      </div>
    </div>
  );
}
