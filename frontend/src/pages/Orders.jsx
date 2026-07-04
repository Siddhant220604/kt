import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { money } from "../lib/product";
import { Badge } from "../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Package } from "@phosphor-icons/react";

const STATUS_COLORS = {
  pending: "bg-muted text-foreground",
  confirmed: "bg-blue-100 text-blue-900",
  shipped: "bg-amber-100 text-amber-900",
  delivered: "bg-emerald-100 text-emerald-900",
  cancelled: "bg-destructive/10 text-destructive",
};

export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/orders").then((r) => setOrders(r.data || [])).finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="label-caps mb-2">Account</div>
      <h1 className="text-3xl font-black tracking-tighter">My orders</h1>

      <div className="mt-8 border border-border bg-card">
        {loading ? (
          <div className="p-8 text-center text-sm text-muted-foreground">Loading orders…</div>
        ) : orders.length === 0 ? (
          <div className="p-12 text-center">
            <Package size={40} weight="duotone" className="mx-auto text-muted-foreground" />
            <p className="mt-4 text-sm text-muted-foreground">No orders yet.</p>
            <Link to="/catalog" className="mt-3 inline-block text-sm font-medium text-primary hover:underline">Browse catalog →</Link>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Order #</TableHead>
                <TableHead>Placed</TableHead>
                <TableHead>Items</TableHead>
                <TableHead>Total</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">View</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {orders.map((o) => (
                <TableRow key={o.id} data-testid={`order-row-${o.order_number}`}>
                  <TableCell className="font-mono text-sm">{o.order_number}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{new Date(o.created_at).toLocaleDateString()}</TableCell>
                  <TableCell className="text-sm">{o.items.length}</TableCell>
                  <TableCell className="font-mono font-semibold">{money(o.total)}</TableCell>
                  <TableCell>
                    <Badge className={`rounded-sm ${STATUS_COLORS[o.status] || ""}`}>{o.status}</Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Link
                      to={`/orders/${o.id}`}
                      className="text-sm font-medium text-primary hover:underline"
                      data-testid={`order-view-${o.order_number}`}
                    >
                      Details →
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
