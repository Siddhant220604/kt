import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';
import { Store, LockKeyhole } from 'lucide-react';

export default function AdminLogin() {
  const nav = useNavigate();
  const [form, setForm] = useState({ email: 'admin@kirantraders.com', password: 'Admin@123' });
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault(); setLoading(true);
    try {
      const { data } = await api.post('/auth/login', form);
      localStorage.setItem('kt_admin_token', data.token);
      toast.success('Welcome back!');
      nav('/admin/dashboard');
    } catch (e) { toast.error(e.response?.data?.detail || 'Login failed'); }
    finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen grid place-items-center bg-muted/30 p-4 hero-radial">
      <form onSubmit={submit} className="w-full max-w-sm bg-card border border-border rounded-2xl p-6 shadow-lg">
        <div className="flex items-center gap-2 mb-4">
          <span className="h-11 w-11 rounded-xl bg-primary text-primary-foreground grid place-items-center font-display font-bold">KT</span>
          <div>
            <div className="font-display font-bold text-lg leading-tight">Kiran Traders</div>
            <div className="text-xs text-muted-foreground">Admin Panel</div>
          </div>
        </div>
        <div className="space-y-3">
          <div>
            <Label className="text-xs text-muted-foreground">Email</Label>
            <Input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="admin-email-input" />
          </div>
          <div>
            <Label className="text-xs text-muted-foreground">Password</Label>
            <Input required type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="admin-password-input" />
          </div>
          <Button type="submit" disabled={loading} className="w-full gap-2" data-testid="admin-login-submit">
            <LockKeyhole className="h-4 w-4" /> {loading ? 'Signing in...' : 'Sign in'}
          </Button>
        </div>
      </form>
    </div>
  );
}
