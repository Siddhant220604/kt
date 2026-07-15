import React, { useCallback, useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api, formatINR, API } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Textarea } from '../../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { ChevronLeft, FileText, MessageCircle } from 'lucide-react';
import { toast } from 'sonner';

const statusColor = { pending: 'bg-amber-500/10 text-amber-700 border-amber-500/20', confirmed: 'bg-sky-500/10 text-sky-700 border-sky-500/20', processing: 'bg-cyan-500/10 text-cyan-700 border-cyan-500/20', packed: 'bg-indigo-500/10 text-indigo-700 border-indigo-500/20', 'out for delivery': 'bg-purple-500/10 text-purple-700 border-purple-500/20', delivered: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20', cancelled: 'bg-red-500/10 text-red-700 border-red-500/20' };

export default function AdminOrderDetail() {
  const { oid } = useParams();
  const [order, setOrder] = useState(null);
  const [next, setNext] = useState('');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [returnNote, setReturnNote] = useState('');

  const load = useCallback(() => api.get(`/orders/${oid}`).then(r => { setOrder(r.data); setNext(r.data.status); }), [oid]);
  useEffect(() => { load(); }, [load]);

  const updateStatus = async () => {
    setSaving(true);
    try {
      await api.put(`/orders/${oid}/status`, { status: next, tracking_note: note });
      toast.success('Status updated');
      setNote('');
      await load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Update failed'); }
    finally { setSaving(false); }
  };

  const markRefunded = async () => {
    if (!window.confirm('Confirm the refund has actually been processed (bank transfer/UPI)?')) return;
    try {
      await api.post(`/orders/${oid}/mark-refunded`);
      toast.success('Marked as refunded');
      await load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to update'); }
  };

  const resolveReturn = async (status) => {
    if (status === 'refunded' && !window.confirm('Confirm the refund has actually been processed (bank transfer/UPI)?')) return;
    try {
      await api.put(`/orders/${oid}/return`, { status, note: returnNote });
      setReturnNote('');
      toast.success('Return request updated');
      await load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to update'); }
  };

  if (!order) return <div>Loading...</div>;

  return (
    <div className="space-y-4">
      <Link to="/admin/orders" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ChevronLeft className="h-4 w-4" />Back to orders</Link>
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="text-xs text-muted-foreground uppercase">Order</div>
          <h1 className="font-mono font-bold text-2xl">{order.id}</h1>
        </div>
        <div className="flex items-center gap-2">
          <Badge className={statusColor[order.status] || ''} variant="outline">{order.status.toUpperCase()}</Badge>
          <a href={`${API}/orders/${order.id}/invoice?mobile=${order.address?.mobile || ''}`} target="_blank" rel="noreferrer"><Button variant="outline" className="gap-2" data-testid="admin-invoice-download"><FileText className="h-4 w-4" />Invoice PDF</Button></a>
          <a href={`https://wa.me/${order.address?.mobile}`} target="_blank" rel="noreferrer"><Button variant="outline" className="gap-2"><MessageCircle className="h-4 w-4" />Customer</Button></a>
        </div>
      </div>
      {order.refund_status === 'pending' && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-4 flex items-center justify-between flex-wrap gap-3">
          <div className="text-sm text-red-700 dark:text-red-300"><b>Refund pending:</b> this order was paid and then cancelled. Process the refund (bank transfer/UPI) and mark it done here.</div>
          <Button size="sm" onClick={markRefunded} data-testid="admin-mark-refunded">Mark as Refunded</Button>
        </div>
      )}
      {order.refund_status === 'refunded' && (
        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-2xl p-3 text-sm text-emerald-700 dark:text-emerald-300">
          Refunded on {order.refunded_at?.slice(0, 10)}
        </div>
      )}
      {order.return_request && (
        <div className="bg-card border border-border rounded-2xl p-4 space-y-2">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="font-display font-semibold">Return Request</div>
            <Badge variant="outline" className="capitalize">{order.return_request.status}</Badge>
          </div>
          <div className="text-sm text-muted-foreground">Reason: {order.return_request.reason}</div>
          <div className="text-sm text-muted-foreground">Items: {order.return_request.items.map(it => `${it.name} × ${it.quantity}`).join(', ')}</div>
          <div className="text-xs text-muted-foreground">Requested {order.return_request.requested_at?.slice(0, 16).replace('T', ' ')}</div>
          {order.return_request.status === 'requested' && (
            <div className="flex flex-wrap gap-2 items-start pt-2">
              <Textarea placeholder="Optional note to the customer" rows={2} value={returnNote} onChange={(e) => setReturnNote(e.target.value)} className="flex-1 min-w-64" />
              <Button size="sm" onClick={() => resolveReturn('approved')} data-testid="admin-return-approve">Approve</Button>
              <Button size="sm" variant="outline" onClick={() => resolveReturn('rejected')} data-testid="admin-return-reject">Reject</Button>
            </div>
          )}
          {order.return_request.status === 'approved' && (
            <div className="flex flex-wrap gap-2 items-start pt-2">
              <Textarea placeholder="Optional note to the customer" rows={2} value={returnNote} onChange={(e) => setReturnNote(e.target.value)} className="flex-1 min-w-64" />
              <Button size="sm" onClick={() => resolveReturn('refunded')} data-testid="admin-return-refund">Mark as Refunded</Button>
            </div>
          )}
          {order.return_request.resolution_note && <div className="text-xs">Note sent: {order.return_request.resolution_note}</div>}
        </div>
      )}
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-card border border-border rounded-2xl p-4">
            <div className="font-display font-semibold mb-3">Items</div>
            <div className="space-y-2">
              {order.items.map((it, i) => (
                <div key={i} className="flex gap-3 items-center border-b border-border last:border-0 pb-2">
                  <img src={it.image || 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=100&q=80'} className="h-14 w-14 rounded-xl object-cover" alt="" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">{it.name}</div>
                    <div className="text-xs text-muted-foreground">{it.size} • {it.quantity} × {formatINR(it.price)}</div>
                  </div>
                  <div className="font-medium">{formatINR(it.total)}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 pt-3 border-t border-border space-y-1 text-sm">
              <div className="flex justify-between"><span>Subtotal</span><span>{formatINR(order.subtotal)}</span></div>
              {order.discount > 0 && <div className="flex justify-between text-emerald-600"><span>Discount ({order.coupon_code})</span><span>-{formatINR(order.discount)}</span></div>}
              {order.shipping > 0 && <div className="flex justify-between"><span>Shipping</span><span>{formatINR(order.shipping)}</span></div>}
              <div className="flex justify-between font-display font-bold text-lg pt-1"><span>Total</span><span>{formatINR(order.total)}</span></div>
            </div>
          </div>

          <div className="bg-card border border-border rounded-2xl p-4">
            <div className="font-display font-semibold mb-3">Update Status</div>
            <div className="flex flex-wrap gap-2 items-start">
              <Select value={next} onValueChange={setNext}>
                <SelectTrigger className="w-52" data-testid="admin-status-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {['pending', 'confirmed', 'packed', 'out for delivery', 'delivered', 'cancelled'].map(s => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}
                </SelectContent>
              </Select>
              <Textarea placeholder="Optional note (e.g., courier tracking #)" rows={2} value={note} onChange={(e) => setNote(e.target.value)} className="flex-1 min-w-64" data-testid="admin-status-note" />
              <Button onClick={updateStatus} disabled={saving} data-testid="admin-status-save">{saving ? 'Saving...' : 'Update Status'}</Button>
            </div>
            {order.status_history && (
              <div className="mt-4 border-t border-border pt-3 space-y-1.5 text-sm">
                {[...order.status_history].reverse().map((h, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Badge variant="outline" className={`capitalize ${statusColor[h.status] || ''}`}>{h.status}</Badge>
                    <span className="text-xs text-muted-foreground">{h.at?.slice(0, 16).replace('T', ' ')}</span>
                    {h.note && <span className="text-xs">— {h.note}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-card border border-border rounded-2xl p-4">
            <div className="font-display font-semibold mb-2">Customer</div>
            <div className="space-y-1 text-sm">
              <div><b>{order.address.name}</b></div>
              <div>{order.address.mobile}</div>
              {order.address.email && <div className="text-muted-foreground">{order.address.email}</div>}
              {order.address.gst_number && <div className="text-xs">GSTIN: {order.address.gst_number}</div>}
              <div className="text-muted-foreground pt-2">
                {order.address.address_line1}<br />
                {order.address.address_line2 && <>{order.address.address_line2}<br /></>}
                {order.address.city}, {order.address.state} - {order.address.pincode}<br />
                {order.address.landmark && <span className="text-xs">Landmark: {order.address.landmark}</span>}
              </div>
            </div>
          </div>
          <div className="bg-card border border-border rounded-2xl p-4 text-sm">
            <div className="font-display font-semibold mb-2">Payment</div>
            <div className="uppercase">{order.payment_method?.replace('_', ' ')}</div>
            <div className="text-xs text-muted-foreground mt-0.5">Status: {order.payment_status || 'pending'}</div>
          </div>
          {order.notes && <div className="bg-card border border-border rounded-2xl p-4 text-sm"><div className="font-display font-semibold mb-1">Notes</div>{order.notes}</div>}
        </div>
      </div>
    </div>
  );
}
