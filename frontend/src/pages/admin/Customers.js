import React, { useEffect, useState } from 'react';
import { api, formatINR, downloadFile } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Download } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminCustomers() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.get('/customers').then(r => setRows(r.data)); }, []);

  const exportCsv = async () => {
    try {
      await downloadFile('/customers/export', {}, `customers-${new Date().toISOString().slice(0, 10)}.csv`);
    } catch { toast.error('Failed to export customers'); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div><h1 className="text-2xl font-display font-bold">Customers</h1><p className="text-sm text-muted-foreground">{rows.length} customers</p></div>
        <Button variant="outline" className="gap-2" onClick={exportCsv} data-testid="admin-customers-export"><Download className="h-4 w-4" />Export CSV</Button>
      </div>
      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground uppercase bg-muted/40"><tr><th className="px-4 py-2.5">Name</th><th>Mobile</th><th>Email</th><th>City</th><th>Orders</th><th>Total Spent</th><th>Last Order</th></tr></thead>
            <tbody>
              {rows.map(c => (
                <tr key={c.mobile} className="border-t border-border hover:bg-muted/30">
                  <td className="px-4 py-2.5 font-medium">{c.name}</td>
                  <td className="py-2.5">{c.mobile}</td>
                  <td className="py-2.5 text-xs text-muted-foreground">{c.email}</td>
                  <td className="py-2.5">{c.city}</td>
                  <td className="py-2.5">{c.orders}</td>
                  <td className="py-2.5 font-medium">{formatINR(c.spent)}</td>
                  <td className="py-2.5 text-xs text-muted-foreground">{c.last_order?.slice(0, 10)}</td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-sm text-muted-foreground">No customers yet</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
