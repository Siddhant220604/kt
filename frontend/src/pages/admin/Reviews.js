import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Star, Trash2, Check } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminReviews() {
  const [rows, setRows] = useState([]);
  const [filter, setFilter] = useState('pending');
  const load = useCallback(() => api.get('/reviews', { params: { approved: filter === 'pending' ? false : true } }).then(r => setRows(r.data)), [filter]);
  useEffect(() => { load(); }, [load]);

  const approve = async (id) => { await api.put(`/reviews/${id}/approve`); toast.success('Approved'); load(); };
  const del = async (id) => { if (!window.confirm('Delete review?')) return; await api.delete(`/reviews/${id}`); load(); };

  return (
    <div className="space-y-4">
      <div><h1 className="text-2xl font-display font-bold">Reviews</h1><p className="text-sm text-muted-foreground">Moderate customer reviews</p></div>
      <Tabs value={filter} onValueChange={setFilter}>
        <TabsList><TabsTrigger value="pending">Pending</TabsTrigger><TabsTrigger value="approved">Approved</TabsTrigger></TabsList>
      </Tabs>
      <div className="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
        {rows.map(r => (
          <div key={r.id} className="bg-card border border-border rounded-2xl p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1 mb-1">{Array.from({ length: r.rating }).map((_, i) => <Star key={i} className="h-4 w-4 fill-[hsl(var(--brand-marigold))] text-[hsl(var(--brand-marigold))]" />)}</div>
                {r.title && <div className="font-semibold">{r.title}</div>}
                <p className="text-sm">{r.comment}</p>
                <div className="text-xs text-muted-foreground mt-1">By {r.name} • Product: {r.product_id}</div>
              </div>
              <div className="flex gap-1">
                {filter === 'pending' && <Button size="sm" onClick={() => approve(r.id)} className="gap-1"><Check className="h-3 w-3" />Approve</Button>}
                <Button size="sm" variant="outline" onClick={() => del(r.id)} className="text-destructive"><Trash2 className="h-3.5 w-3.5" /></Button>
              </div>
            </div>
          </div>
        ))}
        {rows.length === 0 && <div className="text-sm text-muted-foreground text-center py-8">No reviews</div>}
      </div>
    </div>
  );
}
