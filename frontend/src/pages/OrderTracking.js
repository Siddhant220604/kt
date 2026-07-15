import React, { useState, useEffect } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { CheckCircle2, Circle, Truck, Package, Clock, MessageCircle, FileText, Search } from 'lucide-react';
import { api, formatINR, API } from '../lib/api';
import { toast } from 'sonner';
import { useSettings } from '../lib/settings';

const STEPS = [
  { key: 'pending', label: 'Order Placed', icon: Clock },
  { key: 'confirmed', label: 'Confirmed', icon: CheckCircle2 },
  { key: 'packed', label: 'Packed', icon: Package },
  { key: 'out for delivery', label: 'Out for Delivery', icon: Truck },
  { key: 'delivered', label: 'Delivered', icon: CheckCircle2 },
];

export default function OrderTracking() {
  const { orderId: paramOid } = useParams();
  const loc = useLocation();
  const [oid, setOid] = useState(paramOid || '');
  const [mobile, setMobile] = useState(loc.state?.mobile || '');
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(false);
  const { settings } = useSettings();

  const doTrack = async (e) => {
    e && e.preventDefault();
    if (!oid || !mobile) return toast.error('Enter both Order ID and mobile');
    setLoading(true);
    try {
      const { data } = await api.post('/orders/track', { order_id: oid.trim().toUpperCase(), mobile: mobile.trim() });
      setOrder(data);
    } catch (e) { toast.error(e.response?.data?.detail || 'Order not found'); setOrder(null); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    if (paramOid && loc.state?.mobile) {
      setOid(paramOid); setMobile(loc.state.mobile);
      // auto submit
      (async () => {
        setLoading(true);
        try {
          const { data } = await api.post('/orders/track', { order_id: paramOid.trim().toUpperCase(), mobile: loc.state.mobile.trim() });
          setOrder(data);
        } catch {} finally { setLoading(false); }
      })();
    }
    // eslint-disable-next-line
  }, [paramOid]);

  const currentIdx = order ? Math.max(0, STEPS.findIndex(s => s.key === order.status)) : -1;

  return (
    <Section>
      <Container className="max-w-3xl">
        <h1 className="text-3xl md:text-4xl font-display font-bold">Track Your Order</h1>
        <p className="text-muted-foreground mt-1">Enter your Order ID and mobile number to see live status.</p>
        <form onSubmit={doTrack} className="mt-6 bg-card border border-border rounded-2xl p-5 grid sm:grid-cols-[1fr,1fr,auto] gap-3">
          <div><Label className="text-xs text-muted-foreground">Order ID</Label><Input value={oid} onChange={(e) => setOid(e.target.value.toUpperCase())} placeholder="KT20260701AB12CD" data-testid="track-order-id" /></div>
          <div><Label className="text-xs text-muted-foreground">Mobile</Label><Input value={mobile} onChange={(e) => setMobile(e.target.value.replace(/[^0-9]/g, ''))} maxLength={10} data-testid="track-mobile" /></div>
          <div className="self-end"><Button type="submit" disabled={loading} className="gap-2 h-10" data-testid="track-submit"><Search className="h-4 w-4" />{loading ? 'Checking...' : 'Track'}</Button></div>
        </form>
        {order && order.status === 'cancelled' && (
          <div className="mt-6 bg-destructive/10 border border-destructive/30 rounded-2xl p-4 text-destructive font-medium">This order has been cancelled.</div>
        )}
        {order && order.status !== 'cancelled' && (
          <div className="mt-6 space-y-4">
            <div className="bg-card border border-border rounded-2xl p-5">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <div className="text-xs text-muted-foreground uppercase">Order</div>
                  <div className="font-mono font-bold text-lg">{order.id}</div>
                </div>
                <Badge className="text-sm uppercase">{order.status}</Badge>
              </div>
              {/* Timeline */}
              <div className="mt-6">
                <div className="hidden sm:flex items-center justify-between relative">
                  <div className="absolute top-5 left-5 right-5 h-1 bg-muted rounded-full">
                    <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${Math.max(0, currentIdx) / (STEPS.length - 1) * 100}%` }} />
                  </div>
                  {STEPS.map((s, i) => {
                    const Icon = s.icon;
                    const done = i <= currentIdx;
                    return (
                      <div key={s.key} className="relative flex flex-col items-center gap-2 flex-1">
                        <div className={`h-10 w-10 rounded-full grid place-items-center border-2 ${done ? 'bg-primary border-primary text-primary-foreground' : 'bg-background border-border text-muted-foreground'}`}>
                          <Icon className="h-4 w-4" />
                        </div>
                        <div className={`text-xs font-medium ${done ? 'text-foreground' : 'text-muted-foreground'}`}>{s.label}</div>
                      </div>
                    );
                  })}
                </div>
                {/* Mobile timeline */}
                <div className="sm:hidden space-y-3">
                  {STEPS.map((s, i) => {
                    const Icon = s.icon;
                    const done = i <= currentIdx;
                    return (
                      <div key={s.key} className="flex items-center gap-3">
                        <div className={`h-9 w-9 rounded-full grid place-items-center ${done ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}><Icon className="h-4 w-4" /></div>
                        <div className={`text-sm ${done ? '' : 'text-muted-foreground'}`}>{s.label}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
              {order.status_history && (
                <div className="mt-6 border-t border-border pt-4">
                  <div className="text-xs font-semibold uppercase text-muted-foreground mb-2">Timeline</div>
                  <div className="space-y-2">
                    {[...order.status_history].reverse().map((h, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <Circle className="h-2 w-2 fill-primary text-primary" />
                        <span className="font-medium capitalize">{h.status}</span>
                        <span className="text-muted-foreground text-xs ml-auto">{h.at?.slice(0, 16).replace('T', ' ')}</span>
                        {h.note && <div className="text-xs text-muted-foreground w-full pl-4">{h.note}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Order details */}
            <div className="bg-card border border-border rounded-2xl p-5">
              <div className="font-display font-semibold mb-3">Order Details</div>
              <div className="space-y-2 text-sm">
                {order.items.map((it, i) => (
                  <div key={i} className="flex justify-between">
                    <div>{it.name} × {it.quantity}</div>
                    <div>{formatINR(it.total)}</div>
                  </div>
                ))}
                <div className="border-t border-border pt-2 flex justify-between"><span>Subtotal</span><span>{formatINR(order.subtotal)}</span></div>
                {order.discount > 0 && <div className="flex justify-between text-emerald-600"><span>Discount{order.coupon_code ? ` (${order.coupon_code})` : ''}</span><span>-{formatINR(order.discount)}</span></div>}
                {order.is_interstate ? (
                  order.tax > 0 && <div className="flex justify-between"><span>IGST ({order.tax_rate}%)</span><span>{formatINR(order.tax)}</span></div>
                ) : (
                  <>
                    {order.cgst_rate > 0 && <div className="flex justify-between"><span>CGST ({order.cgst_rate}%)</span><span>{formatINR(Math.round(Math.max(0, order.subtotal - (order.discount || 0)) * order.cgst_rate) / 100)}</span></div>}
                    {order.sgst_rate > 0 && <div className="flex justify-between"><span>SGST ({order.sgst_rate}%)</span><span>{formatINR(Math.round(Math.max(0, order.subtotal - (order.discount || 0)) * order.sgst_rate) / 100)}</span></div>}
                  </>
                )}
                {order.shipping > 0 && <div className="flex justify-between"><span>Shipping</span><span>{formatINR(order.shipping)}</span></div>}
                <div className="flex justify-between font-display font-bold text-lg pt-1"><span>Total</span><span>{formatINR(order.total)}</span></div>
              </div>
              <div className="mt-4 grid sm:grid-cols-2 gap-2 text-xs text-muted-foreground">
                <div><b>Delivery:</b> {order.address.name}, {order.address.address_line1}, {order.address.city} - {order.address.pincode}</div>
                <div><b>Payment:</b> {order.payment_method?.toUpperCase()}</div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <a
                  href={`${API}/orders/${order.id}/invoice?mobile=${order.address.mobile}`}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => {
                    if (order.status !== 'delivered') {
                      e.preventDefault();
                      toast.error('Invoice will be available for download once your order is delivered.');
                    }
                  }}
                >
                  <Button variant="outline" className="gap-2" data-testid="track-download-invoice"><FileText className="h-4 w-4" />Download Invoice PDF</Button>
                </a>
                <a href={`https://wa.me/${settings.whatsapp || '919876543210'}?text=${encodeURIComponent(`Hi, I want an update on order ${order.id}`)}`} target="_blank" rel="noreferrer"><Button variant="outline" className="gap-2"><MessageCircle className="h-4 w-4" />WhatsApp</Button></a>
              </div>
            </div>
          </div>
        )}
      </Container>
    </Section>
  );
}
