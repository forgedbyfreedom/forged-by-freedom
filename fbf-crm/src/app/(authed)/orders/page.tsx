export default function OrdersPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Orders</h1>
        <p className="text-sm text-muted-foreground">
          Manual order entry + Stripe-imported orders. Each order links to a client and deducts
          inventory.
        </p>
      </header>
      <div className="rounded-lg border bg-card p-6 text-sm text-muted-foreground">
        Coming next session: new-order form, order list, Stripe webhook auto-import.
      </div>
    </div>
  );
}
