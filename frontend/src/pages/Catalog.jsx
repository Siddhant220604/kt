import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import ProductCard from "../components/ProductCard";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { MagnifyingGlass, FunnelSimple } from "@phosphor-icons/react";

export default function Catalog() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(false);

  const [q, setQ] = useState(searchParams.get("q") || "");
  const [categoryId, setCategoryId] = useState(searchParams.get("category") || "");
  const [minPrice, setMinPrice] = useState(searchParams.get("min") || "");
  const [maxPrice, setMaxPrice] = useState(searchParams.get("max") || "");
  const [maxMoq, setMaxMoq] = useState(searchParams.get("moq") || "");

  useEffect(() => {
    api.get("/categories").then((r) => setCategories(r.data || []));
  }, []);

  const load = async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (categoryId) params.set("category_id", categoryId);
    if (minPrice) params.set("min_price", minPrice);
    if (maxPrice) params.set("max_price", maxPrice);
    if (maxMoq) params.set("max_moq", maxMoq);
    const { data } = await api.get(`/products?${params.toString()}`);
    setItems(data.items || []);
    setTotal(data.total || 0);
    setLoading(false);
  };

  useEffect(() => {
    load();
    // Sync URL
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (categoryId) p.set("category", categoryId);
    if (minPrice) p.set("min", minPrice);
    if (maxPrice) p.set("max", maxPrice);
    if (maxMoq) p.set("moq", maxMoq);
    setSearchParams(p, { replace: true });
    // eslint-disable-next-line
  }, [q, categoryId, minPrice, maxPrice, maxMoq]);

  const clear = () => {
    setQ(""); setCategoryId(""); setMinPrice(""); setMaxPrice(""); setMaxMoq("");
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
      <div className="mb-8">
        <div className="label-caps mb-2">Catalog</div>
        <h1 className="text-3xl sm:text-4xl font-black tracking-tighter">Wholesale disposables</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {total} SKU{total === 1 ? "" : "s"} in stock · Tier pricing on every product
        </p>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[240px_1fr]">
        {/* Filters */}
        <aside className="space-y-6 border border-border bg-card p-5 h-fit lg:sticky lg:top-20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FunnelSimple size={16} />
              <span className="text-sm font-semibold">Filters</span>
            </div>
            <button
              onClick={clear}
              className="text-xs text-primary hover:underline"
              data-testid="filter-clear-button"
            >
              Clear
            </button>
          </div>

          <div>
            <div className="label-caps mb-2">Search</div>
            <div className="relative">
              <MagnifyingGlass size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Name, SKU…"
                className="pl-7 rounded-sm h-9"
                data-testid="filter-search-input"
              />
            </div>
          </div>

          <div>
            <div className="label-caps mb-2">Category</div>
            <div className="space-y-1">
              <button
                onClick={() => setCategoryId("")}
                className={`block w-full text-left text-sm px-2 py-1 ${!categoryId ? "bg-muted font-semibold" : "text-muted-foreground hover:text-foreground"}`}
                data-testid="filter-category-all"
              >
                All categories
              </button>
              {categories.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setCategoryId(c.id)}
                  className={`block w-full text-left text-sm px-2 py-1 ${categoryId === c.id ? "bg-muted font-semibold" : "text-muted-foreground hover:text-foreground"}`}
                  data-testid={`filter-category-${c.slug}`}
                >
                  {c.name}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="label-caps mb-2">Price / unit</div>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                value={minPrice}
                onChange={(e) => setMinPrice(e.target.value)}
                placeholder="Min"
                className="rounded-sm h-9"
                data-testid="filter-min-price"
              />
              <span className="text-muted-foreground">—</span>
              <Input
                type="number"
                value={maxPrice}
                onChange={(e) => setMaxPrice(e.target.value)}
                placeholder="Max"
                className="rounded-sm h-9"
                data-testid="filter-max-price"
              />
            </div>
          </div>

          <div>
            <div className="label-caps mb-2">Max MOQ</div>
            <Input
              type="number"
              value={maxMoq}
              onChange={(e) => setMaxMoq(e.target.value)}
              placeholder="e.g. 5"
              className="rounded-sm h-9"
              data-testid="filter-max-moq"
            />
          </div>
        </aside>

        {/* Grid */}
        <div>
          {loading ? (
            <div className="p-12 text-center text-sm text-muted-foreground">Loading products…</div>
          ) : items.length === 0 ? (
            <div className="border border-border bg-card p-12 text-center">
              <div className="label-caps mb-2">No results</div>
              <p className="text-sm text-muted-foreground">Try clearing filters.</p>
              <Button onClick={clear} variant="outline" className="mt-4 rounded-sm">Clear filters</Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-0 border-l border-t border-border sm:grid-cols-2 xl:grid-cols-3">
              {items.map((p) => (
                <div key={p.id} className="border-b border-r border-border">
                  <ProductCard product={p} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
