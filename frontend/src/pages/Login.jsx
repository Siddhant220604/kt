import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from || "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true); setErr("");
    try {
      const user = await login(email, password);
      toast.success(`Welcome back, ${user.name}`);
      navigate(user.role === "admin" ? "/admin" : from);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-md px-4 py-16 sm:px-6">
      <div className="label-caps mb-2">Sign in</div>
      <h1 className="text-3xl font-black tracking-tighter">Welcome back</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Access tier pricing and manage your wholesale orders.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-4 border border-border bg-card p-6" data-testid="login-form">
        <div>
          <Label htmlFor="email" className="label-caps">Email</Label>
          <Input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="mt-2 rounded-sm"
            data-testid="login-email-input"
          />
        </div>
        <div>
          <Label htmlFor="password" className="label-caps">Password</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="mt-2 rounded-sm"
            data-testid="login-password-input"
          />
        </div>
        {err && (
          <div className="border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive" data-testid="login-error">
            {err}
          </div>
        )}
        <Button
          type="submit"
          className="w-full rounded-sm btn-lift"
          disabled={loading}
          data-testid="login-submit-button"
        >
          {loading ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <p className="mt-4 text-center text-sm text-muted-foreground">
        No account?{" "}
        <Link to="/register" className="font-medium text-primary hover:underline" data-testid="login-register-link">
          Create one
        </Link>
      </p>
      <p className="mt-6 text-center text-xs text-muted-foreground">
        Demo · admin@wholesale.com / admin123 · buyer@wholesale.com / buyer123
      </p>
    </div>
  );
}
