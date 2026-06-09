export default function DashboardPage() {
  const stats = [
    { label: "Revenue (MTD)", value: "—" },
    { label: "Orders (MTD)", value: "—" },
    { label: "Inventory @ Cost", value: "—" },
    { label: "Inventory @ Resale", value: "—" },
  ];

  return (
    <div className="space-y-8">
      <header>
        <div className="fbf-eyebrow mb-2">Overview</div>
        <h1 className="text-3xl font-black tracking-tight">Dashboard</h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Month-to-date revenue, low-stock alerts, and the latest orders will land here as data
          starts flowing in.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((card) => (
          <div key={card.label} className="fbf-card">
            <div className="fbf-eyebrow mb-3 !text-muted-foreground">{card.label}</div>
            <div className="fbf-stat-num text-3xl font-black tracking-tight">{card.value}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-3">Low-Stock Alerts</div>
          <p className="text-sm text-muted-foreground">
            Lots below threshold will appear here once you've added products and inventory.
          </p>
        </div>
        <div className="fbf-card">
          <div className="fbf-eyebrow mb-3">Latest Orders</div>
          <p className="text-sm text-muted-foreground">
            Most recent orders (manual + Stripe-imported) will appear here.
          </p>
        </div>
      </div>
    </div>
  );
}
