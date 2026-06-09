export default function InventoryPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Inventory</h1>
        <p className="text-sm text-muted-foreground">
          Stock on hand, stock on order, tracking numbers, and low-stock alerts.
        </p>
      </header>
      <div className="rounded-lg border bg-card p-6 text-sm text-muted-foreground">
        Coming next session: lots per product (qty on hand + on order), supplier, package tracking
        number, expiration date, unit cost. Receive-shipment action deducts on-order, adds to
        on-hand.
      </div>
    </div>
  );
}
