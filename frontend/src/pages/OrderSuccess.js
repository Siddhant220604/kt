import React, { useEffect, useState } from 'react';
import { useParams, useLocation, Link } from 'react-router-dom';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';
import { CheckCircle2, Package, Truck, Copy, FileText, MessageCircle, ArrowRight } from 'lucide-react';
import { formatINR, api, API } from '../lib/api';
import { toast } from 'sonner';
import { useSettings } from '../lib/settings';

export default function OrderSuccess() {
  const { orderId } = useParams();
  const loc = useLocation();
  const { settings } = useSettings();
  const [order, setOrder] = useState(loc.state?.order || null);
  const mobile = loc.state?.mobile || '';

  useEffect(() => {
    if (!order && orderId && mobile) {
      api.post('/orders/track', { order_id: orderId, mobile }).then(r => setOrder(r.data)).catch(() => {});
    }
  }, [order, orderId, mobile]);

  return (
    <Section>
      <Container className="max-w-2xl">
        <div className="bg-card border border-border rounded-2xl p-6 sm:p-8 text-center">
          <div className="h-16 w-16 rounded-full bg-emerald-500/10 grid place-items-center mx-auto"><CheckCircle2 className="h-8 w-8 text-emerald-600" /></div>
          <h1 className="text-2xl sm:text-3xl font-display font-bold mt-4">Order Placed Successfully!</h1>
          <p className="text-muted-foreground mt-2">Thank you for choosing Kiran Traders. We'll confirm and dispatch your order shortly.</p>
          <div className="mt-6 inline-flex items-center gap-2 bg-muted/50 border border-border rounded-xl px-4 py-3">
            <span className="text-sm text-muted-foreground">Order ID:</span>
            <span className="font-mono font-bold text-lg" data-testid="success-order-id">{orderId}</span>
            <button onClick={() => { navigator.clipboard.writeText(orderId); toast.success('Copied'); }} className="ml-2 p-1 hover:bg-background rounded"><Copy className="h-4 w-4" /></button>
          </div>
          {order && (
            <div className="mt-6 text-left space-y-1 text-sm bg-muted/40 rounded-xl p-4">
              <div className="flex justify-between"><span>Total</span><b>{formatINR(order.total)}</b></div>
              <div className="flex justify-between"><span>Payment</span><b className="uppercase">{order.payment_method?.replace('_', ' ')}</b></div>
              <div className="flex justify-between"><span>Deliver to</span><b>{order.address?.name}, {order.address?.city}</b></div>
            </div>
          )}
          {order && (order.payment_method === 'upi' || order.payment_method === 'bank_transfer') && (
            <div className="mt-4 text-sm bg-amber-500/10 border border-amber-500/30 text-amber-900 dark:text-amber-100 rounded-xl p-4 text-left">
              <b>Action required:</b> Please complete the payment and send screenshot to WhatsApp <b>{settings.whatsapp}</b>. Order will be confirmed once payment is verified.
            </div>
          )}
          <div className="mt-6 grid sm:grid-cols-2 gap-3">
            <Link to={`/track/${orderId}`} state={{ mobile }}><Button variant="outline" className="w-full gap-2"><Truck className="h-4 w-4" />Track Order</Button></Link>
            <a href={`${API}/orders/${orderId}/invoice${mobile ? `?mobile=${mobile}` : ''}`} target="_blank" rel="noreferrer"><Button variant="outline" className="w-full gap-2" data-testid="success-download-invoice"><FileText className="h-4 w-4" />Download Invoice</Button></a>
          </div>
          <div className="mt-3 flex gap-3">
            <a href={`https://wa.me/${settings.whatsapp || '919876543210'}?text=${encodeURIComponent(`Hi, I just placed order ${orderId}`)}`} target="_blank" rel="noreferrer" className="flex-1">
              <Button className="w-full gap-2 bg-[hsl(var(--brand-teal))] hover:bg-[hsl(var(--brand-teal))]/90"><MessageCircle className="h-4 w-4" />WhatsApp Us</Button>
            </a>
            <Link to="/products" className="flex-1"><Button className="w-full gap-2">Continue Shopping <ArrowRight className="h-4 w-4" /></Button></Link>
          </div>
        </div>
      </Container>
    </Section>
  );
}
