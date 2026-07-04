import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", company: "" });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true); setErr("");
    try {
      await register(form);
      toast.success("Account created");
      navigate("/");
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-md px-4 py-16 sm:px-6">
      <div className="label-caps mb-2">Create account</div>
      <h1 className="text-3xl font-black tracking-tighter">Open a B2B account</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Instant activation. Volume pricing unlocks on your first quote.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-4 border border-border bg-card p-6" data-testid="register-form">
        <div>
          <Label htmlFor="name" className="label-caps">Full name</Label>
          <Input id="name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-2 rounded-sm" data-testid="register-name-input" />
        </div>
        <div>
          <Label htmlFor="company" className="label-caps">Company</Label>
          <Input id="company" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} className="mt-2 rounded-sm" data-testid="register-company-input" />
        </div>
        <div>
          <Label htmlFor="email" className="label-caps">Business email</Label>
          <Input id="email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="mt-2 rounded-sm" data-testid="register-email-input" />
        </div>
        <div>
          <Label htmlFor="password" className="label-caps">Password</Label>
          <Input id="password" type="password" required minLength={6} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="mt-2 rounded-sm" data-testid="register-password-input" />
        </div>
        {err && (
          <div className="border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive" data-testid="register-error">
            {err}
          </div>
        )}
        <Button type="submit" className="w-full rounded-sm btn-lift" disabled={loading} data-testid="register-submit-button">
          {loading ? "Creating…" : "Create account"}
        </Button>
      </form>

      <p className="mt-4 text-center text-sm text-muted-foreground">
        Already have one?{" "}
        <Link to="/login" className="font-medium text-primary hover:underline" data-testid="register-login-link">
          Sign in
        </Link>
      </p>
    </div>
  );
}
