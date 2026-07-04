import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Minus, Plus, Trash2, ShoppingBag, MessageCircle, ArrowRight } from 'lucide-react';
import { useCart } from '../lib/cart';
import { formatINR, api } from '../lib/api';
import { toast } from 'sonner';
import { useSettings } from '../lib/settings';

export default function Cart() {
  const { items, updateQty, removeItem, subtotal, clear } = useCart();
  const [coupon, setCoupon] = useState('');
  const [discount, setDiscount] = useState(0);
  const [couponMsg, setCouponMsg] = useState('');
  const [applied, setApplied] = useState('');
  const navigate = useNavigate();
  const { settings } = useSettings();

  const shipping = subtotal >= (settings.free_shipping_above || 2000) ? 0 : (settings.shipping_flat || 100);
  const total = Math.max(0, subtotal - discount) + (subtotal > 0 ? shipping : 0);

  const applyCoupon = async () => {
    if (!coupon.trim()) return;
    try {
      const { data } = await api.post('/coupons/validate', { code: coupon.trim(), subtotal });
      setDiscount(data.discount);
      setApplied(data.code);
      setCouponMsg(`Applied! You saved ${formatINR(data.discount)}`);
      toast.success(`Coupon ${data.code} applied`);
    } catch (e) { setCouponMsg(e.response?.data?.detail || 'Invalid coupon'); setDiscount(0); setApplied(''); toast.error(e.response?.data?.detail || 'Invalid coupon'); }
  };

  if (items.length === 0) return (
    <Section>
      <Container className="text-center py-14">
        <ShoppingBag className="h-16 w-16 mx-auto text-muted-foreground/50" />
        <h2 className="text-2xl font-display font-bold mt-4">Your cart is empty</h2>
        <p className="text-muted-foreground mt-1">Discover our wholesale range and add items to get started.</p>
        <Link to="/products"><Button size="lg" className="mt-6">Browse Products</Button></Link>
      </Container>
    </Section>
  );

  return (
    <Section>
      <Container>
        <h1 className="text-3xl md:text-4xl font-display font-bold mb-6">Your Cart</h1>
        <div className="grid lg:grid-cols-[1fr,380px] gap-6">
          <div className="space-y-3">
            {items.map(it => (
              <div key={it.product_id} className="bg-card border border-border rounded-2xl p-4 flex gap-3" data-testid={`cart-item-${it.product_id}`}>
                <img src={it.image || 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=200&q=80'} alt={it.name} className="h-24 w-24 rounded-xl object-cover shrink-0" />
                <div className="flex-1 min-w-0">
                  <Link to={`/products/${it.product_id}`} className="font-medium line-clamp-2 hover:text-primary">{it.name}</Link>
                  <div className="text-xs text-muted-foreground mt-1">{it.size} · per {it.unit} · MOQ: {it.moq}</div>
                  <div className="mt-2 flex items-center gap-3 flex-wrap">
                    <div className="flex items-center border border-border rounded-lg">
                      <button onClick={() => updateQty(it.product_id, it.quantity - 1)} className="px-2.5 py-1.5 hover:bg-muted"><Minus className="h-3.5 w-3.5" /></button>
                      <span className="px-3 text-sm font-medium" data-testid={`cart-qty-${it.product_id}`}>{it.quantity}</span>
                      <button onClick={() => updateQty(it.product_id, it.quantity + 1)} className="px-2.5 py-1.5 hover:bg-muted"><Plus className="h-3.5 w-3.5" /></button>
                    </div>
                    <div className="font-display font-bold">{formatINR(it.price * it.quantity)}</div>
                    <button onClick={() => { removeItem(it.product_id); toast('Removed'); }} className="ml-auto text-destructive p-1.5 hover:bg-destructive/10 rounded" data-testid={`cart-remove-${it.product_id}`}><Trash2 className="h-4 w-4" /></button>
                  </div>
                </div>
              </div>
            ))}
            <div className="flex justify-between text-sm">
              <button onClick={() => { clear(); toast('Cart cleared'); }} className="text-muted-foreground hover:text-destructive">Clear cart</button>
              <Link to="/products" className="text-primary hover:underline">Continue shopping</Link>
            </div>
          </div>
          <div>
            <div className="bg-card border border-border rounded-2xl p-5 sticky top-24">
              <div className="font-display font-semibold mb-4">Order Summary</div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span>Subtotal</span><span data-testid="cart-subtotal">{formatINR(subtotal)}</span></div>
                {discount > 0 && <div className="flex justify-between text-emerald-600"><span>Discount ({applied})</span><span>-{formatINR(discount)}</span></div>}
                <div className="flex justify-between"><span>Shipping</span><span>{shipping === 0 ? 'FREE' : formatINR(shipping)}</span></div>
                <div className="border-t border-border pt-2 mt-2 flex justify-between font-display font-bold text-lg"><span>Total</span><span data-testid="cart-total">{formatINR(total)}</span></div>
                {subtotal < (settings.free_shipping_above || 2000) && <div className="text-xs text-muted-foreground">Add {formatINR((settings.free_shipping_above || 2000) - subtotal)} more for FREE shipping</div>}
              </div>
              <div className="mt-4">
                <a href="https://wa.me/919044057739?text=Hi%20Kiran%20Traders%2C%20I%20want%20to%20place%20a%20bulk%20order%20and%20check%20discount%20pricing." target="_blank" rel="noreferrer" data-testid="cart-bulk-whatsapp">
                  <Button variant="outline" className="w-full gap-2 bg-[hsl(var(--brand-teal))] text-white border-[hsl(var(--brand-teal))] hover:bg-[hsl(var(--brand-teal))]/90 hover:text-white">
                    Bulk order? Get discount on WhatsApp
                  </Button>
                </a>
                <div className="text-[10px] text-muted-foreground mt-2 text-center">Volume pricing on cartons and pallets — chat with our team.</div>
              </div>
              <Button size="lg" className="w-full mt-4 gap-2" onClick={() => navigate('/checkout', { state: { coupon: applied, discount } })} data-testid="proceed-to-checkout">
                Proceed to Checkout <ArrowRight className="h-4 w-4" />
              </Button>
              <a href={`https://wa.me/${settings.whatsapp || '919876543210'}`} target="_blank" rel="noreferrer" className="mt-2 block">
                <Button variant="outline" className="w-full gap-2"><MessageCircle className="h-4 w-4" />Order via WhatsApp</Button>
              </a>
            </div>
          </div>
        </div>
      </Container>
    </Section>
  );
}
