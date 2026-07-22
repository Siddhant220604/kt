import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { PasswordInput } from '../components/ui/password-input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { User, MapPin, Mail, LockKeyhole, LogOut, Package, Plus, Pencil, Trash2, Star } from 'lucide-react';
import { toast } from 'sonner';
import { api, formatINR, logoutCustomer } from '../lib/api';
import { useWishlist } from '../lib/wishlist';

const statusColor = { pending: 'bg-amber-500/10 text-amber-700 border-amber-500/20', confirmed: 'bg-sky-500/10 text-sky-700 border-sky-500/20', processing: 'bg-cyan-500/10 text-cyan-700 border-cyan-500/20', packed: 'bg-indigo-500/10 text-indigo-700 border-indigo-500/20', 'out for delivery': 'bg-purple-500/10 text-purple-700 border-purple-500/20', delivered: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20', cancelled: 'bg-red-500/10 text-red-700 border-red-500/20' };

const emptyProfile = { name: '', email: '', mobile: '' };
const emptyAddress = { label: '', name: '', mobile: '', address_line1: '', address_line2: '', city: '', state: '', pincode: '', landmark: '', gst_number: '', is_default: false };

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
  const [addresses, setAddresses] = useState([]);
  const [loadingAddresses, setLoadingAddresses] = useState(true);
  const [addrForm, setAddrForm] = useState(null); // null = hidden, object = editing/adding
  const [editingId, setEditingId] = useState(null);
  const [savingAddr, setSavingAddr] = useState(false);

  const loadAddresses = () => {
    setLoadingAddresses(true);
    api.get('/customer/addresses').then(({ data }) => setAddresses(data || [])).finally(() => setLoadingAddresses(false));
  };

  useEffect(() => {
    api.get('/customer/profile').then(({ data }) => {
      setProfile(data);
      setForm({ ...emptyProfile, ...data });
      setNewEmail(data.email || '');
    }).catch(() => toast.error('Unable to load profile'));
    api.get('/customer/orders').then(({ data }) => setOrders(data)).finally(() => setLoadingOrders(false));
    loadAddresses();
  }, []);

  const upd = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const updAddr = (k, v) => setAddrForm(f => ({ ...f, [k]: v }));

  const saveProfile = async (e) => {
    e.preventDefault();
    setSavingProfile(true);
    try {
      const { name, mobile } = form;
      const { data } = await api.put('/customer/profile', { name, mobile });
      setProfile(data);
      localStorage.setItem('kt_customer_name', data.name);
      toast.success('Profile updated');
    } catch (err) { toast.error(err.response?.data?.detail || 'Update failed'); }
    finally { setSavingProfile(false); }
  };

  const startAddAddress = () => { setEditingId(null); setAddrForm({ ...emptyAddress, name: profile.name || '', mobile: profile.mobile || '' }); };
  const startEditAddress = (a) => { setEditingId(a.id); setAddrForm({ ...emptyAddress, ...a }); };
  const cancelAddress = () => { setAddrForm(null); setEditingId(null); };

  const saveAddress = async (e) => {
    e.preventDefault();
    if (!/^[6-9]\d{9}$/.test(addrForm.mobile)) return toast.error('Enter a valid 10-digit mobile number');
    if (!addrForm.pincode || addrForm.pincode.length !== 6) return toast.error('Enter a valid 6-digit pincode');
    setSavingAddr(true);
    try {
      try {
        const { data: check } = await api.get(`/pincode/${addrForm.pincode}/verify`);
        if (check.valid === false) {
          toast.error(check.reason === 'outside_lucknow' ? 'Sorry, we only deliver within Lucknow. Please enter a Lucknow pincode.' : 'Enter a valid pincode - this pincode does not exist');
          return;
        }
      } catch { /* lookup unavailable - fail open, don't block saving the address */ }
      const { data } = editingId
        ? await api.put(`/customer/addresses/${editingId}`, addrForm)
        : await api.post('/customer/addresses', addrForm);
      setAddresses(data);
      cancelAddress();
      toast.success(editingId ? 'Address updated' : 'Address added');
    } catch (err) { toast.error(err.response?.data?.detail || 'Save failed'); }
    finally { setSavingAddr(false); }
  };

  const deleteAddress = async (id) => {
    try {
      const { data } = await api.delete(`/customer/addresses/${id}`);
      setAddresses(data);
      toast.success('Address removed');
    } catch (err) { toast.error(err.response?.data?.detail || 'Delete failed'); }
  };

  const makeDefaultAddress = async (id) => {
    try {
      const { data } = await api.post(`/customer/addresses/${id}/default`);
      setAddresses(data);
    } catch (err) { toast.error(err.response?.data?.detail || 'Update failed'); }
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
              <div className="flex justify-end"><Button type="submit" disabled={savingProfile} data-testid="account-save-profile">{savingProfile ? 'Saving...' : 'Save Profile'}</Button></div>
            </form>

            <div className="bg-card border border-border rounded-2xl p-5 space-y-4">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-semibold"><MapPin className="h-4 w-4" />Saved Addresses</div>
                {!addrForm && <Button type="button" size="sm" variant="outline" className="gap-1" onClick={startAddAddress} data-testid="account-add-address"><Plus className="h-3.5 w-3.5" />Add Address</Button>}
              </div>

              {loadingAddresses ? (
                <div className="space-y-2">{Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}</div>
              ) : addresses.length === 0 && !addrForm ? (
                <p className="text-sm text-muted-foreground">No saved addresses yet. Add one to speed up checkout.</p>
              ) : (
                <div className="space-y-2">
                  {addresses.map(a => (
                    <div key={a.id} className="border border-border rounded-xl p-3 text-sm" data-testid={`account-address-${a.id}`}>
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium">{a.label || 'Address'}</span>
                            {a.is_default && <Badge variant="outline" className="text-[10px] gap-1"><Star className="h-2.5 w-2.5 fill-current" />Default</Badge>}
                          </div>
                          <div className="text-muted-foreground text-xs mt-1">{a.name} · {a.mobile}</div>
                          <div className="text-muted-foreground text-xs">{a.address_line1}{a.address_line2 ? `, ${a.address_line2}` : ''}, {a.city}, {a.state} - {a.pincode}</div>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <button type="button" className="p-1.5 hover:bg-muted rounded" onClick={() => startEditAddress(a)} title="Edit"><Pencil className="h-3.5 w-3.5" /></button>
                          <button type="button" className="p-1.5 hover:bg-destructive/10 text-destructive rounded" onClick={() => deleteAddress(a.id)} title="Delete"><Trash2 className="h-3.5 w-3.5" /></button>
                        </div>
                      </div>
                      {!a.is_default && <button type="button" className="text-xs text-primary hover:underline mt-2" onClick={() => makeDefaultAddress(a.id)}>Set as default</button>}
                    </div>
                  ))}
                </div>
              )}

              {addrForm && (
                <form onSubmit={saveAddress} className="border-t border-border pt-4 space-y-3">
                  <div className="text-sm font-medium">{editingId ? 'Edit Address' : 'New Address'}</div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div><Label className="text-xs text-muted-foreground">Label (e.g. Home, Shop)</Label><Input value={addrForm.label} onChange={(e) => updAddr('label', e.target.value)} /></div>
                    <div><Label className="text-xs text-muted-foreground">Mobile Number</Label><Input required inputMode="numeric" maxLength={10} value={addrForm.mobile} onChange={(e) => updAddr('mobile', e.target.value.replace(/[^0-9]/g, ''))} /></div>
                    <div className="sm:col-span-2"><Label className="text-xs text-muted-foreground">Recipient Name</Label><Input required value={addrForm.name} onChange={(e) => updAddr('name', e.target.value)} /></div>
                    <div className="sm:col-span-2"><Label className="text-xs text-muted-foreground">Address Line 1</Label><Input required value={addrForm.address_line1} onChange={(e) => updAddr('address_line1', e.target.value)} /></div>
                    <div className="sm:col-span-2"><Label className="text-xs text-muted-foreground">Address Line 2</Label><Input value={addrForm.address_line2} onChange={(e) => updAddr('address_line2', e.target.value)} /></div>
                    <div><Label className="text-xs text-muted-foreground">City</Label><Input required value={addrForm.city} onChange={(e) => updAddr('city', e.target.value)} /></div>
                    <div><Label className="text-xs text-muted-foreground">State</Label><Input required value={addrForm.state} onChange={(e) => updAddr('state', e.target.value)} /></div>
                    <div><Label className="text-xs text-muted-foreground">Pincode</Label><Input required value={addrForm.pincode} onChange={(e) => updAddr('pincode', e.target.value.replace(/[^0-9]/g, ''))} maxLength={6} /></div>
                    <div><Label className="text-xs text-muted-foreground">Landmark</Label><Input value={addrForm.landmark} onChange={(e) => updAddr('landmark', e.target.value)} /></div>
                    <div className="sm:col-span-2"><Label className="text-xs text-muted-foreground">GST Number (optional, for business orders)</Label><Input value={addrForm.gst_number || ''} onChange={(e) => updAddr('gst_number', e.target.value)} /></div>
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button type="button" variant="outline" onClick={cancelAddress}>Cancel</Button>
                    <Button type="submit" disabled={savingAddr}>{savingAddr ? 'Saving...' : editingId ? 'Save Changes' : 'Add Address'}</Button>
                  </div>
                </form>
              )}
            </div>

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
