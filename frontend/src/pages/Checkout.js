import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { useCart } from '../lib/cart';
import { useSettings } from '../lib/settings';
import { api, formatINR } from '../lib/api';
import { Wallet, ChevronLeft, ShoppingBag } from 'lucide-react';

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
  const [addresses, setAddresses] = useState([]);
  const [selectedAddressId, setSelectedAddressId] = useState('new');
  const [deliveryEstimate, setDeliveryEstimate] = useState(null);
  const [checkingDelivery, setCheckingDelivery] = useState(false);
  const freeShipAbove = settings.free_shipping_above || 2000;
  const deliveryBlocked = !!(deliveryEstimate && deliveryEstimate.delivery_allowed === false);
  const shipping = deliveryEstimate && deliveryEstimate.delivery_allowed
    ? (subtotal >= freeShipAbove ? 0 : deliveryEstimate.shipping)
    : (subtotal >= freeShipAbove ? 0 : (settings.shipping_flat || 100));
  const taxable = Math.max(0, subtotal - discount);
  const cgst = settings.cgst_rate ? Math.round(taxable * (settings.cgst_rate / 100) * 100) / 100 : 0;
  const sgst = settings.sgst_rate ? Math.round(taxable * (settings.sgst_rate / 100) * 100) / 100 : 0;
  const total = taxable + cgst + sgst + (items.length > 0 && !deliveryBlocked ? shipping : 0);

  // Live delivery-charge check as the address is filled in, so a customer sees the charge (or
  // the "we don't deliver there" rejection) before submitting, not after. Debounced and
  // best-effort - a failed/slow estimate call must never block the checkout page itself.
  useEffect(() => {
    if (!form.address_line1 || !form.city || !form.pincode || form.pincode.length < 6) {
      setDeliveryEstimate(null);
      setCheckingDelivery(false);
      return;
    }
    setCheckingDelivery(true);
    const t = setTimeout(async () => {
      try {
        const { data } = await api.post('/delivery/estimate', {
          address_line1: form.address_line1, address_line2: form.address_line2 || '',
          city: form.city, state: form.state, pincode: form.pincode,
        });
        setDeliveryEstimate(data);
      } catch (err) {
        setDeliveryEstimate(null);
      } finally {
        setCheckingDelivery(false);
      }
    }, 700);
    return () => clearTimeout(t);
  }, [form.address_line1, form.address_line2, form.city, form.state, form.pincode]);

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

  const applyAddress = (a) => {
    setSelectedAddressId(a.id);
    setForm(f => ({
      ...f,
      name: a.name, mobile: a.mobile, address_line1: a.address_line1, address_line2: a.address_line2 || '',
      city: a.city, state: a.state, pincode: a.pincode, landmark: a.landmark || '', gst_number: a.gst_number || '',
    }));
  };

  const useNewAddress = () => {
    setSelectedAddressId('new');
    setForm(f => ({ ...f, address_line1: '', address_line2: '', city: 'Lucknow', state: 'Uttar Pradesh', pincode: '', landmark: '', gst_number: '' }));
  };

  // Pre-fill delivery details from the signed-in customer's account (checkout is now only
  // reachable while logged in, via CustomerProtectedRoute) - fields stay fully editable since
  // a delivery address can differ from any saved one. A saved address (if any default/first
  // one exists) takes priority over the bare profile name/mobile, being more specific.
  useEffect(() => {
    api.get('/customer/profile').then(({ data }) => {
      setForm(f => ({ ...f, name: f.name || data.name || '', mobile: f.mobile || data.mobile || '', email: f.email || data.email || '' }));
    }).catch(() => {});
    api.get('/customer/addresses').then(({ data }) => {
      setAddresses(data || []);
      const def = (data || []).find(a => a.is_default) || (data || [])[0];
      if (def) applyAddress(def);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Opportunistically snapshot the cart once we have a valid mobile number, so an abandoned
  // checkout can still get a WhatsApp reminder later. Debounced and best-effort - failures here
  // must never block or interrupt checkout.
  useEffect(() => {
    if (!/^[6-9]\d{9}$/.test(form.mobile) || items.length === 0) return;
    const t = setTimeout(() => {
      api.post('/cart/sync', {
        mobile: form.mobile,
        name: form.name,
        items: items.map(i => ({ product_id: i.product_id, name: i.name, price: i.price, quantity: i.quantity })),
        subtotal,
      }).catch(() => {});
    }, 1500);
    return () => clearTimeout(t);
  }, [form.mobile, form.name, items, subtotal]);

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
    if (deliveryBlocked) return toast.error(deliveryEstimate.reason || 'Delivery is not available at this address');
    setPlacing(true);

    let rzpOpened = false;
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
          method: {
            upi: true,
            card: true,
            netbanking: true,
            wallet: true,
            emandate: false,
          },
          modal: {
            ondismiss: () => {
              toast.error('Payment was cancelled');
              // Fire-and-forget: let the backend send the "payment didn't complete, try again"
              // WhatsApp nudge. Never block or surface errors from this - it must not affect the
              // customer's ability to retry checkout.
              api.post('/payment/failed', { order_id: data.id, reason: 'dismissed' }).catch(() => {});
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
              // Same nudge as the dismiss path - the payment didn't complete from our side.
              api.post('/payment/failed', { order_id: data.id, reason: 'verification_failed' }).catch(() => {});
            } finally {
              setPlacing(false);
            }
          },
        });
        rzpOpened = true;
        rzp.open();
        return;
      }

      clear();
      toast.success('Order placed successfully!');
      nav(`/order-success/${data.id}`, { state: { mobile: form.mobile, order: data } });
    } catch (err) {
      if (err.response?.status === 401 || err.response?.status === 403) {
        toast.error('Your session expired. Please sign in again.');
        nav('/signup', { state: { from: loc } });
      } else {
        toast.error(err.response?.data?.detail || 'Failed to place order');
      }
    } finally {
      // Once the Razorpay modal has opened, its own handler/ondismiss callbacks own
      // resetting `placing` - resetting it here too would let the button unlock while
      // the modal is still open.
      if (!rzpOpened) setPlacing(false);
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
        <div className="flex items-center justify-between flex-wrap gap-2 mb-6">
          <h1 className="text-3xl md:text-4xl font-display font-bold">Checkout</h1>
          <div className="text-xs text-muted-foreground">
            Signed in as <b>{localStorage.getItem('kt_customer_email')}</b> · <Link to="/account" className="text-primary hover:underline">My Account</Link>
          </div>
        </div>
        <form onSubmit={submit} className="grid lg:grid-cols-[1fr,380px] gap-6">
          <div className="space-y-6">
            {addresses.length > 0 && (
              <div className="bg-card border border-border rounded-2xl p-5 sm:p-6">
                <div className="font-display font-semibold text-lg mb-4">Choose a delivery address</div>
                <div className="grid sm:grid-cols-2 gap-3">
                  {addresses.map(a => (
                    <label key={a.id} className={`flex items-start gap-2 p-3 border rounded-xl cursor-pointer text-sm ${selectedAddressId === a.id ? 'border-primary bg-primary/5' : 'border-border'}`}>
                      <input type="radio" name="saved-address" className="mt-1" checked={selectedAddressId === a.id} onChange={() => applyAddress(a)} />
                      <div className="min-w-0">
                        <div className="font-medium">{a.label || 'Address'}{a.is_default && <span className="text-[10px] text-primary ml-1">(Default)</span>}</div>
                        <div className="text-xs text-muted-foreground mt-0.5">{a.name} · {a.mobile}</div>
                        <div className="text-xs text-muted-foreground">{a.address_line1}, {a.city}, {a.state} - {a.pincode}</div>
                      </div>
                    </label>
                  ))}
                  <label className={`flex items-center gap-2 p-3 border rounded-xl cursor-pointer text-sm ${selectedAddressId === 'new' ? 'border-primary bg-primary/5' : 'border-border'}`}>
                    <input type="radio" name="saved-address" checked={selectedAddressId === 'new'} onChange={useNewAddress} />
                    <div className="font-medium">+ Deliver to a new address</div>
                  </label>
                </div>
              </div>
            )}
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
              {checkingDelivery && <div className="mt-3 text-xs text-muted-foreground">Checking delivery availability...</div>}
              {deliveryBlocked && (
                <div className="mt-3 text-sm text-red-600">{deliveryEstimate.reason}</div>
              )}
              {!checkingDelivery && deliveryEstimate && deliveryEstimate.delivery_allowed && (
                <div className="mt-3 text-xs text-emerald-600">
                  Delivery available{deliveryEstimate.distance_km ? ` · ${deliveryEstimate.distance_km} km away` : ''}
                </div>
              )}
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
              </RadioGroup>
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
                <div className="flex justify-between">
                  <span>Shipping{deliveryEstimate?.delivery_allowed && deliveryEstimate.distance_km ? ` (${deliveryEstimate.distance_km} km)` : ''}</span>
                  <span>{deliveryBlocked ? '—' : (shipping === 0 ? 'FREE' : formatINR(shipping))}</span>
                </div>
                {cgst > 0 && <div className="flex justify-between"><span>CGST ({settings.cgst_rate}%)</span><span>{formatINR(cgst)}</span></div>}
                {sgst > 0 && <div className="flex justify-between"><span>SGST ({settings.sgst_rate}%)</span><span>{formatINR(sgst)}</span></div>}
                <div className="border-t border-border pt-2 flex justify-between font-display font-bold text-lg"><span>Total</span><span data-testid="checkout-total">{formatINR(total)}</span></div>
              </div>
              {deliveryBlocked && (
                <div className="mt-3 text-xs text-red-600 text-center">{deliveryEstimate.reason}</div>
              )}
              <Button type="submit" size="lg" className="w-full mt-4" disabled={placing || deliveryBlocked} data-testid="place-order-button">
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
