import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../../lib/api';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';

export default function AdminAuditLog() {
  const [sp, setSp] = useSearchParams();
  const action = sp.get('action') || 'all';
  const page = Number(sp.get('page') || 1);
  const [data, setData] = useState({ items: [], total: 0, actions: [] });
  const [loading, setLoading] = useState(true);
  const limit = 50;

  useEffect(() => {
    setLoading(true);
    const params = { page, limit };
    if (action && action !== 'all') params.action = action;
    api.get('/admin/audit-logs', { params }).then(r => setData(r.data)).finally(() => setLoading(false));
  }, [action, page]);

  const setAction = (v) => { const n = new URLSearchParams(sp); if (v === 'all') n.delete('action'); else n.set('action', v); n.delete('page'); setSp(n); };
  const setPage = (p) => { const n = new URLSearchParams(sp); n.set('page', p); setSp(n); };

  const totalPages = Math.max(1, Math.ceil(data.total / limit));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold">Audit Log</h1>
          <p className="text-sm text-muted-foreground">{data.total} recorded admin actions</p>
        </div>
        <Select value={action} onValueChange={setAction}>
          <SelectTrigger className="w-56" data-testid="audit-log-action-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All actions</SelectItem>
            {data.actions.map(a => <SelectItem key={a} value={a}>{a.replace(/_/g, ' ')}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        <div className="overflow-x-auto max-h-[70vh] overflow-y-auto">
          <table className="w-full text-sm" data-testid="audit-log-table">
            <thead className="text-left text-xs text-muted-foreground uppercase bg-muted/40 sticky top-0 z-10"><tr>
              <th className="px-4 py-2.5">When</th><th>Admin</th><th>Action</th><th>Record</th><th>IP</th><th>Details</th>
            </tr></thead>
            <tbody>
              {loading ? Array.from({ length: 8 }).map((_, i) => <tr key={i} className="border-t border-border"><td colSpan={6} className="px-4 py-3"><Skeleton className="h-6 w-full" /></td></tr>) :
                data.items.length === 0 ? <tr><td colSpan={6} className="text-center py-8 text-muted-foreground text-sm">No audit entries</td></tr> :
                data.items.map(a => (
                  <tr key={a.id} className="border-t border-border hover:bg-muted/30 align-top">
                    <td className="px-4 py-2.5 text-xs text-muted-foreground whitespace-nowrap">{a.timestamp?.replace('T', ' ').slice(0, 19)}</td>
                    <td className="py-2.5">{a.admin_email}</td>
                    <td className="py-2.5"><Badge variant="outline">{a.action?.replace(/_/g, ' ')}</Badge></td>
                    <td className="py-2.5 font-mono text-xs">{a.document_id}</td>
                    <td className="py-2.5 text-xs text-muted-foreground">{a.ip_address}</td>
                    <td className="py-2.5 text-xs text-muted-foreground max-w-xs truncate" title={JSON.stringify(a.details)}>
                      {a.details && Object.keys(a.details).length > 0 ? JSON.stringify(a.details) : '-'}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border text-sm">
            <span className="text-muted-foreground">Page {page} of {totalPages}</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
              <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
