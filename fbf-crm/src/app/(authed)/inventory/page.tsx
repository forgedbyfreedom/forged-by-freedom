export default function InventoryPage() {
  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Stock Control</div>
        <h1 className="text-3xl font-black tracking-tight">Inventory</h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Stock on hand, stock on order, tracking numbers, expirations, and low-stock alerts.
        </p>
      </header>
      <div className="fbf-card text-sm text-muted-foreground">
        Coming next session: lots per product (on hand + on order), supplier, package tracking
        number, expiration date, unit cost. Receive-shipment action moves on-order → on-hand.
      </div>
    </div>
  );
}
