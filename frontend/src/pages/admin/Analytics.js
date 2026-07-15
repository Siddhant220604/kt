import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, formatINR } from '../../lib/api';
import { Skeleton } from '../../components/ui/skeleton';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { IndianRupee, ShoppingBag, TrendingUp, Repeat, AlertTriangle } from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

const reorderUrgency = (days) => days <= 7
  ? 'bg-red-500/10 text-red-700 border-red-500/20'
  : days <= 14
    ? 'bg-amber-500/10 text-amber-700 border-amber-500/20'
    : 'bg-muted text-muted-foreground border-border';

export default function AdminAnalytics() {
  const [days, setDays] = useState('30');
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get('/admin/analytics', { params: { days } }).then(r => setStats(r.data)).finally(() => setLoading(false));
  }, [days]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold">Analytics</h1>
          <p className="text-sm text-muted-foreground">Revenue trends, top products, and repeat-customer rate.</p>
        </div>
        <Tabs value={days} onValueChange={setDays} data-testid="admin-analytics-range">
          <TabsList>
            <TabsTrigger value="7">7 days</TabsTrigger>
            <TabsTrigger value="30">30 days</TabsTrigger>
            <TabsTrigger value="90">90 days</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {loading || !stats ? (
        <div className="grid md:grid-cols-4 gap-3">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}</div>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              { label: 'Revenue', value: formatINR(stats.total_revenue_range), icon: IndianRupee, tint: 'text-[hsl(var(--brand-terracotta))]' },
              { label: 'Orders', value: stats.total_orders_range, icon: ShoppingBag, tint: 'text-[hsl(var(--brand-teal))]' },
              { label: 'Avg Order Value', value: formatINR(stats.avg_order_value), icon: TrendingUp, tint: 'text-[hsl(var(--brand-marigold))]' },
              { label: 'Repeat Customer Rate', value: `${stats.repeat_rate}%`, icon: Repeat, tint: 'text-foreground' },
            ].map(({ label, value, icon: Icon, tint }) => (
              <div key={label} className="bg-card border border-border rounded-2xl p-4">
                <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-wide"><Icon className={`h-3.5 w-3.5 ${tint}`} />{label}</div>
                <div className="font-display font-bold text-2xl mt-1">{value}</div>
              </div>
            ))}
          </div>

          <div className="grid lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 bg-card border border-border rounded-2xl p-4">
              <div className="font-display font-semibold mb-2">Revenue trend ({stats.days} days)</div>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={stats.revenue_trend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" minTickGap={20} />
                    <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                    <Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 12 }} formatter={(v, name) => name === 'revenue' ? formatINR(v) : v} />
                    <Line type="monotone" dataKey="revenue" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-card border border-border rounded-2xl p-4">
              <div className="font-display font-semibold mb-3">Customers ({stats.days} days)</div>
              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between"><span className="text-muted-foreground">Total customers</span><span className="font-semibold">{stats.total_customers_range}</span></div>
                <div className="flex items-center justify-between"><span className="text-muted-foreground">Repeat customers</span><span className="font-semibold">{stats.repeat_customers}</span></div>
                <div className="flex items-center justify-between"><span className="text-muted-foreground">One-time customers</span><span className="font-semibold">{stats.one_time_customers}</span></div>
                <div className="pt-2 border-t border-border">
                  <div className="h-2.5 rounded-full bg-muted overflow-hidden flex">
                    <div className="h-full bg-primary" style={{ width: `${stats.repeat_rate}%` }} title="Repeat" />
                  </div>
                  <div className="text-xs text-muted-foreground mt-1.5">{stats.repeat_rate}% of customers in this window have placed more than one order</div>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-card border border-border rounded-2xl overflow-hidden">
            <div className="font-display font-semibold p-4 pb-0">Top products ({stats.days} days)</div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm mt-2">
                <thead className="text-left text-xs text-muted-foreground uppercase bg-muted/40"><tr><th className="px-4 py-2.5">Product</th><th>Qty Sold</th><th>Revenue</th></tr></thead>
                <tbody>
                  {stats.top_products.length === 0 ? (
                    <tr><td colSpan={3} className="text-center py-8 text-muted-foreground text-sm">No sales in this window</td></tr>
                  ) : stats.top_products.map(p => (
                    <tr key={p.product_id} className="border-t border-border">
                      <td className="px-4 py-2.5 font-medium">{p.name}</td>
                      <td className="py-2.5">{p.qty}</td>
                      <td className="py-2.5">{formatINR(p.revenue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-card border border-border rounded-2xl overflow-hidden">
            <div className="flex items-center gap-2 font-display font-semibold p-4 pb-0"><AlertTriangle className="h-4 w-4 text-amber-600" />Reorder Suggestions</div>
            <p className="text-xs text-muted-foreground px-4 pt-1">Estimated from sales velocity over the last {stats.days} days, not just a flat low-stock threshold.</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm mt-2">
                <thead className="text-left text-xs text-muted-foreground uppercase bg-muted/40"><tr><th className="px-4 py-2.5">Product</th><th>Stock</th><th>Sold / Day</th><th>Est. Days Left</th></tr></thead>
                <tbody>
                  {stats.reorder_suggestions.length === 0 ? (
                    <tr><td colSpan={4} className="text-center py-8 text-muted-foreground text-sm">Nothing projected to run out within 30 days</td></tr>
                  ) : stats.reorder_suggestions.map(p => (
                    <tr key={p.product_id} className="border-t border-border">
                      <td className="px-4 py-2.5 font-medium"><Link to={`/admin/products?edit=${p.product_id}`} className="hover:text-primary">{p.name}</Link></td>
                      <td className="py-2.5">{p.stock}</td>
                      <td className="py-2.5">{p.daily_velocity}</td>
                      <td className="py-2.5"><Badge variant="outline" className={reorderUrgency(p.days_left)}>{p.days_left} days</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
