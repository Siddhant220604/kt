import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { PasswordInput } from '../components/ui/password-input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { User, MapPin, Mail, LockKeyhole, LogOut, Package } from 'lucide-react';
import { toast } from 'sonner';
import { api, formatINR, logoutCustomer } from '../lib/api';
import { useWishlist } from '../lib/wishlist';

const statusColor = { pending: 'bg-amber-500/10 text-amber-700 border-amber-500/20', confirmed: 'bg-sky-500/10 text-sky-700 border-sky-500/20', processing: 'bg-cyan-500/10 text-cyan-700 border-cyan-500/20', packed: 'bg-indigo-500/10 text-indigo-700 border-indigo-500/20', 'out for delivery': 'bg-purple-500/10 text-purple-700 border-purple-500/20', delivered: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20', cancelled: 'bg-red-500/10 text-red-700 border-red-500/20' };

const emptyProfile = { name: '', email: '', mobile: '', address_line1: '', address_line2: '', city: '', state: '', pincode: '', landmark: '', gst_number: '' };

export default function Account() {
  const nav = useNavigate();
  const { resetOnLogout } = useWishlist();
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState(emptyProfile);
  const [savingProfile, setSavingProfile] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [savingEmail, setSavingEmail] = useState(false);
  const [pw, setPw] = useState({ current_password: '', new_password: '', confirm: '' });
  const [savingPw, setSavingPw] = useState(false);
  const [orders, setOrders] = useState([]);
  const [loadingOrders, setLoadingOrders] = useState(true);

  useEffect(() => {
    api.get('/customer/profile').then(({ data }) => {
      setProfile(data);
      setForm({ ...emptyProfile, ...data });
      setNewEmail(data.email || '');
    }).catch(() => toast.error('Unable to load profile'));
    api.get('/customer/orders').then(({ data }) => setOrders(data)).finally(() => setLoadingOrders(false));
  }, []);

  const upd = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const saveProfile = async (e) => {
    e.preventDefault();
    setSavingProfile(true);
    try {
      const { name, mobile, address_line1, address_line2, city, state, pincode, landmark, gst_number } = form;
      const { data } = await api.put('/customer/profile', { name, mobile, address_line1, address_line2, city, state, pincode, landmark, gst_number });
      setProfile(data);
      localStorage.setItem('kt_customer_name', data.name);
      toast.success('Profile updated');
    } catch (err) { toast.error(err.response?.data?.detail || 'Update failed'); }
    finally { setSavingProfile(false); }
  };

  const saveEmail = async (e) => {
    e.preventDefault();
    setSavingEmail(true);
    try {
      const { data } = await api.put('/customer/profile', { email: newEmail.trim().toLowerCase() });
      setProfile(data);
      setForm(f => ({ ...f, email: data.email }));
      localStorage.setItem('kt_customer_email', data.email);
      toast.success('Email updated');
    } catch (err) { toast.error(err.response?.data?.detail || 'Update failed'); }
    finally { setSavingEmail(false); }
  };

  const changePassword = async (e) => {
    e.preventDefault();
    if (pw.new_password.length < 6) return toast.error('New password must be at least 6 characters');
    if (pw.new_password !== pw.confirm) return toast.error('Passwords do not match');
    setSavingPw(true);
    try {
      const { data } = await api.post('/customer/profile/password', { current_password: pw.current_password, new_password: pw.new_password });
      if (data?.token) localStorage.setItem('kt_customer_token', data.token);
      toast.success('Password changed');
      setPw({ current_password: '', new_password: '', confirm: '' });
    } catch (err) { toast.error(err.response?.data?.detail || 'Change failed'); }
    finally { setSavingPw(false); }
  };

  const logout = () => { logoutCustomer(); resetOnLogout(); nav('/'); };

  if (!profile) return (
    <Section><Container className="max-w-4xl"><Skeleton className="h-64 rounded-2xl" /></Container></Section>
  );

  return (
    <Section>
      <Container className="max-w-4xl space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl md:text-3xl font-display font-bold">My Account</h1>
            <p className="text-sm text-muted-foreground">{profile.name} · {profile.email}</p>
          </div>
          <Button variant="outline" className="gap-2" onClick={logout} data-testid="account-logout"><LogOut className="h-4 w-4" />Log out</Button>
        </div>

        <div className="grid lg:grid-cols-[1fr_320px] gap-4">
          <div className="space-y-4">
            <form onSubmit={saveProfile} className="bg-card border border-border rounded-2xl p-5 space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold"><User className="h-4 w-4" />Profile Details</div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div><Label className="text-xs text-muted-foreground">Full Name</Label><Input required value={form.name} onChange={(e) => upd('name', e.target.value)} data-testid="account-name-input" /></div>
                <div><Label className="text-xs text-muted-foreground">Mobile Number</Label><Input required inputMode="numeric" maxLength={10} value={form.mobile} onChange={(e) => upd('mobile', e.target.value.replace(/[^0-9]/g, ''))} data-testid="account-mobile-input" /></div>
              </div>

              <div className="flex items-center gap-2 text-sm font-semibold pt-2"><MapPin className="h-4 w-4" />Default Delivery Address</div>
              <p className="text-xs text-muted-foreground -mt-2">Used to pre-fill checkout. You can still edit it per order.</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="sm:col-span-2"><Label className="text-xs text-muted-foreground">Address Line 1</Label><Input value={form.address_line1} onChange={(e) => upd('address_line1', e.target.value)} /></div>
                <div className="sm:col-span-2"><Label className="text-xs text-muted-foreground">Address Line 2</Label><Input value={form.address_line2} onChange={(e) => upd('address_line2', e.target.value)} /></div>
                <div><Label className="text-xs text-muted-foreground">City</Label><Input value={form.city} onChange={(e) => upd('city', e.target.value)} /></div>
                <div><Label className="text-xs text-muted-foreground">State</Label><Input value={form.state} onChange={(e) => upd('state', e.target.value)} /></div>
                <div><Label className="text-xs text-muted-foreground">Pincode</Label><Input value={form.pincode} onChange={(e) => upd('pincode', e.target.value.replace(/[^0-9]/g, ''))} maxLength={6} /></div>
                <div><Label className="text-xs text-muted-foreground">Landmark</Label><Input value={form.landmark} onChange={(e) => upd('landmark', e.target.value)} /></div>
                <div className="sm:col-span-2"><Label className="text-xs text-muted-foreground">GST Number (optional, for business orders)</Label><Input value={form.gst_number} onChange={(e) => upd('gst_number', e.target.value)} /></div>
              </div>
              <div className="flex justify-end"><Button type="submit" disabled={savingProfile} data-testid="account-save-profile">{savingProfile ? 'Saving...' : 'Save Profile'}</Button></div>
            </form>

            <form onSubmit={saveEmail} className="bg-card border border-border rounded-2xl p-5 space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold"><Mail className="h-4 w-4" />Change Email</div>
              <div className="grid gap-3 sm:grid-cols-[1fr_auto] items-end">
                <div><Label className="text-xs text-muted-foreground">New Email</Label><Input required type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} data-testid="account-email-input" /></div>
                <Button type="submit" disabled={savingEmail} data-testid="account-save-email">{savingEmail ? 'Updating...' : 'Update Email'}</Button>
              </div>
            </form>

            <form onSubmit={changePassword} className="bg-card border border-border rounded-2xl p-5 space-y-4" autoComplete="off">
              <div className="flex items-center gap-2 text-sm font-semibold"><LockKeyhole className="h-4 w-4" />Change Password</div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div><Label className="text-xs text-muted-foreground">Current Password</Label><PasswordInput required autoComplete="off" value={pw.current_password} onChange={(e) => setPw(p => ({ ...p, current_password: e.target.value }))} /></div>
                <div><Label className="text-xs text-muted-foreground">New Password</Label><PasswordInput required autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw(p => ({ ...p, new_password: e.target.value }))} /></div>
                <div><Label className="text-xs text-muted-foreground">Confirm New Password</Label><PasswordInput required autoComplete="new-password" value={pw.confirm} onChange={(e) => setPw(p => ({ ...p, confirm: e.target.value }))} /></div>
              </div>
              <div className="flex justify-end"><Button type="submit" disabled={savingPw} data-testid="account-save-password">{savingPw ? 'Updating...' : 'Update Password'}</Button></div>
            </form>
          </div>

          <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
            <div className="flex items-center gap-2 text-sm font-semibold"><Package className="h-4 w-4" />Order History</div>
            {loadingOrders ? (
              <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16 rounded-xl" />)}</div>
            ) : orders.length === 0 ? (
              <p className="text-sm text-muted-foreground">No orders yet.</p>
            ) : (
              <div className="space-y-2 max-h-[520px] overflow-auto pr-1">
                {orders.map(o => (
                  <Link key={o.id} to={`/track/${o.id}`} state={{ mobile: o.address?.mobile }} className="block rounded-xl border border-border p-3 hover:border-primary/40 transition-colors" data-testid={`account-order-${o.id}`}>
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-mono text-xs text-muted-foreground truncate">{o.id}</div>
                      <Badge variant="outline" className={`shrink-0 ${statusColor[o.status] || ''}`}>{o.status}</Badge>
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <div className="text-xs text-muted-foreground">{o.created_at?.slice(0, 10)} · {o.items?.length} item(s)</div>
                      <div className="text-sm font-semibold">{formatINR(o.total)}</div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </Container>
    </Section>
  );
}
