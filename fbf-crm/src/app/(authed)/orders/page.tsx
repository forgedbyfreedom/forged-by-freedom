export default function OrdersPage() {
  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Sales</div>
        <h1 className="text-3xl font-black tracking-tight">Orders</h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Manual order entry plus Stripe-imported orders. Each order links to a client and deducts
          inventory.
        </p>
      </header>
      <div className="fbf-card text-sm text-muted-foreground">
        Coming next session: new-order form, order list, Stripe webhook auto-import.
      </div>
    </div>
  );
}
