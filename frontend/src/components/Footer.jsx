export default function Footer() {
  return (
    <footer className="mt-24 border-t border-border bg-card">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-8 px-4 py-12 sm:grid-cols-3 sm:px-6">
        <div>
          <div className="text-xl font-black tracking-tight">BULKHAUS</div>
          <p className="mt-3 max-w-xs text-sm text-muted-foreground">
            Wholesale disposable goods for restaurants, caterers and resellers. Direct sourcing, transparent tiered
            pricing.
          </p>
        </div>
        <div>
          <div className="label-caps mb-3">Shop</div>
          <ul className="space-y-2 text-sm">
            <li><a href="/catalog" className="hover:text-primary">Catalog</a></li>
            <li><a href="/catalog" className="hover:text-primary">Bulk Pricing</a></li>
            <li><a href="/orders" className="hover:text-primary">Track an Order</a></li>
          </ul>
        </div>
        <div>
          <div className="label-caps mb-3">Contact</div>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li>sales@bulkhaus.co</li>
            <li>+1 (800) 555-0187</li>
            <li>Mon-Fri · 8AM to 6PM PT</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-border">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 text-xs text-muted-foreground sm:px-6">
          <span>© {new Date().getFullYear()} Bulkhaus Wholesale Co.</span>
          <span className="font-mono">B2B · MOQ · Tier Pricing</span>
        </div>
      </div>
    </footer>
  );
}
