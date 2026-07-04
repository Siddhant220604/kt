import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError } from "../../lib/api";
import { money } from "../../lib/product";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/table";
import { Badge } from "../../components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../../components/ui/select";
import { Button } from "../../components/ui/button";
import { toast } from "sonner";

const STATUSES = ["pending", "confirmed", "shipped", "delivered", "cancelled"];

export default function AdminOrders() {
  const [orders, setOrders] = useState([]);
  const [filter, setFilter] = useState("all");

  const load = () => {
    const q = filter === "all" ? "" : `?status=${filter}`;
    api.get(`/admin/orders${q}`).then((r) => setOrders(r.data || []));
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter]);

  const updateStatus = async (id, status) => {
    try {
      await api.put(`/admin/orders/${id}/status`, { status });
      toast.success(`Order updated: ${status}`);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="label-caps mb-1">Fulfillment</div>
          <h1 className="text-3xl font-black tracking-tighter">Orders</h1>
        </div>
        <div className="flex items-center gap-2">
          <span className="label-caps">Filter</span>
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-40 rounded-sm" data-testid="admin-order-filter">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {STATUSES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Order #</TableHead>
              <TableHead>Buyer</TableHead>
              <TableHead>Items</TableHead>
              <TableHead>Total</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Update</TableHead>
              <TableHead className="text-right">View</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {orders.length === 0 ? (
              <TableRow><TableCell colSpan={7} className="text-center text-sm text-muted-foreground py-8">No orders.</TableCell></TableRow>
            ) : orders.map((o) => (
              <TableRow key={o.id} data-testid={`admin-order-${o.order_number}`}>
                <TableCell className="font-mono text-xs">{o.order_number}</TableCell>
                <TableCell className="text-sm">{o.user_email}</TableCell>
                <TableCell className="font-mono">{o.items.length}</TableCell>
                <TableCell className="font-mono font-semibold">{money(o.total)}</TableCell>
                <TableCell><Badge variant="outline" className="rounded-sm">{o.status}</Badge></TableCell>
                <TableCell>
                  <Select value={o.status} onValueChange={(v) => updateStatus(o.id, v)}>
                    <SelectTrigger className="w-32 rounded-sm h-8" data-testid={`admin-order-status-${o.order_number}`}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUSES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell className="text-right">
                  <Button asChild size="sm" variant="outline" className="rounded-sm">
                    <Link to={`/orders/${o.id}`}>Open</Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
