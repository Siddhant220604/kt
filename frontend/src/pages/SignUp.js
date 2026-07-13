import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { PasswordInput } from '../components/ui/password-input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { UserPlus } from 'lucide-react';
import { api } from '../lib/api';

export default function SignUp() {
  const nav = useNavigate();
  const loc = useLocation();
  const [form, setForm] = useState({ name: '', email: '', mobile: '', password: '', confirm: '' });
  const [loading, setLoading] = useState(false);

  const upd = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) return toast.error('Enter your name');
    if (!/^[6-9]\d{9}$/.test(form.mobile)) return toast.error('Enter a valid 10-digit mobile number');
    if (form.password.length < 6) return toast.error('Password must be at least 6 characters');
    if (form.password !== form.confirm) return toast.error('Passwords do not match');
    setLoading(true);
    try {
      const { data } = await api.post('/customer/auth/signup', {
        name: form.name.trim(), email: form.email.trim().toLowerCase(), mobile: form.mobile, password: form.password,
      });
      localStorage.setItem('kt_customer_token', data.token);
      localStorage.setItem('kt_customer_name', data.name);
      localStorage.setItem('kt_customer_email', data.email);
      toast.success(`Welcome, ${data.name}!`);
      nav(loc.state?.from?.pathname || '/account', { replace: true, state: loc.state?.from?.state });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Sign up failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Section>
      <Container className="max-w-md">
        <form onSubmit={submit} className="bg-card border border-border rounded-2xl p-6 shadow-sm" autoComplete="off">
          <div className="h-12 w-12 rounded-full bg-primary/10 grid place-items-center mx-auto"><UserPlus className="h-6 w-6 text-primary" /></div>
          <h1 className="text-xl font-display font-bold text-center mt-3">Create your account</h1>
          <p className="text-sm text-muted-foreground text-center mt-1">Sign up to place an order and track your purchase history.</p>
          <div className="mt-5 space-y-3">
            <div><Label className="text-xs text-muted-foreground">Full Name</Label><Input required autoComplete="name" value={form.name} onChange={(e) => upd('name', e.target.value)} data-testid="signup-name-input" /></div>
            <div><Label className="text-xs text-muted-foreground">Email</Label><Input required type="email" autoComplete="off" value={form.email} onChange={(e) => upd('email', e.target.value)} data-testid="signup-email-input" /></div>
            <div><Label className="text-xs text-muted-foreground">Mobile Number</Label><Input required inputMode="numeric" maxLength={10} autoComplete="off" value={form.mobile} onChange={(e) => upd('mobile', e.target.value.replace(/[^0-9]/g, ''))} data-testid="signup-mobile-input" /></div>
            <div><Label className="text-xs text-muted-foreground">Password</Label><PasswordInput required autoComplete="new-password" value={form.password} onChange={(e) => upd('password', e.target.value)} data-testid="signup-password-input" /></div>
            <div><Label className="text-xs text-muted-foreground">Confirm Password</Label><PasswordInput required autoComplete="new-password" value={form.confirm} onChange={(e) => upd('confirm', e.target.value)} data-testid="signup-confirm-input" /></div>
            <Button type="submit" className="w-full" disabled={loading} data-testid="signup-submit">{loading ? 'Creating account...' : 'Create Account'}</Button>
          </div>
          <p className="text-sm text-center text-muted-foreground mt-4">
            Already have an account? <Link to="/signin" state={loc.state} className="text-primary hover:underline font-medium">Sign in</Link>
          </p>
        </form>
      </Container>
    </Section>
  );
}
