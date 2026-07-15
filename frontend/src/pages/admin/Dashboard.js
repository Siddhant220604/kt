import React, { useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { api, formatINR, isAdminOwner } from '../../lib/api';
import { Skeleton } from '../../components/ui/skeleton';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { ShoppingBag, IndianRupee, Users, Package, TrendingUp, AlertTriangle } from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar } from 'recharts';

const statusColor = { pending: 'bg-amber-500/10 text-amber-700 border-amber-500/20', confirmed: 'bg-sky-500/10 text-sky-700 border-sky-500/20', processing: 'bg-cyan-500/10 text-cyan-700 border-cyan-500/20', packed: 'bg-indigo-500/10 text-indigo-700 border-indigo-500/20', 'out for delivery': 'bg-purple-500/10 text-purple-700 border-purple-500/20', delivered: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20', cancelled: 'bg-red-500/10 text-red-700 border-red-500/20' };

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  useEffect(() => { if (isAdminOwner()) api.get('/admin/stats').then(r => setStats(r.data)); }, []);

  // Staff accounts don't have access to /admin/stats (revenue/financial overview) - send them
  // straight to the page they actually use.
  if (!isAdminOwner()) return <Navigate to="/admin/orders" replace />;

  if (!stats) return <div className="grid md:grid-cols-4 gap-3">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}</div>;

  const kpis = [
    { label: 'Revenue', value: formatINR(stats.total_revenue), icon: IndianRupee, tint: 'text-[hsl(var(--brand-terracotta))]' },
    { label: 'Orders', value: stats.total_orders, icon: ShoppingBag, tint: 'text-[hsl(var(--brand-teal))]' },
    { label: 'Customers', value: stats.total_customers, icon: Users, tint: 'text-[hsl(var(--brand-marigold))]' },
    { label: 'Products', value: stats.total_products, icon: Package, tint: 'text-foreground' },
  ];

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-display font-bold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">Overview of your store performance.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button asChild variant="outline" size="sm">
            <Link to="/admin/profile">Profile</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link to="/admin/settings">Settings</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link to="/admin/orders">Orders</Link>
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {kpis.map(({ label, value, icon: Icon, tint }) => (
          <div key={label} className="bg-card border border-border rounded-2xl p-4">
            <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-wide"><Icon className={`h-3.5 w-3.5 ${tint}`} />{label}</div>
            <div className="font-display font-bold text-2xl mt-1">{value}</div>
          </div>
        ))}
      </div>
      <div className="grid lg:grid-cols-3 gap-4">
        {[
          { label: 'Pending', val: stats.pending_orders, color: 'bg-amber-500/10 text-amber-700 border-amber-500/20' },
          { label: 'Confirmed', val: stats.confirmed_orders, color: 'bg-sky-500/10 text-sky-700 border-sky-500/20' },
          { label: 'Out for Delivery', val: stats.out_for_delivery_orders, color: 'bg-purple-500/10 text-purple-700 border-purple-500/20' },
          { label: 'Delivered', val: stats.delivered_orders, color: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20' },
          { label: 'Low Stock', val: stats.low_stock, color: 'bg-red-500/10 text-red-700 border-red-500/20' },
        ].map(k => (
          <div key={k.label} className="bg-card border border-border rounded-xl p-3 flex items-center justify-between">
            <div className="text-sm">{k.label}</div>
            <Badge variant="outline" className={k.color}>{k.val}</Badge>
          </div>
        ))}
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="bg-card border border-border rounded-2xl p-4">
          <div className="font-display font-semibold mb-2">Last 7 days sales</div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={stats.sales_chart}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                <Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 12 }} />
                <Line type="monotone" dataKey="sales" stroke="hsl(var(--primary))" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="bg-card border border-border rounded-2xl p-4">
          <div className="font-display font-semibold mb-2">Top products</div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.top_products} layout="vertical" margin={{ left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis type="number" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                <Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 12 }} />
                <Bar dataKey="qty" fill="hsl(var(--accent))" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      {stats.low_stock_products?.length > 0 && (
        <div className="bg-card border border-border rounded-2xl p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="font-display font-semibold flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-red-600" />Low Stock Products</div>
            <Link to="/admin/products" className="text-xs text-primary hover:underline">View all products</Link>
          </div>
          <div className="space-y-1.5">
            {stats.low_stock_products.map(p => (
              <Link key={p.id} to={`/admin/products?edit=${p.id}`} className="flex items-center justify-between text-sm p-2 rounded-lg hover:bg-muted/50 -mx-2">
                <span className="truncate">{p.name}</span>
                <Badge variant="outline" className={p.stock === 0 ? 'bg-red-500/10 text-red-700 border-red-500/20' : 'bg-amber-500/10 text-amber-700 border-amber-500/20'}>
                  {p.stock === 0 ? 'Out of stock' : `${p.stock} left`}
                </Badge>
              </Link>
            ))}
          </div>
        </div>
      )}
      <div className="bg-card border border-border rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="font-display font-semibold">Recent Orders</div>
          <Link to="/admin/orders" className="text-xs text-primary hover:underline">View all</Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground uppercase"><tr><th className="py-2">Order</th><th>Customer</th><th>Total</th><th>Status</th><th>Date</th></tr></thead>
            <tbody>
              {stats.recent_orders.map(o => (
                <tr key={o.id} className="border-t border-border">
                  <td className="py-2"><Link to={`/admin/orders/${o.id}`} className="font-mono text-xs hover:text-primary">{o.id}</Link></td>
                  <td className="py-2">{o.address?.name}</td>
                  <td className="py-2">{formatINR(o.total)}</td>
                  <td className="py-2"><Badge variant="outline" className={statusColor[o.status] || ''}>{o.status}</Badge></td>
                  <td className="py-2 text-xs text-muted-foreground">{o.created_at?.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {stats.recent_orders.length === 0 && <div className="text-center text-sm text-muted-foreground py-6">No orders yet</div>}
        </div>
      </div>
    </div>
  );
}
