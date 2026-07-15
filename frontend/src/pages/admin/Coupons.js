import React, { useEffect, useState } from 'react';
import { api, formatINR, errorMessage } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from '../../components/ui/dialog';
import { Badge } from '../../components/ui/badge';
import { Plus, Edit, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

const empty = { code: '', type: 'percent', value: 10, min_order: 0, max_discount: 0, starts_at: '', expiry: '', active: true, usage_limit: 0 };

export default function AdminCoupons() {
  const [rows, setRows] = useState([]);
  const [edit, setEdit] = useState(null);
  const load = () => api.get('/coupons').then(r => setRows(r.data));
  useEffect(() => { load(); }, []);

  const save = async () => {
    try {
      // Whitelisted to what CouponIn accepts (extra='forbid') - the coupon list response also
      // carries read-only fields (id, created_at, used_count) that aren't part of the model,
      // and sending them along caused every edit (never a new coupon) to fail.
      const payload = {
        code: edit.code, type: edit.type, value: Number(edit.value),
        min_order: Number(edit.min_order || 0), max_discount: Number(edit.max_discount || 0),
        starts_at: edit.starts_at || '', expiry: edit.expiry || '',
        active: edit.active, usage_limit: Number(edit.usage_limit || 0),
      };
      if (edit.id) await api.put(`/coupons/${edit.id}`, payload); else await api.post('/coupons', payload);
      toast.success('Saved'); setEdit(null); load();
    } catch (e) { toast.error(errorMessage(e, 'Failed')); }
  };

  const del = async (c) => { if (!window.confirm('Delete coupon?')) return; await api.delete(`/coupons/${c.id}`); toast.success('Deleted'); load(); };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-display font-bold">Coupons</h1><p className="text-sm text-muted-foreground">{rows.length} coupons</p></div>
        <Button onClick={() => setEdit(empty)} className="gap-1" data-testid="admin-new-coupon"><Plus className="h-4 w-4" />New Coupon</Button>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {rows.map(c => (
          <div key={c.id} className="bg-card border border-border rounded-2xl p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="font-mono font-bold text-lg">{c.code}</div>
                <div className="text-sm text-muted-foreground">{c.type === 'percent' ? `${c.value}% off` : `${formatINR(c.value)} off`}</div>
                <div className="text-xs text-muted-foreground">Min order: {formatINR(c.min_order)} • Used: {c.used_count}</div>
                {(c.starts_at || c.expiry) && (
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {c.starts_at && `From ${new Date(c.starts_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })}`}
                    {c.starts_at && c.expiry && ' '}
                    {c.expiry && `Until ${new Date(c.expiry).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })}`}
                  </div>
                )}
              </div>
              <div className="flex gap-1">
                <Button size="icon" variant="ghost" onClick={() => setEdit(c)}><Edit className="h-4 w-4" /></Button>
                <Button size="icon" variant="ghost" onClick={() => del(c)} className="text-destructive"><Trash2 className="h-4 w-4" /></Button>
              </div>
            </div>
            <div className="mt-2">{c.active ? <Badge variant="outline" className="bg-emerald-500/10 text-emerald-700 border-emerald-500/20">Active</Badge> : <Badge variant="secondary">Inactive</Badge>}</div>
          </div>
        ))}
      </div>
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>{edit?.id ? 'Edit Coupon' : 'New Coupon'}</DialogTitle></DialogHeader>
          {edit && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="text-xs text-muted-foreground">Code *</Label><Input value={edit.code} onChange={(e) => setEdit({ ...edit, code: e.target.value.toUpperCase() })} placeholder="WELCOME10" /></div>
                <div><Label className="text-xs text-muted-foreground">Type</Label><Select value={edit.type} onValueChange={(v) => setEdit({ ...edit, type: v })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="percent">Percent</SelectItem><SelectItem value="flat">Flat</SelectItem></SelectContent></Select></div>
                <div><Label className="text-xs text-muted-foreground">Value</Label><Input type="number" value={edit.value} onChange={(e) => setEdit({ ...edit, value: e.target.value })} /></div>
                <div><Label className="text-xs text-muted-foreground">Min Order</Label><Input type="number" value={edit.min_order} onChange={(e) => setEdit({ ...edit, min_order: e.target.value })} /></div>
                <div><Label className="text-xs text-muted-foreground">Max Discount (0 = none)</Label><Input type="number" value={edit.max_discount} onChange={(e) => setEdit({ ...edit, max_discount: e.target.value })} /></div>
                <div><Label className="text-xs text-muted-foreground">Usage Limit (0 = unlimited)</Label><Input type="number" value={edit.usage_limit} onChange={(e) => setEdit({ ...edit, usage_limit: e.target.value })} /></div>
                <div><Label className="text-xs text-muted-foreground">Starts At (optional)</Label><Input type="datetime-local" value={edit.starts_at} onChange={(e) => setEdit({ ...edit, starts_at: e.target.value })} /></div>
                <div><Label className="text-xs text-muted-foreground">Expires At (optional)</Label><Input type="datetime-local" value={edit.expiry} onChange={(e) => setEdit({ ...edit, expiry: e.target.value })} /></div>
              </div>
              <p className="text-xs text-muted-foreground">Leave Starts/Expires blank for a coupon that's always live while Active is checked. Set both to auto-activate and auto-expire on schedule, without needing to flip Active manually.</p>
              <label className="flex items-center gap-2"><input type="checkbox" checked={edit.active} onChange={(e) => setEdit({ ...edit, active: e.target.checked })} /> Active</label>
            </div>
          )}
          <DialogFooter><DialogClose asChild><Button variant="outline">Cancel</Button></DialogClose><Button onClick={save}>Save</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
