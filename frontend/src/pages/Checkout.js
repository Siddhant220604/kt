import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { toast } from 'sonner';
import { useCart } from '../lib/cart';
import { useSettings } from '../lib/settings';
import { api, formatINR } from '../lib/api';
import { Truck, Wallet, QrCode, Landmark, Copy, ChevronLeft, ShoppingBag } from 'lucide-react';

export default function Checkout() {
  const { items, subtotal, clear } = useCart();
  const nav = useNavigate();
  const loc = useLocation();
  const { settings } = useSettings();
  const [placing, setPlacing] = useState(false);
  const [payment, setPayment] = useState('cod');
  const [form, setForm] = useState({
    name: '', mobile: '', email: '', address_line1: '', address_line2: '', city: 'Lucknow', state: 'Uttar Pradesh', pincode: '', landmark: '', gst_number: '', notes: '',
  });
  const [coupon, setCoupon] = useState(loc.state?.coupon || '');
  const [discount, setDiscount] = useState(loc.state?.discount || 0);
  const [couponMsg, setCouponMsg] = useState('');
  const [applied, setApplied] = useState(loc.state?.coupon || '');
  const [coupons, setCoupons] = useState([]);
  const [loadingCoupons, setLoadingCoupons] = useState(false);
  const shipping = subtotal >= (settings.free_shipping_above || 2000) ? 0 : (settings.shipping_flat || 100);
  const total = Math.max(0, subtotal - discount) + (items.length > 0 ? shipping : 0);

  const loadRazorpayScript = () => new Promise((resolve, reject) => {
    if (window.Razorpay) return resolve();
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Unable to load Razorpay script'));
    document.body.appendChild(script);
  });

  const upd = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const couponStatus = (c) => {
    const now = new Date();
    if (c.expiry) {
      const exp = new Date(c.expiry);
      if (!isNaN(exp) && exp < now) return 'Expired';
    }
    if (c.usage_limit && c.used_count >= c.usage_limit) return 'Usage limit reached';
    if (subtotal < (c.min_order || 0)) return `Requires ${formatINR((c.min_order || 0) - subtotal)} more`;
    return 'Available';
  };

  const fetchCoupons = async () => {
    setLoadingCoupons(true);
    try {
      const { data } = await api.get('/coupons/public');
      setCoupons(data || []);
    } catch (err) {
      console.error('Failed to load coupons', err);
    } finally {
      setLoadingCoupons(false);
    }
  };

  useEffect(() => {
    fetchCoupons();
  }, []);

  const applyCoupon = async (code = coupon) => {
    const selected = code.trim();
    if (!selected) return;
    try {
      const { data } = await api.post('/coupons/validate', { code: selected, subtotal });
      setDiscount(data.discount);
      setApplied(data.code);
      setCouponMsg(`Applied! You saved ${formatINR(data.discount)}`);
      setCoupon(data.code);
      toast.success(`Coupon ${data.code} applied`);
    } catch (err) {
      setDiscount(0);
      setApplied('');
      setCouponMsg(err.response?.data?.detail || 'Invalid coupon');
      toast.error(err.response?.data?.detail || 'Invalid coupon');
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!items.length) return toast.error('Cart is empty');
    if (!/^[6-9]\d{9}$/.test(form.mobile)) return toast.error('Enter a valid 10-digit mobile number');
    if (!form.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) return toast.error('Enter a valid email address');
    if (!form.pincode || form.pincode.length < 6) return toast.error('Enter a valid pincode');
    setPlacing(true);

    try {
      const payload = {
        items: items.map(i => ({
          product_id: i.product_id, name: i.name, price: i.price, size: i.size, unit: i.unit,
          image: i.image, quantity: i.quantity, moq: i.moq,
        })),
        address: { name: form.name, mobile: form.mobile, email: form.email, address_line1: form.address_line1, address_line2: form.address_line2, city: form.city, state: form.state, pincode: form.pincode, landmark: form.landmark, gst_number: form.gst_number },
        payment_method: payment,
        notes: form.notes,
        coupon_code: applied,
      };
      const { data } = await api.post('/orders', payload);

      if (payment === 'online') {
        await loadRazorpayScript();
        const { data: paymentData } = await api.post('/payment/create-order', { order_id: data.id, amount: Math.round(Number(data.total || 0) * 100) });

        const rzp = new window.Razorpay({
          key: paymentData.key_id,
          amount: paymentData.amount,
          currency: paymentData.currency,
          name: 'Kiran Traders',
          description: `Order ${paymentData.order_id}`,
          order_id: paymentData.razorpay_order_id,
          prefill: { name: form.name, email: form.email, contact: form.mobile },
          theme: { color: '#4f46e5' },
          modal: {
            ondismiss: () => {
              toast.error('Payment was cancelled');
              setPlacing(false);
            },
          },
          handler: async (response) => {
            try {
              await api.post('/payment/verify', {
                order_id: paymentData.order_id,
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
              });
              clear();
              toast.success('Payment successful! Order placed.');
              nav(`/order-success/${data.id}`, { state: { mobile: form.mobile, order: data } });
            } catch (err) {
              toast.error(err.response?.data?.detail || 'Payment verification failed');
            } finally {
              setPlacing(false);
            }
          },
        });
        rzp.open();
        return;
      }

      clear();
      toast.success('Order placed successfully!');
      nav(`/order-success/${data.id}`, { state: { mobile: form.mobile, order: data } });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to place order');
    } finally {
      if (payment !== 'online') setPlacing(false);
    }
  };

  if (items.length === 0) return (
    <Section><Container className="text-center py-14">
      <ShoppingBag className="h-16 w-16 mx-auto text-muted-foreground/50" />
      <h2 className="text-2xl font-display font-bold mt-4">Your cart is empty</h2>
      <Link to="/products"><Button size="lg" className="mt-4">Continue Shopping</Button></Link>
    </Container></Section>
  );

  return (
    <Section>
      <Container>
        <Link to="/cart" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4"><ChevronLeft className="h-4 w-4" /> Back to cart</Link>
        <h1 className="text-3xl md:text-4xl font-display font-bold mb-6">Checkout</h1>
        <form onSubmit={submit} className="grid lg:grid-cols-[1fr,380px] gap-6">
          <div className="space-y-6">
            {/* Address */}
            <div className="bg-card border border-border rounded-2xl p-5 sm:p-6">
              <div className="font-display font-semibold text-lg mb-4">Delivery Details</div>
              <div className="grid sm:grid-cols-2 gap-3">
                <div><Label className="text-xs text-muted-foreground">Full Name *</Label><Input required value={form.name} onChange={(e) => upd('name', e.target.value)} data-testid="checkout-name-input" /></div>
                <div><Label className="text-xs text-muted-foreground">Mobile Number *</Label><Input required inputMode="numeric" pattern="[6-9][0-9]{9}" maxLength={10} value={form.mobile} onChange={(e) => upd('mobile', e.target.value.replace(/[^0-9]/g, ''))} data-testid="checkout-mobile-input" /></div>
                <div className="sm:col-span-2"><Label className="text-xs text-muted-foreground">Email *</Label><Input required type="email" value={form.email} onChange={(e) => upd('email', e.target.value)} data-testid="checkout-email-input" /></div>
                <div className="sm:col-span-2"><Label className="text-xs text-muted-foreground">Address Line 1 *</Label><Input required value={form.address_line1} onChange={(e) => upd('address_line1', e.target.value)} data-testid="checkout-address-line1-input" placeholder="House / Shop No., Street" /></div>
                <div className="sm:col-span-2"><Label className="text-xs text-muted-foreground">Address Line 2</Label><Input value={form.address_line2} onChange={(e) => upd('address_line2', e.target.value)} placeholder="Area, Locality" /></div>
                <div><Label className="text-xs text-muted-foreground">City *</Label><Input required value={form.city} onChange={(e) => upd('city', e.target.value)} /></div>
                <div><Label className="text-xs text-muted-foreground">State *</Label><Input required value={form.state} onChange={(e) => upd('state', e.target.value)} /></div>
                <div><Label className="text-xs text-muted-foreground">Pincode *</Label><Input required inputMode="numeric" maxLength={6} value={form.pincode} onChange={(e) => upd('pincode', e.target.value.replace(/[^0-9]/g, ''))} data-testid="checkout-pincode-input" /></div>
                <div><Label className="text-xs text-muted-foreground">Landmark</Label><Input value={form.landmark} onChange={(e) => upd('landmark', e.target.value)} /></div>
                <div className="sm:col-span-2"><Label className="text-xs text-muted-foreground">GST Number (optional)</Label><Input value={form.gst_number} onChange={(e) => upd('gst_number', e.target.value.toUpperCase())} placeholder="For GST invoice" /></div>
                <div className="sm:col-span-2"><Label className="text-xs text-muted-foreground">Order notes (optional)</Label><Textarea rows={2} value={form.notes} onChange={(e) => upd('notes', e.target.value)} placeholder="Any delivery instructions?" /></div>
              </div>
            </div>
            {/* Payment */}
            <div className="bg-card border border-border rounded-2xl p-5 sm:p-6">
              <div className="font-display font-semibold text-lg mb-4">Payment Method</div>
              <RadioGroup value={payment} onValueChange={setPayment} className="grid gap-3">
                <label className={`flex items-start gap-3 p-4 border rounded-xl cursor-pointer ${payment === 'cod' ? 'border-primary bg-primary/5' : 'border-border'}`}>
                  <RadioGroupItem value="cod" id="pm-cod" data-testid="payment-cod" />
                  <div className="flex-1"><div className="flex items-center gap-2 font-medium"><Wallet className="h-4 w-4" /> Cash on Delivery (COD)</div><div className="text-xs text-muted-foreground mt-0.5">Pay when you receive your order. Available across UP.</div></div>
                </label>
                <label className={`flex items-start gap-3 p-4 border rounded-xl cursor-pointer ${payment === 'online' ? 'border-primary bg-primary/5' : 'border-border'}`}>
                  <RadioGroupItem value="online" id="pm-online" data-testid="payment-online" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 font-medium"><Wallet className="h-4 w-4" /> Online Payment (Razorpay)</div>
                    <div className="text-xs text-muted-foreground mt-0.5">Pay securely with UPI, cards, net banking, wallets and EMI via Razorpay.</div>
                  </div>
                </label>
                <label className={`flex items-start gap-3 p-4 border rounded-xl cursor-pointer ${payment === 'upi' ? 'border-primary bg-primary/5' : 'border-border'}`}>
                  <RadioGroupItem value="upi" id="pm-upi" data-testid="payment-upi" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 font-medium"><QrCode className="h-4 w-4" /> UPI (Manual)</div>
                    <div className="text-xs text-muted-foreground mt-0.5">Pay to UPI ID <b>{settings.upi_id || 'kirantraders@ybl'}</b>. Send screenshot on WhatsApp.</div>
                    {payment === 'upi' && (
                      <Dialog>
                        <DialogTrigger asChild><Button type="button" size="sm" variant="outline" className="mt-2" data-testid="view-upi-qr">View UPI QR</Button></DialogTrigger>
                        <DialogContent className="max-w-sm"><DialogHeader><DialogTitle>Scan to Pay</DialogTitle></DialogHeader>
                          <div className="space-y-3 text-center">
                            {settings.upi_qr ? <img src={settings.upi_qr} alt="UPI QR" className="w-64 h-64 mx-auto rounded-xl border border-border" /> : <div className="text-sm text-muted-foreground">QR not available</div>}
                            <div className="text-sm">UPI ID: <b>{settings.upi_id}</b></div>
                            <Button type="button" variant="outline" size="sm" onClick={() => { navigator.clipboard.writeText(settings.upi_id || ''); toast.success('Copied'); }} className="gap-1"><Copy className="h-3.5 w-3.5" />Copy UPI ID</Button>
                          </div>
                        </DialogContent>
                      </Dialog>
                    )}
                  </div>
                </label>
                <label className={`flex items-start gap-3 p-4 border rounded-xl cursor-pointer ${payment === 'bank_transfer' ? 'border-primary bg-primary/5' : 'border-border'}`}>
                  <RadioGroupItem value="bank_transfer" id="pm-bank" data-testid="payment-bank" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 font-medium"><Landmark className="h-4 w-4" /> Bank Transfer / NEFT (Manual)</div>
                    <div className="text-xs text-muted-foreground mt-0.5">Transfer to our bank account. Send transaction reference to confirm.</div>
                    {payment === 'bank_transfer' && settings.bank_details && (
                      <pre className="mt-2 p-3 bg-muted/60 rounded-lg text-xs whitespace-pre-wrap font-mono">{settings.bank_details}</pre>
                    )}
                  </div>
                </label>
              </RadioGroup>
              <div className="mt-4 text-xs text-muted-foreground bg-muted/40 rounded-lg p-3">
                <Truck className="h-3.5 w-3.5 inline mr-1" /> For UPI/Bank Transfer orders, we’ll confirm your order after receiving payment. Send screenshot on WhatsApp {settings.whatsapp}.
              </div>
            </div>
          </div>
          {/* Summary */}
          <div>
            <div className="bg-card border border-border rounded-2xl p-5 sticky top-24">
              <div className="font-display font-semibold mb-4">Order Summary</div>
              <div className="space-y-2 max-h-64 overflow-auto text-sm mb-3">
                {items.map(it => (
                  <div key={it.product_id} className="flex gap-2">
                    <img src={it.image || 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=100&q=80'} alt="" className="h-12 w-12 rounded-lg object-cover" />
                    <div className="flex-1 min-w-0">
                      <div className="line-clamp-1 text-xs">{it.name}</div>
                      <div className="text-[10px] text-muted-foreground">{it.quantity} × {formatINR(it.price)}</div>
                    </div>
                    <div className="text-xs font-medium">{formatINR(it.price * it.quantity)}</div>
                  </div>
                ))}
              </div>
              <div className="space-y-3 text-sm border-t border-border pt-3">
                <div>
                  <Label className="text-xs text-muted-foreground">Coupon code</Label>
                  <div className="mt-2 flex gap-2">
                    <Input value={coupon} onChange={(e) => setCoupon(e.target.value)} placeholder="Enter coupon code" />
                    <Button type="button" variant="outline" onClick={() => applyCoupon()} className="whitespace-nowrap">Apply</Button>
                  </div>
                  {couponMsg && <div className="mt-2 text-xs text-muted-foreground">{couponMsg}</div>}
                  {applied && (
                    <div className="mt-2 flex items-center justify-between gap-2 text-xs text-emerald-600">
                      <span>Applied coupon: {applied}</span>
                      <button type="button" className="text-[11px] text-primary hover:underline" onClick={() => { setApplied(''); setDiscount(0); setCoupon(''); setCouponMsg('Coupon removed'); }}>
                        Remove
                      </button>
                    </div>
                  )}
                  <div className="mt-4">
                    <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
                      <span>Available coupons</span>
                      {loadingCoupons && <span>Loading...</span>}
                    </div>
                    <div className="space-y-2 max-h-52 overflow-auto">
                      {coupons.length === 0 && !loadingCoupons && <div className="text-xs text-muted-foreground">No coupons available right now.</div>}
                      {coupons.sort((a, b) => {
                        const statusOrder = { 'Available': 0, 'Requires': 1, 'Expired': 2, 'Usage limit reached': 3 };
                        const sa = couponStatus(a);
                        const sb = couponStatus(b);
                        return (statusOrder[sa.split(' ')[0]] ?? 4) - (statusOrder[sb.split(' ')[0]] ?? 4);
                      }).map((c) => {
                        const status = couponStatus(c);
                        const available = status === 'Available';
                        return (
                          <button
                            key={c.code}
                            type="button"
                            className={`w-full text-left px-3 py-2 rounded-lg border ${available ? 'border-border bg-background hover:border-primary' : 'border-border/50 bg-muted/40 text-muted-foreground'} ${applied === c.code ? 'ring-2 ring-primary/50' : ''}`}
                            onClick={() => { setCoupon(c.code); if (available) applyCoupon(); }}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div>
                                <div className="font-medium text-sm">{c.code}</div>
                                <div className="text-[11px] text-muted-foreground mt-0.5">{c.type === 'percent' ? `${c.value}% off` : `${formatINR(c.value)} off`} {c.min_order ? `on orders above ${formatINR(c.min_order)}` : ''}</div>
                              </div>
                              <span className={`text-[11px] ${available ? 'text-emerald-600' : 'text-muted-foreground'}`}>{status}</span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
                <div className="flex justify-between"><span>Subtotal</span><span>{formatINR(subtotal)}</span></div>
                {discount > 0 && <div className="flex justify-between text-emerald-600"><span>Discount ({applied})</span><span>-{formatINR(discount)}</span></div>}
                <div className="flex justify-between"><span>Shipping</span><span>{shipping === 0 ? 'FREE' : formatINR(shipping)}</span></div>
                <div className="border-t border-border pt-2 flex justify-between font-display font-bold text-lg"><span>Total</span><span data-testid="checkout-total">{formatINR(total)}</span></div>
              </div>
              <Button type="submit" size="lg" className="w-full mt-4" disabled={placing} data-testid="place-order-button">
                {placing ? (payment === 'online' ? 'Processing payment...' : 'Placing order...') : (payment === 'online' ? `Pay Now • ${formatINR(total)}` : `Place Order • ${formatINR(total)}`)}
              </Button>
              <div className="text-[10px] text-muted-foreground text-center mt-2">By placing the order, you agree to our terms.</div>
            </div>
          </div>
        </form>
      </Container>
    </Section>
  );
}
