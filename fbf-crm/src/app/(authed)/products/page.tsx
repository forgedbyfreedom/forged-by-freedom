export default function ProductsPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Products</h1>
        <p className="text-sm text-muted-foreground">
          Catalog of peptides and research chemicals you sell. Pricing and current cost live here.
        </p>
      </header>
      <div className="rounded-lg border bg-card p-6 text-sm text-muted-foreground">
        Coming next session: product list, create/edit, sell price + current cost.
      </div>
    </div>
  );
}
