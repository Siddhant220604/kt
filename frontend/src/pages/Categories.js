import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { Container, Section, SectionTitle } from '../components/site/Section';
import Seo from '../components/site/Seo';
import { Skeleton } from '../components/ui/skeleton';

const FALLBACK_IMAGE = 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=600&q=80';

export default function Categories() {
  const [cats, setCats] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/categories').then(r => setCats(r.data)).finally(() => setLoading(false));
  }, []);

  return (
    <Section>
      <Seo title="All Categories" description="Browse every product category available at Kiran Traders - thermocol plates, packaging materials, disposables, and more." />
      <Container>
        <SectionTitle eyebrow="Shop by Category" title="All Categories" subtitle="Browse our complete range of disposables, packaging, and wholesale essentials." />
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {loading ? Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} className="h-40 rounded-2xl" />) : cats.map((c) => (
            <Link key={c.id} to={`/products?category=${c.id}`} data-testid={`all-categories-card-${c.slug}`}
              className="group relative aspect-[4/3] rounded-2xl overflow-hidden border border-border bg-card hover:shadow-lg transition-shadow">
              <img src={c.image || FALLBACK_IMAGE} alt={c.name} className="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
              <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />
              <div className="absolute inset-x-0 bottom-0 p-3.5 text-white">
                <div className="font-display font-semibold text-base leading-tight">{c.name}</div>
                <div className="text-xs opacity-80">{c.product_count || 0} products</div>
              </div>
            </Link>
          ))}
        </div>
      </Container>
    </Section>
  );
}
