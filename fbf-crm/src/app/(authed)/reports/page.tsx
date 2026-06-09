export default function ReportsPage() {
  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Analytics</div>
        <h1 className="text-3xl font-black tracking-tight">Reports</h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Monthly P&L (revenue − COGS − expenses), inventory at cost vs at resale, top clients.
        </p>
      </header>
      <div className="fbf-card text-sm text-muted-foreground">
        Coming next session: monthly P&L table, charts, CSV export.
      </div>
    </div>
  );
}
