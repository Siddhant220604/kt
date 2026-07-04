import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import ProductCard from "../components/ProductCard";
import { Button } from "../components/ui/button";
import { ArrowRight, CheckCircle, Truck, Package, HandCoins } from "@phosphor-icons/react";

export default function Home() {
  const [featured, setFeatured] = useState([]);
  const [categories, setCategories] = useState([]);

  useEffect(() => {
    api.get("/products?limit=8").then((r) => setFeatured(r.data.items || []));
    api.get("/categories").then((r) => setCategories(r.data || []));
  }, []);

  return (
    <div>
      {/* Hero */}
      <section className="relative border-b border-border">
        <div className="absolute inset-0">
          <img
            src="https://images.pexels.com/photos/10834810/pexels-photo-10834810.jpeg"
            alt=""
            className="h-full w-full object-cover"
          />
          <div className="absolute inset-0 bg-black/60" />
        </div>
        <div className="relative mx-auto grid max-w-7xl grid-cols-1 gap-8 px-4 py-24 sm:px-6 md:grid-cols-2 md:py-32">
          <div className="text-white">
            <div className="mb-4 inline-flex items-center gap-2 border border-white/30 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em]">
              <span className="h-1.5 w-1.5 bg-primary" /> B2B Wholesale · Since 2019
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter leading-none">
              Wholesale disposables,
              <br />
              <span className="text-primary">priced by the pallet.</span>
            </h1>
            <p className="mt-6 max-w-lg text-base text-white/80">
              Food containers, cutlery, cups, napkins and cleaning supplies — sourced direct, priced in tiers,
              shipped fast to restaurants, caterers and resellers nationwide.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button asChild size="lg" className="rounded-sm btn-lift" data-testid="hero-shop-catalog-button">
                <Link to="/catalog">
                  Shop Catalog <ArrowRight size={16} className="ml-2" />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="rounded-sm border-white/40 bg-transparent text-white hover:bg-white hover:text-foreground"
                data-testid="hero-create-account-button"
              >
                <Link to="/register">Create B2B Account</Link>
              </Button>
            </div>
            <div className="mt-10 grid grid-cols-3 gap-6 border-t border-white/20 pt-6">
              {[
                ["8k+", "SKUs available"],
                ["2-3d", "Avg. lead time"],
                ["3-tier", "Volume pricing"],
              ].map(([k, v]) => (
                <div key={v}>
                  <div className="font-mono text-2xl font-bold">{k}</div>
                  <div className="text-xs uppercase tracking-widest text-white/60">{v}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Value strip */}
      <section className="border-b border-border bg-card">
        <div className="mx-auto grid max-w-7xl grid-cols-2 md:grid-cols-4">
          {[
            { icon: HandCoins, label: "Tiered Pricing", desc: "Save more the more you buy" },
            { icon: Package, label: "Real MOQ", desc: "Clear minimums on every SKU" },
            { icon: Truck, label: "Direct Ship", desc: "Warehouse to your dock" },
            { icon: CheckCircle, label: "Verified Buyers", desc: "Reviews from real orders only" },
          ].map((f, i) => (
            <div
              key={f.label}
              className={`flex items-start gap-3 p-6 border-border ${i % 2 === 0 ? "border-r" : ""} ${i < 2 ? "border-b md:border-b-0 md:border-r" : ""}`}
            >
              <f.icon size={22} className="mt-0.5 text-primary" weight="regular" aria-hidden="true" />
              <div>
                <div className="text-sm font-semibold">{f.label}</div>
                <div className="text-xs text-muted-foreground">{f.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Categories */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <div className="mb-8 flex items-end justify-between">
          <div>
            <div className="label-caps mb-2">01 — Categories</div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">Browse by department</h2>
          </div>
          <Link to="/catalog" className="hidden sm:inline text-sm font-medium text-primary">
            View all →
          </Link>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 border-l border-t border-border">
          {categories.map((c) => (
            <Link
              key={c.id}
              to={`/catalog?category=${c.id}`}
              data-testid={`category-tile-${c.slug}`}
              className="group border-b border-r border-border p-6 transition-colors hover:bg-muted/50"
            >
              <div className="label-caps text-[9px] mb-2 text-muted-foreground">{c.slug}</div>
              <div className="text-sm font-semibold">{c.name}</div>
              <div className="mt-3 flex items-center gap-1 text-xs text-primary opacity-0 group-hover:opacity-100 transition-opacity">
                Explore <ArrowRight size={12} />
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Featured products */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <div className="mb-8 flex items-end justify-between">
          <div>
            <div className="label-caps mb-2">02 — Best Sellers</div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">Featured products</h2>
          </div>
          <Link to="/catalog" className="text-sm font-medium text-primary">
            View catalog →
          </Link>
        </div>
        <div className="grid grid-cols-1 gap-0 border-l border-t border-border sm:grid-cols-2 lg:grid-cols-4">
          {featured.map((p) => (
            <div key={p.id} className="border-b border-r border-border">
              <ProductCard product={p} />
            </div>
          ))}
        </div>
      </section>

      {/* CTA banner */}
      <section className="mx-auto max-w-7xl px-4 pb-20 sm:px-6">
        <div className="grid grid-cols-1 md:grid-cols-5 items-stretch border border-border bg-card">
          <div className="md:col-span-3 p-10">
            <div className="label-caps mb-3">Onboarding</div>
            <h3 className="text-2xl sm:text-3xl font-bold tracking-tight">
              Open a wholesale account in under 60 seconds.
            </h3>
            <p className="mt-3 max-w-md text-sm text-muted-foreground">
              Get tier pricing, order history, priority fulfillment and account-manager support. No fees, no
              minimum spend.
            </p>
            <Button asChild size="lg" className="mt-6 rounded-sm btn-lift" data-testid="cta-register-button">
              <Link to="/register">Create B2B Account</Link>
            </Button>
          </div>
          <div className="md:col-span-2 border-t md:border-t-0 md:border-l border-border">
            <img
              src="https://images.pexels.com/photos/4487383/pexels-photo-4487383.jpeg"
              alt=""
              className="h-full w-full object-cover"
            />
          </div>
        </div>
      </section>
    </div>
  );
}
