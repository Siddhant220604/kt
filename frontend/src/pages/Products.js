import React, { useEffect, useState, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { api, formatINR } from '../lib/api';
import { Container, Section } from '../components/site/Section';
import ProductCard from '../components/ProductCard';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Skeleton } from '../components/ui/skeleton';
import { Sheet, SheetContent, SheetTrigger } from '../components/ui/sheet';
import { Badge } from '../components/ui/badge';
import { SlidersHorizontal, Search, X, ArrowLeft, ArrowRight, MessageCircle } from 'lucide-react';
import { useSettings } from '../lib/settings';

export default function Products() {
  const [sp, setSp] = useSearchParams();
  const search = sp.get('search') || '';
  const category = sp.get('category') || '';
  const sort = sp.get('sort') || 'newest';
  const inStock = sp.get('in_stock') === '1';
  const minPrice = sp.get('min_price') || '';
  const maxPrice = sp.get('max_price') || '';
  const page = Number(sp.get('page') || 1);

  const [q, setQ] = useState(search);
  const [cats, setCats] = useState([]);
  const [data, setData] = useState({ items: [], total: 0, pages: 1 });
  const [loading, setLoading] = useState(true);
  const { settings } = useSettings();

  useEffect(() => { api.get('/categories').then(r => setCats(r.data)); }, []);
  useEffect(() => { setQ(search); }, [search]);

  useEffect(() => {
    setLoading(true);
    const params = { page, limit: 24, sort };
    if (search) params.search = search;
    if (category) params.category = category;
    if (inStock) params.in_stock = true;
    if (minPrice) params.min_price = Number(minPrice);
    if (maxPrice) params.max_price = Number(maxPrice);
    api.get('/products', { params }).then(r => setData(r.data)).finally(() => setLoading(false));
  }, [search, category, sort, inStock, minPrice, maxPrice, page]);

  const updateParam = (k, v) => {
    const next = new URLSearchParams(sp);
    if (v === '' || v == null || v === false) next.delete(k); else next.set(k, v === true ? '1' : String(v));
    if (k !== 'page') next.delete('page');
    setSp(next);
  };

  const currentCat = cats.find(c => c.id === category);

  const Filters = ({ onClose }) => (
    <div className="space-y-6 p-1">
      <div>
        <div className="text-xs font-semibold uppercase text-muted-foreground mb-2">Categories</div>
        <div className="space-y-1">
          <button onClick={() => { updateParam('category', ''); onClose && onClose(); }} className={`w-full text-left px-3 py-2 rounded-lg text-sm ${!category ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}>All Products</button>
          {cats.map(c => (
            <button key={c.id} onClick={() => { updateParam('category', c.id); onClose && onClose(); }} data-testid={`filter-cat-${c.slug}`}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm flex justify-between items-center ${category === c.id ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}>
              <span>{c.name}</span>
              <Badge variant="secondary" className="text-xs">{c.product_count || 0}</Badge>
            </button>
          ))}
        </div>
      </div>
      <div>
        <div className="text-xs font-semibold uppercase text-muted-foreground mb-2">Price Range</div>
        <div className="flex gap-2">
          <Input placeholder="Min" type="number" value={minPrice} onChange={(e) => updateParam('min_price', e.target.value)} data-testid="filter-min-price" />
          <Input placeholder="Max" type="number" value={maxPrice} onChange={(e) => updateParam('max_price', e.target.value)} data-testid="filter-max-price" />
        </div>
      </div>
      <div>
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={inStock} onChange={(e) => updateParam('in_stock', e.target.checked)} data-testid="filter-in-stock" />
          <span className="text-sm">In stock only</span>
        </label>
      </div>
      <Button variant="outline" className="w-full" onClick={() => { setSp(new URLSearchParams()); onClose && onClose(); }}>Clear all filters</Button>
    </div>
  );

  return (
    <Section>
      <Container>
        <div className="mb-6">
          <h1 className="text-3xl md:text-4xl font-display font-bold">{currentCat ? currentCat.name : search ? `Search: "${search}"` : 'All Products'}</h1>
          <p className="text-sm text-muted-foreground mt-1">{data.total} products</p>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); updateParam('search', q); }} className="mb-4">
          <div className="relative max-w-xl">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search products..." className="pl-10 h-11" data-testid="products-search-input" />
            {q && <button type="button" onClick={() => { setQ(''); updateParam('search', ''); }} className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-muted"><X className="h-3.5 w-3.5" /></button>}
          </div>
        </form>
        <div className="grid lg:grid-cols-[240px,1fr] gap-6">
          <aside className="hidden lg:block"><div className="sticky top-24"><Filters /></div></aside>
          <div>
            <div className="flex items-center gap-3 justify-between mb-4">
              <Sheet>
                <SheetTrigger asChild>
                  <Button variant="outline" className="lg:hidden gap-2" data-testid="open-filters-button"><SlidersHorizontal className="h-4 w-4" /> Filters</Button>
                </SheetTrigger>
                <SheetContent side="left" className="w-80 overflow-auto">
                  <div className="pt-6"><Filters onClose={() => {}} /></div>
                </SheetContent>
              </Sheet>
              <Select value={sort} onValueChange={(v) => updateParam('sort', v)}>
                <SelectTrigger className="w-52" data-testid="sort-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="newest">Newest first</SelectItem>
                  <SelectItem value="price_asc">Price: Low to High</SelectItem>
                  <SelectItem value="price_desc">Price: High to Low</SelectItem>
                  <SelectItem value="name">Name (A-Z)</SelectItem>
                  <SelectItem value="rating">Best rated</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {loading ? (
              <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3 sm:gap-4">
                {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-72 rounded-2xl" />)}
              </div>
            ) : data.items.length === 0 ? (
              <div className="text-center py-16 bg-card border border-border rounded-2xl">
                <div className="font-display font-semibold text-lg">No products found</div>
                <p className="text-sm text-muted-foreground mt-1">Try removing filters, or WhatsApp us your requirement.</p>
                <div className="mt-4 flex gap-3 justify-center">
                  <Button onClick={() => setSp(new URLSearchParams())}>Clear filters</Button>
                  <a href={`https://wa.me/${settings.whatsapp || '919876543210'}`} target="_blank" rel="noreferrer">
                    <Button variant="outline" className="gap-2"><MessageCircle className="h-4 w-4" />WhatsApp Inquiry</Button>
                  </a>
                </div>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3 sm:gap-4">
                  {data.items.map(p => <ProductCard key={p.id} product={p} />)}
                </div>
                {data.pages > 1 && (
                  <div className="flex justify-center items-center gap-2 mt-8">
                    <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => updateParam('page', page - 1)}><ArrowLeft className="h-4 w-4" /></Button>
                    <div className="text-sm px-3">Page {page} of {data.pages}</div>
                    <Button variant="outline" size="sm" disabled={page >= data.pages} onClick={() => updateParam('page', page + 1)}><ArrowRight className="h-4 w-4" /></Button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </Container>
    </Section>
  );
}
