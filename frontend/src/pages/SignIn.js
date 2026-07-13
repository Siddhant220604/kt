import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { LockKeyhole } from 'lucide-react';
import { api } from '../lib/api';

export default function SignIn() {
  const nav = useNavigate();
  const loc = useLocation();
  const [form, setForm] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.email.trim() || !form.password) return toast.error('Enter your email and password');
    setLoading(true);
    try {
      const { data } = await api.post('/customer/auth/login', { email: form.email.trim().toLowerCase(), password: form.password });
      localStorage.setItem('kt_customer_token', data.token);
      localStorage.setItem('kt_customer_name', data.name);
      localStorage.setItem('kt_customer_email', data.email);
      toast.success(`Welcome back, ${data.name}!`);
      nav(loc.state?.from?.pathname || '/account', { replace: true, state: loc.state?.from?.state });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Invalid email or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Section>
      <Container className="max-w-md">
        <form onSubmit={submit} className="bg-card border border-border rounded-2xl p-6 shadow-sm" autoComplete="off">
          <div className="h-12 w-12 rounded-full bg-primary/10 grid place-items-center mx-auto"><LockKeyhole className="h-6 w-6 text-primary" /></div>
          <h1 className="text-xl font-display font-bold text-center mt-3">Sign in</h1>
          <p className="text-sm text-muted-foreground text-center mt-1">Log in to continue to checkout and view your orders.</p>
          <div className="mt-5 space-y-3">
            <div><Label className="text-xs text-muted-foreground">Email</Label><Input required type="email" autoComplete="off" value={form.email} onChange={(e) => setForm(f => ({ ...f, email: e.target.value }))} data-testid="signin-email-input" /></div>
            <div><Label className="text-xs text-muted-foreground">Password</Label><Input required type="password" autoComplete="off" value={form.password} onChange={(e) => setForm(f => ({ ...f, password: e.target.value }))} data-testid="signin-password-input" /></div>
            <Button type="submit" className="w-full" disabled={loading} data-testid="signin-submit">{loading ? 'Signing in...' : 'Sign in'}</Button>
          </div>
          <p className="text-sm text-center text-muted-foreground mt-4">
            Don't have an account? <Link to="/signup" state={loc.state} className="text-primary hover:underline font-medium">Sign up</Link>
          </p>
        </form>
      </Container>
    </Section>
  );
}
