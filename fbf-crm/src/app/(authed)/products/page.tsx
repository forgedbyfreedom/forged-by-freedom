export default function ProductsPage() {
  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Catalog</div>
        <h1 className="text-3xl font-black tracking-tight">Products</h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Peptides and research chemicals you sell — sell price, current cost, and active flag.
        </p>
      </header>
      <div className="fbf-card text-sm text-muted-foreground">
        Coming next session: product list, create / edit, sell price + current cost.
      </div>
    </div>
  );
}
