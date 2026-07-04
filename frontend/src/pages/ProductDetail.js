import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { api, formatINR } from '../lib/api';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { Textarea } from '../components/ui/textarea';
import { Input } from '../components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Minus, Plus, ShoppingCart, Heart, MessageCircle, Star, ShieldCheck, Truck, Award, ChevronLeft } from 'lucide-react';
import { toast } from 'sonner';
import ProductCard from '../components/ProductCard';
import { useCart } from '../lib/cart';
import { useWishlist } from '../lib/wishlist';
import { useSettings } from '../lib/settings';

const FALLBACK = 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=1000&q=80';

export default function ProductDetail() {
  const { idOrSlug } = useParams();
  const navigate = useNavigate();
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [qty, setQty] = useState(1);
  const [activeImg, setActiveImg] = useState(0);
  const [reviews, setReviews] = useState([]);
  const { addItem } = useCart();
  const { toggle, has } = useWishlist();
  const { settings } = useSettings();
  const [reviewForm, setReviewForm] = useState({ name: '', rating: 5, title: '', comment: '' });

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/products/${idOrSlug}`);
      setProduct(data);
      setQty(data.moq || 1);
      const { data: rv } = await api.get(`/reviews/product/${data.id}`);
      setReviews(rv);
    } catch (e) { toast.error('Product not found'); navigate('/products'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [idOrSlug]);

  if (loading || !product) return (
    <Container className="py-10">
      <div className="grid md:grid-cols-2 gap-8">
        <Skeleton className="aspect-square rounded-2xl" />
        <div className="space-y-3">
          <Skeleton className="h-8 w-3/4" /><Skeleton className="h-6 w-1/2" /><Skeleton className="h-20 w-full" />
        </div>
      </div>
    </Container>
  );

  const images = product.images && product.images.length ? product.images : [FALLBACK];
  const inStock = (product.stock || 0) > 0;
  const discount = product.compare_price && product.compare_price > product.price ? Math.round((1 - product.price / product.compare_price) * 100) : 0;
  const changeQty = (delta) => setQty(q => Math.max(product.moq || 1, q + delta));

  const wa = `https://wa.me/${settings.whatsapp || '919876543210'}?text=${encodeURIComponent(`Hi Kiran Traders, I want to enquire bulk price for: ${product.name} (${product.size || ''}). Quantity needed: `)}`;

  const submitReview = async (e) => {
    e.preventDefault();
    try {
      await api.post('/reviews', { ...reviewForm, product_id: product.id, rating: Number(reviewForm.rating) });
      toast.success('Thank you! Your review will appear after admin approval.');
      setReviewForm({ name: '', rating: 5, title: '', comment: '' });
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to submit review'); }
  };

  return (
    <div>
      <Section className="pt-6">
        <Container>
          <Link to="/products" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4"><ChevronLeft className="h-4 w-4" /> Back to products</Link>
          <div className="grid md:grid-cols-2 gap-8 lg:gap-12">
            {/* Gallery */}
            <div>
              <div className="aspect-square rounded-2xl overflow-hidden border border-border bg-card">
                <img src={images[activeImg] || FALLBACK} alt={product.name} className="w-full h-full object-cover" onError={(e) => { e.target.src = FALLBACK; }} data-testid="product-main-image" />
              </div>
              {images.length > 1 && (
                <div className="mt-3 flex gap-2 overflow-x-auto no-scrollbar">
                  {images.map((im, i) => (
                    <button key={i} onClick={() => setActiveImg(i)} className={`h-16 w-16 shrink-0 rounded-xl overflow-hidden border ${i === activeImg ? 'border-primary ring-2 ring-primary' : 'border-border'}`}>
                      <img src={im} className="w-full h-full object-cover" alt="" />
                    </button>
                  ))}
                </div>
              )}
            </div>
            {/* Purchase panel */}
            <div>
              {product.category && <Link to={`/products?category=${product.category.id}`} className="text-xs uppercase tracking-widest text-[hsl(var(--brand-terracotta))] font-semibold">{product.category.name}</Link>}
              <h1 className="text-2xl md:text-3xl font-display font-bold mt-1" data-testid="product-title">{product.name}</h1>
              <div className="mt-2 flex items-center gap-2 text-sm">
                {product.avg_rating > 0 && <div className="flex items-center gap-1"><Star className="h-4 w-4 fill-[hsl(var(--brand-marigold))] text-[hsl(var(--brand-marigold))]" />{product.avg_rating} ({product.review_count})</div>}
                <Badge variant="secondary">MOQ: {product.moq} {product.unit}</Badge>
                {inStock ? <Badge className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20" variant="outline">In Stock</Badge> : <Badge variant="destructive">Out of Stock</Badge>}
              </div>

              <div className="mt-5 flex items-end gap-3">
                <div className="font-display text-3xl md:text-4xl font-bold text-foreground" data-testid="product-detail-price">{formatINR(product.price)}</div>
                {discount > 0 && <><div className="text-lg text-muted-foreground line-through">{formatINR(product.compare_price)}</div><Badge className="bg-[hsl(var(--brand-marigold))] text-black">-{discount}%</Badge></>}
                <div className="text-xs text-muted-foreground pb-1">per {product.unit}</div>
              </div>
              {product.size && <div className="mt-2 text-sm"><span className="text-muted-foreground">Size:</span> <span className="font-medium">{product.size}</span></div>}

              <p className="mt-4 text-muted-foreground text-sm leading-relaxed">{product.description}</p>

              {/* Quantity */}
              <div className="mt-6 flex items-center gap-3">
                <span className="text-sm text-muted-foreground">Qty:</span>
                <div className="flex items-center border border-border rounded-lg h-11">
                  <button onClick={() => changeQty(-1)} className="px-3 h-full hover:bg-muted" data-testid="qty-decrease"><Minus className="h-4 w-4" /></button>
                  <span className="px-4 font-medium min-w-[3rem] text-center" data-testid="qty-value">{qty}</span>
                  <button onClick={() => changeQty(1)} className="px-3 h-full hover:bg-muted" data-testid="qty-increase"><Plus className="h-4 w-4" /></button>
                </div>
                <span className="text-xs text-muted-foreground">Total: <b>{formatINR(product.price * qty)}</b></span>
              </div>

              {/* Actions */}
              <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Button size="lg" disabled={!inStock} data-testid="detail-add-to-cart"
                  onClick={() => { addItem(product, qty); toast.success('Added to cart'); }}>
                  <ShoppingCart className="h-4 w-4 mr-2" />Add to Cart
                </Button>
                <Button size="lg" variant="default" disabled={!inStock} data-testid="detail-buy-now"
                  onClick={() => { addItem(product, qty); navigate('/checkout'); }} className="bg-[hsl(var(--brand-terracotta))]">
                  Buy Now
                </Button>
              </div>
              <div className="mt-3 flex gap-3">
                <a href={wa} target="_blank" rel="noreferrer" className="flex-1">
                  <Button variant="outline" className="w-full bg-[hsl(var(--brand-teal))] text-white border-[hsl(var(--brand-teal))] hover:bg-[hsl(var(--brand-teal))]/90 hover:text-white" data-testid="detail-whatsapp">
                    <MessageCircle className="h-4 w-4 mr-2" />WhatsApp Inquiry
                  </Button>
                </a>
                <Button variant="outline" onClick={() => { toggle(product.id); toast.success(has(product.id) ? 'Removed from wishlist' : 'Added to wishlist'); }} data-testid="detail-wishlist">
                  <Heart className={`h-4 w-4 ${has(product.id) ? 'fill-destructive text-destructive' : ''}`} />
                </Button>
              </div>

              {/* Trust badges */}
              <div className="mt-6 grid grid-cols-3 gap-2 text-xs">
                <div className="flex items-center gap-2 p-3 bg-muted/40 rounded-lg"><ShieldCheck className="h-4 w-4 text-[hsl(var(--brand-terracotta))]" />GST Invoice</div>
                <div className="flex items-center gap-2 p-3 bg-muted/40 rounded-lg"><Truck className="h-4 w-4 text-[hsl(var(--brand-terracotta))]" />Fast Dispatch</div>
                <div className="flex items-center gap-2 p-3 bg-muted/40 rounded-lg"><Award className="h-4 w-4 text-[hsl(var(--brand-terracotta))]" />Since 1996</div>
              </div>

              {/* Specs */}
              {product.specs && Object.keys(product.specs).length > 0 && (
                <div className="mt-8 border-t border-border pt-6">
                  <div className="font-display font-semibold mb-3">Specifications</div>
                  <dl className="grid grid-cols-2 gap-2 text-sm">
                    {Object.entries(product.specs).map(([k, v]) => (
                      <div key={k} className="flex justify-between border-b border-border/60 py-2">
                        <dt className="text-muted-foreground">{k}</dt><dd className="font-medium">{v}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}
            </div>
          </div>

          {/* Reviews */}
          <div className="mt-14">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-display font-bold">Customer Reviews</h2>
              <Dialog>
                <DialogTrigger asChild><Button variant="outline" data-testid="open-review-dialog">Write a Review</Button></DialogTrigger>
                <DialogContent>
                  <DialogHeader><DialogTitle>Write a Review</DialogTitle></DialogHeader>
                  <form onSubmit={submitReview} className="space-y-3">
                    <Input required placeholder="Your name" value={reviewForm.name} onChange={(e) => setReviewForm({ ...reviewForm, name: e.target.value })} data-testid="review-name-input" />
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground">Rating:</span>
                      {[1, 2, 3, 4, 5].map(n => (
                        <button key={n} type="button" onClick={() => setReviewForm({ ...reviewForm, rating: n })}>
                          <Star className={`h-6 w-6 ${n <= reviewForm.rating ? 'fill-[hsl(var(--brand-marigold))] text-[hsl(var(--brand-marigold))]' : 'text-muted-foreground'}`} />
                        </button>
                      ))}
                    </div>
                    <Input placeholder="Title (optional)" value={reviewForm.title} onChange={(e) => setReviewForm({ ...reviewForm, title: e.target.value })} />
                    <Textarea required placeholder="Share your experience with this product..." rows={4} value={reviewForm.comment} onChange={(e) => setReviewForm({ ...reviewForm, comment: e.target.value })} data-testid="review-comment-input" />
                    <Button type="submit" className="w-full" data-testid="submit-review-button">Submit Review</Button>
                  </form>
                </DialogContent>
              </Dialog>
            </div>
            {reviews.length === 0 ? (
              <div className="text-sm text-muted-foreground bg-card border border-border rounded-2xl p-6 text-center">No reviews yet. Be the first to review!</div>
            ) : (
              <div className="space-y-3">
                {reviews.map(r => (
                  <div key={r.id} className="bg-card border border-border rounded-2xl p-4">
                    <div className="flex items-center gap-1 mb-1">{Array.from({ length: r.rating }).map((_, i) => <Star key={i} className="h-4 w-4 fill-[hsl(var(--brand-marigold))] text-[hsl(var(--brand-marigold))]" />)}</div>
                    {r.title && <div className="font-semibold">{r.title}</div>}
                    <p className="text-sm text-muted-foreground">{r.comment}</p>
                    <div className="text-xs text-muted-foreground mt-2">- {r.name}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Related */}
          {product.related && product.related.length > 0 && (
            <div className="mt-14">
              <h2 className="text-2xl font-display font-bold mb-4">Related Products</h2>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
                {product.related.map(p => <ProductCard key={p.id} product={p} />)}
              </div>
            </div>
          )}
        </Container>
      </Section>
    </div>
  );
}
