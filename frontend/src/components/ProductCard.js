import React from 'react';
import { Link } from 'react-router-dom';
import { Heart, ShoppingCart, Star } from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { formatINR } from '../lib/api';
import { useCart } from '../lib/cart';
import { useWishlist } from '../lib/wishlist';
import { toast } from 'sonner';
import { motion } from 'framer-motion';

const FALLBACK = 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=800&q=80';

const ProductCard = ({ product }) => {
  const { addItem } = useCart();
  const { toggle, has } = useWishlist();
  const img = (product.images && product.images[0]) || FALLBACK;
  const inStock = (product.stock || 0) > 0;
  const discount = product.compare_price && product.compare_price > product.price ? Math.round((1 - product.price / product.compare_price) * 100) : 0;

  return (
    <motion.div whileHover={{ y: -3 }} transition={{ type: 'spring', stiffness: 260, damping: 20 }}
      className="group rounded-2xl border border-border bg-card overflow-hidden shadow-[0_1px_0_rgba(0,0,0,0.04)] hover:shadow-[0_10px_30px_rgba(0,0,0,0.08)] transition-shadow"
      data-testid="product-card">
      <div className="relative aspect-square bg-muted/40 overflow-hidden">
        <Link to={`/products/${product.slug || product.id}`}>
          <img src={img} alt={product.name} loading="lazy" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" onError={(e) => { e.target.src = FALLBACK; }} />
        </Link>
        <button onClick={() => { toggle(product.id); toast.success(has(product.id) ? 'Removed from wishlist' : 'Added to wishlist'); }}
          data-testid="product-card-wishlist-toggle"
          className="absolute top-2 right-2 h-9 w-9 rounded-full bg-background/90 backdrop-blur border border-border grid place-items-center hover:bg-background">
          <Heart className={`h-4 w-4 ${has(product.id) ? 'fill-destructive text-destructive' : ''}`} />
        </button>
        {discount > 0 && <Badge className="absolute top-2 left-2 bg-[hsl(var(--brand-marigold))] text-black">{product.on_sale ? 'Flash Sale ' : ''}-{discount}%</Badge>}
        {!inStock && <div className="absolute inset-0 grid place-items-center bg-background/70"><Badge variant="secondary">Out of stock</Badge></div>}
      </div>
      <div className="p-3.5">
        <Link to={`/products/${product.slug || product.id}`}>
          <div className="font-body text-sm line-clamp-2 min-h-[40px] leading-snug" data-testid="product-card-name">{product.name}</div>
        </Link>
        <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
          {product.avg_rating > 0 && <><Star className="h-3 w-3 fill-[hsl(var(--brand-marigold))] text-[hsl(var(--brand-marigold))]" /><span>{product.avg_rating}</span>·</>}
          <span>MOQ: {product.moq || 1} {product.unit || 'pc'}</span>
        </div>
        <div className="mt-2 flex items-end justify-between gap-2">
          <div>
            <div className="font-display font-bold text-lg text-foreground leading-none" data-testid="product-price">{formatINR(product.price)}</div>
            {discount > 0 && <div className="text-xs text-muted-foreground line-through">{formatINR(product.compare_price)}</div>}
            <div className="text-[10px] text-muted-foreground uppercase mt-0.5">per {product.unit || 'pc'}{product.size ? ` • ${product.size}` : ''}</div>
          </div>
          <Button size="sm" data-testid="product-card-add-to-cart" disabled={!inStock}
            onClick={() => { addItem(product, product.moq || 1); toast.success('Added to cart'); }}>
            <ShoppingCart className="h-3.5 w-3.5 mr-1" />Add
          </Button>
        </div>
      </div>
    </motion.div>
  );
};

export default ProductCard;
