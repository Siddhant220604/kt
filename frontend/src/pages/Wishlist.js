import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';
import { Heart } from 'lucide-react';
import { useWishlist } from '../lib/wishlist';
import { api } from '../lib/api';
import ProductCard from '../components/ProductCard';

export default function Wishlist() {
  const { ids } = useWishlist();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ids.length) { setItems([]); return; }
    setLoading(true);
    Promise.all(ids.map(id => api.get(`/products/${id}`).catch(() => null))).then(rs => {
      setItems(rs.filter(Boolean).map(r => r.data));
    }).finally(() => setLoading(false));
  }, [ids]);

  return (
    <Section>
      <Container>
        <h1 className="text-3xl md:text-4xl font-display font-bold">Your Wishlist</h1>
        <p className="text-muted-foreground mt-1">{ids.length} item{ids.length !== 1 ? 's' : ''} saved for later</p>
        {ids.length === 0 ? (
          <div className="mt-10 text-center py-12 bg-card border border-border rounded-2xl">
            <Heart className="h-14 w-14 mx-auto text-muted-foreground/40" />
            <div className="font-display font-semibold text-lg mt-3">Nothing saved yet</div>
            <p className="text-sm text-muted-foreground mt-1">Save items for your next bulk order.</p>
            <Link to="/products"><Button className="mt-4">Browse Products</Button></Link>
          </div>
        ) : loading ? <div className="mt-6">Loading...</div> : (
          <div className="mt-6 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
            {items.map(p => <ProductCard key={p.id} product={p} />)}
          </div>
        )}
      </Container>
    </Section>
  );
}
