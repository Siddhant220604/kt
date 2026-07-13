import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';
import { ShieldCheck, Mail, LockKeyhole, Clock3, ArrowRight } from 'lucide-react';

export default function AdminProfile() {
  const [user, setUser] = useState(null);
  const [loginHistory, setLoginHistory] = useState([]);
  const [email, setEmail] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [savingEmail, setSavingEmail] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    api.get('/admin/profile').then((res) => {
      setUser(res.data);
      setEmail(res.data.email);
    }).catch(() => toast.error('Unable to load profile'));
    api.get('/admin/login-history').then((res) => setLoginHistory(res.data)).catch(() => {});
  }, []);

  const saveEmail = async () => {
    setSavingEmail(true);
    try {
      await api.post('/admin/profile/email', { email });
      toast.success('Email updated');
      setUser((prev) => ({ ...prev, email }));
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Save failed');
    } finally {
      setSavingEmail(false);
    }
  };

  const savePassword = async () => {
    if (newPassword !== confirmPassword) {
      return toast.error('Passwords do not match');
    }
    setSavingPassword(true);
    try {
      const { data } = await api.post('/admin/profile/password', { current_password: currentPassword, new_password: newPassword, confirm_password: confirmPassword });
      if (data?.token) {
        localStorage.setItem('kt_admin_token', data.token);
      }
      toast.success('Password changed');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Change failed');
    } finally {
      setSavingPassword(false);
    }
  };

  const logoutAll = async () => {
    setLoggingOut(true);
    try {
      await api.post('/admin/profile/logout-all');
      localStorage.removeItem('kt_admin_token');
      window.location.href = '/admin/login';
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Unable to logout');
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-display font-bold">Admin Profile</h1>
        <p className="text-sm text-muted-foreground">Manage your account, security, and active sessions.</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          <div className="bg-card border border-border rounded-2xl p-5 space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold"><Mail className="h-4 w-4" /> Account details</div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div><Label>Name</Label><Input value={user?.name || ''} disabled /></div>
              <div><Label>Role</Label><Input value={user?.role || ''} disabled /></div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div><Label>Email</Label><Input value={email} onChange={(e) => setEmail(e.target.value)} /></div>
              <div className="flex items-end justify-end"><Button onClick={saveEmail} disabled={savingEmail}>{savingEmail ? 'Saving...' : 'Update email'}</Button></div>
            </div>
          </div>

          <div className="bg-card border border-border rounded-2xl p-5 space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold"><LockKeyhole className="h-4 w-4" /> Change password</div>
            <div className="grid gap-3">
              <div><Label>Current password</Label><Input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} /></div>
              <div><Label>New password</Label><Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} /></div>
              <div><Label>Confirm password</Label><Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} /></div>
              <div className="flex justify-end"><Button onClick={savePassword} disabled={savingPassword}>{savingPassword ? 'Updating...' : 'Update password'}</Button></div>
            </div>
          </div>

          <div className="bg-card border border-border rounded-2xl p-5 space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold"><ShieldCheck className="h-4 w-4" /> Security actions</div>
            <p className="text-sm text-muted-foreground">Invalidate all active admin sessions and force re-login on all devices.</p>
            <div className="flex justify-end"><Button variant="destructive" onClick={logoutAll} disabled={loggingOut}>{loggingOut ? 'Logging out...' : 'Logout all devices'}</Button></div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold"><Clock3 className="h-4 w-4" /> Recent logins</div>
              <div className="text-xs text-muted-foreground">Last 50</div>
            </div>
            <div className="space-y-3">
              {loginHistory.length === 0 && <div className="rounded-xl border border-border p-4 text-sm text-muted-foreground">No recent login activity found.</div>}
              {loginHistory.map((item) => (
                <div key={item.id} className="rounded-xl border border-border p-4">
                  <div className="flex items-center justify-between gap-2 text-sm"><span>{item.timestamp?.slice(0, 19).replace('T', ' ')}</span><span className="text-muted-foreground">{item.ip_address}</span></div>
                  <div className="text-xs text-muted-foreground">{item.action}</div>
                  <div className="mt-2 text-xs text-muted-foreground"><span className="inline-flex items-center gap-1"><ArrowRight className="h-3.5 w-3.5" /> {item.details?.new_email || 'Login event'}</span></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
