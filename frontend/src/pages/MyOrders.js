import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { LogOut, Package, ShoppingBag } from 'lucide-react';
import { toast } from 'sonner';
import { api, formatINR, logoutCustomer } from '../lib/api';

const statusColor = { pending: 'bg-amber-500/10 text-amber-700 border-amber-500/20', confirmed: 'bg-sky-500/10 text-sky-700 border-sky-500/20', processing: 'bg-cyan-500/10 text-cyan-700 border-cyan-500/20', packed: 'bg-indigo-500/10 text-indigo-700 border-indigo-500/20', 'out for delivery': 'bg-purple-500/10 text-purple-700 border-purple-500/20', delivered: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20', cancelled: 'bg-red-500/10 text-red-700 border-red-500/20' };

function LoginForm({ onLoggedIn }) {
  const [step, setStep] = useState('mobile'); // mobile | otp
  const [mobile, setMobile] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);

  const requestOtp = async (e) => {
    e.preventDefault();
    if (!/^[6-9]\d{9}$/.test(mobile)) return toast.error('Enter a valid 10-digit mobile number');
    setLoading(true);
    try {
      await api.post('/customer/auth/request-otp', { mobile });
      toast.success('If this number has orders with us, a login code has been sent on WhatsApp.');
      setStep('otp');
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to send code'); }
    finally { setLoading(false); }
  };

  const verifyOtp = async (e) => {
    e.preventDefault();
    if (!otp.trim()) return toast.error('Enter the code sent to your WhatsApp');
    setLoading(true);
    try {
      const { data } = await api.post('/customer/auth/verify-otp', { mobile, otp: otp.trim() });
      localStorage.setItem('kt_customer_token', data.token);
      localStorage.setItem('kt_customer_mobile', data.mobile);
      onLoggedIn();
    } catch (e) { toast.error(e.response?.data?.detail || 'Invalid code'); }
    finally { setLoading(false); }
  };

  return (
    <div className="max-w-md mx-auto bg-card border border-border rounded-2xl p-6">
      <div className="h-12 w-12 rounded-full bg-primary/10 grid place-items-center mx-auto"><ShoppingBag className="h-6 w-6 text-primary" /></div>
      <h2 className="text-xl font-display font-bold text-center mt-3">My Orders</h2>
      <p className="text-sm text-muted-foreground text-center mt-1">Log in with your mobile number to see all your past orders.</p>
      {step === 'mobile' ? (
        <form onSubmit={requestOtp} className="mt-5 space-y-3">
          <div><Label className="text-xs text-muted-foreground">Mobile Number</Label><Input inputMode="numeric" maxLength={10} value={mobile} onChange={(e) => setMobile(e.target.value.replace(/[^0-9]/g, ''))} data-testid="myorders-mobile-input" /></div>
          <Button type="submit" className="w-full" disabled={loading} data-testid="myorders-request-otp">{loading ? 'Sending...' : 'Send Login Code'}</Button>
        </form>
      ) : (
        <form onSubmit={verifyOtp} className="mt-5 space-y-3">
          <div><Label className="text-xs text-muted-foreground">Enter the 6-digit code sent to WhatsApp</Label><Input inputMode="numeric" maxLength={6} value={otp} onChange={(e) => setOtp(e.target.value.replace(/[^0-9]/g, ''))} data-testid="myorders-otp-input" /></div>
          <Button type="submit" className="w-full" disabled={loading} data-testid="myorders-verify-otp">{loading ? 'Verifying...' : 'Verify & Continue'}</Button>
          <button type="button" onClick={() => setStep('mobile')} className="text-xs text-muted-foreground hover:underline w-full text-center">Change mobile number</button>
        </form>
      )}
    </div>
  );
}

export default function MyOrders() {
  const [loggedIn, setLoggedIn] = useState(!!localStorage.getItem('kt_customer_token'));
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/customer/orders');
      setOrders(data);
    } catch (e) {
      if (e.response?.status === 401 || e.response?.status === 403) {
        logoutCustomer();
        setLoggedIn(false);
      }
    } finally { setLoading(false); }
  };

  useEffect(() => { if (loggedIn) load(); }, [loggedIn]);

  const logout = () => { logoutCustomer(); setLoggedIn(false); setOrders([]); };

  return (
    <Section>
      <Container className="max-w-3xl">
        {!loggedIn ? (
          <LoginForm onLoggedIn={() => setLoggedIn(true)} />
        ) : (
          <>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-3xl font-display font-bold">My Orders</h1>
                <p className="text-sm text-muted-foreground">{localStorage.getItem('kt_customer_mobile')}</p>
              </div>
              <Button variant="outline" size="sm" className="gap-2" onClick={logout} data-testid="myorders-logout"><LogOut className="h-4 w-4" />Log out</Button>
            </div>
            {loading ? (
              <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}</div>
            ) : orders.length === 0 ? (
              <div className="text-center py-14">
                <Package className="h-14 w-14 mx-auto text-muted-foreground/50" />
                <p className="text-muted-foreground mt-3">No orders found for this number yet.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {orders.map(o => (
                  <Link key={o.id} to={`/track/${o.id}`} state={{ mobile: o.address?.mobile }} className="block bg-card border border-border rounded-2xl p-4 hover:border-primary/40 transition-colors" data-testid={`myorders-order-${o.id}`}>
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <div>
                        <div className="font-mono text-xs text-muted-foreground">{o.id}</div>
                        <div className="text-sm text-muted-foreground mt-0.5">{o.items?.length} item(s) · {o.created_at?.slice(0, 10)}</div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="font-display font-bold">{formatINR(o.total)}</div>
                        <Badge variant="outline" className={statusColor[o.status] || ''}>{o.status}</Badge>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </>
        )}
      </Container>
    </Section>
  );
}
