import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { PasswordInput } from '../components/ui/password-input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { KeyRound } from 'lucide-react';
import { api } from '../lib/api';
import { useWishlist } from '../lib/wishlist';

export default function ForgotPassword() {
  const nav = useNavigate();
  const { syncAfterLogin } = useWishlist();
  const [step, setStep] = useState('request');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const requestCode = async (e) => {
    e.preventDefault();
    if (!email.trim()) return toast.error('Enter your email address');
    setLoading(true);
    try {
      await api.post('/customer/auth/forgot-password', { email: email.trim().toLowerCase() });
      toast.success('If an account exists for this email, a reset code has been sent via WhatsApp.');
      setStep('reset');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const resetPassword = async (e) => {
    e.preventDefault();
    if (!otp.trim() || otp.trim().length !== 6) return toast.error('Enter the 6-digit code sent via WhatsApp');
    if (newPassword.length < 6) return toast.error('New password must be at least 6 characters');
    if (newPassword !== confirmPassword) return toast.error('Passwords do not match');
    setLoading(true);
    try {
      const { data } = await api.post('/customer/auth/reset-password', {
        email: email.trim().toLowerCase(),
        otp: otp.trim(),
        new_password: newPassword,
      });
      localStorage.setItem('kt_customer_token', data.token);
      localStorage.setItem('kt_customer_name', data.name);
      localStorage.setItem('kt_customer_email', data.email);
      syncAfterLogin();
      toast.success('Password reset successfully!');
      nav('/account', { replace: true });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Invalid or expired reset code');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Section>
      <Container className="max-w-md">
        <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
          <div className="h-12 w-12 rounded-full bg-primary/10 grid place-items-center mx-auto"><KeyRound className="h-6 w-6 text-primary" /></div>
          <h1 className="text-xl font-display font-bold text-center mt-3">Reset password</h1>

          {step === 'request' ? (
            <form onSubmit={requestCode} autoComplete="off">
              <p className="text-sm text-muted-foreground text-center mt-1">Enter your account email and we'll send a reset code to your registered WhatsApp number.</p>
              <div className="mt-5 space-y-3">
                <div><Label className="text-xs text-muted-foreground">Email</Label><Input required type="email" autoComplete="off" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="forgot-password-email-input" /></div>
                <Button type="submit" className="w-full" disabled={loading} data-testid="forgot-password-submit">{loading ? 'Sending...' : 'Send reset code'}</Button>
              </div>
            </form>
          ) : (
            <form onSubmit={resetPassword} autoComplete="off">
              <p className="text-sm text-muted-foreground text-center mt-1">Enter the 6-digit code sent to your WhatsApp, then choose a new password.</p>
              <div className="mt-5 space-y-3">
                <div><Label className="text-xs text-muted-foreground">Reset code</Label><Input required inputMode="numeric" maxLength={6} autoComplete="off" value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))} data-testid="reset-password-otp-input" /></div>
                <div><Label className="text-xs text-muted-foreground">New password</Label><PasswordInput required autoComplete="new-password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} data-testid="reset-password-new-input" /></div>
                <div><Label className="text-xs text-muted-foreground">Confirm new password</Label><PasswordInput required autoComplete="new-password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} data-testid="reset-password-confirm-input" /></div>
                <Button type="submit" className="w-full" disabled={loading} data-testid="reset-password-submit">{loading ? 'Resetting...' : 'Reset password'}</Button>
                <button type="button" className="text-xs text-primary hover:underline w-full text-center" onClick={requestCode} disabled={loading}>Resend code</button>
              </div>
            </form>
          )}

          <p className="text-sm text-center text-muted-foreground mt-4">
            Remembered your password? <Link to="/signin" className="text-primary hover:underline font-medium">Sign in</Link>
          </p>
        </div>
      </Container>
    </Section>
  );
}
