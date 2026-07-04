import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { money } from "../../lib/product";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/table";
import { Badge } from "../../components/ui/badge";
import { Package, ListChecks, Users, CurrencyDollar, TrendUp } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

const KPI_ICONS = { revenue: CurrencyDollar, orders: ListChecks, products: Package, users: Users };

export default function AdminDashboard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/admin/analytics").then((r) => setData(r.data));
  }, []);

  if (!data) return <div className="p-8 text-sm text-muted-foreground">Loading analytics…</div>;

  const kpis = [
    { key: "revenue", label: "Total Revenue", value: money(data.total_revenue) },
    { key: "orders", label: "Total Orders", value: data.total_orders, sub: `${data.pending_orders} pending` },
    { key: "products", label: "Active Products", value: data.total_products },
    { key: "users", label: "Buyer Accounts", value: data.total_users },
  ];

  return (
    <div>
      <div className="label-caps mb-2">Dashboard</div>
      <h1 className="text-3xl font-black tracking-tighter" data-testid="admin-dashboard-title">Overview</h1>
      <p className="mt-1 text-sm text-muted-foreground">Live snapshot of your wholesale operation.</p>

      <div className="mt-8 grid grid-cols-2 gap-0 border-l border-t border-border md:grid-cols-4">
        {kpis.map((k) => {
          const Icon = KPI_ICONS[k.key];
          return (
            <div key={k.key} className="border-b border-r border-border bg-card p-5" data-testid={`admin-kpi-${k.key}`}>
              <div className="flex items-center justify-between">
                <span className="label-caps">{k.label}</span>
                <Icon size={16} className="text-primary" />
              </div>
              <div className="mt-3 font-mono text-2xl font-bold">{k.value}</div>
              {k.sub && <div className="mt-1 text-xs text-muted-foreground">{k.sub}</div>}
            </div>
          );
        })}
      </div>

      <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-2">
        <section className="border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border p-4">
            <div>
              <div className="label-caps">Top Products</div>
              <div className="text-sm text-muted-foreground">Units sold, all time</div>
            </div>
            <TrendUp size={18} className="text-primary" />
          </div>
          {data.top_products.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">No sales yet.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead className="text-right">Units</TableHead>
                  <TableHead className="text-right">Revenue</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.top_products.map((p) => (
                  <TableRow key={p._id}>
                    <TableCell className="text-sm">{p.name}</TableCell>
                    <TableCell className="text-right font-mono">{p.units}</TableCell>
                    <TableCell className="text-right font-mono">{money(p.revenue)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </section>

        <section className="border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border p-4">
            <div>
              <div className="label-caps">Recent Orders</div>
              <div className="text-sm text-muted-foreground">Latest 5</div>
            </div>
            <Link to="/admin/orders" className="text-xs font-medium text-primary hover:underline">
              View all →
            </Link>
          </div>
          {data.recent_orders.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">No orders yet.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Order</TableHead>
                  <TableHead>Buyer</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.recent_orders.map((o) => (
                  <TableRow key={o.id}>
                    <TableCell className="font-mono text-xs">
                      <Link to={`/orders/${o.id}`} className="hover:text-primary">{o.order_number}</Link>
                    </TableCell>
                    <TableCell className="text-sm">{o.user_email}</TableCell>
                    <TableCell className="font-mono">{money(o.total)}</TableCell>
                    <TableCell><Badge variant="outline" className="rounded-sm">{o.status}</Badge></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </section>
      </div>
    </div>
  );
}
