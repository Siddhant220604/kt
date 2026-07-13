import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, formatINR, downloadFile } from '../../lib/api';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Skeleton } from '../../components/ui/skeleton';
import { Search, Download } from 'lucide-react';
import { toast } from 'sonner';

const statusColor = { pending: 'bg-amber-500/10 text-amber-700 border-amber-500/20', confirmed: 'bg-sky-500/10 text-sky-700 border-sky-500/20', processing: 'bg-cyan-500/10 text-cyan-700 border-cyan-500/20', packed: 'bg-indigo-500/10 text-indigo-700 border-indigo-500/20', 'out for delivery': 'bg-purple-500/10 text-purple-700 border-purple-500/20', delivered: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20', cancelled: 'bg-red-500/10 text-red-700 border-red-500/20' };

export default function AdminOrders() {
  const [sp, setSp] = useSearchParams();
  const status = sp.get('status') || 'all';
  const search = sp.get('search') || '';
  const [q, setQ] = useState(search);
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = {};
    if (status && status !== 'all') params.status = status;
    if (search) params.search = search;
    api.get('/orders', { params }).then(r => setData(r.data)).finally(() => setLoading(false));
  }, [status, search]);

  const setStatus = (v) => { const n = new URLSearchParams(sp); if (v === 'all') n.delete('status'); else n.set('status', v); setSp(n); };
  const setSearch = (v) => { const n = new URLSearchParams(sp); if (!v) n.delete('search'); else n.set('search', v); setSp(n); };

  const exportCsv = async () => {
    try {
      const params = {};
      if (status && status !== 'all') params.status = status;
      if (search) params.search = search;
      await downloadFile('/orders/export', params, `orders-${new Date().toISOString().slice(0, 10)}.csv`);
    } catch { toast.error('Failed to export orders'); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold">Orders</h1>
          <p className="text-sm text-muted-foreground">{data.total} orders</p>
        </div>
        <div className="flex items-center gap-2">
          <form onSubmit={(e) => { e.preventDefault(); setSearch(q); }} className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search order id / mobile / name" className="pl-9 w-72" data-testid="admin-orders-search" />
          </form>
          <Button variant="outline" className="gap-2" onClick={exportCsv} data-testid="admin-orders-export"><Download className="h-4 w-4" />Export CSV</Button>
        </div>
      </div>
      <Tabs value={status} onValueChange={setStatus} data-testid="admin-orders-status-tabs">
        <TabsList className="flex-wrap h-auto">
          {['all', 'pending', 'confirmed', 'packed', 'out for delivery', 'delivered', 'cancelled'].map(s => (
            <TabsTrigger key={s} value={s} className="capitalize">{s}</TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="admin-orders-table">
            <thead className="text-left text-xs text-muted-foreground uppercase bg-muted/40"><tr>
              <th className="px-4 py-2.5">Order</th><th>Customer</th><th>Items</th><th>Total</th><th>Payment</th><th>Status</th><th>Date</th>
            </tr></thead>
            <tbody>
              {loading ? Array.from({ length: 5 }).map((_, i) => <tr key={i} className="border-t border-border"><td colSpan={7} className="px-4 py-3"><Skeleton className="h-6 w-full" /></td></tr>) :
                data.items.length === 0 ? <tr><td colSpan={7} className="text-center py-8 text-muted-foreground text-sm">No orders</td></tr> :
                data.items.map(o => (
                  <tr key={o.id} className="border-t border-border hover:bg-muted/30">
                    <td className="px-4 py-2.5"><Link to={`/admin/orders/${o.id}`} className="font-mono text-xs hover:text-primary">{o.id}</Link></td>
                    <td className="py-2.5"><div className="font-medium">{o.address?.name}</div><div className="text-xs text-muted-foreground">{o.address?.mobile}</div></td>
                    <td className="py-2.5">{o.items?.length} items</td>
                    <td className="py-2.5 font-medium">{formatINR(o.total)}</td>
                    <td className="py-2.5 uppercase text-xs">{o.payment_method}</td>
                    <td className="py-2.5">
                      <Badge variant="outline" className={statusColor[o.status] || ''}>{o.status}</Badge>
                      {o.refund_status === 'pending' && <Badge variant="outline" className="ml-1 bg-red-500/10 text-red-700 border-red-500/20">Refund pending</Badge>}
                    </td>
                    <td className="py-2.5 text-xs text-muted-foreground">{o.created_at?.slice(0, 10)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
